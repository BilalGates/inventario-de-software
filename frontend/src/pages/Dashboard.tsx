/** Panel «Pulso del parque»: cómo está el parque, qué hacer ahora y el contexto (política, cierre, movimiento). */
import { ArrowRight, Download, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ContextMenu, useContextMenu } from "@/components/ContextMenu";
import { useDeviceActions } from "@/components/DeviceActions";
import { Bar, DOT_LABEL, HATCH, Spark, StackBar, StatusDot, Stepper, Swatch } from "@/components/kit";
import { useClassify } from "@/components/SoftwareActions";
import { Button, EmptyState, ErrorState, Spinner, cx, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { useDashboard, type DashboardData, type FleetDevice, type HealthState } from "@/lib/dashboard";
import { fmtNumber, fmtPeriod, fmtRelative, parseUtc } from "@/lib/format";

const longDate = new Intl.DateTimeFormat("es-ES", { weekday: "long", day: "numeric", month: "long" });
const INFRA = "Infraestructura";
const NO_DEPT = "Sin departamento";

function Card({ children, className, label }: { children: React.ReactNode; className?: string; label?: string }) {
  return <section aria-label={label} className={cx("card flex min-w-0 flex-col gap-4 p-6", className)}>{children}</section>;
}

// ------------------------------------------------------------------ Cabecera
function Header({ data }: { data: DashboardData }) {
  const nav = useNavigate();
  const toast = useToast();
  const [exporting, setExporting] = useState(false);
  const workerAge = data.worker_heartbeat ? Date.now() - (parseUtc(data.worker_heartbeat.at)?.getTime() ?? 0) : null;
  // Margen: dos pasadas perdidas más 10 minutos (el worker en la nube pasa cada hora).
  const workerLimit = ((data.worker_interval_minutes ?? 1) * 2 + 10) * 60_000;
  const workerDown = workerAge === null || workerAge > workerLimit;
  const lastOk = data.runs.find((r) => r.status === "succeeded");
  const exportAll = async () => {
    setExporting(true);
    try { await api.download("/inventory/export"); } catch (e) { toast("danger", (e as Error).message); } finally { setExporting(false); }
  };
  return (
    <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
      <p className="eyebrow">Panel · {longDate.format(new Date())}</p>
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex h-8 items-center gap-2 rounded-full border border-border-strong px-3 text-xs text-fg-2">
          <StatusDot kind="ok" size="sm" />
          {lastOk ? `${lastOk.source_name} · ${fmtRelative(lastOk.finished_at ?? lastOk.requested_at)}` : "Sin sincronizaciones completas"}
        </span>
        {workerDown && (
          <Link to="/sincronizacion" title="Las sincronizaciones y la programación mensual necesitan el worker en ejecución"
            className="inline-flex h-8 items-center gap-2 rounded-full border border-signal/40 px-3 text-xs text-signal hover:border-signal">
            <StatusDot kind="alert" size="sm" />
            Worker parado{workerAge !== null && ` · ${fmtRelative(data.worker_heartbeat!.at)}`}
          </Link>
        )}
        <Button icon={<Download className="size-4" />} loading={exporting} onClick={exportAll}>Exportar inventario</Button>
        <Button variant="primary" icon={<RefreshCw className="size-4" />} onClick={() => nav("/sincronizacion")}>Sincronizar</Button>
      </div>
    </header>
  );
}

// ------------------------------------------------------------------ Salud
function HealthHero({ data }: { data: DashboardData }) {
  const h = data.health;
  if (!h || h.workstations === 0) {
    return <div className="flex-[1_1_22rem]"><EmptyState title="Aún no hay puestos de trabajo inventariados" /></div>;
  }
  const pctClean = Math.round((h.clean / h.workstations) * 100);
  const rows: [HealthState, string, number, string][] = [
    ["alert", "Software no autorizado", h.unauthorized, "/dispositivos?state=alert"],
    ["nc", "No conformes en Intune", h.noncompliant, "/dispositivos?state=nc"],
  ];
  return (
    <div className="flex min-w-0 flex-[1_1_22rem] flex-col gap-5 py-1">
      <p className="eyebrow">Puestos de trabajo limpios</p>
      <p className="disp flex items-end gap-2 font-semibold leading-[0.82]">
        <span className="text-[120px] sm:text-[148px]">{pctClean}</span>
        <span className="pb-1 text-[40px] text-muted">%</span>
      </p>
      <p className="max-w-[28ch] text-xl font-medium leading-snug tracking-[-0.01em]">
        {h.clean} de {h.workstations} equipos no tienen ninguna incidencia.
        {h.clean < h.workstations && <span className="text-muted"> El resto se reparte así:</span>}
      </p>
      <div className="flex flex-col border-t border-border">
        {rows.map(([kind, label, n, to]) => (
          <Link key={kind} to={to} className="flex items-center gap-3.5 border-b border-border py-3.5 transition-colors hover:bg-subtle">
            <StatusDot kind={kind} />
            <span className="flex-1 text-[15px]">{label}</span>
            <span className="disp text-[22px] font-semibold">{n}</span>
          </Link>
        ))}
        <p className="py-3 text-xs text-muted">
          {h.both > 0 && `${h.both} ${h.both === 1 ? "equipo tiene" : "equipos tienen"} ambas cosas · `}
          {h.infra > 0 ? `${h.infra} de infraestructura con inventario manual, fuera de la cifra` : "sin infraestructura manual"}
        </p>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Mapa del parque
function FleetMap({ fleet }: { fleet: FleetDevice[] }) {
  const ctx = useContextMenu();
  const actions = useDeviceActions();
  const groups = useMemo(() => {
    const by = new Map<string, FleetDevice[]>();
    for (const d of fleet) {
      const g = d.state === "infra" ? INFRA : d.department ?? NO_DEPT;
      by.set(g, [...(by.get(g) ?? []), d]);
    }
    const rank = (n: string) => (n === INFRA ? 2 : n === NO_DEPT ? 1 : 0);
    return [...by.entries()].sort((a, b) => rank(a[0]) - rank(b[0]) || b[1].length - a[1].length || a[0].localeCompare(b[0]));
  }, [fleet]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const sel = fleet.find((d) => d.id === selectedId)
    ?? fleet.find((d) => d.state === "alertnc") ?? fleet.find((d) => d.state === "alert") ?? fleet[0];

  if (fleet.length === 0) return <Card className="flex-[2_1_40rem]"><EmptyState title="Aún no hay equipos registrados" /></Card>;
  const issues = (d: FleetDevice) => {
    const out: { text: string; tone?: "signal" }[] = [];
    if (d.unauthorized) out.push({ text: "Tiene software no autorizado instalado", tone: "signal" });
    if (d.state === "nc" || d.state === "alertnc") {
      (d.reasons?.length ? d.reasons : ["No conforme en Intune"]).forEach((r) => out.push({ text: r, tone: "signal" }));
    }
    if (d.state === "infra") out.push({ text: "Sin fuente automática · inventario manual" });
    if (d.state === "ok") out.push({ text: "Sin incidencias" });
    return out;
  };
  return (
    <Card className="flex-[2_1_40rem]" label="Mapa del parque">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="disp text-lg font-semibold">Mapa del parque <span className="font-sans text-sm font-normal text-muted">· {fleet.length} equipos por departamento</span></h2>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {(["ok", "alert", "nc", "infra"] as const).map((k) => (
            <span key={k} className="inline-flex items-center gap-1.5"><StatusDot kind={k} size="sm" />{k === "infra" ? "Infraestructura" : DOT_LABEL[k]}</span>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-start gap-x-7 gap-y-5">
        {groups.map(([name, devs]) => (
          <div key={name} className="flex flex-col gap-2">
            <p className="text-xs text-muted"><span className="font-medium text-fg">{name}</span> · {devs.length}</p>
            <div className="grid gap-0.5" style={{ gridTemplateColumns: `repeat(${Math.min(6, Math.max(1, Math.ceil(Math.sqrt(devs.length * 1.6))))}, 44px)` }}>
              {devs.map((d) => (
                <button key={d.id} type="button" title={d.name}
                  aria-label={`${d.name}: ${DOT_LABEL[d.state ?? "ok"] ?? ""}`} aria-pressed={sel?.id === d.id}
                  onClick={() => setSelectedId(d.id)}
                  onContextMenu={(e) => ctx.openAt(e, actions.entries({ id: d.id, name: d.name, intune: d.type !== "server" && d.state !== "infra" }), d.name)}
                  className={cx("flex size-11 items-center justify-center rounded-[10px] transition-colors hover:bg-subtle",
                    sel?.id === d.id && "bg-subtle ring-1 ring-border-strong")}>
                  <StatusDot kind={d.state ?? "ok"} size="lg" />
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      {sel && (
        <div className="mt-auto flex flex-wrap items-center gap-x-7 gap-y-3 rounded-xl bg-subtle px-4 py-3.5">
          <div className="min-w-40">
            <p className="eyebrow">Seleccionado</p>
            <p className="disp text-[17px] font-semibold">{sel.name}</p>
            <p className="text-xs text-muted">{[sel.state === "infra" ? INFRA : sel.department ?? NO_DEPT, sel.model].filter(Boolean).join(" · ")}</p>
          </div>
          <ul className="flex min-w-60 flex-1 flex-col gap-1 text-[13px]">
            {issues(sel).map((i) => (
              <li key={i.text} className="flex items-baseline gap-2.5">
                <span className={i.tone ? "text-signal" : "text-muted"} aria-hidden>●</span>{i.text}
              </li>
            ))}
          </ul>
          <Link to={`/dispositivos/${sel.id}`} className="link text-[13px]">Abrir ficha →</Link>
        </div>
      )}
      <ContextMenu menu={ctx.menu} onClose={ctx.close} />
      {actions.dialogs}
    </Card>
  );
}

// ------------------------------------------------------------------ Qué hacer ahora
function Actions({ data }: { data: DashboardData }) {
  const can = useCan();
  const { classify, busy } = useClassify();
  const a = data.alerts;
  const causes = a.causes ?? [];
  const maxCause = Math.max(1, ...causes.map((c) => c.devices));
  const reasons = data.compliance_reasons ?? [];
  const queue = data.software.queue ?? [];
  const h = data.health;
  return (
    <section id="acciones" aria-label="Qué hacer ahora" className="flex scroll-mt-20 flex-col gap-4 pt-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="disp text-[26px] font-semibold">Qué hacer ahora</h2>
        <p className="text-[13px] text-muted">Ordenado por cuántos equipos limpia cada acción</p>
      </div>
      <div className="flex flex-wrap items-stretch gap-4">
        <Card className="flex-[1_1_22rem]" label="Software no autorizado">
          <p className="code text-xs text-signal">01 · {fmtNumber(a.unauthorized_devices ?? 0)} EQUIPOS AFECTADOS</p>
          {causes.length === 0 ? <EmptyState title="Ningún equipo tiene software no autorizado" /> : <>
            <h3 className="disp text-xl font-semibold leading-snug">
              Las {fmtNumber(a.open)} alertas vienen de {a.causes_total} {a.causes_total === 1 ? "aplicación" : "aplicaciones"}.
            </h3>
            <ul className="flex flex-col gap-2.5">
              {causes.map((c) => (
                <li key={c.product_id} className="grid grid-cols-[minmax(0,1fr)_6rem_2rem] items-center gap-3 text-[13px]">
                  <Link to={`/software/${c.product_id}`} className="truncate hover:underline hover:underline-offset-4"
                    title={c.alternative ? `Alternativa: ${c.alternative}` : c.name}>{c.name}</Link>
                  <Bar value={c.devices} max={maxCause} className="bg-signal-fill" />
                  <span className="disp text-right font-semibold">{c.devices}</span>
                </li>
              ))}
            </ul>
            {!!a.rest?.products && <p className="text-xs text-muted">y {a.rest.products} aplicaciones más · {a.rest.alerts} alertas</p>}
            <Link to="/auditoria?tab=alertas" className="mt-auto inline-flex h-10 w-fit items-center gap-2 rounded-md bg-accent px-4 text-[13px] font-medium text-accent-fg hover:bg-accent/85">
              Ver alertas por causa <ArrowRight className="size-4" aria-hidden /></Link>
          </>}
        </Card>

        <Card className="flex-[1_1_18rem]" label="No conformes">
          <p className="code text-xs text-signal">02 · {fmtNumber(h?.noncompliant ?? 0)} NO CONFORMES</p>
          {reasons.length === 0 ? <EmptyState title="Todos los equipos cumplen las directivas de Intune" /> : <>
            <h3 className="disp text-xl font-semibold leading-snug">
              {h?.noncompliant} {h?.noncompliant === 1 ? "equipo incumple" : "equipos incumplen"} Intune por {reasons.length} {reasons.length === 1 ? "motivo" : "motivos"}.
            </h3>
            <ul className="flex flex-col gap-3.5">
              {reasons.slice(0, 4).map((r) => (
                <li key={r.reason} className="flex flex-col gap-1">
                  <div className="flex justify-between gap-3 text-[13px]"><span>{r.reason}</span><b className="disp">{r.devices.length}</b></div>
                  <p className="code truncate text-2xs text-muted" title={r.devices.join(" · ")}>{r.devices.join(" · ")}</p>
                </li>
              ))}
            </ul>
            <Link to="/dispositivos?state=nc" className="mt-auto inline-flex h-10 w-fit items-center rounded-md border border-border-strong px-4 text-[13px] font-medium hover:border-muted">
              Ver no conformes</Link>
          </>}
        </Card>

        <Card className="flex-[1_1_20rem]" label="Por decidir">
          <p className="code text-xs text-muted">03 · {fmtNumber(data.software.pending)} POR DECIDIR</p>
          {queue.length === 0 ? <EmptyState title="Todo el catálogo está clasificado" /> : <>
            <h3 className="disp text-xl font-semibold leading-snug">Aplicaciones nuevas esperando tu decisión.</h3>
            <ul className="flex flex-col">
              {queue.slice(0, 3).map((q) => (
                <li key={q.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border py-3 last:border-b-0">
                  <div className="min-w-0 flex-[1_1_9rem]">
                    <Link to={`/software/${q.id}`} className="block truncate text-sm font-medium hover:underline hover:underline-offset-4">{q.name}</Link>
                    <p className="text-xs text-muted">{[q.publisher, `${q.devices} ${q.devices === 1 ? "equipo" : "equipos"}`].filter(Boolean).join(" · ")}</p>
                  </div>
                  {can.write && (
                    <div className="flex gap-1.5">
                      {([["authorized", "Sí"], ["conditional", "Con condiciones"], ["unauthorized", "No"]] as const).map(([s, l]) => (
                        <Button key={s} size="sm" disabled={busy} aria-label={`${l === "Sí" ? "Autorizar" : l === "No" ? "No autorizar" : "Con condiciones"} ${q.name}`}
                          onClick={() => classify([{ id: q.id, name: q.name, status: q.status ?? "unclassified" }], s)}>{l}</Button>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
            <Link to="/software" className="link mt-auto text-[13px]">Ver las {fmtNumber(data.software.pending)} →</Link>
          </>}
        </Card>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ Contexto
const PHASES = ["Recogida", "Revisión", "Cierre", "Informe"];

function Context({ data }: { data: DashboardData }) {
  const by = data.software.by_status;
  const pending = (by.unclassified ?? 0) + (by.pending_review ?? 0);
  const segs = [
    { label: "Autorizadas", value: (by.authorized ?? 0) + (by.exception ?? 0), className: "bg-chart-1", swatch: "bg-chart-1" },
    { label: "Con condiciones", value: by.conditional ?? 0, className: "bg-chart-2", swatch: "bg-chart-2" },
    { label: "No autorizadas", value: by.unauthorized ?? 0, className: "bg-signal-fill", swatch: "bg-signal-fill", tone: "signal" as const },
    { label: "Por decidir", value: pending, className: HATCH, swatch: HATCH },
  ];
  const m = data.monthly;
  const status = m.snapshot?.status;
  const phase = status === "approved" ? 4 : status === "draft" ? 1 : m.coverage.complete ? 1 : 0;
  const [y, mo] = m.period.split("-").map(Number);
  const daysLeft = Math.max(0, Math.ceil((new Date(y, mo, 1).getTime() - Date.now()) / 864e5));
  const sources = Object.values(m.coverage.sources);
  const days = data.changes_daily ?? [];
  const t = days.reduce((a, d) => ({ i: a.i + d.installed, u: a.u + d.updated, r: a.r + d.removed }), { i: 0, u: 0, r: 0 });
  return (
    <section aria-label="Contexto" className="flex flex-wrap gap-4 pt-2">
      <Card className="flex-[2_1_30rem]" label="Política de software">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-semibold">Política de software</h2>
          <Link to="/software" className="link text-xs">{fmtNumber(data.software.products)} aplicaciones</Link>
        </div>
        <StackBar segments={segs} height="h-11" label={segs.map((s) => `${s.value} ${s.label.toLowerCase()}`).join(", ")} />
        <div className="flex flex-wrap gap-x-7 gap-y-2 text-[13px]">
          {segs.map((s) => (
            <span key={s.label} className="inline-flex items-center gap-2">
              <Swatch className={s.swatch} />
              <b className={cx("disp text-lg", s.tone === "signal" && "text-signal")}>{fmtNumber(s.value)}</b>
              <span className="text-muted">{s.label.toLowerCase()}</span>
            </span>
          ))}
        </div>
      </Card>
      <Card className="flex-[1_1_18rem]" label="Cierre mensual">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-semibold">Cierre de {fmtPeriod(m.period).toLowerCase()}</h2>
          <span className={cx("code text-2xs", status === "approved" ? "text-muted" : "text-signal")}>
            {status === "approved" ? "CERRADO" : daysLeft === 1 ? "FALTA 1 DÍA" : `FALTAN ${daysLeft} DÍAS`}</span>
        </div>
        <Stepper steps={PHASES} current={Math.min(phase, 3)} />
        <p className="text-[13px] text-muted">
          {sources.length === 0 ? "Sin fuentes configuradas" : sources.map((s) => `${s.name} ${s.ok ? "completo" : s.runs ? "con errores" : "sin datos este mes"}`).join(" · ")}
        </p>
        <Link to={data.open_review_cases > 0 ? "/auditoria?tab=revision" : "/auditoria?tab=mensual"} className="link mt-auto text-[13px]">
          {data.open_review_cases > 0 ? `Revisar ${data.open_review_cases} casos pendientes →` : "Gestionar inventario →"}</Link>
      </Card>
      <Card className="flex-[1_1_18rem]" label="Movimiento">
        <h2 className="font-semibold">Movimiento · 30 días</h2>
        <Spark values={days.map((d) => d.installed + d.updated + d.removed)} height={56} highlightLast
          label={`${t.u} actualizaciones, ${t.i} instalaciones y ${t.r} desinstalaciones en 30 días`} />
        <p className="text-[13px] text-muted">
          <b className="text-fg">{fmtNumber(t.u)}</b> actualizaciones · <b className="text-fg">+{fmtNumber(t.i)}</b> instalaciones ·{" "}
          <b className="text-fg">−{fmtNumber(t.r)}</b> desinstalaciones</p>
      </Card>
    </section>
  );
}

export function Dashboard() {
  const { data, isLoading, error, refetch } = useDashboard();
  if (isLoading) return <Spinner />;
  if (error || !data) return <ErrorState error={error} retry={refetch} />;
  return (
    <>
      <Header data={data} />
      <div className="flex flex-col gap-7">
        <div className="flex flex-wrap items-stretch gap-7">
          <HealthHero data={data} />
          <FleetMap fleet={data.devices.fleet ?? []} />
        </div>
        <Actions data={data} />
        <Context data={data} />
      </div>
    </>
  );
}
