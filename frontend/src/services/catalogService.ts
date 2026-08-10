import { ApiError, request } from "@/services/api";
import type {
  CatalogLayer,
  CreateLayerRequest,
  GeneratedLayerMetadataResponse,
  GenerateLayerMetadataRequest,
  LayersResponse,
  LayerFieldsResponse,
  MqsSyncResponse,
  RemoteMqsLayersResponse,
  UpdateLayerRequest,
} from "@/types/catalog";

export function getLayers(): Promise<LayersResponse> {
  return request<LayersResponse>("/api/layers");
}

export function getLayerFields(layerId: string): Promise<LayerFieldsResponse> {
  return request<LayerFieldsResponse>(
    `/api/layers/${encodeURIComponent(layerId)}/fields`,
    { cache: "no-store" },
  );
}

export function getMqsLayers(): Promise<RemoteMqsLayersResponse> {
  return request<RemoteMqsLayersResponse>("/api/layers/mqs");
}

export function createLayer(layer: CreateLayerRequest): Promise<CatalogLayer> {
  return request<CatalogLayer>("/api/layers", {
    method: "POST",
    body: JSON.stringify(layer),
  });
}

export function updateLayer(
  layerId: string, update: UpdateLayerRequest,
): Promise<CatalogLayer> {
  return request<CatalogLayer>(`/api/layers/${encodeURIComponent(layerId)}`, {
    method: "PUT",
    body: JSON.stringify(update),
  });
}

export async function deleteLayer(layerId: string): Promise<void> {
  await request<unknown>(`/api/layers/${encodeURIComponent(layerId)}`, {
    method: "DELETE",
  });
}

export async function activateTycheLayer(): Promise<CatalogLayer> {
  try {
    return await request<CatalogLayer>("/api/layers/activate-tyche", {
      method: "POST",
    });
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 404) {
      throw new Error(
        "נתיב הפעלת Tyche לא קיים בשרת הפעיל — יש לבנות ולהפעיל מחדש את ה-backend",
      );
    }
    throw reason;
  }
}

export function generateLayerMetadata(
  layer: GenerateLayerMetadataRequest,
): Promise<GeneratedLayerMetadataResponse> {
  return request<GeneratedLayerMetadataResponse>("/api/layers/generate-metadata", {
    method: "POST",
    body: JSON.stringify(layer),
  });
}

export async function syncMqsLayers(): Promise<MqsSyncResponse> {
  try {
    return await request<MqsSyncResponse>("/api/layers/sync-mqs", {
      method: "POST",
    });
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 502) {
      throw new Error(
        "שרת MQS אינו מוגדר או אינו זמין — בדקו את כתובת ה-MQS בהגדרות",
      );
    }
    throw reason;
  }
}
