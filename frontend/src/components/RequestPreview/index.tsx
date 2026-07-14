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
        <h2>תצוגת הבקשה</h2>
        <span className="badge">ניפוי שגיאות</span>
      </header>
      {request ? (
        <>
          <pre className="json-block">{JSON.stringify(request, null, 2)}</pre>
          {response && (
            <>
              <p className={`response-meta status-${response.status}`}>
                שרת: <strong>{response.status}</strong>
                {response.clarify && <> — {response.clarify}</>}
                {response.timing_ms && <> · {JSON.stringify(response.timing_ms)}</>}
              </p>
              <details className="debug-response-details">
                <summary>תשובת ניפוי שגיאות מהשרת</summary>
                <pre className="json-block">{JSON.stringify({
                  status: response.status,
                  timing_ms: response.timing_ms,
                  plan: response.plan,
                  execution: response.timing_ms?.execute !== undefined
                    ? {
                        completed: true,
                        duration_ms: response.timing_ms.execute,
                        result_count: response.features?.features.length ?? response.scalar_result ?? 0,
                      }
                    : { completed: false },
                }, null, 2)}</pre>
              </details>
            </>
          )}
        </>
      ) : (
        <p className="panel-placeholder">
          הפעילו שאילתה כדי לראות כאן את אובייקט הבקשה המובנה.
        </p>
      )}
    </section>
  );
}
