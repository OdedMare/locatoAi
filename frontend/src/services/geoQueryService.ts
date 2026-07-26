import type {
  GeoQueryRequest,
  GeoQueryResponse,
  PipelineTraceEntry,
} from "@/types/geo-query";
import { QueryDebugLog } from "@/services/queryDebugLog";

function failedResponse(
  message: string, requestId: string, trace: PipelineTraceEntry[]
): GeoQueryResponse {
  return {
    status: "error", request_id: requestId, clarify: message,
    plan: null, features: null, scalar_result: null, timing_ms: null,
    display_field: null,
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

async function httpFailure(
  response: Response, clientRequestId: string
): Promise<GeoQueryResponse> {
  const raw = await response.text().catch(() => "");
  let body: Record<string, unknown> = {};
  try {
    body = JSON.parse(raw) as Record<string, unknown>;
  } catch {
    body = {};
  }
  const message = errorDetail(body) || raw || `השרת החזיר שגיאה ${response.status}`;
  const requestId = typeof body.request_id === "string"
    ? body.request_id
    : response.headers.get("X-Request-ID") ?? clientRequestId;
  const trace = Array.isArray(body.pipeline_trace)
    ? body.pipeline_trace as PipelineTraceEntry[]
    : [transportFailure(message, "UnstructuredHttpError", { http_status: response.status })];
  return failedResponse(message, requestId, trace);
}

export async function submitQuery(
  request: GeoQueryRequest,
): Promise<GeoQueryResponse> {
  const clientRequestId = crypto.randomUUID();
  QueryDebugLog.started(clientRequestId, request);
  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-ID": clientRequestId,
      },
      body: JSON.stringify(request),
    });
    const result = response.ok
      ? await response.json() as GeoQueryResponse
      : await httpFailure(response, clientRequestId);
    QueryDebugLog.completed(result);
    return result;
  } catch (error) {
    const message = "לא ניתן להתחבר לשרת. בדקו שהשרת פועל ונסו שוב.";
    const trace = [transportFailure(message, "NetworkError", {
      cause: error instanceof Error ? error.message : String(error),
    })];
    QueryDebugLog.transportFailed({
      status: 0, detail: message, errorType: "NetworkError",
      pipelineTrace: trace, requestId: clientRequestId,
      cause: error,
    });
    return failedResponse(message, clientRequestId, trace);
  }
}
