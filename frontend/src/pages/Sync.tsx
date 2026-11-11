import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, FileUp, LogIn, MoreHorizontal, Play, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { RunStatusBadge } from "@/components/badges";
import { ContextMenu, useContextMenu, type MenuEntry } from "@/components/ContextMenu";
import { DataTable, type Column } from "@/components/DataTable";
import { Bar, BigNum, FilterChips, HATCH, Kpi, KpiStrip, ScreenHeader, StackBar, StatusDot, groupByDay, hhmm, type DotKind } from "@/components/kit";
import { UploadDialog } from "@/components/UploadDialog";
import { Button, ConfirmDialog, DefinitionList, ErrorState, Modal, Notice, Spinner, cx, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { useDashboard, type DashboardData } from "@/lib/dashboard";
import { CHANGE_LABEL, TRIGGER_LABEL, fmtDateTime, fmtRelative, parseUtc } from "@/lib/format";
import { useAction, useUrlState } from "@/lib/hooks";
import type { DeviceCodeStart, DeviceCodeStatus, Paged, Run, Source } from "@/lib/types";

const STAT_LABEL: Record<string, string> = {
  devices_seen: "Dispositivos recibidos", devices_created: "Dispositivos nuevos", devices_matched: "Dispositivos conciliados",
  review_cases: "Casos de revisión", installs_seen: "Instalaciones recibidas", products_created: "Productos nuevos",
  software_installed: "Altas de software", software_removed: "Bajas de software", software_version_changed: "Cambios de versión",
  devices_not_observed: "Dispositivos no observados", unauthorized_active: "Instalaciones no autorizadas",
  graph_requests: "Peticiones a Graph", graph_throttled: "Limitaciones (429)", programs: "Programas", parse_errors: "Líneas no reconocidas",
};

const runDot = (s: Run["status"]): DotKind =>
  s === "succeeded" ? "success" : s === "failed" ? "failed" : s === "partial" ? "warning" : s === "cancelled" ? "muted" : "running";

/** Próxima ejecución de la programación mensual (día y hora en UTC). */
function nextRun(day: number, hour: number) {
  const now = new Date();
  let d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), day, hour));
  if (d <= now) d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, day, hour));
  return d;
}
const dateFmt = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short" });

function SyncSummary({ dash, runs, schedule }: { dash: DashboardData | undefined; runs: Run[];
  schedule?: { enabled: boolean; day: number; hour: number } }) {
  const hb = dash?.worker_heartbeat?.at;
  const age = hb ? Date.now() - (parseUtc(hb)?.getTime() ?? 0) : null;
  const limit = ((dash?.worker_interval_minutes ?? 1) * 2 + 10) * 60_000;
  const down = age === null || age > limit;
  const last20 = runs.filter((r) => !["queued", "running"].includes(r.status)).slice(0, 20);
  const okRuns = last20.filter((r) => r.status === "succeeded").length;
  const next = schedule?.enabled ? nextRun(schedule.day, schedule.hour) : null;
  const cov = dash?.devices.by_source;
  const total = dash?.devices.total ?? 0;
  const manual = cov?.manual ?? 0;
  const daysToNext = next ? Math.ceil((next.getTime() - Date.now()) / 864e5) : 0;
  return (
    <KpiStrip label="Estado de la sincronización" className="mb-6">
      <Kpi label="Worker" footer={hb ? `Último latido ${fmtRelative(hb)} · pasa cada ${dash?.worker_interval_minutes ?? 1} min` : "Nunca se ha ejecutado"}>
        <p className="disp flex items-center gap-2.5 text-[30px] font-semibold leading-none">
          <StatusDot kind={down ? "failed" : "success"} />{down ? "Parado" : "Activo"}</p>
      </Kpi>
      <Kpi label="Próxima programada" footer={next ? `Mensual · día ${schedule!.day} a las ${String(schedule!.hour).padStart(2, "0")}:00 UTC` : undefined}>
        {next ? <>
          <BigNum value={dateFmt.format(next)}>{daysToNext === 1 ? "mañana" : `faltan ${daysToNext} días`}</BigNum>
          <Bar value={Math.max(0, 30 - daysToNext)} max={30} />
        </> : <p className="text-sm text-muted">Programación desactivada</p>}
      </Kpi>
      <Kpi label={`Últimas ${last20.length} ejecuciones`}>
        <BigNum value={okRuns}>{`correctas · ${last20.length - okRuns} con problemas`}</BigNum>
        <div role="img" aria-label={`${okRuns} correctas y ${last20.length - okRuns} con problemas`} className="flex gap-[3px]">
          {[...last20].reverse().map((r) => <StatusDot key={r.id} kind={runDot(r.status)} className="!h-5 flex-1 !rounded-[3px]" />)}
        </div>
      </Kpi>
      <Kpi label="Cobertura" footer={manual ? `${manual} con inventario manual` : undefined}>
        <BigNum value={total - manual}>de {total} con fuente automática</BigNum>
        <StackBar label="Cobertura por fuente" segments={[
          { label: "Con fuente automática", value: total - manual, className: "bg-chart-1" },
          { label: "Manual", value: manual, className: HATCH },
        ]} />
      </Kpi>
    </KpiStrip>
  );
}

export default function Sync() {
  const can = useCan();
  const [params, setParams] = useSearchParams();
  const runId = params.get("run");
  const [upload, setUpload] = useState<"panda" | "intune" | null>(null);
  const { values, set, page } = useUrlState(["source", "status"] as const);
  const dash = useDashboard().data;
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api.get<{ "schedule.monthly"?: { enabled: boolean; day: number; hour: number } }>("/settings") });
  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api.get<Source[]>("/sources"), refetchInterval: 15_000 });
  const listParams = { source: values.source, status: values.status, page, page_size: 50 };
  const runs = useQuery({ queryKey: ["runs", listParams], queryFn: () => api.get<Paged<Run>>("/runs", listParams),
    refetchInterval: (q) => (q.state.data?.items.some((r) => r.status === "queued" || r.status === "running") ? 3_000 : 20_000),
    placeholderData: (p) => p });
  const recent = useQuery({ queryKey: ["runs", "recent"], queryFn: () => api.get<Paged<Run>>("/runs", { page_size: 20 }) });
  const start = useAction((source: string) => api.send<Run>("POST", "/runs", { source }), {
    success: "Sincronización en cola", invalidate: [["runs"], ["sources"]],
  });
  const retry = useAction((id: number) => api.send<Run>("POST", `/runs/${id}/retry`), { success: "Reintento en cola", invalidate: [["runs"]] });
  const toast = useToast();
  const ctx = useContextMenu();
  const go = useNavigate();
  const visibleSources = (sources.data ?? []).filter((s) => s.code !== "legacy");
  const apiSources = visibleSources.filter((s) => s.kind === "api" && s.enabled && s.configured);
  const lastOk = (recent.data?.items ?? []).find((r) => r.status === "succeeded");
  const hb = dash?.worker_heartbeat?.at;
  const workerDown = !hb || Date.now() - (parseUtc(hb)?.getTime() ?? 0) > ((dash?.worker_interval_minutes ?? 1) * 2 + 10) * 60_000;
  const nav = (src: string) => set({ source: src, page: null });

  const sourceMenu = (s: Source): MenuEntry[] => [
    ...(can.write && s.enabled && s.kind === "api" ? [{ label: "Sincronizar ahora", disabled: !s.configured, onSelect: () => start.mutate(s.code) }] : []),
    ...(can.write && s.enabled ? [{ label: s.code === "panda" ? "Importar exportación…" : "Importar CSV…", onSelect: () => setUpload(s.code as "panda" | "intune") }] : []),
    { label: "Ver sus ejecuciones", onSelect: () => nav(s.code) },
    ...(s.last_error ? ["separator" as const, { label: "Copiar el último error", onSelect: () => navigator.clipboard?.writeText(s.last_error ?? "").then(() => toast("ok", "Error copiado")) }] : []),
  ];
  const sourceDot = (s: Source): DotKind => !s.enabled ? "muted" : s.last_run?.status === "failed" ? "failed"
    : !s.last_success_at || Date.now() - (parseUtc(s.last_success_at)?.getTime() ?? 0) > 31 * 864e5 ? "warning" : "success";
  const sourceNote = (s: Source) => !s.enabled ? "Desactivada" : s.kind === "api" && !s.configured ? "Sin conectar con Microsoft"
    : s.last_error ? s.last_error : sourceDot(s) === "warning" ? (s.code === "panda" ? "Sin datos este mes: sube la exportación" : "Sin datos recientes") : null;

  const cols: Column<Run>[] = [
    { id: "id", header: "#", cell: (r) => <button className="code text-muted hover:text-fg hover:underline" onClick={() => setParams({ run: String(r.id) })}>{r.id}</button> },
    { id: "src", header: "Fuente", cell: (r) => <span className="flex items-center gap-2.5 font-semibold"><StatusDot kind={runDot(r.status)} />{r.source_name}</span> },
    { id: "trg", header: "Origen", cell: (r) => <span className="block max-w-72 truncate text-muted" title={r.filename ?? undefined}>{TRIGGER_LABEL[r.trigger] ?? r.trigger}{r.filename && ` · ${r.filename}`}</span> },
    { id: "st", header: "Estado", cell: (r) => <RunStatusBadge status={r.status} /> },
    { id: "sum", header: "Resultado", cell: (r) => r.status === "running" && r.progress ? <span className="text-xs text-muted">{r.progress}</span>
      : r.status === "failed" ? <span className="block max-w-80 truncate text-xs text-signal" title={r.error ?? ""}>{r.error}</span>
      : r.stats?.devices_seen != null ? <span className="text-xs text-muted">{String(r.stats.devices_seen)} equipos · {String(r.stats.installs_seen ?? 0)} instalaciones · {String(r.stats.changes ?? 0)} cambios</span> : "—" },
    { id: "by", header: "Solicitada por", cell: (r) => <span className="text-muted">{r.requested_by}</span> },
    { id: "at", header: "Hora", cell: (r) => <span className="code whitespace-nowrap text-muted" title={fmtDateTime(r.requested_at)}>{hhmm(r.requested_at)}</span> },
  ];

  return (
    <>
      <ScreenHeader eyebrow="Fuentes · Sincronización"
        title={lastOk ? `Última recogida ${fmtRelative(lastOk.finished_at ?? lastOk.requested_at)}` : "Sin recogidas completas"}
        sub={workerDown ? "· el worker está parado" : "· el worker está activo"}
        actions={can.write && <>
          <Button icon={<FileUp className="size-4" />} onClick={() => setUpload("panda")}>Importar fichero</Button>
          <Button variant="primary" icon={<Play className="size-4" />} disabled={apiSources.length === 0} loading={start.isPending}
            onClick={() => apiSources.forEach((s) => start.mutate(s.code))}>Sincronizar todo</Button>
        </>} />
      <SyncSummary dash={dash} runs={recent.data?.items ?? []} schedule={settings.data?.["schedule.monthly"]} />

      <section aria-label="Fuentes" className="card mb-6 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3.5">
          <h2 className="font-semibold">Fuentes</h2>
          <span className="text-xs text-muted">Si dos fuentes discrepan, gana la de prioridad más baja (arriba)</span>
        </div>
        {sources.isLoading ? <Spinner /> : sources.error ? <ErrorState error={sources.error} /> : (
          <ul>
            {[...visibleSources].sort((a, b) => a.priority - b.priority).map((s) => (
              <li key={s.code} className="border-t border-border first:border-t-0"
                onContextMenu={(e) => ctx.openAt(e, sourceMenu(s), s.name)}>
                <div className="grid grid-cols-1 items-center gap-x-6 gap-y-2 px-4 py-4 transition-colors hover:bg-subtle md:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,0.7fr)_minmax(0,1.6fr)_auto_auto]">
                  <div className="flex min-w-0 items-center gap-3">
                    <StatusDot kind={sourceDot(s)} />
                    <div className="min-w-0">
                      <p className="truncate text-[15px] font-semibold">{s.name}</p>
                      <p className="text-xs text-muted">{s.kind === "api" ? "API automática" : "Ficheros"} · prioridad {s.priority}</p>
                    </div>
                  </div>
                  <div className="text-[13px]"><p className="eyebrow">Última correcta</p>{fmtRelative(s.last_success_at)}</div>
                  <div className="text-[13px]"><p className="eyebrow">Equipos</p><b className="disp">{s.devices}</b></div>
                  <p className={cx("line-clamp-2 text-[13px]", s.last_error || sourceDot(s) === "warning" ? "text-signal" : "text-muted")}
                    title={sourceNote(s) ?? undefined}>{sourceNote(s) ?? `${s.devices_with_software} con software`}</p>
                  <div className="flex gap-2">
                    {can.write && s.enabled && (s.kind === "api"
                      ? <Button size="sm" variant="primary" icon={<Play className="size-3.5" />} disabled={!s.configured}
                          loading={start.isPending && start.variables === s.code} onClick={() => start.mutate(s.code)}
                          title={s.configured ? undefined : "Conecte con Microsoft para sincronizar"}>Sincronizar ahora</Button>
                      : <Button size="sm" icon={<FileUp className="size-3.5" />} onClick={() => setUpload(s.code as "panda" | "intune")}>
                          {s.code === "panda" ? "Importar exportación" : "Importar CSV"}</Button>)}
                  </div>
                  <button type="button" aria-label={`Acciones de ${s.name}`} aria-haspopup="menu"
                    onClick={(e) => ctx.openFrom(e.currentTarget, sourceMenu(s), s.name)}
                    className="inline-flex size-9 items-center justify-center justify-self-end rounded-md text-muted hover:bg-surface hover:text-fg">
                    <MoreHorizontal className="size-4" /></button>
                </div>
                {s.code === "intune" && <div className="px-4 pb-4 pl-[46px]"><GraphConnection source={s} /></div>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <DataTable columns={cols} rows={runs.data?.items} total={runs.data?.total} rowKey={(r) => r.id} loading={runs.isLoading} error={runs.error}
        groups={groupByDay(runs.data?.items ?? [], (r) => r.requested_at)}
        page={page} pageSize={50} onPage={(p) => set({ page: p }, false)}
        onRowClick={(r) => setParams({ run: String(r.id) })}
        rowMenu={(r) => ({ title: `Ejecución #${r.id}`, entries: [
          { label: "Ver detalle", hint: "Intro", onSelect: () => setParams({ run: String(r.id) }) },
          ...(can.write && ["failed", "partial"].includes(r.status) ? [{ label: "Reintentar", onSelect: () => retry.mutate(r.id) }] : []),
          { label: "Ver cambios que produjo", onSelect: () => go("/auditoria?tab=cambios") },
          ...(r.error ? [{ label: "Copiar el error", onSelect: () => navigator.clipboard?.writeText(r.error ?? "").then(() => toast("ok", "Error copiado")) }] : []),
        ] })}
        header={<div className="flex flex-wrap items-center gap-3 py-3">
          <h2 className="mr-2 font-semibold">Ejecuciones</h2>
          <FilterChips label="Estado" value={values.status ?? "all"} onChange={(v) => set({ status: v === "all" ? null : v })} options={[
            { id: "all", label: "Todas" },
            { id: "succeeded", label: "Correctas", dot: "success" },
            { id: "failed,partial", label: "Con problemas", dot: "failed" },
            { id: "queued,running", label: "En curso", dot: "running" },
          ]} />
          <FilterChips label="Fuente" value={values.source ?? "all"} onChange={(v) => set({ source: v === "all" ? null : v })} options={[
            { id: "all", label: "Todas las fuentes" }, { id: "intune", label: "Intune" }, { id: "panda", label: "Panda" },
          ]} />
        </div>} />
      <ContextMenu menu={ctx.menu} onClose={ctx.close} />
      {upload && <UploadDialog source={upload} onClose={() => setUpload(null)} />}
      {runId && <RunDetail id={Number(runId)} onClose={() => { params.delete("run"); setParams(params); }} />}
    </>
  );
}

/** Sesión de Microsoft para Intune sin registro de aplicación: código de dispositivo iniciado desde la web. */
function GraphConnection({ source }: { source: Source }) {
  const can = useCan();
  const qc = useQueryClient();
  const [code, setCode] = useState<DeviceCodeStart | null>(null);
  const [confirmOff, setConfirmOff] = useState(false);
  // full: pide además los permisos de conformidad y acciones remotas (requieren aprobación de un administrador).
  const connect = useAction((level: "read" | "mail" | "full") =>
    api.send<DeviceCodeStart>("POST", `/sources/intune/connect?level=${level}`), { onSuccess: setCode });
  const level = source.graph_scopes ?? (source.graph_read_only ? "read" : "full");
  const disconnect = useAction(() => api.send("DELETE", "/sources/intune/connect"), {
    success: "Sesión de Microsoft desconectada", invalidate: [["sources"]], onSuccess: () => setConfirmOff(false),
  });
  const status = useQuery({
    queryKey: ["intune-connect", code?.user_code], enabled: !!code,
    queryFn: () => api.get<DeviceCodeStatus>("/sources/intune/connect"),
    refetchInterval: (q) => (q.state.data && q.state.data.status !== "pending" ? false : Math.max(code?.interval ?? 5, 3) * 1000),
  });
  const st = status.data?.status;
  useEffect(() => {
    if (st === "connected") qc.invalidateQueries({ queryKey: ["sources"] });
  }, [st, qc]);

  if (source.graph_auth === "app") return <p className="mt-3 text-xs text-muted">Conectado con credenciales de aplicación.</p>;
  return (
    <>
      {source.graph_auth === "delegated" ? (
        <>
          <p className="mt-3 text-xs text-muted">Conectado como <span className="font-medium text-fg">{source.graph_account ?? "cuenta de Microsoft"}</span>
            {can.admin && <> · <button className="link" onClick={() => setConfirmOff(true)}>Desconectar</button></>}</p>
          {level !== "full" && (
            <p className="mt-1.5 text-xs text-muted">
              Permisos: {level === "read" ? "solo inventario" : "inventario, avisos por correo y fotos de perfil"}. El motivo de la no conformidad, las
              acciones remotas y la desinstalación requieren permisos aprobados por un administrador global del tenant
              {can.admin && <>
                {level === "read" && <> · <button className="link" disabled={connect.isPending} onClick={() => connect.mutate("mail")}>Activar avisos por correo y fotos de perfil</button></>}
                {" · "}<button className="link" disabled={connect.isPending} onClick={() => connect.mutate("full")}>Ampliar todos los permisos</button>
              </>}.</p>
          )}
          <p className="mt-1.5 text-xs text-muted">Sesión con el cliente público de Microsoft (Graph Command Line Tools). Para
            producción se recomienda un registro de aplicación propio: ver docs/integrations.md.</p>
        </>
      ) : can.admin && (
        <div className="mt-3"><Button size="sm" icon={<LogIn className="size-3.5" />} loading={connect.isPending}
          onClick={() => connect.mutate("read")}>Conectar con Microsoft</Button></div>
      )}
      <Modal open={!!code} onClose={() => setCode(null)} title="Conectar con Microsoft"
        footer={<Button onClick={() => setCode(null)}>{st === "connected" ? "Cerrar" : "Cancelar"}</Button>}>
        {code && (st === "connected" ? (
          <Notice tone="ok" title="Conectado">Sesión iniciada como {status.data?.account || "su cuenta"}. Intune se sincronizará solo según la programación; también puede pulsar «Sincronizar ahora».</Notice>
        ) : st === "expired" || st === "error" ? (
          <Notice tone="danger" title="No se pudo conectar">{status.data?.error ?? "El código ha caducado."} Cierre y vuelva a intentarlo.</Notice>
        ) : (
          <div className="space-y-3 text-sm">
            <p>1. Abra <a className="link" href={code.verification_uri} target="_blank" rel="noreferrer">{code.verification_uri}</a></p>
            <p>2. Escriba este código e inicie sesión con una cuenta con acceso a Intune:</p>
            <div className="flex items-center gap-2">
              <code className="rounded-md bg-subtle px-3 py-2 font-mono text-lg tracking-widest">{code.user_code}</code>
              <Button size="sm" icon={<Copy className="size-3.5" />} onClick={() => navigator.clipboard?.writeText(code.user_code)}>Copiar</Button>
            </div>
            <Spinner label="Esperando a que complete el inicio de sesión…" />
          </div>
        ))}
      </Modal>
      <ConfirmDialog open={confirmOff} title="Desconectar de Microsoft" danger confirmLabel="Desconectar" busy={disconnect.isPending}
        onConfirm={() => disconnect.mutate(undefined)} onClose={() => setConfirmOff(false)}>
        Intune dejará de sincronizarse solo hasta que vuelva a conectar. Los datos ya importados se conservan.
      </ConfirmDialog>
    </>
  );
}

function RunDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const can = useCan();
  const q = useQuery({ queryKey: ["run", id], queryFn: () => api.get<Run>(`/runs/${id}`),
    refetchInterval: (q) => (q.state.data && ["queued", "running"].includes(q.state.data.status) ? 2_000 : false) });
  const retry = useAction(() => api.send<Run>("POST", `/runs/${id}/retry`), { success: "Reintento en cola", invalidate: [["runs"]], onSuccess: onClose });
  const r = q.data;
  return (
    <Modal open onClose={onClose} title={`Ejecución #${id}`} wide footer={r && can.write && ["failed", "partial"].includes(r.status) &&
      <Button variant="primary" icon={<RotateCcw className="size-4" />} loading={retry.isPending} onClick={() => retry.mutate(undefined)}>Reintentar</Button>}>
      {!r ? <Spinner /> : (
        <div className="space-y-4">
          <DefinitionList items={[
            ["Fuente", r.source_name], ["Estado", <RunStatusBadge key="s" status={r.status} />],
            ["Origen", `${TRIGGER_LABEL[r.trigger] ?? r.trigger}${r.attempt > 1 ? ` · intento ${r.attempt}` : ""}`],
            ["Completa", r.is_complete ? "Sí" : "No — no se han inferido bajas"],
            ["Inicio", fmtDateTime(r.started_at)], ["Fin", fmtDateTime(r.finished_at)],
          ]} />
          {r.error && <Notice tone="danger" title="Error"><span className="whitespace-pre-line font-mono text-xs">{r.error}</span></Notice>}
          {Array.isArray(r.stats?.warnings) && (r.stats.warnings as string[]).length > 0 && (
            <Notice tone="warn" title="Avisos"><ul className="list-disc pl-4">{(r.stats.warnings as string[]).slice(0, 10).map((w, i) => <li key={i}>{w}</li>)}</ul></Notice>
          )}
          <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
            {Object.entries(r.stats ?? {}).filter(([k, v]) => STAT_LABEL[k] && typeof v === "number").map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-border py-1"><span className="text-muted">{STAT_LABEL[k]}</span><span className="num">{String(v)}</span></div>
            ))}
            {Object.entries(r.changes ?? {}).map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-border py-1"><span className="text-muted">{CHANGE_LABEL[k] ?? k}</span><span className="num">{v}</span></div>
            ))}
          </div>
          {r.log && r.log.length > 0 && (
            <details><summary className="cursor-pointer text-sm text-muted">Registro de ejecución ({r.log.length} líneas)</summary>
              <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-subtle p-3 font-mono text-2xs">{r.log.join("\n")}</pre></details>
          )}
        </div>
      )}
    </Modal>
  );
}
