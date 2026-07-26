"use client";

import { useEffect, useState } from "react";
import { MapContainer, ZoomControl, useMapEvents } from "react-leaflet";
import type { Map as LeafletMapInstance } from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";
import LayerPicker from "./LayerPicker";
import MapGeoms from "./MapGeoms";
import MapLayers from "./MapLayers";
import MapResults from "./MapResults";
import type {
  BBox,
  GeographyMode,
  GeoJSONPolygon,
  MapViewState,
} from "@/types/geo-query";

export interface LeafletMapProps {
  mode: GeographyMode;
  drawnGeometry: GeoJSONPolygon | null;
  initialView: MapViewState;
  /** Query results to draw + zoom to (null = nothing to show). */
  resultFeatures: GeoJSON.FeatureCollection | null;
  resultDisplayField?: string | null;
  /** Reports center/zoom/bbox whenever the user pans or zooms. */
  onViewChange: (view: MapViewState) => void;
  /** Called when the user finishes drawing a polygon or rectangle. */
  onGeometryDrawn: (geometry: GeoJSONPolygon, bbox: BBox) => void;
}

function readView(map: LeafletMapInstance): MapViewState {
  const center = map.getCenter();
  const bounds = map.getBounds();
  return {
    center: [center.lng, center.lat],
    zoom: map.getZoom(),
    bbox: [
      bounds.getWest(),
      bounds.getSouth(),
      bounds.getEast(),
      bounds.getNorth(),
    ],
  };
}

/** Reports the map view (center/zoom/bbox) on mount and after every pan/zoom. */
function ViewReporter({ onViewChange }: { onViewChange: (v: MapViewState) => void }) {
  const map = useMapEvents({
    moveend: () => onViewChange(readView(map)),
  });
  useEffect(() => {
    onViewChange(readView(map));
  }, [map, onViewChange]);
  return null;
}

export default function LeafletMap({
  mode,
  drawnGeometry,
  initialView,
  resultFeatures,
  resultDisplayField,
  onViewChange,
  onGeometryDrawn,
}: LeafletMapProps) {
  const [activeLayerId, setActiveLayerId] = useState("orthophoto");

  return (
    <MapContainer
      center={[initialView.center[1], initialView.center[0]]}
      zoom={initialView.zoom}
      className="leaflet-map"
      zoomControl={false}
      minZoom={5}
      maxZoom={19}
      worldCopyJump={false}
    >
      <MapLayers activeLayerId={activeLayerId} />
      <ViewReporter onViewChange={onViewChange} />
      <MapGeoms
        mode={mode}
        value={drawnGeometry}
        onChange={onGeometryDrawn}
      />
      <MapResults
        features={resultFeatures}
        displayField={resultDisplayField}
      />
      <LayerPicker activeLayer={activeLayerId} onLayerChange={setActiveLayerId} />
      <ZoomControl position="bottomleft" />
    </MapContainer>
  );
}
