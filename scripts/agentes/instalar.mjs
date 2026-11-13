#!/usr/bin/env node
/**
 * Instala o actualiza el kit de agentes en el proyecto actual:
 *
 *   filigranas                                  # alias de la linea de abajo
 *   node ~/repositorios/filigranas/kit-agentes/scripts/agentes/instalar.mjs
 *
 * 0. Si se lanza desde el kit, copia el kit a la raiz del proyecto. Un AGENTS.md
 *    propio pasa a .agents/proyecto.md; un .githooks propio no se toca.
 * 1. Activa los git hooks del kit (`core.hooksPath .githooks`).
 * 2. Crea CLAUDE.md apuntando a AGENTS.md si no existe; si existe, avisa.
 * 3. Genera los agentes de Claude Code, Codex y OpenCode (sincronizar.mjs).
 * 4. Recuerda el siguiente paso: la induccion de Pep.
 *
 * No borra nada del proyecto.
 */
import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const git = (...a) => {
  try {
    return execFileSync("git", a, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return null;
  }
};

// Desde cualquier subcarpeta: se instala en la raiz del repo.
const raiz = git("rev-parse", "--show-toplevel");
if (raiz) process.chdir(raiz);

const KIT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
if (KIT.startsWith(`${process.cwd()}/`)) {
  console.error("!!  Este es el repo que contiene el kit: lanza filigranas en otro proyecto.");
  process.exit(1);
}
if (KIT !== process.cwd()) {
  const DEL_KIT = "# AGENTS.md — equipo y forma de trabajar";
  if (existsSync("AGENTS.md") && !readFileSync("AGENTS.md", "utf8").startsWith(DEL_KIT)) {
    if (existsSync(".agents/proyecto.md")) {
      console.error("!!  Hay un AGENTS.md propio y ya existe .agents/proyecto.md: fusionalos a mano y repite.");
      process.exit(1);
    }
    mkdirSync(".agents", { recursive: true });
    renameSync("AGENTS.md", ".agents/proyecto.md");
    console.log("ok  tu AGENTS.md pasa a .agents/proyecto.md (manda sobre lo generico)");
  }
  // Skills grandes y de nicho: solo si se piden (`filigranas impeccable supabase`)
  // o si el proyecto ya las tenía (actualizar).
  const OPCIONALES = { impeccable: "impeccable", supabase: "supabase-postgres-best-practices" };
  const pedidas = process.argv.slice(2).map((a) => OPCIONALES[a] ?? a);
  const fuera = Object.values(OPCIONALES).filter((s) => !pedidas.includes(s) && !existsSync(join(".agents/skills", s)));
  const copiar = (s) => basename(s) !== ".DS_Store" && !fuera.some((o) => s === join(KIT, ".agents/skills", o));
  for (const p of [".agents", "scripts/agentes", "AGENTS.md", ...(existsSync(".githooks") ? [] : [".githooks"])]) {
    cpSync(join(KIT, p), p, { recursive: true, filter: copiar });
  }
  console.log(`ok  kit copiado desde ${KIT}${fuera.length ? ` (sin opcionales: ${Object.keys(OPCIONALES).filter((k) => fuera.includes(OPCIONALES[k])).join(", ")})` : ""}`);
}

const hooksPrevios = git("config", "core.hooksPath");
if (git("rev-parse", "--is-inside-work-tree") !== "true") {
  console.log("--  no es un repositorio git: hooks sin activar");
} else if (hooksPrevios && hooksPrevios !== ".githooks") {
  // husky u otro gestor: no se pisa.
  console.log(`!!  core.hooksPath ya es ${hooksPrevios}: hooks del kit sin activar (llama a scripts/agentes/hooks/*.mjs desde los tuyos)`);
} else {
  git("config", "core.hooksPath", ".githooks");
  console.log("ok  git hooks activados (.githooks)");
}

const IMPORT = "@AGENTS.md\n@.agents/proyecto.md\n";
if (!existsSync("CLAUDE.md")) {
  writeFileSync("CLAUDE.md", `# CLAUDE.md\n\nLa fuente principal es AGENTS.md, comun a Claude Code, Codex, OpenCode y Antigravity.\n\n${IMPORT}`);
  console.log("ok  CLAUDE.md creado (apunta a AGENTS.md)");
} else if (!readFileSync("CLAUDE.md", "utf8").includes("@AGENTS.md")) {
  console.log("!!  Ya existe CLAUDE.md: pasa sus reglas a .agents/proyecto.md durante la induccion y dejalo en:\n" + IMPORT);
}

execFileSync(process.execPath, ["scripts/agentes/sincronizar.mjs"], { stdio: "inherit" });

console.log(`
Siguiente paso: abre el proyecto con tu herramienta (Claude Code, Codex, OpenCode
o Antigravity) y pide: "Pep, haz la induccion del proyecto".
Pep creara .agents/proyecto.md y te propondra las skills del proyecto.`);
