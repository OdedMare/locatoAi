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

const TARGET_STYLE: L.CircleMarkerOptions = {
  radius: 8,
  color: "#1d4ed8",
  weight: 2,
  fillColor: "#60a5fa",
  fillOpacity: 0.9,
};

const INTERNAL_PROPERTIES = new Set([
  "nearest_target_feature",
  "matched_reference_features",
  "distance_to_targets_m",
]);

function popupContent(feature: GeoJSON.Feature, title: string): HTMLElement {
  const root = document.createElement("div");
  const heading = document.createElement("strong");
  heading.textContent = title;
  root.appendChild(heading);
  const list = document.createElement("dl");
  Object.entries(feature.properties ?? {}).forEach(([key, value]) => {
    if (INTERNAL_PROPERTIES.has(key)) return;
    const term = document.createElement("dt");
    term.textContent = key;
    const description = document.createElement("dd");
    description.textContent = value == null ? "—" : String(value);
    list.append(term, description);
  });
  root.appendChild(list);
  return root;
}

function centerOf(layer: L.Layer): L.LatLng | null {
  if (layer instanceof L.CircleMarker || layer instanceof L.Marker) {
    return layer.getLatLng();
  }
  if ("getBounds" in layer) {
    const bounds = (layer as L.Polygon).getBounds();
    return bounds.isValid() ? bounds.getCenter() : null;
  }
  return null;
}

/**
 * Draws the query results on the map and zooms to them. Managed
 * imperatively (add/remove on change) — react-leaflet's <GeoJSON> does
 * not update when its data prop changes.
 */
export default function MapResults({ features }: MapResultsProps) {
  const map = useMap();

  useEffect(() => {
    if (!features || features.features.length === 0) return;

    const group = L.featureGroup().addTo(map);
    L.geoJSON(features, {
      pointToLayer: (_feature, latlng) => L.circleMarker(latlng, POINT_STYLE),
      style: () => SHAPE_STYLE,
      onEachFeature: (feature, featureLayer) => {
        featureLayer.bindPopup(popupContent(feature, "ישות שנמצאה"));

        const nearestTarget = feature.properties?.nearest_target_feature as
          | GeoJSON.Feature
          | undefined;
        const matchedTargets = feature.properties?.matched_reference_features as
          | GeoJSON.Feature[]
          | undefined;
        const targets = matchedTargets ?? (nearestTarget ? [nearestTarget] : []);
        targets.forEach((target) => {
          if (!target?.geometry) return;
          const targetLayer = L.geoJSON(target, {
            pointToLayer: (_targetFeature, latlng) =>
              L.circleMarker(latlng, TARGET_STYLE),
            style: { color: "#1d4ed8", weight: 2, fillOpacity: 0.12 },
            onEachFeature: (targetFeature, targetFeatureLayer) => {
              targetFeatureLayer.bindPopup(
                popupContent(targetFeature, "ישות ייחוס")
              );
            },
          });
          targetLayer.eachLayer((item) => {
            group.addLayer(item);
            const from = centerOf(item);
            const to = centerOf(featureLayer);
            if (!from || !to) return;
            L.polyline([from, to], {
              color: "#475569",
              weight: 2,
              dashArray: "6 5",
            }).addTo(group);
            const angle = Math.atan2(to.lat - from.lat, to.lng - from.lng) * 180 / Math.PI;
            L.marker(L.latLng((from.lat + to.lat) / 2, (from.lng + to.lng) / 2), {
              interactive: false,
              icon: L.divIcon({
                className: "map-relation-arrow",
                html: `<span style="display:block;transform:rotate(${-angle}deg)">➤</span>`,
                iconSize: [18, 18],
                iconAnchor: [9, 9],
              }),
            }).addTo(group);
          });
        });
      },
    }).addTo(group);

    const bounds = group.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.25), { maxZoom: 15 });

    return () => {
      map.removeLayer(group);
    };
  }, [features, map]);

  return null;
}
