import { Layers } from "lucide-react";
import { LAYERS } from "./consts";

interface LayerPickerProps {
  activeLayer: string;
  onLayerChange: (id: string) => void;
}

export default function LayerPicker({
  activeLayer,
  onLayerChange,
}: LayerPickerProps) {
  return (
    <div className="map-layer-picker" aria-label="סגנון מפה">
      <div className="map-layer-picker-label">
        <Layers size={15} aria-hidden="true" />
        שכבות רקע
      </div>
      <div className="map-layer-options">
        {LAYERS.map((layer) => (
          <button
            key={layer.id}
            type="button"
            className={`map-layer-option ${activeLayer === layer.id ? "active" : ""}`}
            onClick={() => onLayerChange(layer.id)}
            aria-pressed={activeLayer === layer.id}
            title={layer.name}
          >
            {/* Remote tile thumbnails intentionally bypass Next image processing. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={layer.previewUrl} alt="" />
            <span>{layer.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
