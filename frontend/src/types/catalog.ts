/** Mirrors backend/app/service/catalog_router.py — keep in sync. */

export type CubesQueryMode = "auto" | "match_not" | "legacy";

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
  cubes_query_mode?: CubesQueryMode;
  cubes_dynamic_parameters?: Record<string, string>;
}

export interface UpdateLayerRequest {
  name: string;
  description: string;
  tags: string[];
}

export interface GenerateLayerMetadataRequest {
  name: string;
  provider: string;
  source_url: string;
  cubes_query_mode?: CubesQueryMode;
  cubes_dynamic_parameters?: Record<string, string>;
}

export interface CubesAutocompleteRequest {
  source_url: string;
  parameter_name: string;
}

export interface CubesAutocompleteOption {
  value: string;
  name: string;
}

export interface CubesAutocompleteResponse {
  options: CubesAutocompleteOption[];
}

export interface GeneratedLayerMetadataResponse {
  description: string;
  tags: string[];
  sample_count: number;
  dynamic_parameters: string[];
}

export interface MqsSyncResponse {
  added: number;
  updated: number;
  skipped: number;
  total: number;
}

export interface RemoteMqsLayer extends CreateLayerRequest {
  id: string;
}

export interface RemoteMqsLayersResponse {
  layers: RemoteMqsLayer[];
  count: number;
  skipped: number;
}
