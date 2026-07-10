import type { LayersResponse } from "@/types/catalog";

/** Fetch the layer catalog (metadata only — what users can ask about). */
export async function getLayers(): Promise<LayersResponse> {
  const res = await fetch("/api/layers");
  if (!res.ok) throw new Error(`GET /api/layers failed (${res.status})`);
  return res.json();
}
