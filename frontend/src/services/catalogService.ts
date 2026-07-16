import type {
  CatalogLayer,
  CreateLayerRequest,
  GeneratedLayerMetadataResponse,
  GenerateLayerMetadataRequest,
  LayersResponse,
  MqsSyncResponse,
  RemoteMqsLayersResponse,
} from "@/types/catalog";

/** Fetch the layer catalog (metadata only — what users can ask about). */
export async function getLayers(): Promise<LayersResponse> {
  const res = await fetch("/api/layers");
  if (!res.ok) throw new Error(`טעינת השכבות נכשלה (${res.status})`);
  return res.json();
}

/** Browse the remote MQS inventory without adding it to the catalog. */
export async function getMqsLayers(): Promise<RemoteMqsLayersResponse> {
  const res = await fetch("/api/layers/mqs");
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `טעינת שכבות MQS נכשלה (${res.status})`);
  }
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

/** Probe Tyche and idempotently add/refresh the Our Forces catalog layer. */
export async function activateTycheLayer(): Promise<CatalogLayer> {
  const res = await fetch("/api/layers/activate-tyche", { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    if (res.status === 404) {
      throw new Error(
        "נתיב הפעלת Tyche לא קיים בשרת הפעיל — יש לבנות ולהפעיל מחדש את ה-backend"
      );
    }
    throw new Error(body?.detail ?? `הפעלת שכבת Tyche נכשלה (${res.status})`);
  }
  return res.json();
}

/** Sample up to 10 entities and ask the LLM for editable metadata suggestions. */
export async function generateLayerMetadata(
  layer: GenerateLayerMetadataRequest
): Promise<GeneratedLayerMetadataResponse> {
  const res = await fetch("/api/layers/generate-metadata", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(layer),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `יצירת התיאור והתגיות נכשלה (${res.status})`);
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
