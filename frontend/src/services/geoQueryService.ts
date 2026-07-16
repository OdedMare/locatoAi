import type {
  GeoQueryRequest,
  GeoQueryResponse,
  PipelineTraceEntry,
} from "@/types/geo-query";

function failedResponse(
  message: string, requestId: string, trace: PipelineTraceEntry[]
): GeoQueryResponse {
  return {
    status: "error", request_id: requestId, clarify: message,
    plan: null, features: null, scalar_result: null, timing_ms: null,
    token_usage: null, selected_layers: [], reasoning: "", tool_calls: [],
    pipeline_trace: trace,
  };
}

function transportFailure(
  message: string, errorType: string, parameters?: Record<string, unknown>
): PipelineTraceEntry {
  return {
    stage: "transport", status: "failed", error_type: errorType,
    error: message, parameters,
  };
}

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
  const clientRequestId = crypto.randomUUID();
  console.info("Query pipeline started", { requestId: clientRequestId, request });
  try {
    res = await fetch("/api/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Request-ID": clientRequestId,
      },
      body: JSON.stringify(request),
    });
  } catch (error) {
    const message = "לא ניתן להתחבר לשרת. בדקו שהשרת פועל ונסו שוב.";
    const trace = [transportFailure(message, "NetworkError", {
      cause: error instanceof Error ? error.message : String(error),
    })];
    console.error("Query pipeline failed", {
      status: 0, detail: message, errorType: "NetworkError",
      pipelineTrace: trace, requestId: clientRequestId,
    });
    return failedResponse(message, clientRequestId, trace);
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
    const requestId = typeof body.request_id === "string"
      ? body.request_id
      : res.headers.get("X-Request-ID") ?? clientRequestId;
    const errorType = typeof body.error_type === "string"
      ? body.error_type
      : "UnstructuredHttpError";
    const trace = Array.isArray(body.pipeline_trace)
      ? body.pipeline_trace as GeoQueryResponse["pipeline_trace"]
      : [transportFailure(message, errorType, {
          http_status: res.status,
          raw_response: raw.slice(0, 1000),
        })];
    console.error("Query pipeline failed", {
      status: res.status,
      requestId,
      pipelineTrace: trace,
      errorType,
      detail: message,
    });
    return failedResponse(message, requestId, trace);
  }
  const response = await res.json() as GeoQueryResponse;
  console.info("Query pipeline completed", response);
  return response;
}
