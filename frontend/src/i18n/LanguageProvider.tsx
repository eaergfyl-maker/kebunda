/**
 * Interface language: English or Bahasa Malaysia.
 *
 * The English text is the translation key. Wrap any visible string in t():
 *
 *   const { t } = useT();
 *   <h2>{t("Rotations")}</h2>
 *   <p>{t("Searched {n} crop sequences", { n: 120 })}</p>
 *
 * then add the Malay text to i18n/ms.ts under exactly the same English key. A string with no
 * entry shows in English, so a missing translation never breaks a page.
 *
 * Text written by the backend (field stories, explanations, risks) is not translated here;
 * crop and rotation names are, through tName().
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { MS, MS_NAME_PARTS } from "./ms";

export type Lang = "en" | "ms";
type Vars = Record<string, string | number>;

const STORAGE_KEY = "kebunda.lang";

function fill(text: string, vars?: Vars): string {
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

/** Translate outside React (export templates, plain functions). */
export function translate(lang: Lang, text: string, vars?: Vars): string {
  return fill(lang === "ms" ? MS[text] ?? text : text, vars);
}

/** Crop and rotation names from the API: swap known crop names and phrases inside the string. */
export function translateName(lang: Lang, name: string): string {
  if (lang !== "ms" || !name) return name;
  if (MS[name]) return MS[name];
  let out = name;
  for (const [en, ms] of MS_NAME_PARTS) if (out.includes(en)) out = out.split(en).join(ms);
  return out;
}

interface LangState {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (text: string, vars?: Vars) => string;
  tName: (name: string) => string;
  /** BCP 47 locale for dates. */
  locale: string;
}

const Ctx = createContext<LangState | null>(null);

function loadLang(): Lang {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === "ms" || v === "en" ? v : "en";
  } catch {
    return "en";
  }
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(loadLang);

  useEffect(() => {
    document.documentElement.lang = lang === "ms" ? "ms" : "en";
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* private mode: the choice lasts for this visit only */
    }
  }, []);

  const value = useMemo<LangState>(() => ({
    lang,
    setLang,
    t: (text, vars) => translate(lang, text, vars),
    tName: (name) => translateName(lang, name),
    locale: lang === "ms" ? "ms-MY" : "en-MY",
  }), [lang, setLang]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useT(): LangState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useT must be used inside <LanguageProvider>");
  return ctx;
}

/** Month names and initials in the current language, for chart axes and tooltips. */
export function useMonths(): { months: string[]; initials: string[] } {
  const { lang } = useT();
  return lang === "ms" ? { months: MONTHS_MS, initials: MONTH_INITIALS_MS } : { months: MONTHS_EN, initials: MONTH_INITIALS_EN };
}

const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_INITIALS_EN = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
export const MONTHS_MS = ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ogo", "Sep", "Okt", "Nov", "Dis"];
export const MONTH_INITIALS_MS = ["J", "F", "M", "A", "M", "J", "J", "O", "S", "O", "N", "D"];
