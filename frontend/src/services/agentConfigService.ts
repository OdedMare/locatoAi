import type { AgentConfig, AgentContent } from "@/types/agent-config";

async function responseJson<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `${fallback} (${res.status})`);
  }
  return res.json();
}

export async function getAgentConfig(): Promise<AgentConfig> {
  const res = await fetch("/api/agent-config", { cache: "no-store" });
  return responseJson(res, "טעינת הגדרות הסוכן נכשלה");
}

export async function updateAgentContent(
  item: AgentContent, content: string
): Promise<AgentContent> {
  const path = [
    "/api/agent-config",
    encodeURIComponent(item.kind),
    encodeURIComponent(item.id),
  ].join("/");
  const res = await fetch(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  return responseJson(res, "שמירת התוכן נכשלה");
}

export async function createAgentSkill(
  title: string, content: string
): Promise<AgentContent> {
  const res = await fetch("/api/agent-config/skills", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, content }),
  });
  return responseJson(res, "יצירת המיומנות נכשלה");
}
