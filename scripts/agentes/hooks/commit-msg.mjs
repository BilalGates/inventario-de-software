// git commit-msg del kit — Conventional Commits. Avisa, nunca bloquea.
import { readFileSync } from "node:fs";

let mensaje = "";
try {
  mensaje = readFileSync(process.argv[2], "utf8");
} catch {
  process.exit(0);
}

const asunto = mensaje.split("\n").find((l) => l.trim() && !l.startsWith("#")) || "";
const avisos = [];
if (!/^(Merge|Revert) /.test(asunto) && !/^(feat|fix|refactor|perf|docs|chore|test|build|ci|style)(\([\w./-]+\))?!?: \S/.test(asunto)) {
  avisos.push(`asunto fuera de Conventional Commits: "${asunto}" → <tipo>(<alcance>): <descripcion>`);
}
if (asunto.length > 72) avisos.push(`asunto de ${asunto.length} caracteres (maximo 72)`);

if (avisos.length) process.stderr.write(`\n[agentes] Mensaje de commit:\n  ${avisos.join("\n  ")}\nAviso, no bloquea.\n\n`);
process.exit(0);
