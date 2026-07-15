"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { Check, Copy, Crosshair, Layers3, Radio } from "lucide-react";
import type { GeographyMode, MapViewState } from "@/types/geo-query";
import type { LeafletMapProps } from "./LeafletMap";

// Leaflet touches `window` at import time, so it must only load on the client.
const LeafletMap = dynamic(() => import("./LeafletMap"), {
  ssr: false,
  loading: () => <div className="map-loading">המפה נטענת…</div>,
});

const DRAW_HINTS: Partial<Record<GeographyMode, string>> = {
  polygon: "לחצו על נקודות לציור · לסיום לחצו על הנקודה הראשונה",
  rectangle: "לחצו וגררו כדי לצייר מלבן",
};

/** Map area: central visual element. Hosts the Leaflet map and drawing hints. */
interface MapWorkspaceProps extends LeafletMapProps {
  view: MapViewState;
}

function toDms(value: number, positive: string, negative: string): string {
  const absolute = Math.abs(value);
  const degrees = Math.floor(absolute);
  const minutesFloat = (absolute - degrees) * 60;
  const minutes = Math.floor(minutesFloat);
  const seconds = ((minutesFloat - minutes) * 60).toFixed(2);
  return `${degrees}°${minutes}′${seconds}″${value >= 0 ? positive : negative}`;
}

export default function MapWorkspace({ view, ...props }: MapWorkspaceProps) {
  const [copied, setCopied] = useState<string | null>(null);
  const hint = DRAW_HINTS[props.mode];
  const featureCount = props.resultFeatures?.features.length ?? 0;
  const scopeLabel = props.mode === "viewport" ? "תחום תצוגה" :
    props.mode === "polygon" ? "פוליגון" : "מלבן";
  const [lng, lat] = view.center;
  const formats = [
    ["Lat, Lon", `${lat.toFixed(6)}, ${lng.toFixed(6)}`],
    ["Lon, Lat", `${lng.toFixed(6)}, ${lat.toFixed(6)}`],
    ["DMS", `${toDms(lat, "N", "S")} ${toDms(lng, "E", "W")}`],
    ["WKT", `POINT (${lng.toFixed(6)} ${lat.toFixed(6)})`],
  ];

  const copy = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(label);
      window.setTimeout(() => setCopied(null), 1400);
    } catch (error) {
      console.error("Coordinate copy failed", error);
    }
  };

  return (
    <main className="map-workspace">
      <LeafletMap {...props} />
      <div className="map-hud map-hud-top">
        <div className="hud-title"><Crosshair size={15} /> תמונת מצב</div>
        <div className="hud-metric"><span className="hud-live-dot" /> מקורות מחוברים</div>
      </div>
      <div className="map-hud map-hud-bottom">
        <span><Layers3 size={13} /> {featureCount} ישויות מוצגות</span>
        <span><Radio size={13} /> {scopeLabel}</span>
      </div>
      <div className="coordinate-console" dir="ltr">
        <div className="coordinate-console-head">
          <span><Crosshair size={13} /> MAP CENTER</span>
          <small>ZOOM {view.zoom}</small>
        </div>
        <strong>{lat.toFixed(6)}° N&nbsp;&nbsp;{lng.toFixed(6)}° E</strong>
        <div className="coordinate-formats">
          {formats.map(([label, value]) => (
            <button key={label} type="button" onClick={() => copy(label, value)} title={value}>
              {copied === label ? <Check size={11} /> : <Copy size={11} />}{label}
            </button>
          ))}
        </div>
      </div>
      {hint && <div className="map-draw-hint">{hint}</div>}
    </main>
  );
}
