"use client";

import type { GeoQueryRequest, GeoQueryResponse } from "@/types/geo-query";

interface RequestPreviewProps {
  request: GeoQueryRequest | null;
  response: GeoQueryResponse | null;
}

/**
 * Debug panel showing the exact request JSON sent to the geo-query service.
 * This is the payload the future backend (`POST /api/geo-query`) will receive.
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
            <p className="response-meta">
              Mock service accepted · <code>{response.requestId}</code>
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
