/**
 * Map layer registry. The map draws whatever this file describes.
 *
 * OWNER: Member 2.
 *
 * Two sources feed the layer list:
 *   1. the backend catalogue of verified NASA GIBS layers (GET /nasa/gibs/layers);
 *   2. EXTRA_LAYERS below, for anything you want to add from the frontend alone.
 *
 * To add a layer, append one object to EXTRA_LAYERS. No other file needs to change: the
 * layer switcher, date scrubber, legend and opacity slider all pick it up.
 *
 *   {
 *     id: "VIIRS_SNPP_L3_NDVI_Monthly", title: "Greenness (VIIRS)", group: "vegetation", mission: "VIIRS",
 *     tileUrl: gibsUrl("VIIRS_SNPP_L3_NDVI_Monthly", "GoogleMapsCompatible_Level7", "png"),
 *     temporal: "monthly", start: "2012-01-01", end: null, maxNativeZoom: 7, resolution_m: 1000,
 *     plain: "Same idea as MODIS greenness, from the newer VIIRS sensor.", legend: null,
 *   }
 *
 * Find identifiers and tile matrix sets in NASA Worldview or the GIBS capabilities document:
 * https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml
 *
 * TODO (Member 2): slope shader. SRTM_Color_Index is elevation; a true slope or hillshade
 *   layer could be drawn client-side from Terrarium/Mapzen elevation tiles with a canvas layer.
 * TODO (Member 2): regional watershed (HUC) and aquifer outlines as GeoJSON layers
 *   (add `kind: "geojson"` to MapLayerDef and render it in layers/NasaLayer.tsx).
 * TODO (Member 2): OpenET and Sentinel-2 NDVI tiles once a key or tile service is chosen.
 */
import type { GibsLayerMeta } from "@/types/api";

export type LayerGroup = "imagery" | "vegetation" | "water" | "heat" | "terrain" | "landscape";
export type Temporal = "daily" | "monthly" | "yearly" | "static";

export interface MapLayerDef {
  id: string;
  title: string;
  group: LayerGroup;
  mission: string;
  /** XYZ template with {z}/{y}/{x} and, for time-varying layers, {time} (YYYY-MM-DD). */
  tileUrl: string;
  temporal: Temporal;
  start: string | null;
  end: string | null;
  /** Deepest zoom the provider serves; Leaflet upscales beyond it. */
  maxNativeZoom: number;
  resolution_m: number;
  /** One sentence a farmer can read. */
  plain: string;
  legend: { unit: string; stops: [number, string][] } | null;
  attribution?: string;
  defaultOpacity?: number;
}

export interface BaseLayerDef {
  id: string;
  title: string;
  url: string;
  attribution: string;
  maxNativeZoom: number;
}

export const GROUP_LABEL: Record<LayerGroup, string> = {
  imagery: "Satellite picture", vegetation: "Crops and cover", water: "Water", heat: "Heat", terrain: "Terrain", landscape: "Surroundings",
};
export const GROUP_ORDER: LayerGroup[] = ["vegetation", "water", "heat", "imagery", "terrain", "landscape"];

const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";
export const gibsUrl = (layer: string, tileMatrixSet: string, ext: string, timed = true) =>
  `${GIBS}/${layer}/default/${timed ? "{time}/" : ""}${tileMatrixSet}/{z}/{y}/{x}.${ext}`;

export const BASE_LAYERS: BaseLayerDef[] = [
  { id: "streets", title: "Roads and towns", url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: "© OpenStreetMap contributors", maxNativeZoom: 19 },
  { id: "bluemarble", title: "NASA Blue Marble", url: gibsUrl("BlueMarble_ShadedRelief_Bathymetry", "GoogleMapsCompatible_Level8", "jpeg", false),
    attribution: "NASA EOSDIS GIBS", maxNativeZoom: 8 },
];

/** Layers added from the frontend. See the header comment for the shape. */
export const EXTRA_LAYERS: MapLayerDef[] = [];

export function buildLayerList(apiLayers: GibsLayerMeta[] | null | undefined): MapLayerDef[] {
  const fromApi: MapLayerDef[] = (apiLayers ?? []).map((l) => ({
    id: l.id, title: l.title, group: l.group, mission: l.mission, tileUrl: l.tile_url, temporal: l.temporal,
    start: l.start, end: l.end, maxNativeZoom: l.max_zoom, resolution_m: l.resolution_m, plain: l.plain,
    legend: l.legend, attribution: l.attribution,
  }));
  const ids = new Set(fromApi.map((l) => l.id));
  return [...fromApi, ...EXTRA_LAYERS.filter((l) => !ids.has(l.id))];
}

const iso = (d: Date) => d.toISOString().slice(0, 10);

/** The most recent date a layer is likely to have imagery for (daily products lag a few days). */
export function latestDate(layer: MapLayerDef, now = new Date()): string {
  const d = new Date(now);
  d.setUTCDate(d.getUTCDate() - (layer.temporal === "daily" ? 4 : 45));
  const candidate = iso(d);
  return layer.end && candidate > layer.end ? layer.end : candidate;
}

/** Snap a requested date to what the layer can serve: inside its record, on its time step. */
export function snapDate(layer: MapLayerDef, date: string): string {
  if (layer.temporal === "static") return layer.start ?? date;
  let d = date;
  const latest = latestDate(layer);
  if (d > latest) d = latest;
  if (layer.start && d < layer.start) d = layer.start;
  if (layer.temporal === "monthly") return `${d.slice(0, 7)}-01`;
  if (layer.temporal === "yearly") return `${d.slice(0, 4)}-01-01`;
  return d;
}

export function resolveTileUrl(layer: MapLayerDef, date: string): string {
  return layer.tileUrl.replace("{time}", snapDate(layer, date));
}

/** Month choices for the date scrubber: the last `count` months, oldest first, mid-month dates. */
export function monthSteps(count = 48, now = new Date()): { date: string; label: string }[] {
  const out: { date: string; label: string }[] = [];
  for (let i = count; i >= 1; i--) {
    const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - i, 15));
    out.push({ date: iso(d), label: d.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" }) });
  }
  return out;
}
