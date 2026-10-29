export interface Repository {
  id: string;
  name: string;
  path: string;
  type: 'git' | 'archive';
  url?: string;
  branch?: string;
  created_at?: string;
}

export interface Dependency {
  name: string;
  current_version: string | null;
  target_version: string;
  ecosystem: 'pypi' | 'npm' | 'maven' | 'gradle';
  manifest_path: string;
}

export interface MigrationPlan {
  id: string;
  repository_id: string;
  dependency: Dependency;
  breaking_changes: BreakingChange[];
  affected_files: AffectedFile[];
  planned_edits: PlannedEdit[];
  execution_commands: string[] | string[][];
  risks: string[];
  created_at: string;
}

export interface BreakingChange {
  type: 'removed_api' | 'changed_signature' | 'behavior_change' | 'config_incompatibility' | 'transitive_conflict';
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  source: string;
}

export interface AffectedFile {
  path: string;
  reason: string;
  estimated_changes: number;
}

export interface PlannedEdit {
  file_path: string;
  original_code: string;
  new_code: string;
  description: string;
}

export interface BaselineResult {
  id: string;
  migration_id: string;
  tests_passed: number;
  tests_failed: number;
  tests_skipped: number;
  build_success: boolean;
  import_check_success: boolean;
  test_report_valid?: boolean;
  pytest_exit_code?: number | null;
  test_run_success?: boolean;
  pre_existing_failures: TestFailure[];
  command_outputs: CommandOutput[];
  git_commit: string;
  created_at: string;
}

export interface TestFailure {
  test_name: string;
  error_message: string;
  file_path: string;
  line_number?: number;
}

export interface CommandOutput {
  command: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  duration_ms: number;
  timestamp: string;
}

export interface MigrationJob {
  id: string;
  repository_id: string;
  plan_id: string;
  status: 'pending' | 'inspecting' | 'baseline' | 'planning' | 'patching' | 'executing' | 'diagnosing' | 'repairing' | 'verifying' | 'completed' | 'failed' | 'blocked';
  current_step?: string | null;
  progress: number;
  baseline_result?: BaselineResult | null;
  final_result?: VerificationResult | null;
  repair_attempts: RepairAttempt[];
  command_history: CommandOutput[];
  model_interactions: ModelInteraction[];
  started_at: string;
  updated_at?: string | null;
  completed_at?: string;
}

export interface RepairAttempt {
  attempt_number: number;
  failure_type: string;
  diagnosis: string;
  proposed_patch: PlannedEdit[];
  applied: boolean;
  result?: CommandOutput;
  created_at: string;
}

export interface ModelInteraction {
  id: string;
  job_id: string;
  stage: 'planning' | 'diagnosis' | 'repair';
  prompt: string;
  response: string;
  tokens_used?: number;
  duration_ms: number;
  timestamp: string;
}

export interface VerificationResult {
  id: string;
  migration_id: string;
  status: 'verified' | 'partially_verified' | 'failed' | 'blocked';
  tests_passed: number;
  tests_failed: number;
  tests_skipped: number;
  new_regressions: TestFailure[];
  modified_files: string[];
  repair_attempts_count: number;
  command_outputs: CommandOutput[];
  summary: string;
  created_at: string;
}

export interface JobStatus {
  job: MigrationJob;
  logs: JobLog[];
}

export interface MigrationReport {
  job_id: string;
  status: string;
  baseline: BaselineResult | null;
  final_result: VerificationResult | null;
  repair_attempts: RepairAttempt[];
  command_history: CommandOutput[];
  model_interactions: ModelInteraction[];
  started_at: string;
  completed_at?: string | null;
}

export interface JobLog {
  timestamp: string;
  level: string;
  message: string;
  command?: string;
  exitCode?: number;
}