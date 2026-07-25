import type { GeoQueryResponse, PipelineTraceEntry } from "@/types/geo-query";

/**
 * Mirror the backend pipeline into the browser DevTools console.
 *
 * The server logs every stage to its own console and `requests.jsonl`, but
 * until now the browser only saw two coarse lines. These helpers print each
 * streamed stage as it arrives — grouped, with counts and errors — so a failed
 * query can be diagnosed from DevTools without reading the server log.
 */

const STYLE_STAGE = "color:#4c8bf5;font-weight:600";
const STYLE_FAIL = "color:#e5484d;font-weight:600";
const STYLE_OK = "color:#30a46c;font-weight:600";

function isFailure(entry: PipelineTraceEntry): boolean {
  return entry.status === "failed" || entry.status === "error";
}

/** Fields worth showing per stage; undefined entries are dropped. */
function details(entry: PipelineTraceEntry): Record<string, unknown> {
  const all: Record<string, unknown> = {
    status: entry.status,
    duration_ms: entry.duration_ms,
    step_id: entry.step_id,
    operation: entry.operation,
    input_count: entry.input_count,
    output_count: entry.output_count,
    feature_count: entry.feature_count,
    scalar_result: entry.scalar_result,
    attempts: entry.attempts,
    explanation: entry.explanation,
    clarify: entry.clarify,
    selected_layer_ids: entry.selected_layer_ids,
    selected_layer_names: entry.selected_layer_names,
    dropped_layer_ids: entry.dropped_layer_ids,
    tool_calls: entry.tool_calls,
    diagnostics: entry.diagnostics,
    error_type: entry.error_type,
    error: entry.error,
    parameters: entry.parameters,
  };
  return Object.fromEntries(
    Object.entries(all).filter(([, value]) => value !== undefined && value !== null)
  );
}

export const QueryDebugLog = {
  /** One line per streamed stage, as it happens. */
  stage(entry: PipelineTraceEntry): void {
    const label = entry.step_id
      ? `${entry.stage}:${entry.operation ?? "?"}#${entry.step_id}`
      : entry.stage;
    const style = isFailure(entry) ? STYLE_FAIL : STYLE_STAGE;
    const suffix = entry.duration_ms !== undefined ? ` (${entry.duration_ms}ms)` : "";
    if (isFailure(entry)) {
      console.error(`%c▸ ${label}${suffix}`, style, details(entry));
      return;
    }
    console.info(`%c▸ ${label}${suffix}`, style, details(entry));
  },

  started(requestId: string, request: unknown): void {
    console.info("%c◆ Query pipeline started", STYLE_STAGE, {
      requestId, request,
    });
  },

  /** Full picture once the response lands: timings, plan, trace table. */
  completed(result: GeoQueryResponse): void {
    const failed = result.status === "error";
    const style = failed ? STYLE_FAIL : STYLE_OK;
    const label = failed ? "◆ Query pipeline FAILED" : "◆ Query pipeline completed";
    console.groupCollapsed(`%c${label}`, style, {
      status: result.status,
      request_id: result.request_id,
      features: result.features?.features.length ?? null,
      scalar_result: result.scalar_result,
    });
    if (result.clarify) console.info("clarify:", result.clarify);
    if (result.reasoning) console.info("reasoning:", result.reasoning);
    if (result.timing_ms) console.info("timing_ms:", result.timing_ms);
    if (result.token_usage) console.info("token_usage:", result.token_usage);
    if (result.selected_layers.length) {
      console.info("selected_layers:", result.selected_layers);
    }
    if (result.plan) console.info("plan:", result.plan);
    QueryDebugLog.trace(result.pipeline_trace);
    console.groupEnd();
  },

  /** The trace as a table, with failures called out separately. */
  trace(trace: PipelineTraceEntry[]): void {
    if (!trace.length) return;
    console.table(trace.map((entry) => ({
      stage: entry.stage,
      status: entry.status,
      ms: entry.duration_ms ?? "",
      step: entry.step_id ?? "",
      operation: entry.operation ?? "",
      in: entry.input_count ?? "",
      out: entry.output_count ?? entry.feature_count ?? "",
      error: entry.error ?? "",
    })));
    for (const entry of trace.filter(isFailure)) {
      console.error(
        `%c✕ ${entry.stage} failed`, STYLE_FAIL,
        { error_type: entry.error_type, error: entry.error, ...details(entry) }
      );
    }
  },

  transportFailed(payload: unknown): void {
    console.error("%c◆ Query pipeline transport failure", STYLE_FAIL, payload);
  },
};
