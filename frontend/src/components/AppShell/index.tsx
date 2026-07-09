"use client";

import { useCallback, useState } from "react";
import QueryPanel from "@/components/QueryPanel";
import MapWorkspace from "@/components/MapWorkspace";
import { submitQuery } from "@/services/mockGeoQueryService";
import type {
  BBox,
  GeographyMode,
  GeoJSONPolygon,
  GeoQueryRequest,
  GeoQueryResponse,
  MapViewState,
} from "@/types/geo-query";

/** Default view: Tel Aviv. */
const INITIAL_VIEW: MapViewState = {
  center: [34.7818, 32.0853],
  zoom: 12,
  bbox: [34.72, 32.03, 34.85, 32.14],
};

/**
 * AppShell owns all query-building state and lays out the two halves of the
 * app: the query panel on the left and the map workspace on the right.
 */
export default function AppShell() {
  const [queryText, setQueryText] = useState("");
  const [geographyMode, setGeographyMode] = useState<GeographyMode>("none");
  const [drawnGeometry, setDrawnGeometry] = useState<GeoJSONPolygon | null>(null);
  const [drawnBbox, setDrawnBbox] = useState<BBox | null>(null);
  const [mapView, setMapView] = useState<MapViewState>(INITIAL_VIEW);
  const [lastRequest, setLastRequest] = useState<GeoQueryRequest | null>(null);
  const [lastResponse, setLastResponse] = useState<GeoQueryResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleModeChange = useCallback((mode: GeographyMode) => {
    setGeographyMode(mode);
    // Any previously drawn shape belongs to the old mode — discard it.
    setDrawnGeometry(null);
    setDrawnBbox(null);
  }, []);

  const handleGeometryDrawn = useCallback(
    (geometry: GeoJSONPolygon, bbox: BBox) => {
      setDrawnGeometry(geometry);
      setDrawnBbox(bbox);
    },
    []
  );

  /** Build the structured request object from current UI state. */
  const buildRequest = (): GeoQueryRequest => ({
    queryText: queryText.trim(),
    geography: {
      mode: geographyMode,
      geometry:
        geographyMode === "polygon" || geographyMode === "rectangle"
          ? drawnGeometry
          : null,
      bbox:
        geographyMode === "viewport"
          ? mapView.bbox
          : geographyMode === "polygon" || geographyMode === "rectangle"
            ? drawnBbox
            : null,
    },
    uiContext: {
      mapCenter: mapView.center,
      mapZoom: mapView.zoom,
    },
  });

  const handleRunQuery = async () => {
    if (!queryText.trim() || isSubmitting) return;
    const request = buildRequest();
    setLastRequest(request);
    setIsSubmitting(true);
    try {
      // Mock for now — swaps to POST /api/geo-query in the next stage.
      const response = await submitQuery(request);
      setLastResponse(response);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="app-shell">
      <QueryPanel
        queryText={queryText}
        onQueryTextChange={setQueryText}
        geographyMode={geographyMode}
        onGeographyModeChange={handleModeChange}
        hasDrawnGeometry={drawnGeometry !== null}
        onRunQuery={handleRunQuery}
        isSubmitting={isSubmitting}
        lastRequest={lastRequest}
        lastResponse={lastResponse}
      />
      <MapWorkspace
        mode={geographyMode}
        drawnGeometry={drawnGeometry}
        onViewChange={setMapView}
        onGeometryDrawn={handleGeometryDrawn}
        initialView={INITIAL_VIEW}
      />
    </div>
  );
}
