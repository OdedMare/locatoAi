import { useEffect, useRef } from "react";
import L from "leaflet";
import { FeatureGroup, GeoJSON, useMap } from "react-leaflet";
import { EditControl } from "react-leaflet-draw";
import type { GeographyMode, GeoJSONPolygon } from "@/types/geo-query";

interface MapGeomsProps {
  mode: GeographyMode;
  value: GeoJSONPolygon | null;
  onChange: (
    geometry: GeoJSONPolygon,
    bbox: [number, number, number, number]
  ) => void;
}

function bboxForGeometry(geometry: GeoJSONPolygon): [number, number, number, number] {
  const points = geometry.coordinates.flat();
  const lngs = points.map(([lng]) => lng);
  const lats = points.map(([, lat]) => lat);
  return [Math.min(...lngs), Math.min(...lats), Math.max(...lngs), Math.max(...lats)];
}

export default function MapGeoms({ mode, value, onChange }: MapGeomsProps) {
  const featureGroupRef = useRef<L.FeatureGroup>(null);
  const activeDrawRef = useRef<L.Draw.Feature | null>(null);
  const map = useMap();

  useEffect(() => {
    featureGroupRef.current?.clearLayers();

    activeDrawRef.current?.disable();
    activeDrawRef.current = null;

    const shapeOptions = {
      color: "#ff776b",
      fillColor: "#ff776b",
      fillOpacity: 0.3,
    };

    // leaflet-draw's published types incorrectly model its augmented Map as a
    // subclass. At runtime this is the same Leaflet map instance.
    const drawMap = map as unknown as L.DrawMap;

    if (mode === "polygon") {
      activeDrawRef.current = new L.Draw.Polygon(drawMap, {
        allowIntersection: false,
        showArea: true,
        shapeOptions,
      });
    } else if (mode === "rectangle") {
      activeDrawRef.current = new L.Draw.Rectangle(drawMap, { shapeOptions });
    }

    activeDrawRef.current?.enable();

    return () => {
      activeDrawRef.current?.disable();
      activeDrawRef.current = null;
    };
  }, [map, mode]);

  const handleCreated = (event: L.DrawEvents.Created) => {
    const feature = (event.layer as L.Polygon).toGeoJSON() as GeoJSON.Feature<GeoJSON.Polygon>;
    if (feature.geometry.type !== "Polygon") return;

    featureGroupRef.current?.clearLayers();
    onChange(feature.geometry as GeoJSONPolygon, bboxForGeometry(feature.geometry as GeoJSONPolygon));
  };

  const drawEnabled = mode === "polygon" || mode === "rectangle";

  return (
    <>
      <FeatureGroup ref={featureGroupRef}>
        {drawEnabled && (
          <EditControl
            position="bottomleft"
            onCreated={handleCreated}
            edit={{ edit: false, remove: false }}
            draw={{
              marker: false,
              polyline: false,
              circle: false,
              circlemarker: false,
              polygon:
                mode === "polygon"
                  ? {
                      allowIntersection: false,
                      showArea: true,
                      shapeOptions: { color: "#ff776b", fillColor: "#ff776b" },
                    }
                  : false,
              rectangle:
                mode === "rectangle"
                  ? { shapeOptions: { color: "#ff776b", fillColor: "#ff776b" } }
                  : false,
            }}
          />
        )}
      </FeatureGroup>
      {value && (
        <GeoJSON
          key={JSON.stringify(bboxForGeometry(value))}
          data={value}
          style={{ color: "#ff776b", fillColor: "#ff776b", fillOpacity: 0.3 }}
        />
      )}
    </>
  );
}
