from sqlalchemy import Column, String, Text, DateTime, Integer, Enum as SQLEnum, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
import enum
import uuid

class RepositoryType(str, enum.Enum):
    GIT = "git"
    ARCHIVE = "archive"

class MigrationStatus(str, enum.Enum):
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

class VerificationStatus(str, enum.Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    FAILED = "failed"
    BLOCKED = "blocked"

class BreakingChangeType(str, enum.Enum):
    REMOVED_API = "removed_api"
    CHANGED_SIGNATURE = "changed_signature"
    BEHAVIOR_CHANGE = "behavior_change"
    CONFIG_INCOMPATIBILITY = "config_incompatibility"
    TRANSITIVE_CONFLICT = "transitive_conflict"

class FailureType(str, enum.Enum):
    DEPENDENCY_RESOLUTION = "dependency_resolution"
    INSTALLATION = "installation"
    SYNTAX = "syntax"
    IMPORT = "import"
    API_INCOMPATIBILITY = "api_incompatibility"
    CONFIGURATION = "configuration"
    TEST_REGRESSION = "test_regression"
    RUNTIME = "runtime"
    ENVIRONMENT = "environment"

class Repository(Base):
    __tablename__ = "repositories"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    path = Column(String(500), nullable=False)
    type = Column(SQLEnum(RepositoryType), nullable=False)
    url = Column(String(500), nullable=True)
    branch = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    migrations = relationship("MigrationJob", back_populates="repository")

class MigrationPlan(Base):
    __tablename__ = "migration_plans"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id"), nullable=False)
    dependency_name = Column(String(255), nullable=False)
    current_version = Column(String(100), nullable=True)
    target_version = Column(String(100), nullable=False)
    ecosystem = Column(String(50), nullable=False)
    manifest_path = Column(String(500), nullable=False)
    breaking_changes = Column(JSON, nullable=True)
    affected_files = Column(JSON, nullable=True)
    planned_edits = Column(JSON, nullable=True)
    execution_commands = Column(JSON, nullable=True)
    risks = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    jobs = relationship("MigrationJob", back_populates="plan")

class MigrationJob(Base):
    __tablename__ = "migration_jobs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id"), nullable=False)
    plan_id = Column(String(36), ForeignKey("migration_plans.id"), nullable=False)
    status = Column(SQLEnum(MigrationStatus), default=MigrationStatus.PENDING)
    current_step = Column(String(100), nullable=True)
    progress = Column(Integer, default=0)
    baseline_result = Column(JSON, nullable=True)
    final_result = Column(JSON, nullable=True)
    repair_attempts = Column(JSON, nullable=True)
    command_history = Column(JSON, nullable=True)
    model_interactions = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    repository = relationship("Repository", back_populates="migrations")
    plan = relationship("MigrationPlan", back_populates="jobs")

class ModelInteraction(Base):
    __tablename__ = "model_interactions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("migration_jobs.id"), nullable=False)
    stage = Column(String(50), nullable=False)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    tokens_used = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())