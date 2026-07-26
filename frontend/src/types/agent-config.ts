export type AgentContentKind = "prompt" | "skill";

export interface AgentContent {
  id: string;
  title: string;
  kind: AgentContentKind;
  content: string;
  is_custom: boolean;
  is_overridden: boolean;
}

export interface AgentConfig {
  prompts: AgentContent[];
  skills: AgentContent[];
}
