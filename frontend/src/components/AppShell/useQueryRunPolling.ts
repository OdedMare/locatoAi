import type { Dispatch, SetStateAction } from "react";
import { useEffect } from "react";
import { failedResponse, getQueryRun } from "@/services/geoQueryService";
import { QueryDebugLog } from "@/services/queryDebugLog";
import type { GeoQueryResponse, GeoQueryRun } from "@/types/geo-query";

type Setter<T> = Dispatch<SetStateAction<T>>;

export const isActive = (run: GeoQueryRun | null) =>
  run?.status === "queued" || run?.status === "running";

export function useQueryRunPolling(
  run: GeoQueryRun | null,
  setRun: Setter<GeoQueryRun | null>,
  setResponse: Setter<GeoQueryResponse | null>,
  setError: Setter<string | null>,
) {
  const runId = run?.id;
  const active = isActive(run);
  useEffect(() => {
    if (!runId || !active) return;
    const startedAt = Date.now();
    let timer: number | undefined;
    let stopped = false;
    let warned = false;
    console.debug(`[poll] watching query run ${runId}`);

    const poll = () => {
      getQueryRun(runId).then((next) => {
        if (stopped) return;
        const age = (Date.now() - startedAt) / 1000;
        console.debug(
          `[poll] query ${next.id} status=${next.status} `
          + `events=${next.pipeline_trace.length} age=${age.toFixed(0)}s`,
        );
        if (isActive(next) && age > 180 && !warned) {
          warned = true;
          console.warn(
            `[poll] query ${next.id} is still ${next.status} after `
            + `${age.toFixed(0)}s; check backend external-call timeouts.`,
          );
        }
        setError(null);
        setRun(next);
        if (isActive(next)) {
          timer = window.setTimeout(poll, 1500);
          return;
        }
        const response = next.response ?? failedResponse(next);
        QueryDebugLog.completed(response);
        setResponse(response);
      }).catch((reason) => {
        if (stopped) return;
        console.error(`[poll] query ${runId} failed`, reason);
        setError(reason instanceof Error ? reason.message : String(reason));
        timer = window.setTimeout(poll, 1500);
      });
    };

    timer = window.setTimeout(poll, 1500);
    return () => {
      stopped = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [runId, active, setRun, setResponse, setError]);
}
