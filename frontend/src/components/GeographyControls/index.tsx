"use client";

import type { GeographyMode } from "@/types/geo-query";

const MODES: { value: GeographyMode; label: string; hint: string }[] = [
  { value: "viewport", label: "תצוגת המפה", hint: "שימוש באזור המוצג" },
  { value: "polygon", label: "ציור פוליגון", hint: "לחצו על נקודות ולסיום על הראשונה" },
  { value: "rectangle", label: "ציור מלבן", hint: "לחצו וגררו" },
];

interface GeographyControlsProps {
  mode: GeographyMode;
  onModeChange: (mode: GeographyMode) => void;
  /** Whether a shape has been drawn for the current mode. */
  hasDrawnGeometry: boolean;
}

/** Required geography selector (viewport / polygon / rectangle). */
export default function GeographyControls({
  mode,
  onModeChange,
  hasDrawnGeometry,
}: GeographyControlsProps) {
  const needsDrawing = mode === "polygon" || mode === "rectangle";

  return (
    <div className="geography-controls">
      <span className="field-label">אזור גיאוגרפי</span>
      <div className="mode-grid" role="radiogroup" aria-label="בחירת אזור גיאוגרפי">
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
            ? "הצורה נשמרה — ציירו שוב במפה כדי להחליף אותה."
            : mode === "polygon"
              ? "לחצו על נקודות במפה, ולסיום לחצו על הנקודה הראשונה."
              : "לחצו וגררו על המפה כדי לצייר מלבן."}
        </p>
      )}
    </div>
  );
}
