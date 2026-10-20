import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, FileUp, LogIn, Play, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { RunStatusBadge } from "@/components/badges";
import { DataTable, type Column } from "@/components/DataTable";
import { UploadDialog } from "@/components/UploadDialog";
import { Badge, Button, Card, ConfirmDialog, DefinitionList, ErrorState, Modal, Notice, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { CHANGE_LABEL, TRIGGER_LABEL, fmtDateTime, fmtRelative } from "@/lib/format";
import { useAction, useUrlState } from "@/lib/hooks";
import type { DeviceCodeStart, DeviceCodeStatus, Paged, Run, Source } from "@/lib/types";

const STAT_LABEL: Record<string, string> = {
  devices_seen: "Dispositivos recibidos", devices_created: "Dispositivos nuevos", devices_matched: "Dispositivos conciliados",
  review_cases: "Casos de revisión", installs_seen: "Instalaciones recibidas", products_created: "Productos nuevos",
  software_installed: "Altas de software", software_removed: "Bajas de software", software_version_changed: "Cambios de versión",
  devices_not_observed: "Dispositivos no observados", unauthorized_active: "Instalaciones no autorizadas",
  graph_requests: "Peticiones a Graph", graph_throttled: "Limitaciones (429)", programs: "Programas", parse_errors: "Líneas no reconocidas",
};

export default function Sync() {
  const can = useCan();
  const [params, setParams] = useSearchParams();
  const runId = params.get("run");
  const [upload, setUpload] = useState<"panda" | "intune" | null>(null);
  const { values, set, page } = useUrlState(["source", "status"] as const);
  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api.get<Source[]>("/sources"), refetchInterval: 15_000 });
  const listParams = { source: values.source, status: values.status, page, page_size: 25 };
  const runs = useQuery({ queryKey: ["runs", listParams], queryFn: () => api.get<Paged<Run>>("/runs", listParams),
    refetchInterval: (q) => (q.state.data?.items.some((r) => r.status === "queued" || r.status === "running") ? 3_000 : 20_000),
    placeholderData: (p) => p });
  const start = useAction((source: string) => api.send<Run>("POST", "/runs", { source }), {
    success: "Sincronización en cola", invalidate: [["runs"], ["sources"]],
  });
  const cols: Column<Run>[] = [
    { id: "id", header: "#", cell: (r) => <button className="font-mono text-xs text-accent hover:underline" onClick={() => setParams({ run: String(r.id) })}>{r.id}</button> },
    { id: "src", header: "Fuente", cell: (r) => <span className="font-medium">{r.source_name}</span> },
    { id: "trg", header: "Origen", cell: (r) => <span className="block max-w-72 truncate text-muted" title={r.filename ?? undefined}>{TRIGGER_LABEL[r.trigger] ?? r.trigger}{r.filename && ` · ${r.filename}`}</span> },
    { id: "st", header: "Estado", cell: (r) => <RunStatusBadge status={r.status} /> },
    { id: "sum", header: "Resultado", cell: (r) => r.status === "running" && r.progress ? <span className="text-xs text-muted">{r.progress}</span>
      : r.status === "failed" ? <span className="block max-w-80 truncate text-xs text-danger" title={r.error ?? ""}>{r.error}</span>
      : r.stats?.devices_seen != null ? <span className="text-xs text-muted">{String(r.stats.devices_seen)} disp. · {String(r.stats.installs_seen ?? 0)} inst. · {String(r.stats.changes ?? 0)} cambios</span> : "—" },
    { id: "by", header: "Solicitada por", cell: (r) => <span className="text-muted">{r.requested_by}</span> },
    { id: "at", header: "Fecha", cell: (r) => <span className="whitespace-nowrap text-muted" title={fmtDateTime(r.requested_at)}>{fmtRelative(r.requested_at)}</span> },
  ];

  return (
    <>
      <PageHeader title="Sincronización" description="Conectores, ejecuciones e importación de ficheros. Todas las ejecuciones las procesa el worker." />
      {sources.isLoading ? <Spinner /> : sources.error ? <ErrorState error={sources.error} /> : (
        <div className="mb-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {sources.data!.filter((s) => s.code !== "legacy").map((s) => (
            <Card key={s.code} title={<span className="flex items-center gap-2">{s.name}
              {!s.enabled && <Badge>Desactivada</Badge>}{s.kind === "api" && !s.configured && <Badge tone="warn">Sin conectar</Badge>}</span>}>
              <DefinitionList items={[
                ["Tipo", s.kind === "api" ? "API automática" : "Ficheros"], ["Prioridad", s.priority],
                ["Última ejecución correcta", fmtRelative(s.last_success_at)],
                ["Último estado", s.last_run ? <span key="r" className="flex flex-wrap items-center gap-1.5"><RunStatusBadge status={s.last_run.status} />
                  {s.last_run.progress && <span className="text-xs text-muted">{s.last_run.progress}</span>}</span> : "—"],
                ["Dispositivos identificados", s.devices], ["Equipos con software", s.devices_with_software],
              ]} />
              {s.last_error && <p className="mt-3 line-clamp-3 text-xs text-danger" title={s.last_error}>{s.last_error}</p>}
              {s.code === "intune" && <GraphConnection source={s} />}
              {can.write && s.enabled && (
                <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-3">
                  {s.kind === "api" && <Button size="sm" variant="primary" icon={<Play className="size-3.5" />} disabled={!s.configured}
                    loading={start.isPending && start.variables === s.code} onClick={() => start.mutate(s.code)}
                    title={s.configured ? undefined : "Conecte con Microsoft para sincronizar"}>Sincronizar ahora</Button>}
                  <Button size="sm" icon={<FileUp className="size-3.5" />} onClick={() => setUpload(s.code as "panda" | "intune")}>
                    {s.code === "panda" ? "Importar exportación" : "Importar CSV"}</Button>
                </div>
              )}
              {s.code === "panda" && <p className="mt-3 text-xs text-muted">Carpeta supervisada: {s.watch_folder ? "activa" : "no configurada"}. API de WatchGuard: pendiente de confirmar licencia.</p>}
            </Card>
          ))}
        </div>
      )}
      <h2 className="mb-2 text-sm font-semibold">Historial de ejecuciones</h2>
      <DataTable columns={cols} rows={runs.data?.items} total={runs.data?.total} rowKey={(r) => r.id} loading={runs.isLoading} error={runs.error}
        page={page} pageSize={25} onPage={(p) => set({ page: p }, false)}
        toolbar={<>
          <select aria-label="Fuente" className="field w-auto" value={values.source ?? ""} onChange={(e) => set({ source: e.target.value || null })}>
            <option value="">Todas las fuentes</option><option value="intune">Intune</option><option value="panda">Panda</option>
          </select>
          <select aria-label="Estado" className="field w-auto" value={values.status ?? ""} onChange={(e) => set({ status: e.target.value || null })}>
            <option value="">Cualquier estado</option><option value="failed,partial">Con problemas</option><option value="queued,running">En curso</option><option value="succeeded">Completadas</option>
          </select>
        </>} />
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
  const connect = useAction(() => api.send<DeviceCodeStart>("POST", "/sources/intune/connect"), { onSuccess: setCode });
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
        <p className="mt-3 text-xs text-muted">Conectado como <span className="font-medium text-fg">{source.graph_account ?? "cuenta de Microsoft"}</span>
          {can.admin && <> · <button className="text-accent hover:underline" onClick={() => setConfirmOff(true)}>Desconectar</button></>}</p>
      ) : can.admin && (
        <div className="mt-3"><Button size="sm" icon={<LogIn className="size-3.5" />} loading={connect.isPending}
          onClick={() => connect.mutate(undefined)}>Conectar con Microsoft</Button></div>
      )}
      <Modal open={!!code} onClose={() => setCode(null)} title="Conectar con Microsoft"
        footer={<Button onClick={() => setCode(null)}>{st === "connected" ? "Cerrar" : "Cancelar"}</Button>}>
        {code && (st === "connected" ? (
          <Notice tone="ok" title="Conectado">Sesión iniciada como {status.data?.account || "su cuenta"}. Intune se sincronizará solo según la programación; también puede pulsar «Sincronizar ahora».</Notice>
        ) : st === "expired" || st === "error" ? (
          <Notice tone="danger" title="No se pudo conectar">{status.data?.error ?? "El código ha caducado."} Cierre y vuelva a intentarlo.</Notice>
        ) : (
          <div className="space-y-3 text-sm">
            <p>1. Abra <a className="text-accent hover:underline" href={code.verification_uri} target="_blank" rel="noreferrer">{code.verification_uri}</a></p>
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
