import type { GeoQueryResponse } from "@/types/geo-query";
import { request } from "@/services/api";

/** Store a 👍/👎 verdict on an agent selection in PostgreSQL. */
export async function submitFeedback(
  query: string,
  response: GeoQueryResponse,
  verdict: "up" | "down"
): Promise<boolean> {
  try {
    await request<unknown>("/api/feedback", {
      method: "POST",
      body: JSON.stringify({
        query,
        verdict,
        selected_layers: response.selected_layers.map((l) => l.name),
        reasoning: response.reasoning,
        clarify: response.clarify,
      }),
    });
    return true;
  } catch {
    return false;
  }
}
