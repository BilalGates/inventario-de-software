/**
 * Piezas visuales comunes a todas las pantallas (rediseño 2026-11):
 * cuadros de estado, franja de KPI con gráficos, chips de filtro.
 * Paleta neutra; el bermellón (`signal`) solo para lo que requiere acción.
 */
import type { ReactNode } from "react";
import { cx } from "./ui";

// ---------------------------------------------------------------- Cuadros de estado
/** La misma leyenda en todas partes: relleno = bien, bermellón = acción, contorno = aviso, discontinuo = manual/pendiente. */
export type DotKind =
  | "ok" | "alert" | "nc" | "alertnc" | "infra"
  | "authorized" | "conditional" | "unauthorized" | "pending"
  | "critical" | "warning" | "info"
  | "success" | "failed" | "running" | "muted";

const DOT: Record<DotKind, string> = {
  ok: "bg-chart-1",
  authorized: "bg-chart-1",
  success: "bg-chart-1",
  alert: "bg-signal-fill",
  unauthorized: "bg-signal-fill",
  critical: "bg-signal-fill",
  failed: "bg-signal-fill",
  nc: "border-2 border-signal-fill",
  warning: "border-2 border-signal-fill",
  alertnc: "bg-signal-fill ring-[1.5px] ring-signal-fill ring-offset-2 ring-offset-surface",
  conditional: "border-2 border-chart-1 bg-[linear-gradient(90deg,rgb(var(--chart-1))_50%,transparent_50%)]",
  infra: "border-[1.5px] border-dashed border-muted",
  pending: "border-[1.5px] border-dashed border-muted",
  info: "border-[1.5px] border-dashed border-muted",
  running: "border-2 border-chart-2",
  muted: "bg-chart-3",
};

export const DOT_LABEL: Partial<Record<DotKind, string>> = {
  ok: "Limpio", alert: "Software no autorizado", nc: "No conforme", alertnc: "No autorizado y no conforme",
  infra: "Infraestructura (inventario manual)", authorized: "Autorizado", conditional: "Con condiciones",
  unauthorized: "No autorizado", pending: "Por decidir",
};

export function StatusDot({ kind, size = "md", title, className }: { kind: DotKind; size?: "sm" | "md" | "lg"; title?: string;
  className?: string }) {
  return (
    <span title={title ?? DOT_LABEL[kind]} aria-hidden={title ? undefined : true}
      className={cx("inline-block shrink-0 box-border",
        size === "sm" ? "size-2.5 rounded-[3px]" : size === "lg" ? "size-[26px] rounded-[7px]" : "size-3.5 rounded-[4px]",
        DOT[kind], className)} />
  );
}

/** Estado de autorización de un producto → cuadro de la leyenda. */
export const authDot = (status: string): DotKind =>
  status === "authorized" ? "authorized" : status === "conditional" ? "conditional"
    : status === "unauthorized" ? "unauthorized" : status === "exception" ? "authorized" : "pending";

// ---------------------------------------------------------------- Franja de KPI
export function KpiStrip({ children, label, className }: { children: ReactNode; label: string; className?: string }) {
  return (
    <section aria-label={label}
      className={cx("grid grid-cols-[repeat(auto-fit,minmax(15rem,1fr))] gap-px overflow-hidden rounded-panel border border-border bg-border",
        className)}>
      {children}
    </section>
  );
}

export function Kpi({ label, children, footer, className }: { label: string; children: ReactNode; footer?: ReactNode;
  className?: string }) {
  return (
    <div className={cx("flex min-w-0 flex-col gap-3.5 bg-surface p-5", className)}>
      <p className="eyebrow">{label}</p>
      {children}
      {footer && <p className="mt-auto text-xs text-muted">{footer}</p>}
    </div>
  );
}

/** Cifra grande con su contexto a continuación. */
export function BigNum({ value, children, tone }: { value: ReactNode; children?: ReactNode; tone?: "signal" }) {
  return (
    <p className={cx("disp text-[30px] font-semibold leading-none", tone === "signal" && "text-signal")}>
      {value}{children && <span className="ml-1.5 font-sans text-sm font-normal tracking-normal text-muted">{children}</span>}
    </p>
  );
}

export interface Segment { label: string; value: number; className: string; strokeClass?: string; tone?: "signal" }

/** Leyenda vertical (cuadro de color · etiqueta · cifra). */
export function Legend({ items, className }: { items: { label: string; value: ReactNode; swatch: ReactNode; tone?: "signal" }[];
  className?: string }) {
  return (
    <ul className={cx("flex flex-col gap-1.5 text-xs", className)}>
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-2">
          {i.swatch}
          <span className={cx("min-w-0 flex-1 truncate", i.tone === "signal" ? "text-signal" : "text-fg-2")}>{i.label}</span>
          <b className={cx("disp", i.tone === "signal" && "text-signal")}>{i.value}</b>
        </li>
      ))}
    </ul>
  );
}

export const Swatch = ({ className }: { className: string }) => <span aria-hidden className={cx("size-2.5 shrink-0 rounded-[3px]", className)} />;

// ---------------------------------------------------------------- Gráficos (SVG/CSS, sin librerías)
const C = 2 * Math.PI * 52;

/** Anillo con el total (u otra cifra) en el centro. Cada segmento lleva `strokeClass` (p. ej. stroke-chart-1). */
export function Donut({ segments, center, caption, label }: { segments: Segment[]; center: ReactNode; caption?: string; label: string }) {
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  let offset = 0;
  return (
    <svg width="128" height="128" viewBox="0 0 128 128" role="img" aria-label={label} className="shrink-0">
      <circle cx="64" cy="64" r="52" fill="none" strokeWidth="14" className="stroke-chart-4" />
      <g transform="rotate(-90 64 64)" fill="none" strokeWidth="14">
        {segments.filter((s) => s.value > 0).map((s) => {
          const len = (s.value / total) * C;
          const el = <circle key={s.label} cx="64" cy="64" r="52" className={s.strokeClass}
            strokeDasharray={`${Math.max(0.5, len - 2)} ${C}`} strokeDashoffset={-offset} />;
          offset += len;
          return el;
        })}
      </g>
      <text x="64" y={caption ? 62 : 72} textAnchor="middle" className="fill-fg font-display text-[26px] font-semibold">{center}</text>
      {caption && <text x="64" y="80" textAnchor="middle" className="fill-muted text-[11px]">{caption}</text>}
    </svg>
  );
}

/** Medidor semicircular segmentado (p. ej. conformes / en gracia / no conformes). */
export function Gauge({ segments, center, label }: { segments: Segment[]; center: ReactNode; label: string }) {
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  const L = Math.PI * 70;
  let offset = 0;
  const d = "M20 94 A70 70 0 0 1 160 94";
  return (
    <div className="relative mx-auto h-[104px] w-[180px]">
      <svg width="180" height="104" viewBox="0 0 180 104" role="img" aria-label={label}>
        <path d={d} fill="none" strokeWidth="16" className="stroke-chart-4" />
        {segments.filter((s) => s.value > 0).map((s) => {
          const len = (s.value / total) * L;
          const el = <path key={s.label} d={d} fill="none" strokeWidth="16" className={s.strokeClass}
            strokeDasharray={`${Math.max(0.5, len - 2)} 400`} strokeDashoffset={-offset} />;
          offset += len;
          return el;
        })}
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">{center}</div>
    </div>
  );
}

/** Barra apilada horizontal. */
export function StackBar({ segments, label, height = "h-3.5" }: { segments: Segment[]; label: string; height?: string }) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  return (
    <div role="img" aria-label={label} className={cx("flex gap-0.5 overflow-hidden rounded-[4px] bg-chart-4", height)}>
      {total > 0 && segments.filter((s) => s.value > 0).map((s) => (
        <span key={s.label} title={`${s.label}: ${s.value}`} className={s.className} style={{ width: `${(s.value / total) * 100}%` }} />
      ))}
    </div>
  );
}

/** Rayado para lo «manual» o «sin fuente» en barras apiladas. */
export const HATCH = "bg-[repeating-linear-gradient(135deg,rgb(var(--chart-3))_0_4px,rgb(var(--chart-4))_4px_8px)]";

/** Un cuadro por elemento (p. ej. un equipo por tipo). */
export function Waffle({ items, label, cols = 11 }: { items: { key: string | number; className: string; title?: string }[];
  label: string; cols?: number }) {
  return (
    <div role="img" aria-label={label} className="grid gap-1" style={{ gridTemplateColumns: `repeat(${cols}, 16px)` }}>
      {items.map((i) => <span key={i.key} title={i.title} className={cx("size-4 rounded-[3px] box-border", i.className)} />)}
    </div>
  );
}

/** Barras verticales mínimas; la última se resalta en señal si `highlightLast`. */
export function Spark({ values, height = 48, highlightLast, label }: { values: number[]; height?: number; highlightLast?: boolean;
  label?: string }) {
  const max = Math.max(1, ...values);
  return (
    <div role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}
      className="flex items-end gap-[3px]" style={{ height }}>
      {values.map((v, i) => (
        <span key={i} className={cx("flex-1 rounded-[2px]", v === 0 ? "bg-chart-4" : highlightLast && i === values.length - 1 ? "bg-signal-fill" : "bg-chart-2")}
          style={{ height: Math.max(3, Math.round((v / max) * height)) }} />
      ))}
    </div>
  );
}

/** Barra fina de proporción con color propio. */
export function Bar({ value, max, className = "bg-chart-1" }: { value: number; max: number; className?: string }) {
  return (
    <span className="block h-1.5 overflow-hidden rounded-[3px] bg-chart-4" aria-hidden>
      <span className={cx("block h-full rounded-[3px]", className)} style={{ width: `${max ? Math.min(100, (value / max) * 100) : 0}%` }} />
    </span>
  );
}

/** Fases del cierre mensual. */
export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol aria-label="Fases" className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
      {steps.map((s, i) => (
        <li key={s} aria-current={i === current ? "step" : undefined} className={cx("flex flex-col gap-1.5 text-2xs",
          i < current ? "text-fg" : i === current ? "font-semibold text-fg" : "text-muted")}>
          <span className={cx("h-1 rounded-sm", i < current ? "bg-chart-1" : i === current ? "bg-signal-fill" : "bg-chart-4")} />
          {s}
        </li>
      ))}
    </ol>
  );
}

// ---------------------------------------------------------------- Filtros
export interface ChipOption<T extends string> { id: T; label: string; count?: number; dot?: DotKind }

/** Chips de filtro de una sola selección (sustituyen a desplegables y pestañas de estado). */
export function FilterChips<T extends string>({ options, value, onChange, label }: { options: ChipOption<T>[]; value: T;
  onChange: (v: T) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((o) => {
        const on = o.id === value;
        return (
          <button key={o.id} type="button" aria-pressed={on} onClick={() => onChange(o.id)}
            className={cx("inline-flex min-h-9 items-center gap-2 whitespace-nowrap rounded-full border px-3.5 text-[13px] font-medium transition-colors",
              on ? "border-fg bg-fg text-bg" : "border-border-strong text-fg-2 hover:border-muted hover:text-fg")}>
            {o.dot && <StatusDot kind={o.dot} size="sm" className={on ? "ring-offset-fg" : undefined} />}
            {o.label}{o.count !== undefined && <span className={on ? "opacity-80" : "text-muted"}>· {o.count.toLocaleString("es-ES")}</span>}
          </button>
        );
      })}
    </div>
  );
}

/** Cabecera de página común: etiqueta, frase con la cifra principal y acciones. */
export function ScreenHeader({ eyebrow, title, sub, actions }: { eyebrow: string; title: ReactNode; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="flex min-w-0 flex-col gap-2">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="disp text-[28px] font-semibold leading-tight sm:text-[34px]">
          {title}{sub && <span className="font-medium text-muted"> {sub}</span>}
        </h1>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
