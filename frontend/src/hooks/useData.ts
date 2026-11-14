/**
 * Data hooks: one per backend resource. Import these, never the API client, in components.
 *
 *   const { data, loading, refreshing, error } = useComparison(fieldId);
 *
 * `data` keeps the last good result while a newer one loads, so sliders feel instant.
 */
import { useMemo } from "react";

import { useAsync } from "@/hooks/useAsync";
import { isNeutral, useFieldShift } from "@/hooks/useFieldShift";
import { api } from "@/services/apiClient";
import type { RotationSpec, ScenarioKey, Strategy } from "@/types/api";

export const useFarms = () => useAsync("farms", (s) => api.listFarms(s));
export const useField = (id: string | null) => useAsync(id ? `field:${id}` : null, (s) => api.getField(id!, s));
export const useVulnerability = (id: string | null) => useAsync(id ? `vuln:${id}` : null, (s) => api.getVulnerability(id!, s));
export const useGibsLayers = () => useAsync("gibs", (s) => api.gibsLayers(s));
export const useSources = () => useAsync("sources", (s) => api.sources(s));
export const useCatalog = () => useAsync("catalog", (s) => api.catalog(s));
export const useRotationOptions = () => useAsync("rotation-options", (s) => api.rotationOptions(s));
export const useScenarioPresets = () => useAsync("scenario-presets", (s) => api.scenarioPresets(s));
export const useSuitability = (id: string | null) => useAsync(id ? `suit:${id}` : null, (s) => api.suitability(id!, s));

/** Live NASA POWER summary for a clicked coordinate. Rounded so nearby clicks share a cache entry. */
export function usePowerPoint(point: { lat: number; lon: number } | null) {
  const lat = point ? Math.round(point.lat * 100) / 100 : 0;
  const lon = point ? Math.round(point.lon * 100) / 100 : 0;
  return useAsync(point ? `power:${lat},${lon}` : null, (s) => api.powerPoint(lat, lon, s));
}

/**
 * The main comparison for a field under today's climate, driven by the farmer's priorities,
 * constraints, baseline correction and own rotations (all read from shared state).
 */
export function useComparison(fieldId: string | null) {
  const { priorities, constraints, customStrategies, baselineOverride } = useFieldShift();
  const body = useMemo(
    () => ({
      field_id: fieldId ?? "",
      priorities: Object.keys(priorities).length ? priorities : undefined,
      constraints: Object.keys(constraints).length ? constraints : undefined,
      baseline: baselineOverride ?? undefined,
      custom_strategies: customStrategies.length ? customStrategies : undefined,
    }),
    [fieldId, priorities, constraints, customStrategies, baselineOverride],
  );
  const key = fieldId ? `compare:${JSON.stringify(body)}` : null;
  return useAsync(key, (s) => api.compare(body, s), { debounceMs: 180 });
}

export function toSpecs(strategies: Strategy[]): RotationSpec[] {
  return strategies.map((s) => ({ id: s.id, role: s.role, name: s.name, years: s.years, tillage: s.tillage }));
}

/** Stress-test the compared strategies under the scenario in shared state. Skipped while the scenario is neutral. */
export function useStressTest(fieldId: string | null, strategies: Strategy[] | null) {
  const { scenario, priorities, constraints } = useFieldShift();
  const specs = useMemo(() => (strategies ? toSpecs(strategies) : []), [strategies]);
  const active = Boolean(fieldId && specs.length && !isNeutral(scenario));
  const body = useMemo(
    () => ({
      field_id: fieldId ?? "", strategies: specs, scenario,
      priorities: Object.keys(priorities).length ? priorities : undefined,
      constraints: Object.keys(constraints).length ? constraints : undefined,
    }),
    [fieldId, specs, scenario, priorities, constraints],
  );
  return useAsync(active ? `stress:${JSON.stringify(body)}` : null, (s) => api.stressTest(body, s), { debounceMs: 220 });
}

/** Vary one scenario dial across its range for the compared strategies. */
export function useSweep(fieldId: string | null, strategies: Strategy[] | null, parameter: ScenarioKey | null) {
  const { priorities, constraints } = useFieldShift();
  const specs = useMemo(() => (strategies ? toSpecs(strategies) : []), [strategies]);
  const body = useMemo(
    () => ({
      field_id: fieldId ?? "", strategies: specs, parameter: parameter ?? ("rain_pct" as ScenarioKey), steps: 7,
      priorities: Object.keys(priorities).length ? priorities : undefined,
      constraints: Object.keys(constraints).length ? constraints : undefined,
    }),
    [fieldId, specs, parameter, priorities, constraints],
  );
  const active = Boolean(fieldId && specs.length && parameter);
  return useAsync(active ? `sweep:${JSON.stringify(body)}` : null, (s) => api.sweep(body, s));
}
