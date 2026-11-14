/**
 * Colours and labels needed in JavaScript (SVG charts, map styling). Mirrors tokens.css.
 * Use these instead of hard-coding hex values so charts and CSS stay in step.
 */
import type { Access, CropKind, DimensionId, HazardId, StrategyRole } from "@/types/api";

export const DIM_COLOR: Record<DimensionId, string> = {
  water: "#2f7fa3", soil: "#8a5a3c", erosion: "#4f8f4a", pest: "#9a5ba0", income: "#c9952b",
};
export const DIM_SHORT: Record<DimensionId, string> = {
  water: "Water", soil: "Soil health", erosion: "Soil cover", pest: "Pest break", income: "Income",
};
export const DIM_ICON: Record<DimensionId, string> = { water: "💧", soil: "🌱", erosion: "🛡️", pest: "🔁", income: "💵" };

export const HAZARD_COLOR: Record<HazardId, string> = {
  storm: "#2c6e91", heat: "#c8553d", frost: "#7c9cc4", drought: "#c98b2a", leaching: "#7a5ea8",
};
export const HAZARD_SHORT: Record<HazardId, string> = {
  storm: "Hard rain on bare soil", heat: "Heat stress", frost: "Frost", drought: "Water shortage", leaching: "Nitrogen loss",
};

/** One colour per plant functional group: the four groups a diverse rotation mixes. */
export const GROUP_COLOR: Record<string, string> = {
  cool_grass: "#d9a441", warm_grass: "#e07b39", cool_broadleaf: "#5aa9a3", warm_broadleaf: "#6a9f4c",
};
export const GROUP_LABEL: Record<string, string> = {
  cool_grass: "Cool-season grass", warm_grass: "Warm-season grass",
  cool_broadleaf: "Cool-season broadleaf", warm_broadleaf: "Warm-season broadleaf",
};
export const BARE_COLOR = "#b08a63";
export const FALLOW_COLOR = "#d8c7ac";

export const ROLE_COLOR: Record<StrategyRole, string> = {
  baseline: "#6b7570", step: "#4f8f4a", match: "#1f3a2b", resilient: "#2f7fa3", income: "#c9952b", custom: "#9a5ba0",
};

export const ACCESS_LABEL: Record<Access, { label: string; tone: "good" | "info" | "warn" | "bad"; help: string }> = {
  live: { label: "Live", tone: "good", help: "Pulled from the provider for this field." },
  cache: { label: "Live (cached)", tone: "good", help: "Pulled from the provider earlier and stored." },
  curated: { label: "Curated", tone: "info", help: "Assembled from published sources, not measured at this field." },
  proxy: { label: "Stand-in", tone: "warn", help: "A related NASA product is standing in for the named one." },
  unavailable: { label: "Missing", tone: "bad", help: "Could not be retrieved. Results that depend on it are less certain." },
  model: { label: "Modelled", tone: "info", help: "Computed by FieldShift from the observed layers." },
};

export const KIND_LABEL: Record<CropKind, string> = { cash: "Cash crop", cover: "Cover crop", forage: "Forage", perennial: "Perennial" };

export const CHART = {
  ink: "#1d2b22", soft: "#45544a", faint: "#76827a", rule: "#d9cfbb", grid: "#e6dece", paper: "#fbf8f1",
  precip: "#2f7fa3", imerg: "#5aa9c9", ground: "#1f3a2b", et: "#c9952b", temp: "#c8553d", ndvi: "#4f8f4a", moisture: "#3a8fb7",
};

/** Sequential scale for the vulnerability grid: paper to the hazard colour. */
export function riskFill(hex: string, value: number): string {
  const v = Math.max(0, Math.min(1, value));
  if (v < 0.04) return "transparent";
  const alpha = 0.12 + 0.88 * v;
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha.toFixed(2)})`;
}

export function scoreTone(score: number): "good" | "warn" | "bad" {
  return score >= 66 ? "good" : score >= 40 ? "warn" : "bad";
}
