#!/usr/bin/env node
/**
 * Propone grupos de commit para el arbol de trabajo actual, sin tocar nada.
 *
 * Lo usa Larry al cerrar la sesion: la agrupacion es determinista (por dominio
 * y tipo de fichero) y el modelo solo ajusta los dudosos y redacta mensajes.
 * Asi commitear cuesta segundos, no minutos de razonamiento.
 *
 *   node scripts/agentes/agrupar-commits.mjs          # texto legible
 *   node scripts/agentes/agrupar-commits.mjs --json   # para scripts
 *
 * No hace `git add` ni `git commit`: solo lee `git status` y `git diff --numstat`.
 */
import { execFileSync } from "node:child_process";

const git = (...a) => execFileSync("git", a, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"] });

// ── 1. Ficheros cambiados (indice + arbol + nuevos sin seguimiento) ─────────
const estado = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
  .split("\0")
  .filter(Boolean);

const ficheros = [];
for (let i = 0; i < estado.length; i++) {
  const linea = estado[i];
  const xy = linea.slice(0, 2);
  let ruta = linea.slice(3);
  // En renombrados, -z pone el origen en la entrada siguiente.
  if (xy[0] === "R" || xy[0] === "C") i++;
  const nuevo = xy === "??" || xy.includes("A");
  const borrado = xy.includes("D");
  ficheros.push({ ruta, nuevo, borrado, xy });
}

// Cabecera de estado: rama, distancia a la base (sin fetch, al ultimo conocido)
// y ultimos commits. Asi una sola llamada basta para commitear o para responder
// "como esta mi rama".
const intentar = (...a) => {
  try {
    return git(...a).trim();
  } catch {
    return "";
  }
};
const rama = intentar("branch", "--show-current") || "(HEAD suelto)";
const base = intentar("rev-parse", "--verify", "--quiet", "origin/main") ? "origin/main" : "";
const [detras, delante] = base ? intentar("rev-list", "--left-right", "--count", `${base}...HEAD`).split(/\s+/) : [];
console.log(`Rama ${rama}${base ? ` · ${delante} por delante / ${detras} por detras de ${base} (ultimo fetch)` : ""}`);
// Repo recien creado: sin HEAD, ni log ni diff contra HEAD.
console.log(`Ultimos commits:\n${(intentar("log", "-5", "--format=%h %s") || "(ninguno)").replace(/^/gm, "  ")}`);
console.log("");

if (!ficheros.length) {
  console.log("Arbol limpio: nada que commitear.");
  process.exit(0);
}

// ── 2. Clasificar cada fichero: tipo probable + alcance ────────────────────
const esTest = (r) => /(^|\/)(__tests__|tests?|e2e)\//.test(r) || /\.(test|spec)\.[cm]?[jt]sx?$/.test(r);
const esDocs = (r) => /^docs\//.test(r) || (/\.md$/.test(r) && !/^\.agents\//.test(r));
const esChore = (r) =>
  /^(scripts|\.github|\.agents|\.claude|\.codex|\.opencode|\.githooks)\//.test(r) ||
  /(^|\/)(package\.json|pnpm-lock\.yaml|tsconfig[^/]*\.json|[^/]*\.config\.[cm]?[jt]s|\.env[^/]*example)$/.test(r) ||
  /^(AGENTS|CLAUDE)\.md$/.test(r);
const esDb = (r) => /^db\//.test(r);

function alcance(r) {
  let m;
  if ((m = r.match(/^src\/modules\/([^/]+)/))) return m[1];
  if ((m = r.match(/^src\/app\/(?:\([^/]+\)\/)*([^/[(]+)/))) return m[1];
  if ((m = r.match(/(?:__tests__|tests?)\/(?:[^/]+\/)*?([a-z][\w-]*?)(?:[.-][\w.-]*)?\.(?:test|spec)\./))) return m[1];
  if ((m = r.match(/^src\/(lib|components|hooks|i18n|locales)\b/))) return m[1];
  if (esDb(r)) return "baseline";
  if ((m = r.match(/^docs\/(?:[^/]+\/)?([^/.]+)/))) return m[1];
  if ((m = r.match(/^scripts\/([^/.]+)/))) return m[1];
  // La fuente de los agentes y sus copias generadas son la misma unidad.
  if (/^\.(agents|claude|codex|opencode|githooks)\/|^(AGENTS|CLAUDE)\.md$/.test(r)) return "agentes";
  return "";
}

function tipo(f) {
  const r = f.ruta;
  // Herramientas primero: `.agents/skills/tests/` no es un test.
  if (esChore(r)) return "chore";
  if (esTest(r)) return "test";
  if (esDocs(r)) return "docs";
  if (f.nuevo) return "feat";
  return "feat|fix|refactor"; // modificado: lo decide el diff
}

// ── 3. Agrupar: los tests y la db se pegan al codigo de su mismo alcance ────
const grupos = new Map();
const clave = (t, a) => `${t}::${a}`;
const tiposCodigo = (t) => t !== "test" && t !== "docs" && t !== "chore";

const clasif = ficheros.map((f) => ({ ...f, tipo: tipo(f), alcance: alcance(f.ruta) }));
const alcancesConCodigo = new Set(clasif.filter((f) => tiposCodigo(f.tipo)).map((f) => f.alcance));

for (const f of clasif) {
  let t = f.tipo;
  // Un test o una pieza de db del mismo dominio que un cambio de codigo va con el.
  if (t === "test" && alcancesConCodigo.has(f.alcance)) t = "codigo";
  if (tiposCodigo(t)) t = "codigo";
  const k = clave(t, f.alcance);
  if (!grupos.has(k)) grupos.set(k, { tipo: t, alcance: f.alcance, ficheros: [] });
  grupos.get(k).ficheros.push(f);
}

// Tipo final del grupo de codigo: feat si todo es nuevo, si no lo decide el diff.
for (const g of grupos.values()) {
  if (g.tipo !== "codigo") continue;
  const cod = g.ficheros.filter((f) => tiposCodigo(f.tipo));
  g.tipo = cod.length && cod.every((f) => f.nuevo) ? "feat" : "feat|fix|refactor";
}

// Lineas cambiadas por fichero, para que Larry sepa que diffs mirar.
const numstat = new Map();
for (const l of intentar("diff", "HEAD", "--numstat").split("\n").filter(Boolean)) {
  const [mas, menos, ruta] = l.split("\t");
  numstat.set(ruta, `+${mas}/-${menos}`);
}

// Orden por dependencia: db → codigo → test → chore → docs.
const peso = (g) => (g.alcance === "baseline" ? 0 : g.tipo === "test" ? 2 : g.tipo === "chore" ? 3 : g.tipo === "docs" ? 4 : 1);
const lista = [...grupos.values()].sort((a, b) => peso(a) - peso(b) || a.alcance.localeCompare(b.alcance));

// Plan del repo tocado: avisar para que vaya con el commit que cierra trabajo.
const planes = ficheros.map((f) => f.ruta).filter((r) => /(^|\/)(plan[\w-]*|ruta[\w-]*|roadmap|todo)\.md$/i.test(r));

if (process.argv.includes("--json")) {
  console.log(JSON.stringify({ grupos: lista, planes }, null, 2));
  process.exit(0);
}

console.log(`${ficheros.length} fichero(s) en ${lista.length} grupo(s) propuesto(s):\n`);
lista.forEach((g, i) => {
  const t = g.tipo.includes("|") ? `<${g.tipo}>` : g.tipo;
  console.log(`${i + 1}. ${t}${g.alcance ? `(${g.alcance})` : ""}`);
  for (const f of g.ficheros) {
    const marca = f.borrado ? "D" : f.nuevo ? "A" : "M";
    console.log(`     ${marca} ${f.ruta}  ${numstat.get(f.ruta) ?? ""}`);
  }
});
if (planes.length) {
  console.log(`\nPlan tocado (${planes.join(", ")}): va dentro del commit que cierra el trabajo, no en un docs aparte.`);
}
console.log("\n<feat|fix|refactor> = modificados: decide el tipo mirando solo esos diffs.");
