"use client";

import dynamic from "next/dynamic";
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

  return (
    <main className="map-workspace">
      <LeafletMap {...props} />
      {hint && <div className="map-draw-hint">{hint}</div>}
    </main>
  );
}
