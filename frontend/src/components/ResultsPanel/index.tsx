"use client";

import type { GeoQueryResponse } from "@/types/geo-query";

interface ResultsPanelProps {
  response: GeoQueryResponse | null;
}

/** Computed by NearOp (backend/app/bl/executor/ops/near.py) — shown as its
 * own formatted column, and used to sort nearest-first when present. */
const DISTANCE_FIELD = "distance_to_target_m";
const MAX_ROWS = 20;

function ResultsTable({ response }: { response: GeoQueryResponse }) {
  const features = response.features?.features ?? [];
  if (features.length === 0) {
    return (
      <p className="panel-placeholder">לא נמצאו תוצאות מתאימות לשאילתה.</p>
    );
  }

  const rows = features.map(
    (f) => (f.properties as Record<string, unknown> | null) ?? {}
  );
  const hasDistance = rows.some((row) => typeof row[DISTANCE_FIELD] === "number");
  if (hasDistance) {
    rows.sort(
      (a, b) =>
        ((a[DISTANCE_FIELD] as number) ?? Infinity) -
        ((b[DISTANCE_FIELD] as number) ?? Infinity)
    );
  }

  const columns = Array.from(
    new Set(rows.flatMap((row) => Object.keys(row)))
  ).filter((key) => key !== DISTANCE_FIELD);
  const visibleRows = rows.slice(0, MAX_ROWS);

  return (
    <div dir="auto">
      <p className="panel-placeholder">
        ✅ נמצאו {features.length} תוצאות (מסומנות על המפה):
      </p>
      <div className="results-table-scroll">
        <table className="results-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col} dir="ltr">{col}</th>
              ))}
              {hasDistance && <th dir="ltr">{DISTANCE_FIELD}</th>}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td key={col}>{formatValue(row[col])}</td>
                ))}
                {hasDistance && (
                  <td dir="ltr">
                    {typeof row[DISTANCE_FIELD] === "number"
                      ? `${Math.round(row[DISTANCE_FIELD] as number)} מ'`
                      : "—"}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > MAX_ROWS && (
        <p className="panel-placeholder">ועוד {rows.length - MAX_ROWS}…</p>
      )}
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return String(value);
  return String(value);
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
        <ResultsTable response={response} />
      )}
    </section>
  );
}
