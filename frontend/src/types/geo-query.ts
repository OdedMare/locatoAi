/**
 * Core types for the Geo-AI query request pipeline.
 *
 * GeoQueryRequest/GeoQueryResponse mirror the backend contract exactly
 * (backend/app/service/dto.py). Do not change one side without the other.
 */

/** How the user scopes the query geographically (UI concept only). */
export type GeographyMode = "none" | "viewport" | "polygon" | "rectangle";

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
  boundaries: GeoJSONMultiPolygon | null;
}

/** Agent trace: one layer the model selected for the query. */
export interface SelectedLayer {
  id: string;
  name: string;
  tags: string[];
  description: string;
}

/** Backend response (backend/app/service/dto.py QueryResponse). */
export interface GeoQueryResponse {
  status: "ok" | "clarify" | "error";
  clarify: string | null;
  /** The Geo Query Plan the agent built (Day 2+). */
  plan: unknown | null;
  /** GeoJSON FeatureCollection of results. */
  features: GeoJSON.FeatureCollection | null;
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
