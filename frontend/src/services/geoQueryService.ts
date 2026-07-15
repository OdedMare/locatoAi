import type { GeoQueryRequest, GeoQueryResponse } from "@/types/geo-query";

function errorDetail(body: unknown): string {
  if (!body || typeof body !== "object" || !("detail" in body)) return "";

  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return String(item);
      })
      .join("; ");
  }
  return detail == null ? "" : String(detail);
}

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
  console.info("Query pipeline started", request);
  try {
    res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch (error) {
    console.warn("Query request could not reach the backend", error);
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
    let detail = "";
    let body: Record<string, unknown> = {};
    try {
      body = JSON.parse(raw) as Record<string, unknown>;
      detail = errorDetail(body);
    } catch {
      detail = raw;
    }
    const message = detail || `השרת החזיר שגיאה ${res.status}`;
    console.error("Query pipeline failed", {
      status: res.status,
      requestId: body.request_id,
      pipelineTrace: body.pipeline_trace,
      errorType: body.error_type,
      detail: message,
    });
    return {
      status: "error",
      request_id: typeof body.request_id === "string" ? body.request_id : null,
      clarify: message,
      plan: null,
      features: null,
      scalar_result: null,
      timing_ms: null,
      token_usage: null,
      selected_layers: [],
      reasoning: "",
      tool_calls: [],
      pipeline_trace: Array.isArray(body.pipeline_trace)
        ? body.pipeline_trace as GeoQueryResponse["pipeline_trace"]
        : [],
    };
  }
  const response = await res.json() as GeoQueryResponse;
  console.info("Query pipeline completed", response);
  return response;
}
