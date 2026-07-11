"use client";

import { useEffect } from "react";
import L from "leaflet";
import { useMap } from "react-leaflet";

interface MapResultsProps {
  features: GeoJSON.FeatureCollection | null;
}

const POINT_STYLE: L.CircleMarkerOptions = {
  radius: 9,
  color: "#be123c",
  weight: 2,
  fillColor: "#fb7185",
  fillOpacity: 0.85,
};

const SHAPE_STYLE: L.PathOptions = {
  color: "#be123c",
  weight: 2,
  fillOpacity: 0.15,
};

/**
 * Draws the query results on the map and zooms to them. Managed
 * imperatively (add/remove on change) — react-leaflet's <GeoJSON> does
 * not update when its data prop changes.
 */
export default function MapResults({ features }: MapResultsProps) {
  const map = useMap();

  useEffect(() => {
    if (!features || features.features.length === 0) return;

    const layer = L.geoJSON(features, {
      pointToLayer: (_feature, latlng) => L.circleMarker(latlng, POINT_STYLE),
      style: () => SHAPE_STYLE,
      onEachFeature: (feature, featureLayer) => {
        const name = feature.properties?.name;
        if (name) featureLayer.bindPopup(String(name));
      },
    }).addTo(map);

    const bounds = layer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.25), { maxZoom: 15 });

    return () => {
      map.removeLayer(layer);
    };
  }, [features, map]);

  return null;
}
