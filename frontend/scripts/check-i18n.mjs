// Lists every literal t("...") key in src/ that has no Bahasa Malaysia entry in src/i18n/ms.ts,
// and every ms.ts entry no longer used by a literal key (it may still be used for API text).
//   npm run i18n:check            missing keys only
//   npm run i18n:check -- --all   also list unused entries
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const SRC = new URL("../src/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? walk(p) : /\.tsx?$/.test(name) ? [p] : [];
  });
}

const unescape = (s) => s.replace(/\\"/g, '"').replace(/\\\\/g, "\\");
const keyRe = /(?<![\w.])(?:t\(|translate\(lang,)\s*"((?:[^"\\]|\\.)*)"/g;

const used = new Map();
for (const file of walk(SRC)) {
  if (file.includes(`${join("i18n", "ms.ts")}`)) continue;
  // Skip comments so usage examples in doc blocks are not counted.
  const text = readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  for (const m of text.matchAll(keyRe)) {
    const key = unescape(m[1]);
    if (!used.has(key)) used.set(key, file.slice(SRC.length));
  }
}

const ms = readFileSync(join(SRC, "i18n", "ms.ts"), "utf8");
const entries = new Set([...ms.matchAll(/^\s*"((?:[^"\\]|\\.)*)":\s*"/gm)].map((m) => unescape(m[1])));

const missing = [...used].filter(([k]) => !entries.has(k));
for (const [k, f] of missing) console.log(`missing  ${JSON.stringify(k)}  (${f})`);
if (process.argv.includes("--all")) {
  for (const k of entries) if (!used.has(k)) console.log(`unused   ${JSON.stringify(k)}`);
}
console.log(`\n${used.size} literal keys, ${entries.size} Malay entries, ${missing.length} missing.`);
process.exit(missing.length ? 1 : 0);
