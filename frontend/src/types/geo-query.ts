/**
 * Core types for the Geo-AI query request pipeline.
 *
 * These types define the contract between the UI and the future backend
 * endpoint (`POST /api/geo-query`). Keep them stable — the AI agent /
 * SQL-generation stage will consume exactly this shape.
 */

/** How the user scopes the query geographically. */
export type GeographyMode = "none" | "viewport" | "polygon" | "rectangle";

/** Minimal GeoJSON Polygon (RFC 7946). Coordinates are [lng, lat]. */
export interface GeoJSONPolygon {
  type: "Polygon";
  /** Array of linear rings; first ring is the outer boundary (closed). */
  coordinates: [number, number][][];
}

/** Bounding box: [minLng, minLat, maxLng, maxLat]. */
export type BBox = [number, number, number, number];

/** Geographic scope attached to a query. */
export interface GeographySelection {
  mode: GeographyMode;
  /** Drawn shape (polygon / rectangle modes). Null otherwise. */
  geometry: GeoJSONPolygon | null;
  /** Bounding box (viewport mode, or derived from a drawn shape). Null otherwise. */
  bbox: BBox | null;
}

/** Map state at submit time — useful context for the agent (e.g. "near me", ambiguous place names). */
export interface UiContext {
  /** [lng, lat] */
  mapCenter: [number, number];
  mapZoom: number;
}

/** The structured request object sent to the (future) geo-query backend. */
export interface GeoQueryRequest {
  queryText: string;
  geography: GeographySelection;
  uiContext: UiContext;
}

/** Mock response shape for this stage. The real backend will return parsed intent + spatial results. */
export interface GeoQueryResponse {
  status: "accepted";
  requestId: string;
  receivedAt: string;
  /** Echo of the submitted request, for debugging. */
  echo: GeoQueryRequest;
  /** Empty in this stage — populated by the GIS execution engine later. */
  results: unknown[];
}

/** Live map view state reported by the map component. */
export interface MapViewState {
  /** [lng, lat] */
  center: [number, number];
  zoom: number;
  /** Current viewport bounds as [minLng, minLat, maxLng, maxLat]. */
  bbox: BBox;
}
