import type { GeoQueryResponse } from "@/types/geo-query";

/** Log a 👍/👎 verdict on an agent selection (backend appends to feedback.jsonl). */
export async function submitFeedback(
  query: string,
  response: GeoQueryResponse,
  verdict: "up" | "down"
): Promise<boolean> {
  try {
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        verdict,
        selected_layers: response.selected_layers.map((l) => l.name),
        reasoning: response.reasoning,
        clarify: response.clarify,
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}
