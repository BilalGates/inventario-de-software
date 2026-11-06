import { ArrowRight, CheckCircle2, RefreshCw } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { SeverityBadge } from "@/components/badges";
import { Button, EmptyState, ErrorState, Notice, PageHeader, Spinner, Stat, StatStrip, cx } from "@/components/ui";
import { FleetLegend, FleetTiles, Meter, MonthlyClose, Panel, Swatch, fmtPct, pct } from "@/components/viz";
import { useDashboard, type DashboardData, type DayActivity } from "@/lib/dashboard";
import { AUTH_LABEL, RUN_STATUS_LABEL, TRIGGER_LABEL, fmtNumber, fmtRelative, parseUtc } from "@/lib/format";

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
  const classified = total - (s.by_status.unclassified ?? 0) - (s.by_status.pending_review ?? 0);
  return (
    <Panel title="Catálogo por estado" className="flex-[1_1_21rem]"
      aside={<Link to="/software" className="link ml-auto text-xs">Catálogo</Link>}>
      <div role="img" aria-label={rows.map((r) => `${r.n} ${AUTH_LABEL[r.key]?.toLowerCase()}`).join(", ")}
        className="flex h-9 gap-0.5 overflow-hidden rounded-[3px]">
        {total === 0 ? <span className="flex-1 bg-chart-4" /> : rows.filter((r) => r.n > 0).map((r) => (
          <span key={r.key} className={r.cls} style={{ width: `${pct(r.n, total)}%` }} />
        ))}
      </div>
      <p className="-mt-2 text-xs text-muted">
        <span className="font-medium text-fg-2">{fmtNumber(classified)} de {fmtNumber(total)}</span> aplicaciones clasificadas
      </p>
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
function shortTime(v: string) {
  const d = parseUtc(v);
  if (!d) return "—";
  if (d.toDateString() === new Date().toDateString())
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
  const depts = [...data.departments.map((x) => ({ ...x, none: false })),
    ...(data.devices.unassigned ? [{ name: "Sin departamento", devices: data.devices.unassigned, none: true }] : [])];
  // Las informativas no compiten por la atención: primero críticas y avisos.
  const urgent = data.alerts.top.filter((a) => a.severity !== "info");
  const shown = (urgent.length ? urgent : data.alerts.top).slice(0, 5);
  return (
    <StatStrip label="Detalle operativo" minCell="20rem">
      <div className="flex flex-col gap-3.5 bg-surface p-6">
        <SectionHead title="Requiere atención" to="/auditoria?tab=alertas" label="Todas" />
        {shown.length === 0 ? (
          <EmptyState title="Sin incidencias abiertas" icon={<CheckCircle2 className="size-5" aria-hidden />} />
        ) : (
          <ul className="-mx-3">
            {shown.map((a) => (
              <li key={a.id}>
                <Link to={a.device_id ? `/dispositivos/${a.device_id}` : "/auditoria?tab=alertas"}
                  className="grid grid-cols-[3.25rem_1fr] gap-2.5 rounded-md px-3 py-2.5 transition-colors hover:bg-bg">
                  <span className="pt-0.5"><SeverityBadge severity={a.severity} /></span>
                  <span className="min-w-0">
                    <span className="block text-[13px] font-medium">{a.title}</span>
                    <span className="code mt-0.5 block text-2xs text-muted">{fmtRelative(a.created_at)}</span>
                  </span>
                </Link>
              </li>
            ))}
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
                <Meter value={x.devices} max={maxDept} className={x.none ? "bg-chart-3" : "bg-fg"} />
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
    </StatStrip>
  );
}

// ------------------------------------------------------------------ Página
const longDate = new Intl.DateTimeFormat("es-ES", { weekday: "long", day: "numeric", month: "short", year: "numeric" });

export function Dashboard() {
  const nav = useNavigate();
  const { data, isLoading, error, refetch } = useDashboard();
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
  const urgent = critical + warnings;
  const lastOk = data.runs.find((r) => r.status === "succeeded");
  const alertHint = [critical && `${critical} críticas`, warnings && `${warnings} avisos`, infos && `+${infos} informativas`]
    .filter(Boolean).join(" · ");

  return (
    <>
      <PageHeader eyebrow={`Panel · ${longDate.format(new Date())}`} title="Parque tecnológico"
        description={<>
          {fmtNumber(d.total)} equipos, {fmtNumber(sw.products)} aplicaciones y {sources} {sources === 1 ? "fuente conectada" : "fuentes conectadas"}.{" "}
          <span className="text-fg-2">
            {behind ? `${fmtNumber(behind)} equipos sin datos recientes. ` : ""}
            {lastOk ? `Última sincronización completa ${fmtRelative(lastOk.finished_at ?? lastOk.requested_at)}.` : "Aún no hay sincronizaciones completas."}
          </span>
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
            <span className="mt-1.5 block w-full"><Meter value={d.current} max={d.total} /></span>
          </Stat>
          <Stat label="Aplicaciones" value={fmtNumber(sw.products)} hint={`${fmtNumber(sw.installations)} instalaciones`} onClick={() => nav("/software")} />
          <Stat label="Por clasificar" value={fmtNumber(sw.pending)} tone={sw.pending ? "warn" : undefined}
            hint={sw.pending ? `${fmtPct(pct(sw.pending, sw.products))} % del catálogo` : "catálogo clasificado"}
            onClick={() => nav("/software?status=unclassified,pending_review")} />
          <Stat label="Alertas" value={fmtNumber(urgent)} tone={urgent ? "danger" : undefined}
            hint={alertHint || "sin incidencias"} onClick={() => nav("/auditoria?tab=alertas")} />
        </StatStrip>

        <div className="flex flex-wrap gap-6">
          <Panel title="Estado del parque" className="flex-[2_1_34rem]"
            aside={<>
              <span className="text-[13px] text-muted">cada recuadro es un equipo</span>
              <Link to="/dispositivos" className="link ml-auto text-xs">Ver equipos</Link>
            </>}>
            <FleetTiles fleet={d.fleet ?? []} />
            <FleetLegend d={d} />
          </Panel>
          <MonthlyClose m={data.monthly} reviewCases={data.open_review_cases} className="flex-[1_1_21rem]" />
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
