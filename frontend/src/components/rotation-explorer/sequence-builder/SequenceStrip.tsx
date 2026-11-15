/**
 * Read-only picture of a rotation: one column per year, one block per crop.
 * Colour is the crop type; a dashed outline marks a cover crop; a leaf marks a legume.
 *
 * OWNER: Member 3.
 */
import { useT } from "@/i18n/LanguageProvider";
import { FALLOW_COLOR, GROUP_COLOR } from "@/styles/theme";
import type { YearLabel } from "@/types/api";

const shortName = (name: string) => name.replace(/ \(.*\)| cover$| forage$| hay$/g, "").replace("Rye + vetch + radish mix", "Cover mix");

export function SequenceStrip({ years, compact = false }: { years: YearLabel[]; compact?: boolean }) {
  const { t, tName } = useT();
  return (
    <ol className={`seq-strip ${compact ? "is-compact" : ""}`} aria-label={t("Rotation sequence")}>
      {years.map((y, i) => (
        <li key={i} className="seq-year">
          <span className="seq-year-label">{t("Yr {n}", { n: y.year })}</span>
          <div className="seq-blocks">
            {y.fallow ? (
              <span className="seq-block seq-fallow" style={{ background: FALLOW_COLOR }}>{t("Fallow")}</span>
            ) : (
              y.crops.map((c, k) => (
                <span
                  key={k} className={`seq-block ${c.role === "cover" ? "seq-cover" : ""}`} title={`${tName(c.name)}${c.legume ? ` · ${t("fixes nitrogen")}` : ""}${c.role === "cover" ? ` · ${t("cover crop")}` : ""}`}
                  style={{ background: c.role === "cover" ? "transparent" : GROUP_COLOR[c.functional_group] ?? "#aaa", borderColor: GROUP_COLOR[c.functional_group] ?? "#aaa" }}
                >
                  {c.legume && <span aria-hidden>☘ </span>}
                  {shortName(tName(c.name))}
                </span>
              ))
            )}
          </div>
          {i < years.length - 1 && <span className="seq-arrow" aria-hidden>→</span>}
        </li>
      ))}
      <li className="seq-loop" aria-hidden title={t("Then the rotation repeats")}>↻</li>
    </ol>
  );
}
