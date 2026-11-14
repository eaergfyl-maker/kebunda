import "./timelines.css";

import { useState } from "react";

import { Card, Loading, Tabs } from "@/components/common/ui";

import { TIMELINES, type TimelineProps } from "./timelineRegistry";

/** Tabbed host for every chart in timelineRegistry.tsx. */
export function TimelinePanel({ field, comparison, initial }: TimelineProps & { initial?: string }) {
  const [tab, setTab] = useState(initial ?? TIMELINES[0].id);
  const def = TIMELINES.find((t) => t.id === tab) ?? TIMELINES[0];
  return (
    <Card title="Seasons and exposure" subtitle={def.question}>
      <Tabs label="Timeline views" tabs={TIMELINES.map((t) => ({ id: t.id, label: t.label }))} value={def.id} onChange={setTab} />
      <div style={{ paddingTop: 16 }} className="fade-in" key={def.id}>
        {def.needsComparison && !comparison ? <Loading label="Simulating rotations" height={260} /> : <def.Component field={field} comparison={comparison} />}
      </div>
    </Card>
  );
}
