import "./timelines.css";

import { useState } from "react";

import { Card, Loading, Tabs } from "@/components/common/ui";
import { useT } from "@/i18n/LanguageProvider";

import { TIMELINES, type TimelineProps } from "./timelineRegistry";

/** Tabbed host for every chart in timelineRegistry.tsx. */
export function TimelinePanel({ field, comparison, initial }: TimelineProps & { initial?: string }) {
  const { t } = useT();
  const [tab, setTab] = useState(initial ?? TIMELINES[0].id);
  const def = TIMELINES.find((t) => t.id === tab) ?? TIMELINES[0];
  return (
    <Card title={t("Seasons and exposure")} subtitle={t(def.question)}>
      <Tabs label={t("Timeline views")} tabs={TIMELINES.map((tl) => ({ id: tl.id, label: t(tl.label) }))} value={def.id} onChange={setTab} />
      <div style={{ paddingTop: 16 }} className="fade-in" key={def.id}>
        {def.needsComparison && !comparison ? <Loading label="Simulating rotations" height={260} /> : <def.Component field={field} comparison={comparison} />}
      </div>
    </Card>
  );
}
