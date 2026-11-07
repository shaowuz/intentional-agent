import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  CircleHelp,
  FlaskConical,
  KeyRound,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Network,
  Orbit,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  SkipForward,
  Square,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { ApiError, downloadRun, message, request } from "./api";
import type {
  Agent,
  Experiment,
  ExperimentConfig,
  ExperimentSummary,
  ForumMessage,
  Health,
  ModelInfo,
  User,
} from "./types";
import SetupModal from "./SetupModal";
import { InteractionGraph, PayoffChart } from "./Visualizations";

const TOKEN_KEY = "intentional-agent-session";
const currency = (value: number) => `$${Number(value || 0).toFixed(4)}`;
const dateLabel = (value?: string) =>
  value
    ? new Date(value).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Just created";

export default function App() {
  const [token, setToken] = useState<string | null>(() =>
    sessionStorage.getItem(TOKEN_KEY),
  );
  const activeToken = useRef(token);
  activeToken.current = token;
  const [user, setUser] = useState<User | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [view, setView] = useState<"experiments" | "run" | "settings">(
    "experiments",
  );
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [run, setRun] = useState<Experiment | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const activeExperimentId = useRef(selectedId);
  activeExperimentId.current = selectedId;
  const [defaults, setDefaults] = useState<ExperimentConfig | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelError, setModelError] = useState("");
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [showSetup, setShowSetup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loadingList, setLoadingList] = useState(true);
  const [error, setError] = useState("");
  const [setupError, setSetupError] = useState("");

  const clearSession = useCallback(() => {
    activeToken.current = null;
    activeExperimentId.current = null;
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setRun(null);
    setSelectedId(null);
    setExperiments([]);
    setKeyConfigured(false);
    setView("experiments");
    setShowSetup(false);
    setSetupError("");
    setDefaults(null);
    setModels([]);
    setModelError("");
    setBusy(false);
  }, []);
  const handleError = useCallback(
    (cause: unknown) => {
      if (cause instanceof ApiError && cause.status === 401) clearSession();
      setError(message(cause));
    },
    [clearSession],
  );

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const result = await request<Health>("/health", null);
        if (active) setHealth(result);
      } catch {
        if (active) setHealth(null);
      }
    };
    void load();
    const timer = setInterval(load, 20000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!token) return;
    let active = true;
    request<User>("/auth/me", token)
      .then((value) => {
        if (active) setUser(value);
      })
      .catch((cause) => {
        if (active) handleError(cause);
      });
    return () => {
      active = false;
    };
  }, [token, handleError]);

  const loadList = useCallback(async () => {
    if (!token) return;
    try {
      const result = await request<{ experiments: ExperimentSummary[] }>(
        "/experiments",
        token,
      );
      if (activeToken.current === token) setExperiments(result.experiments);
    } catch (cause) {
      if (activeToken.current === token) handleError(cause);
    } finally {
      if (activeToken.current === token) setLoadingList(false);
    }
  }, [token, handleError]);

  useEffect(() => {
    if (!user || !token) return;
    let active = true;
    setLoadingList(true);
    void loadList();
    request<{ key_configured: boolean }>("/settings", token)
      .then((result) => {
        if (active) setKeyConfigured(result.key_configured);
      })
      .catch((cause) => {
        if (active) handleError(cause);
      });
    request<ExperimentConfig>("/config/defaults", token)
      .then((result) => {
        if (active) setDefaults(result);
      })
      .catch((cause) => {
        if (active) handleError(cause);
      });
    request<{ models: ModelInfo[]; error?: string }>("/models", token)
      .then((result) => {
        if (active) {
          setModels(result.models);
          setModelError(result.error ?? "");
        }
      })
      .catch((cause) => {
        if (active) setModelError(message(cause));
      });
    const timer = setInterval(() => {
      void loadList();
    }, 6000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [user, token, loadList, handleError]);

  useEffect(() => {
    if (!selectedId || !token) return;
    let active = true;
    let inFlight = false;
    const load = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const result = await request<Experiment>(
          `/experiments/${selectedId}`,
          token,
        );
        if (
          active &&
          activeToken.current === token &&
          activeExperimentId.current === selectedId
        )
          setRun(result);
      } catch (cause) {
        if (active) handleError(cause);
      } finally {
        inFlight = false;
      }
    };
    void load();
    const timer = setInterval(load, 1500);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [selectedId, token, handleError]);

  async function authenticate(
    mode: "login" | "register",
    username: string,
    password: string,
  ) {
    const result = await request<{ token: string; user: User }>(
      `/auth/${mode}`,
      null,
      { method: "POST", body: JSON.stringify({ username, password }) },
    );
    sessionStorage.setItem(TOKEN_KEY, result.token);
    setError("");
    setUser(result.user);
    setToken(result.token);
  }
  async function logout() {
    try {
      await request("/auth/logout", token, { method: "POST" });
    } catch {
      /* Clear the browser session even if the server is unavailable. */
    }
    if (activeToken.current === token) clearSession();
  }
  function openRun(id: string) {
    activeExperimentId.current = id;
    setError("");
    if (id !== selectedId) setRun(null);
    setSelectedId(id);
    setView("run");
  }
  async function createRun(config: ExperimentConfig) {
    setBusy(true);
    setSetupError("");
    try {
      const result = await request<Experiment>("/experiments", token, {
        method: "POST",
        body: JSON.stringify(config),
      });
      if (activeToken.current !== token) return;
      activeExperimentId.current = result.id;
      setRun(result);
      setSelectedId(result.id);
      setView("run");
      setShowSetup(false);
      await loadList();
    } catch (cause) {
      if (activeToken.current === token) setSetupError(message(cause));
    } finally {
      if (activeToken.current === token) setBusy(false);
    }
  }
  async function control(action: "start" | "pause" | "step" | "stop") {
    if (!run) return;
    setBusy(true);
    setError("");
    try {
      const result = await request<Experiment>(
        `/experiments/${run.id}/control`,
        token,
        { method: "POST", body: JSON.stringify({ action }) },
      );
      if (activeToken.current !== token) return;
      if (activeExperimentId.current === run.id) setRun(result);
      await loadList();
    } catch (cause) {
      if (activeToken.current === token) handleError(cause);
    } finally {
      if (activeToken.current === token) setBusy(false);
    }
  }
  async function exportRun(format: "json" | "csv") {
    if (!run || !token) return;
    try {
      await downloadRun(run.id, format, token);
    } catch (cause) {
      handleError(cause);
    }
  }
  async function reconcileUsage(confirmedCost: number, note: string) {
    if (!run) return;
    const result = await request<Experiment>(
      `/experiments/${run.id}/usage/reconcile`,
      token,
      {
        method: "POST",
        body: JSON.stringify({ confirmed_cost_usd: confirmedCost, note }),
      },
    );
    if (activeToken.current !== token) return;
    if (activeExperimentId.current === run.id) setRun(result);
    await loadList();
  }

  if (!token)
    return (
      <AuthScreen
        onAuthenticate={authenticate}
        serverAvailable={!!health}
        initialError={error}
      />
    );
  if (!user)
    return (
      <div className="loading-screen">
        <Brand />
        <p>Opening your research workspace…</p>
        <button className="button secondary" onClick={clearSession}>
          Return to sign in
        </button>
      </div>
    );

  const activeCount = experiments.filter(
    (experiment) => experiment.status === "running",
  ).length;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <div className="workspace-label">
          <span className="workspace-icon">IA</span>
          <span>
            <strong>Research workspace</strong>
            <small>Local environment</small>
          </span>
        </div>
        <span className="nav-heading">WORKSPACE</span>
        <nav aria-label="Workspace navigation">
          <button
            className={view !== "settings" ? "nav-item active" : "nav-item"}
            onClick={() => {
              setView("experiments");
              void loadList();
            }}
          >
            <LayoutDashboard size={18} />
            Experiments<span className="nav-count">{experiments.length}</span>
          </button>
          <button
            className={view === "settings" ? "nav-item active" : "nav-item"}
            onClick={() => setView("settings")}
          >
            <KeyRound size={18} />
            API Settings
            {keyConfigured && (
              <span className="nav-key-dot" aria-label="Key configured" />
            )}
          </button>
        </nav>
        {experiments.length > 0 && (
          <div className="recent-runs">
            <span className="nav-heading">RECENT EXPERIMENTS</span>
            {experiments.slice(0, 5).map((experiment) => (
              <button
                key={experiment.id}
                onClick={() => openRun(experiment.id)}
                className={`recent-run ${view === "run" && selectedId === experiment.id ? "selected" : ""}`}
              >
                <span className={`status-dot ${experiment.status}`} />
                <span>{experiment.name}</span>
              </button>
            ))}
          </div>
        )}
        <div className="sidebar-bottom">
          <div className="environment-status">
            <span
              className={health ? "status-dot completed" : "status-dot stopped"}
            />
            <strong>
              {health ? "Backend connected" : "Backend unavailable"}
            </strong>
            <small>
              {health ? `Local · v${health.version}` : "Check the local server"}
            </small>
          </div>
          <div className="researcher">
            <span className="avatar">
              {user.username.slice(0, 2).toUpperCase()}
            </span>
            <span>
              <strong>{user.username}</strong>
              <small>Researcher</small>
            </span>
            <button
              className="icon-button"
              onClick={() => void logout()}
              aria-label="Sign out"
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <span className="breadcrumb">
            Workspace
            <ChevronRight size={14} />
            <strong>
              {view === "settings"
                ? "API Settings"
                : view === "run"
                  ? "Experiment"
                  : "Experiments"}
            </strong>
          </span>
          <div className="topbar-right">
            <span className="researcher-view">
              <ShieldCheck size={14} />
              Researcher view
            </span>
            {activeCount > 0 && (
              <span className="live-indicator">
                <span />
                {activeCount} running
              </span>
            )}
          </div>
        </header>
        <main>
          {error && (
            <div className="notice error global-notice" role="alert">
              <span>{error}</span>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {view === "experiments" && (
            <ExperimentsView
              experiments={experiments}
              loading={loadingList}
              onOpen={openRun}
              onCreate={() => {
                setSetupError("");
                setShowSetup(true);
              }}
              canCreate={!!defaults}
            />
          )}
          {view === "run" &&
            (run ? (
              <RunView
                key={run.id}
                run={run}
                busy={busy}
                health={health}
                keyConfigured={keyConfigured}
                onControl={control}
                onExport={exportRun}
                onReconcile={reconcileUsage}
                onBack={() => setView("experiments")}
                onSettings={() => setView("settings")}
              />
            ) : (
              <div className="empty-state">
                <RefreshCw className="spinning" />
                <h2>Loading experiment</h2>
                <p>Retrieving the saved state and event log.</p>
              </div>
            ))}
          {view === "settings" && (
            <SettingsView
              token={token}
              keyConfigured={keyConfigured}
              onKeyChange={(configured) => {
                if (activeToken.current === token) setKeyConfigured(configured);
              }}
              health={health}
              user={user}
              onLogout={logout}
            />
          )}
        </main>
        <footer className="workspace-footer">
          <span>Intentional Agent</span>
          <span>A workspace for reproducible experimental records.</span>
          <span>Local MVP · {new Date().getFullYear()}</span>
        </footer>
      </div>
      {showSetup && defaults && (
        <SetupModal
          defaults={defaults}
          models={models}
          modelError={modelError}
          keyConfigured={keyConfigured}
          busy={busy}
          error={setupError}
          onClose={() => {
            if (!busy) setShowSetup(false);
          }}
          onCreate={(config) => void createRun(config)}
        />
      )}
    </div>
  );
}

function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <Orbit size={23} strokeWidth={1.7} />
      </span>
      <span>
        intentional<span className="brand-secondary">agent</span>
      </span>
    </div>
  );
}

function AuthScreen({
  onAuthenticate,
  serverAvailable,
  initialError,
}: {
  onAuthenticate: (
    mode: "login" | "register",
    username: string,
    password: string,
  ) => Promise<void>;
  serverAvailable: boolean;
  initialError: string;
}) {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initialError);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onAuthenticate(mode, username.trim(), password);
      setPassword("");
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-page">
      <div className="auth-top">
        <Brand />
        <span className="badge neutral">LOCAL RESEARCH ENVIRONMENT</span>
      </div>
      <div className="auth-layout">
        <section className="auth-intro">
          <div className="eyebrow">
            <span className="short-line" /> INTENTIONAL AGENT / EXPERIMENTAL LAB
          </div>
          <h1>
            Different objectives.
            <br />
            Shared environment.
            <br />
            <span>Emergent behavior.</span>
          </h1>
          <p>
            Study how agents cooperate, communicate, and respond to hidden
            objectives in repeated games.
          </p>
          <div className="auth-features">
            <div>
              <Network size={20} />
              <span>
                <strong>Design controlled experiments</strong>
                <small>
                  Choose models, private objectives, and information access.
                </small>
              </span>
            </div>
            <div>
              <MessageSquare size={20} />
              <span>
                <strong>Follow the conversation</strong>
                <small>
                  Observe interactions, forum discussions, and decisions.
                </small>
              </span>
            </div>
            <div>
              <Search size={20} />
              <span>
                <strong>Inspect the evidence</strong>
                <small>
                  Trace each agent's observations, tools, and game results.
                </small>
              </span>
            </div>
          </div>
          <div className="auth-footnote">
            <span
              className={
                serverAvailable ? "status-dot completed" : "status-dot stopped"
              }
            />
            {serverAvailable
              ? "Local backend is connected"
              : "Waiting for the local backend"}
          </div>
        </section>
        <section className="auth-card">
          <span className="auth-card-icon">
            <FlaskConical size={23} />
          </span>
          <h2>
            {mode === "register"
              ? "Create your workspace account"
              : "Welcome back"}
          </h2>
          <p>
            {mode === "register"
              ? "Your experiments and API key belong to your account."
              : "Sign in to continue your experiments."}
          </p>
          <div className="segmented-control">
            <button
              className={mode === "register" ? "selected" : ""}
              onClick={() => {
                setMode("register");
                setError("");
              }}
            >
              Create account
            </button>
            <button
              className={mode === "login" ? "selected" : ""}
              onClick={() => {
                setMode("login");
                setError("");
              }}
            >
              Sign in
            </button>
          </div>
          <form onSubmit={submit}>
            {error && (
              <div className="notice error" role="alert">
                {error}
              </div>
            )}
            <label className="field">
              Username
              <input
                required
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Your researcher name"
                minLength={3}
                maxLength={40}
              />
            </label>
            <label className="field">
              Password
              <input
                required
                type="password"
                autoComplete={
                  mode === "register" ? "new-password" : "current-password"
                }
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={
                  mode === "register"
                    ? "At least 8 characters"
                    : "Enter your password"
                }
                minLength={mode === "register" ? 8 : undefined}
              />
            </label>
            <button
              type="submit"
              className="button primary full-width"
              disabled={busy}
            >
              {busy
                ? "Please wait…"
                : mode === "register"
                  ? "Create account"
                  : "Sign in"}
              <ArrowRight size={17} />
            </button>
          </form>
          <div className="auth-account-note">
            <ShieldCheck size={16} />
            <span>
              This account is stored on your local server. Add your OpenRouter
              API key later, or start with a free scripted demo.
            </span>
          </div>
        </section>
      </div>
      <footer className="auth-footer">
        <span>Intentional Agent</span>
        <span>Repeated games. Observable decisions.</span>
      </footer>
    </div>
  );
}

function ExperimentsView({
  experiments,
  loading,
  onOpen,
  onCreate,
  canCreate,
}: {
  experiments: ExperimentSummary[];
  loading: boolean;
  onOpen: (id: string) => void;
  onCreate: () => void;
  canCreate: boolean;
}) {
  const [filter, setFilter] = useState("");
  const filtered = experiments.filter((experiment) =>
    experiment.name.toLowerCase().includes(filter.toLowerCase()),
  );
  const completed = experiments.filter(
    (experiment) => experiment.status === "completed",
  ).length;
  const running = experiments.filter(
    (experiment) => experiment.status === "running",
  ).length;
  const spend = experiments.reduce(
    (sum, experiment) => sum + experiment.cost_usd,
    0,
  );
  return (
    <div className="page-content">
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR RESEARCH WORKSPACE</span>
          <h1>Experiments</h1>
          <p>Design, run, and inspect repeated-game experiments.</p>
        </div>
        <button
          className="button primary"
          onClick={onCreate}
          disabled={!canCreate}
        >
          <Plus size={18} />
          New experiment
        </button>
      </div>
      <div className="metrics-grid">
        <Metric
          icon={<FlaskConical size={18} />}
          label="Total experiments"
          value={String(experiments.length)}
          detail="Saved in your workspace"
        />
        <Metric
          icon={<Activity size={18} />}
          label="Running now"
          value={String(running)}
          detail="Active experiment workers"
        />
        <Metric
          icon={<Check size={18} />}
          label="Completed"
          value={String(completed)}
          detail="All configured rounds finished"
        />
        <Metric
          icon={<Wallet size={18} />}
          label="Recorded API cost"
          value={currency(spend)}
          detail="From returned usage records"
        />
      </div>
      <section className="panel experiments-panel">
        <div className="panel-header">
          <div>
            <h2>Experiment history</h2>
            <p>Each run keeps its configuration and interaction records.</p>
          </div>
          <label className="search-field">
            <Search size={16} />
            <input
              aria-label="Search experiments"
              placeholder="Search experiments…"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
          </label>
        </div>
        {loading ? (
          <div className="empty-state compact">
            <RefreshCw className="spinning" />
            <p>Loading experiments…</p>
          </div>
        ) : experiments.length === 0 ? (
          <div className="empty-state first-experiment">
            <div className="empty-orbit">
              <Orbit size={38} strokeWidth={1.3} />
            </div>
            <span className="eyebrow">START WITH A QUESTION</span>
            <h2>Your first experiment starts here</h2>
            <p>
              Set up a small population and watch cooperation unfold.
              <br />A scripted demo lets you explore the full workflow without
              an API key.
            </p>
            <button
              className="button primary"
              onClick={onCreate}
              disabled={!canCreate}
            >
              <Plus size={17} />
              Create your first experiment
            </button>
            <div className="empty-step-row">
              <span>
                <b>01</b> Configure
              </span>
              <ChevronRight size={14} />
              <span>
                <b>02</b> Run
              </span>
              <ChevronRight size={14} />
              <span>
                <b>03</b> Inspect
              </span>
            </div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state compact">
            <Search size={24} />
            <h3>No matching experiments</h3>
            <p>Try a different name.</p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="experiment-table">
              <thead>
                <tr>
                  <th>Experiment</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>API cost</th>
                  <th>Created</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((experiment) => (
                  <tr key={experiment.id}>
                    <td>
                      <button
                        className="experiment-name"
                        onClick={() => onOpen(experiment.id)}
                      >
                        <span className="table-run-icon">
                          <FlaskConical size={19} />
                        </span>
                        <span>
                          <strong>{experiment.name}</strong>
                          <small>
                            {experiment.mode === "demo"
                              ? "Scripted demo · no LLM calls"
                              : "OpenRouter experiment"}
                          </small>
                        </span>
                      </button>
                    </td>
                    <td>
                      <StatusBadge status={experiment.status} />
                    </td>
                    <td>
                      <div className="table-progress">
                        <span>
                          {experiment.round} / {experiment.rounds} rounds
                        </span>
                        <div className="progress-track">
                          <i
                            style={{
                              width: `${(100 * experiment.round) / experiment.rounds}%`,
                            }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="number-cell">
                      {currency(experiment.cost_usd)}
                    </td>
                    <td className="muted nowrap">
                      {dateLabel(experiment.created_at)}
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        onClick={() => onOpen(experiment.id)}
                        aria-label={`Open ${experiment.name}`}
                      >
                        <ArrowRight size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <div className="workflow-note">
        <CircleHelp size={17} />
        <span>
          <strong>Start simple.</strong> Keep the same model in both groups,
          then vary one information condition at a time. Scripted demo outcomes
          are not evidence about LLM behavior.
        </span>
      </div>
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
  detail,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="metric">
      <div className="metric-top">
        <span>{label}</span>
        {icon}
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge status-badge ${status}`}>
      <span className={`status-dot ${status}`} />
      {status === "created" ? "Ready" : status.replaceAll("_", " ")}
    </span>
  );
}

function RunView({
  run,
  busy,
  health,
  keyConfigured,
  onControl,
  onExport,
  onReconcile,
  onBack,
  onSettings,
}: {
  run: Experiment;
  busy: boolean;
  health: Health | null;
  keyConfigured: boolean;
  onControl: (action: "start" | "pause" | "step" | "stop") => Promise<void>;
  onExport: (format: "json" | "csv") => Promise<void>;
  onReconcile: (confirmedCost: number, note: string) => Promise<void>;
  onBack: () => void;
  onSettings: () => void;
}) {
  const [tab, setTab] = useState<
    "overview" | "forum" | "inspector" | "results"
  >("overview");
  const [selectedAgent, setSelectedAgent] = useState(run.agents[0]?.id ?? "");
  const [followLatest, setFollowLatest] = useState(true);
  const [historicalRound, setHistoricalRound] = useState(1);
  const [confirmStop, setConfirmStop] = useState(false);
  const latestRound = Math.max(run.round, run.pending?.round || 0, 1);
  const round = followLatest
    ? latestRound
    : Math.min(historicalRound, latestRound);
  const visibleMatches = useMemo(
    () => run.matches.filter((match) => match.round <= round),
    [run.matches, round],
  );
  const currentMatches = visibleMatches.filter(
    (match) => match.round === round,
  );
  const cooperations = visibleMatches.reduce(
    (sum, match) =>
      sum + Number(match.action_a === "C") + Number(match.action_b === "C"),
    0,
  );
  const payoff = visibleMatches.reduce(
    (sum, match) => sum + match.payoff_a + match.payoff_b,
    0,
  );
  const finished = ["completed", "stopped"].includes(run.status);
  const running = run.status === "running";
  const canRun =
    !busy &&
    !finished &&
    !running &&
    (run.config.mode === "demo" || keyConfigured);
  function chooseAgent(id: string) {
    setSelectedAgent(id);
    setTab("inspector");
  }

  return (
    <div className="page-content run-page">
      <button className="text-button back-button" onClick={onBack}>
        <ArrowLeft size={15} />
        All experiments
      </button>
      <div className="page-heading run-heading">
        <div>
          <div className="run-eyebrow">
            <span className="eyebrow">EXPERIMENT WORKSPACE</span>
            <StatusBadge status={run.status} />
            <span
              className={`badge ${run.config.mode === "demo" ? "neutral" : "teal"}`}
            >
              {run.config.mode === "demo" ? "Scripted demo" : "OpenRouter"}
            </span>
          </div>
          <h1>{run.config.name}</h1>
          <p>
            {run.config.agents} agents · {run.config.rounds} fixed rounds ·
            Random matching · Seed {run.config.seed}
          </p>
        </div>
        <div className="run-controls">
          {running ? (
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => void onControl("pause")}
            >
              <Pause size={16} />
              Pause
            </button>
          ) : (
            <>
              <button
                className="button secondary"
                disabled={!canRun}
                onClick={() => void onControl("step")}
              >
                <SkipForward size={16} />
                Step round
              </button>
              <button
                className="button primary"
                disabled={!canRun}
                onClick={() => void onControl("start")}
              >
                <Play size={16} />
                {run.status === "paused" ? "Resume" : "Start run"}
              </button>
            </>
          )}
          {!finished && (
            <button
              className="button stop-button"
              disabled={busy}
              onClick={() => setConfirmStop(true)}
              title="Stop experiment"
            >
              <Square size={14} />
              <span>Stop</span>
            </button>
          )}
        </div>
      </div>
      {confirmStop && (
        <div className="notice warning stop-confirm" role="alert">
          <span>
            <strong>Stop this experiment?</strong> Saved results remain
            available. A stopped run cannot be resumed.
          </span>
          <button
            className="button danger small"
            onClick={() => {
              setConfirmStop(false);
              void onControl("stop");
            }}
          >
            Stop experiment
          </button>
          <button
            className="button secondary small"
            onClick={() => setConfirmStop(false)}
          >
            Cancel
          </button>
        </div>
      )}
      {run.config.mode === "demo" && (
        <div className="run-mode-note">
          <FlaskConical size={16} />
          <span>
            <strong>Scripted demo.</strong> Decisions come from fixed
            strategies, not language models. API spending is zero.
          </span>
        </div>
      )}
      {run.config.mode === "openrouter" && !keyConfigured && !finished && (
        <div className="notice warning">
          <span>
            Add your OpenRouter API key before starting this experiment.
          </span>
          <button className="text-button" onClick={onSettings}>
            Open API Settings
            <ArrowRight size={15} />
          </button>
        </div>
      )}
      {health && !health.docker_available && (
        <div className="capability-note">
          <ShieldCheck size={15} />
          <span>
            Docker is unavailable. Isolated Python execution is unavailable;
            file tools and game interactions remain available. There is no host
            execution fallback.
          </span>
        </div>
      )}
      {run.error && (
        <div className="notice error" role="alert">
          <strong>Run needs attention</strong>
          <span>{run.error}</span>
        </div>
      )}
      {run.usage.unknown_cost_requests > 0 && (
        <UsageReconciliation run={run} onReconcile={onReconcile} />
      )}
      {(run.usage.reserved_usd ?? 0) > 0 && (
        <p className="field-hint budget-reservation">
          Budget reserved for calls in progress:{" "}
          {currency(run.usage.reserved_usd ?? 0)}. This is a reservation, not a
          confirmed charge.
        </p>
      )}
      <div className="metrics-grid">
        <Metric
          icon={<Users size={18} />}
          label="Population"
          value={String(run.config.agents)}
          detail={`${run.config.group1_count} collective · ${run.config.agents - run.config.group1_count} individual`}
        />
        <Metric
          icon={<Activity size={18} />}
          label="Cooperation rate"
          value={
            visibleMatches.length
              ? `${Math.round((100 * cooperations) / (visibleMatches.length * 2))}%`
              : "—"
          }
          detail={`Across ${visibleMatches.length * 2} settled actions through round ${round}`}
        />
        <Metric
          icon={<Network size={18} />}
          label="Total game payoff"
          value={visibleMatches.length ? String(payoff) : "—"}
          detail={`All agents · through round ${round}`}
        />
        <Metric
          icon={<Wallet size={18} />}
          label="Recorded API cost"
          value={currency(run.usage.cost_usd)}
          detail={`${run.usage.requests} calls · ${currency(run.config.budget_usd)} run budget`}
        />
      </div>
      <nav className="run-tabs" aria-label="Experiment views">
        {(
          [
            { id: "overview", label: "Overview", icon: Network },
            { id: "forum", label: "Forum", icon: MessageSquare },
            { id: "inspector", label: "Agent Inspector", icon: Search },
            { id: "results", label: "Results & Export", icon: ArrowDownToLine },
          ] as const
        ).map((item) => (
          <button
            key={item.id}
            aria-current={tab === item.id ? "page" : undefined}
            className={tab === item.id ? "selected" : ""}
            onClick={() => setTab(item.id)}
          >
            <item.icon size={16} />
            {item.label}
            {item.id === "forum" && run.forum.length > 0 && (
              <span>{run.forum.length}</span>
            )}
          </button>
        ))}
      </nav>
      <div className="round-bar">
        <div>
          <span className={running ? "pulse-dot" : "status-dot paused"} />
          <strong>
            Round {round}
            <span> / {run.config.rounds}</span>
          </strong>
          <span className="phase-label">
            {followLatest && running
              ? run.phase.replaceAll("_", " ")
              : round <= run.round
                ? "Settled game records"
                : "Awaiting decisions"}
          </span>
        </div>
        <div className="round-controls">
          <label htmlFor="round-slider">Review round</label>
          <input
            id="round-slider"
            type="range"
            min={1}
            max={latestRound}
            value={round}
            onChange={(event) => {
              setFollowLatest(false);
              setHistoricalRound(Number(event.target.value));
            }}
            disabled={latestRound === 1}
          />
          <button
            className={followLatest ? "latest-button active" : "latest-button"}
            onClick={() => setFollowLatest(true)}
          >
            {running ? "Follow live" : "Latest"}
          </button>
        </div>
      </div>
      {tab === "overview" && (
        <div className="run-grid">
          <section className="panel interaction-panel">
            <div className="panel-header">
              <div>
                <h2>Interaction network</h2>
                <p>Pairings and revealed actions in round {round}.</p>
              </div>
              <span className="badge neutral">Researcher view</span>
            </div>
            <InteractionGraph
              run={run}
              round={round}
              selectedAgent={selectedAgent}
              onSelectAgent={chooseAgent}
            />
            <div className="network-footer">
              <span>
                <span className="dot group-1" />
                Group 1 · Collective
              </span>
              <span>
                <span className="dot group-2" />
                Group 2 · Individual
              </span>
              <small>Select an agent to inspect its record.</small>
            </div>
          </section>
          <section className="panel forum-panel">
            <div className="panel-header">
              <div>
                <h2>Public forum</h2>
                <p>
                  {run.config.forum_enabled
                    ? "Discussion follows game settlement."
                    : "Disabled for this experiment."}
                </p>
              </div>
              <MessageSquare size={18} />
            </div>
            <ForumView
              messages={run.forum.filter((post) => post.round === round)}
              agents={run.agents}
              enabled={run.config.forum_enabled}
              round={round}
              compact
            />
            <div className="panel-bottom">
              <button className="text-button" onClick={() => setTab("forum")}>
                Open discussion history
                <ArrowRight size={14} />
              </button>
            </div>
          </section>
          <section className="panel payoff-panel">
            <div className="panel-header">
              <div>
                <h2>Cumulative payoff</h2>
                <p>Group totals calculated from settled matches.</p>
              </div>
              <span className="badge neutral">Through round {round}</span>
            </div>
            <PayoffChart run={run} round={round} />
          </section>
          <section className="panel conditions-panel">
            <div className="panel-header">
              <div>
                <h2>Information conditions</h2>
                <p>Access configured for this experiment.</p>
              </div>
              <Settings2 size={18} />
            </div>
            <Condition label="Personal match history" enabled />
            <Condition
              label="Public forum"
              enabled={run.config.forum_enabled}
            />
            <Condition
              label="Global game history"
              enabled={run.config.global_history_enabled}
            />
            <Condition
              label="Web search & reading"
              enabled={run.config.internet_enabled}
            />
            <Condition
              label="Private objective score"
              enabled={run.config.group_score_visible}
            />
            <div className="condition-footnote">
              <ShieldCheck size={14} />
              <span>
                Group labels and private objectives are hidden from peers.
              </span>
            </div>
          </section>
          <section className="panel matches-panel">
            <div className="panel-header">
              <div>
                <h2>Round {round} match ledger</h2>
                <p>All decisions are collected before results are revealed.</p>
              </div>
              <span className="badge neutral">
                {currentMatches.length} settled matches
              </span>
            </div>
            <MatchTable matches={currentMatches} />
          </section>
        </div>
      )}
      {tab === "forum" && (
        <section className="panel full-forum">
          <div className="panel-header">
            <div>
              <h2>Discussion history</h2>
              <p>
                Posts and replies through round {round}. Agent statements are
                separate from the verified match ledger.
              </p>
            </div>
            <span className="badge neutral">
              {run.forum.filter((post) => post.round <= round).length} messages
            </span>
          </div>
          <ForumView
            messages={run.forum.filter((post) => post.round <= round)}
            agents={run.agents}
            enabled={run.config.forum_enabled}
            round={round}
          />
        </section>
      )}
      {tab === "inspector" && (
        <Inspector
          run={run}
          selectedAgent={selectedAgent}
          onSelect={setSelectedAgent}
          round={round}
        />
      )}
      {tab === "results" && (
        <ResultsView run={run} round={round} onExport={onExport} />
      )}
    </div>
  );
}

function Condition({ label, enabled }: { label: string; enabled: boolean }) {
  return (
    <div className="condition">
      <span>{label}</span>
      <span className={enabled ? "condition-on" : "condition-off"}>
        {enabled ? "Enabled" : "Off"}
        {enabled && <Check size={12} />}
      </span>
    </div>
  );
}

function UsageReconciliation({
  run,
  onReconcile,
}: {
  run: Experiment;
  onReconcile: (confirmedCost: number, note: string) => Promise<void>;
}) {
  const [cost, setCost] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await onReconcile(Number(cost), note.trim());
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="reconciliation-panel">
      <summary>
        <Wallet size={16} />
        <span>
          {run.usage.unknown_cost_requests} call
          {run.usage.unknown_cost_requests === 1 ? "" : "s"} without confirmed
          cost
        </span>
        <strong>Reconcile Usage</strong>
        <ChevronRight size={15} />
      </summary>
      <div className="reconciliation-content">
        <p>
          Inspect your OpenRouter activity before continuing. Enter the verified{" "}
          <strong>total cost of this experiment</strong>, including previously
          recorded calls and any uncertain charges. Your note is saved in the
          experiment audit log.
        </p>
        <a
          href="https://openrouter.ai/activity"
          target="_blank"
          rel="noreferrer"
          className="external-link"
        >
          Open OpenRouter activity ↗
        </a>
        {error && (
          <div className="notice error" role="alert">
            {error}
          </div>
        )}
        <form onSubmit={submit}>
          <label className="field">
            Verified total cost (USD)
            <input
              type="number"
              min={run.usage.cost_usd}
              step="any"
              required
              value={cost}
              onChange={(event) => setCost(event.target.value)}
              placeholder={`At least ${run.usage.cost_usd.toFixed(6)}`}
              disabled={busy || run.status === "running"}
            />
          </label>
          <label className="field">
            Verification note
            <input
              required
              minLength={3}
              maxLength={1000}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="How did you verify this total?"
              disabled={busy || run.status === "running"}
            />
          </label>
          <button
            className="button secondary"
            disabled={busy || run.status === "running"}
            type="submit"
          >
            {busy ? "Saving…" : "Confirm reconciled total"}
          </button>
        </form>
        {run.status === "running" && (
          <p className="field-hint">
            Pause the experiment before reconciling its usage.
          </p>
        )}
      </div>
    </details>
  );
}

function MatchTable({ matches }: { matches: Experiment["matches"] }) {
  if (matches.length === 0)
    return (
      <div className="empty-state compact">
        <Network size={25} />
        <p>No settled matches in this selection.</p>
        <small>
          Submitted actions stay hidden until every paired agent has decided.
        </small>
      </div>
    );
  return (
    <div className="table-scroll">
      <table className="match-table">
        <thead>
          <tr>
            <th>Round</th>
            <th>Agent</th>
            <th>Action</th>
            <th>Payoff</th>
            <th>Opponent</th>
            <th>Action</th>
            <th>Payoff</th>
          </tr>
        </thead>
        <tbody>
          {matches.map((match) => (
            <tr key={`${match.round}-${match.a}-${match.b}`}>
              <td className="muted">{match.round}</td>
              <td>
                <strong>{match.a}</strong>
              </td>
              <td>
                <ActionBadge action={match.action_a} />
              </td>
              <td className="number-cell">+{match.payoff_a}</td>
              <td>
                <strong>{match.b}</strong>
              </td>
              <td>
                <ActionBadge action={match.action_b} />
              </td>
              <td className="number-cell">+{match.payoff_b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function ActionBadge({ action }: { action: "C" | "D" }) {
  return (
    <span className={`action-badge ${action === "C" ? "cooperate" : "defect"}`}>
      {action === "C" ? "C · Cooperate" : "D · Defect"}
    </span>
  );
}

function ForumView({
  messages,
  agents,
  enabled,
  round,
  compact = false,
}: {
  messages: ForumMessage[];
  agents: Agent[];
  enabled: boolean;
  round: number;
  compact?: boolean;
}) {
  if (!enabled)
    return (
      <div className="empty-state forum-empty">
        <span className="empty-small-icon">
          <MessageSquare size={27} />
        </span>
        <h3>A private-history baseline</h3>
        <p>
          The public forum is turned off.
          <br />
          Enable it when creating another experiment to study communication.
        </p>
        <span className="badge neutral">Forum disabled</span>
      </div>
    );
  if (messages.length === 0)
    return (
      <div className="empty-state forum-empty">
        <span className="empty-small-icon">
          <MessageSquare size={27} />
        </span>
        <h3>No messages yet</h3>
        <p>
          Discussion happens after game settlement.
          <br />
          Agents may also choose not to post.
        </p>
        <span className="badge neutral">Round {round}</span>
      </div>
    );
  const ids = new Set(messages.map((post) => post.id));
  const roots = messages.filter(
    (post) => !post.parent_id || !ids.has(post.parent_id),
  );
  const groupOf = (agentId: string) =>
    agents.find((agent) => agent.id === agentId)?.group ?? 1;
  const rendered = new Set<string>();
  function renderPost(post: ForumMessage, reply = false): ReactNode {
    if (rendered.has(post.id)) return null;
    rendered.add(post.id);
    const children = messages.filter(
      (candidate) =>
        candidate.parent_id === post.id && candidate.id !== post.id,
    );
    return (
      <article
        className={`forum-message ${reply ? "is-reply" : ""}`}
        key={post.id}
      >
        <div className={`agent-avatar group-${groupOf(post.agent_id)}`}>
          {post.agent_id.replace(/[^0-9]/g, "").slice(-2) ||
            post.agent_id.slice(-2)}
        </div>
        <div className="message-main">
          <div className="message-meta">
            <strong>{post.agent_id}</strong>
            <span>Round {post.round}</span>
            {reply && <span className="reply-marker">Reply</span>}
          </div>
          <p>{post.content}</p>
          {children.map((child) => renderPost(child, true))}
        </div>
      </article>
    );
  }
  return (
    <div className={`forum-messages ${compact ? "compact-forum" : ""}`}>
      {roots.map((post) => renderPost(post, !!post.parent_id))}
      {messages
        .filter((post) => !rendered.has(post.id))
        .map((post) => renderPost(post))}
    </div>
  );
}

function Inspector({
  run,
  selectedAgent,
  onSelect,
  round,
}: {
  run: Experiment;
  selectedAgent: string;
  onSelect: (id: string) => void;
  round: number;
}) {
  const agent =
    run.agents.find((candidate) => candidate.id === selectedAgent) ??
    run.agents[0];
  const [showAll, setShowAll] = useState(false);
  const [kindFilter, setKindFilter] = useState("");
  const events = run.events.filter(
    (event) =>
      event.agent_id === agent?.id &&
      event.round <= round &&
      (!kindFilter || event.kind === kindFilter),
  );
  const kinds = Array.from(
    new Set(
      run.events
        .filter((event) => event.agent_id === agent?.id)
        .map((event) => event.kind),
    ),
  );
  const visibleEvents = [...(showAll ? events : events.slice(-100))].reverse();
  if (!agent)
    return (
      <div className="empty-state">
        <p>No agents are available.</p>
      </div>
    );
  const privateMatches = run.matches.filter(
    (match) =>
      match.round <= round && (match.a === agent.id || match.b === agent.id),
  );
  const payoff = privateMatches.reduce(
    (total, match) =>
      total + (match.a === agent.id ? match.payoff_a : match.payoff_b),
    0,
  );
  return (
    <div className="inspector-layout">
      <section className="panel agent-list-panel">
        <div className="panel-header">
          <div>
            <h2>Agents</h2>
            <p>Researcher-only identities.</p>
          </div>
        </div>
        <div className="agent-list">
          {run.agents.map((candidate) => (
            <button
              className={
                candidate.id === agent.id
                  ? "agent-list-item selected"
                  : "agent-list-item"
              }
              key={candidate.id}
              onClick={() => {
                onSelect(candidate.id);
                setKindFilter("");
                setShowAll(false);
              }}
            >
              <span className={`agent-avatar group-${candidate.group}`}>
                {candidate.id.replace(/[^0-9]/g, "").slice(-2) ||
                  candidate.id.slice(-2)}
              </span>
              <span>
                <strong>{candidate.id}</strong>
                <small>Group {candidate.group}</small>
              </span>
              <ChevronRight size={15} />
            </button>
          ))}
        </div>
      </section>
      <div className="inspector-details">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>{agent.id}</h2>
              <p>
                {agent.group === 1
                  ? "Collective objective"
                  : "Individual objective"}{" "}
                · Group {agent.group}
              </p>
            </div>
            <span className={`badge ${agent.group === 1 ? "teal" : "indigo"}`}>
              {payoff} payoff through round {round}
            </span>
          </div>
          <div className="agent-detail-content">
            <div className="detail-row">
              <span>Model</span>
              <strong>
                {run.config.mode === "demo"
                  ? "Deterministic scripted strategy"
                  : agent.model}
              </strong>
            </div>
            <div className="detail-row">
              <span>Settled matches</span>
              <strong>{privateMatches.length}</strong>
            </div>
            <div className="objective-box">
              <span className="eyebrow">PRIVATE OBJECTIVE</span>
              <p>
                {agent.group === 1
                  ? run.config.group1_prompt
                  : run.config.group2_prompt}
              </p>
            </div>
          </div>
        </section>
        <section className="panel event-panel">
          <div className="panel-header">
            <div>
              <h2>Observation & tool trace</h2>
              <p>Recorded inputs, outputs, and tool activity for this agent.</p>
            </div>
            <label className="event-filter">
              <span className="sr-only">Filter events</span>
              <select
                value={kindFilter}
                onChange={(event) => setKindFilter(event.target.value)}
              >
                <option value="">All event types</option>
                {kinds.map((kind) => (
                  <option key={kind} value={kind}>
                    {kind.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="trace-note">
            Private records are visible to the researcher. Hidden model
            reasoning is not available.
          </p>
          {visibleEvents.length === 0 ? (
            <div className="empty-state compact">
              <Search size={25} />
              <p>No matching events have been recorded.</p>
            </div>
          ) : (
            <div className="event-list">
              {visibleEvents.map((event, index) => (
                <details
                  className="event"
                  key={event.id || `${event.kind}-${index}`}
                >
                  <summary>
                    <span className="event-kind">
                      {event.kind.replaceAll("_", " ")}
                    </span>
                    <span className="event-round">
                      Round {event.round} · {event.phase}
                    </span>
                    <span className="event-time">
                      {event.time
                        ? new Date(event.time).toLocaleTimeString()
                        : ""}
                    </span>
                    <ChevronRight size={14} />
                  </summary>
                  <pre>{JSON.stringify(event.data, null, 2)}</pre>
                </details>
              ))}
            </div>
          )}
          {events.length > 100 && !showAll && (
            <button
              className="text-button show-events"
              onClick={() => setShowAll(true)}
            >
              Showing the latest 100 of {events.length} events. Show all.
            </button>
          )}
        </section>
      </div>
    </div>
  );
}

function ResultsView({
  run,
  round,
  onExport,
}: {
  run: Experiment;
  round: number;
  onExport: (format: "json" | "csv") => Promise<void>;
}) {
  const matches = run.matches.filter((match) => match.round <= round);
  return (
    <div className="results-layout">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Results & provenance</h2>
            <p>
              Exports include the entire saved run, regardless of the round
              selected above.
            </p>
          </div>
          <div className="export-buttons">
            <button
              className="button secondary small"
              onClick={() => void onExport("csv")}
            >
              <ArrowDownToLine size={15} />
              Match CSV
            </button>
            <button
              className="button primary small"
              onClick={() => void onExport("json")}
            >
              <ArrowDownToLine size={15} />
              Full JSON
            </button>
          </div>
        </div>
        <div className="results-summary">
          <div>
            <span>Execution mode</span>
            <strong>
              {run.config.mode === "demo"
                ? "Scripted demo — not LLM evidence"
                : "OpenRouter models"}
            </strong>
          </div>
          <div>
            <span>Settled game rounds</span>
            <strong>
              {run.round} / {run.config.rounds}
            </strong>
          </div>
          <div>
            <span>Recorded model calls</span>
            <strong>{run.usage.requests}</strong>
          </div>
          <div>
            <span>Input / output tokens</span>
            <strong>
              {run.usage.input_tokens.toLocaleString()} /{" "}
              {run.usage.output_tokens.toLocaleString()}
            </strong>
          </div>
          <div>
            <span>Recorded API cost</span>
            <strong>{currency(run.usage.cost_usd)}</strong>
          </div>
          <div>
            <span>Calls without confirmed cost</span>
            <strong>{run.usage.unknown_cost_requests || 0}</strong>
          </div>
        </div>
        {run.status !== "completed" && (
          <p className="notice warning result-notice">
            This run is {run.status}. Its export is a partial record, not a
            completed experiment.
          </p>
        )}
        <p className="export-note">
          JSON preserves configuration, groups, observations, messages, events,
          and results. API keys are excluded. Pairing seeds reproduce
          environment randomness, not identical model outputs.
        </p>
      </section>
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Agent outcomes</h2>
            <p>Computed from settled matches through round {round}.</p>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Agent</th>
                <th>Group</th>
                <th>Matches</th>
                <th>Cooperation</th>
                <th>Total payoff</th>
                <th>Payoff / match</th>
              </tr>
            </thead>
            <tbody>
              {run.agents.map((agent) => {
                const own = matches.filter(
                  (match) => match.a === agent.id || match.b === agent.id,
                );
                const sum = own.reduce(
                  (total, match) =>
                    total +
                    (match.a === agent.id ? match.payoff_a : match.payoff_b),
                  0,
                );
                const cooperation = own.filter(
                  (match) =>
                    (match.a === agent.id ? match.action_a : match.action_b) ===
                    "C",
                ).length;
                return (
                  <tr key={agent.id}>
                    <td>
                      <strong>{agent.id}</strong>
                    </td>
                    <td>
                      <span className={`dot group-${agent.group}`} />
                      Group {agent.group}
                    </td>
                    <td>{own.length}</td>
                    <td>
                      {own.length
                        ? `${Math.round((cooperation / own.length) * 100)}%`
                        : "—"}
                    </td>
                    <td>{sum}</td>
                    <td>{own.length ? (sum / own.length).toFixed(2) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Match ledger</h2>
            <p>
              Game outcomes through round {round}; byes are not counted as
              matches.
            </p>
          </div>
        </div>
        <MatchTable matches={matches} />
      </section>
      <details className="panel config-details">
        <summary>
          Saved experiment configuration
          <ChevronRight size={16} />
        </summary>
        <pre>{JSON.stringify(run.config, null, 2)}</pre>
      </details>
    </div>
  );
}

function SettingsView({
  token,
  keyConfigured,
  onKeyChange,
  health,
  user,
  onLogout,
}: {
  token: string;
  keyConfigured: boolean;
  onKeyChange: (configured: boolean) => void;
  health: Health | null;
  user: User;
  onLogout: () => Promise<void>;
}) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  async function save(value: string) {
    setBusy(true);
    setError("");
    setSaved("");
    try {
      await request("/settings/key", token, {
        method: "PUT",
        body: JSON.stringify({ api_key: value.trim() }),
      });
      onKeyChange(!!value.trim());
      setKey("");
      setSaved(
        value.trim()
          ? "Your key is configured for this server session."
          : "Your key has been removed.",
      );
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page-content settings-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">PERSONAL CONNECTION</span>
          <h1>API Settings</h1>
          <p>Connect your own account for live model experiments.</p>
        </div>
      </div>
      <section className="panel settings-card">
        <div className="panel-header">
          <div className="settings-provider">
            <span className="provider-icon">
              <KeyRound size={22} />
            </span>
            <div>
              <h2>OpenRouter</h2>
              <p>One connection, separate model choices for each group.</p>
            </div>
          </div>
          <span className={`badge ${keyConfigured ? "teal" : "neutral"}`}>
            {keyConfigured ? "Key configured" : "Not configured"}
          </span>
        </div>
        <div className="settings-content">
          {error && (
            <div className="notice error" role="alert">
              {error}
            </div>
          )}
          {saved && (
            <div className="notice success" role="status">
              <Check size={17} />
              {saved}
            </div>
          )}
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void save(key);
            }}
          >
            <label className="field">
              OpenRouter API key
              <input
                type="password"
                autoComplete="off"
                spellCheck={false}
                placeholder={
                  keyConfigured
                    ? "Enter a replacement key"
                    : "Enter your OpenRouter API key"
                }
                value={key}
                onChange={(event) => {
                  setKey(event.target.value);
                  setSaved("");
                }}
                required
              />
            </label>
            <p className="field-hint">
              The key stays in server memory for your account and clears when
              the server restarts. It is not saved in the browser, agent
              workspaces, or experiment exports.
            </p>
            <div className="settings-actions">
              <button
                type="submit"
                className="button primary"
                disabled={busy || !key.trim()}
              >
                {busy
                  ? "Saving…"
                  : keyConfigured
                    ? "Replace key"
                    : "Save API key"}
                <ArrowRight size={16} />
              </button>
              {keyConfigured && (
                <button
                  type="button"
                  className="button secondary"
                  disabled={busy}
                  onClick={() => void save("")}
                >
                  Remove key
                </button>
              )}
              <a
                className="external-link"
                href="https://openrouter.ai/settings/keys"
                target="_blank"
                rel="noreferrer"
              >
                Manage keys on OpenRouter ↗
              </a>
            </div>
          </form>
        </div>
      </section>
      <div className="settings-lower">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Researcher account</h2>
              <p>Experiments and credentials are scoped to this account.</p>
            </div>
            <Users size={18} />
          </div>
          <div className="settings-content">
            <div className="detail-row">
              <span>Username</span>
              <strong>{user.username}</strong>
            </div>
            <div className="detail-row">
              <span>Data location</span>
              <strong>Local application server</strong>
            </div>
            <div className="detail-row">
              <span>Experiment access</span>
              <strong>Your account only</strong>
            </div>
            <button
              className="button secondary small"
              onClick={() => void onLogout()}
            >
              <LogOut size={14} />
              Sign out
            </button>
          </div>
        </section>
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Execution capabilities</h2>
              <p>Web access is separate from offline code execution.</p>
            </div>
            <ShieldCheck size={18} />
          </div>
          <div className="settings-content">
            <Condition label="Local backend" enabled={!!health} />
            <Condition
              label="Docker code sandbox"
              enabled={health?.docker_available ?? false}
            />
            <p className="field-hint">
              Start Docker to enable isolated Python execution. The application
              never runs agent code directly on your computer. Web tools are
              configured per experiment.
            </p>
          </div>
        </section>
      </div>
      <div className="workflow-note">
        <Wallet size={18} />
        <span>
          Model usage and web searches may incur charges on your OpenRouter
          account. Set a budget for each experiment. Calls already in progress
          can still be billed after a pause or budget stop.
        </span>
      </div>
    </div>
  );
}
