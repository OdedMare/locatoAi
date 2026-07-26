import type { AppSettings, SettingsUpdate } from "@/types/settings";

export async function getSettings(): Promise<AppSettings> {
  const res = await fetch("/api/settings");
  if (!res.ok) throw new Error(`טעינת ההגדרות נכשלה (${res.status})`);
  return res.json();
}

export async function updateSettings(
  update: SettingsUpdate
): Promise<AppSettings> {
  const res = await fetch("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `שמירת ההגדרות נכשלה (${res.status})`);
  }
  return res.json();
}

/**
 * List models from the provider. Pass the CURRENT form values so the
 * check tests what the user typed, before saving (empty key = saved key).
 */
export async function getModels(overrides?: {
  llm_base_url?: string;
  openai_api_key?: string;
}): Promise<string[]> {
  const res = await fetch("/api/models", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(overrides ?? {}),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `טעינת המודלים נכשלה (${res.status})`);
  }
  const body = await res.json();
  return Array.isArray(body.models) ? body.models : [];
}
