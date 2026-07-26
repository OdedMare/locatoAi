"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
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
  const [copied, setCopied] = useState(false);
  const debugPayload = { request, response };
  const copyDebug = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(debugPayload, null, 2));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch (error) {
      console.error("Debug payload copy failed", error);
    }
  };
  return (
    <section className="request-preview">
      <header className="panel-section-header">
        <h2>תצוגת הבקשה</h2>
        <span className="badge">ניפוי שגיאות</span>
        <button className="debug-copy-button" type="button" onClick={copyDebug}>
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? "הועתק" : "העתקת debug"}
        </button>
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
                  selected_layers: response.selected_layers,
                  tool_calls: response.tool_calls,
                  pipeline_trace: response.pipeline_trace,
                  token_usage: response.token_usage,
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
