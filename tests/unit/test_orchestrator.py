import asyncio
from pathlib import Path

from app.services.orchestrator import MigrationOrchestrator
from app.services.sandbox import CommandResult, cleanup_isolated_environment
from app.schemas import BaselineResult, VerificationResult


def test_verification_requires_successful_pytest_exit_code_and_junit_report(tmp_path, monkeypatch):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    orchestrator = MigrationOrchestrator(str(repo_path), "job-1", db_session=None)
    monkeypatch.setattr(orchestrator, "_update_job", lambda *args, **kwargs: None)

    def failed_pytest(commands, env=None):
        report_path = next(arg.split("=", 1)[1] for arg in commands[0] if arg.startswith("--junitxml="))
        Path(report_path).write_text(
            '<testsuites><testsuite><testcase classname="sample" name="test_ok"/>'
            '</testsuite></testsuites>'
        )
        return [
            CommandResult(
                command="python -m pytest",
                exit_code=7,
                stdout="1 passed",
                stderr="",
                duration_ms=1,
                args=commands[0],
            )
        ]

    monkeypatch.setattr(orchestrator.sandbox, "run_commands", failed_pytest)
    result = asyncio.run(orchestrator.run_verification({"tests_failed": 0}))

    assert result["status"] == "failed"
    assert result["tests_passed"] == 1
    assert result["pytest_exit_code"] == 7
    assert result["test_report_valid"] is True
    assert result["new_regressions"] == []
    VerificationResult.model_validate(result)
    cleanup_isolated_environment(orchestrator.work_dir)


def test_verification_reports_structured_junit_failures(tmp_path, monkeypatch):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    orchestrator = MigrationOrchestrator(str(repo_path), "job-2", db_session=None)
    monkeypatch.setattr(orchestrator, "_update_job", lambda *args, **kwargs: None)

    def failed_pytest(commands, env=None):
        report_path = next(arg.split("=", 1)[1] for arg in commands[0] if arg.startswith("--junitxml="))
        Path(report_path).write_text(
            '<testsuites><testsuite><testcase classname="sample" name="test_breaks" '
            'file="tests/test_sample.py" line="12"><failure message="assertion failed">'
            'expected one</failure></testcase></testsuite></testsuites>'
        )
        return [
            CommandResult(
                command="python -m pytest",
                exit_code=1,
                stdout="1 failed",
                stderr="",
                duration_ms=1,
                args=commands[0],
            )
        ]

    monkeypatch.setattr(orchestrator.sandbox, "run_commands", failed_pytest)
    result = asyncio.run(orchestrator.run_verification({"tests_failed": 0}))

    assert result["status"] == "failed"
    assert result["tests_failed"] == 1
    assert result["new_regressions"] == [
        {
            "test_name": "sample::test_breaks",
            "error_message": "assertion failedexpected one",
            "file_path": "tests/test_sample.py",
            "line_number": 12,
        }
    ]
    VerificationResult.model_validate(result)
    cleanup_isolated_environment(orchestrator.work_dir)


def test_baseline_result_matches_api_schema(tmp_path, monkeypatch):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    orchestrator = MigrationOrchestrator(str(repo_path), "job-3", db_session=None)
    monkeypatch.setattr(orchestrator, "_update_job", lambda *args, **kwargs: None)

    def successful_commands(commands, env=None):
        report_path = next(arg.split("=", 1)[1] for arg in commands[0] if arg.startswith("--junitxml="))
        Path(report_path).write_text(
            '<testsuites><testsuite><testcase classname="sample" name="test_ok"/>'
            '</testsuite></testsuites>'
        )
        return [
            CommandResult(
                command="python -m pytest",
                exit_code=0,
                stdout="1 passed",
                stderr="",
                duration_ms=1,
                args=commands[0],
            ),
            CommandResult(
                command="python -c",
                exit_code=0,
                stdout="Python OK",
                stderr="",
                duration_ms=1,
                args=commands[1],
            ),
        ]

    monkeypatch.setattr(orchestrator.sandbox, "run_commands", successful_commands)
    baseline = asyncio.run(orchestrator.run_baseline({}))

    assert baseline["test_run_success"] is True
    BaselineResult.model_validate(baseline)
    cleanup_isolated_environment(orchestrator.work_dir)
