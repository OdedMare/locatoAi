"use client";

import { useState } from "react";
import { submitFeedback } from "@/services/feedbackService";
import type { GeoPlanStep, GeoQueryResponse } from "@/types/geo-query";

const EXTREME_DIRECTION_HE: Record<string, string> = {
  north: "הצפוני ביותר",
  south: "הדרומי ביותר",
  east: "המזרחי ביותר",
  west: "המערבי ביותר",
};

const MOVEMENT_DIRECTION_HE: Record<string, string> = {
  any: "בכיוון כלשהו",
  north: "צפונה",
  south: "דרומה",
  east: "מזרחה",
  west: "מערבה",
};

const TRAJECTORY_RELATION_HE: Record<string, string> = {
  together: "נעו או שהו יחד",
  same_destination: "הגיעו לאותו יעד",
  same_time: "נעו באותו זמן",
  same_place_different_times: "עברו באותו מקום בזמנים שונים",
};

const ORIGIN_MOVEMENT_HE: Record<string, string> = {
  departed: "יצאו מנקודת המוצא המשוערת",
  round_trip: "יצאו וחזרו לנקודת המוצא המשוערת",
};

/** One Hebrew line per plan step, with layer ids resolved to names. */
function describeStep(step: GeoPlanStep, layerName: (id?: string) => string): string {
  switch (step.op) {
    case "load":
      return `טעינת השכבה ${layerName(step.layer)}`;
    case "within_geometry":
      return "סינון לאזור שסומן על המפה";
    case "attribute_filter":
      return `סינון לפי ${step.field} ${step.operator} "${step.value}"`;
    case "near":
      return `בקרבת ${layerName(step.target_layer)} (עד ${step.distance_m} מ')`;
    case "nearest_n":
      return `${step.count ?? "—"} הקרובים ביותר ל${layerName(step.target_layer)}`;
    case "near_all":
      return `${step.count ? `${step.count} הטובים ביותר ` : ""}בקרבת כל השכבות: ${(step.targets ?? []).map((target) => layerName(target.layer)).join(", ")} (עד ${step.distance_m ?? "—"} מ')`;
    case "between":
      return `בין ${layerName(step.first_target_layer)} ל${layerName(step.second_target_layer)} (מסדרון ${step.corridor_width_m ?? "—"} מ')`;
    case "crosses":
      return `חוצה את ${layerName(step.target_layer)}`;
    case "touches":
      return `נוגע בגבול של ${layerName(step.target_layer)}`;
    case "contains":
      return `מכיל ישות מתוך ${layerName(step.target_layer)}`;
    case "directional":
      return `${EXTREME_DIRECTION_HE[step.direction ?? ""] ?? step.direction}${(step.count ?? 1) > 1 ? ` (${step.count})` : ""}`;
    case "temporal_filter":
      return `סינון זמן: ${step.from} עד ${step.to}`;
    case "cluster":
      return `איתור קבוצות של ${step.min_group_size ?? "—"}+ ישויות קרובות זו לזו (עד ${step.max_distance_m ?? "—"} מ')`;
    case "latest_per_entity":
      return `המיקום האחרון לכל ישות לפי ${step.entity_field ?? "תפקיד הזהות בסכמה"}`;
    case "movement_direction":
      return `ישויות שנעו ${MOVEMENT_DIRECTION_HE[step.direction ?? ""] ?? step.direction} לפחות ${step.min_distance_m ?? "—"} מ'`;
    case "trajectory_relation":
      return `${TRAJECTORY_RELATION_HE[step.relation ?? ""] ?? step.relation} (מרחק עד ${step.max_distance_m ?? "—"} מ', מרווח זמן ${step.time_tolerance_minutes ?? "—"} דק')`;
    case "origin_movement":
      return `${ORIGIN_MOVEMENT_HE[step.pattern ?? ""] ?? step.pattern} בין ${step.start_at} ל-${step.end_at}`;
    case "count":
      return "ספירת תוצאות";
  }
}

const STAGE_HE: Record<string, string> = {
  transport: "תקשורת עם השרת",
  layer_selection: "בחירת שכבות",
  plan_building: "בניית תוכנית",
  plan_validation: "אימות תוכנית",
  execution: "ביצוע התוכנית",
  execute_step: "ביצוע פעולה",
  zero_result_diagnosis: "אבחון תוצאה ריקה",
  re_execution: "ביצוע תוכנית מתוקנת",
  response: "הכנת תשובה",
};

const STATUS_MARK: Record<string, string> = {
  started: "◌", completed: "✓", clarify: "?", failed: "✕", error: "✕",
};

const OP_HE: Record<string, string> = {
  load: "טעינת נתונים", within_geometry: "תחום גיאוגרפי",
  attribute_filter: "סינון מאפיינים", near: "בדיקת קרבה",
  nearest_n: "הקרובים ביותר", near_all: "קרבה למספר יעדים",
  between: "בין יעדים", crosses: "חצייה", touches: "נגיעה",
  contains: "הכלה", directional: "כיוון", temporal_filter: "טווח זמן",
  cluster: "קיבוץ", latest_per_entity: "מיקום אחרון",
  movement_direction: "כיוון תנועה", trajectory_relation: "קשר בין מסלולים",
  origin_movement: "תנועה מנקודת מוצא", count: "ספירה",
};

function PipelineTimeline({ response }: { response: GeoQueryResponse }) {
  const trace = response.pipeline_trace ?? [];
  if (trace.length === 0) return null;
  return (
    <div className="plan-trace pipeline-timeline" dir="auto">
      <p className="agent-step done">פירוט מלא של הצינור:</p>
      {response.request_id && (
        <p className="plan-explanation" dir="ltr">request_id: {response.request_id}</p>
      )}
      <ol className="plan-steps">
        {trace.map((entry, index) => (
          <li key={`${index}-${entry.stage}-${entry.step_id ?? ""}`} className="plan-step">
            <div>
              <strong>{STATUS_MARK[entry.status] ?? "•"} {STAGE_HE[entry.stage] ?? entry.stage}</strong>
              <span dir="ltr"> · {entry.status}</span>
              {entry.operation && <span dir="ltr"> · {entry.operation}</span>}
              {typeof entry.duration_ms === "number" && ` · ${entry.duration_ms} מ״ש`}
            </div>
            {entry.selected_layer_names?.length ? (
              <div>שכבות: {entry.selected_layer_names.join(", ")}</div>
            ) : null}
            {(entry.requested_layer_ids?.length || entry.dropped_layer_ids?.length) ? (
              <details>
                <summary>מזהי שכבות מהמודל</summary>
                <pre dir="ltr">{JSON.stringify({
                  requested: entry.requested_layer_ids ?? [],
                  selected: entry.selected_layer_ids ?? [],
                  dropped: entry.dropped_layer_ids ?? [],
                }, null, 2)}</pre>
              </details>
            ) : null}
            {entry.explanation && <div>{entry.explanation}</div>}
            {entry.clarify && <div>{entry.clarify}</div>}
            {entry.error && (
              <div className="agent-step clarify" dir="auto">
                {entry.error_type ? `${entry.error_type}: ` : ""}{entry.error}
              </div>
            )}
            {typeof entry.attempts === "number" && <div>ניסיונות תכנון: {entry.attempts}</div>}
            {entry.tool_calls?.length ? (
              <details>
                <summary>קריאות כלי תכנון</summary>
                <pre dir="ltr">{JSON.stringify(entry.tool_calls, null, 2)}</pre>
              </details>
            ) : null}
            {(entry.input_count !== undefined || entry.output_count !== undefined) && (
              <div>
                קלט: {entry.input_count ?? "—"} · פלט: {entry.output_count ?? "—"}
              </div>
            )}
            {entry.geometry_returned && (
              <div>גאומטריה הוחזרה · {entry.feature_count ?? 0} ישויות</div>
            )}
            {entry.parameters && Object.keys(entry.parameters).length > 0 && (
              <details>
                <summary>פרמטרים</summary>
                <pre dir="ltr">{JSON.stringify(entry.parameters, null, 2)}</pre>
              </details>
            )}
            {entry.diagnostics?.length ? (
              <details>
                <summary>אבחון תכנון מלא</summary>
                <pre dir="ltr">{JSON.stringify(entry.diagnostics, null, 2)}</pre>
              </details>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

interface AgentTraceProps {
  response: GeoQueryResponse | null;
  isSubmitting: boolean;
  /** The query text that produced `response` (for feedback logging). */
  query: string;
}

/**
 * The agent's "thinking" panel: which catalog layers the model selected
 * (with tags + timing) or the clarification it asked instead — so
 * selection quality can be judged at a glance.
 */
export default function AgentTrace({ response, isSubmitting, query }: AgentTraceProps) {
  const [voteState, setVoteState] = useState<{
    query: string;
    verdict: "up" | "down";
  } | null>(null);
  const voted = voteState?.query === query ? voteState.verdict : null;

  if (!isSubmitting && response === null) return null;

  const selectMs = response?.timing_ms?.select;
  const canVote =
    !isSubmitting &&
    response !== null &&
    (response.selected_layers.length > 0 || response.status === "clarify");

  const vote = (verdict: "up" | "down") => {
    if (!response || voted) return;
    setVoteState({ query, verdict });
    void submitFeedback(query, response, verdict);
  };

  const planMs = response?.timing_ms?.plan;
  const executeMs = response?.timing_ms?.execute;
  const resultCount = response?.features?.features.length ?? response?.scalar_result;

  const layerName = (id?: string) =>
    response?.selected_layers.find((layer) => layer.id === id)?.name ?? "שכבה";

  return (
    <section className="agent-trace">
      <header className="panel-section-header">
        <h2>הסוכן</h2>
        {typeof selectMs === "number" && (
          <span className="badge">בחירה {selectMs} אלפיות שנייה</span>
        )}
        {typeof planMs === "number" && <span className="badge">תכנון {planMs} מ״ש</span>}
        {typeof executeMs === "number" && <span className="badge">ביצוע {executeMs} מ״ש</span>}
        {response?.token_usage && (
          <span
            className="badge token-badge"
            title={`קלט: ${response.token_usage.prompt_tokens} · פלט: ${response.token_usage.completion_tokens}`}
          >
            {response.token_usage.total_tokens} טוקנים
          </span>
        )}
        {canVote && (
          <span className="feedback-buttons">
            <button
              type="button"
              className={`feedback-button${voted === "up" ? " voted" : ""}`}
              onClick={() => vote("up")}
              disabled={voted !== null}
              title="בחירה טובה"
            >
              👍
            </button>
            <button
              type="button"
              className={`feedback-button${voted === "down" ? " voted" : ""}`}
              onClick={() => vote("down")}
              disabled={voted !== null}
              title="בחירה שגויה"
            >
              👎
            </button>
            {voted && <span className="feedback-thanks">נשמר</span>}
          </span>
        )}
      </header>

      {!isSubmitting && response && <PipelineTimeline response={response} />}

      {isSubmitting ? (
        <div className="plan-trace" aria-live="polite">
          <p className="agent-step running">⏳ הצינור פועל בשרת…</p>
          <ol className="plan-steps debug-stage-list">
            <li>בחירת שכבות</li>
            <li>בניית תוכנית ואימותה</li>
            <li>ביצוע התוכנית</li>
          </ol>
          <p className="plan-explanation">השרת מחזיר תשובה רק לאחר סיום הביצוע.</p>
        </div>
      ) : response!.status === "error" ? (
        <div className="plan-trace">
          <p className="agent-step clarify" dir="auto">✕ הצינור נכשל</p>
          {response!.clarify && <p className="plan-explanation" dir="auto">{response!.clarify}</p>}
          <p className="agent-step">לא התקבל אישור לביצוע התוכנית.</p>
        </div>
      ) : response!.selected_layers.length > 0 ? (
        <>
          {response!.reasoning && (
            <p className="agent-reasoning" dir="auto">
              🧠 {response!.reasoning}
            </p>
          )}
          {(response!.tool_calls ?? []).map((call, index) => (
            <p key={`${call.skill_id ?? call.layer_id}-${call.field ?? ""}-${index}`} className="agent-step done" dir="auto">
              {call.skill_id
                ? `🧩 טעינת מיומנות: ${call.skill_id}`
                : `🔍 דגימת ערכים: ${layerName(call.layer_id ?? "")}${call.field ? ` · ${call.field}` : ""}`}
            </p>
          ))}
          <p className="agent-step done">✓ השכבות שנבחרו מהקטלוג:</p>
          <ul className="layer-chip-list">
            {response!.selected_layers.map((layer) => (
              <li
                key={layer.id}
                className="layer-chip"
                title={`${layer.description}\n${layer.id}`}
              >
                <span className="layer-chip-name">{layer.name}</span>
                <span className="layer-chip-tags">{layer.tags.join(" · ")}</span>
              </li>
            ))}
          </ul>
          {response!.plan && (
            <div className="plan-trace" dir="auto">
              <p className="agent-step done">✓ תוכנית השאילתה שנבנתה:</p>
              <ol className="plan-steps">
                {response!.plan.steps.map((step, index) => (
                  <li key={step.id} className="plan-step query-plan-step">
                    <span className="plan-step-index">{index + 1}</span>
                    <span className="plan-step-content">
                      <strong>{OP_HE[step.op] ?? step.op}</strong>
                      <small>{describeStep(step, layerName)}</small>
                    </span>
                    <code>{step.op}</code>
                  </li>
                ))}
              </ol>
              <p className="plan-explanation">{response!.plan.explanation}</p>
              {typeof executeMs === "number" ? (
                <p className="agent-step done">
                  ✓ התוכנית בוצעה בפועל בשרת ({executeMs} מ״ש) · התקבלו {resultCount ?? 0} תוצאות
                </p>
              ) : (
                <p className="agent-step clarify">⚠ התוכנית נבנתה אך אין אישור ביצוע בתשובת השרת</p>
              )}
            </div>
          )}
          {!response!.plan && (
            <p className="agent-step clarify">⊘ לא נבנתה תוכנית ולכן שלב הביצוע לא הופעל</p>
          )}
        </>
      ) : response!.clarify && response!.status === "clarify" ? (
        <>
          {response!.reasoning && (
            <p className="agent-reasoning" dir="auto">
              🧠 {response!.reasoning}
            </p>
          )}
          <p className="agent-step clarify" dir="auto">
            💬 {response!.clarify}
          </p>
        </>
      ) : (
        <p className="agent-step">אין פעילות סוכן עבור הבקשה הזו.</p>
      )}
    </section>
  );
}
