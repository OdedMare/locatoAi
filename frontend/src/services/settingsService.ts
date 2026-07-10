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
