/**
 * Timeline tabs. The Timelines panel renders whatever is registered here.
 *
 * OWNER: Member 2.
 *
 * To add a chart: write a component that takes TimelineProps and add one entry to TIMELINES.
 * It gets its own tab. You have the whole field overview and the current comparison to draw from:
 *
 *   field.climate.monthly / .annual / .trends     24-year NASA POWER summary
 *   field.series.*                                year-by-month grids (rain, wetness, heat days)
 *   field.vegetation / surface_temperature / evapotranspiration   MODIS products by month and year
 *   field.fusion.*                                fused rainfall, soil moisture, layer inventory
 *   field.hazards.months                          hazard calendar
 *   comparison.strategies[i].months / .vulnerability / .history   per-rotation simulation output
 *
 * TODO (Member 2), high-impact additions:
 *   - Animated seasonal NDVI scrubber synced with the map date (lift `date` into useFieldShift).
 *   - CoCoRaHS rain-gauge vs. GPM IMERG comparison (see SatelliteVsGround.tsx).
 *   - GRACE-FO groundwater trend view (see ClimateRecord.tsx).
 *   - Soil-water tank animation: strategy.months[i].soil_water_frac through the rotation.
 */
import type { ComponentType } from "react";

import type { CompareResponse, FieldOverview } from "@/types/api";

import { ClimateRecord } from "./ClimateRecord";
import { SatelliteVsGround } from "./SatelliteVsGround";
import { SeasonYear } from "./SeasonYear";
import { VulnerabilityCalendar } from "./VulnerabilityCalendar";
import { SoilWaterThroughRotation } from "./SoilWaterThroughRotation";
import { NetReturnByYear } from "./NetReturnByYear";

export interface TimelineProps {
  field: FieldOverview;
  /** Null until the rotation comparison has loaded. */
  comparison: CompareResponse | null;
}

export interface TimelineDef {
  id: string;
  label: string;
  /** One line shown under the tabs. */
  question: string;
  /** Show a loading state instead of the component until the comparison is ready. */
  needsComparison?: boolean;
  Component: ComponentType<TimelineProps>;
}

export const TIMELINES: TimelineDef[] = [
  {
    id: "vulnerability", label: "Bare-field calendar", question: "When is the soil exposed, and what is falling on it then?", needsComparison: true,
    Component: ({ field, comparison }) => <VulnerabilityCalendar field={field} strategies={comparison!.strategies} />,
  },
  { id: "season", label: "A year on this field", question: "How do rain, heat and greenness move through the seasons?", Component: ({ field }) => <SeasonYear field={field} /> },
  { id: "record", label: "24-year record", question: "What has changed since 2001, and is the change real?", Component: ({ field }) => <ClimateRecord field={field} /> },
  {
    id: "ground", label: "Satellite vs. ground", question: "How far can a pixel be trusted for one field?",
    Component: ({ field, comparison }) => <SatelliteVsGround field={field} validation={comparison?.strategies[0]?.calendar_validation} />,
  },
    {
    id: "soilwater", label: "Soil water", question: "Does the soil stay supplied with water through each rotation?", needsComparison: true,
    Component: ({ comparison }) => <SoilWaterThroughRotation strategies={comparison!.strategies} />,
  },
  {
    id: "returns", label: "Money by year", question: "How much does each rotation's income swing from year to year?", needsComparison: true,
    Component: ({ comparison }) => <NetReturnByYear strategies={comparison!.strategies} />,
  },
];
