'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Activity, ArrowRight, FileText, Github, Layers3, LoaderCircle, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { repositoryApi } from '@/lib/api';
import { apiErrorMessage } from '@/lib/dependencies';
import { uniqueRepositories as deduplicateRepositories } from '@/lib/repositories';
import { PageHeader } from './PageHeader';
import type { Repository } from '@/types';

export function RepositoriesPage({ initialQuery = '' }: { initialQuery?: string }) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [query, setQuery] = useState(initialQuery);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [type, setType] = useState<'git' | 'archive'>('git');
  const [urlOrPath, setUrlOrPath] = useState('');
  const [branch, setBranch] = useState('main');
  const [working, setWorking] = useState(false);
  const [deletingRepositoryId, setDeletingRepositoryId] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const refresh = async () => {
    setLoading(true);
    try {
      const response = await repositoryApi.list();
      setRepositories(response.data);
      setFailed(false);
      setError('');
    } catch (requestError) {
      setFailed(true);
      setError(apiErrorMessage(requestError, 'Could not load repositories. Check the backend connection.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void refresh(); }, []);
  useEffect(() => { setQuery(initialQuery); }, [initialQuery]);

  const uniqueRepositories = useMemo(() => deduplicateRepositories(repositories), [repositories]);

  const filteredRepositories = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return needle
      ? uniqueRepositories.filter((repository) =>
        `${repository.name} ${repository.path} ${repository.url ?? ''}`.toLowerCase().includes(needle))
      : uniqueRepositories;
  }, [uniqueRepositories, query]);

  const addRepository = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!urlOrPath.trim()) {
      setError(type === 'git' ? 'Enter a Git URL.' : 'Enter an archive path available to the backend.');
      return;
    }
    setWorking(true);
    setError('');
    setNotice('');
    try {
      const response = await repositoryApi.create(type === 'git'
        ? { path: '', type: 'git', url: urlOrPath.trim(), branch: branch.trim() || undefined }
        : { path: urlOrPath.trim(), type: 'archive' });
      setRepositories((current) => [response.data, ...current.filter((item) => item.id !== response.data.id)]);
      setUrlOrPath('');
      setNotice(`Added repository ${response.data.name}.`);
      setShowForm(false);
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Repository could not be added.'));
    } finally {
      setWorking(false);
    }
  };

  const deleteRepository = async (repository: Repository) => {
    if (deletingRepositoryId) return;
    if (!window.confirm(`Remove the registration for "${repository.name}"? This will not delete its local files or remote repository.`)) return;
    setDeletingRepositoryId(repository.id);
    setError('');
    setNotice('');
    try {
      await repositoryApi.remove(repository.id);
      setRepositories((current) => current.filter((item) => item.id !== repository.id));
      await refresh();
      setNotice(`Removed the registration for ${repository.name}. Repository files were not deleted.`);
    } catch (requestError) {
      const detail = apiErrorMessage(requestError, 'Repository registration could not be removed.');
      const status = axios.isAxiosError(requestError) ? requestError.response?.status : undefined;
      setError(status === 405
        ? `The connected backend does not support repository deletion (HTTP 405: ${detail}). Restart it from the current project version and retry.`
        : detail);
    } finally {
      setDeletingRepositoryId('');
    }
  };

  return (
    <div className="workspace-page">
      <PageHeader
        eyebrow="WORKSPACE LIBRARY"
        title="Repositories"
        description="Repositories are loaded from the connected backend. Open a record for details or inspect its manifests."
        action={<button className="outline-button" type="button" onClick={() => void refresh()} disabled={loading}><RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh</button>}
      />
      {error && <div className="error-banner" role="alert"><Activity size={17} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}>×</button></div>}
      {notice && <div className="notice-banner" role="status"><Layers3 size={16} /><span>{notice}</span><button aria-label="Dismiss notice" onClick={() => setNotice('')}>×</button></div>}

      <section className="panel page-panel">
        <div className="page-section-heading"><div><p className="eyebrow">REGISTERED SOURCES</p><h2>{loading ? 'Loading repositories…' : failed ? 'Repository list unavailable' : `${uniqueRepositories.length} unique ${uniqueRepositories.length === 1 ? 'repository' : 'repositories'}`}</h2><p>{loading ? 'Loading registrations from the backend.' : failed ? 'Registration count unavailable.' : `${repositories.length} ${repositories.length === 1 ? 'registration' : 'registrations'} returned by the backend. Search filters the unique repositories shown below.`}</p></div><button className="gold-button" type="button" onClick={() => setShowForm((open) => !open)}><Plus size={14} /> {showForm ? 'Close form' : 'Add repository'}</button></div>
        <input className="page-search-input" value={query} onChange={(event) => setQuery(event.target.value)} aria-label="Filter repositories" placeholder="Filter by repository name, path, or URL" />

        {showForm && <form className="repository-add-form" onSubmit={(event) => void addRepository(event)}>
          <div className="source-switch" role="group" aria-label="Repository type">
            <button type="button" className={type === 'git' ? 'source-active' : ''} onClick={() => setType('git')}><Github size={14} /> Git URL</button>
            <button type="button" className={type === 'archive' ? 'source-active' : ''} onClick={() => setType('archive')}><FileText size={14} /> Local archive</button>
          </div>
          <div className="inline-field">
            <input value={urlOrPath} onChange={(event) => setUrlOrPath(event.target.value)} aria-label={type === 'git' ? 'Git repository URL' : 'Backend archive path'} placeholder={type === 'git' ? 'https://github.com/owner/repository' : '/path/to/archive.zip'} />
            {type === 'git' && <input value={branch} onChange={(event) => setBranch(event.target.value)} aria-label="Git branch" placeholder="Branch (default main)" />}
            <button className="gold-button" type="submit" disabled={working}>{working ? <LoaderCircle className="spin" size={14} /> : <Plus size={14} />} Add</button>
          </div>
          <p className="form-help">{type === 'git' ? 'Submitting may make the backend clone the URL.' : 'Archive paths must be accessible to the backend host; this form does not upload files.'}</p>
        </form>}

        {loading ? <div className="page-empty"><LoaderCircle className="spin" size={20} /><span>Loading repository records…</span></div>
          : failed ? <div className="page-empty"><Activity size={20} /><strong>Could not retrieve repositories</strong><span>Check the backend connection, then retry.</span><button className="outline-button" onClick={() => void refresh()}>Retry</button></div>
            : filteredRepositories.length === 0 ? <div className="page-empty"><Layers3 size={20} /><strong>{query ? 'No repositories match this filter.' : 'No repositories are registered.'}</strong><span>{query ? 'Try another search.' : 'Add a repository to begin.'}</span></div>
              : <div className="repository-cards">{filteredRepositories.map((repository) => (
                <article className="repository-card" key={repository.id}>
                  <div className="repo-row-icon">{repository.type === 'git' ? <Github size={17} /> : <FileText size={17} />}</div>
                  <div className="repository-card-copy"><strong>{repository.name}</strong><span>{repository.path}</span>{repository.url && <span>{repository.url}</span>}</div>
                  <span className="repo-row-type">{repository.type}</span>
                  <Link className="outline-button" href={`/repositories/${encodeURIComponent(repository.id)}`}>Details <ArrowRight size={13} /></Link>
                  <button className="outline-button repository-delete-button" type="button" onClick={() => void deleteRepository(repository)} disabled={deletingRepositoryId !== ''} aria-label={`Delete registration for ${repository.name}`}>
                    {deletingRepositoryId === repository.id ? <LoaderCircle className="spin" size={13} /> : <Trash2 size={13} />}
                    {deletingRepositoryId === repository.id ? 'Removing…' : 'Delete'}
                  </button>
                </article>
              ))}</div>}
      </section>
    </div>
  );
}
