/**
 * Core types for the Geo-AI query request pipeline.
 *
 * GeoQueryRequest/GeoQueryResponse mirror the backend contract exactly
 * (backend/app/service/dto.py). Do not change one side without the other.
 */

/** How the user scopes the query geographically (UI concept only). */
export type GeographyMode = "viewport" | "polygon" | "rectangle";

/** Minimal GeoJSON Polygon (RFC 7946). Coordinates are [lng, lat]. */
export interface GeoJSONPolygon {
  type: "Polygon";
  /** Array of linear rings; first ring is the outer boundary (closed). */
  coordinates: [number, number][][];
}

/** GeoJSON MultiPolygon — the boundary shape the backend accepts. */
export interface GeoJSONMultiPolygon {
  type: "MultiPolygon";
  coordinates: [number, number][][][];
}

/** Bounding box: [minLng, minLat, maxLng, maxLat]. */
export type BBox = [number, number, number, number];

/** The request sent to POST /api/query — exactly {query, boundaries}. */
export interface GeoQueryRequest {
  query: string;
  boundaries: GeoJSONMultiPolygon;
}

/** Agent trace: one layer the model selected for the query. */
export interface SelectedLayer {
  id: string;
  name: string;
  tags: string[];
  description: string;
}

/** One step of a Geo Query Plan (discriminated by `op` on the backend). */
export interface GeoPlanStep {
  id: string;
  op:
    | "load"
    | "within_geometry"
    | "attribute_filter"
    | "near"
    | "nearest_n"
    | "near_all"
    | "between"
    | "crosses"
    | "touches"
    | "contains"
    | "directional"
    | "temporal_filter"
    | "cluster"
    | "latest_per_entity"
    | "movement_direction"
    | "count";
  input?: string;
  layer?: string;
  target_layer?: string;
  target_field?: string;
  target_operator?: "eq" | "contains";
  target_value?: string | number;
  first_target_layer?: string;
  second_target_layer?: string;
  corridor_width_m?: number;
  first_target_field?: string;
  first_target_operator?: "eq" | "contains";
  first_target_value?: string | number;
  second_target_field?: string;
  second_target_operator?: "eq" | "contains";
  second_target_value?: string | number;
  field?: string;
  operator?: string;
  value?: string | number;
  distance_m?: number;
  targets?: {
    layer: string;
    field?: string;
    operator?: "eq" | "contains";
    value?: string | number;
  }[];
  direction?: "north" | "south" | "east" | "west";
  count?: number;
  from?: string;
  to?: string;
  min_group_size?: number;
  max_distance_m?: number;
  entity_field?: string;
  time_field?: string;
  min_distance_m?: number;
}

/** The plan the agent built (mirrors backend GeoQueryPlan). */
export interface GeoQueryPlanDto {
  explanation: string;
  steps: GeoPlanStep[];
  output: string;
  context_layers: string[];
}

/** Backend response (backend/app/service/dto.py QueryResponse). */
export interface GeoQueryResponse {
  status: "ok" | "clarify" | "error";
  clarify: string | null;
  /** The Geo Query Plan the agent built and executed. */
  plan: GeoQueryPlanDto | null;
  /** GeoJSON FeatureCollection of results. */
  features: GeoJSON.FeatureCollection | null;
  /** Set alongside `features` when the plan ends in a `count` step. */
  scalar_result: number | null;
  timing_ms: Record<string, number> | null;
  token_usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null;
  /** Which catalog layers the agent chose (its "thinking", for review). */
  selected_layers: SelectedLayer[];
  /** The model's short Hebrew reasoning for the choice. */
  reasoning: string;
  /** sample_field rounds the plan builder ran ({layer_id, field} each). */
  tool_calls: { layer_id: string; field: string }[];
  /** Operational pipeline trace (not private model chain-of-thought). */
  pipeline_trace: PipelineTraceEntry[];
}

export interface PipelineTraceEntry {
  stage: "layer_selection" | "plan_building" | "plan_validation" | "execute_step" | "response";
  status: "completed" | "clarify" | "error";
  duration_ms?: number;
  explanation?: string | null;
  attempts?: number;
  tool_calls?: { layer_id: string; field: string }[];
  selected_layer_ids?: string[];
  selected_layer_names?: string[];
  step_id?: string;
  operation?: GeoPlanStep["op"];
  input_count?: number | null;
  output_count?: number;
  parameters?: Record<string, unknown>;
  feature_count?: number;
  scalar_result?: number | null;
  geometry_returned?: boolean;
}

/** Live map view state reported by the map component (UI-internal). */
export interface MapViewState {
  /** [lng, lat] */
  center: [number, number];
  zoom: number;
  /** Current viewport bounds as [minLng, minLat, maxLng, maxLat]. */
  bbox: BBox;
}

/** Wrap a single polygon as the MultiPolygon the backend expects. */
export function polygonToMultiPolygon(
  polygon: GeoJSONPolygon
): GeoJSONMultiPolygon {
  return { type: "MultiPolygon", coordinates: [polygon.coordinates] };
}

/** Convert a viewport bbox to a MultiPolygon boundary. */
export function bboxToMultiPolygon(bbox: BBox): GeoJSONMultiPolygon {
  const [minLng, minLat, maxLng, maxLat] = bbox;
  return {
    type: "MultiPolygon",
    coordinates: [
      [
        [
          [minLng, minLat],
          [maxLng, minLat],
          [maxLng, maxLat],
          [minLng, maxLat],
          [minLng, minLat],
        ],
      ],
    ],
  };
}
