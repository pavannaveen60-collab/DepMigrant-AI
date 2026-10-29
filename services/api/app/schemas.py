from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

class RepositoryType(str, Enum):
    GIT = "git"
    ARCHIVE = "archive"

class MigrationStatus(str, Enum):
    PENDING = "pending"
    INSPECTING = "inspecting"
    BASELINE = "baseline"
    PLANNING = "planning"
    PATCHING = "patching"
    EXECUTING = "executing"
    DIAGNOSING = "diagnosing"
    REPAIRING = "repairing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"

class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    FAILED = "failed"
    BLOCKED = "blocked"

class BreakingChangeType(str, Enum):
    REMOVED_API = "removed_api"
    CHANGED_SIGNATURE = "changed_signature"
    BEHAVIOR_CHANGE = "behavior_change"
    CONFIG_INCOMPATIBILITY = "config_incompatibility"
    TRANSITIVE_CONFLICT = "transitive_conflict"

class FailureType(str, Enum):
    DEPENDENCY_RESOLUTION = "dependency_resolution"
    INSTALLATION = "installation"
    SYNTAX = "syntax"
    IMPORT = "import"
    API_INCOMPATIBILITY = "api_incompatibility"
    CONFIGURATION = "configuration"
    TEST_REGRESSION = "test_regression"
    RUNTIME = "runtime"
    ENVIRONMENT = "environment"

class BreakingChange(BaseModel):
    type: BreakingChangeType
    description: str
    severity: str
    source: str

class AffectedFile(BaseModel):
    path: str
    reason: str
    estimated_changes: int

class PlannedEdit(BaseModel):
    file_path: str
    original_code: str
    new_code: str
    description: str

class Dependency(BaseModel):
    name: str
    current_version: Optional[str]
    target_version: str
    ecosystem: str
    manifest_path: str

class MigrationPlanCreate(BaseModel):
    repository_id: str
    dependency_name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    current_version: Optional[str] = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9.!+_-]{0,127}$",
    )
    target_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9.!+_-]{0,127}$")

class MigrationPlanResponse(BaseModel):
    id: str
    repository_id: str
    dependency: Dependency
    breaking_changes: List[BreakingChange]
    affected_files: List[AffectedFile]
    planned_edits: List[PlannedEdit]
    execution_commands: Union[List[str], List[List[str]]]
    risks: List[str]
    created_at: datetime

class RepositoryCreate(BaseModel):
    path: str
    type: RepositoryType
    url: Optional[str] = None
    branch: Optional[str] = None

class RepositoryResponse(BaseModel):
    id: str
    name: str
    path: str
    type: RepositoryType
    url: Optional[str]
    branch: Optional[str]
    created_at: datetime

class CommandOutput(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timestamp: datetime

class TestFailure(BaseModel):
    test_name: str
    error_message: str
    file_path: str
    line_number: Optional[int] = None

class BaselineResult(BaseModel):
    id: str
    migration_id: str
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    build_success: bool
    import_check_success: bool
    test_report_valid: bool = False
    pytest_exit_code: Optional[int] = None
    test_run_success: bool = False
    pre_existing_failures: List[TestFailure]
    command_outputs: List[CommandOutput]
    git_commit: str
    created_at: datetime

class RepairAttempt(BaseModel):
    attempt_number: int
    failure_type: str
    diagnosis: str
    proposed_patch: List[PlannedEdit]
    applied: bool
    result: Optional[CommandOutput] = None
    created_at: datetime

class ModelInteraction(BaseModel):
    id: str
    job_id: str
    stage: str
    prompt: str
    response: str
    tokens_used: Optional[int] = None
    duration_ms: int
    timestamp: datetime

class MigrationJobResponse(BaseModel):
    id: str
    repository_id: str
    plan_id: str
    status: MigrationStatus
    current_step: Optional[str]
    progress: int
    baseline_result: Optional[BaselineResult]
    final_result: Optional[Dict[str, Any]]
    repair_attempts: List[RepairAttempt]
    command_history: List[CommandOutput]
    model_interactions: List[ModelInteraction]
    started_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]

class VerificationResult(BaseModel):
    id: str
    migration_id: str
    status: VerificationStatus
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    new_regressions: List[TestFailure]
    modified_files: List[str]
    repair_attempts_count: int
    command_outputs: List[CommandOutput]
    summary: str
    created_at: datetime

class JobStatusResponse(BaseModel):
    job: MigrationJobResponse
    logs: List[Dict[str, Any]]