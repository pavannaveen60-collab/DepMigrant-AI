from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import httpx
from ipaddress import ip_address
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import time
import logging
import traceback
from pathlib import Path
from urllib.parse import urlsplit

from app.db.session import get_db
from app.models import Repository, MigrationPlan, MigrationJob, MigrationStatus
from app.schemas import (
    RepositoryCreate, RepositoryResponse,
    MigrationPlanCreate, MigrationPlanResponse,
    MigrationJobResponse, JobStatusResponse,
)
from app.services.repository_inspector import (
    RepositoryInspector,
    clone_repository,
    extract_archive,
)
from app.services.migration_planner import (
    InvalidPlannerResponseError,
    MigrationPlanner,
)
from app.services.nebius_client import (
    ProviderConfigurationError,
    ProviderResponseError,
)
from app.services.orchestrator import MigrationOrchestrator
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)
REPOSITORY_STORAGE_DIR = Path.home() / "DepMigrant AI" / "repositories"


def _inspect_repository(repo: Repository) -> dict:
    if not Path(repo.path).is_dir():
        raise HTTPException(
            status_code=409,
            detail=(
                "The registered repository checkout is unavailable. "
                "Restore the checkout or register the repository again."
            ),
        )
    return RepositoryInspector(repo.path).inspect()


# Repository endpoints
@router.post("/repositories", response_model=RepositoryResponse)
async def create_repository(repo: RepositoryCreate, db: Session = Depends(get_db)):
    """Add a new repository for migration."""
    repo_path = repo.path
    repo_url = repo.url.strip() if repo.url else None
    branch = (repo.branch or "main").strip() or "main"
    
    # Handle git repositories
    if repo.type.value == "git":
        if not repo_url:
            raise HTTPException(status_code=422, detail="A Git repository URL is required.")
        try:
            parsed_url = urlsplit(repo_url)
            host = (parsed_url.hostname or "").rstrip(".").lower()
            try:
                public_ip = ip_address(host).is_global
            except ValueError:
                public_ip = True
            valid_url = (
                parsed_url.scheme.lower() == "https"
                and bool(host)
                and bool(parsed_url.path.strip("/"))
                and parsed_url.username is None
                and parsed_url.password is None
                and not parsed_url.query
                and not parsed_url.fragment
                and host != "localhost"
                and not host.endswith((".localhost", ".local"))
                and public_ip
            )
        except ValueError:
            valid_url = False
        if not valid_url:
            raise HTTPException(
                status_code=422,
                detail="Git repository URL must be an HTTPS URL without embedded credentials or query parameters.",
            )

        existing_query = db.query(Repository).filter(
            Repository.type == repo.type,
            Repository.url == repo_url,
        )
        if branch == "main":
            existing_query = existing_query.filter(
                or_(Repository.branch == branch, Repository.branch.is_(None))
            )
        else:
            existing_query = existing_query.filter(Repository.branch == branch)
        existing_repo = existing_query.first()
        if existing_repo:
            if Path(existing_repo.path).is_dir():
                return existing_repo
            try:
                repo_path = clone_repository(
                    repo_url, str(REPOSITORY_STORAGE_DIR), branch
                )
            except Exception as exc:
                logger.error("Repository checkout restoration failed (%s)", type(exc).__name__)
                raise HTTPException(
                    status_code=400,
                    detail="Repository checkout could not be restored; verify the URL and branch.",
                ) from exc
            existing_repo.path = repo_path
            db.commit()
            db.refresh(existing_repo)
            return existing_repo
        try:
            repo_path = clone_repository(
                repo_url, str(REPOSITORY_STORAGE_DIR), branch
            )
        except Exception as exc:
            logger.error("Repository clone failed (%s)", type(exc).__name__)
            raise HTTPException(status_code=400, detail="Repository clone failed; verify the URL and branch.") from exc
    
    # Handle archive
    elif repo.type.value == "archive" and repo.path:
        try:
            repo_path = extract_archive(
                repo.path, str(REPOSITORY_STORAGE_DIR)
            )
        except Exception as exc:
            logger.error("Archive extraction failed (%s)", type(exc).__name__)
            raise HTTPException(status_code=400, detail="Archive extraction failed; verify the file and format.") from exc
    elif repo.type.value == "archive":
        raise HTTPException(status_code=422, detail="A backend-accessible archive path is required.")
    
    # Verify path exists
    if not Path(repo_path).is_dir():
        raise HTTPException(status_code=400, detail="Repository directory does not exist")
    
    # Create repository record
    name = Path(repo_path).name
    db_repo = Repository(
        id=str(uuid.uuid4()),
        name=name,
        path=repo_path,
        type=repo.type,
        url=repo_url,
        branch=branch if repo.type.value == "git" else repo.branch,
    )
    db.add(db_repo)
    db.commit()
    db.refresh(db_repo)
    
    return db_repo

@router.get("/repositories", response_model=List[RepositoryResponse])
async def list_repositories(db: Session = Depends(get_db)):
    """List all repositories."""
    return db.query(Repository).all()

@router.get("/repositories/{repo_id}", response_model=RepositoryResponse)
async def get_repository(repo_id: str, db: Session = Depends(get_db)):
    """Get repository details."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo

@router.delete("/repositories/{repo_id}")
async def delete_repository(repo_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete an unreferenced repository registration without removing its files."""
    repository_id = str(repo_id)
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    has_plan = db.query(MigrationPlan.id).filter(
        MigrationPlan.repository_id == repository_id
    ).first()
    has_job = db.query(MigrationJob.id).filter(
        MigrationJob.repository_id == repository_id
    ).first()
    if has_plan or has_job:
        raise HTTPException(
            status_code=409,
            detail="Repository cannot be deleted while migration plans or jobs reference it.",
        )

    db.delete(repo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Repository cannot be deleted because related records still exist.",
        ) from exc
    return {"message": "Repository registration deleted; local files were not removed."}

@router.post("/repositories/{repo_id}/inspect")
async def inspect_repository(repo_id: str, db: Session = Depends(get_db)):
    """Inspect repository structure and dependencies."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    return _inspect_repository(repo)

# Migration plan endpoints
@router.post("/migrations/plan", response_model=MigrationPlanResponse)
async def create_migration_plan(plan: MigrationPlanCreate, db: Session = Depends(get_db)):
    """Create a migration plan for a dependency."""
    repo = db.query(Repository).filter(Repository.id == plan.repository_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Inspect repository
    inspection = _inspect_repository(repo)
    
    current_version = plan.current_version
    
    # Create plan using AI
    planner = MigrationPlanner()
    try:
        plan_data = await planner.create_plan(
            inspection,
            plan.dependency_name,
            plan.target_version,
            current_version,
        )
    except httpx.TimeoutException as exc:
        logger.exception("Migration planning timed out while waiting for the AI provider")
        raise HTTPException(
            status_code=504,
            detail=(
                "The AI provider took too long to generate the migration plan. "
                "Please retry, or ask your administrator to check provider availability."
            ),
        ) from exc
    except ProviderConfigurationError as exc:
        logger.exception("Migration planning is unavailable because provider credentials are not configured")
        raise HTTPException(
            status_code=503,
            detail=(
                "AI provider credentials are not configured on the backend. "
                "Set NEBIUS_API_KEY or NVIDIA_NIM_API_KEY, then restart the API."
            ),
        ) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        logger.exception("AI provider returned HTTP status %s", status_code)
        if status_code == 429:
            raise HTTPException(
                status_code=503,
                detail="The AI provider is rate-limiting requests. Wait briefly and retry.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=(
                f"The AI provider rejected the request (HTTP {status_code}). "
                "Verify backend access to the configured model and provider endpoint."
            ),
        ) from exc
    except httpx.RequestError as exc:
        logger.exception(
            "Could not connect to the AI provider (%s)", type(exc).__name__
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "The backend could not connect to the AI provider. "
                "Check network access and the configured provider endpoint, then retry."
            ),
        ) from exc
    except (InvalidPlannerResponseError, ProviderResponseError) as exc:
        logger.exception(
            "AI provider returned an unusable planning response (%s)", type(exc).__name__
        )
        if isinstance(exc, InvalidPlannerResponseError):
            detail = (
                "The AI model returned incomplete or invalid structured data: "
                f"{exc}. No plan was saved. Retry or use a model that follows the "
                "requested JSON schema."
            )
        else:
            detail = (
                "The AI provider response could not be used to create a plan. "
                "Retry or check that the configured model supports chat-completion responses."
            )
        raise HTTPException(
            status_code=502,
            detail=detail,
        ) from exc
    except Exception as exc:
        logger.error(
            "Unexpected migration planning failure (%s)\n%s",
            type(exc).__name__,
            "".join(traceback.format_tb(exc.__traceback__)),
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "An unexpected error prevented plan creation. "
                "Check the backend logs for the request traceback and try again."
            ),
        ) from exc
    
    # Save plan
    db_plan = MigrationPlan(
        id=str(uuid.uuid4()),
        repository_id=plan.repository_id,
        dependency_name=plan.dependency_name,
        current_version=current_version,
        target_version=plan.target_version,
        ecosystem="pypi",
        manifest_path=plan_data["dependency"]["manifest_path"],
        breaking_changes=plan_data["breaking_changes"],
        affected_files=plan_data["affected_files"],
        planned_edits=plan_data["planned_edits"],
        execution_commands=plan_data["execution_commands"],
        risks=plan_data["risks"],
    )
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    
    return {
        "id": db_plan.id,
        "repository_id": db_plan.repository_id,
        "dependency": plan_data["dependency"],
        "breaking_changes": plan_data["breaking_changes"],
        "affected_files": plan_data["affected_files"],
        "planned_edits": plan_data["planned_edits"],
        "execution_commands": plan_data["execution_commands"],
        "risks": plan_data["risks"],
        "created_at": db_plan.created_at,
    }

def _migration_plan_response(plan: MigrationPlan) -> dict:
    return {
        "id": plan.id,
        "repository_id": plan.repository_id,
        "dependency": {
            "name": plan.dependency_name,
            "current_version": plan.current_version,
            "target_version": plan.target_version,
            "ecosystem": plan.ecosystem,
            "manifest_path": plan.manifest_path,
        },
        "breaking_changes": plan.breaking_changes or [],
        "affected_files": plan.affected_files or [],
        "planned_edits": plan.planned_edits or [],
        "execution_commands": plan.execution_commands or [],
        "risks": plan.risks or [],
        "created_at": plan.created_at,
    }


@router.get("/migrations/plans", response_model=List[MigrationPlanResponse])
async def list_migration_plans(db: Session = Depends(get_db)):
    """List saved migration plans, newest first."""
    plans = db.query(MigrationPlan).order_by(MigrationPlan.created_at.desc()).all()
    return [_migration_plan_response(plan) for plan in plans]


@router.get("/migrations/plan/{plan_id}", response_model=MigrationPlanResponse)
async def get_migration_plan(plan_id: str, db: Session = Depends(get_db)):
    """Get migration plan details."""
    plan = db.query(MigrationPlan).filter(MigrationPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Migration plan not found")

    return _migration_plan_response(plan)

# Migration job endpoints
@router.post("/migrations/{plan_id}/start", response_model=MigrationJobResponse)
async def start_migration(plan_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start a migration job."""
    if not settings.allow_unsafe_repository_execution:
        raise HTTPException(
            status_code=503,
            detail=(
                "Migration execution is disabled because repository commands are not OS-isolated. "
                "Review the security guidance before explicitly enabling it."
            ),
        )
    plan = db.query(MigrationPlan).filter(MigrationPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Migration plan not found")
    
    # Create job
    job = MigrationJob(
        id=str(uuid.uuid4()),
        repository_id=plan.repository_id,
        plan_id=plan_id,
        status=MigrationStatus.PENDING,
        current_step="Initializing",
        progress=0,
        repair_attempts=[],
        command_history=[],
        model_interactions=[],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Start migration in background
    background_tasks.add_task(run_migration_task, job.id, plan_id)
    
    return job

async def run_migration_task(job_id: str, plan_id: str):
    """Background task to run migration."""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        plan = db.query(MigrationPlan).filter(MigrationPlan.id == plan_id).first()
        if not plan:
            return
        
        plan_data = {
            "dependency": {
                "name": plan.dependency_name,
                "current_version": plan.current_version,
                "target_version": plan.target_version,
                "ecosystem": plan.ecosystem,
                "manifest_path": plan.manifest_path,
            },
            "breaking_changes": plan.breaking_changes or [],
            "affected_files": plan.affected_files or [],
            "planned_edits": plan.planned_edits or [],
            "execution_commands": plan.execution_commands or [],
            "risks": plan.risks or [],
        }
        
        orchestrator = MigrationOrchestrator(plan.repository.path, job_id, db)
        await orchestrator.run_full_migration(plan_data)
    
    except Exception as exc:
        logger.error("Migration task failed for job %s (%s)", job_id, type(exc).__name__)
    finally:
        db.close()

@router.get("/migrations/job/{job_id}", response_model=MigrationJobResponse)
async def get_migration_job(job_id: str, db: Session = Depends(get_db)):
    """Get migration job details."""
    job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")
    return job

@router.get("/migrations/jobs", response_model=List[MigrationJobResponse])
async def list_migration_jobs(db: Session = Depends(get_db)):
    """List actual migration jobs, newest first."""
    return db.query(MigrationJob).order_by(MigrationJob.started_at.desc()).all()

@router.get("/migrations/job/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get migration job status with logs."""
    job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")
    
    # Convert command history to logs format
    logs = []
    for cmd in job.command_history or []:
        logs.append({
            "timestamp": cmd.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S")),
            "level": "info" if cmd.get("exit_code") == 0 else "error",
            "message": cmd.get("stderr") or cmd.get("stdout", ""),
            "command": cmd.get("command"),
            "exitCode": cmd.get("exit_code"),
        })
    
    return {"job": job, "logs": logs}

@router.post("/migrations/job/{job_id}/cancel")
async def cancel_migration(job_id: str, db: Session = Depends(get_db)):
    """Reject cancellation when the background process cannot be safely stopped."""
    job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")
    
    if job.status in [MigrationStatus.COMPLETED, MigrationStatus.FAILED, MigrationStatus.BLOCKED]:
        raise HTTPException(status_code=400, detail="Job already completed")
    
    raise HTTPException(
        status_code=409,
        detail="Safe cancellation is unavailable because the running migration process cannot be stopped.",
    )

@router.get("/migrations/job/{job_id}/report")
async def get_migration_report(job_id: str, db: Session = Depends(get_db)):
    """Get final migration report."""
    job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")
    
    return {
        "job_id": job.id,
        "status": job.status,
        "baseline": job.baseline_result,
        "final_result": job.final_result,
        "repair_attempts": job.repair_attempts,
        "command_history": job.command_history,
        "model_interactions": job.model_interactions,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }

# Health check
@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "depmigrant-api"}