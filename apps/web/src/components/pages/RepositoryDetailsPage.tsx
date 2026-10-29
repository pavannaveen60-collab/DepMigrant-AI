'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Activity, ArrowLeft, FileText, Github, LoaderCircle, Package, RefreshCw } from 'lucide-react';
import { repositoryApi } from '@/lib/api';
import { apiErrorMessage, parseInspectedDependencies } from '@/lib/dependencies';
import { PageHeader } from './PageHeader';
import type { Repository } from '@/types';

export function RepositoryDetailsPage({ repositoryId }: { repositoryId: string }) {
  const [repository, setRepository] = useState<Repository | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [dependencies, setDependencies] = useState<ReturnType<typeof parseInspectedDependencies> | null>(null);

  useEffect(() => {
    let active = true;
    repositoryApi.get(repositoryId)
      .then((response) => { if (active) setRepository(response.data); })
      .catch((requestError: unknown) => { if (active) setError(apiErrorMessage(requestError, 'Could not load this repository.')); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [repositoryId]);

  const inspect = async () => {
    setWorking(true);
    setError('');
    try {
      const response = await repositoryApi.inspect(repositoryId);
      setDependencies(parseInspectedDependencies(response.data));
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Could not inspect this repository.'));
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="workspace-page">
      <PageHeader eyebrow="REPOSITORY DETAILS" title={repository?.name ?? (loading ? 'Loading repository…' : 'Repository unavailable')} description="Details and manifest inspection are retrieved from the existing repository endpoints." action={<Link className="outline-button" href="/repositories"><ArrowLeft size={14} /> All repositories</Link>} />
      {error && <div className="error-banner" role="alert"><Activity size={17} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}>×</button></div>}
      {loading ? <section className="panel page-empty"><LoaderCircle className="spin" size={20} /><span>Loading repository details…</span></section>
        : repository && <section className="panel page-panel">
          <div className="page-section-heading"><div><p className="eyebrow">REGISTERED REPOSITORY</p><h2>{repository.name}</h2><p>{repository.type.toUpperCase()} · Added {repository.created_at ? new Date(repository.created_at).toLocaleString() : 'date not provided'}</p></div><button className="outline-button" type="button" onClick={() => void inspect()} disabled={working}>{working ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />} Inspect manifests</button></div>
          <dl className="detail-grid"><div><dt>Path</dt><dd>{repository.path}</dd></div><div><dt>URL</dt><dd>{repository.url || 'Not provided'}</dd></div><div><dt>Branch</dt><dd>{repository.branch || 'Not provided'}</dd></div><div><dt>Repository ID</dt><dd>{repository.id}</dd></div></dl>
          {dependencies && <div className="detail-inspection">
            <h3><Package size={16} /> Inspected dependencies</h3>
            {dependencies.length === 0 ? <div className="page-empty compact"><FileText size={18} /><span>No supported dependency entries were found in the returned manifests.</span></div>
              : <div className="dependency-tags">{dependencies.map((dependency) => <span key={dependency.name}><Package size={13} /><strong>{dependency.name}</strong><small>Installed version: Unknown · Manifest requirement: {dependency.versionConstraint || 'not specified'} · {dependency.manifest}</small></span>)}</div>}
          </div>}
        </section>}
    </div>
  );
}
