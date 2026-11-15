/**
 * Unit formatting. The API is metric, as Malaysian farmers and extension officers work in mm, °C and
 * hectares; the imperial toggle is kept for visiting reviewers. Money is Malaysian ringgit (RM).
 * Always format through this hook so the units toggle works everywhere.
 */
import { useMemo } from "react";

import { useKebunda } from "@/hooks/useKebunda";

const nf = (digits: number) => new Intl.NumberFormat("en-MY", { maximumFractionDigits: digits, minimumFractionDigits: digits });

export function useUnits() {
  const { units } = useKebunda();
  return useMemo(() => {
    const us = units === "us";
    return {
      system: units,
      /** Depth of water: mm, or inches. */
      water: (mm: number, digits?: number) => (us ? `${nf(digits ?? 1).format(mm / 25.4)} in` : `${nf(digits ?? 0).format(mm)} mm`),
      waterValue: (mm: number) => (us ? mm / 25.4 : mm),
      waterUnit: us ? "in" : "mm",
      temp: (c: number, digits = 0) => (us ? `${nf(digits).format((c * 9) / 5 + 32)}°F` : `${nf(digits).format(c)}°C`),
      tempDelta: (c: number) => (us ? `${c >= 0 ? "+" : ""}${nf(1).format((c * 9) / 5)}°F` : `${c >= 0 ? "+" : ""}${nf(1).format(c)}°C`),
      tempValue: (c: number) => (us ? (c * 9) / 5 + 32 : c),
      tempUnit: us ? "°F" : "°C",
      area: (ha: number) => (us ? `${nf(0).format(ha * 2.4711)} acres` : `${nf(0).format(ha)} ha`),
      /** Soil loss arrives in tons/acre/yr. */
      soilLoss: (tonsAc: number) => (us ? `${nf(1).format(tonsAc)} tons/ac` : `${nf(1).format(tonsAc * 2.2417)} t/ha`),
      /** Nitrogen arrives in kg/ha. */
      nitrogen: (kgHa: number) => (us ? `${nf(0).format(kgHa * 0.8922)} lb/ac` : `${nf(0).format(kgHa)} kg/ha`),
      money: (rm: number) => `${rm < 0 ? "−" : ""}RM ${nf(0).format(Math.abs(rm))}`,
      currency: "RM",
      distance: (m: number) =>
        us ? (m >= 1609 ? `${nf(m >= 16090 ? 0 : 1).format(m / 1609.34)} mi` : `${nf(0).format(m * 3.281)} ft`)
           : (m >= 1000 ? `${nf(m >= 10000 ? 0 : 1).format(m / 1000)} km` : `${nf(0).format(m)} m`),
      /** Format a benefit/metric value whose unit string comes from the API. */
      metric: (value: number, unit: string): string => {
        if (unit === "mm/yr") return us ? `${nf(1).format(value / 25.4)} in/yr` : `${nf(0).format(value)} mm/yr`;
        if (unit === "kg N/ha/yr") return us ? `${nf(0).format(value * 0.8922)} lb N/ac` : `${nf(0).format(value)} kg N/ha`;
        if (unit === "tons/ac/yr") return us ? `${nf(1).format(value)} tons/ac` : `${nf(1).format(value * 2.2417)} t/ha`;
        if (unit.startsWith("RM")) return `${value < 0 ? "−" : ""}RM ${nf(0).format(Math.abs(value))}${unit.slice(2)}`;
        if (unit === "%") return `${nf(Math.abs(value) < 10 ? 1 : 0).format(value)}%`;
        if (unit === "% points") return `${value >= 0 ? "+" : ""}${nf(2).format(value)} pts`;
        if (unit === "/100") return `${nf(0).format(value)}/100`;
        return `${nf(Math.abs(value) < 10 ? 1 : 0).format(value)} ${unit}`;
      },
    };
  }, [units]);
}

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const MONTH_INITIALS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
