import { Link } from "react-router-dom";

import { useFieldShift } from "@/hooks/useFieldShift";
import type { CompareResponse, FieldOverview } from "@/types/api";

import { downloadText, EXPORT_TEMPLATES } from "./briefTemplates";

/** Buttons for every template in briefTemplates.ts, plus the printable page. */
export function ExportButtons({ field, comparison, showPrintLink = true }: { field: FieldOverview; comparison: CompareResponse; showPrintLink?: boolean }) {
  const { reviewed } = useFieldShift();
  const ctx = { field, comparison, reviewed };
  return (
    <div className="export-menu no-print">
      {showPrintLink
        ? <Link className="btn btn-primary" to={`/field/${field.id}/brief`}>Open printable Field Brief</Link>
        : <button className="btn btn-primary" onClick={() => window.print()}>Print or save as PDF</button>}
      {EXPORT_TEMPLATES.map((t) => (
        <button key={t.id} className="btn" onClick={() => downloadText(t.filename(ctx), t.mime, t.build(ctx))}>{t.label}</button>
      ))}
    </div>
  );
}
