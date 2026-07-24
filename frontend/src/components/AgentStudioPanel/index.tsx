"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, Plus, Save, Sparkles, Wrench } from "lucide-react";
import {
  createAgentSkill,
  getAgentConfig,
  updateAgentContent,
} from "@/services/agentConfigService";
import type { AgentConfig, AgentContent } from "@/types/agent-config";

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

export default function AgentStudioPanel({ onClose }: AgentStudioPanelProps) {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [activeKey, setActiveKey] = useState("");
  const [draft, setDraft] = useState("");
  const [skillTitle, setSkillTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const allItems = useMemo(
    () => config ? [...config.prompts, ...config.skills] : [],
    [config]
  );
  const activeItem = allItems.find((item) => itemKey(item) === activeKey) ?? null;
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
        setMessage(error instanceof Error ? error.message : "הטעינה נכשלה");
      });
  }, []);

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
      setMessage("נשמר. השינוי יחול בבקשת הסוכן הבאה ✓");
    } catch (error) {
      console.error("Agent configuration save failed", error);
      setMessage(error instanceof Error ? error.message : "השמירה נכשלה");
    } finally {
      setSaving(false);
    }
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
        aria-label="Agent Studio"
      >
        <header className="settings-header agent-studio-header">
          <div>
            <h2><Sparkles size={18} /> Agent Studio</h2>
            <p>ניהול ההוראות והמיומנויות שהסוכן קורא בזמן אמת</p>
          </div>
          <button type="button" className="settings-close" onClick={handleClose}>✕</button>
        </header>

        <div className="agent-studio-body">
          <aside className="agent-content-nav">
            <button type="button" className="add-layer-toggle" onClick={startSkill}>
              <Plus size={15} /> מיומנות חדשה
            </button>
            {config ? (
              <>
                {renderItems("PROMPTS", config.prompts)}
                {renderItems("SKILLS", config.skills)}
              </>
            ) : (
              <p className="panel-placeholder" dir="auto">
                {message ?? "טוען את הגדרות הסוכן…"}
              </p>
            )}
          </aside>

          <main className="agent-content-editor">
            {(activeItem || creating) ? (
              <>
                <div className="agent-editor-title">
                  <div>
                    <span>{creating ? "SKILL חדש" : activeItem?.kind.toUpperCase()}</span>
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
                <textarea
                  className="agent-content-textarea"
                  dir="ltr"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  spellCheck={false}
                  aria-label="תוכן ההוראה"
                />
                <p className="agent-editor-note">
                  תוכן מיומנות מותאמת נטען רק כשה-planner מבקש אותה לפי Use when.
                  מיומנויות מרכיבות פעולות קיימות; tool חדש עדיין דורש backend ובדיקות.
                </p>
                {message && <p className="settings-message" dir="auto">{message}</p>}
              </>
            ) : (
              <p className="panel-placeholder" dir="auto">
                {message ?? "בחרו prompt או skill לעריכה."}
              </p>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
