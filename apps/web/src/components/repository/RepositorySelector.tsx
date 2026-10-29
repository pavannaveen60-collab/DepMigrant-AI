'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Repository } from '@/types';

interface RepositorySelectorProps {
  repositories: Repository[];
  onSelect: (repo: Repository) => void;
  onRefresh: () => void;
  loading: boolean;
}

export function RepositorySelector({ repositories, onSelect, onRefresh, loading }: RepositorySelectorProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newRepo, setNewRepo] = useState({
    path: '',
    type: 'git' as 'git' | 'archive',
    url: '',
    branch: 'main',
  });
  const [formError, setFormError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    
    if (!newRepo.path && !newRepo.url) {
      setFormError('Please provide a local path or Git URL');
      return;
    }

    try {
      const response = await fetch('/api/repositories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRepo),
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to add repository');
      }
      
      const repo = await response.json();
      onSelect(repo);
      setShowAddForm(false);
      setNewRepo({ path: '', type: 'git', url: '', branch: 'main' });
    } catch (err: any) {
      setFormError(err.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Select Repository</h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Choose a repository to migrate dependencies
          </p>
        </div>
        <Button onClick={() => setShowAddForm(true)}>
          Add Repository
        </Button>
      </div>

      {showAddForm && (
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle>Add Repository</CardTitle>
            <CardDescription>Enter the path or URL of the repository to migrate</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Repository Type
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="type"
                      value="git"
                      checked={newRepo.type === 'git'}
                      onChange={(e) => setNewRepo({ ...newRepo, type: e.target.value as 'git' | 'archive' })}
                      className="text-primary-600"
                    />
                    <span>Git Repository</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="type"
                      value="archive"
                      checked={newRepo.type === 'archive'}
                      onChange={(e) => setNewRepo({ ...newRepo, type: e.target.value as 'git' | 'archive' })}
                      className="text-primary-600"
                    />
                    <span>Local Archive</span>
                  </label>
                </div>
              </div>

              {newRepo.type === 'git' && (
                <div className="space-y-4">
                  <Input
                    label="Git URL"
                    value={newRepo.url}
                    onChange={(e) => setNewRepo({ ...newRepo, url: e.target.value })}
                    placeholder="https://github.com/user/repo.git"
                    required
                  />
                  <Input
                    label="Branch (optional)"
                    value={newRepo.branch}
                    onChange={(e) => setNewRepo({ ...newRepo, branch: e.target.value })}
                    placeholder="main"
                  />
                </div>
              )}

              {newRepo.type === 'archive' && (
                <Input
                  label="Local Path"
                  value={newRepo.path}
                  onChange={(e) => setNewRepo({ ...newRepo, path: e.target.value })}
                  placeholder="/path/to/project"
                  required
                />
              )}

              {formError && (
                <div className="text-red-600 dark:text-red-400 text-sm">{formError}</div>
              )}

              <div className="flex gap-3 pt-4">
                <Button type="submit" disabled={loading}>
                  Add Repository
                </Button>
                <Button type="button" variant="secondary" onClick={() => setShowAddForm(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {repositories.length === 0 && !showAddForm && (
        <Card className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">No repositories yet</h3>
          <p className="mt-2 text-gray-500 dark:text-gray-400">Add a repository to start a migration</p>
          <Button onClick={() => setShowAddForm(true)} className="mt-4">
            Add Repository
          </Button>
        </Card>
      )}

      {repositories.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {repositories.map((repo) => (
            <Card key={repo.id} className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => onSelect(repo)}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle>{repo.name}</CardTitle>
                    <CardDescription>{repo.path}</CardDescription>
                  </div>
                  <Badge variant="status" status={repo.type === 'git' ? 'completed' : 'pending'}>
                    {repo.type}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                  {repo.url && (
                    <a href={repo.url} target="_blank" rel="noopener noreferrer" className="hover:text-primary-600">
                      View on Git
                    </a>
                  )}
                  {repo.branch && <span>Branch: {repo.branch}</span>}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}