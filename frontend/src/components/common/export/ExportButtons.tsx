import { Link } from "react-router-dom";

import { useKebunda } from "@/hooks/useKebunda";
import { useT } from "@/i18n/LanguageProvider";
import type { CompareResponse, FieldOverview } from "@/types/api";

import { downloadText, EXPORT_TEMPLATES } from "./briefTemplates";

/** Buttons for every template in briefTemplates.ts, plus the printable page. */
export function ExportButtons({ field, comparison, showPrintLink = true }: { field: FieldOverview; comparison: CompareResponse; showPrintLink?: boolean }) {
  const { reviewed } = useKebunda();
  const { t, lang } = useT();
  const ctx = { field, comparison, reviewed, lang };
  return (
    <div className="export-menu no-print">
      {showPrintLink
        ? <Link className="btn btn-primary" to={`/field/${field.id}/brief`}>{t("Open printable Field Brief")}</Link>
        : <button className="btn btn-primary" onClick={() => window.print()}>{t("Print or save as PDF")}</button>}
      {EXPORT_TEMPLATES.map((tpl) => (
        <button key={tpl.id} className="btn" onClick={() => downloadText(tpl.filename(ctx), tpl.mime, tpl.build(ctx))}>{t(tpl.label)}</button>
      ))}
    </div>
  );
}
