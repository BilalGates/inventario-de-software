import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button, EmptyState, ErrorState, Notice, PageHeader, Spinner, Stat, StatStrip, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { AUTH_LABEL, RUN_STATUS_LABEL, TRIGGER_LABEL, fmtNumber, fmtPeriod, fmtRelative, parseUtc } from "@/lib/format";
import type { Alert, Change, Coverage, Run, Snapshot } from "@/lib/types";

interface DayActivity { date: string; installed: number; removed: number; updated: number }

interface DashboardData {
  generated_at: string;
  devices: { total: number; current: number; stale: number; never_synced: number; unassigned: number;
    compliance: Record<string, number> };
  software: { products: number; installations: number; pending: number; unauthorized_products: number;
    by_status: Record<string, number> };
  alerts: { open: number; by_severity: Record<string, number>; top: Alert[] };
  monthly: { period: string; snapshot: Snapshot | null; coverage: Coverage };
  runs: Run[];
  changes: Change[];
  changes_30d: Record<string, number>;
  changes_daily?: DayActivity[];
  departments: { name: string; devices: number }[];
  worker_heartbeat: { at: string } | null;
  open_review_cases: number;
}

const pct = (n: number, d: number) => (d ? (n / d) * 100 : 0);
const fmtPct = (v: number) => `${v.toLocaleString("es-ES", { maximumFractionDigits: 1 })}`;

function Panel({ title, aside, children, className }: { title: string; aside?: ReactNode; children: ReactNode;
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

function Swatch({ className }: { className: string }) {
  return <span className={cx("inline-block size-[9px] shrink-0 rounded-[2px]", className)} aria-hidden />;
}

// ------------------------------------------------------------------ Estado del parque (un cuadro por equipo)
function Fleet({ d }: { d: DashboardData["devices"] }) {
  const unit = Math.max(1, Math.ceil(d.total / 480));
  // Con pocos equipos, cuadros más grandes para que el gráfico tenga presencia.
  const size = d.total <= 60 ? 22 : d.total <= 200 ? 16 : 11;
  const groups = [
    { n: d.current, cls: "bg-chart-1", label: "Al día" },
    { n: d.stale, cls: "bg-signal-fill", label: "Sin observar" },
    { n: d.never_synced, cls: "bg-chart-3", label: "Sin fuente automática" },
  ];
  const cells = groups.flatMap((g) => Array.from({ length: Math.ceil(g.n / unit) }, () => g.cls));
  const summary = groups.map((g) => `${fmtNumber(g.n)} ${g.label.toLowerCase()}`).join(", ");
  return (
    <Panel title="Estado del parque" className="flex-[2_1_34rem]"
      aside={<>
        <span className="text-[13px] text-muted">{unit === 1 ? "cada cuadro es un equipo" : `cada cuadro son ${unit} equipos`}</span>
        <Link to="/dispositivos" className="link ml-auto text-xs">Ver equipos</Link>
      </>}>
      {d.total === 0 ? <EmptyState title="Aún no hay equipos registrados" /> : (
        <div role="img" aria-label={summary} className="grid gap-[3px]"
          style={{ gridTemplateColumns: `repeat(auto-fill, ${size}px)` }}>
          {cells.map((cls, i) => <span key={i} className={cx("rounded-[2px]", cls)} style={{ width: size, height: size }} />)}
        </div>
      )}
      <dl className="grid grid-cols-[repeat(auto-fit,minmax(9rem,1fr))] gap-4 border-t border-border pt-4">
        {groups.map((g, i) => (
          <div key={g.label}>
            <dt className="flex items-center gap-2 text-xs text-muted"><Swatch className={g.cls} />{g.label}</dt>
            <dd className="disp mt-1 text-[22px] font-semibold">
              <Link to={`/dispositivos?freshness=${["current", "stale", "never_synced"][i]}`} className="hover:underline hover:underline-offset-4">
                {fmtNumber(g.n)}
              </Link>
            </dd>
          </div>
        ))}
        <div>
          <dt className="flex items-center gap-2 text-xs text-muted">
            <span className="inline-block size-[9px] rounded-[2px] border border-dashed border-chart-2" aria-hidden />Sin departamento
          </dt>
          <dd className="disp mt-1 text-[22px] font-semibold">{fmtNumber(d.unassigned)}</dd>
        </div>
      </dl>
    </Panel>
  );
}

// ------------------------------------------------------------------ Cierre mensual (panel oscuro)
const PHASES = ["Recogida", "Revisión", "Cierre", "Informe"];

function MonthlyClose({ m, reviewCases }: { m: DashboardData["monthly"]; reviewCases: number }) {
  const sources = Object.entries(m.coverage.sources);
  const essential = sources.filter(([, s]) => s.essential);
  const okCount = essential.filter(([, s]) => s.ok).length;
  const status = m.snapshot?.status;
  const phase = status === "approved" ? 4 : status === "draft" ? 1 : m.coverage.complete ? 1 : 0;
  const [y, mo] = m.period.split("-").map(Number);
  const daysLeft = Math.max(0, Math.ceil((new Date(y, mo, 1).getTime() - Date.now()) / 864e5));
  return (
    <section aria-label="Cierre mensual"
      className="flex min-w-0 flex-[1_1_21rem] flex-col gap-5 rounded-panel border border-[#1C1917] bg-[#1C1917] p-6 text-[#F3F2F0]">
      <div className="flex items-center justify-between gap-2">
        <p className="eyebrow text-[#A39E98]">Cierre mensual</p>
        {status === "approved"
          ? <span className="font-mono text-2xs text-[#A39E98]">APROBADO</span>
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
            <span className="min-w-0 flex-1 truncate">{s.name}</span>
            <span className={cx("text-right", s.ok ? "" : s.runs ? "text-[#FF8A5C]" : "text-[#A39E98]")}>
              {s.ok ? "Completa" : s.runs ? "Con errores" : "Pendiente"}
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

// ------------------------------------------------------------------ Actividad de software (30 días)
const dayFmt = new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "short" });

function Activity({ days }: { days: DayActivity[] }) {
  const max = Math.max(1, ...days.map((d) => d.installed + d.updated));
  const maxOut = Math.max(1, ...days.map((d) => d.removed));
  const total = (k: keyof Omit<DayActivity, "date">) => days.reduce((a, d) => a + d[k], 0);
  const label = (iso: string) => dayFmt.format(new Date(`${iso}T12:00:00`)).replace(".", "").toUpperCase();
  const ticks = days.length ? [0, 7, 14, 21].map((i) => days[i]).filter(Boolean) : [];
  const empty = total("installed") + total("updated") + total("removed") === 0;
  return (
    <Panel title="Actividad de software" className="flex-[2_1_34rem]"
      aside={<ul className="ml-auto flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
        <li className="flex items-center gap-2"><Swatch className="bg-chart-1" />Instalaciones <span className="code text-fg">{fmtNumber(total("installed"))}</span></li>
        <li className="flex items-center gap-2"><Swatch className="bg-chart-3" />Actualizaciones <span className="code text-fg">{fmtNumber(total("updated"))}</span></li>
        <li className="flex items-center gap-2"><Swatch className="bg-signal-fill" />Desinstalaciones <span className="code text-fg">{fmtNumber(total("removed"))}</span></li>
      </ul>}>
      {empty ? <EmptyState title="Sin cambios de software en los últimos 30 días" /> : (
        <div role="img" className="pt-4"
          aria-label={`Últimos 30 días: ${total("installed")} instalaciones, ${total("updated")} actualizaciones y ${total("removed")} desinstalaciones`}>
          <div className="relative flex h-40 items-end gap-[3px] border-b border-fg">
            <span className="absolute inset-x-0 top-0 border-t border-dashed border-border-strong" aria-hidden />
            <span className="absolute inset-x-0 top-1/2 border-t border-dashed border-border" aria-hidden />
            <span className="code absolute -top-[18px] right-0 text-[10px] text-muted">{fmtNumber(max)} / día</span>
            {days.map((d) => (
              <div key={d.date} title={`${label(d.date)}: ${d.installed} instalaciones, ${d.updated} actualizaciones, ${d.removed} desinstalaciones`}
                className="relative flex h-full flex-1 flex-col justify-end gap-px hover:opacity-75">
                {d.updated > 0 && <span className="block rounded-t-[2px] bg-chart-3" style={{ height: `${pct(d.updated, max)}%` }} />}
                {d.installed > 0 && <span className={cx("block bg-chart-1", d.updated === 0 && "rounded-t-[2px]")} style={{ height: `${pct(d.installed, max)}%` }} />}
              </div>
            ))}
          </div>
          <div className="flex h-7 items-start gap-[3px]" aria-hidden>
            {days.map((d) => (
              <div key={d.date} className="flex h-full flex-1">
                {d.removed > 0 && <span className="block w-full rounded-b-[2px] bg-signal-fill" style={{ height: `${pct(d.removed, maxOut)}%` }} />}
              </div>
            ))}
          </div>
          <div className="code flex justify-between text-[10px] text-muted" aria-hidden>
            {ticks.map((d) => <span key={d.date}>{label(d.date)}</span>)}<span>HOY</span>
          </div>
        </div>
      )}
    </Panel>
  );
}

// ------------------------------------------------------------------ Catálogo por estado
const CATALOG = [
  { key: "authorized", cls: "bg-chart-1" },
  { key: "exception", cls: "bg-chart-2" },
  { key: "unauthorized", cls: "bg-signal-fill", alert: true },
  { key: "pending_review", cls: "bg-chart-3" },
  { key: "unclassified", cls: "bg-chart-4 border border-border-strong" },
];

function Catalog({ s }: { s: DashboardData["software"] }) {
  const rows = CATALOG.map((c) => ({ ...c, n: s.by_status[c.key] ?? 0 })).filter((c) => c.n > 0 || c.key === "unauthorized");
  const total = rows.reduce((a, r) => a + r.n, 0);
  return (
    <Panel title="Catálogo por estado" className="flex-[1_1_21rem]"
      aside={<Link to="/software" className="link ml-auto text-xs">Catálogo</Link>}>
      <div role="img" aria-label={rows.map((r) => `${r.n} ${AUTH_LABEL[r.key]?.toLowerCase()}`).join(", ")}
        className="flex h-9 gap-0.5 overflow-hidden rounded-[3px]">
        {total === 0 ? <span className="flex-1 bg-chart-4" /> : rows.filter((r) => r.n > 0).map((r) => (
          <span key={r.key} className={r.cls} style={{ width: `${pct(r.n, total)}%` }} />
        ))}
      </div>
      <ul>
        {rows.map((r) => (
          <li key={r.key} className="border-b border-border last:border-b-0">
            <Link to={`/software?status=${r.key}`} className="flex items-center gap-2.5 py-2.5 hover:bg-bg">
              <Swatch className={r.cls} />
              <span className={cx("flex-1", r.alert && r.n > 0 && "font-medium text-signal")}>{AUTH_LABEL[r.key]}</span>
              <span className={cx("disp text-[15px] font-semibold", r.alert && r.n > 0 && "text-signal")}>{fmtNumber(r.n)}</span>
              <span className="code w-12 text-right text-muted">{fmtPct(pct(r.n, total))}%</span>
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ------------------------------------------------------------------ Franja inferior
const SEV: Record<string, [string, string]> = {
  critical: ["CRIT", "text-signal"], warning: ["AVISO", "text-fg"], info: ["INFO", "text-muted"],
};

function shortTime(v: string) {
  const d = parseUtc(v);
  if (!d) return "—";
  const today = new Date();
  if (d.toDateString() === today.toDateString())
    return d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
  return dayFmt.format(d).replace(".", "").toUpperCase();
}

function SectionHead({ title, to, label }: { title: string; to: string; label: string }) {
  return (
    <div className="flex items-baseline gap-3">
      <h2 className="disp text-lg font-semibold tracking-[-0.02em]">{title}</h2>
      <Link to={to} className="link ml-auto text-xs">{label}</Link>
    </div>
  );
}

function Operations({ data }: { data: DashboardData }) {
  const maxDept = Math.max(1, ...data.departments.map((x) => x.devices), data.devices.unassigned);
  const depts = [...data.departments.slice(0, 7).map((x) => ({ ...x, none: false })),
    ...(data.devices.unassigned ? [{ name: "Sin departamento", devices: data.devices.unassigned, none: true }] : [])];
  return (
    <section aria-label="Detalle operativo"
      className="card grid grid-cols-[repeat(auto-fit,minmax(min(100%,20rem),1fr))] overflow-hidden [&>*]:shadow-[1px_1px_0_0_rgb(var(--border))]">
      <div className="flex flex-col gap-3.5 bg-surface p-6">
        <SectionHead title="Requiere atención" to="/auditoria?tab=alertas" label="Todas" />
        {data.alerts.top.length === 0 ? (
          <EmptyState title="Sin incidencias abiertas" icon={<CheckCircle2 className="size-5" aria-hidden />} />
        ) : (
          <ul className="-mx-3">
            {data.alerts.top.slice(0, 5).map((a) => {
              const [code, tone] = SEV[a.severity] ?? ["—", "text-muted"];
              return (
                <li key={a.id}>
                  <Link to={a.device_id ? `/dispositivos/${a.device_id}` : "/auditoria?tab=alertas"}
                    className="grid grid-cols-[3.25rem_1fr] gap-2.5 rounded-md px-3 py-2.5 transition-colors hover:bg-bg">
                    <span className={cx("code pt-0.5 text-2xs font-medium", tone)}>{code}</span>
                    <span className="min-w-0">
                      <span className="block text-[13px] font-medium">{a.title}</span>
                      <span className="code mt-0.5 block text-2xs text-muted">{fmtRelative(a.created_at)}</span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
        {data.open_review_cases > 0 && (
          <Link to="/auditoria?tab=revision" className="mt-auto flex items-center gap-2 border-t border-border pt-3 text-[13px] font-medium text-signal hover:underline hover:underline-offset-4">
            {data.open_review_cases} casos de conciliación pendientes de revisión <ArrowRight className="size-4" aria-hidden />
          </Link>
        )}
      </div>
      <div className="flex flex-col gap-3.5 bg-surface p-6">
        <SectionHead title="Por departamento" to="/departamentos" label="Departamentos" />
        {depts.length === 0 ? <p className="text-muted">Ningún dispositivo asignado todavía.</p> : (
          <ul className="flex flex-col gap-3">
            {depts.map((x) => (
              <li key={x.name} className="flex flex-col gap-1.5">
                <div className="flex text-[13px]">
                  <span className={cx("min-w-0 flex-1 truncate", x.none && "text-muted")} title={x.name}>{x.name}</span>
                  <span className="disp font-semibold">{fmtNumber(x.devices)}</span>
                </div>
                <span className="block h-[3px] rounded-sm bg-chart-4" aria-hidden>
                  <span className={cx("block h-full rounded-sm", x.none ? "bg-chart-3" : "bg-fg")} style={{ width: `${pct(x.devices, maxDept)}%` }} />
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex flex-col gap-3.5 bg-surface p-6">
        <SectionHead title="Sincronizaciones" to="/sincronizacion" label="Historial" />
        {data.runs.length === 0 ? <EmptyState title="Aún no hay ejecuciones" /> : (
          <ol>
            {data.runs.slice(0, 5).map((r) => {
              const bad = r.status === "failed" || r.status === "partial";
              return (
                <li key={r.id} className="grid grid-cols-[3.25rem_1fr_auto] items-baseline gap-3 border-b border-border py-2.5 last:border-b-0">
                  <span className="code text-2xs text-muted">{shortTime(r.requested_at)}</span>
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] font-medium">{r.source_name}</span>
                    <span className="block text-xs text-muted">{TRIGGER_LABEL[r.trigger] ?? r.trigger}</span>
                  </span>
                  <span className={cx("code text-2xs uppercase", bad ? "text-signal" : "text-muted")}>
                    {r.status === "succeeded" ? "OK" : RUN_STATUS_LABEL[r.status] ?? r.status}
                  </span>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ Página
const longDate = new Intl.DateTimeFormat("es-ES", { weekday: "long", day: "numeric", month: "short", year: "numeric" });

export function Dashboard() {
  const nav = useNavigate();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get<DashboardData>("/dashboard"),
    refetchInterval: 60_000,
  });
  if (isLoading) return <Spinner />;
  if (error || !data) return <ErrorState error={error} retry={refetch} />;
  const d = data.devices;
  const sw = data.software;
  const workerAge = data.worker_heartbeat ? Date.now() - (parseUtc(data.worker_heartbeat.at)?.getTime() ?? 0) : null;
  const behind = d.stale + d.never_synced;
  const sources = Object.keys(data.monthly.coverage.sources).length;
  const critical = data.alerts.by_severity.critical ?? 0;
  const warnings = data.alerts.by_severity.warning ?? 0;
  const infos = data.alerts.by_severity.info ?? 0;
  const alertHint = [critical && `${critical} críticas`, warnings && `${warnings} avisos`, infos && `${infos} informativas`]
    .filter(Boolean).join(" · ");

  return (
    <>
      <PageHeader eyebrow={`Panel · ${longDate.format(new Date())}`} title="Parque tecnológico"
        description={<>
          {fmtNumber(d.total)} equipos, {fmtNumber(sw.products)} aplicaciones y {sources} {sources === 1 ? "fuente conectada" : "fuentes conectadas"}.{" "}
          <span className="text-fg-2">{behind ? `${fmtNumber(behind)} equipos sin datos recientes.` : "Todo al día."}</span>
          <span className="text-muted"> Actualizado {fmtRelative(data.generated_at)}.</span>
        </>}
        actions={<Button variant="primary" icon={<RefreshCw className="size-4" />} onClick={() => nav("/sincronizacion")}>Sincronizar</Button>} />

      {(workerAge === null || workerAge > 10 * 60_000) && (
        <div className="mb-6">
          <Notice tone="warn" title="El proceso de sincronización no está activo">
            Las sincronizaciones y la programación mensual necesitan el worker en ejecución
            ({workerAge === null ? "nunca se ha ejecutado" : `último latido ${fmtRelative(data.worker_heartbeat!.at)}`}).
          </Notice>
        </div>
      )}

      <div className="flex flex-col gap-6">
        <StatStrip>
          <Stat label="Equipos" value={fmtNumber(d.total)} hint={`${fmtNumber(d.unassigned)} sin departamento`} onClick={() => nav("/dispositivos")} />
          <Stat label="Al día" onClick={() => nav("/dispositivos?freshness=current")}
            value={<>{fmtPct(pct(d.current, d.total))}<span className="text-[20px] text-muted"> %</span></>}>
            <span className="mt-1.5 block h-[3px] w-full overflow-hidden rounded-sm bg-chart-4" aria-hidden>
              <span className="block h-full bg-fg" style={{ width: `${pct(d.current, d.total)}%` }} />
            </span>
          </Stat>
          <Stat label="Aplicaciones" value={fmtNumber(sw.products)} hint={`${fmtNumber(sw.installations)} instalaciones`} onClick={() => nav("/software")} />
          <Stat label="Por clasificar" value={fmtNumber(sw.pending)} hint="pendientes de autorizar o revisar"
            onClick={() => nav("/software?status=unclassified,pending_review")} />
          <Stat label="Alertas abiertas" value={fmtNumber(data.alerts.open)} tone={data.alerts.open ? "danger" : undefined}
            hint={alertHint || "sin incidencias"}
            onClick={() => nav("/auditoria?tab=alertas")} />
        </StatStrip>

        <div className="flex flex-wrap gap-6">
          <Fleet d={d} />
          <MonthlyClose m={data.monthly} reviewCases={data.open_review_cases} />
        </div>

        <div className="flex flex-wrap gap-6">
          <Activity days={data.changes_daily ?? []} />
          <Catalog s={sw} />
        </div>

        <Operations data={data} />
      </div>
    </>
  );
}
