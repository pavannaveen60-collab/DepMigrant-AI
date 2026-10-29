'use client';

import { FormEvent, useEffect, useState } from 'react';
import { Activity, Check, Download, LockKeyhole, RotateCcw, Save, Settings as SettingsIcon, ShieldCheck } from 'lucide-react';
import { useWorkspace, WorkspacePreferences } from '@/components/WorkspaceShell';
import { PageHeader } from './PageHeader';

export function SettingsPage() {
  const { preferences, savePreferences, resetPreferences } = useWorkspace();
  const [draft, setDraft] = useState<WorkspacePreferences>(preferences);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => { setDraft(preferences); }, [preferences]);

  const save = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      savePreferences(draft);
      setError('');
      setNotice('Workspace preferences saved in this browser.');
    } catch {
      setError('Could not save preferences in browser storage.');
    }
  };

  const reset = () => {
    try {
      resetPreferences();
      setError('');
      setNotice('Workspace preferences reset to their defaults.');
    } catch {
      setError('Could not reset preferences in browser storage.');
    }
  };

  const exportSettings = () => {
    try {
      const exportData = {
        version: 1,
        preferences: {
          defaultRepositoryType: draft.defaultRepositoryType,
          confirmBeforeExecution: draft.confirmBeforeExecution,
          theme: draft.theme,
        },
      };
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'depmigrant-settings.json';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setError('');
      setNotice('Non-sensitive preferences exported as JSON.');
    } catch {
      setError('Could not export preferences as a JSON file.');
    }
  };

  return (
    <div className="workspace-page">
      <PageHeader eyebrow="WORKSPACE CONTROL" title="Settings" description="Manage local preferences. Provider credentials and execution policy stay on the backend." />
      {notice && <div className="notice-banner" role="status"><Check size={16} /><span>{notice}</span><button aria-label="Dismiss notice" onClick={() => setNotice('')}>×</button></div>}
      {error && <div className="error-banner" role="alert"><Activity size={17} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}>×</button></div>}

      <form onSubmit={save} className="settings-stack">
        <section className="panel page-panel settings-section">
          <div className="page-section-heading"><div><p className="eyebrow">APPEARANCE</p><h2><SettingsIcon size={17} /> Display</h2></div></div>
          <label className="setting-row setting-control" htmlFor="display-theme"><span><strong>Theme</strong><small>Choose the appearance used across this workspace.</small></span><select id="display-theme" value={draft.theme} onChange={(event) => setDraft((current) => ({ ...current, theme: event.target.value as 'dark' | 'light' }))}><option value="dark">Dark</option><option value="light">Light</option></select></label>
        </section>

        <section className="panel page-panel settings-section">
          <div className="page-section-heading"><div><p className="eyebrow">LOCAL PREFERENCES</p><h2>Migration workflow</h2><p>Saved only in this browser; these preferences do not change backend policy.</p></div></div>
          <label className="setting-row setting-control"><span><strong>Default repository type</strong><small>Preselect this source on the New Migration page.</small></span><select value={draft.defaultRepositoryType} onChange={(event) => setDraft((current) => ({ ...current, defaultRepositoryType: event.target.value as 'git' | 'archive' }))}><option value="git">Git URL</option><option value="archive">Local archive</option></select></label>
          <label className="setting-row setting-control"><span><strong>Confirm before requesting execution</strong><small>Show a browser confirmation before calling the existing migration-start endpoint.</small></span><input type="checkbox" checked={draft.confirmBeforeExecution} onChange={(event) => setDraft((current) => ({ ...current, confirmBeforeExecution: event.target.checked }))} /></label>
        </section>

        <section className="panel page-panel settings-section">
          <div className="page-section-heading"><div><p className="eyebrow">AI PROVIDER</p><h2><LockKeyhole size={17} /> Credentials</h2></div><span className="setting-state">Backend-managed</span></div>
          <p className="setting-description">Provider credentials are configured through backend environment variables. This frontend does not read, display, or store API keys.</p>
          <p className="setting-description"><ShieldCheck size={14} /> Migration execution remains governed by backend safety controls. This page cannot enable unsafe repository execution.</p>
        </section>

        <div className="settings-actions">
          <button className="gold-button" type="submit"><Save size={14} /> Save preferences</button>
          <button className="outline-button" type="button" onClick={reset}><RotateCcw size={14} /> Reset defaults</button>
          <button className="outline-button" type="button" onClick={exportSettings}><Download size={14} /> Export Settings</button>
        </div>
      </form>

      <section className="panel page-panel settings-section" id="about">
        <div className="page-section-heading"><div><p className="eyebrow">ABOUT</p><h2>DepMigrant AI</h2><p>Version 0.1.0</p></div></div>
        <p className="setting-description">A careful workspace for Python dependency migration: inspect repositories, review AI-assisted upgrade plans, and verify outcomes with evidence.</p>
      </section>
    </div>
  );
}
