// git pre-commit del kit. Si el proyecto define `.agents/reglas.mjs` (lo crea
// Pep en la induccion cuando hay reglas comprobables), se le pasa cada fichero
// preparado. Contrato: `export default (ruta, texto) => string[]` de avisos.
// Avisa, nunca bloquea.
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const reglas = resolve(".agents/reglas.mjs");
if (!existsSync(reglas)) process.exit(0);

try {
  const revisar = (await import(pathToFileURL(reglas).href)).default;
  // -z: sin él git escapa rutas no ASCII ("dise\303\261o.md") y no se pueden leer.
  const preparados = execFileSync("git", ["diff", "--cached", "--name-only", "-z", "--diff-filter=AMR"], { encoding: "utf8" })
    .split("\0")
    .filter(Boolean);
  const avisos = [];
  for (const ruta of preparados) {
    let texto = "";
    try {
      texto = readFileSync(ruta, "utf8");
    } catch {
      continue;
    }
    const hallazgos = revisar(ruta, texto) || [];
    if (hallazgos.length) avisos.push(`${ruta}:\n${hallazgos.map((h) => `  ${h}`).join("\n")}`);
  }
  if (avisos.length) process.stderr.write(`\n[agentes] Reglas del proyecto:\n${avisos.join("\n")}\nAviso, no bloquea.\n\n`);
} catch (e) {
  // Un hook nunca falla, pero unas reglas rotas no pueden callar para siempre.
  process.stderr.write(`\n[agentes] .agents/reglas.mjs falló: ${e.message}\nAviso, no bloquea.\n\n`);
}
process.exit(0);
