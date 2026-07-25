/** Mirrors backend/app/service/catalog_router.py — keep in sync. */

import type { GeoJSONMultiPolygon } from "@/types/geo-query";

export interface CatalogLayer {
  id: string;
  name: string;
  description: string;
  tags: string[];
  entity_field?: string | null;
  display_field?: string | null;
  profiles: string[];
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
  package_parameters?: Record<string, unknown>;
  package_query?: string | null;
  package_input_parameter?: string | null;
  package_output_fields?: string[];
  entity_field?: string;
  display_field?: string;
  profiles?: string[];
  tyche_geometry_field?: string;
  tyche_geo_query_field?: string;
  tyche_time_field?: string;
  tyche_entity_field?: string;
  tyche_time_from_field?: string;
  tyche_time_to_field?: string;
  tyche_parameters?: Record<string, string>;
}

export interface UpdateLayerRequest {
  name: string;
  description: string;
  tags: string[];
  entity_field?: string | null;
  display_field?: string | null;
  profiles?: string[];
}

export interface LayerFieldsResponse {
  layer_id: string;
  fields: string[];
}

export interface GenerateLayerMetadataRequest {
  name: string;
  provider: string;
  source_url: string;
  package_parameters?: Record<string, unknown>;
  package_query?: string | null;
  package_input_parameter?: string | null;
  cubes_sample_boundary?: GeoJSONMultiPolygon | null;
  tyche_geometry_field?: string;
  tyche_geo_query_field?: string;
  tyche_time_field?: string;
  tyche_entity_field?: string;
  tyche_time_from_field?: string;
  tyche_time_to_field?: string;
  tyche_parameters?: Record<string, string>;
}

export interface GeneratedLayerMetadataResponse {
  description: string;
  tags: string[];
  sample_count: number;
  dynamic_parameters: string[];
  configurable_parameters: FlapiParameterDefinition[];
  requires_sample_polygon: boolean;
  output_fields: string[];
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
