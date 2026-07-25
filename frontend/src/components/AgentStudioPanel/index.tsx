"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDown, ArrowUp, CheckCircle2, FileText, GitFork, ListOrdered, LoaderCircle,
  MapPinned, Plus, RefreshCw, Save, Sparkles, Trash2, TriangleAlert, Wrench, X,
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

const SUMMARY_SKILL_TEMPLATE = `# \`summary-workflow\`

**Use when:** The user asks to determine a target, run an ordered series of checks around it, and return one evidence-backed summary.

**Do not use when:** One direct query or one existing operation fully answers the request.

## Summary target

Determine the summary target: the request polygon, the latest place where a friend was observed, or a location produced by an earlier step.

## Workflow

1. Determine the summary target from the request and available evidence.
2. Check relevant static information inside the target.
3. [parallel] Check movement, presence, and encounters related to the target.
4. [parallel] Check events and recommendations near the target.
5. Summarize the results and identify failed layers or missing information.

## Summary rules

Never invent a layer, field, entity, time, or relationship. When the target is an
entity's latest location, use the schema's entity and time roles. Steps marked
[parallel] are independent and may run concurrently; wait for all of them before
the next sequential step. Continue after an isolated failure and mark partial coverage.
Write the final user-facing summary in Hebrew.
`;

const AREA_SUMMARY_NAME = /סיכום\s+(?:של\s+)?תא\s+שטח|summari[sz]e[-_ ]area|area[-_ ]summary/i;
const SUMMARY_NAME = /סיכום|summary|summari[sz](?:e|ing|ation)/i;
const SUMMARY_TARGET = /^##\s+(?:יעד הסיכום|summary target)\s*$/i;
const SUMMARY_WORKFLOW = /^##\s+(?:שלבי העבודה|שלבים|workflow)\s*$/i;
const AREA_SUMMARY_EXAMPLES = [
  { text: "נמצאו 2 מבנים מסוג בניין.", source: "שכבת מבנים" },
  { text: "עודד ביקר כאן במהלך 24 השעות האחרונות.", source: "שכבת חברים" },
  { text: "נמצאה כאן המלצת Google Maps ששמר עודד.", source: "שכבת המלצות" },
  { text: "בשעה 14:00 עודד ומשה שהו כאן יחד.", source: "שכבת חברים" },
];

interface SummaryStep {
  text: string;
  parallel: boolean;
}

const sectionBounds = (content: string, heading: RegExp) => {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const start = lines.findIndex((line) => heading.test(line.trim()));
  const next = start < 0
    ? -1
    : lines.findIndex((line, index) => index > start && /^##\s+/.test(line));
  return { lines, start, end: next < 0 ? lines.length : next };
};

const summaryTarget = (content: string) => {
  const { lines, start, end } = sectionBounds(content, SUMMARY_TARGET);
  return start < 0
    ? ""
    : lines.slice(start + 1, end).map((line) => line.trim()).filter(Boolean).join(" ");
};

const summarySteps = (content: string) => {
  const { lines, start, end } = sectionBounds(content, SUMMARY_WORKFLOW);
  if (start < 0) return [];
  return lines.slice(start + 1, end).flatMap((line) => {
    const match = line.match(/^\s*\d+\.\s*(.*)$/);
    if (!match) return [];
    const parallel = /^\[(?:parallel|במקביל)\]\s*/i.test(match[1]);
    return [{
      text: match[1].replace(/^\[(?:parallel|במקביל)\]\s*/i, ""),
      parallel,
    }];
  });
};

const withSummaryTarget = (content: string, target: string) => {
  const { lines, start, end } = sectionBounds(content, SUMMARY_TARGET);
  const block = ["## Summary target", "", target, ""];
  if (start >= 0) return [...lines.slice(0, start), ...block, ...lines.slice(end)].join("\n");
  return `${content.trimEnd()}\n\n${block.join("\n")}`;
};

const withSummarySteps = (content: string, steps: SummaryStep[]) => {
  const { lines, start, end } = sectionBounds(content, SUMMARY_WORKFLOW);
  const block = [
    "## Workflow", "",
    ...steps.map((step, index) => (
      `${index + 1}. ${step.parallel ? "[parallel] " : ""}${step.text}`
    )),
  ];
  if (start >= 0) {
    const suffix = lines.slice(end);
    if (suffix.length && suffix[0].startsWith("## ")) block.push("");
    return [...lines.slice(0, start), ...block, ...suffix].join("\n");
  }
  return `${content.trimEnd()}\n\n${block.join("\n")}\n`;
};

function SummaryWorkflowEditor({
  target,
  steps,
  onTargetChange,
  onChange,
}: {
  target: string;
  steps: SummaryStep[];
  onTargetChange: (target: string) => void;
  onChange: (steps: SummaryStep[]) => void;
}) {
  const commit = (next: SummaryStep[]) => {
    onChange(next.map((step, index) => (
      index === 0 ? { ...step, parallel: false } : step
    )));
  };
  const updateStep = (index: number, value: string) => {
    commit(steps.map((step, position) => (
      position === index ? { ...step, text: value } : step
    )));
  };
  const moveStep = (index: number, offset: number) => {
    const moved = [...steps];
    [moved[index], moved[index + offset]] = [moved[index + offset], moved[index]];
    commit(moved);
  };

  return (
    <section className="agent-workflow-editor" aria-labelledby="summary-workflow-title">
      <header>
        <span className="agent-workflow-icon" aria-hidden="true">
          <ListOrdered size={18} />
        </span>
        <div>
          <h4 id="summary-workflow-title">תבנית הסיכום</h4>
          <p>הגדירו מה מסכמים, ואז ערכו את סדר הבדיקות.</p>
        </div>
        <button
          type="button"
          className="agent-workflow-add"
          onClick={() => commit([...steps, { text: "שלב חדש", parallel: false }])}
        >
          <Plus size={16} /> הוספת שלב
        </button>
      </header>
      <label className="agent-summary-target" htmlFor="summary-workflow-target">
        <span>יעד הסיכום</span>
        <input
          id="summary-workflow-target"
          value={target}
          onChange={(event) => onTargetChange(event.target.value)}
          placeholder="למשל: המקום האחרון שבו חבר נצפה"
          dir="auto"
        />
      </label>
      <ol>
        {steps.map((step, index) => (
          <li key={index}>
            <label htmlFor={`summary-workflow-step-${index}`}>
              <span>שלב {index + 1}</span>
              <input
                id={`summary-workflow-step-${index}`}
                value={step.text}
                onChange={(event) => updateStep(index, event.target.value)}
                dir="auto"
              />
            </label>
            <div className="agent-workflow-actions">
              <button
                type="button"
                onClick={() => moveStep(index, -1)}
                disabled={index === 0}
                aria-label={`העברת שלב ${index + 1} למעלה`}
              >
                <ArrowUp size={16} />
              </button>
              <button
                type="button"
                onClick={() => moveStep(index, 1)}
                disabled={index === steps.length - 1}
                aria-label={`העברת שלב ${index + 1} למטה`}
              >
                <ArrowDown size={16} />
              </button>
              <button
                type="button"
                className={`agent-parallel-toggle${step.parallel ? " active" : ""}`}
                onClick={() => commit(steps.map((item, position) => (
                  position === index
                    ? { ...item, parallel: !item.parallel }
                    : item
                )))}
                disabled={index === 0}
                aria-pressed={step.parallel}
                aria-label={`הרצת שלב ${index + 1} במקביל לשלב הקודם`}
                title="במקביל לשלב הקודם"
              >
                <GitFork size={16} />
                <span>{step.parallel ? "במקביל" : "סדרתי"}</span>
              </button>
              <button
                type="button"
                onClick={() => commit(steps.filter((_, position) => position !== index))}
                aria-label={`מחיקת שלב ${index + 1}`}
              >
                <Trash2 size={16} />
              </button>
            </div>
          </li>
        ))}
      </ol>
      {!steps.length && (
        <p className="agent-workflow-empty">
          אין שלבים עדיין. לחצו על “הוספת שלב” כדי להתחיל.
        </p>
      )}
    </section>
  );
}

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
  const summaryWorkflow = (
    creating || activeItem?.kind === "skill"
  ) && SUMMARY_NAME.test(
    `${skillTitle} ${activeItem?.title ?? ""} ${draft}`
  );
  const showAreaSummaryExamples = AREA_SUMMARY_NAME.test(
    `${skillTitle} ${activeItem?.title ?? ""} ${draft}`
  );
  const target = useMemo(() => summaryTarget(draft), [draft]);
  const workflowSteps = useMemo(() => summarySteps(draft), [draft]);
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

  const applyTemplate = (title: string, content: string) => {
    const untouched = draft === SKILL_TEMPLATE || draft === SUMMARY_SKILL_TEMPLATE;
    if (!untouched && !window.confirm("להחליף את תוכן הטיוטה בתבנית שנבחרה?")) return;
    setSkillTitle(title);
    setDraft(content);
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
                  <>
                    <label className="agent-skill-title" htmlFor="agent-skill-title">
                      <span>שם המיומנות</span>
                      <input
                        id="agent-skill-title"
                        className="settings-input"
                        value={skillTitle}
                        onChange={(event) => setSkillTitle(event.target.value)}
                        placeholder="שם המיומנות"
                        autoFocus
                      />
                    </label>
                    <section className="agent-skill-templates" aria-labelledby="skill-template-title">
                      <div>
                        <strong id="skill-template-title">התחלה מתבנית</strong>
                        <small>אפשר לערוך את כל התוכן לאחר הבחירה.</small>
                      </div>
                      <button
                        type="button"
                        className={draft === SUMMARY_SKILL_TEMPLATE ? "active" : ""}
                        onClick={() => applyTemplate("תהליך סיכום", SUMMARY_SKILL_TEMPLATE)}
                      >
                        <ListOrdered size={17} />
                        <span>
                          <strong>תבנית סיכום</strong>
                          <small>יעד, סדרת בדיקות וסיכום עם ראיות</small>
                        </span>
                      </button>
                      <button
                        type="button"
                        className={draft === SKILL_TEMPLATE ? "active" : ""}
                        onClick={() => applyTemplate("", SKILL_TEMPLATE)}
                      >
                        <FileText size={17} />
                        <span>
                          <strong>תבנית ריקה</strong>
                          <small>הוראות חופשיות למיומנות אחרת</small>
                        </span>
                      </button>
                    </section>
                  </>
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
                {summaryWorkflow && (
                  <SummaryWorkflowEditor
                    target={target}
                    steps={workflowSteps}
                    onTargetChange={(value) => setDraft((current) => (
                      withSummaryTarget(current, value)
                    ))}
                    onChange={(steps) => setDraft((current) => (
                      withSummarySteps(current, steps)
                    ))}
                  />
                )}
                <label className="agent-raw-editor-label" htmlFor="agent-content-source">
                  תוכן מלא — עריכה מתקדמת
                </label>
                <textarea
                  id="agent-content-source"
                  ref={textareaRef}
                  className="agent-content-textarea"
                  dir="ltr"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  spellCheck={false}
                  aria-label="תוכן ההוראה"
                />
                {showAreaSummaryExamples && (
                  <section
                    className="agent-summary-examples"
                    aria-labelledby="agent-summary-examples-title"
                  >
                    <header>
                      <span className="agent-summary-examples-icon" aria-hidden="true">
                        <MapPinned size={18} />
                      </span>
                      <div>
                        <strong id="agent-summary-examples-title">
                          כך ייראה סיכום תא השטח
                        </strong>
                        <small>דוגמת פלט למשתמש, כולל שכבת המקור</small>
                      </div>
                    </header>
                    <ul>
                      {AREA_SUMMARY_EXAMPLES.map((example) => (
                        <li key={example.text}>
                          <span>{example.text}</span>
                          <small>{example.source}</small>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
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
