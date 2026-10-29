'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { MigrationPlan, Dependency, BreakingChange, AffectedFile, PlannedEdit } from '@/types';

interface MigrationPlanViewProps {
  repository: { name: string; id: string };
  plan: MigrationPlan | null;
  onCreatePlan: (dependency: Dependency) => void;
  onStartMigration: () => void;
  onBack: () => void;
  loading: boolean;
}

export function MigrationPlanView({ repository, plan, onCreatePlan, onStartMigration, onBack, loading }: MigrationPlanViewProps) {
  const [showPlanForm, setShowPlanForm] = useState(!plan);
  const [dependency, setDependency] = useState({
    name: '',
    current_version: '',
    target_version: '',
  });
  const [formError, setFormError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    
    if (!dependency.name || !dependency.target_version) {
      setFormError('Please provide dependency name and target version');
      return;
    }

    onCreatePlan({
      name: dependency.name,
      current_version: dependency.current_version,
      target_version: dependency.target_version,
      ecosystem: 'pypi',
      manifest_path: 'pyproject.toml',
    });
  };

  if (!plan) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <Button variant="ghost" size="sm" onClick={onBack}>
              ← Back
            </Button>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mt-2">
              Create Migration Plan
            </h2>
            <p className="text-gray-600 dark:text-gray-400">Repository: {repository.name}</p>
          </div>
        </div>

        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle>Configure Migration</CardTitle>
            <CardDescription>Select the dependency and target version to migrate</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Dependency Name"
                value={dependency.name}
                onChange={(e) => setDependency({ ...dependency, name: e.target.value })}
                placeholder="e.g., requests, django, numpy"
                required
              />
              <Input
                label="Current Version (optional)"
                value={dependency.current_version}
                onChange={(e) => setDependency({ ...dependency, current_version: e.target.value })}
                placeholder="e.g., 2.28.0"
              />
              <Input
                label="Target Version"
                value={dependency.target_version}
                onChange={(e) => setDependency({ ...dependency, target_version: e.target.value })}
                placeholder="e.g., 2.31.0"
                required
              />

              {formError && (
                <div className="text-red-600 dark:text-red-400 text-sm">{formError}</div>
              )}

              <div className="flex gap-3 pt-4">
                <Button type="submit" disabled={loading}>
                  Generate Plan
                </Button>
                <Button type="button" variant="secondary" onClick={onBack}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Button variant="ghost" size="sm" onClick={onBack}>
            ← Back
          </Button>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mt-2">
            Migration Plan
          </h2>
          <p className="text-gray-600 dark:text-gray-400">Repository: {repository.name}</p>
        </div>
        <Button onClick={onStartMigration} disabled={loading} className="ml-auto">
          Start Migration
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Dependency</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="text-2xl font-bold text-gray-900 dark:text-white">{plan.dependency.name}</div>
                <Badge variant="status" status="completed">{plan.dependency.ecosystem}</Badge>
              </div>
              <div className="flex items-center gap-4 text-gray-600 dark:text-gray-400">
                <span>Reported start: {plan.dependency.current_version || 'unknown'} (not independently verified)</span>
                <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
                <span className="text-primary-600 font-medium">{plan.dependency.target_version}</span>
              </div>
              <div className="text-sm text-gray-500">Manifest: {plan.dependency.manifest_path}</div>
            </CardContent>
          </Card>

          {plan.breaking_changes.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Breaking Changes ({plan.breaking_changes.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {plan.breaking_changes.map((change, index) => (
                    <div key={index} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border-l-4 border-primary-500">
                      <div className="flex items-start gap-3">
                        <Badge variant="severity" severity={change.severity}>{change.severity}</Badge>
                        <div className="flex-1">
                          <p className="font-medium text-gray-900 dark:text-white">{change.description}</p>
                          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Type: {change.type.replace('_', ' ')}</p>
                          <p className="text-sm text-gray-500 dark:text-gray-400">Source: {change.source}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {plan.affected_files.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Affected Files ({plan.affected_files.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {plan.affected_files.map((file, index) => (
                    <div key={index} className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded">
                      <div className="flex-1 min-w-0">
                        <p className="font-mono text-sm text-gray-900 dark:text-white truncate">{file.path}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{file.reason}</p>
                      </div>
                      <Badge variant="default">{file.estimated_changes} changes</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {plan.planned_edits.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Planned Edits ({plan.planned_edits.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4 max-h-96 overflow-y-auto">
                  {plan.planned_edits.map((edit, index) => (
                    <div key={index} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800 font-mono text-sm text-gray-900 dark:text-white">
                        {edit.file_path}
                      </div>
                      <div className="p-4 space-y-2">
                        <p className="text-sm text-gray-600 dark:text-gray-400">{edit.description}</p>
                        <div className="font-mono text-xs bg-gray-950 dark:bg-black p-3 rounded max-h-40 overflow-y-auto">
                          <div className="text-red-400">− {edit.original_code.split('\n')[0]}</div>
                          <div className="text-green-400">+ {edit.new_code.split('\n')[0]}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {plan.risks.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Known Risks</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {plan.risks.map((risk, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400">
                      <svg className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                      {risk}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {plan.execution_commands.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Execution Commands</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="font-mono text-sm bg-gray-950 dark:bg-black p-4 rounded max-h-60 overflow-y-auto">
                  {plan.execution_commands.map((cmd, index) => (
                    <div key={index} className="text-green-400 mb-1">
                      $ {Array.isArray(cmd) ? cmd.join(' ') : cmd}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Plan Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-3 bg-primary-50 dark:bg-primary-900/30 rounded-lg">
                <p className="text-sm text-primary-700 dark:text-primary-300">
                  This plan will migrate <strong>{plan.dependency.name}</strong> from 
                  <strong>{plan.dependency.current_version || 'unknown starting version'}</strong> to 
                  <strong>{plan.dependency.target_version}</strong>.
                </p>
              </div>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Breaking Changes</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{plan.breaking_changes.length}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Affected Files</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{plan.affected_files.length}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Planned Edits</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{plan.planned_edits.length}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Execution Commands</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{plan.execution_commands.length}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500 dark:text-gray-400">Known Risks</dt>
                  <dd className="font-medium text-gray-900 dark:text-white">{plan.risks.length}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}