"""Unit tests for DepMigrant AI backend."""

import os
import json
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import RepositoryCreate, MigrationPlanCreate, MigrationJobResponse
from app.api import routes
from app.db.session import Base, get_db
from app.models import (
    MigrationJob,
    MigrationPlan,
    MigrationStatus,
    Repository,
    RepositoryType,
)
from app.services.migration_planner import InvalidPlannerResponseError
from app.services.nebius_client import (
    ProviderConfigurationError,
    ProviderResponseError,
)

client = TestClient(app)

@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield test_session
    finally:
        engine.dispose()

@pytest.fixture
def api_client(test_db):
    def override_get_db():
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.pop(get_db, None)

def test_app_import():
    """Verify that the FastAPI app can be imported."""
    from fastapi import FastAPI
    assert isinstance(app, FastAPI)

def test_health_endpoint():
    """Test that the health check endpoint returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "depmigrant-api"

def test_repository_create_valid(api_client, monkeypatch, tmp_path):
    """Test creating a repository with valid data."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    def fake_clone_repository(url, target_dir, branch):
        assert url == "https://github.com/example/repo.git"
        assert branch == "main"
        return str(repo_path)

    monkeypatch.setattr(routes, "clone_repository", fake_clone_repository)
    valid_data = {
        "type": "git",
        "path": "/tmp/test-repo",
        "url": "https://github.com/example/repo.git",
        "branch": "main"
    }
    response = api_client.post("/api/repositories", json=valid_data)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["name"] == "repo"  # derived from path name

def test_repository_create_is_idempotent_for_same_git_source_and_branch(
    api_client, test_db, monkeypatch, tmp_path
):
    clone_paths = []

    def fake_clone_repository(url, target_dir, branch):
        assert url == "https://github.com/example/repo.git"
        clone_paths.append(branch)
        path = tmp_path / branch
        path.mkdir()
        return str(path)

    monkeypatch.setattr(routes, "clone_repository", fake_clone_repository)
    source = {
        "type": "git",
        "path": "",
        "url": "https://github.com/example/repo.git",
        "branch": "main",
    }

    first = api_client.post("/api/repositories", json=source)
    duplicate = api_client.post("/api/repositories", json={**source, "branch": None})
    other_branch = api_client.post(
        "/api/repositories", json={**source, "branch": "release"}
    )

    assert first.status_code == duplicate.status_code == other_branch.status_code == 200
    assert first.json()["id"] == duplicate.json()["id"]
    assert first.json()["id"] != other_branch.json()["id"]
    assert clone_paths == ["main", "release"]
    with test_db() as db:
        assert db.query(Repository).count() == 2


def test_repository_reregistration_restores_missing_checkout(
    api_client, test_db, monkeypatch, tmp_path
):
    repository_id = "00000000-0000-0000-0000-000000000001"
    missing_path = tmp_path / "missing-checkout"
    persistent_root = tmp_path / "repositories"
    restored_path = tmp_path / "repositories" / "restored-requests"
    restored_path.mkdir(parents=True)
    clone_calls = []

    def fake_clone_repository(url, target_dir, branch):
        clone_calls.append((url, target_dir, branch))
        return str(restored_path)

    monkeypatch.setattr(routes, "REPOSITORY_STORAGE_DIR", persistent_root)
    monkeypatch.setattr(routes, "clone_repository", fake_clone_repository)
    with test_db() as db:
        db.add(
            Repository(
                id=repository_id,
                name="requests",
                path=str(missing_path),
                type=RepositoryType.GIT,
                url="https://github.com/psf/requests.git",
                branch="main",
            )
        )
        db.commit()

    response = api_client.post(
        "/api/repositories",
        json={
            "path": "",
            "type": "git",
            "url": "https://github.com/psf/requests.git",
            "branch": "main",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == repository_id
    assert response.json()["path"] == str(restored_path)
    assert clone_calls == [
        ("https://github.com/psf/requests.git", str(persistent_root), "main")
    ]
    with test_db() as db:
        assert db.query(Repository).count() == 1
        assert db.query(Repository).first().path == str(restored_path)


def test_repository_create_missing_type():
    """Test that missing 'type' raises validation error."""
    invalid_data = {
        "path": "/tmp/test",
        "url": "https://example.com/repo.git"
        # missing 'type'
    }
    response = client.post("/api/repositories", json=invalid_data)
    assert response.status_code == 422  # FastAPI validation error

def test_repository_create_rejects_missing_or_unsafe_git_url(api_client, monkeypatch):
    def clone_must_not_run(*args, **kwargs):
        pytest.fail("invalid Git URL reached the clone function")

    monkeypatch.setattr(routes, "clone_repository", clone_must_not_run)
    missing_url = api_client.post(
        "/api/repositories",
        json={"type": "git", "path": ""},
    )
    credentialed_url = api_client.post(
        "/api/repositories",
        json={
            "type": "git",
            "path": "",
            "url": "https://user:password@example.com/owner/repository.git",
        },
    )
    private_ip_url = api_client.post(
        "/api/repositories",
        json={
            "type": "git",
            "path": "",
            "url": "https://127.0.0.1/owner/repository.git",
        },
    )

    assert missing_url.status_code == 422
    assert credentialed_url.status_code == 422
    assert private_ip_url.status_code == 422


def test_repository_inspect_reports_missing_checkout(api_client, test_db, tmp_path):
    repo_path = tmp_path / "removed-checkout"
    with test_db() as db:
        db.add(
            Repository(
                id="missing-checkout",
                name="requests",
                path=str(repo_path),
                type=RepositoryType.GIT,
                url="https://github.com/psf/requests.git",
            )
        )
        db.commit()

    response = api_client.post(
        "/api/repositories/missing-checkout/inspect"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "The registered repository checkout is unavailable. "
        "Restore the checkout or register the repository again."
    )


def test_repository_inspect_returns_static_setup_py_dependencies(
    api_client, test_db, tmp_path
):
    repo_path = tmp_path / "setup-checkout"
    repo_path.mkdir()
    marker = tmp_path / "setup-executed"
    (repo_path / "setup.py").write_text(
        f"""
from setuptools import setup

setup(
    install_requires=["urllib3<3,>=1.21.1", "certifi>=2017.4.17"],
    extras_require={{"security": ["idna>=2.5"]}},
)
open({str(marker)!r}, "w").write("executed")
"""
    )
    with test_db() as db:
        db.add(
            Repository(
                id="setup-checkout",
                name="requests",
                path=str(repo_path),
                type=RepositoryType.GIT,
            )
        )
        db.commit()

    response = api_client.post("/api/repositories/setup-checkout/inspect")

    assert response.status_code == 200
    assert response.json()["dependencies"]["setup_py_dependencies"] == {
        "dependencies": ["urllib3<3,>=1.21.1", "certifi>=2017.4.17"],
        "optional_dependencies": {"security": ["idna>=2.5"]},
    }
    assert not marker.exists()

def test_repository_delete_removes_only_unreferenced_registration(api_client, test_db, tmp_path):
    repository_id = "00000000-0000-0000-0000-000000000001"
    repo_path = tmp_path / "source-repo"
    repo_path.mkdir()
    (repo_path / "keep.txt").write_text("keep local source")
    with test_db() as db:
        db.add(
            Repository(
                id=repository_id,
                name="source-repo",
                path=str(repo_path),
                type=RepositoryType.ARCHIVE,
            )
        )
        db.commit()

    response = api_client.delete(f"/api/repositories/{repository_id}")

    assert response.status_code == 200
    assert "local files were not removed" in response.json()["message"]
    assert (repo_path / "keep.txt").read_text() == "keep local source"
    with test_db() as db:
        assert db.query(Repository).filter_by(id=repository_id).first() is None

def test_repository_delete_rejects_records_with_migration_plans(api_client, test_db, tmp_path):
    repository_id = "00000000-0000-0000-0000-000000000002"
    repo_path = tmp_path / "repo-with-plan"
    repo_path.mkdir()
    with test_db() as db:
        db.add(
            Repository(
                id=repository_id,
                name="repo-with-plan",
                path=str(repo_path),
                type=RepositoryType.ARCHIVE,
            )
        )
        db.add(
            MigrationPlan(
                id="plan-preserved",
                repository_id=repository_id,
                dependency_name="requests",
                current_version="2.0",
                target_version="3.0",
                ecosystem="pypi",
                manifest_path="requirements.txt",
            )
        )
        db.commit()

    response = api_client.delete(f"/api/repositories/{repository_id}")

    assert response.status_code == 409
    with test_db() as db:
        assert db.query(Repository).filter_by(id=repository_id).first() is not None
        assert db.query(MigrationPlan).filter_by(id="plan-preserved").first() is not None

def test_repository_delete_rejects_records_with_migration_jobs(api_client, test_db, tmp_path):
    repository_id = "00000000-0000-0000-0000-000000000003"
    repo_path = tmp_path / "repo-with-job"
    repo_path.mkdir()
    with test_db() as db:
        db.add(
            Repository(
                id=repository_id,
                name="repo-with-job",
                path=str(repo_path),
                type=RepositoryType.ARCHIVE,
            )
        )
        db.add(
            MigrationPlan(
                id="00000000-0000-0000-0000-000000000004",
                repository_id=repository_id,
                dependency_name="requests",
                current_version="2.0",
                target_version="3.0",
                ecosystem="pypi",
                manifest_path="requirements.txt",
            )
        )
        db.add(
            MigrationJob(
                id="00000000-0000-0000-0000-000000000005",
                repository_id=repository_id,
                plan_id="00000000-0000-0000-0000-000000000004",
                status=MigrationStatus.PENDING,
            )
        )
        db.commit()

    response = api_client.delete(f"/api/repositories/{repository_id}")

    assert response.status_code == 409
    with test_db() as db:
        assert db.query(Repository).filter_by(id=repository_id).first() is not None
        assert db.query(MigrationJob).filter_by(id="00000000-0000-0000-0000-000000000005").first() is not None

def test_repository_delete_returns_not_found(api_client):
    response = api_client.delete("/api/repositories/00000000-0000-0000-0000-000000000006")

    assert response.status_code == 404

def test_repository_delete_rejects_invalid_id(api_client):
    response = api_client.delete("/api/repositories/not-a-uuid")

    assert response.status_code == 422

def test_migration_job_list_returns_recorded_jobs(api_client, test_db, tmp_path):
    repo_path = tmp_path / "history-repo"
    repo_path.mkdir()
    with test_db() as db:
        db.add(
            Repository(
                id="history-repo",
                name="history-repo",
                path=str(repo_path),
                type=RepositoryType.ARCHIVE,
            )
        )
        db.add(
            MigrationPlan(
                id="history-plan",
                repository_id="history-repo",
                dependency_name="requests",
                current_version="2.0",
                target_version="3.0",
                ecosystem="pypi",
                manifest_path="requirements.txt",
            )
        )
        db.add(
            MigrationJob(
                id="history-job",
                repository_id="history-repo",
                plan_id="history-plan",
                status=MigrationStatus.FAILED,
                progress=35,
                repair_attempts=[],
                command_history=[],
                model_interactions=[],
            )
        )
        db.commit()

    response = api_client.get("/api/migrations/jobs")

    assert response.status_code == 200
    assert [job["id"] for job in response.json()] == ["history-job"]
    assert response.json()[0]["status"] == "failed"
    assert response.json()[0]["updated_at"] is None

def test_migration_plan_list_returns_saved_plans(api_client, test_db, tmp_path):
    repo_path = tmp_path / "saved-plan-repo"
    repo_path.mkdir()
    with test_db() as db:
        db.add(
            Repository(
                id="saved-plan-repo",
                name="saved-plan-repo",
                path=str(repo_path),
                type=RepositoryType.ARCHIVE,
            )
        )
        db.add(
            MigrationPlan(
                id="saved-plan",
                repository_id="saved-plan-repo",
                dependency_name="requests",
                current_version="2.0",
                target_version="2.32.0",
                ecosystem="pypi",
                manifest_path="pyproject.toml",
                execution_commands=["pip install requests==2.32.0", "pytest -v"],
                breaking_changes=[],
                affected_files=[],
                planned_edits=[],
                risks=["Review test results."],
            )
        )
        db.commit()

    response = api_client.get("/api/migrations/plans")

    assert response.status_code == 200
    plans = response.json()
    assert len(plans) == 1
    assert plans[0]["id"] == "saved-plan"
    assert plans[0]["dependency"]["name"] == "requests"
    assert plans[0]["execution_commands"] == [
        "pip install requests==2.32.0",
        "pytest -v",
    ]

def test_migration_plan_get_preserves_flat_stored_commands(api_client, test_db, tmp_path):
    repo_path = tmp_path / "plan-detail-repo"
    repo_path.mkdir()
    with test_db() as db:
        db.add(
            Repository(
                id="plan-detail-repo",
                name="plan-detail-repo",
                path=str(repo_path),
                type=RepositoryType.ARCHIVE,
            )
        )
        db.add(
            MigrationPlan(
                id="flat-command-plan",
                repository_id="plan-detail-repo",
                dependency_name="requests",
                current_version=None,
                target_version="2.32.0",
                ecosystem="pypi",
                manifest_path="pyproject.toml",
                execution_commands=["pip install requests==2.32.0", "pytest -v"],
                breaking_changes=[],
                affected_files=[],
                planned_edits=[],
                risks=[],
            )
        )
        db.commit()

    response = api_client.get("/api/migrations/plan/flat-command-plan")

    assert response.status_code == 200
    plan = response.json()
    assert plan["dependency"]["current_version"] is None
    assert plan["execution_commands"] == [
        "pip install requests==2.32.0",
        "pytest -v",
    ]

def test_cancel_migration_does_not_claim_to_stop_background_job(api_client, test_db, tmp_path):
    repo_path = tmp_path / "uncancellable-repo"
    repo_path.mkdir()
    with test_db() as db:
        db.add(
            Repository(
                id="uncancellable-repo",
                name="uncancellable-repo",
                path=str(repo_path),
                type=RepositoryType.ARCHIVE,
            )
        )
        db.add(
            MigrationPlan(
                id="uncancellable-plan",
                repository_id="uncancellable-repo",
                dependency_name="requests",
                current_version="2.0",
                target_version="3.0",
                ecosystem="pypi",
                manifest_path="requirements.txt",
            )
        )
        db.add(
            MigrationJob(
                id="uncancellable-job",
                repository_id="uncancellable-repo",
                plan_id="uncancellable-plan",
                status=MigrationStatus.EXECUTING,
                progress=50,
                current_step="Applying changes",
                repair_attempts=[],
                command_history=[],
                model_interactions=[],
            )
        )
        db.commit()

    response = api_client.post("/api/migrations/job/uncancellable-job/cancel")

    assert response.status_code == 409
    with test_db() as db:
        job = db.query(MigrationJob).filter_by(id="uncancellable-job").one()
        assert job.status == MigrationStatus.EXECUTING
        assert job.current_step == "Applying changes"

def test_migration_plan_create_valid(api_client, test_db, monkeypatch, tmp_path):
    """Test that MigrationPlanCreate schema validates correctly."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    with test_db() as db:
        db.add(
            Repository(
                id="repo-123",
                name="repo",
                path=str(repo_path),
                type=RepositoryType.GIT,
            )
        )
        db.commit()

    observed = {}

    async def fake_create_plan(self, repo_inspection, dependency_name, target_version, current_version=None):
        observed["current_version"] = current_version
        return {
            "dependency": {
                "name": dependency_name,
                "current_version": current_version or "unknown",
                "target_version": target_version,
                "ecosystem": "pypi",
                "manifest_path": "pyproject.toml",
            },
            "breaking_changes": [],
            "affected_files": [],
            "planned_edits": [],
            "execution_commands": [],
            "risks": [],
        }

    monkeypatch.setattr(routes.MigrationPlanner, "create_plan", fake_create_plan)
    valid_data = {
        "repository_id": "repo-123",
        "dependency_name": "requests",
        "current_version": "2.31.0",
        "target_version": "2.28.0"
    }
    response = api_client.post("/api/migrations/plan", json=valid_data)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["repository_id"] == "repo-123"
    assert data["dependency"]["name"] == "requests"
    assert data["dependency"]["current_version"] == "2.31.0"
    assert data["dependency"]["target_version"] == "2.28.0"
    assert observed["current_version"] == "2.31.0"
    with test_db() as db:
        assert db.query(MigrationPlan).filter_by(id=data["id"]).one().current_version == "2.31.0"
        assert db.query(MigrationJob).count() == 0


def test_migration_plan_does_not_infer_current_version_from_manifest_constraint(
    api_client, test_db, monkeypatch, tmp_path
):
    repo_path = tmp_path / "requirements-repo"
    repo_path.mkdir()
    (repo_path / "requirements.txt").write_text("requests==2.31.0\n")
    with test_db() as db:
        db.add(
            Repository(
                id="requirements-repo",
                name="requirements-repo",
                path=str(repo_path),
                type=RepositoryType.ARCHIVE,
            )
        )
        db.commit()

    observed = {}

    async def fake_create_plan(self, repo_inspection, dependency_name, target_version, current_version=None):
        observed["current_version"] = current_version
        return {
            "dependency": {
                "name": dependency_name,
                "current_version": current_version,
                "target_version": target_version,
                "ecosystem": "pypi",
                "manifest_path": "requirements.txt",
            },
            "breaking_changes": [],
            "affected_files": [],
            "planned_edits": [],
            "execution_commands": [],
            "risks": [],
        }

    monkeypatch.setattr(routes.MigrationPlanner, "create_plan", fake_create_plan)
    response = api_client.post(
        "/api/migrations/plan",
        json={
            "repository_id": "requirements-repo",
            "dependency_name": "requests",
            "target_version": "2.32.0",
        },
    )

    assert response.status_code == 200
    assert observed["current_version"] is None
    assert response.json()["dependency"]["current_version"] is None
    with test_db() as db:
        assert db.query(MigrationPlan).count() == 1
        assert db.query(MigrationPlan).one().current_version is None
        assert db.query(MigrationJob).count() == 0


def test_migration_plan_rejects_invalid_explicit_current_version(api_client):
    response = api_client.post(
        "/api/migrations/plan",
        json={
            "repository_id": "unused",
            "dependency_name": "requests",
            "current_version": ">=1.26,<3",
            "target_version": "2.32.0",
        },
    )

    assert response.status_code == 422


def test_migration_plan_failure_logs_exception_and_traceback(
    api_client, test_db, monkeypatch, tmp_path, caplog
):
    repo_path = tmp_path / "private-repository-content"
    repo_path.mkdir()
    with test_db() as db:
        db.add(
            Repository(
                id="planner-error-repo",
                name="private-repository-content",
                path=str(repo_path),
                type=RepositoryType.ARCHIVE,
            )
        )
        db.commit()

    async def fail_create_plan(*args, **kwargs):
        raise InvalidPlannerResponseError(
            "The model returned invalid JSON for breaking changes (line 1, column 2)"
        )

    monkeypatch.setattr(routes.MigrationPlanner, "create_plan", fail_create_plan)
    response = api_client.post(
        "/api/migrations/plan",
        json={
            "repository_id": "planner-error-repo",
            "dependency_name": "requests",
            "target_version": "2.32.0",
        },
    )

    assert response.status_code == 502
    assert "incomplete or invalid structured data" in response.json()["detail"]
    assert "breaking changes" in response.json()["detail"]
    assert "No plan was saved" in response.json()["detail"]
    log_text = caplog.text
    assert "AI provider returned an unusable planning response" in log_text
    assert "Traceback (most recent call last)" in log_text
    assert "private-repository-content" not in log_text
    with test_db() as db:
        assert db.query(MigrationPlan).count() == 0
        assert db.query(MigrationJob).count() == 0


@pytest.mark.parametrize(
    ("failure_kind", "expected_status", "expected_detail"),
    [
        (
            "configuration",
            503,
            "AI provider credentials are not configured on the backend.",
        ),
        (
            "http_status",
            502,
            "The AI provider rejected the request (HTTP 401).",
        ),
        (
            "connection",
            502,
            "The backend could not connect to the AI provider.",
        ),
        (
            "provider_response",
            502,
            "The AI provider response could not be used to create a plan.",
        ),
        (
            "planner_response",
            502,
            "The AI model returned incomplete or invalid structured data:",
        ),
    ],
)
def test_migration_plan_provider_failures_have_distinct_safe_messages(
    api_client,
    test_db,
    monkeypatch,
    tmp_path,
    failure_kind,
    expected_status,
    expected_detail,
):
    repo_path = tmp_path / "failure-repo"
    repo_path.mkdir()
    with test_db() as db:
        db.add(
            Repository(
                id="provider-failure-repo",
                name="failure-repo",
                path=str(repo_path),
                type=RepositoryType.ARCHIVE,
            )
        )
        db.commit()

    request = httpx.Request("POST", "https://provider.example.test/chat/completions")
    if failure_kind == "configuration":
        error = ProviderConfigurationError("credentials are not configured")
    elif failure_kind == "http_status":
        response = httpx.Response(401, request=request)
        error = httpx.HTTPStatusError(
            "unauthorized", request=request, response=response
        )
    elif failure_kind == "connection":
        error = httpx.ConnectError("connection refused", request=request)
    elif failure_kind == "provider_response":
        error = ProviderResponseError("invalid provider shape")
    else:
        error = InvalidPlannerResponseError("invalid JSON in affected files")

    async def fail_create_plan(*args, **kwargs):
        raise error

    monkeypatch.setattr(routes.MigrationPlanner, "create_plan", fail_create_plan)
    response = api_client.post(
        "/api/migrations/plan",
        json={
            "repository_id": "provider-failure-repo",
            "dependency_name": "requests",
            "target_version": "3.0",
        },
    )

    assert response.status_code == expected_status
    assert expected_detail in response.json()["detail"]
    assert "Authorization" not in response.json()["detail"]
    with test_db() as db:
        assert db.query(MigrationPlan).count() == 0
        assert db.query(MigrationJob).count() == 0


def test_migration_plan_provider_timeout_returns_actionable_gateway_timeout(
    api_client, test_db, monkeypatch, tmp_path, caplog
):
    repo_path = tmp_path / "timeout-repo"
    repo_path.mkdir()
    with test_db() as db:
        db.add(
            Repository(
                id="planner-timeout-repo",
                name="timeout-repo",
                path=str(repo_path),
                type=RepositoryType.ARCHIVE,
            )
        )
        db.commit()

    async def timeout_create_plan(*args, **kwargs):
        raise httpx.ReadTimeout("provider response timed out")

    monkeypatch.setattr(routes.MigrationPlanner, "create_plan", timeout_create_plan)
    response = api_client.post(
        "/api/migrations/plan",
        json={
            "repository_id": "planner-timeout-repo",
            "dependency_name": "requests",
            "target_version": "3.0",
        },
    )

    assert response.status_code == 504
    assert response.json()["detail"] == (
        "The AI provider took too long to generate the migration plan. "
        "Please retry, or ask your administrator to check provider availability."
    )
    assert "Migration planning timed out while waiting for the AI provider" in caplog.text
    assert "provider response timed out" in caplog.text
    assert "Authorization" not in caplog.text
    with test_db() as db:
        assert db.query(MigrationPlan).count() == 0
        assert db.query(MigrationJob).count() == 0


def test_migration_job_creation():
    """Test that MigrationJob can be created with valid data."""
    from app.models import MigrationJob, MigrationStatus
    job = MigrationJob(
        id="job-123",
        repository_id="repo-123",
        plan_id="plan-123",
        status=MigrationStatus.PENDING,
        current_step="planning",
        progress=0,
        baseline_result=None,
        final_result=None,
        repair_attempts=[],
        command_history=[],
        model_interactions=[],
    )
    assert job.id == "job-123"
    assert job.status == MigrationStatus.PENDING
    assert job.current_step == "planning"

def test_migration_start_is_blocked_without_os_isolation(api_client, monkeypatch):
    monkeypatch.setattr(routes.settings, "allow_unsafe_repository_execution", False)

    response = api_client.post("/api/migrations/plan-1/start")

    assert response.status_code == 503
    assert "not OS-isolated" in response.json()["detail"]

def test_health_endpoint_returns_json():
    """Ensure health endpoint returns JSON content type."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

def test_health_endpoint_returns_expected_structure():
    """Verify health endpoint returns expected keys."""
    response = client.get("/health")
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "service" in data
    assert data["service"] == "depmigrant-api"

def test_health_endpoint_returns_json_content_type():
    """Ensure health endpoint returns JSON content type."""
    response = client.get("/health")
    assert response.headers["content-type"].startswith("application/json")