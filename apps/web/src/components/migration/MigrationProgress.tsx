'use client';

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Progress, StepIndicator } from '@/components/ui/Progress';
import { LogViewer } from '@/components/ui/LogViewer';
import { Button } from '@/components/ui/Button';
import { MigrationJob } from '@/types';
import { formatTimestamp, formatDuration, getStatusColor } from '@/lib/utils';

interface MigrationProgressProps {
  job: MigrationJob;
  jobStatus: { job: MigrationJob; logs: any[] } | null;
  steps: string[];
  currentStepIndex: number;
  onCancel: () => void;
}

export function MigrationProgress({ job, jobStatus, steps, currentStepIndex, onCancel }: MigrationProgressProps) {
  const logs = jobStatus?.logs || job.command_history.map((cmd) => ({
    timestamp: cmd.timestamp,
    level: cmd.exit_code === 0 ? 'info' : 'error',
    message: cmd.stderr || cmd.stdout,
    command: cmd.command,
    exitCode: cmd.exit_code,
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Migration in Progress</h2>
          <p className="text-gray-600 dark:text-gray-400">Job ID: {job.id.slice(0, 8)}...</p>
        </div>
        <div className="flex items-center gap-4">
          <Badge variant="status" status={job.status} className="text-sm">
            {job.status}
          </Badge>
          <Button variant="danger" onClick={onCancel} size="sm">
            Cancel
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Workflow Progress</CardTitle>
        </CardHeader>
        <CardContent>
          <StepIndicator steps={steps} currentStep={currentStepIndex} />
          <Progress value={job.progress} max={100} showLabel label="Overall Progress" className="mt-4" />
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            Current step: <span className="font-medium text-gray-900 dark:text-white">{job.current_step}</span>
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Live Logs</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <LogViewer logs={logs} autoScroll maxHeight="500px" />
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Job Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Job ID</dt>
                  <dd className="font-mono font-medium text-gray-900 dark:text-white">{job.id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Plan ID</dt>
                  <dd className="font-mono font-medium text-gray-900 dark:text-white">{job.plan_id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Started</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{formatTimestamp(job.started_at)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Updated</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{job.updated_at ? formatTimestamp(job.updated_at) : 'Not updated'}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Repair Attempts</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{job.repair_attempts.length}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Model Interactions</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{job.model_interactions.length}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          {job.repair_attempts.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Repair Attempts ({job.repair_attempts.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 max-h-60 overflow-y-auto">
                  {job.repair_attempts.map((attempt, index) => (
                    <div key={index} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border-l-4 border-yellow-500">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-gray-900 dark:text-white">Attempt #{attempt.attempt_number}</span>
                        <Badge variant="severity" severity={attempt.applied ? 'low' : 'high'}>
                          {attempt.applied ? 'Applied' : 'Rejected'}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-600 dark:text-gray-400">{attempt.failure_type}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{attempt.diagnosis.slice(0, 100)}...</p>
                      {attempt.result && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 font-mono">
                          Exit: {attempt.result.exit_code} ({formatDuration(attempt.result.duration_ms)})
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {job.model_interactions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Model Interactions ({job.model_interactions.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 max-h-60 overflow-y-auto">
                  {job.model_interactions.map((interaction, index) => (
                    <div key={index} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                      <div className="flex items-center justify-between mb-1">
                        <Badge variant="default">{interaction.stage}</Badge>
                        <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                          {formatDuration(interaction.duration_ms)}
                        </span>
                      </div>
                      <p className="text-xs text-gray-600 dark:text-gray-400 font-mono max-h-20 overflow-y-auto">
                        {interaction.prompt.slice(0, 200)}...
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}