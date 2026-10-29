import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from app.services.sandbox import (
    Sandbox,
    CommandResult,
    cleanup_isolated_environment,
    create_isolated_environment,
)
from app.services.failure_diagnoser import FailureDiagnoser
from app.services.nebius_client import nebius_client
from app.core.config import settings

@dataclass
class RepairAttempt:
    attempt_number: int
    failure_type: str
    diagnosis: str
    proposed_patch: List[Dict[str, Any]]
    applied: bool
    result: Optional[CommandResult] = None
    created_at: str = ""

class MigrationOrchestrator:
    def __init__(self, repo_path: str, job_id: str, db_session):
        self.repo_path = repo_path
        self.job_id = job_id
        self.db = db_session
        self.work_dir = create_isolated_environment(repo_path)
        self.sandbox = Sandbox(self.work_dir)
        self.diagnoser = FailureDiagnoser()
        self.max_repair_attempts = 3
        self.repair_attempts: List[RepairAttempt] = []
        self.command_history: List[CommandResult] = []
        self.model_interactions: List[Dict[str, Any]] = []
    
    def _update_job(self, status: str, current_step: str = None, progress: int = None, **kwargs):
        """Update job in database."""
        from app.models import MigrationJob, MigrationStatus
        job = self.db.query(MigrationJob).filter(MigrationJob.id == self.job_id).first()
        if job:
            job.status = MigrationStatus(status)
            if current_step:
                job.current_step = current_step
            if progress is not None:
                job.progress = progress
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            self.db.commit()
    
    def _record_command(self, result: CommandResult):
        """Record command in history."""
        self.command_history.append(result)
        self._update_job(
            command_history=[asdict(r) for r in self.command_history]
        )
    
    def _record_model_interaction(self, stage: str, prompt: str, response: str, tokens: int, duration: int):
        """Record model interaction."""
        interaction = {
            "id": f"mi_{len(self.model_interactions)}",
            "job_id": self.job_id,
            "stage": stage,
            "prompt": prompt[:1000],
            "response": response[:1000],
            "tokens_used": tokens,
            "duration_ms": duration,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self.model_interactions.append(interaction)
        self._update_job(model_interactions=self.model_interactions)
    
    async def run_baseline(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Run baseline tests before migration."""
        self._update_job("baseline", "Running baseline tests", 10)

        report_path = str(Path(self.work_dir) / ".depmigrant-baseline.xml")
        test_commands = [
            ["python", "-m", "pytest", "-v", "--tb=short", f"--junitxml={report_path}"],
            ["python", "-c", "import sys; print('Python OK')"],
        ]
        
        results = self.sandbox.run_commands(test_commands, env=self._test_environment())
        for r in results:
            self._record_command(r)
        
        pytest_result = next((result for result in results if "pytest" in result.args), None)
        python_result = next(
            (result for result in results if result.args[:2] == ["python", "-c"]),
            None,
        )
        report = self._read_test_report(report_path)
        passed = report["passed"]
        failed = report["failed"]
        skipped = report["skipped"]
        
        # Get git commit
        git_result = self.sandbox.run_command(["git", "rev-parse", "HEAD"])
        git_commit = git_result.stdout.strip() if git_result.exit_code == 0 else "unknown"
        
        baseline = {
            "id": f"baseline_{self.job_id}",
            "migration_id": self.job_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tests_passed": passed,
            "tests_failed": failed,
            "tests_skipped": skipped,
            "build_success": python_result is not None and python_result.exit_code == 0,
            "import_check_success": python_result is not None and python_result.exit_code == 0,
            "test_report_valid": report["valid"],
            "pytest_exit_code": pytest_result.exit_code if pytest_result is not None else None,
            "test_run_success": (
                report["valid"]
                and pytest_result is not None
                and pytest_result.exit_code == 0
                and passed > 0
                and failed == 0
            ),
            "pre_existing_failures": report["failures"],
            "command_outputs": [asdict(r) for r in results],
            "git_commit": git_commit,
        }
        
        self._update_job(baseline_result=baseline)
        return baseline

    @staticmethod
    def _read_test_report(report_path: str) -> Dict[str, Any]:
        try:
            root = ET.parse(report_path).getroot()
            test_cases = root.findall(".//testcase")
            failures = []
            for case in test_cases:
                failure_nodes = case.findall("failure") + case.findall("error")
                if not failure_nodes:
                    continue
                first_failure = failure_nodes[0]
                line_number = case.get("line")
                failures.append(
                    {
                        "test_name": "::".join(
                            part for part in (case.get("classname", ""), case.get("name", ""))
                            if part
                        ),
                        "error_message": (
                            first_failure.get("message", "") + (first_failure.text or "")
                        )[:4000],
                        "file_path": case.get("file", ""),
                        "line_number": int(line_number) if line_number and line_number.isdigit() else None,
                    }
                )
            failed = len(failures)
            skipped = sum(1 for case in test_cases if case.find("skipped") is not None)
            return {
                "valid": True,
                "passed": len(test_cases) - failed - skipped,
                "failed": failed,
                "skipped": skipped,
                "failures": failures,
            }
        except (OSError, ET.ParseError):
            return {
                "valid": False,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "failures": [],
            }
        finally:
            Path(report_path).unlink(missing_ok=True)

    def _test_environment(self) -> Optional[Dict[str, str]]:
        api_source = Path(self.work_dir) / "services" / "api"
        if api_source.is_dir():
            return {"PYTHONPATH": str(api_source)}
        return None
    
    async def apply_patches(self, patches: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Apply migration patches."""
        self._update_job("patching", "Applying code patches", 30)
        
        results = self.sandbox.apply_patches(patches)
        return results
    
    async def execute_migration(self, commands: List[List[str]]) -> List[CommandResult]:
        """Execute migration commands."""
        self._update_job("executing", "Running migration commands", 50)
        
        results = self.sandbox.run_commands(commands)
        for r in results:
            self._record_command(r)
        
        return results
    
    async def run_verification(
        self,
        baseline: Dict[str, Any],
        migration_succeeded: bool = True,
    ) -> Dict[str, Any]:
        """Run verification tests after migration."""
        self._update_job("verifying", "Running verification tests", 80)

        report_path = str(Path(self.work_dir) / ".depmigrant-verification.xml")
        test_commands = [
            ["python", "-m", "pytest", "-v", "--tb=short", f"--junitxml={report_path}"],
        ]
        
        results = self.sandbox.run_commands(test_commands, env=self._test_environment())
        for r in results:
            self._record_command(r)
        
        pytest_result = next((result for result in results if "pytest" in result.args), None)
        report = self._read_test_report(report_path)
        passed = report["passed"]
        failed = report["failed"]
        skipped = report["skipped"]
        
        # Get modified files
        git_status = self.sandbox.get_git_status()
        modified_files = [f["path"] for f in git_status.get("files", [])]
        
        # Compare with baseline
        baseline_failure_ids = {
            (failure.get("file_path", ""), failure.get("test_name", ""))
            for failure in baseline.get("pre_existing_failures", [])
        }
        new_regressions = [
            failure
            for failure in report["failures"]
            if (failure["file_path"], failure["test_name"]) not in baseline_failure_ids
        ]
        
        test_run_succeeded = (
            report["valid"]
            and pytest_result is not None
            and pytest_result.exit_code == 0
            and passed > 0
            and failed == 0
        )
        if migration_succeeded and test_run_succeeded:
            status = "verified"
        else:
            status = "failed"
        
        verification = {
            "id": f"verification_{self.job_id}",
            "migration_id": self.job_id,
            "status": status,
            "tests_passed": passed,
            "tests_failed": failed,
            "tests_skipped": skipped,
            "new_regressions": new_regressions,
            "modified_files": modified_files,
            "repair_attempts_count": len(self.repair_attempts),
            "command_outputs": [asdict(r) for r in results],
            "pytest_exit_code": pytest_result.exit_code if pytest_result is not None else None,
            "test_report_valid": report["valid"],
            "migration_commands_succeeded": migration_succeeded,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "summary": self._generate_summary(
                status,
                passed,
                failed,
                skipped,
                len(new_regressions),
                len(modified_files),
            ),
        }
        
        return verification
    
    def _generate_summary(self, status: str, passed: int, failed: int, skipped: int, regressions: int, modified: int) -> str:
        """Generate verification summary."""
        if status == "verified":
            return f"Migration verified successfully. {passed} tests passed, {failed} failed, {skipped} skipped. {modified} files modified."
        elif status == "partially_verified":
            return f"Migration partially verified. {passed} tests passed, {failed} failed ({regressions} new regressions), {skipped} skipped. {modified} files modified."
        else:
            return f"Migration failed verification. {passed} tests passed, {failed} failed, {skipped} skipped. {modified} files modified."
    
    async def attempt_repair(self, failure: CommandResult, dependency_info: Dict[str, Any]) -> bool:
        """Attempt to repair a failure."""
        if len(self.repair_attempts) >= self.max_repair_attempts:
            return False
        
        self._update_job("repairing", f"Repair attempt {len(self.repair_attempts) + 1}", 60)
        
        # Get repo context
        repo_context = {"path": self.work_dir}
        
        # Diagnose failure
        diagnosis_result = await self.diagnoser.diagnose(
            failure, repo_context, dependency_info, 
            [asdict(a) for a in self.repair_attempts]
        )
        
        attempt = RepairAttempt(
            attempt_number=len(self.repair_attempts) + 1,
            failure_type=diagnosis_result["failure_type"],
            diagnosis=diagnosis_result["diagnosis"],
            proposed_patch=diagnosis_result["proposed_patch"],
            applied=False,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        
        # Apply proposed patch if confident
        if diagnosis_result["confidence"] > 0.6 and diagnosis_result["proposed_patch"]:
            patch_results = self.sandbox.apply_patches(diagnosis_result["proposed_patch"])
            if patch_results and all(patch_results.values()):
                attempt.applied = True
                
                # Re-run the failed command
                retry_result = self.sandbox.run_command(failure.args)
                attempt.result = retry_result
                self._record_command(retry_result)
        
        self.repair_attempts.append(attempt)
        self._update_job(repair_attempts=[asdict(a) for a in self.repair_attempts])
        
        return attempt.applied and (attempt.result.exit_code == 0 if attempt.result else False)
    
    async def run_full_migration(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Run the complete migration workflow."""
        try:
            # Baseline
            baseline = await self.run_baseline(plan)
            
            # Apply patches
            patch_results = await self.apply_patches(plan.get("planned_edits", []))
            patches_succeeded = all(patch_results.values())

            exec_results = []
            if patches_succeeded:
                exec_results = await self.execute_migration(plan.get("execution_commands", []))

            execution_succeeded = bool(exec_results or patch_results)
            for result in exec_results:
                if result.exit_code != 0:
                    execution_succeeded = (
                        await self.attempt_repair(result, plan.get("dependency", {}))
                    ) and execution_succeeded

            verification = await self.run_verification(
                baseline,
                migration_succeeded=patches_succeeded and execution_succeeded,
            )

            cleanup_isolated_environment(self.work_dir)
            self.work_dir = ""
            
            # Final status
            final_status = "completed" if verification["status"] == "verified" else "failed"
            self._update_job(
                final_status,
                "Migration complete",
                100,
                final_result=verification,
                completed_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            
            return verification
        
        except Exception:
            self._update_job("failed", "Migration failed", 0)
            raise
        finally:
            if self.work_dir:
                cleanup_isolated_environment(self.work_dir)