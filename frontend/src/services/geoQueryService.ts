import type {
  GeoQueryRequest,
  GeoQueryResponse,
  PipelineTraceEntry,
} from "@/types/geo-query";
import { QueryDebugLog } from "@/services/queryDebugLog";

export type QueryProgressHandler = (entry: PipelineTraceEntry) => void;

interface StreamFrame {
  event: "trace" | "result" | "error";
  data: unknown;
}

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

function parseFrame(raw: string): StreamFrame | null {
  const event = raw.match(/^event:\s*(.+)$/m)?.[1];
  const data = raw
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!event || !data) return null;
  return { event: event as StreamFrame["event"], data: JSON.parse(data) };
}

async function* streamFrames(
  body: ReadableStream<Uint8Array>
): AsyncGenerator<StreamFrame> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const parts = buffer.replaceAll("\r\n", "\n").split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const frame = parseFrame(part);
      if (frame) yield frame;
    }
    if (done) break;
  }
}

function streamedError(
  data: unknown, fallbackId: string
): GeoQueryResponse {
  const error = data as {
    detail?: string;
    error_type?: string;
    request_id?: string;
    pipeline_trace?: PipelineTraceEntry[];
  };
  const message = error.detail || "זרם הביצוע הופסק לפני שהתקבלה תשובה.";
  const trace = error.pipeline_trace?.length
    ? error.pipeline_trace
    : [transportFailure(message, error.error_type || "StreamError")];
  return failedResponse(
    message,
    error.request_id || fallbackId,
    trace,
  );
}

async function readStream(
  response: Response,
  requestId: string,
  onProgress?: QueryProgressHandler,
): Promise<GeoQueryResponse> {
  if (!response.body) {
    return failedResponse("השרת לא החזיר זרם ביצוע.", requestId, []);
  }
  for await (const frame of streamFrames(response.body)) {
    if (frame.event === "trace") {
      // Mirror every stage into DevTools as it streams, not just at the end.
      QueryDebugLog.stage(frame.data as PipelineTraceEntry);
      onProgress?.(frame.data as PipelineTraceEntry);
    } else if (frame.event === "result") {
      return frame.data as GeoQueryResponse;
    } else if (frame.event === "error") {
      return streamedError(frame.data, requestId);
    }
  }
  return failedResponse("זרם הביצוע הסתיים ללא תשובה.", requestId, []);
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

/**
 * Stream the real backend pipeline while retaining the final response contract.
 */
export async function submitQuery(
  request: GeoQueryRequest,
  onProgress?: QueryProgressHandler,
  streamMode = true,
): Promise<GeoQueryResponse> {
  const clientRequestId = crypto.randomUUID();
  QueryDebugLog.started(clientRequestId, request);
  try {
    const response = await fetch(streamMode ? "/api/query/stream" : "/api/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": streamMode ? "text/event-stream" : "application/json",
        "X-Request-ID": clientRequestId,
      },
      body: JSON.stringify(request),
    });
    const result = response.ok
      ? streamMode
        ? await readStream(response, clientRequestId, onProgress)
        : await response.json() as GeoQueryResponse
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
