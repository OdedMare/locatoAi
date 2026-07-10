export interface LayerOption {
  id: string;
  name: string;
  url: string;
  previewUrl: string;
  attribution: string;
  maxZoom: number;
}

export const LAYERS: LayerOption[] = [
  {
    id: "orthophoto",
    name: "תצלום אוויר",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    previewUrl: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/6/26/38",
    attribution: "Tiles &copy; Esri and imagery providers",
    maxZoom: 19,
  },
  {
    id: "streets",
    name: "רחובות",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    previewUrl: "https://a.tile.openstreetmap.org/6/38/26.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  },
];
