import type { GeoQueryRequest, GeoQueryResponse } from "@/types/geo-query";

/**
 * Mock geo-query service.
 *
 * FUTURE BACKEND INTEGRATION:
 * Replace the body of `submitQuery` with a real call to the backend:
 *
 *   const res = await fetch("/api/geo-query", {
 *     method: "POST",
 *     headers: { "Content-Type": "application/json" },
 *     body: JSON.stringify(request),
 *   });
 *   return res.json();
 *
 * The backend will run the LLM agent (intent parsing → spatial plan →
 * SQL/GIS execution) and return real results. The request shape must not
 * change — it is the UI ↔ agent contract defined in types/geo-query.ts.
 */
export async function submitQuery(
  request: GeoQueryRequest
): Promise<GeoQueryResponse> {
  // Simulate network latency so the UI's loading state is exercised.
  await new Promise((resolve) => setTimeout(resolve, 400));

  return {
    status: "accepted",
    requestId: `mock-${Date.now().toString(36)}`,
    receivedAt: new Date().toISOString(),
    echo: request,
    results: [],
  };
}
