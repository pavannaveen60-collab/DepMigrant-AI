'use client';

import { FormEvent, useEffect, useState } from 'react';
import { Activity, AlertTriangle, Clock3, FileCode2, FileText, LoaderCircle, Package, RefreshCw, Search, ShieldCheck } from 'lucide-react';
import { migrationApi } from '@/lib/api';
import { apiErrorMessage } from '@/lib/dependencies';
import { PageHeader } from './PageHeader';
import type { MigrationJob, MigrationPlan, MigrationReport } from '@/types';

export function HistoryPage() {
  const [jobId, setJobId] = useState('');
  const [jobs, setJobs] = useState<MigrationJob[]>([]);
  const [plans, setPlans] = useState<MigrationPlan[]>([]);
  const [job, setJob] = useState<MigrationJob | null>(null);
  const [plan, setPlan] = useState<MigrationPlan | null>(null);
  const [report, setReport] = useState<MigrationReport | null>(null);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [jobsUnavailable, setJobsUnavailable] = useState(false);
  const [plansUnavailable, setPlansUnavailable] = useState(false);
  const [error, setError] = useState('');

  const refreshHistory = async () => {
    setLoadingJobs(true);
    setLoadingPlans(true);
    const [jobsResult, plansResult] = await Promise.allSettled([
      migrationApi.listJobs(),
      migrationApi.listPlans(),
    ]);
    const errors: string[] = [];
    if (jobsResult.status === 'fulfilled') {
      setJobs(jobsResult.value.data);
      setJobsUnavailable(false);
    } else {
      setJobsUnavailable(true);
      errors.push(apiErrorMessage(jobsResult.reason, 'Could not load migration jobs.'));
    }
    if (plansResult.status === 'fulfilled') {
      setPlans(plansResult.value.data);
      setPlansUnavailable(false);
    } else {
      setPlansUnavailable(true);
      errors.push(apiErrorMessage(plansResult.reason, 'Could not load saved migration plans.'));
    }
    setError(errors.join(' '));
    setLoadingJobs(false);
    setLoadingPlans(false);
  };

  useEffect(() => { void refreshHistory(); }, []);

  const loadJob = async (id: string) => {
    setLoadingDetail(true);
    setError('');
    setJob(null);
    setPlan(null);
    setReport(null);
    try {
      const [jobResponse, reportResponse] = await Promise.all([
        migrationApi.getJob(id),
        migrationApi.getReport(id),
      ]);
      setJob(jobResponse.data);
      setReport(reportResponse.data);
      setJobId(id);
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Could not load this job or report.'));
    } finally {
      setLoadingDetail(false);
    }
  };

  const loadPlan = async (id: string) => {
    setLoadingDetail(true);
    setError('');
    setJob(null);
    setPlan(null);
    setReport(null);
    try {
      const response = await migrationApi.getPlan(id);
      setPlan(response.data);
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Could not load this migration plan.'));
    } finally {
      setLoadingDetail(false);
    }
  };

  const findJob = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!jobId.trim()) {
      setError('Enter a migration job ID to look it up.');
      return;
    }
    await loadJob(jobId.trim());
  };

  return (
    <div className="workspace-page">
      <PageHeader
        eyebrow="RECORDED WORK"
        title="Migration History"
        description="Jobs and reports below are loaded from recorded backend data; no sample history is shown."
        action={<button className="outline-button" type="button" onClick={() => void refreshHistory()} disabled={loadingJobs || loadingPlans}>{loadingJobs || loadingPlans ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />} Refresh</button>}
      />
      {error && <div className="error-banner history-error" role="alert"><Activity size={17} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}>×</button></div>}

      <section className="panel page-panel">
        <div className="page-section-heading"><div><p className="eyebrow">SAVED PLANS</p><h2>{loadingPlans ? 'Loading plans…' : plansUnavailable ? 'Plans unavailable' : `${plans.length} ${plans.length === 1 ? 'plan' : 'plans'}`}</h2><p>Saved analysis only; opening a plan does not create a job or run its commands.</p></div><span className="heading-icon"><FileText size={19} /></span></div>
        {loadingPlans
          ? <div className="page-empty"><LoaderCircle className="spin" size={20} /><span>Loading saved migration plans…</span></div>
          : plansUnavailable
            ? <div className="page-empty"><Activity size={20} /><strong>Could not retrieve saved plans</strong><span>Retry when the backend is available.</span><button className="outline-button" type="button" onClick={() => void refreshHistory()}>Retry</button></div>
            : plans.length === 0
              ? <div className="page-empty"><FileText size={20} /><strong>No saved migration plans.</strong><span>Plans appear here after the backend saves a planning result.</span></div>
              : <div className="history-job-list">{plans.map((item) => (
                <button className={`history-job ${plan?.id === item.id ? 'history-job-active' : ''}`} type="button" key={item.id} onClick={() => void loadPlan(item.id)} disabled={loadingDetail}>
                  <span><strong>{item.dependency.name}: start {item.dependency.current_version || 'unknown'} → {item.dependency.target_version}</strong><small>Plan {item.id} · Repository {item.repository_id}</small></span>
                  <span className="status-chip"><span />Saved plan</span>
                  <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time>
                </button>
              ))}</div>}
      </section>

      <section className="panel page-panel">
        <div className="page-section-heading"><div><p className="eyebrow">MIGRATION JOBS</p><h2>{loadingJobs ? 'Loading history…' : jobsUnavailable ? 'History unavailable' : `${jobs.length} ${jobs.length === 1 ? 'job' : 'jobs'}`}</h2><p>Select a recorded job to inspect its status and report.</p></div><span className="heading-icon"><Clock3 size={19} /></span></div>
        {loadingJobs
          ? <div className="page-empty"><LoaderCircle className="spin" size={20} /><span>Loading migration jobs from the backend…</span></div>
          : jobsUnavailable
            ? <div className="page-empty"><Activity size={20} /><strong>Could not retrieve migration history</strong><span>Retry when the backend is available.</span><button className="outline-button" type="button" onClick={() => void refreshHistory()}>Retry</button></div>
            : jobs.length === 0
              ? <div className="page-empty"><Clock3 size={20} /><strong>No migration jobs have been recorded.</strong><span>Jobs appear here only after the backend records an execution request.</span></div>
              : <div className="history-job-list">{jobs.map((item) => (
                <button className={`history-job ${job?.id === item.id ? 'history-job-active' : ''}`} type="button" key={item.id} onClick={() => void loadJob(item.id)}>
                  <span><strong>{item.id}</strong><small>Repository {item.repository_id} · Plan {item.plan_id}</small></span>
                  <span className={`status-chip ${['completed', 'failed', 'blocked'].includes(item.status) ? item.status : 'running'}`}><span />{item.status}</span>
                  <time dateTime={item.started_at}>{new Date(item.started_at).toLocaleString()}</time>
                </button>
              ))}</div>}
        <form className="inline-field history-lookup" onSubmit={(event) => void findJob(event)}>
          <label className="visually-hidden" htmlFor="history-job-id">Migration job ID</label>
          <input id="history-job-id" value={jobId} onChange={(event) => setJobId(event.target.value)} placeholder="Look up a job ID not shown above" />
          <button className="gold-button" type="submit" disabled={loadingDetail}>{loadingDetail ? <LoaderCircle className="spin" size={14} /> : <Search size={14} />} Look up</button>
        </form>
      </section>

      {loadingDetail && <section className="panel page-empty"><LoaderCircle className="spin" size={20} /><span>Loading recorded plan or job details from the backend…</span></section>}
      {plan && <>
        <section className="panel page-panel">
          <div className="page-section-heading"><div><p className="eyebrow">SAVED MIGRATION PLAN</p><h2>{plan.dependency.name}: start {plan.dependency.current_version || 'unknown'} → {plan.dependency.target_version}</h2><p>Plan {plan.id} · Saved {new Date(plan.created_at).toLocaleString()}</p></div><span className="heading-icon"><Package size={19} /></span></div>
          <div className="detail-grid">
            <div><dt>Repository ID</dt><dd>{plan.repository_id}</dd></div>
            <div><dt>Ecosystem</dt><dd>{plan.dependency.ecosystem}</dd></div>
            <div><dt>Manifest</dt><dd>{plan.dependency.manifest_path}</dd></div>
            <div><dt>Reported starting version</dt><dd>{plan.dependency.current_version || 'Not recorded'} (not independently verified)</dd></div>
          </div>
        </section>
        <section className="insights-detail-grid">
          <article className="panel page-panel">
            <div className="page-section-heading"><div><p className="eyebrow">COMPATIBILITY NOTES</p><h2><Activity size={17} /> Breaking changes</h2></div></div>
            {plan.breaking_changes.length
              ? <div className="record-list">{plan.breaking_changes.map((change, index) => <article key={`${change.type}-${index}`}><span className={`severity severity-${change.severity}`}>{change.severity}</span><p>{change.description}</p><small>{change.type.replaceAll('_', ' ')} · {change.source}</small></article>)}</div>
              : <div className="page-empty compact"><Activity size={18} /><span>No specific breaking-change notes were saved.</span></div>}
          </article>
          <article className="panel page-panel">
            <div className="page-section-heading"><div><p className="eyebrow">PLANNER RISK NOTES</p><h2><AlertTriangle size={17} /> Risks and affected files</h2></div></div>
            {plan.risks.length
              ? <ul className="risk-list">{plan.risks.map((risk, index) => <li key={`${risk}-${index}`}><AlertTriangle size={14} />{risk}</li>)}</ul>
              : <div className="page-empty compact"><span>No risk notes were saved.</span></div>}
            {plan.affected_files.length > 0 && <ul className="risk-list">{plan.affected_files.map((file, index) => <li key={`${file.path}-${index}`}><FileCode2 size={14} /><span>{file.path} — {file.reason}</span></li>)}</ul>}
          </article>
        </section>
        <section className="panel page-panel">
          <div className="page-section-heading"><div><p className="eyebrow">PROPOSED PLAN</p><h2>{plan.planned_edits.length} planned edits</h2><p>Review-only plan data. No edits or commands are run from this page.</p></div></div>
          {plan.planned_edits.length
            ? <div className="record-list">{plan.planned_edits.map((edit, index) => <article key={`${edit.file_path}-${index}`}><strong>{edit.file_path}</strong><p>{edit.description}</p><small>Original and proposed code are included in the saved plan.</small></article>)}</div>
            : <div className="page-empty compact"><FileText size={18} /><span>No planned edits were saved.</span></div>}
          {plan.execution_commands.length > 0 && <details className="plan-commands"><summary>View saved command suggestions</summary><pre>{JSON.stringify(plan.execution_commands, null, 2)}</pre></details>}
        </section>
      </>}
      {job && report && <>
        <section className="panel page-panel">
          <div className="page-section-heading"><div><p className="eyebrow">JOB STATUS</p><h2>{job.status.replaceAll('_', ' ')}</h2><p>Job {job.id} · Plan {job.plan_id}</p></div><span className={`status-chip ${['completed', 'failed', 'blocked'].includes(job.status) ? job.status : 'running'}`}><span />{job.status}</span></div>
          <div className="detail-grid"><div><dt>Progress</dt><dd>{job.progress}% · {job.current_step || 'No current step reported'}</dd></div><div><dt>Started</dt><dd>{new Date(job.started_at).toLocaleString()}</dd></div><div><dt>Completed</dt><dd>{job.completed_at ? new Date(job.completed_at).toLocaleString() : 'Not completed'}</dd></div><div><dt>Repository ID</dt><dd>{job.repository_id}</dd></div></div>
        </section>
        <section className="panel page-panel">
          <div className="page-section-heading"><div><p className="eyebrow">BACKEND REPORT</p><h2><ShieldCheck size={18} /> Verification evidence</h2><p>Report status: {report.status}</p></div><FileText size={19} className="page-icon" /></div>
          {report.final_result
            ? <div className="report-evidence"><p>{report.final_result.summary}</p><div className="report-stats"><span>{report.final_result.tests_passed} passed</span><span>{report.final_result.tests_failed} failed</span><span>{report.final_result.tests_skipped} skipped</span><span>{report.final_result.modified_files.length} modified files</span></div></div>
            : <div className="page-empty compact"><FileText size={18} /><span>The report does not yet contain a final verification result.</span></div>}
          <p className="form-help">{report.command_history.length} command record(s) · {report.repair_attempts.length} repair attempt(s) recorded</p>
        </section>
      </>}
    </div>
  );
}
