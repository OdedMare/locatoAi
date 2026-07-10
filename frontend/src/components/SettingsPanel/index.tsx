"use client";

import { useEffect, useState } from "react";
import { getSettings, updateSettings } from "@/services/settingsService";
import type { AppSettings } from "@/types/settings";

interface SettingsPanelProps {
  onClose: () => void;
}

/**
 * Settings modal: LLM (API key / model / base URL) and catalog database
 * (Postgres URL / layers table). Saved values persist on the backend and
 * apply immediately — the catalog status line confirms the DB connection.
 */
export default function SettingsPanel({ onClose }: SettingsPanelProps) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [apiKey, setApiKey] = useState(""); // empty = keep existing
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [databaseUrl, setDatabaseUrl] = useState("");
  const [layersTable, setLayersTable] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    getSettings()
      .then((s) => {
        setSettings(s);
        setModel(s.llm_model);
        setBaseUrl(s.llm_base_url ?? "");
        setDatabaseUrl(s.database_url);
        setLayersTable(s.layers_table);
      })
      .catch(() => setMessage("Could not load settings — is the backend running?"));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const saved = await updateSettings({
        llm_model: model,
        llm_base_url: baseUrl.trim() === "" ? null : baseUrl.trim(),
        openai_api_key: apiKey, // backend ignores empty
        database_url: databaseUrl,
        layers_table: layersTable,
      });
      setSettings(saved);
      setApiKey("");
      setMessage("Saved ✓");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div
        className="settings-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Settings"
      >
        <header className="settings-header">
          <h2>Settings</h2>
          <button type="button" className="settings-close" onClick={onClose}>
            ✕
          </button>
        </header>

        <section className="settings-section">
          <h3>AI model</h3>
          <label className="field-label" htmlFor="set-api-key">
            OpenAI API key
            {settings?.openai_api_key_set && (
              <span className="key-hint"> (saved {settings.openai_api_key_hint})</span>
            )}
          </label>
          <input
            id="set-api-key"
            type="password"
            className="settings-input"
            placeholder={settings?.openai_api_key_set ? "Leave empty to keep current key" : "sk-…"}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <label className="field-label" htmlFor="set-model">Model</label>
          <input
            id="set-model"
            className="settings-input"
            placeholder="gpt-3.5-turbo"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
          <label className="field-label" htmlFor="set-base-url">
            Base URL <span className="optional">(optional — for OpenAI-compatible servers)</span>
          </label>
          <input
            id="set-base-url"
            className="settings-input"
            placeholder="https://api.openai.com/v1"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
          />
        </section>

        <section className="settings-section">
          <h3>Layer catalog (Postgres)</h3>
          <label className="field-label" htmlFor="set-db-url">Database URL</label>
          <input
            id="set-db-url"
            className="settings-input"
            placeholder="postgresql://localhost:5432/gis"
            value={databaseUrl}
            onChange={(e) => setDatabaseUrl(e.target.value)}
          />
          <label className="field-label" htmlFor="set-table">Layers table</label>
          <input
            id="set-table"
            className="settings-input"
            placeholder="public.layers"
            value={layersTable}
            onChange={(e) => setLayersTable(e.target.value)}
          />
          {settings && (
            <p className={`catalog-status ${settings.catalog.ok ? "ok" : "bad"}`}>
              {settings.catalog.ok
                ? `✓ Connected — ${settings.catalog.layer_count} layers found`
                : `✗ ${settings.catalog.error}`}
            </p>
          )}
        </section>

        <footer className="settings-footer">
          {message && <span className="settings-message">{message}</span>}
          <button
            type="button"
            className="run-query-button settings-save"
            onClick={handleSave}
            disabled={saving || settings === null}
          >
            {saving ? "Saving…" : "Save settings"}
          </button>
        </footer>
      </div>
    </div>
  );
}
