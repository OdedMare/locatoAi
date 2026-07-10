/** Mirrors backend/app/service/catalog_router.py — keep in sync. */

export interface CatalogLayer {
  id: string;
  name: string;
  description: string;
  tags: string[];
}

export interface LayersResponse {
  layers: CatalogLayer[];
  count: number;
}

export interface CreateLayerRequest {
  name: string;
  description: string;
  tags: string[];
  provider: string;
  source_url: string;
}
