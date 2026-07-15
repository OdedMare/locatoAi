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
  } catch (error) {
    console.error("Query request could not reach the backend", error);
    return {
      status: "error",
      clarify: "לא ניתן להתחבר לשרת. בדקו שהשרת פועל ונסו שוב.",
      plan: null,
      features: null,
      scalar_result: null,
      timing_ms: null,
      token_usage: null,
      selected_layers: [],
      reasoning: "",
      tool_calls: [],
      pipeline_trace: [],
    };
  }

  if (!res.ok) {
    const raw = await res.text().catch(() => "");
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: string };
      detail = parsed.detail ?? raw;
    } catch {
      detail = raw;
    }
    console.error("Query backend error", { status: res.status, detail });
    return {
      status: "error",
      clarify: detail || `השרת החזיר שגיאה ${res.status}`,
      plan: null,
      features: null,
      scalar_result: null,
      timing_ms: null,
      token_usage: null,
      selected_layers: [],
      reasoning: "",
      tool_calls: [],
      pipeline_trace: [],
    };
  }
  return res.json();
}
