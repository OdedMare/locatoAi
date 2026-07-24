/** Mirrors backend/app/service/catalog_router.py — keep in sync. */

import type { GeoJSONMultiPolygon } from "@/types/geo-query";

export type CubesQueryMode = "auto" | "match_not" | "legacy";
export type FlapiResourceType = "cube" | "package";

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
  flapi_resource_type?: FlapiResourceType;
  cubes_query_mode?: CubesQueryMode;
  cubes_parameters?: Record<string, string>;
  cubes_dynamic_parameters?: Record<string, string>;
  package_parameters?: Record<string, unknown>;
  package_query?: string | null;
  entity_field?: string;
  tyche_geometry_field?: string;
  tyche_geo_query_field?: string;
  tyche_time_field?: string;
  tyche_entity_field?: string;
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
  flapi_resource_type?: FlapiResourceType;
  cubes_query_mode?: CubesQueryMode;
  cubes_parameters?: Record<string, string>;
  cubes_dynamic_parameters?: Record<string, string>;
  package_parameters?: Record<string, unknown>;
  package_query?: string | null;
  cubes_sample_boundary?: GeoJSONMultiPolygon | null;
  tyche_geometry_field?: string;
  tyche_geo_query_field?: string;
  tyche_time_field?: string;
  tyche_entity_field?: string;
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
  configurable_parameters: FlapiParameterDefinition[];
  requires_sample_polygon: boolean;
}

export interface FlapiParameterDefinition {
  name: string;
  display_name: string;
  description: string;
  type: string;
  required: boolean;
  single_value: boolean;
  ontology_type: string;
  has_default: boolean;
  dynamic: boolean;
  options: string[];
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
