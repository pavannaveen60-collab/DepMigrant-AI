import pytest

from app.services import sandbox as sandbox_module
from app.services.sandbox import (
    CommandResult,
    Sandbox,
    cleanup_isolated_environment,
    create_isolated_environment,
)


def test_apply_patch_accepts_path_inside_work_dir(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    target_file = work_dir / "module.py"
    target_file.write_text("before")
    sandbox = Sandbox(str(work_dir))

    assert sandbox.apply_patch("module.py", "before", "after")
    assert target_file.read_text() == "after"


def test_apply_patches_tracks_each_patch_for_the_same_file(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    target_file = work_dir / "module.py"
    target_file.write_text("before")
    sandbox = Sandbox(str(work_dir))

    results = sandbox.apply_patches(
        [
            {"file_path": "module.py", "original_code": "before", "new_code": "middle"},
            {"file_path": "module.py", "original_code": "missing", "new_code": "ignored"},
            {"file_path": "module.py", "original_code": "middle", "new_code": "after"},
        ]
    )

    assert len(results) == 3
    assert sorted(results.values()) == [False, True, True]
    assert target_file.read_text() == "after"


def test_apply_patch_rejects_parent_directory_traversal(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("before")
    sandbox = Sandbox(str(work_dir))

    with pytest.raises(ValueError, match="within sandbox working directory"):
        sandbox.apply_patch("../outside.py", "before", "after")

    assert outside_file.read_text() == "before"


def test_apply_patch_rejects_absolute_path_outside_work_dir(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("before")
    sandbox = Sandbox(str(work_dir))

    with pytest.raises(ValueError, match="within sandbox working directory"):
        sandbox.apply_patch(str(outside_file), "before", "after")

    assert outside_file.read_text() == "before"


def test_run_command_rejects_working_directory_outside_work_dir(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    sandbox = Sandbox(str(work_dir))

    with pytest.raises(ValueError, match="within sandbox working directory"):
        sandbox.run_command(["echo", "should-not-run"], cwd=str(outside_dir))


def test_run_command_does_not_inherit_parent_secrets(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    sandbox = Sandbox(str(work_dir))
    monkeypatch.setenv("SANDBOX_TEST_SECRET", "not-for-subprocess")

    result = sandbox.run_command(
        ["python", "-c", "import os; raise SystemExit('SANDBOX_TEST_SECRET' in os.environ)"]
    )

    assert result.exit_code == 0


def test_run_command_passes_explicit_environment_variables(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    sandbox = Sandbox(str(work_dir))

    result = sandbox.run_command(
        ["python", "-c", "import os; raise SystemExit(os.environ.get('SANDBOX_SAFE_VALUE') != 'available')"],
        env={"SANDBOX_SAFE_VALUE": "available"},
    )

    assert result.exit_code == 0


def test_run_command_can_run_python_and_pytest(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    sandbox = Sandbox(str(work_dir))

    python_result = sandbox.run_command(["python", "-c", "print('python-ok')"])
    pytest_result = sandbox.run_command(["pytest", "--version"])

    assert python_result.exit_code == 0
    assert python_result.stdout.strip() == "python-ok"
    assert pytest_result.exit_code == 0
    assert pytest_result.stdout.startswith("pytest ")


def test_run_command_executes_argument_list_without_shell(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    sandbox = Sandbox(str(work_dir))
    real_run = sandbox_module.subprocess.run
    observed = {}

    def run_without_shell(*args, **kwargs):
        observed["shell"] = kwargs["shell"]
        return real_run(*args, **kwargs)

    monkeypatch.setattr(sandbox_module.subprocess, "run", run_without_shell)
    result = sandbox.run_command(["python", "-c", "print('no-shell')"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "no-shell"
    assert observed["shell"] is False


def test_run_command_preserves_nonzero_exit_code(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    sandbox = Sandbox(str(work_dir))

    result = sandbox.run_command(["python", "-c", "raise SystemExit(7)"])

    assert result.exit_code == 7


def test_failed_install_command_is_not_mistaken_for_a_test_command(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    sandbox = Sandbox(str(work_dir))
    invoked = []

    def fail_install(command, **kwargs):
        invoked.append(command)
        return CommandResult(
            command=" ".join(command),
            exit_code=1,
            stdout="",
            stderr="install failed",
            duration_ms=1,
            args=list(command),
        )

    monkeypatch.setattr(sandbox, "run_command", fail_install)
    results = sandbox.run_commands(
        [["pip", "install", "mytestlib"], ["python", "-m", "pytest"]]
    )

    assert len(results) == 1
    assert invoked == [["pip", "install", "mytestlib"]]


def test_run_command_does_not_interpret_shell_operators(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    sandbox = Sandbox(str(work_dir))

    result = sandbox.run_command(
        ["python", "-c", "raise SystemExit(9)", "||", "true"]
    )

    assert result.exit_code == 9
    assert result.args[-2:] == ["||", "true"]


def test_isolated_environments_are_unique_and_do_not_modify_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    source_file = source / "module.py"
    source_file.write_text("original")

    first_copy = create_isolated_environment(str(source))
    second_copy = create_isolated_environment(str(source))
    first_file = sandbox_module.Path(first_copy) / "module.py"
    first_file.write_text("changed")

    assert first_copy != second_copy
    assert source_file.read_text() == "original"
    assert (sandbox_module.Path(second_copy) / "module.py").read_text() == "original"

    cleanup_isolated_environment(first_copy)
    cleanup_isolated_environment(second_copy)
    assert not sandbox_module.Path(first_copy).exists()
    assert not sandbox_module.Path(second_copy).exists()


def test_isolated_environment_rejects_symlinks_without_following_them(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside source")
    (source / "linked.txt").symlink_to(outside_file)

    with pytest.raises(ValueError, match="symlinks are not supported"):
        create_isolated_environment(str(source))

    assert outside_file.read_text() == "outside source"


def test_cleanup_refuses_non_generated_directories(tmp_path):
    with pytest.raises(ValueError, match="Refusing to remove"):
        cleanup_isolated_environment(str(tmp_path))
