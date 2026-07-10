"use client";

import type { GeographyMode } from "@/types/geo-query";

const MODES: { value: GeographyMode; label: string; hint: string }[] = [
  { value: "none", label: "No boundary", hint: "Search everywhere" },
  { value: "viewport", label: "Map viewport", hint: "Use the visible map area" },
  { value: "polygon", label: "Draw polygon", hint: "Click points, then the first point" },
  { value: "rectangle", label: "Draw rectangle", hint: "Click and drag" },
];

interface GeographyControlsProps {
  mode: GeographyMode;
  onModeChange: (mode: GeographyMode) => void;
  /** Whether a shape has been drawn for the current mode. */
  hasDrawnGeometry: boolean;
}

/** Geography scoping mode selector (none / viewport / polygon / rectangle). */
export default function GeographyControls({
  mode,
  onModeChange,
  hasDrawnGeometry,
}: GeographyControlsProps) {
  const needsDrawing = mode === "polygon" || mode === "rectangle";

  return (
    <div className="geography-controls">
      <span className="field-label">Geographic area</span>
      <div className="mode-grid" role="radiogroup" aria-label="Geography mode">
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            role="radio"
            aria-checked={mode === m.value}
            className={`mode-option${mode === m.value ? " selected" : ""}`}
            onClick={() => onModeChange(m.value)}
          >
            <span className="mode-label">{m.label}</span>
            <span className="mode-hint">{m.hint}</span>
          </button>
        ))}
      </div>
      {needsDrawing && (
        <p className={`draw-status${hasDrawnGeometry ? " done" : ""}`}>
          {hasDrawnGeometry
            ? "✓ Shape captured — redraw on the map to replace it."
            : mode === "polygon"
              ? "Click points on the map, then click the first point to finish."
              : "Click and drag across the map to draw a rectangle."}
        </p>
      )}
    </div>
  );
}
