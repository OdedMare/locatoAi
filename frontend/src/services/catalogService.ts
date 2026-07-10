import type { CatalogLayer, CreateLayerRequest, LayersResponse } from "@/types/catalog";

/** Fetch the layer catalog (metadata only — what users can ask about). */
export async function getLayers(): Promise<LayersResponse> {
  const res = await fetch("/api/layers");
  if (!res.ok) throw new Error(`טעינת השכבות נכשלה (${res.status})`);
  return res.json();
}

export async function createLayer(layer: CreateLayerRequest): Promise<CatalogLayer> {
  const res = await fetch("/api/layers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(layer),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `הוספת השכבה נכשלה (${res.status})`);
  }
  return res.json();
}
