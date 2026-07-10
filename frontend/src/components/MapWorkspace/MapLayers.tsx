import { TileLayer } from "react-leaflet";
import { LAYERS } from "./consts";

export default function MapLayers({ activeLayerId }: { activeLayerId: string }) {
  const layer = LAYERS.find(({ id }) => id === activeLayerId) ?? LAYERS[0];

  return (
    <TileLayer
      key={layer.id}
      url={layer.url}
      attribution={layer.attribution}
      maxZoom={layer.maxZoom}
    />
  );
}
