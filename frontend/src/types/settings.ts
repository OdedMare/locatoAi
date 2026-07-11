/** Mirrors backend/app/service/settings_router.py — keep in sync. */

export interface CatalogStatus {
  ok: boolean;
  layer_count: number | null;
  error: string | null;
}

export interface AppSettings {
  llm_model: string;
  llm_base_url: string | null;
  openai_api_key_set: boolean;
  /** Masked hint like "…abcd" — the real key is never sent back. */
  openai_api_key_hint: string | null;
  database_url: string;
  database_user: string;
  database_password_set: boolean;
  database_host: string;
  database_port: number | null;
  database_name: string;
  layers_table: string;
  catalog: CatalogStatus;
}

/** Partial update; empty/omitted api key keeps the existing one. */
export interface SettingsUpdate {
  llm_model?: string;
  llm_base_url?: string | null;
  openai_api_key?: string;
  database_url?: string;
  database_user?: string;
  database_password?: string;
  database_host?: string;
  database_port?: number;
  database_name?: string;
  layers_table?: string;
}
