"use client";

import { useEffect, useState } from "react";
import { submitFeedback } from "@/services/feedbackService";
import type { GeoQueryResponse } from "@/types/geo-query";

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
  const [voted, setVoted] = useState<"up" | "down" | null>(null);

  // A new response resets the vote state.
  useEffect(() => setVoted(null), [response]);

  if (!isSubmitting && response === null) return null;

  const selectMs = response?.timing_ms?.select;
  const canVote =
    !isSubmitting &&
    response !== null &&
    (response.selected_layers.length > 0 || response.status === "clarify");

  const vote = (verdict: "up" | "down") => {
    if (!response || voted) return;
    setVoted(verdict);
    void submitFeedback(query, response, verdict);
  };

  return (
    <section className="agent-trace">
      <header className="panel-section-header">
        <h2>הסוכן</h2>
        {typeof selectMs === "number" && (
          <span className="badge">בחירה {selectMs} אלפיות שנייה</span>
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

      {isSubmitting ? (
        <p className="agent-step running">🧠 בוחר שכבות מהקטלוג…</p>
      ) : response!.selected_layers.length > 0 ? (
        <>
          {response!.reasoning && (
            <p className="agent-reasoning" dir="auto">
              🧠 {response!.reasoning}
            </p>
          )}
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
