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
  const [databaseUser, setDatabaseUser] = useState("");
  const [databasePassword, setDatabasePassword] = useState("");
  const [databaseHost, setDatabaseHost] = useState("");
  const [databasePort, setDatabasePort] = useState("");
  const [databaseName, setDatabaseName] = useState("");
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
        setDatabaseUser(s.database_user);
        setDatabaseHost(s.database_host);
        setDatabasePort(s.database_port?.toString() ?? "");
        setDatabaseName(s.database_name);
        setLayersTable(s.layers_table);
      })
      .catch(() => setMessage("לא ניתן לטעון את ההגדרות — האם השרת פועל?"));
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
        database_user: databaseUser.trim(),
        database_password: databasePassword, // backend ignores empty
        database_host: databaseHost.trim(),
        database_port: databasePort.trim() ? Number(databasePort) : null,
        database_name: databaseName.trim(),
        layers_table: layersTable,
      });
      setSettings(saved);
      setApiKey("");
      setDatabasePassword("");
      setMessage("נשמר ✓");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "השמירה נכשלה");
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
        aria-label="הגדרות"
      >
        <header className="settings-header">
          <h2>הגדרות</h2>
          <button type="button" className="settings-close" onClick={onClose}>
            ✕
          </button>
        </header>

        <section className="settings-section">
          <h3>מודל בינה מלאכותית</h3>
          <label className="field-label" htmlFor="set-api-key">
            מפתח API{" "}
            <span className="optional">(לא נדרש לשרתים מקומיים כמו Ollama)</span>
            {settings?.openai_api_key_set && (
              <span className="key-hint"> (נשמר {settings.openai_api_key_hint})</span>
            )}
          </label>
          <input
            id="set-api-key"
            dir="ltr"
            type="password"
            className="settings-input"
            placeholder={settings?.openai_api_key_set ? "השאירו ריק כדי לשמור את המפתח הנוכחי" : "sk-… (אופציונלי)"}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <label className="field-label" htmlFor="set-model">מודל</label>
          <input
            id="set-model"
            dir="ltr"
            className="settings-input"
            placeholder="gemma4:31b-cloud"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
          <label className="field-label" htmlFor="set-base-url">
            כתובת בסיס{" "}
            <span className="optional">(שרת תואם OpenAI; ריק = OpenAI)</span>
          </label>
          <input
            id="set-base-url"
            dir="ltr"
            className="settings-input"
            placeholder="http://pghost:11434/v1"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
          />
        </section>

        <section className="settings-section">
          <h3>קטלוג שכבות (PostgreSQL)</h3>
          <label className="field-label" htmlFor="set-db-url">
            כתובת חיבור מלאה <span className="optional">(ברירת מחדל לשדות הריקים)</span>
          </label>
          <input
            id="set-db-url"
            dir="ltr"
            className="settings-input"
            placeholder="postgresql://localhost:5432/gis"
            value={databaseUrl}
            onChange={(e) => setDatabaseUrl(e.target.value)}
          />
          <div className="settings-input-row">
            <div>
              <label className="field-label" htmlFor="set-db-host">שרת</label>
              <input
                id="set-db-host"
                dir="ltr"
                className="settings-input"
                placeholder="localhost"
                value={databaseHost}
                onChange={(e) => setDatabaseHost(e.target.value)}
              />
            </div>
            <div>
              <label className="field-label" htmlFor="set-db-port">פורט</label>
              <input
                id="set-db-port"
                dir="ltr"
                type="number"
                min="1"
                max="65535"
                className="settings-input"
                placeholder="5432"
                value={databasePort}
                onChange={(e) => setDatabasePort(e.target.value)}
              />
            </div>
          </div>
          <label className="field-label" htmlFor="set-db-name">שם מסד הנתונים</label>
          <input
            id="set-db-name"
            dir="ltr"
            className="settings-input"
            placeholder="gis"
            value={databaseName}
            onChange={(e) => setDatabaseName(e.target.value)}
          />
          <div className="settings-input-row">
            <div>
              <label className="field-label" htmlFor="set-db-user">שם משתמש</label>
              <input
                id="set-db-user"
                dir="ltr"
                className="settings-input"
                autoComplete="username"
                placeholder="postgres"
                value={databaseUser}
                onChange={(e) => setDatabaseUser(e.target.value)}
              />
            </div>
            <div>
              <label className="field-label" htmlFor="set-db-password">
                סיסמה
                {settings?.database_password_set && (
                  <span className="key-hint"> (נשמרה)</span>
                )}
              </label>
              <input
                id="set-db-password"
                dir="ltr"
                type="password"
                className="settings-input"
                autoComplete="current-password"
                placeholder={settings?.database_password_set ? "השאירו ריק כדי לשמור" : "סיסמה"}
                value={databasePassword}
                onChange={(e) => setDatabasePassword(e.target.value)}
              />
            </div>
          </div>
          <label className="field-label" htmlFor="set-table">טבלת שכבות</label>
          <input
            id="set-table"
            dir="ltr"
            className="settings-input"
            placeholder="public.layers"
            value={layersTable}
            onChange={(e) => setLayersTable(e.target.value)}
          />
          {settings && (
            <p className={`catalog-status ${settings.catalog.ok ? "ok" : "bad"}`}>
              {settings.catalog.ok
                ? `✓ מחובר — נמצאו ${settings.catalog.layer_count} שכבות`
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
            {saving ? "שומר…" : "שמירת הגדרות"}
          </button>
        </footer>
      </div>
    </div>
  );
}
