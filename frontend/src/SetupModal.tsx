import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  ArrowRight,
  ChevronDown,
  FlaskConical,
  Globe2,
  MessageSquare,
  ShieldCheck,
  SlidersHorizontal,
  X,
} from "lucide-react";
import type { ExperimentConfig, ModelInfo } from "./types";

interface Props {
  defaults: ExperimentConfig;
  models: ModelInfo[];
  modelError: string;
  keyConfigured: boolean;
  busy: boolean;
  error: string;
  onClose: () => void;
  onCreate: (config: ExperimentConfig) => void;
}

export default function SetupModal({
  defaults,
  models,
  modelError,
  keyConfigured,
  busy,
  error,
  onClose,
  onCreate,
}: Props) {
  const [config, setConfig] = useState<ExperimentConfig>({
    ...defaults,
    name: defaults.name || "Cooperation baseline",
  });
  const dialog = useRef<HTMLDialogElement>(null);
  const set = <K extends keyof ExperimentConfig>(
    key: K,
    value: ExperimentConfig[K],
  ) => setConfig((current) => ({ ...current, [key]: value }));
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  function submit(event: FormEvent) {
    event.preventDefault();
    onCreate(config);
  }

  return (
    <dialog
      ref={dialog}
      className="setup-dialog"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      aria-labelledby="setup-title"
    >
      <div className="dialog-top">
        <div>
          <span className="eyebrow">EXPERIMENT DESIGN</span>
          <h2 id="setup-title">Create an experiment</h2>
          <p>Define the population, objectives, and information conditions.</p>
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close experiment setup"
          disabled={busy}
        >
          <X size={20} />
        </button>
      </div>
      <form onSubmit={submit}>
        <div className="dialog-content">
          {error && (
            <div className="notice error" role="alert">
              {error}
            </div>
          )}
          <section className="form-section">
            <div className="section-heading">
              <FlaskConical size={18} />
              <h3>Experiment basics</h3>
            </div>
            <label className="field">
              Experiment name
              <input
                autoFocus
                required
                maxLength={120}
                value={config.name}
                onChange={(event) => set("name", event.target.value)}
                placeholder="e.g. Public discussion baseline"
              />
            </label>
            <fieldset className="mode-picker">
              <legend>Execution mode</legend>
              <label
                className={
                  config.mode === "demo"
                    ? "mode-option selected"
                    : "mode-option"
                }
              >
                <input
                  type="radio"
                  name="mode"
                  value="demo"
                  checked={config.mode === "demo"}
                  onChange={() => set("mode", "demo")}
                />
                <span>
                  <strong>Scripted demo</strong>
                  <small>
                    Validate the workflow with deterministic strategies. No LLM
                    calls or charges.
                  </small>
                </span>
                <span className="badge neutral">Free</span>
              </label>
              <label
                className={
                  config.mode === "openrouter"
                    ? "mode-option selected"
                    : "mode-option"
                }
              >
                <input
                  type="radio"
                  name="mode"
                  value="openrouter"
                  checked={config.mode === "openrouter"}
                  onChange={() => set("mode", "openrouter")}
                />
                <span>
                  <strong>OpenRouter experiment</strong>
                  <small>
                    Run real models using your own API key and experiment
                    budget.
                  </small>
                </span>
                <span className="badge teal">Live models</span>
              </label>
            </fieldset>
            {config.mode === "openrouter" && !keyConfigured && (
              <p className="notice warning">
                No API key is configured. You can create this experiment, then
                add your key in API Settings before running it.
              </p>
            )}
            <div className="form-grid four">
              <NumberField
                label="Agents"
                value={config.agents}
                min={2}
                max={100}
                onChange={(value) =>
                  setConfig((current) => ({
                    ...current,
                    agents: value,
                    group1_count: Math.min(current.group1_count, value - 1),
                  }))
                }
              />
              <NumberField
                label="Group 1 agents"
                value={config.group1_count}
                min={1}
                max={config.agents - 1}
                onChange={(value) => set("group1_count", value)}
              />
              <NumberField
                label="Rounds"
                value={config.rounds}
                min={1}
                max={200}
                onChange={(value) => set("rounds", value)}
              />
              <NumberField
                label="Pairing seed"
                value={config.seed}
                min={0}
                max={2147483647}
                onChange={(value) => set("seed", value)}
              />
            </div>
            <p className="field-hint">
              Group 2 has {Math.max(0, config.agents - config.group1_count)}{" "}
              agents. Group membership is hidden from peers. An odd population
              leaves one agent unpaired each round.
            </p>
          </section>

          <section className="form-section">
            <div className="section-heading">
              <SlidersHorizontal size={18} />
              <h3>Group objectives & models</h3>
            </div>
            <div className="group-cards">
              <div className="group-card group-one">
                <span className="dot group-1" />
                <strong>Group 1 · Collective objective</strong>
                <p>
                  Maximize the cumulative payoff of the designated group, whose
                  other members are unknown.
                </p>
              </div>
              <div className="group-card group-two">
                <span className="dot group-2" />
                <strong>Group 2 · Individual objective</strong>
                <p>
                  Maximize personal cumulative payoff. Other Group 2 agents do
                  not share this objective score.
                </p>
              </div>
            </div>
            <div className="form-grid">
              <label className="field">
                Group 1 model
                <input
                  list="model-options"
                  placeholder="Choose or enter an OpenRouter model ID"
                  value={config.model_group1}
                  onChange={(event) => set("model_group1", event.target.value)}
                  disabled={config.mode === "demo"}
                  required={config.mode === "openrouter"}
                />
              </label>
              <label className="field">
                Group 2 model
                <input
                  list="model-options"
                  placeholder="Choose or enter an OpenRouter model ID"
                  value={config.model_group2}
                  onChange={(event) => set("model_group2", event.target.value)}
                  disabled={config.mode === "demo"}
                  required={config.mode === "openrouter"}
                />
              </label>
            </div>
            <datalist id="model-options">
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </datalist>
            {config.mode === "openrouter" && modelError && (
              <p className="field-hint warning-text">
                Model catalog unavailable: {modelError} You can enter a model ID
                manually.
              </p>
            )}
            <p className="field-hint">
              Use the same model in both groups to isolate the objective
              difference. Changing both model and objective creates a combined
              intervention.
            </p>
          </section>

          <section className="form-section">
            <div className="section-heading">
              <ShieldCheck size={18} />
              <h3>Information conditions</h3>
            </div>
            <p className="section-description">
              Personal match history is always available. Each additional source
              is independent.
            </p>
            <Toggle
              checked={config.forum_enabled}
              onChange={(value) => set("forum_enabled", value)}
              icon={<MessageSquare size={18} />}
              title="Public forum"
              description="Allow posts and replies after settlement, before the next round."
            />
            <Toggle
              checked={config.global_history_enabled}
              onChange={(value) => set("global_history_enabled", value)}
              icon={<FlaskConical size={18} />}
              title="Global game history"
              description="Allow access to all settled matches. Hidden groups and objectives stay private."
            />
            <Toggle
              checked={config.internet_enabled}
              onChange={(value) => set("internet_enabled", value)}
              icon={<Globe2 size={18} />}
              title="Internet access"
              description="Enable web search and page reading. Code execution remains offline."
            />
            <Toggle
              checked={config.group_score_visible}
              onChange={(value) => set("group_score_visible", value)}
              icon={<ShieldCheck size={18} />}
              title="Private objective score"
              description="Also reveal the agent's objective score, including Group 1's aggregate payoff."
            />
          </section>

          <details className="advanced-settings">
            <summary>
              <span>
                <SlidersHorizontal size={17} /> Prompts, limits & parameters
              </span>
              <ChevronDown size={17} />
            </summary>
            <div className="advanced-content">
              <div className="form-grid three">
                <NumberField
                  label="Budget (USD)"
                  value={config.budget_usd}
                  min={0.01}
                  max={1000}
                  step={0.01}
                  onChange={(value) => set("budget_usd", value)}
                />
                <NumberField
                  label="Temperature"
                  value={config.temperature}
                  min={0}
                  max={2}
                  step={0.1}
                  onChange={(value) => set("temperature", value)}
                />
                <label className="field">
                  Reasoning effort
                  <select
                    value={config.reasoning_effort ?? ""}
                    onChange={(event) =>
                      set(
                        "reasoning_effort",
                        (event.target.value ||
                          null) as ExperimentConfig["reasoning_effort"],
                      )
                    }
                  >
                    <option value="">Model default</option>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </label>
                <NumberField
                  label="Output token limit"
                  value={config.max_tokens}
                  min={64}
                  max={32768}
                  onChange={(value) => set("max_tokens", value)}
                />
                <NumberField
                  label="Tool calls per turn"
                  value={config.tool_limit}
                  min={1}
                  max={50}
                  onChange={(value) => set("tool_limit", value)}
                />
                <NumberField
                  label="Turn timeout (seconds)"
                  value={config.turn_timeout}
                  min={5}
                  max={600}
                  onChange={(value) => set("turn_timeout", value)}
                />
                <NumberField
                  label="Code timeout (seconds)"
                  value={config.code_timeout}
                  min={1}
                  max={60}
                  onChange={(value) => set("code_timeout", value)}
                />
              </div>
              <p className="field-hint">
                Reasoning effort is model-dependent. Budget checks stop new
                calls; requests already in flight may still incur costs.
              </p>
              <label className="field">
                Common prompt
                <textarea
                  rows={5}
                  value={config.common_prompt}
                  onChange={(event) => set("common_prompt", event.target.value)}
                />
              </label>
              <label className="field">
                Group 1 private objective
                <textarea
                  rows={4}
                  value={config.group1_prompt}
                  onChange={(event) => set("group1_prompt", event.target.value)}
                />
              </label>
              <label className="field">
                Group 2 private objective
                <textarea
                  rows={4}
                  value={config.group2_prompt}
                  onChange={(event) => set("group2_prompt", event.target.value)}
                />
              </label>
              <p className="field-hint">
                Prompts are preserved with the run. Editing them can change the
                experimental conditions. Engine rules and access permissions
                remain enforced.
              </p>
            </div>
          </details>
          <div className="payoff-reference">
            <strong>Prisoner's Dilemma payoffs</strong>
            <span>
              C/C <b>3, 3</b>
            </span>
            <span>
              C/D <b>0, 5</b>
            </span>
            <span>
              D/C <b>5, 0</b>
            </span>
            <span>
              D/D <b>1, 1</b>
            </span>
          </div>
        </div>
        <div className="dialog-footer">
          <p>Creating an experiment does not start model calls.</p>
          <button
            type="button"
            className="button secondary"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button className="button primary" type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create experiment"}
            <ArrowRight size={16} />
          </button>
        </div>
      </form>
    </dialog>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="field">
      {label}
      <input
        type="number"
        required
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.valueAsNumber || 0)}
      />
    </label>
  );
}

function Toggle({
  title,
  description,
  checked,
  onChange,
  icon,
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  icon: ReactNode;
}) {
  return (
    <label className="toggle-row">
      <span className="toggle-icon">{icon}</span>
      <span className="toggle-copy">
        <strong>{title}</strong>
        <small>{description}</small>
      </span>
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="switch-track" aria-hidden="true" />
    </label>
  );
}
