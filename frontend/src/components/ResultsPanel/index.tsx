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
        <h2>Results</h2>
      </header>
      {response === null ? (
        <p className="panel-placeholder">
          Results will appear here in the next stage.
        </p>
      ) : response.status === "clarify" ? (
        response.selected_layers.length > 0 ? (
          <p className="panel-placeholder">
            Layers are selected — results arrive once plan building
            (agent call 2) is implemented.
          </p>
        ) : (
          <p className="panel-placeholder" dir="auto">
            💬 {response.clarify}
          </p>
        )
      ) : response.status === "error" ? (
        <p className="panel-placeholder">
          ⚠️ Request failed{response.clarify ? ` — ${response.clarify}` : ""}.
          Is the backend running on port 8000?
        </p>
      ) : (
        <p className="panel-placeholder">
          ✅ {response.features?.features.length ?? 0} features returned.
        </p>
      )}
    </section>
  );
}
