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
const MAX_LISTED = 8;

function ResultsList({ response }: { response: GeoQueryResponse }) {
  const features = response.features?.features ?? [];
  if (features.length === 0) {
    return (
      <p className="panel-placeholder">לא נמצאו תוצאות מתאימות לשאילתה.</p>
    );
  }
  const names = features
    .map((f) => (f.properties as Record<string, unknown> | null)?.name)
    .filter((n): n is string => typeof n === "string");
  return (
    <div dir="auto">
      <p className="panel-placeholder">✅ נמצאו {features.length} תוצאות (מסומנות על המפה):</p>
      <ul className="results-name-list">
        {names.slice(0, MAX_LISTED).map((name, i) => (
          <li key={`${name}-${i}`}>{name}</li>
        ))}
        {names.length > MAX_LISTED && <li>ועוד {names.length - MAX_LISTED}…</li>}
      </ul>
    </div>
  );
}

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
        <ResultsList response={response} />
      )}
    </section>
  );
}
