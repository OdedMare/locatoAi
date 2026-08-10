import type { AgentConfig, AgentContent } from "@/types/agent-config";
import { request } from "@/services/api";

export async function getAgentConfig(): Promise<AgentConfig> {
  return request<AgentConfig>("/api/agent-config", { cache: "no-store" });
}

export async function updateAgentContent(
  item: AgentContent, content: string
): Promise<AgentContent> {
  const path = [
    "/api/agent-config",
    encodeURIComponent(item.kind),
    encodeURIComponent(item.id),
  ].join("/");
  return request<AgentContent>(path, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

export async function createAgentSkill(
  title: string, content: string
): Promise<AgentContent> {
  return request<AgentContent>("/api/agent-config/skills", {
    method: "POST",
    body: JSON.stringify({ title, content }),
  });
}
