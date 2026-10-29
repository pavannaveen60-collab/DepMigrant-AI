'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Activity, ArrowRight, CheckCircle2, FileText, Github, LoaderCircle, LockKeyhole, Package, Sparkles } from 'lucide-react';
import { migrationApi, repositoryApi } from '@/lib/api';
import { apiErrorMessage, parseInspectedDependencies } from '@/lib/dependencies';
import { uniqueRepositories } from '@/lib/repositories';
import { useWorkspace } from '@/components/WorkspaceShell';
import { PageHeader } from './PageHeader';
import { demoPlan } from '@/lib/demoPlan';
import type { MigrationPlan, Repository } from '@/types';

type RepositoryKind = 'git' | 'archive';

export function MigrationPage() {
  const { preferences, setLatestPlan } = useWorkspace();
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [repositoryId, setRepositoryId] = useState('');
  const [repositoryKind, setRepositoryKind] = useState<RepositoryKind>(preferences.defaultRepositoryType);
  const [repositoryInput, setRepositoryInput] = useState('');
  const [dependencyName, setDependencyName] = useState('');
  const [currentVersion, setCurrentVersion] = useState('');
  const [targetVersion, setTargetVersion] = useState('');
  const [dependencies, setDependencies] = useState<ReturnType<typeof parseInspectedDependencies>>([]);
  const [inspectionCompleted, setInspectionCompleted] = useState(false);
  const [plan, setPlan] = useState<MigrationPlan | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [loadingRepositories, setLoadingRepositories] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const selectedRepository = useMemo(
    () => repositories.find((repository) => repository.id === repositoryId) ?? null,
    [repositories, repositoryId],
  );

  const refreshRepositories = async () => {
    setLoadingRepositories(true);
    try {
      const response = await repositoryApi.list();
      setRepositories(uniqueRepositories(response.data));
      setError('');
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Could not load repositories. Check the backend connection.'));
    } finally {
      setLoadingRepositories(false);
    }
  };

  useEffect(() => {
    void refreshRepositories();
  }, []);

  useEffect(() => {
    setRepositoryKind(preferences.defaultRepositoryType);
  }, [preferences.defaultRepositoryType]);

  const registerRepository = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!repositoryInput.trim()) {
      setError(repositoryKind === 'git' ? 'Enter a Git repository URL.' : 'Enter an archive path available to the backend.');
      return;
    }
    setWorking(true);
    setError('');
    setNotice('');
    setPlan(null);
    setDemoMode(false);
    setDependencies([]);
    try {
      const response = await repositoryApi.create(repositoryKind === 'git'
        ? { path: '', type: 'git', url: repositoryInput.trim() }
        : { path: repositoryInput.trim(), type: 'archive' });
      setRepositories((current) => uniqueRepositories([response.data, ...current.filter((item) => item.id !== response.data.id)]));
      setRepositoryId(response.data.id);
      setInspectionCompleted(false);
      setNotice(`Repository ${response.data.name} was registered. Inspect it to read its dependency manifests.`);
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Repository could not be added.'));
    } finally {
      setWorking(false);
    }
  };

  const inspectRepository = async () => {
    if (!selectedRepository) return;
    setWorking(true);
    setDemoMode(false);
    setError('');
    setNotice('');
    setPlan(null);
    try {
      const response = await repositoryApi.inspect(selectedRepository.id);
      const found = parseInspectedDependencies(response.data);
      setDependencies(found);
      setInspectionCompleted(true);
      setDependencyName(found[0]?.name ?? '');
      setCurrentVersion('');
      setTargetVersion('');
      setNotice(`Inspection completed. ${found.length} supported dependency entries were found.`);
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Could not inspect this repository.'));
    } finally {
      setWorking(false);
    }
  };

  const createPlan = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedRepository || !dependencyName || !currentVersion.trim() || !targetVersion.trim()) {
      setError('Select a repository and dependency, then enter the current and target versions.');
      return;
    }
    setWorking(true);
    setDemoMode(false);
    setError('');
    setNotice('');
    try {
      const response = await migrationApi.createPlan({
        repository_id: selectedRepository.id,
        dependency_name: dependencyName,
        current_version: currentVersion.trim(),
        target_version: targetVersion.trim(),
      });
      setPlan(response.data);
      setLatestPlan(response.data);
      setNotice('Plan received from the configured provider. No migration was started.');
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Could not create a plan. Check the backend connection and try again.'));
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="workspace-page">
      <PageHeader
        eyebrow="DEPENDENCY WORKFLOW"
        title="New Migration"
        description="Select or register a repository, inspect its manifests, and request a reviewable plan. Creating a plan does not execute it."
        action={<button className="gold-button" type="button" onClick={() => {
          setPlan(null);
          setDemoMode(true);
          setError('');
          setNotice('');
        }}><Sparkles size={15} /> Try Demo</button>}
      />
      {error && <div className="error-banner" role="alert"><Activity size={17} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}>×</button></div>}
      {notice && <div className="notice-banner" role="status"><CheckCircle2 size={16} /><span>{notice}</span><button aria-label="Dismiss notice" onClick={() => setNotice('')}>×</button></div>}

      {demoMode && <section className="panel page-panel" aria-label="Demo migration plan">
        <div className="page-section-heading">
          <div>
            <p className="eyebrow">DEMO — SIMULATED DATA</p>
            <h2>Example plan: {demoPlan.dependency.name}</h2>
            <p>Example current version {demoPlan.dependency.currentVersion} → example target version {demoPlan.dependency.targetVersion}</p>
            <p className="form-help">Illustrative sample only. This is not an actual repository analysis, a result from Nebius, or a compatibility guarantee. Versions and findings are examples, not verified facts.</p>
          </div>
          <span className="heading-icon"><Sparkles size={19} /></span>
        </div>
        <div className="detail-grid">
          <div><dt>Example dependency</dt><dd>{demoPlan.dependency.name}</dd></div>
          <div><dt>Example starting version</dt><dd>{demoPlan.dependency.currentVersion} (illustrative)</dd></div>
          <div><dt>Example target version</dt><dd>{demoPlan.dependency.targetVersion} (illustrative)</dd></div>
          <div><dt>Plan source</dt><dd>Frontend demo fixture; no provider request</dd></div>
        </div>
        <div className="insights-detail-grid">
          <article className="panel page-panel">
            <div className="page-section-heading"><div><p className="eyebrow">EXAMPLE FINDINGS</p><h3>Breaking-change considerations</h3></div></div>
            <ul className="risk-list">{demoPlan.breakingChangeExamples.map((item) => <li key={item}><Activity size={14} />{item}</li>)}</ul>
          </article>
          <article className="panel page-panel">
            <div className="page-section-heading"><div><p className="eyebrow">BOUNDED EXAMPLE</p><h3>Migration steps</h3></div></div>
            <ol>{demoPlan.migrationSteps.map((step) => <li key={step}>{step}</li>)}</ol>
          </article>
          <article className="panel page-panel">
            <div className="page-section-heading"><div><p className="eyebrow">EXAMPLE CHECKS</p><h3>Validation</h3></div></div>
            <ul>{demoPlan.validationChecks.map((check) => <li key={check}>{check}</li>)}</ul>
          </article>
          <article className="panel page-panel">
            <div className="page-section-heading"><div><p className="eyebrow">EXAMPLE RECOVERY</p><h3>Rollback guidance</h3></div></div>
            <ul>{demoPlan.rollbackGuidance.map((step) => <li key={step}>{step}</li>)}</ul>
          </article>
        </div>
        <p className="safety-note"><LockKeyhole size={14} /> Demo only: no backend plan or migration job was created, and nothing was executed.</p>
        <button className="outline-button" type="button" onClick={() => setDemoMode(false)}>Exit Demo and return to New Migration</button>
      </section>}

      <section className="panel page-panel">
        <div className="page-section-heading"><div><p className="eyebrow">STEP 1 · REPOSITORY</p><h2>Choose a workspace</h2><p>Select an already registered repository or add one using the backend.</p></div><span className="heading-icon"><Github size={19} /></span></div>
        <div className="page-form-grid">
          <label className="field-label" htmlFor="migration-repository">Registered repository</label>
          <div className="inline-field">
            <select id="migration-repository" value={repositoryId} onChange={(event) => {
              setRepositoryId(event.target.value);
              setDependencies([]);
              setInspectionCompleted(false);
              setCurrentVersion('');
              setPlan(null);
              setDemoMode(false);
            }}>
              <option value="">Select a repository</option>
              {repositories.map((repository) => <option key={repository.id} value={repository.id}>{repository.name} · {repository.type}</option>)}
            </select>
            <button type="button" className="outline-button" disabled={!selectedRepository || working} onClick={() => void inspectRepository()}>
              {working ? <LoaderCircle className="spin" size={14} /> : <Activity size={14} />} Inspect
            </button>
          </div>
          {loadingRepositories && <p className="form-help">Loading repository list…</p>}
          {!loadingRepositories && repositories.length === 0 && <p className="form-help">No repositories returned. Add a repository below or retry the list.</p>}
        </div>
        <form className="page-form-grid page-form-divider" onSubmit={(event) => void registerRepository(event)}>
          <span className="field-label">Or register a repository</span>
          <div className="source-switch" role="group" aria-label="Repository type">
            <button type="button" className={repositoryKind === 'git' ? 'source-active' : ''} onClick={() => setRepositoryKind('git')}><Github size={14} /> Git URL</button>
            <button type="button" className={repositoryKind === 'archive' ? 'source-active' : ''} onClick={() => setRepositoryKind('archive')}><FileText size={14} /> Local archive</button>
          </div>
          <div className="inline-field">
            <input value={repositoryInput} onChange={(event) => setRepositoryInput(event.target.value)} aria-label={repositoryKind === 'git' ? 'Git repository URL' : 'Backend archive path'} placeholder={repositoryKind === 'git' ? 'https://github.com/owner/repository' : '/path/to/archive.zip'} />
            <button className="gold-button" type="submit" disabled={working}>{working ? 'Adding…' : 'Add repository'}<ArrowRight size={14} /></button>
          </div>
          <p className="form-help">{repositoryKind === 'git' ? 'The backend registers the Git URL when you submit.' : 'Archive paths are read by the backend, not uploaded from this browser.'}</p>
        </form>
      </section>

      <section className="panel page-panel">
        <div className="page-section-heading"><div><p className="eyebrow">STEP 2 · ANALYZE</p><h2>Dependency analysis</h2><p>{selectedRepository ? `Manifest data inspected from ${selectedRepository.name}.` : 'Choose and inspect a repository to load dependency data.'}</p></div><span className="heading-icon"><Package size={19} /></span></div>
        {dependencies.length === 0
          ? <div className="page-empty"><Package size={20} />
            {inspectionCompleted
              ? <>
                <strong>No supported Python dependency manifests detected</strong>
                <span>This does not necessarily mean the repository has no dependencies. The inspector currently reads dependency declarations from <code>pyproject.toml</code> (PEP 621 or Poetry), root <code>requirements.txt</code>, and literal <code>install_requires</code>/<code>extras_require</code> values in <code>setup.py</code>.</span>
                <span>Select a repository containing one of these supported Python manifests, or use an ecosystem-specific analyzer when available.</span>
              </>
              : <><strong>No dependency data loaded</strong><span>Inspect a selected repository to show detected manifest entries here.</span></>}
          </div>
          : <form onSubmit={(event) => void createPlan(event)} className="page-form-grid">
            <label className="field-label" htmlFor="migration-dependency">Dependency to upgrade</label>
            <div className="inline-field">
              <select id="migration-dependency" value={dependencyName} onChange={(event) => {
                setDependencyName(event.target.value);
                setCurrentVersion('');
              }}>
                {dependencies.map((dependency) => <option key={dependency.name} value={dependency.name}>{dependency.name} · installed version unknown</option>)}
              </select>
              <input value={currentVersion} onChange={(event) => setCurrentVersion(event.target.value)} aria-label="Current version" placeholder="Current version (enter if unknown)" required />
              <input value={targetVersion} onChange={(event) => setTargetVersion(event.target.value)} aria-label="Target version" placeholder="Target version" required />
              <button className="gold-button" type="submit" disabled={working || !selectedRepository}>
                {working ? 'Requesting plan…' : 'Create plan'} <ArrowRight size={14} />
              </button>
            </div>
            <p className="form-help">Manifest data confirms the dependency is declared, but does not establish its installed version. Verify the installed version or explicitly enter the starting version before requesting a version-specific plan; manually entered values are treated as user-reported, not independently verified.</p>
            <div className="dependency-tags">{dependencies.map((dependency) => <span key={dependency.name}><Package size={13} /><strong>{dependency.name}</strong><small>Installed version: Unknown · Manifest requirement: {dependency.versionConstraint || 'not specified'} · {dependency.manifest}</small></span>)}</div>
          </form>}
      </section>

      {plan && <section className="panel page-panel">
        <div className="page-section-heading"><div><p className="eyebrow">STEP 3 · REVIEW</p><h2>Plan suggestions for {plan.dependency.name}</h2><p>Reported starting version: {plan.dependency.current_version || 'Unknown'} → {plan.dependency.target_version} · {plan.planned_edits.length} suggested edits</p><p className="form-help">The starting version was user-supplied and is not independently verified. Planner-generated findings and edits are suggestions, not independently verified by static analysis.</p></div><span className="heading-icon"><Sparkles size={19} /></span></div>
        {plan.breaking_changes.length > 0
          ? <div className="record-list">{plan.breaking_changes.map((change, index) => <article key={`${change.type}-${index}`}><span className={`severity severity-${change.severity}`}>{change.severity}</span><p>{change.description}</p><small>Planner suggestion · {change.source}</small></article>)}</div>
          : <div className="page-empty compact"><CheckCircle2 size={18} /><span>The plan returned no specific breaking-change notes. This is not a guarantee of compatibility.</span></div>}
        <p className="safety-note"><LockKeyhole size={14} /> Execution has not been started. The backend safety policy remains in control.</p>
      </section>}

    </div>
  );
}
