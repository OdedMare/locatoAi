"use client";

import type { GeoQueryResponse } from "@/types/geo-query";

interface ResultsPanelProps {
  response: GeoQueryResponse | null;
}

/**
 * Results panel. Shows feature counts / clarify questions from the
 * backend; rich result rendering (lists, map highlights) comes with the
 * agent in the next stage.
 */
export default function ResultsPanel({ response }: ResultsPanelProps) {
  return (
    <section className="results-panel">
      <header className="panel-section-header">
        <h2>תוצאות</h2>
      </header>
      {response === null ? (
        <p className="panel-placeholder">
          התוצאות יופיעו כאן בשלב הבא.
        </p>
      ) : response.status === "clarify" ? (
        response.selected_layers.length > 0 ? (
          <p className="panel-placeholder">
            השכבות נבחרו — התוצאות יופיעו לאחר השלמת בניית התוכנית.
          </p>
        ) : (
          <p className="panel-placeholder" dir="auto">
            💬 {response.clarify}
          </p>
        )
      ) : response.status === "error" ? (
        <p className="panel-placeholder">
          ⚠️ הבקשה נכשלה{response.clarify ? ` — ${response.clarify}` : ""}.
          האם השרת פועל בפורט 8000?
        </p>
      ) : (
        <p className="panel-placeholder">
          ✅ הוחזרו {response.features?.features.length ?? 0} ישויות.
        </p>
      )}
    </section>
  );
}
