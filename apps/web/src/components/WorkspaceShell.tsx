'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Activity,
  ChevronDown,
  History,
  Home,
  Layers3,
  Menu,
  Plus,
  Search,
  Settings,
  Sparkles,
  X,
} from 'lucide-react';
import {
  createContext,
  FormEvent,
  ReactNode,
  useContext,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { healthApi } from '@/lib/api';
import type { MigrationPlan } from '@/types';

type Route = {
  href: string;
  label: string;
  icon: typeof Home;
};

const navigation: Route[] = [
  { href: '/', label: 'Dashboard', icon: Home },
  { href: '/migration', label: 'New Migration', icon: Plus },
  { href: '/repositories', label: 'Repositories', icon: Layers3 },
  { href: '/history', label: 'Migration History', icon: History },
  { href: '/insights', label: 'AI Insights', icon: Activity },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export interface WorkspacePreferences {
  defaultRepositoryType: 'git' | 'archive';
  confirmBeforeExecution: boolean;
  theme: 'dark' | 'light';
}

type BackendHealth =
  | { state: 'checking' | 'unavailable' | 'error' }
  | { state: 'online'; service: string };

interface WorkspaceContextValue {
  latestPlan: MigrationPlan | null;
  setLatestPlan: (plan: MigrationPlan) => void;
  preferences: WorkspacePreferences;
  savePreferences: (preferences: WorkspacePreferences) => void;
  resetPreferences: () => void;
}

const defaultPreferences: WorkspacePreferences = {
  defaultRepositoryType: 'git',
  confirmBeforeExecution: true,
  theme: 'dark',
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error('useWorkspace must be used inside WorkspaceShell');
  return context;
}

function parseWorkspacePreferences(value: unknown): WorkspacePreferences {
  if (!value || typeof value !== 'object') return defaultPreferences;
  const candidate = value as Partial<WorkspacePreferences>;
  return {
    defaultRepositoryType: candidate.defaultRepositoryType === 'archive' ? 'archive' : 'git',
    confirmBeforeExecution: typeof candidate.confirmBeforeExecution === 'boolean'
      ? candidate.confirmBeforeExecution
      : true,
    theme: candidate.theme === 'light' ? 'light' : 'dark',
  };
}

export function WorkspaceShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [health, setHealth] = useState<BackendHealth>({ state: 'checking' });
  const healthRequest = useRef<AbortController | null>(null);
  const [latestPlan, setLatestPlan] = useState<MigrationPlan | null>(null);
  const [preferences, setPreferences] = useState(defaultPreferences);
  const accountMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem('depmigrant.preferences');
      if (saved) {
        const parsed: unknown = JSON.parse(saved);
        setPreferences(parseWorkspacePreferences(parsed));
      }
    } catch {
      setPreferences(defaultPreferences);
    }
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = preferences.theme;
    document.documentElement.style.colorScheme = preferences.theme;
  }, [preferences.theme]);

  const checkHealth = useCallback(async () => {
    healthRequest.current?.abort();
    const controller = new AbortController();
    healthRequest.current = controller;
    setHealth({ state: 'checking' });
    try {
      const { data } = await healthApi.check(controller.signal);
      if (controller.signal.aborted) return;
      if (typeof data.status !== 'string' || typeof data.service !== 'string') {
        setHealth({ state: 'error' });
      } else if (data.status === 'healthy') {
        setHealth({ state: 'online', service: data.service });
      } else {
        setHealth({ state: 'unavailable' });
      }
    } catch (requestError) {
      if (controller.signal.aborted) return;
      const hasHttpResponse = typeof requestError === 'object'
        && requestError !== null
        && 'response' in requestError
        && Boolean(requestError.response);
      setHealth({ state: hasHttpResponse ? 'unavailable' : 'error' });
    } finally {
      if (healthRequest.current === controller) healthRequest.current = null;
    }
  }, []);

  useEffect(() => {
    void checkHealth();
    const interval = window.setInterval(() => void checkHealth(), 30000);
    return () => {
      window.clearInterval(interval);
      healthRequest.current?.abort();
    };
  }, [checkHealth]);

  useEffect(() => {
    if (!accountMenuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setAccountMenuOpen(false);
    };
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (event.target instanceof Node && !accountMenuRef.current?.contains(event.target)) {
        setAccountMenuOpen(false);
      }
    };
    document.addEventListener('keydown', closeOnEscape);
    document.addEventListener('mousedown', closeOnOutsideClick);
    return () => {
      document.removeEventListener('keydown', closeOnEscape);
      document.removeEventListener('mousedown', closeOnOutsideClick);
    };
  }, [accountMenuOpen]);

  const savePreferences = (next: WorkspacePreferences) => {
    window.localStorage.setItem('depmigrant.preferences', JSON.stringify(next));
    setPreferences(next);
  };

  const resetPreferences = () => {
    window.localStorage.setItem('depmigrant.preferences', JSON.stringify(defaultPreferences));
    setPreferences(defaultPreferences);
  };

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = search.trim();
    router.push(query ? `/repositories?query=${encodeURIComponent(query)}` : '/repositories');
    setMobileMenuOpen(false);
  };

  const contextValue: WorkspaceContextValue = {
    latestPlan,
    setLatestPlan,
    preferences,
    savePreferences,
    resetPreferences,
  };

  return (
    <WorkspaceContext.Provider value={contextValue}>
      <div className="app-shell" onKeyDownCapture={(event) => {
        if (event.key === 'Escape') setAccountMenuOpen(false);
      }}>
        {mobileMenuOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setMobileMenuOpen(false)} />}
        <aside className={`sidebar ${mobileMenuOpen ? 'sidebar-open' : ''}`} aria-label="Main navigation">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>
            <div>
              <div className="brand-name">DepMigrant <span>AI</span></div>
              <div className="brand-caption">Autonomous Python<br />Dependency Migration</div>
            </div>
            <button className="sidebar-close" aria-label="Close navigation" onClick={() => setMobileMenuOpen(false)}><X size={18} /></button>
          </div>
          <div className="sidebar-rule" />
          <nav className="side-nav">
            {navigation.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || (href !== '/' && pathname.startsWith(`${href}/`));
              return (
                <Link
                  key={href}
                  href={href}
                  className={`nav-item ${active ? 'nav-active' : ''}`}
                  title={label}
                  aria-current={active ? 'page' : undefined}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  <Icon size={17} strokeWidth={1.8} />
                  <span>{label}</span>
                </Link>
              );
            })}
          </nav>
          <div className="sidebar-foot">
            <div className="foot-spark"><Sparkles size={16} /></div>
            <strong>AI-assisted upgrades</strong>
            <span>Clear plans. Bounded steps.<br />Evidence you can review.</span>
          </div>
          <div className="sidebar-version">DEPMIGRANT <span>•</span> LOCAL WORKSPACE</div>
        </aside>

        <main className="main-area">
          <header className="topbar">
            <button className="mobile-menu" aria-label="Open navigation" aria-expanded={mobileMenuOpen} onClick={() => setMobileMenuOpen(true)}><Menu size={21} /></button>
            <form className="global-search" role="search" onSubmit={submitSearch}>
              <Search size={15} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search repositories..."
                aria-label="Search repositories"
              />
              <kbd>⌘ K</kbd>
            </form>
            <button
              className={`connection-pill connection-${health.state}`}
              type="button"
              onClick={() => void checkHealth()}
              aria-label={`Refresh backend health. Current state: ${health.state}`}
              aria-live="polite"
              title="Refresh backend health"
            >
              <span className="connection-dot" />
              {health.state === 'checking'
                ? 'Checking'
                : health.state === 'online'
                  ? `Online · ${health.service}`
                  : health.state === 'unavailable' ? 'Unavailable' : 'Error'}
            </button>
            <div className="account-menu" ref={accountMenuRef}>
              <button
                className="user-avatar"
                aria-label="Open local workspace account menu"
                aria-haspopup="menu"
                aria-expanded={accountMenuOpen}
                onClick={() => setAccountMenuOpen((open) => !open)}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') setAccountMenuOpen(false);
                }}
              >
                D <ChevronDown size={11} />
              </button>
              {accountMenuOpen && (
                <div className="account-dropdown" role="menu" aria-label="Local workspace account">
                  <div className="account-summary">
                    <strong>Local demo workspace</strong>
                    <span>Not signed in · No account service configured</span>
                  </div>
                  <Link href="/settings" role="menuitem" onClick={() => setAccountMenuOpen(false)}>Settings</Link>
                  <Link href="/settings#about" role="menuitem" onClick={() => setAccountMenuOpen(false)}>About DepMigrant AI</Link>
                </div>
              )}
            </div>
          </header>
          <div className="content-wrap">{children}</div>
        </main>
      </div>
    </WorkspaceContext.Provider>
  );
}
