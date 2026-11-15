/**
 * Map overlay plugins: things drawn on top of the tiles (pins, footprints, probes).
 *
 * OWNER: Member 2.
 *
 * An overlay is a React component that renders react-leaflet children. To add one:
 *   1. create overlays/MyOverlay.tsx exporting a component that takes OverlayProps;
 *   2. add one entry to OVERLAYS below.
 * It then appears on the map with its own on/off toggle. Nothing else changes.
 *
 * TODO (Member 2): custom field-boundary drawing. Let the farmer click corners to outline the
 *   field (leaflet-draw or Geoman), compute its area, and pass the centroid and area to
 *   `onAnalyzePoint` so the custom-field request uses the real size.
 * TODO (Member 2): within-field vulnerability overlay. Shade the field by SRTM slope class and
 *   SoilGrids or DOA soil-map polygons to show erosion hot spots.
 * TODO (Member 2): CoCoRaHS / USGS NWIS station markers near the field, linking each gauge
 *   or well to its record, to make the "ground truth" side of the comparison tangible.
 */
import type { ComponentType } from "react";

import type { FarmSummary, FieldOverview } from "@/types/api";

import { FarmPins } from "./FarmPins";
import { PixelFootprints } from "./PixelFootprints";
import { PointProbe } from "./PointProbe";

export interface OverlayProps {
  farms: FarmSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Overview of the open field, when a field page is showing. */
  field: FieldOverview | null;
  /** Coordinate the user last clicked, if any. */
  probe: { lat: number; lon: number } | null;
  setProbe: (p: { lat: number; lon: number } | null) => void;
  /** Ask the app to build a custom field at a coordinate. Undefined when not supported in this view. */
  onAnalyzePoint?: (lat: number, lon: number) => void;
  analyzing?: boolean;
}

export interface OverlayDef {
  id: string;
  label: string;
  /** Short plain-language description for the toggle's tooltip. */
  help: string;
  defaultOn: boolean;
  /** Hide the toggle (and the overlay) unless a field is open. */
  needsField?: boolean;
  Component: ComponentType<OverlayProps>;
}

export const OVERLAYS: OverlayDef[] = [
  { id: "farms", label: "Benchmark farms", help: "Five real Malaysian fields with pre-loaded NASA, Sentinel-2, SoilGrids and FAO GAEZ data.", defaultOn: true, Component: FarmPins },
  { id: "footprints", label: "Satellite pixel sizes", help: "How big one pixel of each dataset is next to this field.", defaultOn: true, needsField: true, Component: PixelFootprints },
  { id: "probe", label: "Click to query NASA POWER", help: "Click anywhere to pull 24 years of NASA climate data for that spot.", defaultOn: true, Component: PointProbe },
];
