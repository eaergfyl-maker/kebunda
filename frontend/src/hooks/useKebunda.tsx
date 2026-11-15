/**
 * Shared app state: which field is open and what the farmer has told us.
 *
 * Everything a farmer can change lives here (priorities, constraints, scenario, their own
 * rotations, units), so any component in any folder can read or change it without props
 * being threaded through pages. Add new shared state here rather than in a page.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { Constraints, Priorities, RotationSpec, Scenario } from "@/types/api";

export const NEUTRAL_SCENARIO: Scenario = { temp_delta_c: 0, rain_pct: 0, storm_intensity_pct: 0, water_cap_pct: 100 };
export type UnitSystem = "us" | "metric";

interface KebundaState {
  /** Priorities the farmer has moved. Empty means "use this field's defaults". */
  priorities: Partial<Priorities>;
  setPriority: (id: keyof Priorities, value: number) => void;
  setPriorities: (p: Partial<Priorities>) => void;
  constraints: Constraints;
  setConstraint: <K extends keyof Constraints>(key: K, value: Constraints[K] | undefined) => void;
  resetConstraints: () => void;
  scenario: Scenario;
  setScenario: (s: Scenario) => void;
  customStrategies: RotationSpec[];
  setCustomStrategies: (s: RotationSpec[]) => void;
  /** The farmer's correction of the baseline rotation, if any. */
  baselineOverride: RotationSpec | null;
  setBaselineOverride: (s: RotationSpec | null) => void;
  units: UnitSystem;
  setUnits: (u: UnitSystem) => void;
  /** Risk-review checklist ticks, keyed "fieldId:strategyId:riskId". Kept in this browser only. */
  reviewed: Record<string, boolean>;
  toggleReviewed: (key: string) => void;
  /** Clear everything field-specific when another field is opened. */
  resetForField: () => void;
}

const Ctx = createContext<KebundaState | null>(null);

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function KebundaProvider({ children }: { children: ReactNode }) {
  const [priorities, setPrioritiesState] = useState<Partial<Priorities>>({});
  const [constraints, setConstraints] = useState<Constraints>({});
  const [scenario, setScenario] = useState<Scenario>(NEUTRAL_SCENARIO);
  const [customStrategies, setCustomStrategies] = useState<RotationSpec[]>([]);
  const [baselineOverride, setBaselineOverride] = useState<RotationSpec | null>(null);
  const [units, setUnitsState] = useState<UnitSystem>(() => loadJson<UnitSystem>("kebunda.units.my", "metric"));
  const [reviewed, setReviewed] = useState<Record<string, boolean>>(() => loadJson("kebunda.reviewed", {}));

  useEffect(() => {
    try {
      window.localStorage.setItem("kebunda.reviewed", JSON.stringify(reviewed));
    } catch {
      /* private mode: the checklist simply does not persist */
    }
  }, [reviewed]);

  const setUnits = useCallback((u: UnitSystem) => {
    setUnitsState(u);
    try {
      window.localStorage.setItem("kebunda.units.my", JSON.stringify(u));
    } catch {
      /* ignore */
    }
  }, []);

  const setPriority = useCallback((id: keyof Priorities, value: number) => setPrioritiesState((p) => ({ ...p, [id]: value })), []);
  const setConstraint = useCallback(<K extends keyof Constraints>(key: K, value: Constraints[K] | undefined) => {
    setConstraints((c) => {
      const next = { ...c };
      if (value === undefined) delete next[key];
      else next[key] = value;
      return next;
    });
  }, []);
  const toggleReviewed = useCallback((key: string) => setReviewed((r) => ({ ...r, [key]: !r[key] })), []);
  const resetForField = useCallback(() => {
    setPrioritiesState({});
    setConstraints({});
    setScenario(NEUTRAL_SCENARIO);
    setCustomStrategies([]);
    setBaselineOverride(null);
  }, []);

  const value = useMemo<KebundaState>(
    () => ({
      priorities, setPriority, setPriorities: setPrioritiesState, constraints, setConstraint,
      resetConstraints: () => setConstraints({}), scenario, setScenario, customStrategies, setCustomStrategies,
      baselineOverride, setBaselineOverride, units, setUnits, reviewed, toggleReviewed, resetForField,
    }),
    [priorities, setPriority, constraints, setConstraint, scenario, customStrategies, baselineOverride, units, setUnits, reviewed, toggleReviewed, resetForField],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useKebunda(): KebundaState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useKebunda must be used inside <KebundaProvider>");
  return ctx;
}

export function isNeutral(s: Scenario): boolean {
  return s.temp_delta_c === 0 && s.rain_pct === 0 && s.storm_intensity_pct === 0 && s.water_cap_pct === 100;
}
