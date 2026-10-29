import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.services.nebius_client import nebius_client
from app.services.sandbox import CommandResult

class FailureDiagnoser:
    def __init__(self):
        self.client = nebius_client
    
    async def diagnose(
        self,
        failure: CommandResult,
        repo_context: Dict[str, Any],
        dependency_info: Dict[str, Any],
        previous_attempts: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Diagnose a failure and propose a repair."""
        
        # Classify failure type
        failure_type = self._classify_failure(failure)
        
        # Get relevant source context
        source_context = self._get_source_context(failure, repo_context)
        
        # Ask model for diagnosis
        diagnosis = await self._get_model_diagnosis(
            failure, failure_type, source_context, dependency_info, previous_attempts
        )
        
        return {
            "failure_type": failure_type,
            "diagnosis": diagnosis.get("diagnosis", ""),
            "proposed_patch": diagnosis.get("proposed_patch", []),
            "confidence": diagnosis.get("confidence", 0.5),
        }
    
    def _classify_failure(self, failure: CommandResult) -> str:
        """Classify the type of failure based on error output."""
        stderr = failure.stderr.lower()
        stdout = failure.stdout.lower()
        combined = stderr + " " + stdout
        
        # Dependency resolution errors
        if any(keyword in combined for keyword in [
            "resolution", "resolve", "dependency conflict", "version conflict",
            "no matching distribution", "could not find a version",
        ]):
            return "dependency_resolution"
        
        # Installation errors
        if any(keyword in combined for keyword in [
            "install", "pip install", "poetry add", "uv add",
            "error: ", "failed to install", "installation failed",
        ]):
            return "installation"
        
        # Syntax errors
        if any(keyword in combined for keyword in [
            "syntaxerror", "indentationerror", "taberror",
            "invalid syntax", "unexpected token",
        ]):
            return "syntax"
        
        # Import errors
        if any(keyword in combined for keyword in [
            "importerror", "modulenotfounderror", "no module named",
            "cannot import", "import failed",
        ]):
            return "import"
        
        # API incompatibility
        if any(keyword in combined for keyword in [
            "attributeerror", "typeerror", "argumenterror",
            "unexpected keyword", "missing argument", "got an unexpected",
            "deprecated", "removed", "no attribute",
        ]):
            return "api_incompatibility"
        
        # Configuration errors
        if any(keyword in combined for keyword in [
            "config", "configuration", "setting", "yaml", "toml",
            "invalid config", "configuration error",
        ]):
            return "configuration"
        
        # Test regressions
        if any(keyword in combined for keyword in [
            "pytest", "test", "assert", "failed", "error",
            "test_", "_test", "testsession",
        ]) and "passed" in combined and "failed" in combined:
            return "test_regression"
        
        # Runtime errors
        if any(keyword in combined for keyword in [
            "runtimeerror", "valueerror", "keyerror", "indexerror",
            "exception", "traceback", "error:",
        ]):
            return "runtime"
        
        # Environment errors
        if any(keyword in combined for keyword in [
            "permission denied", "not found", "command not found",
            "no such file", "environment", "path",
        ]):
            return "environment"
        
        return "unknown"
    
    def _get_source_context(
        self,
        failure: CommandResult,
        repo_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract relevant source code context for the failure."""
        context = {
            "error_output": failure.stderr[:5000] if failure.stderr else failure.stdout[:5000],
            "command": failure.command,
            "exit_code": failure.exit_code,
        }
        
        # Try to extract file paths from error
        import re
        file_paths = re.findall(r'([a-zA-Z0-9_\-./]+\.py)', failure.stderr + failure.stdout)
        context["mentioned_files"] = list(set(file_paths))[:10]
        
        # Get content of mentioned files
        file_contents = {}
        repository_root = Path(repo_context.get("path", "")).resolve()
        for file_path in context["mentioned_files"][:5]:
            full_path = (repository_root / file_path).resolve()
            try:
                full_path.relative_to(repository_root)
            except ValueError:
                continue
            if full_path.is_file():
                file_contents[file_path] = full_path.read_text()[:3000]
        
        context["file_contents"] = file_contents
        return context
    
    async def _get_model_diagnosis(
        self,
        failure: CommandResult,
        failure_type: str,
        source_context: Dict[str, Any],
        dependency_info: Dict[str, Any],
        previous_attempts: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get diagnosis and repair proposal from the model."""
        
        prompt = f"""You are an expert Python dependency migration engineer. Diagnose this failure and propose a minimal repair.

Failure type: {failure_type}
Command: {failure.command}
Exit code: {failure.exit_code}
Error output:
{failure.stderr[:3000] if failure.stderr else failure.stdout[:3000]}

Dependency being migrated: {dependency_info.get('name', 'unknown')}
Target version: {dependency_info.get('target_version', 'unknown')}

Relevant source context:
{json.dumps(source_context, indent=2)[:4000]}

Previous repair attempts:
{json.dumps(previous_attempts or [], indent=2)}

Provide a diagnosis and a minimal repair patch. Return JSON:
{{
  "diagnosis": "Clear explanation of what went wrong",
  "confidence": 0.8,
  "proposed_patch": [
    {{
      "file_path": "path/to/file.py",
      "original_code": "exact code to replace",
      "new_code": "new code",
      "description": "What this fixes"
    }}
  ]
}}

Only propose patches you are confident about. The original_code must exactly match the current file content.
If no repair is possible, return empty proposed_patch array."""
        
        response = await self.client.chat_completion([
            {"role": "system", "content": "You are an expert Python dependency migration engineer. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ])

        content = response["content"]
        start = content.find('{')
        end = content.rfind('}') + 1
        if start < 0 or end <= start:
            raise ValueError("The model returned an invalid diagnosis response")
        return json.loads(content[start:end])