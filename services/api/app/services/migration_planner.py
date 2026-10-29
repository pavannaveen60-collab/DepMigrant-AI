import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.services.nebius_client import nebius_client


class InvalidPlannerResponseError(ValueError):
    """Raised when a model's planning response does not match the requested format."""


class MigrationPlanner:
    MAX_MODEL_RESPONSE_CHARS = 256_000
    MAX_JSON_CANDIDATES = 256
    BREAKING_CHANGES_SCHEMA_INSTRUCTION = """Return only one complete JSON array matching this schema:
[
  {
    "type": "removed_api|changed_signature|behavior_change|config_incompatibility|transitive_conflict",
    "description": "Detailed description of the breaking change",
    "severity": "low|medium|high|critical",
    "source": "changelog|documentation|inference"
  }
]
Each item must contain exactly these four keys, with string values. The listed type, severity, and source values are the allowed enum values. Use [] if no changes are confidently known. Do not include Markdown fences, comments, or surrounding explanation."""
    RESPONSE_SCHEMAS = {
        "breaking changes": {
            "type": str,
            "description": str,
            "severity": str,
            "source": str,
        },
        "affected files": {
            "path": str,
            "reason": str,
            "estimated_changes": int,
        },
        "planned edits": {
            "file_path": str,
            "original_code": str,
            "new_code": str,
            "description": str,
        },
    }

    def __init__(self):
        self.client = nebius_client

    @staticmethod
    def _parse_json_array(content: str, stage: str) -> List[Dict[str, Any]]:
        if not isinstance(content, str):
            raise InvalidPlannerResponseError(
                f"The model returned an invalid {stage} response: expected text"
            )
        if len(content) > MigrationPlanner.MAX_MODEL_RESPONSE_CHARS:
            raise InvalidPlannerResponseError(
                f"The model returned an oversized {stage} response"
            )

        # Strip reasoning / thinking tokens (e.g. <think>...</think> or <thought>...</thought>)
        cleaned = re.sub(r"<think>.*?(?:</think>|$)", "", content, flags=re.DOTALL)
        cleaned = re.sub(r"<thought>.*?(?:</thought>|$)", "", cleaned, flags=re.DOTALL)

        # Check if there is an explicit fenced code block containing a JSON array or object
        fenced_array_matches = re.findall(
            r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", cleaned, re.IGNORECASE
        )
        target_contents = []
        if len(fenced_array_matches) == 1:
            target_contents.append(fenced_array_matches[0])
        else:
            fenced_any_matches = re.findall(
                r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE
            )
            if len(fenced_any_matches) == 1:
                target_contents.append(fenced_any_matches[0])
            target_contents.append(cleaned)

        last_error: Optional[Exception] = None
        for target in target_contents:
            decoder = json.JSONDecoder()
            candidates = []
            candidate_attempts = 0
            for start, character in enumerate(target):
                if character not in "[{":
                    continue
                candidate_attempts += 1
                if candidate_attempts > MigrationPlanner.MAX_JSON_CANDIDATES:
                    raise InvalidPlannerResponseError(
                        f"The model returned an overly complex {stage} response"
                    )
                try:
                    value, end = decoder.raw_decode(target, start)
                except (json.JSONDecodeError, RecursionError):
                    continue
                if isinstance(value, (list, dict)):
                    candidates.append((start, end, value))

            top_level_candidates = []
            enclosing_end = -1
            for candidate in sorted(candidates, key=lambda span: (span[0], -span[1])):
                if candidate[0] >= enclosing_end:
                    top_level_candidates.append(candidate)
                    enclosing_end = candidate[1]

            chosen_candidate = None
            if len(top_level_candidates) == 1 and isinstance(top_level_candidates[0][2], list):
                chosen_candidate = top_level_candidates[0][2]
            elif len(top_level_candidates) > 1:
                list_candidates = [
                    cand[2]
                    for cand in top_level_candidates
                    if isinstance(cand[2], list)
                    and (len(cand[2]) == 0 or all(isinstance(x, dict) for x in cand[2]))
                ]
                if len(list_candidates) == 1:
                    chosen_candidate = list_candidates[0]

            if chosen_candidate is None:
                last_error = InvalidPlannerResponseError(
                    f"The model returned an invalid {stage} response: "
                    "expected exactly one complete JSON array"
                )
                continue

            value = chosen_candidate
            schema = MigrationPlanner.RESPONSE_SCHEMAS.get(stage)
            if schema is None:
                raise ValueError(f"Unknown migration planning response stage: {stage}")

            try:
                for index, item in enumerate(value):
                    if not isinstance(item, dict):
                        raise InvalidPlannerResponseError(
                            f"The {stage} response item {index} must be a JSON object"
                        )
                    missing = schema.keys() - item.keys()
                    unexpected = item.keys() - schema.keys()
                    if missing:
                        raise InvalidPlannerResponseError(
                            f"The {stage} response item {index} is missing required fields"
                        )
                    if unexpected:
                        raise InvalidPlannerResponseError(
                            f"The {stage} response item {index} contains unexpected fields"
                        )
                    for field, expected_type in schema.items():
                        field_value = item[field]
                        if expected_type is int:
                            is_valid = type(field_value) is int and field_value >= 0
                        else:
                            is_valid = isinstance(field_value, expected_type)
                        if not is_valid:
                            raise InvalidPlannerResponseError(
                                f"The {stage} response item {index} has an invalid {field} field"
                            )

                    if stage == "breaking changes" and (
                        item["type"]
                        not in {
                            "removed_api",
                            "changed_signature",
                            "behavior_change",
                            "config_incompatibility",
                            "transitive_conflict",
                        }
                        or item["severity"] not in {"low", "medium", "high", "critical"}
                        or item["source"] not in {"changelog", "documentation", "inference"}
                    ):
                        raise InvalidPlannerResponseError(
                            f"The breaking changes response item {index} has an invalid enum field"
                        )

                    non_empty_fields = {
                        "breaking changes": ("type", "description", "severity", "source"),
                        "affected files": ("path", "reason"),
                        "planned edits": ("file_path", "description"),
                    }[stage]
                    if any(not item[field].strip() for field in non_empty_fields):
                        raise InvalidPlannerResponseError(
                            f"The {stage} response item {index} has an empty required field"
                        )
                    if stage in {"affected files", "planned edits"}:
                        path = item["path" if stage == "affected files" else "file_path"]
                        if path.startswith(("/", "\\")) or ".." in path.replace("\\", "/").split("/"):
                            raise InvalidPlannerResponseError(
                                f"The {stage} response item {index} has an unsafe path"
                            )
                return value
            except InvalidPlannerResponseError as val_err:
                last_error = val_err
                continue

        if last_error:
            raise last_error

        raise InvalidPlannerResponseError(
            f"The model returned an invalid {stage} response: "
            "expected exactly one complete JSON array"
        )
    
    async def create_plan(
        self,
        repo_inspection: Dict[str, Any],
        dependency_name: str,
        target_version: str,
        current_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a migration plan using the NVIDIA Nemotron model."""
        
        # Build context for the model
        context = self._build_context(repo_inspection, dependency_name, target_version, current_version)
        
        # Get breaking changes from model
        breaking_changes = await self._analyze_breaking_changes(context)
        
        # Get affected files
        affected_files = await self._identify_affected_files(context, breaking_changes)
        
        # Get planned edits
        planned_edits = await self._generate_edits(context, breaking_changes, affected_files)
        
        # Generate execution commands
        execution_commands = self._generate_execution_commands(repo_inspection, dependency_name, target_version)
        
        # Identify risks
        risks = self._identify_risks(breaking_changes, affected_files)
        
        return {
            "dependency": {
                "name": dependency_name,
                "current_version": current_version or "unknown",
                "target_version": target_version,
                "ecosystem": "pypi",
                "manifest_path": self._find_manifest_path(repo_inspection),
            },
            "breaking_changes": breaking_changes,
            "affected_files": affected_files,
            "planned_edits": planned_edits,
            "execution_commands": execution_commands,
            "risks": risks,
        }
    
    def _build_context(
        self,
        repo_inspection: Dict[str, Any],
        dependency_name: str,
        target_version: str,
        current_version: Optional[str],
    ) -> str:
        """Build context string for the model."""
        deps = repo_inspection.get("dependencies", {})
        pyproject = deps.get("pyproject_toml", {})
        
        context_parts = [
            f"Repository: {repo_inspection.get('name', 'unknown')}",
            f"Target dependency: {dependency_name}",
            f"Current version: {current_version or 'unknown'}",
            f"Target version: {target_version}",
            f"Python version: {repo_inspection.get('python_version', 'unknown')}",
            "",
            "Dependencies found:",
        ]
        
        if pyproject:
            if "dependencies" in pyproject:
                context_parts.append(f"  Main: {', '.join(pyproject['dependencies'][:20])}")
            if "optional_dependencies" in pyproject:
                optional_groups = list(pyproject["optional_dependencies"].items())
                for opt, dep_list in optional_groups[:10]:
                    context_parts.append(f"  [{opt}]: {', '.join(dep_list[:10])}")
                if len(optional_groups) > 10:
                    context_parts.append(
                        f"  ... and {len(optional_groups) - 10} optional groups omitted"
                    )
        
        if deps.get("requirements_txt"):
            context_parts.append(f"  requirements.txt: {', '.join(deps['requirements_txt'][:20])}")

        setup_py = deps.get("setup_py_dependencies") or {}
        if setup_py.get("dependencies"):
            context_parts.append(
                f"  setup.py: {', '.join(setup_py['dependencies'][:20])}"
            )
        optional_groups = list(setup_py.get("optional_dependencies", {}).items())
        for opt, dep_list in optional_groups[:10]:
            context_parts.append(f"  setup.py [{opt}]: {', '.join(dep_list[:10])}")
        if len(optional_groups) > 10:
            context_parts.append(
                f"  setup.py: ... and {len(optional_groups) - 10} optional groups omitted"
            )
        
        context_parts.extend([
            "",
            "Python files in repository:",
            f"  {len(repo_inspection.get('files', []))} files found",
        ])
        
        # Add first 20 files as context
        for f in repo_inspection.get("files", [])[:20]:
            context_parts.append(f"  - {f}")
        
        if len(repo_inspection.get("files", [])) > 20:
            context_parts.append(f"  ... and {len(repo_inspection['files']) - 20} more")
        
        return "\n".join(context_parts)
    
    async def _analyze_breaking_changes(self, context: str) -> List[Dict[str, Any]]:
        """Analyze breaking changes using the model."""
        prompt = f"""You are an expert Python dependency migration engineer. Analyze the breaking changes when upgrading a dependency.

{context}

Based on the repository context and the dependency upgrade, identify potential breaking changes. Consider:
1. Removed or renamed APIs
2. Changed function signatures
3. Behavior changes
4. Configuration incompatibilities
5. Transitive dependency conflicts

{self.BREAKING_CHANGES_SCHEMA_INSTRUCTION}"""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert Python dependency migration engineer. "
                    "Return exactly one complete JSON array and nothing else: "
                    "no Markdown fences, preamble, or trailing explanation."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        response = await self.client.chat_completion(messages)
        try:
            return self._parse_json_array(response["content"], "breaking changes")
        except InvalidPlannerResponseError:
            corrective_messages = [
                *messages,
                {
                    "role": "user",
                    "content": (
                        "Your previous response did not pass strict validation. "
                        "Regenerate the breaking changes response now. "
                        f"{self.BREAKING_CHANGES_SCHEMA_INSTRUCTION}"
                    ),
                },
            ]
            retry_response = await self.client.chat_completion(corrective_messages)
            try:
                return self._parse_json_array(
                    retry_response["content"], "breaking changes"
                )
            except InvalidPlannerResponseError as retry_error:
                raise InvalidPlannerResponseError(
                    "The model returned an invalid breaking changes response after "
                    "one corrective retry: expected exactly one complete JSON array "
                    "matching the requested schema. Retry or use a model that follows "
                    f"JSON-only instructions. Validation detail: {retry_error}"
                ) from retry_error
    
    async def _identify_affected_files(
        self,
        context: str,
        breaking_changes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Identify files likely affected by the migration."""
        prompt = f"""You are an expert Python dependency migration engineer. Identify files likely affected by the dependency upgrade.

{context}

Breaking changes identified:
{json.dumps(breaking_changes, indent=2)}

Based on the repository structure and breaking changes, identify files that likely need modification. Return a JSON array:
[
  {{
    "path": "relative/path/to/file.py",
    "reason": "Why this file is affected",
    "estimated_changes": 3
  }}
]

Each item must contain exactly path (string), reason (string), and estimated_changes (non-negative integer). If no files are confidently affected, return []. Do not include absolute paths or parent-directory traversal. Return exactly one complete JSON array with no surrounding text. Focus on files that import or use the target dependency and be conservative."""
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert Python dependency migration engineer. "
                    "Return exactly one complete JSON array and nothing else: "
                    "no Markdown fences, preamble, or trailing explanation."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        response = await self.client.chat_completion(messages)
        try:
            return self._parse_json_array(response["content"], "affected files")
        except InvalidPlannerResponseError:
            corrective_messages = [
                *messages,
                {
                    "role": "user",
                    "content": (
                        "Your previous response did not pass strict validation. "
                        "Regenerate the affected files response now as exactly one complete JSON array. "
                        "Each item must contain exactly path, reason, and estimated_changes. Use [] if no files are affected."
                    ),
                },
            ]
            retry_response = await self.client.chat_completion(corrective_messages)
            try:
                return self._parse_json_array(retry_response["content"], "affected files")
            except InvalidPlannerResponseError as retry_error:
                raise InvalidPlannerResponseError(
                    "The model returned an invalid affected files response after "
                    "one corrective retry: expected exactly one complete JSON array "
                    f"matching the requested schema. Validation detail: {retry_error}"
                ) from retry_error
    
    async def _generate_edits(
        self,
        context: str,
        breaking_changes: List[Dict[str, Any]],
        affected_files: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Generate specific code edits for the migration."""
        if not affected_files:
            return []
        
        prompt = f"""You are an expert Python dependency migration engineer. Generate specific code edits for the migration.

{context}

Breaking changes:
{json.dumps(breaking_changes, indent=2)}

Affected files:
{json.dumps(affected_files, indent=2)}

For each affected file, generate the specific code changes needed. Return a JSON array:
[
  {{
    "file_path": "relative/path/to/file.py",
    "original_code": "the exact code to replace",
    "new_code": "the new code",
    "description": "What this change does"
  }}
]

Each item must contain exactly file_path, original_code, new_code, and description, all strings. Do not include absolute paths or parent-directory traversal. If no safe, specific edits can be proposed, return []. The original_code must exactly match the current code in the file. Return exactly one complete JSON array with no surrounding text."""
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert Python dependency migration engineer. "
                    "Return exactly one complete JSON array and nothing else: "
                    "no Markdown fences, preamble, or trailing explanation."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        response = await self.client.chat_completion(messages)
        try:
            return self._parse_json_array(response["content"], "planned edits")
        except InvalidPlannerResponseError:
            corrective_messages = [
                *messages,
                {
                    "role": "user",
                    "content": (
                        "Your previous response did not pass strict validation. "
                        "Regenerate the planned edits response now as exactly one complete JSON array. "
                        "Each item must contain file_path, original_code, new_code, and description. "
                        "Use [] if no safe, specific edits can be proposed."
                    ),
                },
            ]
            retry_response = await self.client.chat_completion(corrective_messages)
            try:
                return self._parse_json_array(retry_response["content"], "planned edits")
            except InvalidPlannerResponseError as retry_error:
                raise InvalidPlannerResponseError(
                    "The model returned an invalid planned edits response after "
                    "one corrective retry: expected exactly one complete JSON array "
                    f"matching the requested schema. Validation detail: {retry_error}"
                ) from retry_error
    
    def _generate_execution_commands(
        self,
        repo_inspection: Dict[str, Any],
        dependency_name: str,
        target_version: str,
    ) -> List[List[str]]:
        """Generate execution commands for the migration."""
        commands = []
        
        # Check for uv
        if (Path(repo_inspection["path"]) / "uv.lock").exists():
            commands.append(["uv", "add", f"{dependency_name}=={target_version}"])
            commands.append(["uv", "sync"])
        # Check for poetry
        elif (Path(repo_inspection["path"]) / "poetry.lock").exists():
            commands.append(["poetry", "add", f"{dependency_name}=={target_version}"])
            commands.append(["poetry", "install"])
        # Check for pipenv
        elif (Path(repo_inspection["path"]) / "Pipfile.lock").exists():
            commands.append(["pipenv", "install", f"{dependency_name}=={target_version}"])
        # Default to pip
        else:
            commands.append(["pip", "install", f"{dependency_name}=={target_version}"])
        
        # Test commands
        test_config = repo_inspection.get("test_config", {})
        if test_config.get("pytest"):
            commands.append(["pytest", "-v"])
        else:
            commands.append(["python", "-m", "pytest", "-v"])
        
        return commands
    
    def _identify_risks(
        self,
        breaking_changes: List[Dict[str, Any]],
        affected_files: List[Dict[str, Any]],
    ) -> List[str]:
        """Identify migration risks."""
        risks = []
        
        critical_changes = [c for c in breaking_changes if c.get("severity") == "critical"]
        if critical_changes:
            risks.append(f"{len(critical_changes)} critical breaking changes detected")
        
        high_changes = [c for c in breaking_changes if c.get("severity") == "high"]
        if high_changes:
            risks.append(f"{len(high_changes)} high-severity breaking changes detected")
        
        if len(affected_files) > 10:
            risks.append(f"Large number of affected files ({len(affected_files)}) - higher chance of regressions")
        
        if not breaking_changes:
            risks.append("No specific breaking changes identified - unexpected issues may arise")
        
        return risks
    
    def _find_manifest_path(self, repo_inspection: Dict[str, Any]) -> str:
        """Find the primary dependency manifest path."""
        deps = repo_inspection.get("dependencies", {})
        if deps.get("pyproject_toml"):
            return "pyproject.toml"
        if deps.get("requirements_txt"):
            return "requirements.txt"
        if deps.get("setup_py"):
            return "setup.py"
        return "pyproject.toml"
