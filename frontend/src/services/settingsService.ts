import type { AppSettings, SettingsUpdate } from "@/types/settings";
import { request } from "@/services/api";

export async function getSettings(): Promise<AppSettings> {
  return request<AppSettings>("/api/settings");
}

export async function updateSettings(
  update: SettingsUpdate
): Promise<AppSettings> {
  return request<AppSettings>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(update),
  });
}

/**
 * List models from the provider. Pass the CURRENT form values so the
 * check tests what the user typed, before saving (empty key = saved key).
 */
export async function getModels(overrides?: {
  llm_base_url?: string;
  openai_api_key?: string;
}): Promise<string[]> {
  const body = await request<{ models?: unknown }>("/api/models", {
    method: "POST",
    body: JSON.stringify(overrides ?? {}),
  });
  return Array.isArray(body.models) ? body.models : [];
}
