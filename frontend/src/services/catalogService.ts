import type {
  CatalogLayer,
  CreateLayerRequest,
  LayersResponse,
  MqsSyncResponse,
} from "@/types/catalog";

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

/** Pull the MQS layer inventory into the catalog (upsert by source URL). */
export async function syncMqsLayers(): Promise<MqsSyncResponse> {
  const res = await fetch("/api/layers/sync-mqs", { method: "POST" });
  if (!res.ok) {
    if (res.status === 502) {
      throw new Error("שרת MQS אינו מוגדר או אינו זמין — בדקו את כתובת ה-MQS בהגדרות");
    }
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `סנכרון שכבות MQS נכשל (${res.status})`);
  }
  return res.json();
}
