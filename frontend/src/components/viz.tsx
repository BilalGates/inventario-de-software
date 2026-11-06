/** Piezas visuales compartidas por el Panel y las páginas de inventario (tinta + señal, sin librerías de gráficos). */
import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { DashboardData, FleetDevice, RankedProduct, WeekActivity } from "@/lib/dashboard";
import { COMPLIANCE_LABEL, FRESHNESS_LABEL, fmtNumber, fmtPeriod } from "@/lib/format";
import { EmptyState, cx } from "./ui";

export const pct = (n: number, d: number) => (d ? (n / d) * 100 : 0);
export const fmtPct = (v: number) => v.toLocaleString("es-ES", { maximumFractionDigits: 1 });

export function Swatch({ className }: { className: string }) {
  return <span className={cx("inline-block size-[9px] shrink-0 rounded-[2px]", className)} aria-hidden />;
}

/** Panel blanco con título en Inter Tight y un hueco a la derecha (leyenda o enlace). */
export function Panel({ title, aside, children, className }: { title: string; aside?: ReactNode; children: ReactNode;
  className?: string }) {
  return (
    <section className={cx("card flex min-w-0 flex-col gap-5 p-6", className)} aria-label={title}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="disp text-lg font-semibold tracking-[-0.02em]">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** Barra fina de proporción. */
export function Meter({ value, max, className = "bg-fg", thick }: { value: number; max: number; className?: string; thick?: boolean }) {
  return (
    <span className={cx("block overflow-hidden rounded-sm bg-chart-4", thick ? "h-1.5" : "h-[3px]")} aria-hidden>
      <span className={cx("block h-full rounded-sm", className)} style={{ width: `${Math.min(100, pct(value, max))}%` }} />
    </span>
  );
}

// ------------------------------------------------------------------ Parque: un recuadro por equipo
const TILE: Record<string, string> = {
  current: "bg-fg text-bg",
  stale: "bg-signal-fill text-white",
  never_synced: "border border-border-strong bg-chart-4 text-fg-2",
};

export function FleetTiles({ fleet }: { fleet: FleetDevice[] }) {
  if (fleet.length === 0) return <EmptyState title="Aún no hay equipos registrados" />;
  if (fleet.length > 80) {
    // Por si el parque crece: cuadros sin nombre.
    return (
      <div className="grid grid-cols-[repeat(auto-fill,12px)] gap-[3px]">
        {fleet.map((d) => <span key={d.id} title={d.name} className={cx("size-3 rounded-[2px]", TILE[d.freshness] ?? TILE.never_synced)} />)}
      </div>
    );
  }
  return (
    <ul className="grid grid-cols-[repeat(auto-fill,minmax(8.25rem,1fr))] gap-1.5">
      {fleet.map((d) => {
        const nc = d.compliance === "noncompliant";
        const label = [d.name, FRESHNESS_LABEL[d.freshness], nc && "no conforme", d.department ?? "sin departamento"]
          .filter(Boolean).join(" · ");
        return (
          <li key={d.id}>
            <Link to={`/dispositivos/${d.id}`} title={label} aria-label={label}
              className={cx("relative flex h-9 items-center rounded-[4px] px-2.5 transition-opacity hover:opacity-80",
                TILE[d.freshness] ?? TILE.never_synced,
                !d.department && "outline-dashed outline-1 outline-offset-[3px] outline-chart-2")}>
              <span className="code truncate text-[11px] font-medium">{d.name}</span>
              {nc && <span className={cx("absolute right-1.5 top-1.5 size-1.5 rounded-full",
                d.freshness === "stale" ? "bg-white" : "bg-signal-fill")} aria-hidden />}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function FleetLegend({ d }: { d: DashboardData["devices"] }) {
  const nc = d.compliance.noncompliant ?? 0;
  const items: [ReactNode, string, number, string?][] = [
    [<Swatch className="bg-fg" />, "Al día", d.current, "/dispositivos?freshness=current"],
    [<Swatch className="bg-signal-fill" />, "Sin observar", d.stale, "/dispositivos?freshness=stale"],
    [<Swatch className="border border-border-strong bg-chart-4" />, "Sin fuente automática", d.never_synced, "/dispositivos?freshness=never_synced"],
    [<span className="inline-flex size-[9px] items-center justify-center" aria-hidden><span className="size-1.5 rounded-full bg-signal-fill" /></span>,
      COMPLIANCE_LABEL.noncompliant, nc],
    [<span className="inline-block size-[9px] rounded-[2px] border border-dashed border-chart-2" aria-hidden />, "Sin departamento",
      d.unassigned, "/dispositivos?unassigned=true"],
  ];
  return (
    <dl className="grid grid-cols-[repeat(auto-fit,minmax(8.5rem,1fr))] gap-4 border-t border-border pt-4">
      {items.map(([icon, label, n, to]) => (
        <div key={label}>
          <dt className="flex items-center gap-2 text-xs text-muted">{icon}{label}</dt>
          <dd className="disp mt-1 text-[22px] font-semibold">
            {to ? <Link to={to} className="hover:underline hover:underline-offset-4">{fmtNumber(n)}</Link> : fmtNumber(n)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

// ------------------------------------------------------------------ Cierre mensual (panel oscuro)
const PHASES = ["Recogida", "Revisión", "Cierre", "Informe"];

export function MonthlyClose({ m, reviewCases, className }: { m: DashboardData["monthly"]; reviewCases: number; className?: string }) {
  const sources = Object.entries(m.coverage.sources);
  const essential = sources.filter(([, s]) => s.essential);
  const okCount = essential.filter(([, s]) => s.ok).length;
  const status = m.snapshot?.status;
  const phase = status === "approved" ? 4 : status === "draft" ? 1 : m.coverage.complete ? 1 : 0;
  const [y, mo] = m.period.split("-").map(Number);
  const daysLeft = Math.max(0, Math.ceil((new Date(y, mo, 1).getTime() - Date.now()) / 864e5));
  return (
    <section aria-label="Cierre mensual"
      className={cx("flex min-w-0 flex-col gap-5 rounded-panel border border-[#1C1917] bg-[#1C1917] p-6 text-[#F3F2F0]", className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="eyebrow text-[#A39E98]">Cierre mensual</p>
        {status === "approved"
          ? <span className="font-mono text-2xs text-[#A39E98]">CERRADO</span>
          : <span className="font-mono text-2xs text-[#FF8A5C]">{daysLeft === 1 ? "FALTA 1 DÍA" : `FALTAN ${daysLeft} DÍAS`}</span>}
      </div>
      <div>
        <h2 className="disp text-lg font-semibold tracking-[-0.02em]">Inventario de {fmtPeriod(m.period).toLowerCase()}</h2>
        <p className="disp mt-3 text-[52px] font-semibold leading-none">
          {okCount}<span className="text-[28px] text-[#A39E98]"> / {essential.length}</span>
        </p>
        <p className="mt-1.5 text-[13px] text-[#B5B0AA]">
          {essential.length === 0 ? "No hay fuentes automáticas activas" : "fuentes automáticas con recogida completa"}
        </p>
      </div>
      <ol aria-label="Fases del cierre" className="grid grid-cols-4 gap-1">
        {PHASES.map((p, i) => (
          <li key={p} aria-current={i === phase ? "step" : undefined}>
            <span className={cx("block h-1 rounded-sm", i < phase ? "bg-[#F3F2F0]" : i === phase ? "bg-[#E4572E]" : "bg-[#3A3734]")} />
            <span className={cx("mt-2 block text-2xs", i <= phase ? "text-[#F3F2F0]" : "text-[#A39E98]")}>{p}</span>
          </li>
        ))}
      </ol>
      <ul className="border-t border-[#33302D]">
        {sources.length === 0 && <li className="py-2.5 text-[13px] text-[#B5B0AA]">Sin fuentes configuradas.</li>}
        {sources.map(([code, s]) => (
          <li key={code} className="flex items-center gap-3 border-b border-[#33302D] py-2.5 text-[13px] last:border-b-0">
            <span className="min-w-0 flex-1 truncate">
              {s.name}{!s.essential && <span className="text-[#A39E98]"> · complementaria</span>}
            </span>
            <span className={cx("text-right", s.ok ? "" : s.runs ? "text-[#FF8A5C]" : "text-[#A39E98]")}>
              {s.ok ? "Completa" : s.runs ? "Con errores" : "Sin datos este mes"}
            </span>
          </li>
        ))}
      </ul>
      <Link to={reviewCases > 0 ? "/auditoria?tab=revision" : "/auditoria?tab=mensual"}
        className="mt-auto inline-flex min-h-[42px] items-center justify-center gap-2 rounded-md bg-[#F3F2F0] text-[13px] font-medium text-[#141312] transition-opacity hover:opacity-90">
        {reviewCases > 0 ? `Revisar ${reviewCases} ${reviewCases === 1 ? "caso pendiente" : "casos pendientes"}` : "Gestionar inventario"}
        <ArrowRight className="size-4" aria-hidden />
      </Link>
    </section>
  );
}

// ------------------------------------------------------------------ Ranking de productos
export function RankedList({ items, total }: { items: RankedProduct[]; total: number }) {
  if (items.length === 0) return <EmptyState title="Aún no hay software inventariado" />;
  return (
    <ol>
      {items.map((t, i) => (
        <li key={t.id} className="grid grid-cols-[1.5rem_minmax(0,13rem)_1fr_2.75rem] items-center gap-3 border-b border-border py-2.5 last:border-b-0">
          <span className="code text-2xs text-muted">{String(i + 1).padStart(2, "0")}</span>
          <Link to={`/software/${t.id}`} title={t.name} className="truncate text-[13px] hover:underline hover:underline-offset-4">{t.name}</Link>
          <Meter value={t.devices} max={total} thick />
          <span className="disp text-right font-semibold">{fmtNumber(t.devices)}</span>
        </li>
      ))}
    </ol>
  );
}

// ------------------------------------------------------------------ Cambios por semana
const weekFmt = new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "short" });

export function WeeklyChanges({ weeks, className }: { weeks: WeekActivity[]; className?: string }) {
  const max = Math.max(1, ...weeks.map((w) => w.installed + w.updated));
  const total = weeks.reduce((a, w) => a + w.installed + w.updated, 0);
  const label = (iso: string) => weekFmt.format(new Date(`${iso}T12:00:00`)).replace(".", "").toUpperCase();
  return (
    <Panel title="Cambios por semana" className={className} aside={<span className="code ml-auto text-2xs text-muted">8 SEMANAS</span>}>
      {total === 0 ? <EmptyState title="Sin cambios de software en 8 semanas" /> : (
        <div role="img" aria-label={`Cambios de software por semana en las últimas 8 semanas: ${total} en total`}
          className="flex flex-1 flex-col">
          <div className="flex min-h-32 flex-1 items-end gap-1.5 border-b border-fg">
            {weeks.map((w) => (
              <div key={w.week_start} title={`Semana del ${label(w.week_start)}: ${w.installed} instalaciones, ${w.updated} actualizaciones`}
                className="flex h-full flex-1 flex-col justify-end gap-px hover:opacity-75">
                {w.updated > 0 && <span className="block rounded-t-[2px] bg-chart-3" style={{ height: `${pct(w.updated, max)}%` }} />}
                {w.installed > 0 && <span className={cx("block bg-chart-1", w.updated === 0 && "rounded-t-[2px]")} style={{ height: `${pct(w.installed, max)}%` }} />}
              </div>
            ))}
          </div>
          <div className="code mt-1.5 flex gap-1.5 text-[10px] text-muted" aria-hidden>
            {weeks.map((w) => <span key={w.week_start} className="flex-1 text-center">{label(w.week_start)}</span>)}
          </div>
          <div className="mt-3 flex gap-4 text-xs text-muted">
            <span className="flex items-center gap-2"><Swatch className="bg-chart-1" />Instalaciones</span>
            <span className="flex items-center gap-2"><Swatch className="bg-chart-3" />Actualizaciones</span>
          </div>
        </div>
      )}
    </Panel>
  );
}
