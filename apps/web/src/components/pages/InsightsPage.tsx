'use client';

import { Activity, AlertTriangle, FileCode2, LockKeyhole, Package, Sparkles } from 'lucide-react';
import { useWorkspace } from '@/components/WorkspaceShell';
import { PageHeader } from './PageHeader';

export function InsightsPage() {
  const { latestPlan } = useWorkspace();

  return (
    <div className="workspace-page">
      <PageHeader eyebrow="PLAN-BASED FINDINGS" title="AI Insights" description="This page only presents findings returned by a migration plan created in the current browser session." />
      {!latestPlan
        ? <section className="panel page-empty"><Sparkles size={22} /><strong>No plan analysis available in this session</strong><span>Request a plan from New Migration to display its actual analysis here. Plans are not listed by the current API.</span></section>
        : <>
          <section className="panel page-panel">
            <div className="page-section-heading"><div><p className="eyebrow">PLAN REVIEW</p><h2>{latestPlan.dependency.name}: start {latestPlan.dependency.current_version || 'unknown'} → {latestPlan.dependency.target_version}</h2><p>Plan {latestPlan.id} · Generated {new Date(latestPlan.created_at).toLocaleString()}</p><p className="form-help">Reported starting version is not independently verified.</p></div><span className="heading-icon"><Sparkles size={19} /></span></div>
            <div className="insights-summary-grid">
              <article><FileCode2 size={17} /><strong>{latestPlan.affected_files.length}</strong><span>Affected files returned by planner</span></article>
              <article><Package size={17} /><strong>{latestPlan.planned_edits.length}</strong><span>Proposed edits returned by planner</span></article>
              <article><AlertTriangle size={17} /><strong>{latestPlan.risks.length}</strong><span>Risk notes returned by planner</span></article>
            </div>
          </section>
          <section className="insights-detail-grid">
            <article className="panel page-panel">
              <div className="page-section-heading"><div><p className="eyebrow">COMPATIBILITY NOTES</p><h2><Activity size={17} /> Breaking-change considerations</h2></div></div>
              {latestPlan.breaking_changes.length > 0
                ? <div className="record-list">{latestPlan.breaking_changes.map((change, index) => <article key={`${change.type}-${index}`}><span className={`severity severity-${change.severity}`}>{change.severity}</span><p>{change.description}</p><small>{change.type.replaceAll('_', ' ')} · {change.source}</small></article>)}</div>
                : <div className="page-empty compact"><Activity size={18} /><span>The plan returned no specific breaking-change notes. This does not establish runtime compatibility.</span></div>}
            </article>
            <article className="panel page-panel">
              <div className="page-section-heading"><div><p className="eyebrow">PLANNER RISK NOTES</p><h2>Risks reported</h2></div></div>
              {latestPlan.risks.length > 0
                ? <ul className="risk-list">{latestPlan.risks.map((risk, index) => <li key={`${risk}-${index}`}><AlertTriangle size={14} />{risk}</li>)}</ul>
                : <div className="page-empty compact"><Sparkles size={18} /><span>No risk notes were returned in this plan.</span></div>}
            </article>
          </section>
          <section className="panel page-panel security-disclaimer">
            <LockKeyhole size={17} /><div><strong>Security scan unavailable</strong><span>The backend has no vulnerability-scanning endpoint. No package safety or vulnerability result is implied by these plan findings.</span></div>
          </section>
        </>}
    </div>
  );
}
