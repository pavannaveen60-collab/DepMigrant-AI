'use client';

import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { LogViewer, DiffViewer } from '@/components/ui/LogViewer';
import { MigrationJob, VerificationResult, TestFailure, CommandOutput } from '@/types';
import { formatTimestamp, formatDuration, getStatusColor } from '@/lib/utils';

interface VerificationReportProps {
  job: MigrationJob;
  jobStatus: { job: MigrationJob; logs: any[] };
  onNewMigration: () => void;
}

export function VerificationReport({ job, jobStatus, onNewMigration }: VerificationReportProps) {
  const result = jobStatus.job.final_result;
  const logs = jobStatus.logs || job.command_history.map((cmd) => ({
    timestamp: cmd.timestamp,
    level: cmd.exit_code === 0 ? 'info' : 'error',
    message: cmd.stderr || cmd.stdout,
    command: cmd.command,
    exitCode: cmd.exit_code,
  }));

  if (!result) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Verification Report</h2>
            <p className="text-gray-600 dark:text-gray-400">Generating report...</p>
          </div>
        </div>
        <Card>
          <CardContent className="py-12 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
            <p className="mt-4 text-gray-600 dark:text-gray-400">Finalizing verification...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    verified: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
    partially_verified: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
    failed: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
    blocked: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Verification Report</h2>
          <p className="text-gray-600 dark:text-gray-400">Migration completed with status: {result.status}</p>
        </div>
        <div className="flex items-center gap-4">
          <Badge variant="status" status={result.status} className="text-lg px-4 py-2">
            {result.status.replace('_', ' ').toUpperCase()}
          </Badge>
          <Button onClick={onNewMigration}>New Migration</Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="prose dark:prose-invert max-w-none">
                <p className="whitespace-pre-wrap">{result.summary}</p>
              </div>
            </CardContent>
          </Card>

          {result.new_regressions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>New Regressions ({result.new_regressions.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {result.new_regressions.map((regression, index) => (
                    <div key={index} className="p-3 bg-red-50 dark:bg-red-900/30 rounded-lg border-l-4 border-red-500">
                      <div className="flex items-start gap-3">
                        <svg className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                        </svg>
                        <div className="flex-1">
                          <p className="font-medium text-gray-900 dark:text-white">{regression.test_name}</p>
                          <p className="text-sm text-gray-600 dark:text-gray-400 font-mono">{regression.file_path}</p>
                          <p className="text-sm text-red-600 dark:text-red-400 mt-1">{regression.error_message}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {result.modified_files.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Modified Files ({result.modified_files.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {result.modified_files.map((file, index) => (
                    <div key={index} className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded">
                      <span className="font-mono text-sm text-gray-900 dark:text-white truncate max-w-[300px]">{file}</span>
                      <Button variant="ghost" size="sm">View Diff</Button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Command History</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <LogViewer logs={logs} autoScroll maxHeight="400px" />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Test Results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-4 bg-green-50 dark:bg-green-900/30 rounded-lg">
                  <div className="text-3xl font-bold text-green-600 dark:text-green-400">{result.tests_passed}</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Passed</div>
                </div>
                <div className="p-4 bg-red-50 dark:bg-red-900/30 rounded-lg">
                  <div className="text-3xl font-bold text-red-600 dark:text-red-400">{result.tests_failed}</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Failed</div>
                </div>
                <div className="p-4 bg-yellow-50 dark:bg-yellow-900/30 rounded-lg">
                  <div className="text-3xl font-bold text-yellow-600 dark:text-yellow-400">{result.tests_skipped}</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Skipped</div>
                </div>
              </div>
              <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-gray-500 dark:text-gray-400">Repair Attempts</dt>
                    <dd className="font-medium text-gray-900 dark:text-white">{result.repair_attempts_count}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500 dark:text-gray-400">Modified Files</dt>
                    <dd className="font-medium text-gray-900 dark:text-white">{result.modified_files.length}</dd>
                  </div>
                </dl>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Job Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Job ID</dt>
                  <dd className="font-mono font-medium text-gray-900 dark:text-white">{job.id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Status</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{job.status}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Started</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{formatTimestamp(job.started_at)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Completed</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">
                    {job.completed_at ? formatTimestamp(job.completed_at) : '—'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Model Calls</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{job.model_interactions.length}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button className="w-full" onClick={onNewMigration}>
                Start New Migration
              </Button>
              <Button variant="secondary" className="w-full">
                Download JSON Report
              </Button>
              <Button variant="ghost" className="w-full">
                View Full Logs
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}