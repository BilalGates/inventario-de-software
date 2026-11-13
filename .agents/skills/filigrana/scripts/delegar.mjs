#!/usr/bin/env node
/**
 * Lanza una sesión no interactiva en otro motor y devuelve solo su respuesta final.
 *
 *   node delegar.mjs --nivel fuerte --motor codex "encargo"
 *   node delegar.mjs --motor agy --agente aniol "revisa el diff actual"
 *   echo "encargo largo" | node delegar.mjs --motor opencode -
 *
 * --nivel    barato | medio | fuerte | maximo      (por defecto: el de la ficha del agente, o medio)
 * --motor    claude | codex | opencode | agy       (por defecto: claude)
 * --agente   id de una ficha del kit (.agents/agents/<id>/agent.md)
 * --escribir permite editar, en un git worktree nuevo (nunca en el árbol actual)
 * --dir      carpeta de trabajo (por defecto: la actual)
 * --dry      imprime el comando sin ejecutarlo
 *
 * La salida completa queda en $TMPDIR/filigrana/<id>.log.
 */
import { spawnSync, execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const NIVELES = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), "niveles.json"), "utf8"));

const args = process.argv.slice(2);
const opt = {};
const libres = [];
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === "--escribir" || a === "--dry") opt[a.slice(2)] = true;
  else if (a.startsWith("--")) opt[a.slice(2)] = args[++i];
  else libres.push(a);
}

let encargo = libres.join(" ");
if (encargo === "-" || (!encargo && !process.stdin.isTTY)) encargo = readFileSync(0, "utf8");
const fallo = (m) => { console.error(`delegar: ${m}`); process.exit(2); };
if (!encargo.trim()) fallo("falta el encargo");

const motor = opt.motor ?? "claude";
if (!NIVELES[motor]) fallo(`motor \`${motor}\` no es ${Object.keys(NIVELES).filter((k) => k[0] !== "_").join("|")}`);

let dir = resolve(opt.dir ?? ".");
let nivel = opt.nivel;
if (opt.agente) {
  const ficha = join(dir, ".agents/agents", opt.agente, "agent.md");
  if (!existsSync(ficha)) fallo(`no existe ${ficha}`);
  nivel ??= readFileSync(ficha, "utf8").match(/^nivel:\s*(\w+)/m)?.[1];
  encargo = `Actúa según .agents/agents/${opt.agente}/agent.md (léela primero).\n\n${encargo}`;
}
nivel ??= "medio";
const conf = NIVELES[motor][nivel];
if (!conf) fallo(`nivel \`${nivel}\` no es barato|medio|fuerte|maximo`);

// agy en modo plan aborta sin salida si el modelo intenta un comando: se le avisa.
if (motor === "agy" && !opt.escribir) encargo = `Solo lectura: responde directamente, sin plan, y no ejecutes comandos de terminal; usa solo lectura y búsqueda de ficheros.\n\n${encargo}`;

const id = `${motor}-${nivel}-${new Date().toISOString().replace(/\D/g, "").slice(0, 14)}-${process.pid}`; // pid: dos delegaciones en el mismo segundo
const escribir = !!opt.escribir;

if (escribir && !opt.dry) {
  const raiz = execFileSync("git", ["-C", dir, "rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim();
  const destino = join(dirname(raiz), `${basename(raiz)}.filigrana`, id);
  execFileSync("git", ["-C", raiz, "worktree", "add", "-q", "-b", `filigrana/${id}`, destino], { stdio: "inherit" });
  dir = destino;
}

const logs = join(tmpdir(), "filigrana");
mkdirSync(logs, { recursive: true });
const ultimo = join(logs, `${id}.ultimo.txt`);

const comandos = {
  claude: ["claude", "-p", encargo, "--model", conf.modelo, "--permission-mode", escribir ? "acceptEdits" : "plan"],
  codex: ["codex", "exec", "-m", conf.modelo, "-c", `model_reasoning_effort="${conf.esfuerzo}"`,
    "-s", escribir ? "workspace-write" : "read-only", "-C", dir, "--skip-git-repo-check", "-o", ultimo, encargo],
  opencode: ["opencode", "run", "-m", conf.modelo, "--agent", escribir ? "build" : "plan", "--dir", dir, encargo],
  agy: ["agy", "-p", encargo, "--model", conf.modelo, "--effort", conf.esfuerzo, "--mode", escribir ? "accept-edits" : "plan"],
};
const [bin, ...resto] = comandos[motor];

if (opt.dry) {
  const q = (s) => (/^[\w@%+=:,./-]+$/.test(s) ? s : `'${s.replace(/'/g, "'\\''")}'`);
  console.log(`(cd ${q(dir)} && ${[bin, ...resto].map(q).join(" ")})`);
  process.exit(0);
}

const r = spawnSync(bin, resto, { cwd: dir, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], maxBuffer: 1 << 28 });
const log = join(logs, `${id}.log`);
writeFileSync(log, `$ ${bin} …\n\n--- stdout\n${r.stdout ?? ""}\n--- stderr\n${r.stderr ?? ""}\n${r.error ?? ""}`);

// codex deja su último mensaje en un fichero; los demás lo imprimen al final de stdout.
let respuesta = motor === "codex" && existsSync(ultimo) ? readFileSync(ultimo, "utf8") : (r.stdout ?? "");
const lineas = respuesta.trim().split("\n");
if (lineas.length > 150) respuesta = `[… ${lineas.length - 150} líneas recortadas, ver log]\n${lineas.slice(-150).join("\n")}`;

console.log(`## ${motor} · ${nivel} · ${conf.modelo}${conf.esfuerzo ? ` (${conf.esfuerzo})` : ""} · ${escribir ? "escritura" : "solo lectura"}`);
if (escribir) console.log(`worktree: ${dir}  rama: filigrana/${id}`);
console.log(`log: ${log}\n`);
console.log(respuesta.trim() || `(sin respuesta; código ${r.status}${r.error ? `, ${r.error.message}` : ""} — mira el log)`);
process.exit(r.status ?? 1);
