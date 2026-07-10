"use client";

import type { GeoQueryRequest, GeoQueryResponse } from "@/types/geo-query";

interface RequestPreviewProps {
  request: GeoQueryRequest | null;
  response: GeoQueryResponse | null;
}

/**
 * Debug panel: the exact JSON sent to POST /api/query, and the backend's
 * response status (clarify text / timings) once it answers.
 */
export default function RequestPreview({ request, response }: RequestPreviewProps) {
  return (
    <section className="request-preview">
      <header className="panel-section-header">
        <h2>Request preview</h2>
        <span className="badge">debug</span>
      </header>
      {request ? (
        <>
          <pre className="json-block">{JSON.stringify(request, null, 2)}</pre>
          {response && (
            <p className={`response-meta status-${response.status}`}>
              Backend: <strong>{response.status}</strong>
              {response.clarify && <> — {response.clarify}</>}
              {response.timing_ms && (
                <> · {JSON.stringify(response.timing_ms)}</>
              )}
            </p>
          )}
        </>
      ) : (
        <p className="panel-placeholder">
          Run a query to see the structured request object here.
        </p>
      )}
    </section>
  );
}
