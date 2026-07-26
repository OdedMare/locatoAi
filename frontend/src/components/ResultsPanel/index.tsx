"use client";

import { AlertTriangle, CheckCircle2, Database, MapPinned, SearchX } from "lucide-react";
import type { GeoQueryResponse } from "@/types/geo-query";

interface ResultsPanelProps {
  response: GeoQueryResponse | null;
}

/** Computed by NearOp (backend/app/bl/executor/ops/near.py) — shown as its
 * own formatted column, and used to sort nearest-first when present. */
const DISTANCE_FIELD = "distance_to_target_m";
const INTERNAL_FIELDS = new Set([
  "nearest_target_feature",
  "matched_reference_features",
  "distance_to_targets_m",
]);
const MAX_ROWS = 20;

function ResultsTable({ response }: { response: GeoQueryResponse }) {
  const features = response.features?.features ?? [];
  if (features.length === 0) {
    return (
      <div className="result-state empty"><SearchX size={20} /><span>לא נמצאו תוצאות מתאימות לשאילתה.</span></div>
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
  ).filter((key) => key !== DISTANCE_FIELD && !INTERNAL_FIELDS.has(key));
  const visibleRows = rows.slice(0, MAX_ROWS);

  return (
    <div dir="auto">
      <div className="results-summary">
        <span className="results-summary-icon"><MapPinned size={17} /></span>
        <span><strong>{features.length} תוצאות</strong><small>מוצגות ומסומנות על המפה</small></span>
        <span className="results-live"><i /> LIVE</span>
      </div>
      <div className="results-table-scroll">
        <table className="results-table">
          <thead>
            <tr>
              <th className="result-index">#</th>
              {columns.map((col) => (
                <th key={col} dir="ltr">{col}</th>
              ))}
              {hasDistance && <th dir="ltr">{DISTANCE_FIELD}</th>}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, i) => (
              <tr key={i}>
                <td className="result-index"><span>{i + 1}</span></td>
                {columns.map((col) => (
                  <td key={col}>{formatValue(row[col])}</td>
                ))}
                {hasDistance && (
                  <td dir="ltr" className="distance-cell">
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
        <h2><Database size={13} /> תוצאות</h2>
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
        <div className="result-state error"><AlertTriangle size={20} /><span>
          הבקשה נכשלה{response.clarify ? ` — ${response.clarify}` : ""}.
        </span></div>
      ) : response.scalar_result !== null ? (
        <div className="result-state success" dir="auto"><CheckCircle2 size={20} />
          <span><strong>{response.scalar_result}</strong> תוצאות נמצאו</span>
        </div>
      ) : (
        <ResultsTable response={response} />
      )}
    </section>
  );
}
