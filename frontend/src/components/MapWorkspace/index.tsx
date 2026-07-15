"use client";

import dynamic from "next/dynamic";
import { Crosshair, Layers3, Radio } from "lucide-react";
import type { GeographyMode } from "@/types/geo-query";
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
export default function MapWorkspace(props: LeafletMapProps) {
  const hint = DRAW_HINTS[props.mode];
  const featureCount = props.resultFeatures?.features.length ?? 0;
  const scopeLabel = props.mode === "viewport" ? "תחום תצוגה" :
    props.mode === "polygon" ? "פוליגון" : "מלבן";

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
      {hint && <div className="map-draw-hint">{hint}</div>}
    </main>
  );
}
