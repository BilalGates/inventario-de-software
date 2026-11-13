#!/usr/bin/env node
/**
 * Detecta patrones de UI "hecha por IA" según reference/gusto.md.
 *   node detectar-slop.mjs [carpeta…]     (por defecto: .)
 * Salida: ruta:línea  regla  sugerencia. Solo avisa; nunca cambia nada.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";

const IGNORAR = new Set(["node_modules", ".git", ".next", "dist", "build", "out", "coverage", ".turbo", ".vercel", ".claude", ".agents"]);
const EXT = new Set([".css", ".scss", ".tsx", ".jsx", ".ts", ".js", ".html", ".vue", ".svelte", ".astro"]);
const MARCADO = new Set([".tsx", ".jsx", ".html", ".vue", ".svelte", ".astro"]);
// Donde no hay CSS variables: imágenes OG, iconos, manifest, emails (estilos en línea).
const SIN_TOKENS = /\/(e-?mails?|mail-templates)\/|(opengraph-image|twitter-image|apple-icon|icon|manifest)\.\w+$/;
const COMENTARIO = /^\s*(\/\/|\/?\*|<!--)/;

// [regla, regex, sugerencia, ¿solo en ficheros de marcado?]
const REGLAS = [
  ["gradiente-ia", /(from|via|to)-(purple|violet|indigo|fuchsia)-\d|gradient\([^)]*(purple|violet|indigo|#8b5cf6|#a855f7|#7c3aed|#6366f1)/i, "gradiente morado/índigo: color plano + un único acento"],
  ["acento-de-stock", /#(3b82f6|2563eb|1d4ed8|6366f1|4f46e5|8b5cf6|7c3aed|a855f7|9333ea|0ea5e9|2f5bea)\b/i, "azul/índigo/violeta de stock de Tailwind: un color propio"],
  ["radio-grande", /\brounded-(xl|2xl|3xl)\b|border-radius:\s*(1[2-9]|[2-9]\d|\d{3,})px/, "radio ≥12px: 2–8px como máximo"],
  ["sombra-estructura", /\bshadow-(lg|xl|2xl)\b/, "sombra grande: filete de 1px; la sombra solo para lo que flota"],
  ["transition-all", /transition:\s*all\b|\btransition-all\b/, "anima una propiedad concreta (transform, opacity)"],
  ["rebote", /animate-bounce|type:\s*["']spring|easeOutBack|cubic-bezier\([^)]*\b1\.\d/, "sin rebotes: cubic-bezier(.22,1,.36,1), 120–240ms"],
  ["slate", /\b(bg|text|border|from|to|via|ring|fill|stroke)-slate-\d|--slate-/, "slate es frío y genérico: grises cálidos o negro"],
  ["texto-gris-claro", /\btext-(gray|neutral|zinc|slate|stone)-(300|400)\b/, "contraste dudoso: oscurece el texto"],
  ["texto-diminuto", /text-\[(?:\d|10)(?:\.\d+)?px\]|font-size:\s*(?:\d|10)(?:\.\d+)?px/, "menos de 11px"],
  ["blob-glow", /\bblur-(2xl|3xl)\b|blur-\[\d{2,}px\]|filter:\s*blur\(\s*\d{2,}px/, "orb/blob/glow decorativo"],
  ["glass", /\bbackdrop-blur(-\w+)?\b|backdrop-filter:\s*blur/, "glassmorphism: solo si es imprescindible"],
  ["fuente-inter", /\bInter\b(?!\s*Tight)|['"]Inter['"]/, "Inter por defecto: justifícalo o elige una pareja propia"],
  ["hex-suelto", /(["'`\[(:]\s*)#[0-9a-fA-F]{3,8}\b/, "color suelto en un componente: usa un token", true],
  ["emoji", /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u, "emoji: icono de trazo o nada", true],
];

function* ficheros(ruta) {
  const st = statSync(ruta);
  if (st.isFile()) { if (EXT.has(extname(ruta))) yield ruta; return; }
  for (const n of readdirSync(ruta)) if (!IGNORAR.has(n) && !n.startsWith(".")) yield* ficheros(join(ruta, n));
}

const raices = process.argv.slice(2).length ? process.argv.slice(2) : ["."];
const hits = [];
for (const raiz of raices) {
  for (const f of ficheros(raiz)) {
    if (SIN_TOKENS.test(f)) continue;
    const marcado = MARCADO.has(extname(f));
    readFileSync(f, "utf8").split("\n").forEach((linea, i) => {
      if (linea.length > 2000 || COMENTARIO.test(linea)) return; // minificado o comentario
      for (const [regla, re, sugerencia, soloMarcado] of REGLAS) {
        if (soloMarcado && !marcado) continue;
        if (re.test(linea)) hits.push([`${relative(".", f)}:${i + 1}`, regla, sugerencia]);
      }
    });
  }
}

const MAX = 200;
const ancho = Math.min(60, Math.max(0, ...hits.slice(0, MAX).map((h) => h[0].length)));
for (const [donde, regla, sug] of hits.slice(0, MAX)) console.log(`${donde.padEnd(ancho)}  ${regla.padEnd(17)}  ${sug}`);
if (hits.length > MAX) console.log(`… ${hits.length - MAX} más`);

const cuenta = {};
for (const [, r] of hits) cuenta[r] = (cuenta[r] ?? 0) + 1;
console.log(hits.length ? `\n${hits.length} avisos: ${Object.entries(cuenta).sort((a, b) => b[1] - a[1]).map(([r, n]) => `${r} ${n}`).join(" · ")}` : "Sin patrones de IA. Limpio.");
