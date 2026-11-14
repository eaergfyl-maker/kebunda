import { TileLayer } from "react-leaflet";

import { resolveTileUrl, type BaseLayerDef, type MapLayerDef } from "./layerRegistry";

/** One NASA overlay. `key` forces Leaflet to reload tiles when the layer or date changes. */
export function NasaLayer({ layer, date, opacity }: { layer: MapLayerDef; date: string; opacity: number }) {
  const url = resolveTileUrl(layer, date);
  return (
    <TileLayer
      key={url} url={url} opacity={opacity} maxNativeZoom={layer.maxNativeZoom} maxZoom={18}
      attribution={layer.attribution ?? "NASA EOSDIS GIBS"} zIndex={300} crossOrigin
      // GIBS answers 404 for tiles outside a swath or before data arrives: show nothing rather than a broken image
      errorTileUrl="data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=="
    />
  );
}

export function BaseLayer({ layer }: { layer: BaseLayerDef }) {
  return <TileLayer key={layer.id} url={layer.url} attribution={layer.attribution} maxNativeZoom={layer.maxNativeZoom} maxZoom={18} zIndex={100} />;
}
