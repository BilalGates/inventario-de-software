#!/usr/bin/env node
/**
 * Genera la configuracion de agentes y skills de cada herramienta a partir de
 * la fuente unica en `.agents/`:
 *
 *   .agents/agents/<id>/agent.md  ──►  .claude/agents/<id>.md      (Claude Code)
 *                                 ──►  .opencode/agents/<id>.md    (OpenCode)
 *                                 ──►  .codex/agents/<id>.toml     (Codex)
 *                                      (Antigravity lee la fuente directamente)
 *   .agents/skills/<skill>/       ──►  .claude/skills/<skill>      (Claude Code, enlace simbolico)
 *                                      (Codex, OpenCode y Antigravity leen .agents/skills)
 *
 *   node scripts/agentes/sincronizar.mjs           # escribe
 *   node scripts/agentes/sincronizar.mjs --check   # falla si algo esta desincronizado
 *
 * Lo generado lleva una cabecera "GENERADO" y no se edita a mano.
 */
import { existsSync, lstatSync, mkdirSync, readdirSync, readFileSync, readlinkSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = process.cwd();
const FUENTE_AGENTES = join(ROOT, ".agents/agents");
const FUENTE_SKILLS = join(ROOT, ".agents/skills");
const CHECK = process.argv.includes("--check");

// Nivel neutral → modelo/esfuerzo de cada herramienta. Fuente unica compartida con
// `delegar.mjs` de filigrana: cambiar alli y regenerar.
const MODELOS = JSON.parse(readFileSync(join(FUENTE_SKILLS, "filigrana/scripts/niveles.json"), "utf8"));
const NIVEL = Object.fromEntries(
  ["barato", "medio", "fuerte", "maximo"].map((n) => [n, {
    claude: MODELOS.claude[n].modelo,
    codex: MODELOS.codex[n].modelo,
    codexEsfuerzo: MODELOS.codex[n].esfuerzo,
  }]),
);
const AVISO = "GENERADO por scripts/agentes/sincronizar.mjs desde .agents/agents — no editar a mano.";

// ── Fuente ──────────────────────────────────────────────────────────────────
function leerFrontmatter(texto, ruta) {
  const m = texto.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!m) throw new Error(`${ruta}: falta la cabecera YAML`);
  const datos = {};
  for (const linea of m[1].split(/\r?\n/)) {
    const kv = linea.match(/^(\w+):\s*(.*)$/);
    if (!kv) continue;
    let valor = kv[2].trim();
    if (valor.startsWith("[")) valor = valor.slice(1, -1).split(",").map((s) => s.trim()).filter(Boolean);
    datos[kv[1]] = valor;
  }
  for (const campo of ["name", "description", "nivel", "capacidades"]) {
    if (!datos[campo]) throw new Error(`${ruta}: falta el campo \`${campo}\``);
  }
  if (!NIVEL[datos.nivel]) throw new Error(`${ruta}: nivel \`${datos.nivel}\` no es barato|medio|fuerte|maximo`);
  return { ...datos, cuerpo: m[2].trim() };
}

const agentes = readdirSync(FUENTE_AGENTES)
  .filter((id) => existsSync(join(FUENTE_AGENTES, id, "agent.md")))
  .map((id) => {
    const ruta = join(FUENTE_AGENTES, id, "agent.md");
    // Normaliza CRLF: en Windows la fuente puede guardarse con \r\n y lo generado
    // no debe depender del editor que la toco.
    const a = leerFrontmatter(readFileSync(ruta, "utf8").replace(/\r\n/g, "\n"), relative(ROOT, ruta));
    if (a.name !== id) throw new Error(`${relative(ROOT, ruta)}: name \`${a.name}\` no coincide con la carpeta \`${id}\``);
    return a;
  });

const tiene = (a, c) => a.capacidades.includes(c);
const descripcion = (a) => (a.nombre ? `${a.nombre} — ${a.description}` : a.description);
const yamlTexto = (s) => JSON.stringify(s); // JSON es YAML valido y escapa comillas

// ── Generadores por herramienta ─────────────────────────────────────────────
function claude(a) {
  const tools = ["Read", "Grep", "Glob"];
  if (tiene(a, "editar")) tools.push("Edit", "Write");
  if (tiene(a, "shell")) tools.push("Bash");
  if (tiene(a, "red")) tools.push("WebFetch", "WebSearch");
  if (tiene(a, "delegar")) tools.push("Agent");
  return `---
name: ${a.name}
description: ${yamlTexto(descripcion(a))}
tools: ${tools.join(", ")}
model: ${NIVEL[a.nivel].claude}
---

<!-- ${AVISO} -->

${a.cuerpo}
`;
}

function opencode(a) {
  // Sintaxis \`permission\` heredada: la V2 (\`permissions\`) se parsea pero no se aplica (opencode#50598).
  const permitir = (c) => (tiene(a, c) ? "allow" : "deny");
  return `---
description: ${yamlTexto(descripcion(a))}
mode: ${a.name === "pep" ? "all" : "subagent"}
permission:
  edit: ${permitir("editar")}
  bash: ${tiene(a, "shell") ? "allow" : "deny"}
  webfetch: ${permitir("red")}
---

<!-- ${AVISO} -->

${a.cuerpo}
`;
}

function codex(a) {
  const sandbox = tiene(a, "editar") ? "workspace-write" : "read-only";
  // Cadena literal multilinea TOML: no puede contener ''' (se comprueba).
  if (a.cuerpo.includes("'''")) throw new Error(`${a.name}: el cuerpo contiene ''' y rompe el TOML`);
  return `# ${AVISO}
name = ${JSON.stringify(a.name)}
description = ${JSON.stringify(descripcion(a))}
model = "${NIVEL[a.nivel].codex}"
model_reasoning_effort = "${NIVEL[a.nivel].codexEsfuerzo}"
sandbox_mode = "${sandbox}"
developer_instructions = '''
${a.cuerpo}
'''
`;
}

// ── Escritura / comprobacion ────────────────────────────────────────────────
const desfases = [];

function volcar(dir, ext, generar) {
  const esperados = new Map(agentes.map((a) => [`${a.name}.${ext}`, generar(a)]));
  if (!CHECK) mkdirSync(dir, { recursive: true });
  for (const [nombre, contenido] of esperados) {
    const ruta = join(dir, nombre);
    const actual = existsSync(ruta) ? readFileSync(ruta, "utf8").replace(/\r\n/g, "\n") : null;
    if (actual === contenido) continue;
    if (CHECK) desfases.push(relative(ROOT, ruta));
    else writeFileSync(ruta, contenido);
  }
  // Lo que sobra en el destino y no viene de la fuente (agentes retirados).
  // Solo lo generado por el kit: los agentes propios del proyecto no se tocan.
  if (!existsSync(dir)) return;
  for (const nombre of readdirSync(dir)) {
    if (!nombre.endsWith(`.${ext}`) || esperados.has(nombre)) continue;
    if (!readFileSync(join(dir, nombre), "utf8").includes(AVISO)) continue;
    if (CHECK) desfases.push(`${relative(ROOT, join(dir, nombre))} (sobra)`);
    else rmSync(join(dir, nombre));
  }
}

// Cada skill del kit es un enlace simbólico `.claude/skills/<s>` → `.agents/skills/<s>`:
// una entrada en git en vez de una copia de cada fichero. Las skills propias de
// `.claude/skills` no se tocan; el manifiesto `.kit` recuerda cuáles puso el kit.
// ponytail: en Windows sin core.symlinks git deja ficheros de texto; si hay equipo en Windows, volver a copiar.
function espejoSkills(destino) {
  const manifiesto = join(destino, ".kit");
  const skills = readdirSync(FUENTE_SKILLS).filter((n) => statSync(join(FUENTE_SKILLS, n)).isDirectory());
  const antes = existsSync(manifiesto) ? readFileSync(manifiesto, "utf8").split("\n").filter(Boolean) : [];
  const existe = (r) => { try { lstatSync(r); return true; } catch { return false; } };
  const retiradas = antes.filter((s) => !skills.includes(s) && existe(join(destino, s)));
  const lista = `${skills.join("\n")}\n`;

  if (!CHECK) mkdirSync(destino, { recursive: true });
  for (const skill of skills) {
    const dst = join(destino, skill);
    const objetivo = join("../../.agents/skills", skill);
    const bien = existe(dst) && lstatSync(dst).isSymbolicLink() && readlinkSync(dst) === objetivo;
    if (bien) continue;
    if (CHECK) desfases.push(relative(ROOT, dst));
    else {
      rmSync(dst, { recursive: true, force: true }); // copia antigua del kit
      symlinkSync(objetivo, dst);
    }
  }

  if (CHECK) {
    desfases.push(...retiradas.map((s) => `${relative(ROOT, join(destino, s))} (sobra)`));
    if (!existsSync(manifiesto) || readFileSync(manifiesto, "utf8") !== lista) desfases.push(relative(ROOT, manifiesto));
    return;
  }
  for (const s of retiradas) rmSync(join(destino, s), { recursive: true, force: true });
  mkdirSync(destino, { recursive: true });
  writeFileSync(manifiesto, lista);
}

volcar(join(ROOT, ".claude/agents"), "md", claude);
volcar(join(ROOT, ".opencode/agents"), "md", opencode);
volcar(join(ROOT, ".codex/agents"), "toml", codex);
espejoSkills(join(ROOT, ".claude/skills"));

if (CHECK) {
  if (desfases.length) {
    console.error(`Agentes desincronizados (${desfases.length}). Ejecuta \`pnpm agentes:sync\`:`);
    for (const d of desfases) console.error(`  - ${d}`);
    process.exit(1);
  }
  console.log(`ok agentes sincronizados (${agentes.length} agentes).`);
} else {
  console.log(`Sincronizados ${agentes.length} agentes: ${agentes.map((a) => a.nombre ?? a.name).join(", ")}.`);
}
