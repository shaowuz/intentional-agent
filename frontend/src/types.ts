export interface ExperimentConfig {
  name: string;
  agents: number;
  group1_count: number;
  rounds: number;
  seed: number;
  mode: "demo" | "openrouter";
  model_group1: string;
  model_group2: string;
  temperature: number;
  reasoning_effort: "low" | "medium" | "high" | null;
  max_tokens: number;
  tool_limit: number;
  turn_timeout: number;
  code_timeout: number;
  budget_usd: number;
  forum_enabled: boolean;
  global_history_enabled: boolean;
  internet_enabled: boolean;
  group_score_visible: boolean;
  common_prompt: string;
  group1_prompt: string;
  group2_prompt: string;
}

export interface Agent {
  id: string;
  group: 1 | 2;
  model: string;
  payoff: number;
  matches: number;
  cooperations: number;
}

export interface Match {
  round: number;
  a: string;
  b: string;
  action_a: "C" | "D";
  action_b: "C" | "D";
  payoff_a: number;
  payoff_b: number;
}

export interface ForumMessage {
  id: string;
  round: number;
  agent_id: string;
  content: string;
  parent_id: string | null;
  stage: string;
}

export interface RunEvent {
  id: string;
  time: string;
  kind: string;
  agent_id?: string | null;
  round: number;
  phase: string;
  data: unknown;
}

export interface Experiment {
  id: string;
  config: ExperimentConfig;
  status: string;
  round: number;
  phase: string;
  agents: Agent[];
  matches: Match[];
  forum: ForumMessage[];
  events: RunEvent[];
  usage: {
    cost_usd: number;
    requests: number;
    input_tokens: number;
    output_tokens: number;
    unknown_cost_requests: number;
    estimated_in_flight_usd?: number;
    reserved_usd?: number;
  };
  pending: {
    round?: number;
    pairs?: string[][];
    byes?: string[];
    decisions?: Record<string, unknown>;
    [key: string]: unknown;
  } | null;
  error: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ExperimentSummary {
  id: string;
  name: string;
  status: string;
  round: number;
  rounds: number;
  mode: "demo" | "openrouter";
  created_at: string;
  updated_at: string;
  cost_usd: number;
  error: string | null;
}

export interface ModelInfo {
  id: string;
  name: string;
  context_length: number;
  supported_parameters: string[];
  pricing: Record<string, string>;
}

export interface Health {
  status: string;
  docker_available: boolean;
  version: string;
}

export interface User {
  id: string;
  username: string;
}
