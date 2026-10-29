import subprocess
import tempfile
import os
import shutil
import time
import signal
import sys
import shlex
from pathlib import Path
from typing import List, Dict, Any, Optional, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from app.core.config import settings

@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    args: List[str]
    timed_out: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Sandbox:
    def __init__(self, work_dir: str, timeout: int = None):
        self.work_dir = Path(work_dir).resolve()
        self.timeout = timeout or settings.sandbox_timeout
        self.max_memory_mb = settings.sandbox_max_memory_mb

    def _resolve_work_path(self, path: str) -> Path:
        requested_path = Path(path)
        if not requested_path.is_absolute():
            requested_path = self.work_dir / requested_path

        resolved_path = requested_path.resolve()
        try:
            resolved_path.relative_to(self.work_dir)
        except ValueError as exc:
            raise ValueError(f"Path must be within sandbox working directory: {path}") from exc

        return resolved_path
    
    def run_command(
        self,
        command: Sequence[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """Run an argument-list command in the sandbox without a shell."""
        if isinstance(command, (str, bytes)) or not command:
            raise TypeError("command must be a non-empty sequence of string arguments")
        if any(not isinstance(argument, str) or "\0" in argument for argument in command):
            raise ValueError("command arguments must be strings without null bytes")

        command_args = list(command)
        command_text = shlex.join(command_args)
        start_time = time.time()
        cmd_timeout = timeout or self.timeout
        
        # Keep command lookup and basic platform operation without inheriting secrets.
        allowed_env = ("PATH", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL")
        if os.name == "nt":
            allowed_env += ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT")
        cmd_env = {key: os.environ[key] for key in allowed_env if key in os.environ}
        command_path = cmd_env.get("PATH") or os.defpath
        cmd_env["PATH"] = os.pathsep.join((str(Path(sys.executable).parent), command_path))

        if env is not None:
            if not isinstance(env, dict):
                raise TypeError("env must be a dictionary of string keys and values")
            for key, value in env.items():
                if (
                    not isinstance(key, str)
                    or not key
                    or "=" in key
                    or "\0" in key
                    or not isinstance(value, str)
                    or "\0" in value
                ):
                    raise ValueError("env must contain valid string keys and values")
            cmd_env.update(env)
        
        # Set working directory
        cmd_cwd = self._resolve_work_path(cwd) if cwd is not None else self.work_dir
        
        exec_args = list(command_args)
        if exec_args and exec_args[0] == "python" and not shutil.which("python", path=cmd_env.get("PATH")):
            exec_args[0] = sys.executable

        try:
            # Run command with timeout
            result = subprocess.run(
                exec_args,
                shell=False,
                cwd=cmd_cwd,
                env=cmd_env,
                capture_output=True,
                text=True,
                timeout=cmd_timeout,
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            return CommandResult(
                command=command_text,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
                timed_out=False,
                args=command_args,
            )
        
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return CommandResult(
                command=command_text,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {cmd_timeout} seconds",
                duration_ms=duration_ms,
                timed_out=True,
                args=command_args,
            )
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return CommandResult(
                command=command_text,
                exit_code=-1,
                stdout="",
                stderr=f"Command could not be started ({type(e).__name__})",
                duration_ms=duration_ms,
                timed_out=False,
                args=command_args,
            )
    
    def run_commands(self, commands: List[Sequence[str]], env: Optional[Dict[str, str]] = None) -> List[CommandResult]:
        """Run multiple commands sequentially."""
        results = []
        for cmd in commands:
            result = self.run_command(cmd, env=env)
            results.append(result)
            # Stop on failure if not a test command
            if result.exit_code != 0 and not self._is_test_command(cmd):
                break
        return results

    @staticmethod
    def _is_test_command(command: Sequence[str]) -> bool:
        if not command:
            return False
        executable = Path(command[0]).stem.lower()
        if executable in {"pytest", "ruff", "mypy", "tox"}:
            return True
        return (
            executable.startswith("python")
            and len(command) >= 3
            and command[1] == "-m"
            and command[2] in {"pytest", "unittest", "ruff", "mypy"}
        )
    
    def apply_patch(self, file_path: str, original_code: str, new_code: str) -> bool:
        """Apply a code patch to a file."""
        full_path = self._resolve_work_path(file_path)
        
        if not full_path.exists():
            return False
        
        try:
            content = full_path.read_text()
            
            # Verify original code matches
            if original_code not in content:
                return False
            
            # Apply patch
            new_content = content.replace(original_code, new_code, 1)
            full_path.write_text(new_content)
            return True
        
        except Exception:
            return False
    
    def apply_patches(self, patches: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Apply multiple patches."""
        results = {}
        for index, patch in enumerate(patches):
            file_path = patch.get("file_path")
            original = patch.get("original_code", "")
            new = patch.get("new_code", "")
            result_key = str(file_path)
            if result_key in results:
                result_key = f"{index}:{result_key}"
            results[result_key] = self.apply_patch(file_path, original, new)
        return results
    
    def get_git_status(self) -> Dict[str, Any]:
        """Get git status of the working directory."""
        result = self.run_command(["git", "status", "--porcelain"])
        if result.exit_code == 0:
            files = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    status = line[:2]
                    path = line[3:]
                    files.append({"status": status.strip(), "path": path})
            return {"clean": len(files) == 0, "files": files}
        return {"clean": False, "files": [], "error": result.stderr}
    
    def get_git_diff(self, file_path: Optional[str] = None) -> str:
        """Get git diff for a file or all files."""
        cmd = ["git", "diff"]
        if file_path:
            cmd.extend(["--", file_path])
        result = self.run_command(cmd)
        return result.stdout if result.exit_code == 0 else result.stderr
    
    def create_backup(self) -> str:
        """Create a backup of the current state."""
        backup_dir = self.work_dir.parent / f"{self.work_dir.name}.backup.{int(time.time())}"
        shutil.copytree(self.work_dir, backup_dir)
        return str(backup_dir)
    
    def restore_backup(self, backup_path: str) -> bool:
        """Restore from backup."""
        try:
            shutil.rmtree(self.work_dir)
            shutil.copytree(backup_path, self.work_dir)
            return True
        except Exception:
            return False

def create_isolated_environment(repo_path: str) -> str:
    """Create an isolated copy of the repository for testing."""
    source = Path(repo_path)
    if source.is_symlink():
        raise ValueError("Repository symlinks are not supported in isolated copies.")
    source = source.resolve(strict=True)

    def contains_symlink(root: Path) -> bool:
        for current, directories, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            if any((current_path / name).is_symlink() for name in (*directories, *files)):
                return True
        return False

    if contains_symlink(source):
        raise ValueError("Repository symlinks are not supported in isolated copies.")

    temp_dir = Path(tempfile.mkdtemp(prefix="depmigrant_", dir=tempfile.gettempdir()))
    try:
        shutil.copytree(source, temp_dir, dirs_exist_ok=True, symlinks=True)
        if contains_symlink(temp_dir):
            raise ValueError("Repository symlinks are not supported in isolated copies.")
    except Exception:
        shutil.rmtree(temp_dir)
        raise
    return str(temp_dir)


def cleanup_isolated_environment(work_dir: str) -> None:
    """Remove only a generated DepMigrant working copy under the system temp directory."""
    temp_root = Path(tempfile.gettempdir()).resolve()
    target = Path(work_dir).resolve()
    if target.parent != temp_root or not target.name.startswith("depmigrant_"):
        raise ValueError("Refusing to remove a directory outside the DepMigrant temp workspace")
    shutil.rmtree(target)