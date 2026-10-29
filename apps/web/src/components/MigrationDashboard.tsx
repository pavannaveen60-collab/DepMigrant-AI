'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import {
  Activity,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  Code2,
  FileCode2,
  FileText,
  GitBranch,
  Github,
  Layers3,
  LoaderCircle,
  LockKeyhole,
  Package,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Terminal,
  X,
} from 'lucide-react';
import { migrationApi, repositoryApi } from '@/lib/api';
import { MigrationJob, MigrationPlan, Repository } from '@/types';
import { useWorkspace } from '@/components/WorkspaceShell';
import { parseInspectedDependencies } from '@/lib/dependencies';
import { uniqueRepositories } from '@/lib/repositories';

type RepositoryKind = 'git' | 'archive';
type FeedLog = {
  timestamp: string;
  level: string;
  message: string;
  command?: string;
  exitCode?: number;
};
const workflow = ['Analyze', 'Plan', 'Apply', 'Test', 'Verify'];

function nowLabel() {
  return new Date().toLocaleTimeString([], { hour12: false });
}

function stepIndex(status?: MigrationJob['status']) {
  if (!status) return -1;
  if (status === 'inspecting' || status === 'pending') return 0;
  if (status === 'planning') return 1;
  if (status === 'patching' || status === 'executing' || status === 'diagnosing' || status === 'repairing') return 2;
  if (status === 'baseline' || status === 'verifying') return 3;
  return 4;
}

export function MigrationDashboard() {
  const { setLatestPlan, preferences } = useWorkspace();
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selectedRepository, setSelectedRepository] = useState<Repository | null>(null);
  const [inspection, setInspection] = useState<unknown>(null);
  const [plan, setPlan] = useState<MigrationPlan | null>(null);
  const [job, setJob] = useState<MigrationJob | null>(null);
  const [serverLogs, setServerLogs] = useState<FeedLog[]>([]);
  const [sessionLogs, setSessionLogs] = useState<FeedLog[]>([]);
  const [repositoryInput, setRepositoryInput] = useState('');
  const [repositoryKind, setRepositoryKind] = useState<RepositoryKind>(preferences.defaultRepositoryType);
  const [dependencyName, setDependencyName] = useState('');
  const [currentVersion, setCurrentVersion] = useState('');
  const [targetVersion, setTargetVersion] = useState('');
  const [currentVersions, setCurrentVersions] = useState<Record<string, string>>({});
  const [targetVersions, setTargetVersions] = useState<Record<string, string>>({});
  const [loadingRepositories, setLoadingRepositories] = useState(true);
  const [repositoryLoadFailed, setRepositoryLoadFailed] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [changeTab, setChangeTab] = useState<'diff' | 'files' | 'explanation'>('diff');
  const [logsPaused, setLogsPaused] = useState(false);
  const [sessionLogOffset, setSessionLogOffset] = useState(0);
  const [serverLogOffset, setServerLogOffset] = useState(0);
  const formRef = useRef<HTMLElement>(null);

  const dependencies = useMemo(
    () => (inspection ? parseInspectedDependencies(inspection) : []),
    [inspection],
  );
  const visibleRepositories = useMemo(() => uniqueRepositories(repositories), [repositories]);
  const terminal = job && ['completed', 'failed', 'blocked'].includes(job.status);
  const displayedLogs = job
    ? serverLogs.slice(serverLogOffset)
    : sessionLogs.slice(sessionLogOffset);

  const appendLog = (level: string, message: string, command?: string) => {
    setSessionLogs((current) => [...current, { timestamp: nowLabel(), level, message, command }]);
  };

  const refreshRepositories = async () => {
    setLoadingRepositories(true);
    try {
      const response = await repositoryApi.list();
      setRepositories(uniqueRepositories(response.data));
      setRepositoryLoadFailed(false);
      setError('');
    } catch {
      setRepositoryLoadFailed(true);
      setError('Could not load repositories. Check that the backend is running.');
    } finally {
      setLoadingRepositories(false);
    }
  };

  useEffect(() => {
    let active = true;
    repositoryApi.list()
      .then((response) => {
        if (active) {
          setRepositories(uniqueRepositories(response.data));
          setRepositoryLoadFailed(false);
        }
      })
      .catch(() => {
        if (active) {
          setRepositoryLoadFailed(true);
          setError('Could not load repositories. Check that the backend is running.');
        }
      })
      .finally(() => { if (active) setLoadingRepositories(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!job || terminal || logsPaused) return;
    let active = true;
    const poll = async () => {
      try {
        const response = await migrationApi.getJobStatus(job.id);
        if (!active) return;
        const status = response.data;
        setJob(status.job);
        setServerLogs((status.logs ?? []).map((entry: any) => ({
          timestamp: entry.timestamp ?? '',
          level: entry.level ?? 'info',
          message: entry.message ?? '',
          command: entry.command,
          exitCode: entry.exitCode,
        })));
      } catch {
        if (active) setError('Unable to refresh migration progress. The job may still be running.');
      }
    };
    void poll();
    const timer = window.setInterval(poll, 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.status, terminal, logsPaused]);

  const analyzeRepository = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setNotice('');
    if (!repositoryInput.trim()) {
      setError(repositoryKind === 'git' ? 'Enter a Git repository URL.' : 'Enter a local archive path.');
      return;
    }
    setWorking(true);
    setPlan(null);
    setInspection(null);
    setJob(null);
    try {
      appendLog('info', 'Repository analysis requested.');
      const created = await repositoryApi.create(repositoryKind === 'git'
        ? { path: '', type: 'git', url: repositoryInput.trim() }
        : { path: repositoryInput.trim(), type: 'archive' });
      setSelectedRepository(created.data);
      setRepositories((current) => uniqueRepositories([created.data, ...current.filter((item) => item.id !== created.data.id)]));
      appendLog('success', `Repository registered: ${created.data.name}.`);
      const inspected = await repositoryApi.inspect(created.data.id);
      setInspection(inspected.data);
      const found = parseInspectedDependencies(inspected.data);
      setDependencyName(found[0]?.name ?? '');
      setTargetVersion('');
      appendLog('success', `Inspection completed. ${found.length} dependency entries were found.`);
    } catch (requestError: any) {
      const detail = requestError?.response?.data?.detail;
      const message = detail || 'Repository analysis failed. Confirm the backend is running and the repository is accessible.';
      setError(message);
      appendLog('error', message);
    } finally {
      setWorking(false);
    }
  };

  const startMigration = async () => {
    if (!plan) return;
    if (preferences.confirmBeforeExecution && !window.confirm('Request migration execution? The backend may block it unless OS-level isolation is enabled.')) return;
    setWorking(true);
    setError('');
    setNotice('');
    try {
      appendLog('info', 'Migration start requested. The backend safety policy remains in control.');
      const response = await migrationApi.start(plan.id);
      setJob(response.data);
      setServerLogs([]);
      setServerLogOffset(0);
      appendLog('success', 'Migration job accepted by the backend.');
    } catch (requestError: any) {
      const detail = requestError?.response?.data?.detail;
      const message = detail || 'Migration could not be started.';
      setError(message);
      appendLog('error', message);
    } finally {
      setWorking(false);
    }
  };

  const selectRepository = async (repository: Repository) => {
    setWorking(true);
    setError('');
    setNotice('');
    setSelectedRepository(repository);
    setPlan(null);
    setInspection(null);
    try {
      const response = await repositoryApi.inspect(repository.id);
      setInspection(response.data);
      const found = parseInspectedDependencies(response.data);
      setDependencyName(found[0]?.name ?? '');
      setTargetVersion('');
      appendLog('success', `Repository inspected: ${repository.name}.`);
      formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Could not inspect this repository.');
    } finally {
      setWorking(false);
    }
  };

  const repoName = selectedRepository?.name ?? 'No repository selected';
  const currentStep = job ? stepIndex(job.status) : plan ? 1 : inspection ? 0 : -1;
  const planChanges = plan?.planned_edits ?? [];

  async function createPlanWithTarget(event: FormEvent, target: string) {
    event.preventDefault();
    setTargetVersion(target);
    const current = currentVersions[dependencyName] || currentVersion;
    if (!selectedRepository || !dependencyName || !target.trim()) {
      setError('Choose a dependency and enter a target version.');
      return;
    }
    setWorking(true);
    setError('');
    try {
      appendLog('info', `Plan requested for ${dependencyName}${current.trim() ? ` (${current.trim()})` : ''} → ${target}.`);
      const response = await migrationApi.createPlan({
        repository_id: selectedRepository.id,
        dependency_name: dependencyName,
        current_version: current.trim() || undefined,
        target_version: target.trim(),
      });
      setPlan(response.data);
      setLatestPlan(response.data);
      appendLog('success', `Migration plan received for ${response.data.dependency.name}.`);
    } catch (requestError: any) {
      const message = requestError?.response?.data?.detail || 'Could not create a plan. The model provider may not be configured.';
      setError(message);
      appendLog('error', message);
    } finally {
      setWorking(false);
    }
  }

  return (
    <>
          {notice && (
            <div className="notice-banner" role="status">
              <span>{notice}</span>
              <button aria-label="Dismiss message" onClick={() => setNotice('')}><X size={15} /></button>
            </div>
          )}
          {error && (
            <div className="error-banner" role="alert">
              <ShieldAlert size={17} />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError('')}><X size={15} /></button>
            </div>
          )}

          <section className="hero-panel" aria-labelledby="hero-title">
            <div className="hero-copy">
              <p className="eyebrow"><span className="eyebrow-line" /> DEPENDENCY MIGRATION, MADE CLEAR</p>
              <h1 id="hero-title">Upgrade with <em>Confidence</em></h1>
              <p className="hero-description">
                Plan thoughtful Python dependency upgrades, review every proposed change,
                and verify outcomes with evidence.
              </p>
              <div className="hero-tags">
                <span><Sparkles size={13} /> AI-assisted planning</span>
                <span><LockKeyhole size={13} /> Safety controls enforced</span>
                <span><CheckCircle2 size={13} /> Evidence-led reports</span>
              </div>
            </div>
            <div className="origami-scene" aria-hidden="true">
              <div className="scene-glow" />
              <div className="origami">
                <i className="fold fold-a" /><i className="fold fold-b" /><i className="fold fold-c" />
                <i className="fold fold-d" /><i className="fold fold-e" /><i className="fold fold-f" />
              </div>
              <div className="scene-quote">“Safer dependencies,<br />steadier releases.”</div>
            </div>
          </section>

          <section className="action-grid" ref={formRef} id="new-migration">
            <div className="panel start-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">GET STARTED</p>
                  <h2>Start a New Migration</h2>
                  <p>Connect a repository to inspect its dependency manifests.</p>
                </div>
                <span className="heading-icon"><GitBranch size={19} /></span>
              </div>
              <form onSubmit={analyzeRepository}>
                <div className="source-switch" role="group" aria-label="Repository source type">
                  <button type="button" className={repositoryKind === 'git' ? 'source-active' : ''} onClick={() => setRepositoryKind('git')}>
                    <Github size={14} /> Git URL
                  </button>
                  <button type="button" className={repositoryKind === 'archive' ? 'source-active' : ''} onClick={() => setRepositoryKind('archive')}>
                    <FileText size={14} /> Local archive
                  </button>
                </div>
                <div className="repo-input-row">
                  <div className="repo-input-wrap">
                    {repositoryKind === 'git' ? <Github size={17} /> : <FileText size={17} />}
                    <input
                      value={repositoryInput}
                      onChange={(event) => setRepositoryInput(event.target.value)}
                      placeholder={repositoryKind === 'git' ? 'https://github.com/owner/repository' : '/path/to/archive.zip'}
                      aria-label={repositoryKind === 'git' ? 'Git repository URL' : 'Local archive path'}
                    />
                  </div>
                  <button className="gold-button" type="submit" disabled={working}>
                    {working ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={15} />}
                    {working ? 'Analyzing…' : 'Analyze Repository'}
                    {!working && <ArrowRight size={15} />}
                  </button>
                </div>
                <div className="examples-line">
                  <span>{repositoryKind === 'git' ? 'Try a known URL you control:' : 'Local archive path on the backend:'}</span>
                  {repositoryKind === 'git' && ['pydantic', 'fastapi', 'requests'].map((name) => (
                    <button key={name} type="button" onClick={() => setRepositoryInput(`https://github.com/${name === 'fastapi' ? 'fastapi/fastapi' : name === 'requests' ? 'psf/requests' : 'pydantic/pydantic'}`)}>{name}</button>
                  ))}
                </div>
              </form>
            </div>

            <div className="panel how-panel">
              <div className="panel-title-row"><h3>How it works</h3><span className="muted-mini">5 clear steps</span></div>
              <div className="how-list">
                {workflow.map((label, index) => (
                  <div className={`how-step ${currentStep === index ? 'how-current' : ''}`} key={label}>
                    <span className="how-number">{index + 1}</span>
                    <strong>{label}</strong>
                    <small>{[
                      'Inspect dependency manifests',
                      'Review an AI-generated plan',
                      'Apply proposed edits in a copy',
                      'Run configured project tests',
                      'See the verification evidence',
                    ][index]}</small>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="summary-grid" aria-label="Workspace summary">
            <SummaryCard
              icon={<Layers3 size={19} />}
              label="Repositories"
              value={loadingRepositories ? '…' : repositoryLoadFailed ? 'Unavailable' : `${visibleRepositories.length} ${visibleRepositories.length === 1 ? 'repository' : 'repositories'}`}
              note={loadingRepositories ? 'Loading from the backend' : repositoryLoadFailed ? 'Backend did not return repository data' : visibleRepositories.length === 0 ? 'No repositories available' : 'Available in this workspace'}
            />
            <SummaryCard icon={<Package size={19} />} label="Detected dependencies" value={inspection ? String(dependencies.length) : '—'} note={inspection ? 'From selected repository' : 'Analyze a repository to begin'} />
            <SummaryCard icon={<Code2 size={19} />} label="Proposed edits" value={plan ? String(plan.planned_edits.length) : '—'} note={plan ? 'In the current plan' : 'No plan generated yet'} />
            <SummaryCard icon={<ShieldCheck size={19} />} label="Verification" value={job?.final_result ? job.final_result.status.replace('_', ' ') : 'Not run'} note={job?.final_result ? `${job.final_result.tests_passed} passed · ${job.final_result.tests_failed} failed` : 'No test results available'} positive={job?.final_result?.status === 'verified'} />
          </section>

          <section className="workbench-grid">
            <div className="panel migration-panel">
              <div className="panel-title-row">
                <div className="section-title">
                  <span className="panel-icon"><Activity size={17} /></span>
                  <div><h2>{job ? 'Current Migration' : 'Migration Workspace'}</h2><p>{job ? `Job ${job.id.slice(0, 8)} · ${job.current_step || job.status}` : repoName}</p></div>
                </div>
                {job && <span className={`status-chip ${terminal ? job.status : 'running'}`}><span />{terminal ? job.status : 'In progress'}</span>}
                {job && !terminal && (
                  <span className="cancel-unavailable" title="The backend cannot safely stop its running background process.">
                    Cancellation unavailable
                  </span>
                )}
              </div>

              <div className="workflow-track" aria-label="Migration workflow">
                {workflow.map((label, index) => {
                  const done = currentStep > index
                    || (terminal && index < 4)
                    || (job?.status === 'completed' && index === 4);
                  const active = currentStep === index && !terminal;
                  return (
                    <div className={`workflow-step ${done ? 'step-done' : ''} ${active ? 'step-active' : ''} ${terminal && job?.status !== 'completed' && index === 4 ? 'step-error' : ''}`} key={label}>
                      <span className="workflow-circle">{done ? <Check size={13} /> : index + 1}</span>
                      <span>{label}</span>
                    </div>
                  );
                })}
              </div>

              <div className="table-heading">
                <div><h3>Detected Dependencies</h3><span>{inspection !== null ? `${dependencies.length} from inspected manifests` : 'No repository inspected yet'}</span></div>
                {inspection !== null && <button className="text-button" onClick={() => selectedRepository && void selectRepository(selectedRepository)} disabled={working}>Refresh</button>}
              </div>
              <div className="dependency-table-wrap">
                <table className="dependency-table">
                  <thead><tr><th>Package</th><th>Installed current</th><th>Target version</th><th>Risk</th></tr></thead>
                  <tbody>
                    {inspection === null && (
                      <tr><td className="empty-table" colSpan={4}>Analyze a repository to see real dependency data here.</td></tr>
                    )}
                    {inspection !== null && dependencies.length === 0 && (
                      <tr><td className="empty-table" colSpan={4}>No supported dependency entries were found in the inspected manifests.</td></tr>
                    )}
                    {dependencies.slice(0, 8).map((dependency) => (
                      <tr key={dependency.name} className={dependencyName === dependency.name ? 'selected-row' : ''}>
                        <td><button className="package-name" onClick={() => setDependencyName(dependency.name)}><Package size={13} />{dependency.name}</button><small>{dependency.manifest}</small></td>
                        <td className="version-cell">
                          <input
                            className="target-cell-input"
                            value={currentVersions[dependency.name] ?? ''}
                            placeholder="Current (if known)"
                            aria-label={`Current version for ${dependency.name}`}
                            onChange={(event) => {
                              const val = event.target.value;
                              setCurrentVersions((current) => ({ ...current, [dependency.name]: val }));
                              if (dependencyName === dependency.name) setCurrentVersion(val);
                            }}
                            onFocus={() => {
                              setDependencyName(dependency.name);
                              setCurrentVersion(currentVersions[dependency.name] ?? '');
                            }}
                          />
                          <small>{dependency.versionConstraint ? `Declared requirement: ${dependency.versionConstraint} · ` : ''}Installed version unverified</small>
                        </td>
                        <td>
                          <input
                            className="target-cell-input"
                            value={targetVersions[dependency.name] ?? ''}
                            placeholder="Set target"
                            aria-label={`Target version for ${dependency.name}`}
                            onChange={(event) => setTargetVersions((current) => ({ ...current, [dependency.name]: event.target.value }))}
                            onFocus={() => setDependencyName(dependency.name)}
                          />
                        </td>
                        <td><span className="risk-neutral"><Circle size={7} /> Not assessed</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {inspection !== null && dependencies.length > 0 && (
                <form className="plan-inline-form" onSubmit={(event) => {
                  const selectedTarget = targetVersions[dependencyName] ?? targetVersion;
                  setTargetVersion(selectedTarget);
                  void createPlanWithTarget(event, selectedTarget);
                }}>
                  <label htmlFor="plan-target">Plan an upgrade</label>
                  <select value={dependencyName} onChange={(event) => {
                    const selected = event.target.value;
                    setDependencyName(selected);
                    setTargetVersion(targetVersions[selected] ?? '');
                    setCurrentVersion(currentVersions[selected] ?? '');
                  }} aria-label="Dependency to upgrade">
                    {dependencies.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
                  </select>
                  <input id="plan-current" value={currentVersion || currentVersions[dependencyName] || ''} onChange={(event) => {
                    setCurrentVersion(event.target.value);
                    setCurrentVersions((current) => ({ ...current, [dependencyName]: event.target.value }));
                  }} placeholder="Current version (optional)" aria-label="Current version" />
                  <input id="plan-target" value={targetVersion || targetVersions[dependencyName] || ''} onChange={(event) => {
                    setTargetVersion(event.target.value);
                    setTargetVersions((current) => ({ ...current, [dependencyName]: event.target.value }));
                  }} placeholder="Target version" required />
                  <button className="subtle-gold-button" disabled={working}>{working ? 'Planning…' : 'Generate plan'}<ArrowRight size={14} /></button>
                </form>
              )}
              {plan && (
                <div className="plan-action-row">
                  <span><CheckCircle2 size={15} /> Plan is ready to review. Execution remains subject to backend safety controls.</span>
                  <button className="subtle-gold-button" onClick={() => void startMigration()} disabled={working || Boolean(job && !terminal)}>
                    {working ? 'Starting…' : 'Request migration'}<ArrowRight size={14} />
                  </button>
                </div>
              )}
            </div>

            <div className="panel changes-panel">
              <div className="panel-title-row">
                <div><h2>Proposed Changes</h2><p>{plan ? `${planChanges.length} planned file edits` : 'Changes appear after a plan is created'}</p></div>
                <span className={`change-count ${plan ? '' : 'count-muted'}`}>{plan ? planChanges.length : '—'}</span>
              </div>
              <div className="change-tabs" role="tablist" aria-label="Proposed change views">
                {(['diff', 'files', 'explanation'] as const).map((tab) => (
                  <button key={tab} role="tab" aria-selected={changeTab === tab} className={changeTab === tab ? 'tab-active' : ''} onClick={() => setChangeTab(tab)}>
                    {tab === 'diff' ? 'Diff View' : tab === 'files' ? 'Files' : 'AI Explanation'}
                  </button>
                ))}
              </div>
              <div className="change-view">
                {!plan && <div className="empty-state compact-empty"><FileCode2 size={23} /><strong>No proposed changes yet</strong><span>Analyze a repository and request a plan to review edits.</span></div>}
                {plan && changeTab === 'files' && (
                  planChanges.length ? <ul className="file-list">{planChanges.map((edit, index) => <li key={`${edit.file_path}-${index}`}><FileText size={14} /><span><strong>{edit.file_path}</strong><small>{edit.description}</small></span></li>)}</ul>
                    : <div className="empty-state compact-empty"><FileCode2 size={23} /><strong>No file edits proposed</strong><span>The plan contains no planned edits.</span></div>
                )}
                {plan && changeTab === 'explanation' && (
                  plan.breaking_changes.length ? <div className="explanation-list">{plan.breaking_changes.map((change, index) => <article key={index}><span className={`severity severity-${change.severity}`}>{change.severity}</span><p>{change.description}</p><small>Source: {change.source}</small></article>)}</div>
                    : <div className="empty-state compact-empty"><Sparkles size={22} /><strong>No breaking changes returned</strong><span>The plan did not report specific breaking changes.</span></div>
                )}
                {plan && changeTab === 'diff' && (
                  planChanges.length ? <div className="diff-list">{planChanges.map((edit, index) => (
                    <div className="diff-file" key={`${edit.file_path}-${index}`}>
                      <div className="diff-file-header"><FileCode2 size={13} />{edit.file_path}</div>
                      {edit.original_code && <div className="diff-line diff-remove"><span>−</span><code>{edit.original_code}</code></div>}
                      {edit.new_code && <div className="diff-line diff-add"><span>+</span><code>{edit.new_code}</code></div>}
                      <p>{edit.description}</p>
                    </div>
                  ))}</div>
                    : <div className="empty-state compact-empty"><FileCode2 size={23} /><strong>No diff to display</strong><span>No planned edits were provided.</span></div>
                )}
              </div>
              {plan && <div className="changes-footnote"><LockKeyhole size={12} /> Review the plan before requesting execution.</div>}
            </div>
          </section>

          <section className="insights-grid" id="ai-insights">
            <div className="panel insight-panel">
              <div className="panel-title-row"><div className="insight-title"><span className="insight-icon"><Sparkles size={16} /></span><h2>AI Analysis</h2></div><span className="live-label">{plan ? 'PLAN DATA' : 'WAITING'}</span></div>
              {plan ? (
                <>
                  <p className="insight-copy">The generated plan covers <strong>{plan.affected_files.length}</strong> affected files and <strong>{plan.planned_edits.length}</strong> proposed edits.</p>
                  <p className="insight-copy">{plan.breaking_changes.length ? `${plan.breaking_changes.length} breaking-change consideration(s) were returned by the planner.` : 'No specific breaking changes were returned.'}</p>
                  <div className="insight-foot">{plan.risks.length} plan risk note{plan.risks.length === 1 ? '' : 's'} · Based on this plan</div>
                </>
              ) : (
                <div className="empty-state side-empty"><Sparkles size={19} /><span>AI analysis appears after a plan is requested. No analysis is being assumed.</span></div>
              )}
            </div>

            <div className="panel insight-panel">
              <div className="panel-title-row"><div className="insight-title"><span className="insight-icon compatibility-icon"><Activity size={16} /></span><h2>Compatibility</h2></div></div>
              {plan?.breaking_changes.length ? (
                <div className="compatibility-list">{plan.breaking_changes.slice(0, 4).map((item, index) => (
                  <div key={index}><span>{item.type.replaceAll('_', ' ')}</span><b className={`severity severity-${item.severity}`}>{item.severity}</b></div>
                ))}</div>
              ) : (
                <div className="empty-state side-empty"><Circle size={15} /><span>{plan ? 'No compatibility findings were returned by the planner.' : 'Compatibility findings will appear when a plan is available.'}</span></div>
              )}
              <div className="insight-foot">Not a package vulnerability or runtime compatibility scan</div>
            </div>

            <div className="panel insight-panel security-panel">
              <div className="panel-title-row"><div className="insight-title"><span className="security-icon"><ShieldCheck size={16} /></span><h2>Security Insights</h2></div><span className="unavailable-label">NOT SCANNED</span></div>
              <p className="insight-copy">The backend does not currently provide a vulnerability scan for target versions.</p>
              <div className="security-note"><ShieldAlert size={14} /> No security result is available. This is not a clean bill of health.</div>
            </div>
          </section>

          <section className="panel repository-panel" id="repositories">
            <div className="panel-title-row">
              <div><h2>Repositories</h2><p>Repositories currently available through the backend</p></div>
              <button className="outline-button" onClick={() => void refreshRepositories()} disabled={loadingRepositories}>
                {loadingRepositories ? <LoaderCircle className="spin" size={14} /> : <Activity size={14} />} Refresh
              </button>
            </div>
            {loadingRepositories ? <div className="repository-empty"><LoaderCircle className="spin" size={18} /> Loading repository list…</div>
              : repositoryLoadFailed ? <div className="repository-empty"><Activity size={19} /><span>Repository list unavailable. Check the backend connection.</span><button onClick={() => void refreshRepositories()}>Retry</button></div>
                : visibleRepositories.length === 0 ? <div className="repository-empty"><Layers3 size={19} /><span>No repositories are registered yet.</span><Link href="/migration">Add one above</Link></div>
                : <div className="repository-list">{visibleRepositories.map((repository) => (
                  <button className={`repository-row ${selectedRepository?.id === repository.id ? 'repository-selected' : ''}`} key={repository.id} onClick={() => void selectRepository(repository)}>
                    <span className="repo-row-icon">{repository.type === 'git' ? <Github size={16} /> : <FileText size={16} />}</span>
                    <span className="repo-row-name"><strong>{repository.name}</strong><small>{repository.path}</small></span>
                    <span className="repo-row-type">{repository.type}</span>
                    <ChevronRight size={15} />
                  </button>
                ))}</div>
            }
          </section>

          <section className="panel logs-panel">
            <div className="logs-header">
              <div className="logs-title"><Terminal size={16} /><div><h2>{job ? 'Migration Logs' : 'Workspace Activity'}</h2><p>{job ? 'Live output reported by the migration API' : 'Events from this browser session; no migration results are implied'}</p></div></div>
              <div className="logs-actions">
                {job && <button onClick={() => setLogsPaused((value) => !value)}><span className="live-dot" />{logsPaused ? 'Paused' : 'Live'}</button>}
                <button onClick={() => {
                  if (job) setServerLogOffset(serverLogs.length);
                  else setSessionLogOffset(sessionLogs.length);
                }}><X size={13} /> Clear</button>
                {terminal && <span className={`status-chip ${job.status}`}><span />{job.status}</span>}
              </div>
            </div>
            <div className="terminal-view" role="log" aria-live="polite">
              {displayedLogs.length === 0 ? <div className="terminal-empty"><span className="terminal-prompt">›</span>{job ? 'No command output has been reported yet.' : 'Waiting for repository activity. Start by analyzing a repository.'}</div>
                : displayedLogs.map((entry, index) => (
                  <div className="terminal-line" key={`${entry.timestamp}-${index}`}>
                    <time>[{entry.timestamp || '—'}]</time>
                    <span className={`terminal-level level-${entry.level.toLowerCase()}`}>{entry.level.toUpperCase()}</span>
                    {entry.command && <code>{entry.command}</code>}
                    <span className="terminal-message">{entry.message}</span>
                    {entry.exitCode !== undefined && entry.exitCode !== 0 && <span className="terminal-exit">exit {entry.exitCode}</span>}
                  </div>
                ))}
            </div>
          </section>

          {job && terminal && job.final_result && (
            <section className="panel final-summary">
              <div className="insight-title"><CheckCircle2 size={17} /><h2>Verification report</h2></div>
              <p>{job.final_result.summary}</p>
              <div className="report-stats">
                <span>{job.final_result.tests_passed} passed</span>
                <span>{job.final_result.tests_failed} failed</span>
                <span>{job.final_result.tests_skipped} skipped</span>
                <b className={`severity severity-${job.final_result.status === 'verified' ? 'low' : 'high'}`}>{job.final_result.status}</b>
              </div>
            </section>
          )}

          <footer className="footer-note"><span>DEPMIGRANT AI</span><i /> A careful workspace for dependency change.</footer>
    </>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  note,
  positive = false,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  note: string;
  positive?: boolean;
}) {
  return (
    <article className={`summary-card ${positive ? 'summary-positive' : ''}`}>
      <div className="summary-top"><span>{label}</span><i>{icon}</i></div>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}
