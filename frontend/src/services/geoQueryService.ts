import { request } from "@/services/api";
import { QueryDebugLog } from "@/services/queryDebugLog";
import type {
  GeoQueryRequest,
  GeoQueryResponse,
  GeoQueryRun,
  PipelineTraceEntry,
} from "@/types/geo-query";

export async function startQueryRun(
  query: GeoQueryRequest,
): Promise<GeoQueryRun> {
  const requestId = crypto.randomUUID();
  QueryDebugLog.started(requestId, query);
  try {
    return await request<GeoQueryRun>("/api/query-runs", {
      method: "POST",
      headers: { "X-Request-ID": requestId },
      body: JSON.stringify(query),
    });
  } catch (reason) {
    const message = reason instanceof Error
      ? reason.message
      : "לא ניתן להתחבר לשרת. בדקו שהשרת פועל ונסו שוב.";
    const trace = [transportFailure(message, reason)];
    QueryDebugLog.transportFailed({ requestId, message, cause: reason });
    return failedRun(requestId, message, trace);
  }
}

export function getQueryRun(id: string): Promise<GeoQueryRun> {
  return request<GeoQueryRun>(`/api/query-runs/${encodeURIComponent(id)}`);
}

export function failedResponse(run: GeoQueryRun): GeoQueryResponse {
  const message = run.error || "הרצת השאילתה נכשלה";
  return {
    status: "error", request_id: run.id, clarify: message,
    plan: null, features: null, scalar_result: null, timing_ms: null,
    display_field: null, token_usage: null, selected_layers: [], reasoning: "",
    tool_calls: [], pipeline_trace: run.pipeline_trace.length
      ? run.pipeline_trace
      : [transportFailure(message, run.error_type)],
  };
}

function failedRun(
  id: string, error: string, pipelineTrace: PipelineTraceEntry[],
): GeoQueryRun {
  const now = new Date().toISOString();
  return {
    id, status: "failed", created_at: now, updated_at: now,
    pipeline_trace: pipelineTrace, response: null,
    error_type: "TransportError", error,
  };
}

function transportFailure(message: string, reason: unknown): PipelineTraceEntry {
  return {
    stage: "transport", status: "failed", error: message,
    error_type: reason instanceof Error ? reason.name : String(reason),
  };
}
