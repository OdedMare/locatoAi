"use client";

import { useEffect, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Polygon,
  Polyline,
  TileLayer,
  useMapEvents,
} from "react-leaflet";
import type { LatLng, Map as LeafletMapInstance } from "leaflet";
import "leaflet/dist/leaflet.css";
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
  /** Reports center/zoom/bbox whenever the user pans or zooms. */
  onViewChange: (view: MapViewState) => void;
  /** Called when the user finishes drawing a polygon or rectangle. */
  onGeometryDrawn: (geometry: GeoJSONPolygon, bbox: BBox) => void;
}

/** Convert Leaflet [lat, lng] points to a closed GeoJSON ring ([lng, lat]). */
function toGeoJSONPolygon(points: LatLng[]): { geometry: GeoJSONPolygon; bbox: BBox } {
  const ring: [number, number][] = points.map((p) => [p.lng, p.lat]);
  ring.push(ring[0]); // close the ring per GeoJSON spec
  const lngs = points.map((p) => p.lng);
  const lats = points.map((p) => p.lat);
  return {
    geometry: { type: "Polygon", coordinates: [ring] },
    bbox: [
      Math.min(...lngs),
      Math.min(...lats),
      Math.max(...lngs),
      Math.max(...lats),
    ],
  };
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

/**
 * Lightweight click-to-draw implementation (no plugin needed at this stage):
 * - rectangle: click two opposite corners
 * - polygon: click vertices, double-click to finish
 */
function DrawingHandler({
  mode,
  onGeometryDrawn,
}: {
  mode: GeographyMode;
  onGeometryDrawn: LeafletMapProps["onGeometryDrawn"];
}) {
  const [draft, setDraft] = useState<LatLng[]>([]);
  const drawing = mode === "polygon" || mode === "rectangle";

  // Discard an in-progress draft when the mode changes (render-time state
  // adjustment, per React guidance — avoids an extra effect pass).
  const [prevMode, setPrevMode] = useState(mode);
  if (prevMode !== mode) {
    setPrevMode(mode);
    setDraft([]);
  }

  const map = useMapEvents({
    click: (e) => {
      if (mode === "rectangle") {
        if (draft.length === 0) {
          setDraft([e.latlng]);
        } else {
          const [a] = draft;
          const b = e.latlng;
          const corners = [
            { lat: a.lat, lng: a.lng },
            { lat: a.lat, lng: b.lng },
            { lat: b.lat, lng: b.lng },
            { lat: b.lat, lng: a.lng },
          ] as LatLng[];
          const { geometry, bbox } = toGeoJSONPolygon(corners);
          onGeometryDrawn(geometry, bbox);
          setDraft([]);
        }
      } else if (mode === "polygon") {
        setDraft((prev) => [...prev, e.latlng]);
      }
    },
    dblclick: () => {
      if (mode !== "polygon") return;
      // A double-click also fires two `click` events, so drop consecutive
      // duplicate points before closing the shape.
      setDraft((prev) => {
        const points = prev.filter(
          (p, i) => i === 0 || !p.equals(prev[i - 1])
        );
        if (points.length >= 3) {
          const { geometry, bbox } = toGeoJSONPolygon(points);
          onGeometryDrawn(geometry, bbox);
          return [];
        }
        return prev;
      });
    },
  });

  // Drawing UX: crosshair cursor, no accidental double-click zoom.
  useEffect(() => {
    const container = map.getContainer();
    if (drawing) {
      map.doubleClickZoom.disable();
      container.style.cursor = "crosshair";
    } else {
      map.doubleClickZoom.enable();
      container.style.cursor = "";
    }
  }, [drawing, map]);

  if (draft.length === 0) return null;
  return (
    <>
      <Polyline
        positions={draft}
        pathOptions={{ color: "#6366f1", weight: 2, dashArray: "6 4" }}
      />
      {draft.map((p, i) => (
        <CircleMarker
          key={i}
          center={p}
          radius={4}
          pathOptions={{ color: "#6366f1", fillColor: "#fff", fillOpacity: 1 }}
        />
      ))}
    </>
  );
}

export default function LeafletMap({
  mode,
  drawnGeometry,
  initialView,
  onViewChange,
  onGeometryDrawn,
}: LeafletMapProps) {
  // GeoJSON stores [lng, lat]; Leaflet wants [lat, lng].
  const drawnPositions = drawnGeometry?.coordinates[0].map(
    ([lng, lat]) => [lat, lng] as [number, number]
  );

  return (
    <MapContainer
      center={[initialView.center[1], initialView.center[0]]}
      zoom={initialView.zoom}
      className="leaflet-map"
      zoomControl
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ViewReporter onViewChange={onViewChange} />
      <DrawingHandler mode={mode} onGeometryDrawn={onGeometryDrawn} />
      {drawnPositions && (
        <Polygon
          positions={drawnPositions}
          pathOptions={{ color: "#6366f1", weight: 2, fillOpacity: 0.12 }}
        />
      )}
    </MapContainer>
  );
}
