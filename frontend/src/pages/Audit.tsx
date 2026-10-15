import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Download, FileSpreadsheet, GitCompare, Plus, ShieldCheck, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { SeverityBadge, SnapshotBadge } from "@/components/badges";
import { DataTable, type Column } from "@/components/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Spinner, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { CHANGE_LABEL, FIELD_LABEL, SOURCE_LABEL, currentPeriod, fmtDateTime, fmtPeriod, fmtRelative } from "@/lib/format";
import { useAction, useUrlState } from "@/lib/hooks";
import type { Alert, Change, Paged, Snapshot } from "@/lib/types";

type Tab = "mensual" | "cambios" | "alertas" | "revision" | "registro";

export default function Audit() {
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") ?? "mensual") as Tab;
  return (
    <>
      <PageHeader title="Auditoría" description="Inventarios mensuales, cambios detectados, incidencias y evidencias trazables." />
      <Tabs value={tab} onChange={(t) => setParams({ tab: t })} tabs={[
        { id: "mensual", label: "Inventarios mensuales" }, { id: "cambios", label: "Cambios" },
        { id: "alertas", label: "Alertas" }, { id: "revision", label: "Casos de revisión" }, { id: "registro", label: "Registro de auditoría" },
      ]} />
      {tab === "mensual" && <Monthly />}
      {tab === "cambios" && <Changes />}
      {tab === "alertas" && <Alerts />}
      {tab === "revision" && <ReviewCases />}
      {tab === "registro" && <AuditLog />}
    </>
  );
}

// ------------------------------------------------------------------ inventarios mensuales
function Monthly() {
  const can = useCan();
  const q = useQuery({ queryKey: ["snapshots"], queryFn: () => api.get<Snapshot[]>("/snapshots") });
  const [period, setPeriod] = useState(currentPeriod());
  const [reviewing, setReviewing] = useState<Snapshot | null>(null);
  const [compare, setCompare] = useState<[number, number] | null>(null);
  const generate = useAction(() => api.send<Snapshot>("POST", "/snapshots", { period }), {
    success: "Inventario generado como borrador", invalidate: [["snapshots"], ["dashboard"]],
  });
  if (q.isLoading) return <Spinner />;
  const snaps = q.data ?? [];
  const cols: Column<Snapshot>[] = [
    { id: "p", header: "Periodo", cell: (s) => <span className="font-medium">{fmtPeriod(s.period)}{s.version > 1 && <span className="text-muted"> · v{s.version}</span>}</span> },
    { id: "st", header: "Estado", cell: (s) => <SnapshotBadge status={s.status} /> },
    { id: "c", header: "Recogida", cell: (s) => s.status === "legacy" ? <span className="text-muted">Importado</span>
      : s.is_complete ? <Badge tone="ok">Completa</Badge> : <Badge tone="warn">Incompleta</Badge> },
    { id: "d", header: "Dispositivos", align: "right", cell: (s) => s.totals?.devices ?? "—" },
    { id: "i", header: "Instalaciones", align: "right", cell: (s) => s.totals?.installations ?? "—" },
    { id: "u", header: "No autorizadas", align: "right", cell: (s) => s.totals?.by_status?.unauthorized ?? 0 },
    { id: "r", header: "Revisión", cell: (s) => s.reviewed_by ? <span className="text-xs text-muted">{s.reviewed_by} · {fmtDateTime(s.reviewed_at)}</span> : "—" },
    { id: "a", header: "", cell: (s) => {
      const prev = snaps.find((x) => x.period < s.period && x.status !== "rejected");
      return (
        <div className="flex justify-end gap-1">
          {prev && <Button size="sm" variant="ghost" icon={<GitCompare className="size-3.5" />} onClick={() => setCompare([prev.id, s.id])}>Comparar</Button>}
          <Button size="sm" variant="ghost" icon={<FileSpreadsheet className="size-3.5" />} onClick={() => api.download(`/snapshots/${s.id}/report`)}>Informe</Button>
          {can.write && s.status === "draft" && <Button size="sm" variant="primary" onClick={() => setReviewing(s)}>Revisar</Button>}
        </div>
      );
    } },
  ];
  return (
    <>
      <div className="mb-4">
        <Notice>
          La recogida automática y la aprobación son pasos separados: el worker genera el borrador mensual cuando terminan las
          sincronizaciones programadas, y un técnico lo revisa y aprueba. Un inventario solo es «completo» si todas las fuentes
          esenciales terminaron sin errores.
        </Notice>
      </div>
      <DataTable columns={cols} rows={snaps} rowKey={(s) => s.id} error={q.error}
        toolbar={can.write && <div className="flex items-center gap-2">
          <input type="month" aria-label="Periodo" className="field w-40" value={period} onChange={(e) => setPeriod(e.target.value)} />
          <Button icon={<Plus className="size-4" />} loading={generate.isPending} onClick={() => generate.mutate(undefined)}>Generar inventario</Button>
        </div>}
        empty={<EmptyState title="Aún no hay inventarios mensuales">Se generan automáticamente tras la sincronización programada o manualmente desde aquí.</EmptyState>} />
      {reviewing && <ReviewSnapshot snap={reviewing} onClose={() => setReviewing(null)} />}
      {compare && <CompareDialog ids={compare} onClose={() => setCompare(null)} />}
    </>
  );
}

function ReviewSnapshot({ snap, onClose }: { snap: Snapshot; onClose: () => void }) {
  const [notes, setNotes] = useState("");
  const [accept, setAccept] = useState(false);
  const review = useAction((approve: boolean) => api.send("POST", `/snapshots/${snap.id}/review`,
    { approve, notes: notes || null, accept_incomplete: accept }), { success: "Revisión registrada", invalidate: [["snapshots"], ["dashboard"]], onSuccess: onClose });
  const sources = Object.values(snap.coverage?.sources ?? {});
  return (
    <Modal open onClose={onClose} title={`Revisar inventario de ${fmtPeriod(snap.period)}`} footer={<>
      <Button onClick={() => review.mutate(false)} loading={review.isPending}>Rechazar</Button>
      <Button variant="primary" disabled={!snap.is_complete && (!accept || !notes.trim())} loading={review.isPending}
        onClick={() => review.mutate(true)}>Aprobar</Button>
    </>}>
      <div className="space-y-4">
        <ul className="space-y-1.5">{sources.map((s) => (
          <li key={s.name} className="flex items-center gap-2">
            {s.ok ? <ShieldCheck className="size-4 text-ok" aria-hidden /> : <ShieldAlert className="size-4 text-warn" aria-hidden />}
            {s.name}{!s.essential && <span className="text-xs text-muted">(complementaria)</span>}
            <span className="ml-auto text-xs text-muted">{s.ok ? "completa" : s.runs ? "con errores" : "sin ejecuciones"}</span>
          </li>
        ))}</ul>
        <p className="text-muted">{snap.totals?.devices} dispositivos · {snap.totals?.installations} instalaciones · {snap.totals?.products} productos</p>
        {!snap.is_complete && (
          <Notice tone="warn" title="Inventario incompleto">
            Alguna fuente esencial no completó la recogida. Lo recomendable es reintentar la sincronización y regenerar el inventario.
            <label className="mt-2 flex items-center gap-2"><input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} className="accent-[rgb(var(--accent))]" />
              Acepto aprobarlo incompleto (requiere justificación)</label>
          </Notice>
        )}
        <Field label="Notas de revisión">{(id) => <textarea id={id} rows={3} className="field" value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}

interface Diff {
  devices_added: { id: number; name: string }[]; devices_removed: { id: number; name: string }[];
  products_new: { id: number; name: string }[]; products_gone: { id: number; name: string }[];
  installs_added: { device_id: number; device: string; product_id: number; product: string; versions: string[] }[];
  installs_removed: { device_id: number; device: string; product_id: number; product: string; versions: string[] }[];
  versions_changed: { device_id: number; device: string; product_id: number; product: string; from: string[]; to: string[] }[];
}

function CompareDialog({ ids, onClose }: { ids: [number, number]; onClose: () => void }) {
  const q = useQuery({ queryKey: ["compare", ids], queryFn: () => api.get<Diff>("/snapshots/compare", { base: ids[0], target: ids[1] }) });
  const d = q.data;
  const list = (title: string, items: { key: string; text: React.ReactNode }[]) => (
    <Card title={`${title} (${items.length})`} padded={false}>
      {items.length === 0 ? <p className="px-4 py-3 text-muted">Ninguno</p> : (
        <ul className="max-h-56 divide-y divide-border overflow-y-auto">{items.map((i) => <li key={i.key} className="px-4 py-1.5">{i.text}</li>)}</ul>
      )}
    </Card>
  );
  return (
    <Modal open onClose={onClose} title="Comparación de inventarios" wide>
      {!d ? <Spinner /> : (
        <div className="grid gap-3 md:grid-cols-2">
          {list("Dispositivos nuevos", d.devices_added.map((x) => ({ key: `${x.id}`, text: <Link to={`/dispositivos/${x.id}`}>{x.name}</Link> })))}
          {list("Dispositivos que ya no figuran", d.devices_removed.map((x) => ({ key: `${x.id}`, text: x.name })))}
          {list("Productos nuevos", d.products_new.map((x) => ({ key: `${x.id}`, text: <Link to={`/software/${x.id}`}>{x.name}</Link> })))}
          {list("Productos desaparecidos", d.products_gone.map((x) => ({ key: `${x.id}`, text: x.name })))}
          {list("Instalaciones nuevas", d.installs_added.map((x) => ({ key: `${x.device_id}-${x.product_id}`, text: <>{x.product} <span className="text-muted">· {x.device}</span></> })))}
          {list("Desinstalaciones", d.installs_removed.map((x) => ({ key: `${x.device_id}-${x.product_id}`, text: <>{x.product} <span className="text-muted">· {x.device}</span></> })))}
          <div className="md:col-span-2">{list("Cambios de versión", d.versions_changed.map((x) => ({ key: `${x.device_id}-${x.product_id}`,
            text: <>{x.product} <span className="text-muted">· {x.device} · {x.from.join(", ")} → {x.to.join(", ")}</span></> })))}</div>
        </div>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ cambios
const CHANGE_GROUPS: Record<string, string> = {
  "": "Todos los cambios",
  "software_installed,software_removed,software_version_changed": "Software",
  "device_added,device_retired,device_not_observed,device_updated,device_reactivated,device_merged": "Dispositivos",
  "department_changed,user_changed": "Asignaciones",
  "authorization_changed": "Autorizaciones",
};

function Changes() {
  const { values, set, page } = useUrlState(["type", "since"] as const);
  const params = { type: values.type, since: values.since, page, page_size: 50 };
  const q = useQuery({ queryKey: ["changes", params], queryFn: () => api.get<Paged<Change>>("/changes", params), placeholderData: (p) => p });
  const cols: Column<Change>[] = [
    { id: "at", header: "Fecha", cell: (c) => <span className="whitespace-nowrap text-muted">{fmtDateTime(c.at)}</span> },
    { id: "type", header: "Cambio", cell: (c) => CHANGE_LABEL[c.type] ?? c.type },
    { id: "device", header: "Dispositivo", cell: (c) => c.device ? <Link className="hover:underline" to={`/dispositivos/${c.device_id}`}>{c.device}</Link> : "—" },
    { id: "product", header: "Software / campo", cell: (c) => c.product ? <Link className="hover:underline" to={`/software/${c.product_id}`}>{c.product}</Link> : c.field ? FIELD_LABEL[c.field] ?? c.field : "—" },
    { id: "diff", header: "Detalle", cell: (c) => (c.old || c.new) ? <span className="font-mono text-xs">{c.old ?? "—"} → {c.new ?? "—"}</span> : "—" },
    { id: "src", header: "Fuente", cell: (c) => <span className="text-muted">{SOURCE_LABEL[c.source ?? ""] ?? c.source}</span> },
  ];
  return (
    <DataTable columns={cols} rows={q.data?.items} total={q.data?.total} rowKey={(c) => c.id} loading={q.isLoading} error={q.error}
      page={page} pageSize={50} onPage={(p) => set({ page: p }, false)} storageKey="changes"
      toolbar={<>
        <select aria-label="Tipo de cambio" className="field w-auto" value={values.type ?? ""} onChange={(e) => set({ type: e.target.value || null })}>
          {Object.entries(CHANGE_GROUPS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <input type="date" aria-label="Desde" className="field w-40" value={values.since?.slice(0, 10) ?? ""}
          onChange={(e) => set({ since: e.target.value ? `${e.target.value}T00:00:00` : null })} />
        <Button size="sm" icon={<Download className="size-4" />} onClick={() => api.download("/changes/export", { format: "xlsx", type: values.type, since: values.since })}>Exportar</Button>
      </>} />
  );
}

// ------------------------------------------------------------------ alertas
function Alerts() {
  const can = useCan();
  const { values, set, page } = useUrlState(["status", "severity"] as const);
  const status = values.status ?? "open,acknowledged";
  const params = { status, severity: values.severity, page, page_size: 50 };
  const q = useQuery({ queryKey: ["alerts", params], queryFn: () => api.get<Paged<Alert>>("/alerts", params), placeholderData: (p) => p });
  const [resolving, setResolving] = useState<Alert | null>(null);
  const [note, setNote] = useState("");
  const act = useAction(({ id, action, note }: { id: number; action: string; note?: string }) => api.send("POST", `/alerts/${id}`, { action, note }), {
    success: "Alerta actualizada", invalidate: [["alerts"], ["alerts-count"], ["dashboard"]], onSuccess: () => { setResolving(null); setNote(""); },
  });
  const cols: Column<Alert>[] = [
    { id: "sev", header: "Severidad", cell: (a) => <SeverityBadge severity={a.severity} /> },
    { id: "title", header: "Incidencia", cell: (a) => <div className="min-w-0"><p className="font-medium">{a.title}</p>
      {a.detail && <p className="line-clamp-2 text-xs text-muted">{a.detail}</p>}</div> },
    { id: "link", header: "Relacionado", cell: (a) => <div className="flex flex-col text-xs">
      {a.device_id && <Link className="text-accent hover:underline" to={`/dispositivos/${a.device_id}`}>Dispositivo</Link>}
      {a.product_id && <Link className="text-accent hover:underline" to={`/software/${a.product_id}`}>Producto</Link>}
      {a.run_id && <Link className="text-accent hover:underline" to={`/sincronizacion?run=${a.run_id}`}>Ejecución #{a.run_id}</Link>}</div> },
    { id: "when", header: "Detectada", cell: (a) => <span className="whitespace-nowrap text-muted" title={`Vista por última vez ${fmtDateTime(a.last_seen_at)}`}>{fmtRelative(a.created_at)}</span> },
    { id: "status", header: "Estado", cell: (a) => a.status === "resolved"
      ? <span className="text-xs text-muted" title={a.resolution ?? ""}>Resuelta por {a.resolved_by}</span>
      : a.status === "acknowledged" ? <Badge tone="info">En curso</Badge> : <Badge tone="warn">Abierta</Badge> },
    { id: "act", header: "", cell: (a) => can.write && a.status !== "resolved" && <div className="flex justify-end gap-1">
      {a.status === "open" && <Button size="sm" variant="ghost" onClick={() => act.mutate({ id: a.id, action: "acknowledge" })}>Asumir</Button>}
      <Button size="sm" onClick={() => setResolving(a)}>Resolver</Button></div> },
  ];
  return (
    <>
      <DataTable columns={cols} rows={q.data?.items} total={q.data?.total} rowKey={(a) => a.id} loading={q.isLoading} error={q.error}
        page={page} pageSize={50} onPage={(p) => set({ page: p }, false)}
        empty={<EmptyState title="Sin alertas" icon={<CheckCircle2 className="size-5 text-ok" />} />}
        toolbar={<>
          <select aria-label="Estado" className="field w-auto" value={status} onChange={(e) => set({ status: e.target.value })}>
            <option value="open,acknowledged">Pendientes</option><option value="resolved">Resueltas</option><option value="open,acknowledged,resolved">Todas</option>
          </select>
          <select aria-label="Severidad" className="field w-auto" value={values.severity ?? ""} onChange={(e) => set({ severity: e.target.value || null })}>
            <option value="">Cualquier severidad</option><option value="critical">Crítica</option><option value="warning">Aviso</option><option value="info">Info</option>
          </select>
        </>} />
      {resolving && (
        <Modal open onClose={() => setResolving(null)} title="Resolver alerta" footer={<>
          <Button onClick={() => setResolving(null)}>Cancelar</Button>
          <Button variant="primary" disabled={!note.trim()} loading={act.isPending} onClick={() => act.mutate({ id: resolving.id, action: "resolve", note })}>Resolver</Button>
        </>}>
          <p className="mb-3 font-medium">{resolving.title}</p>
          <Field label="¿Cómo se ha resuelto?" hint="Si la condición persiste, la próxima sincronización volverá a abrir la alerta.">
            {(id) => <textarea id={id} rows={3} className="field" value={note} onChange={(e) => setNote(e.target.value)} />}
          </Field>
        </Modal>
      )}
    </>
  );
}

// ------------------------------------------------------------------ casos de revisión
interface Case { id: number; type: string; summary: string; data: Record<string, unknown>; created_at: string; run_id: number | null }

function ReviewCases() {
  const can = useCan();
  const q = useQuery({ queryKey: ["review-cases"], queryFn: () => api.get<Case[]>("/review-cases") });
  const [open, setOpen] = useState<Case | null>(null);
  const [form, setForm] = useState({ action: "dismiss", note: "", keep: "", merge: "" });
  const resolve = useAction(() => api.send("POST", `/review-cases/${open!.id}`, { action: form.action, note: form.note,
    keep_device_id: form.keep ? Number(form.keep) : null, merge_device_id: form.merge ? Number(form.merge) : null }), {
    success: "Caso resuelto", invalidate: [["review-cases"], ["devices"], ["dashboard"]], onSuccess: () => setOpen(null),
  });
  const ids = (c: Case) => [c.data.existing_device_id, ...(Array.isArray(c.data.device_ids) ? c.data.device_ids : [])].filter(Boolean) as number[];
  return (
    <>
      <div className="mb-3"><Notice>Cuando la conciliación no tiene información suficiente para decidir si dos registros son el mismo equipo, no fusiona nada y abre un caso aquí.</Notice></div>
      <DataTable rows={q.data} rowKey={(c) => c.id} loading={q.isLoading} error={q.error}
        empty={<EmptyState title="No hay casos pendientes" icon={<CheckCircle2 className="size-5 text-ok" />} />}
        columns={[
          { id: "s", header: "Caso", cell: (c) => <span className="font-medium">{c.summary}</span> },
          { id: "d", header: "Dispositivos", cell: (c) => <div className="flex gap-2">{ids(c).map((i) => <Link key={i} className="text-accent hover:underline" to={`/dispositivos/${i}`}>#{i}</Link>)}</div> },
          { id: "w", header: "Detectado", cell: (c) => <span className="text-muted">{fmtRelative(c.created_at)}</span> },
          { id: "a", header: "", cell: (c) => can.write && <Button size="sm" onClick={() => { setOpen(c); setForm({ action: "dismiss", note: "", keep: String(ids(c)[0] ?? ""), merge: String(ids(c)[1] ?? "") }); }}>Resolver</Button> },
        ]} />
      {open && (
        <Modal open onClose={() => setOpen(null)} title="Resolver caso de conciliación" footer={<>
          <Button onClick={() => setOpen(null)}>Cancelar</Button>
          <Button variant={form.action === "merge_devices" ? "danger" : "primary"} disabled={form.note.trim().length < 3} loading={resolve.isPending}
            onClick={() => resolve.mutate(undefined)}>{form.action === "merge_devices" ? "Fusionar" : "Descartar"}</Button>
        </>}>
          <div className="space-y-4">
            <p>{open.summary}</p>
            <pre className="max-h-40 overflow-auto rounded-md bg-subtle p-3 font-mono text-2xs">{JSON.stringify(open.data, null, 2)}</pre>
            <Field label="Decisión">{(id) => <select id={id} className="field" value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })}>
              <option value="dismiss">Son equipos distintos (descartar)</option><option value="merge_devices">Son el mismo equipo (fusionar)</option></select>}</Field>
            {form.action === "merge_devices" && <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Conservar dispositivo #">{(id) => <input id={id} className="field" value={form.keep} onChange={(e) => setForm({ ...form, keep: e.target.value })} />}</Field>
              <Field label="Fusionar y retirar #">{(id) => <input id={id} className="field" value={form.merge} onChange={(e) => setForm({ ...form, merge: e.target.value })} />}</Field>
            </div>}
            <Field label="Justificación">{(id) => <input id={id} className="field" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />}</Field>
          </div>
        </Modal>
      )}
    </>
  );
}

// ------------------------------------------------------------------ registro
interface Event { id: number; at: string; actor: string; action: string; entity_type: string; entity_id: string | null; summary: string | null; hash: string }

function AuditLog() {
  const { values, set, page } = useUrlState(["actor", "entity_type"] as const);
  const params = { actor: values.actor, entity_type: values.entity_type, page, page_size: 50 };
  const q = useQuery({ queryKey: ["audit", params], queryFn: () => api.get<Paged<Event>>("/audit", params), placeholderData: (p) => p });
  const verify = useQuery({ queryKey: ["audit-verify"], queryFn: () => api.get<{ valid: boolean; checked: number; broken_event_id: number | null }>("/audit/verify"), enabled: false });
  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Button icon={<ShieldCheck className="size-4" />} loading={verify.isFetching} onClick={() => verify.refetch()}>Verificar integridad</Button>
        {verify.data && (verify.data.valid
          ? <Badge tone="ok">Cadena íntegra · {verify.data.checked} eventos verificados</Badge>
          : <Badge tone="danger">Manipulación detectada en el evento #{verify.data.broken_event_id}</Badge>)}
        <Button className="ml-auto" icon={<Download className="size-4" />} onClick={() => api.download("/audit/export", { format: "xlsx" })}>Exportar evidencias</Button>
      </div>
      <DataTable rows={q.data?.items} total={q.data?.total} rowKey={(e) => e.id} loading={q.isLoading} error={q.error}
        page={page} pageSize={50} onPage={(p) => set({ page: p }, false)} search={values.actor ?? ""} onSearch={(s) => set({ actor: s })}
        searchPlaceholder="Filtrar por actor…" storageKey="audit"
        toolbar={<select aria-label="Entidad" className="field w-auto" value={values.entity_type ?? ""} onChange={(e) => set({ entity_type: e.target.value || null })}>
          <option value="">Todas las entidades</option>
          {["device", "department", "software_product", "software_policy", "inventory_run", "inventory_snapshot", "alert", "review_case", "app_setting", "inventory_source", "user"].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>}
        columns={[
          { id: "at", header: "Fecha (UTC)", cell: (e) => <span className="whitespace-nowrap text-muted">{fmtDateTime(e.at)}</span> },
          { id: "actor", header: "Actor", cell: (e) => e.actor },
          { id: "action", header: "Acción", cell: (e) => <span className="font-mono text-xs">{e.action}</span> },
          { id: "summary", header: "Resumen", cell: (e) => e.summary ?? "—" },
          { id: "hash", header: "Hash", hidden: true, cell: (e) => <span className="font-mono text-2xs" title={e.hash}>{e.hash.slice(0, 12)}…</span> },
        ]} />
    </>
  );
}
