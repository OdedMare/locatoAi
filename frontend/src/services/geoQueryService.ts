import type { GeoQueryRequest, GeoQueryResponse } from "@/types/geo-query";

/**
 * Real backend call. `/api/*` is proxied to the FastAPI backend by the
 * rewrite in next.config.ts, so the backend must be running:
 *
 *   cd backend && .venv/bin/uvicorn app.main:app --port 8000
 *
 * Day 1: the backend's agent is stubbed, so this returns a `clarify`
 * response. The contract is final — nothing here changes on Day 2.
 */
export async function submitQuery(
  request: GeoQueryRequest
): Promise<GeoQueryResponse> {
  let res: Response;
  try {
    res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    return {
      status: "error",
      clarify: null,
      plan: null,
      features: null,
      timing_ms: null,
    };
  }

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    return {
      status: "error",
      clarify: detail || `Backend returned ${res.status}`,
      plan: null,
      features: null,
      timing_ms: null,
    };
  }
  return res.json();
}
