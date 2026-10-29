import json
import ast
import os
import subprocess
import tempfile
import shutil
import tarfile
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import List, Dict, Any, Optional
from urllib.parse import urlsplit
from git import Repo
import toml


_IGNORED_DISCOVERY_DIRECTORIES = {
    "__pycache__",
    "benchmarks",
    "build",
    "dist",
    "docs",
    "env",
    "example",
    "examples",
    "fixtures",
    "node_modules",
    "samples",
    "site-packages",
    "test",
    "tests",
    "third-party",
    "third_party",
    "vendor",
    "vendors",
    "venv",
    "virtualenv",
    "virtualenvs",
}


class RepositoryInspector:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
    
    def inspect(self) -> Dict[str, Any]:
        """Inspect repository structure and return metadata."""
        result = {
            "name": self.repo_path.name,
            "path": str(self.repo_path),
            "type": "git" if (self.repo_path / ".git").exists() else "archive",
            "files": [],
            "dependencies": {},
            "test_config": {},
            "python_version": None,
        }
        
        # Get git info
        if result["type"] == "git":
            try:
                repo = Repo(self.repo_path)
                result["git"] = {
                    "branch": repo.active_branch.name,
                    "commit": repo.head.commit.hexsha,
                    "remote_url": repo.remotes.origin.url if repo.remotes else None,
                }
            except Exception:
                pass
        
        # Find Python files
        result["files"] = self._find_python_files()
        
        # Parse dependencies
        result["dependencies"] = self._parse_dependencies()
        
        # Find test configuration
        result["test_config"] = self._find_test_config()
        
        # Detect Python version
        result["python_version"] = self._detect_python_version()
        
        return result
    
    def _find_python_files(self) -> List[str]:
        """Find all Python files in the repository."""
        python_files = []
        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d.lower() not in _IGNORED_DISCOVERY_DIRECTORIES
            ]
            
            for file in files:
                if file.endswith('.py'):
                    rel_path = Path(root).relative_to(self.repo_path) / file
                    python_files.append(str(rel_path))
        return python_files
    
    def _parse_dependencies(self) -> Dict[str, Any]:
        """Parse dependency manifests."""
        deps = {
            "pyproject_toml": None,
            "requirements_txt": None,
            "setup_py": None,
            "setup_cfg": None,
            "lockfiles": [],
        }
        
        # pyproject.toml
        pyproject_path = self.repo_path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                with open(pyproject_path) as f:
                    data = toml.load(f)
                deps["pyproject_toml"] = self._extract_deps_from_pyproject(data)
            except Exception:
                pass
        
        # requirements.txt files, excluding generated, vendored, and auxiliary trees.
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [
                directory for directory in dirs
                if not directory.startswith(".")
                and directory.lower() not in _IGNORED_DISCOVERY_DIRECTORIES
            ]
            if "requirements.txt" not in files:
                continue
            req_path = Path(root) / "requirements.txt"
            try:
                with req_path.open(encoding="utf-8") as requirements_file:
                    declarations = [
                        line.strip()
                        for line in requirements_file
                        if line.strip() and not line.lstrip().startswith("#")
                    ]
                if deps["requirements_txt"] is None:
                    deps["requirements_txt"] = []
                deps["requirements_txt"].extend(declarations)
            except (OSError, UnicodeError):
                continue
        
        # setup.py
        setup_py = self.repo_path / "setup.py"
        if setup_py.exists():
            deps["setup_py"] = str(setup_py)
            deps["setup_py_dependencies"] = self._parse_setup_py(setup_py)
        
        # setup.cfg
        setup_cfg = self.repo_path / "setup.cfg"
        if setup_cfg.exists():
            deps["setup_cfg"] = str(setup_cfg)
        
        # Lockfiles
        for lockfile in ["poetry.lock", "Pipfile.lock", "requirements.lock", "uv.lock"]:
            lock_path = self.repo_path / lockfile
            if lock_path.exists():
                deps["lockfiles"].append(lockfile)
        
        return deps

    @staticmethod
    def _literal_string_sequence(node: ast.AST) -> Optional[List[str]]:
        try:
            value = ast.literal_eval(node)
        except (ValueError, TypeError, SyntaxError):
            return None
        if isinstance(value, (list, tuple)) and all(
            isinstance(item, str) for item in value
        ):
            return list(value)
        return None

    def _parse_setup_py(self, setup_path: Path) -> Dict[str, Any]:
        """Extract only literal setup() dependency declarations; never execute setup.py."""
        result: Dict[str, Any] = {
            "dependencies": [],
            "optional_dependencies": {},
        }
        try:
            tree = ast.parse(setup_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            return result

        literal_assignments: Dict[str, Any] = {}
        for statement in tree.body:
            if isinstance(statement, ast.Assign):
                targets = statement.targets
                value_node = statement.value
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
                value_node = statement.value
            else:
                continue
            if value_node is None:
                continue
            try:
                value = ast.literal_eval(value_node)
            except (ValueError, TypeError, SyntaxError):
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    literal_assignments[target.id] = value

        def literal_value(node: ast.AST) -> Any:
            if isinstance(node, ast.Name):
                return literal_assignments.get(node.id)
            try:
                return ast.literal_eval(node)
            except (ValueError, TypeError, SyntaxError):
                return None

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            is_setup_call = (
                isinstance(function, ast.Name) and function.id == "setup"
            ) or (
                isinstance(function, ast.Attribute) and function.attr == "setup"
            )
            if not is_setup_call:
                continue

            for keyword in node.keywords:
                if keyword.arg == "install_requires":
                    dependencies = self._literal_string_sequence(
                        ast.Constant(value=literal_value(keyword.value))
                        if isinstance(keyword.value, ast.Name)
                        and keyword.value.id in literal_assignments
                        else keyword.value
                    )
                    if dependencies is not None:
                        result["dependencies"].extend(dependencies)
                elif keyword.arg == "extras_require":
                    extras = literal_value(keyword.value)
                    if not isinstance(extras, dict):
                        continue
                    for extra, values in extras.items():
                        if (
                            not isinstance(extra, str)
                            or not isinstance(values, (list, tuple))
                            or not all(isinstance(item, str) for item in values)
                        ):
                            continue
                        result["optional_dependencies"].setdefault(
                            extra, []
                        ).extend(values)

        return result
    
    def _extract_deps_from_pyproject(self, data: Dict) -> Dict[str, Any]:
        """Extract dependencies from pyproject.toml."""
        result = {
            "project": data.get("project", {}),
            "dependencies": [],
            "optional_dependencies": {},
            "build_system": data.get("build-system", {}),
        }
        
        project = data.get("project", {})
        if "dependencies" in project:
            result["dependencies"] = project["dependencies"]
        if "optional-dependencies" in project:
            result["optional_dependencies"] = project["optional-dependencies"]
        
        # Poetry
        if "tool" in data and "poetry" in data["tool"]:
            poetry = data["tool"]["poetry"]
            result["poetry"] = {
                "dependencies": poetry.get("dependencies", {}),
                "dev_dependencies": poetry.get("dev-dependencies", {}),
            }
        
        # PDM
        if "tool" in data and "pdm" in data["tool"]:
            pdm = data["tool"]["pdm"]
            result["pdm"] = pdm
        
        return result
    
    def _find_test_config(self) -> Dict[str, Any]:
        """Find test configuration files."""
        config = {
            "pytest": None,
            "tox": None,
            "coverage": None,
        }
        
        # pytest.ini / pyproject.toml [tool.pytest]
        pytest_ini = self.repo_path / "pytest.ini"
        if pytest_ini.exists():
            config["pytest"] = str(pytest_ini)
        
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject) as f:
                    data = toml.load(f)
                if "tool" in data and "pytest" in data["tool"]:
                    config["pytest"] = "pyproject.toml"
            except Exception:
                pass
        
        # tox.ini
        tox_ini = self.repo_path / "tox.ini"
        if tox_ini.exists():
            config["tox"] = str(tox_ini)
        
        # coverage
        for cov_file in [".coveragerc", "coverage.ini"]:
            cov_path = self.repo_path / cov_file
            if cov_path.exists():
                config["coverage"] = str(cov_path)
        
        return config
    
    def _detect_python_version(self) -> Optional[str]:
        """Detect Python version from various sources."""
        # pyproject.toml
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject) as f:
                    data = toml.load(f)
                # Check project.requires-python
                if "project" in data and "requires-python" in data["project"]:
                    return data["project"]["requires-python"]
                # Check tool.poetry.dependencies.python
                if "tool" in data and "poetry" in data["tool"]:
                    poetry_deps = data["tool"]["poetry"].get("dependencies", {})
                    if "python" in poetry_deps:
                        return poetry_deps["python"]
            except Exception:
                pass
        
        # .python-version
        py_version = self.repo_path / ".python-version"
        if py_version.exists():
            try:
                return py_version.read_text().strip()
            except Exception:
                pass
        
        # runtime.txt (Heroku)
        runtime = self.repo_path / "runtime.txt"
        if runtime.exists():
            try:
                content = runtime.read_text().strip()
                if content.startswith("python-"):
                    return content[7:]
            except Exception:
                pass
        
        return None

def clone_repository(url: str, target_dir: str, branch: str = "main") -> str:
    """Clone a git repository."""
    parsed_url = urlsplit(url)
    if parsed_url.scheme != "https" or not parsed_url.hostname or parsed_url.username or parsed_url.password:
        raise ValueError("Repository URLs must use HTTPS and must not contain credentials")
    destination_root = Path(target_dir)
    destination_root.mkdir(parents=True, exist_ok=True)
    repo_path = Path(tempfile.mkdtemp(prefix="depmigrant-repo-", dir=destination_root))
    try:
        Repo.clone_from(url, repo_path, branch=branch)
    except Exception:
        shutil.rmtree(repo_path)
        raise
    return str(repo_path)

def extract_archive(archive_path: str, target_dir: str) -> str:
    """Safely extract a ZIP or tar archive into a new, unique directory."""
    archive = Path(archive_path)
    if archive.name.endswith(".zip"):
        archive_type = "zip"
    elif archive.name.endswith((".tar.gz", ".tgz", ".tar")):
        archive_type = "tar"
    else:
        raise ValueError(f"Unsupported archive format: {archive.name}")

    destination_root = Path(target_dir)
    destination_root.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix="depmigrant-archive-", dir=destination_root))
    max_members = 10_000
    max_uncompressed_bytes = 512 * 1024 * 1024

    def destination_for(member_name: str) -> Path:
        member_path = PurePosixPath(member_name)
        if member_path.is_absolute() or "\\" in member_name or ".." in member_path.parts:
            raise ValueError(f"Archive contains an unsafe path: {member_name}")
        destination = (target / Path(*member_path.parts)).resolve()
        try:
            destination.relative_to(target.resolve())
        except ValueError as exc:
            raise ValueError(f"Archive contains an unsafe path: {member_name}") from exc
        return destination

    try:
        if archive_type == "zip":
            with zipfile.ZipFile(archive, "r") as archive_file:
                members = archive_file.infolist()
                if len(members) > max_members or sum(member.file_size for member in members) > max_uncompressed_bytes:
                    raise ValueError("Archive exceeds the extraction limits")
                for member in members:
                    destination = destination_for(member.filename)
                    if member.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive_file.open(member) as source, destination.open("xb") as output:
                        shutil.copyfileobj(source, output)
        else:
            with tarfile.open(archive, "r:*") as archive_file:
                members = archive_file.getmembers()
                if len(members) > max_members or sum(member.size for member in members) > max_uncompressed_bytes:
                    raise ValueError("Archive exceeds the extraction limits")
                for member in members:
                    destination = destination_for(member.name)
                    if member.isdir():
                        destination.mkdir(parents=True, exist_ok=True)
                        continue
                    if not member.isfile():
                        raise ValueError(f"Archive contains an unsupported entry: {member.name}")
                    source = archive_file.extractfile(member)
                    if source is None:
                        raise ValueError(f"Could not read archive entry: {member.name}")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with source, destination.open("xb") as output:
                        shutil.copyfileobj(source, output)
    except Exception:
        shutil.rmtree(target)
        raise

    return str(target)