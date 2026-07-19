"use client";

import { useCallback, useEffect, useState } from "react";
import QueryPanel from "@/components/QueryPanel";
import MapWorkspace from "@/components/MapWorkspace";
import SettingsPanel from "@/components/SettingsPanel";
import LayersPanel from "@/components/LayersPanel";
import { submitQuery } from "@/services/geoQueryService";
import {
  bboxToMultiPolygon,
  polygonToMultiPolygon,
  type GeographyMode,
  type GeoJSONMultiPolygon,
  type GeoJSONPolygon,
  type GeoQueryRequest,
  type GeoQueryResponse,
  type MapViewState,
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
  const [geographyMode, setGeographyMode] = useState<GeographyMode>("viewport");
  const [drawnGeometry, setDrawnGeometry] = useState<GeoJSONPolygon | null>(null);
  const [mapView, setMapView] = useState<MapViewState>(INITIAL_VIEW);
  const [lastRequest, setLastRequest] = useState<GeoQueryRequest | null>(null);
  const [lastResponse, setLastResponse] = useState<GeoQueryResponse | null>(null);
  const [lastDisplayQuery, setLastDisplayQuery] = useState("");
  const [history, setHistory] = useState<Array<{
    request: GeoQueryRequest;
    response: GeoQueryResponse;
    displayQuery: string;
  }>>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isLayersOpen, setIsLayersOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

  const drawnSampleBoundary: GeoJSONMultiPolygon | null = drawnGeometry
    ? polygonToMultiPolygon(drawnGeometry)
    : null;
  const viewportSampleBoundary = bboxToMultiPolygon(mapView.bbox);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const savedTheme = window.localStorage.getItem("locato-theme");
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      setIsDarkMode(savedTheme ? savedTheme === "dark" : prefersDark);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = isDarkMode ? "dark" : "light";
    window.localStorage.setItem("locato-theme", isDarkMode ? "dark" : "light");
  }, [isDarkMode]);

  const handleModeChange = useCallback((mode: GeographyMode) => {
    setGeographyMode(mode);
    // Any previously drawn shape belongs to the old mode — discard it.
    setDrawnGeometry(null);
  }, []);

  const handleGeometryDrawn = useCallback(
    (geometry: GeoJSONPolygon) => setDrawnGeometry(geometry),
    []
  );

  const handleNewChat = useCallback(() => {
    setQueryText("");
    setGeographyMode("viewport");
    setDrawnGeometry(null);
    setLastRequest(null);
    setLastResponse(null);
    setLastDisplayQuery("");
    setHistory([]);
  }, []);

  /** Build the backend request — exactly {query, boundaries}. */
  const buildRequest = (): GeoQueryRequest => {
    const boundaries = geographyMode === "viewport"
      ? bboxToMultiPolygon(mapView.bbox)
      : drawnGeometry
        ? polygonToMultiPolygon(drawnGeometry)
        : null;
    if (!boundaries) throw new Error("Geographic boundaries are required");
    return { query: queryText.trim(), boundaries };
  };

  const handleRunQuery = async () => {
    const needsDrawing = geographyMode === "polygon" || geographyMode === "rectangle";
    if (!queryText.trim() || isSubmitting || (needsDrawing && !drawnGeometry)) return;
    if (lastRequest && lastResponse) {
      setHistory((turns) => [...turns, {
        request: lastRequest,
        response: lastResponse,
        displayQuery: lastDisplayQuery,
      }].slice(-8));
    }
    const displayQuery = queryText.trim();
    const request = buildRequest();
    if (lastResponse?.status === "clarify" && lastRequest) {
      request.query = `${lastRequest.query}\nUser clarification: ${displayQuery}`;
    }
    setLastDisplayQuery(displayQuery);
    setLastRequest(request);
    setLastResponse(null);
    setQueryText("");
    setIsSubmitting(true);
    try {
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
        lastDisplayQuery={lastDisplayQuery}
        history={history}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenLayers={() => setIsLayersOpen(true)}
        onNewChat={handleNewChat}
        isDarkMode={isDarkMode}
        onToggleTheme={() => setIsDarkMode((dark) => !dark)}
      />
      {isSettingsOpen && (
        <SettingsPanel onClose={() => setIsSettingsOpen(false)} />
      )}
      {isLayersOpen && (
        <LayersPanel
          onClose={() => setIsLayersOpen(false)}
          drawnSampleBoundary={drawnSampleBoundary}
          viewportSampleBoundary={viewportSampleBoundary}
        />
      )}
      <MapWorkspace
        mode={geographyMode}
        drawnGeometry={drawnGeometry}
        resultFeatures={
          lastResponse?.status === "ok" ? lastResponse.features : null
        }
        onViewChange={setMapView}
        onGeometryDrawn={handleGeometryDrawn}
        initialView={INITIAL_VIEW}
        view={mapView}
      />
    </div>
  );
}
