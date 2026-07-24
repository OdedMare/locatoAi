"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2, FileText, LoaderCircle, Plus, RefreshCw, Save, Sparkles,
  TriangleAlert, Wrench, X,
} from "lucide-react";
import {
  createAgentSkill,
  getAgentConfig,
  updateAgentContent,
} from "@/services/agentConfigService";
import { getLayerFields, getLayers } from "@/services/catalogService";
import type { AgentConfig, AgentContent } from "@/types/agent-config";
import type { CatalogLayer } from "@/types/catalog";

interface AgentStudioPanelProps {
  onClose: () => void;
}

const SKILL_TEMPLATE = `# \`new-skill\`

**Use when:** Describe exactly when the planner should use this skill.

**Do not use when:** Describe the closest cases where another skill is better.

**Compose:** Name the existing operations and their dependency order.

Describe semantic constraints using layer/schema roles. Do not hard-code layer ids,
step ids, provider names, field names, or operation defaults.
`;

const itemKey = (item: AgentContent) => `${item.kind}:${item.id}`;
const kindLabel = (kind: AgentContent["kind"] | undefined) => (
  kind === "prompt" ? "הנחיית מערכת" : "מיומנות"
);
const friendlyError = (error: unknown, fallback: string) => {
  if (!(error instanceof Error)) return fallback;
  const message = error.message.toLowerCase();
  if (message.includes("not found") || message.includes("(404)")) {
    return "תוכן הסוכן עדיין לא זמין בסביבה הזו.";
  }
  if (message.includes("unauthorized") || message.includes("(401)")) {
    return "אין הרשאה לגשת לתוכן הסוכן.";
  }
  return error.message || fallback;
};

export default function AgentStudioPanel({ onClose }: AgentStudioPanelProps) {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [activeKey, setActiveKey] = useState("");
  const [draft, setDraft] = useState("");
  const [skillTitle, setSkillTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [layers, setLayers] = useState<CatalogLayer[]>([]);
  const [fieldLayerId, setFieldLayerId] = useState("");
  const [layerFields, setLayerFields] = useState<string[]>([]);
  const [fieldName, setFieldName] = useState("");
  const [fieldsLoading, setFieldsLoading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const allItems = useMemo(
    () => config ? [...config.prompts, ...config.skills] : [],
    [config]
  );
  const activeItem = allItems.find((item) => itemKey(item) === activeKey) ?? null;
  const canBindField = creating || Boolean(activeItem?.is_custom);
  const dirty = creating
    ? draft !== SKILL_TEMPLATE || skillTitle.trim().length > 0
    : activeItem !== null && draft !== activeItem.content;

  useEffect(() => {
    getAgentConfig()
      .then((loaded) => {
        setConfig(loaded);
        const first = loaded.prompts[0] ?? loaded.skills[0];
        if (first) {
          setActiveKey(itemKey(first));
          setDraft(first.content);
        }
      })
      .catch((error) => {
        console.error("Agent configuration loading failed", error);
        setMessage(friendlyError(error, "לא ניתן לטעון את תוכן הסוכן."));
      });
  }, [loadAttempt]);

  useEffect(() => {
    getLayers()
      .then((result) => setLayers(result.layers))
      .catch((error) => console.error("Agent layer loading failed", error));
  }, [loadAttempt]);

  useEffect(() => {
    if (!fieldLayerId) return;
    let active = true;
    getLayerFields(fieldLayerId)
      .then((result) => {
        if (!active) return;
        setLayerFields(result.fields);
        setFieldName(result.fields[0] ?? "");
      })
      .catch((error) => {
        if (!active) return;
        console.error("Agent layer schema loading failed", error);
        setLayerFields([]);
        setFieldName("");
        setMessage(friendlyError(error, "טעינת שדות השכבה נכשלה."));
      })
      .finally(() => {
        if (active) setFieldsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [fieldLayerId]);

  const retryLoad = () => {
    setConfig(null);
    setMessage(null);
    setLoadAttempt((attempt) => attempt + 1);
  };

  const canLeaveDraft = () => (
    !dirty || window.confirm("יש שינויים שלא נשמרו. להמשיך בלעדיהם?")
  );

  const handleClose = () => {
    if (canLeaveDraft()) onClose();
  };

  const selectItem = (item: AgentContent) => {
    if (!canLeaveDraft()) return;
    setCreating(false);
    setActiveKey(itemKey(item));
    setDraft(item.content);
    setMessage(null);
  };

  const startSkill = () => {
    if (!canLeaveDraft()) return;
    setCreating(true);
    setActiveKey("");
    setSkillTitle("");
    setDraft(SKILL_TEMPLATE);
    setMessage(null);
  };

  const replaceItem = (saved: AgentContent) => {
    setConfig((current) => current && ({
      ...current,
      [saved.kind === "prompt" ? "prompts" : "skills"]:
        (saved.kind === "prompt" ? current.prompts : current.skills)
          .map((item) => itemKey(item) === itemKey(saved) ? saved : item),
    }));
  };

  const save = async () => {
    if ((!activeItem && !creating) || !draft.trim()) return;
    setSaving(true);
    setMessage(null);
    try {
      if (creating) {
        const saved = await createAgentSkill(skillTitle, draft);
        setConfig((current) => current && ({
          ...current, skills: [...current.skills, saved],
        }));
        setCreating(false);
        setActiveKey(itemKey(saved));
        setDraft(saved.content);
      } else if (activeItem) {
        const saved = await updateAgentContent(activeItem, draft);
        replaceItem(saved);
        setDraft(saved.content);
      }
      setMessage("נשמר. השינוי יחול בבקשת הסוכן הבאה.");
    } catch (error) {
      console.error("Agent configuration save failed", error);
      setMessage(friendlyError(error, "שמירת התוכן נכשלה."));
    } finally {
      setSaving(false);
    }
  };

  const insertFieldReference = () => {
    if (!fieldLayerId || !fieldName) return;
    const token = `@field[${encodeURIComponent(fieldLayerId)}/${encodeURIComponent(fieldName)}]`;
    const textarea = textareaRef.current;
    const start = textarea?.selectionStart ?? draft.length;
    const end = textarea?.selectionEnd ?? start;
    setDraft(draft.slice(0, start) + token + draft.slice(end));
    window.requestAnimationFrame(() => {
      textarea?.focus();
      textarea?.setSelectionRange(start + token.length, start + token.length);
    });
  };

  const renderItems = (title: string, items: AgentContent[]) => (
    <section className="agent-studio-group">
      <h3>{title} <span>{items.length}</span></h3>
      {items.map((item) => (
        <button
          type="button"
          key={itemKey(item)}
          className={`agent-content-item ${activeKey === itemKey(item) ? "active" : ""}`}
          onClick={() => selectItem(item)}
        >
          {item.kind === "prompt" ? <FileText size={15} /> : <Wrench size={15} />}
          <span>{item.title}</span>
          {(item.is_custom || item.is_overridden) && <small>נערך</small>}
        </button>
      ))}
    </section>
  );

  return (
    <div className="settings-overlay" onClick={handleClose}>
      <div
        className="settings-card agent-studio-card"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="agent-studio-title"
      >
        <header className="settings-header agent-studio-header">
          <div className="settings-title">
            <span className="settings-title-icon"><Sparkles size={20} /></span>
            <div>
              <h2 id="agent-studio-title">סטודיו לסוכן</h2>
              <p>עריכת ההנחיות והמיומנויות שהסוכן קורא בזמן אמת</p>
            </div>
          </div>
          <div className="agent-studio-header-actions">
            <span className={`agent-draft-state${dirty ? " dirty" : ""}`}>
              {dirty ? "שינויים לא נשמרו" : <><CheckCircle2 size={14} /> מעודכן</>}
            </span>
            <button type="button" className="settings-close" onClick={handleClose} aria-label="סגירת סטודיו לסוכן">
              <X size={20} />
            </button>
          </div>
        </header>

        <div className="agent-studio-body">
          <aside className="agent-content-nav">
            <div className="agent-nav-heading">
              <strong>תוכן הסוכן</strong>
              <small>בחרו פריט לעריכה</small>
            </div>
            <button type="button" className="add-layer-toggle" onClick={startSkill}>
              <Plus size={15} /> מיומנות חדשה
            </button>
            {config ? (
              <>
                {renderItems("הנחיות מערכת", config.prompts)}
                {renderItems("מיומנויות", config.skills)}
              </>
            ) : (
              <div className={`agent-load-state${message ? " error" : ""}`}>
                {message
                  ? <TriangleAlert size={17} />
                  : <LoaderCircle className="spin" size={17} />}
                <span>{message ? "התוכן לא נטען" : "טוען את תוכן הסוכן…"}</span>
              </div>
            )}
          </aside>

          <main className="agent-content-editor">
            {(activeItem || creating) ? (
              <>
                <div className="agent-editor-title">
                  <div>
                    <span>{creating ? "מיומנות חדשה" : kindLabel(activeItem?.kind)}</span>
                    <h3>{creating ? "יצירת מיומנות" : activeItem?.title}</h3>
                  </div>
                  <button
                    type="button"
                    className="run-query-button agent-save-button"
                    onClick={save}
                    disabled={saving || !draft.trim() || (creating && !skillTitle.trim())}
                  >
                    <Save size={15} /> {saving ? "שומר…" : "שמירה"}
                  </button>
                </div>
                {creating && (
                  <input
                    className="settings-input"
                    value={skillTitle}
                    onChange={(event) => setSkillTitle(event.target.value)}
                    placeholder="שם המיומנות"
                    aria-label="שם המיומנות"
                    autoFocus
                  />
                )}
                {canBindField && (
                  <div className="agent-field-picker">
                    <select
                      className="settings-input"
                      value={fieldLayerId}
                      onChange={(event) => {
                        setFieldLayerId(event.target.value);
                        setLayerFields([]);
                        setFieldName("");
                        setFieldsLoading(Boolean(event.target.value));
                      }}
                      aria-label="בחירת שכבה לקישור שדה"
                    >
                      <option value="">בחירת שכבה…</option>
                      {layers.map((layer) => (
                        <option key={layer.id} value={layer.id}>{layer.name}</option>
                      ))}
                    </select>
                    <select
                      className="settings-input"
                      value={fieldName}
                      onChange={(event) => setFieldName(event.target.value)}
                      disabled={!fieldLayerId || fieldsLoading}
                      aria-label="בחירת שדה מהשכבה"
                    >
                      <option value="">
                        {fieldsLoading ? "טוען שדות…" : "בחירת שדה…"}
                      </option>
                      {layerFields.map((field) => (
                        <option key={field} value={field}>{field}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="agent-insert-field"
                      onClick={insertFieldReference}
                      disabled={!fieldLayerId || !fieldName || fieldsLoading}
                    >
                      הוספת ‎@שדה
                    </button>
                  </div>
                )}
                <textarea
                  ref={textareaRef}
                  className="agent-content-textarea"
                  dir="ltr"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  spellCheck={false}
                  aria-label="תוכן ההוראה"
                />
                <p className="agent-editor-note">
                  מיומנות מותאמת נטענת רק כאשר בונה התוכנית מזהה שהיא מתאימה לבקשה.
                  קישור ‎@שדה נשמר לפי מזהה שכבה ושם שדה ונבדק מול ה־schema בעת השמירה.
                  המיומנויות מרכיבות פעולות קיימות; כלי חדש עדיין דורש מימוש בצד השרת ובדיקות.
                </p>
                {message && <p className="settings-message" role="status" dir="auto">{message}</p>}
              </>
            ) : (
              <div className="agent-empty-state">
                {message ? <TriangleAlert size={26} /> : <LoaderCircle className="spin" size={26} />}
                <strong>{message ? "תוכן הסוכן אינו זמין" : "טוען את תוכן הסוכן"}</strong>
                <p className="panel-placeholder" dir="auto">
                  {message ?? "ההנחיות והמיומנויות יופיעו כאן בעוד רגע."}
                </p>
                {message && (
                  <button type="button" className="agent-retry-button" onClick={retryLoad}>
                    <RefreshCw size={15} /> ניסיון נוסף
                  </button>
                )}
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
