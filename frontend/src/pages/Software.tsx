import { useQuery } from "@tanstack/react-query";
import { Download, Tags } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AuthBadge } from "@/components/badges";
import { DataTable, type Column } from "@/components/DataTable";
import { Badge, Button, ConfirmDialog, Field, Modal, PageHeader, Stat, StatStrip, Tabs } from "@/components/ui";
import { Meter, Panel, RankedList, fmtPct, pct } from "@/components/viz";
import { useDashboard, type DashboardData, type RankedProduct } from "@/lib/dashboard";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { AUTH_LABEL, CATEGORY_LABEL, fmtDate, fmtNumber } from "@/lib/format";
import { useAction, useUrlState } from "@/lib/hooks";
import { useDepartments } from "@/lib/queries";
import type { Paged, Product } from "@/lib/types";

const PAGE_SIZE = 50;

function monthStart(offset = 0) {
  const d = new Date();
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + offset, 1)).toISOString().slice(0, 19);
}

const VIEWS = {
  all: { label: "Todo el catálogo", params: {} },
  new: { label: "Aparecidos este mes", params: { seen_since: monthStart() } },
  gone: { label: "Dejaron de detectarse (30 días)", params: { not_seen_since: new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 19) } },
  unused: { label: "Sin instalaciones vigentes", params: { installed: false } },
} as const;

function columns(fleet: number): Column<Product>[] {
  return [
    { id: "name", header: "Producto", sortKey: "name", cell: (p) => (
      <Link to={`/software/${p.id}`} title={p.name}
        className="block max-w-[22rem] truncate font-medium hover:underline hover:underline-offset-4 2xl:max-w-xl">{p.name}</Link>
    ) },
    { id: "publisher", header: "Editor", sortKey: "publisher", cell: (p) => <span className="block max-w-48 truncate text-muted" title={p.publisher ?? ""}>{p.publisher ?? "—"}</span> },
    { id: "category", header: "Categoría", cell: (p) => <span className="text-muted">{CATEGORY_LABEL[p.category] ?? p.category}</span> },
    { id: "versions", header: "Versiones", align: "right", cell: (p) => <span className="code">{p.versions}</span> },
    { id: "devices", header: "Equipos", sortKey: "devices", cell: (p) => (
      <div className="flex items-center gap-2.5">
        <span className="disp w-7 text-right text-sm font-semibold">{p.devices}</span>
        <span className="w-20"><Meter value={p.devices} max={fleet} /></span>
      </div>
    ) },
    { id: "status", header: "Autorización", sortKey: "status", cell: (p) => <AuthBadge status={p.authorization_status} /> },
    { id: "ens", header: "Clasificación ENS", hidden: true, cell: (p) => p.ens_classification ?? "—" },
    { id: "first", header: "Primera detección", sortKey: "first_seen_at", hidden: true, cell: (p) => <span className="text-muted">{fmtDate(p.first_seen_at)}</span> },
  ];
}

const STATUS_TABS = [
  { id: "all", label: "Todo", status: null },
  { id: "authorized", label: "Autorizado", status: "authorized" },
  { id: "conditional", label: "Condicionado", status: "conditional" },
  { id: "pending", label: "Por clasificar", status: "unclassified,pending_review" },
  { id: "unauthorized", label: "No autorizado", status: "unauthorized" },
  { id: "exception", label: "Excepciones", status: "exception" },
] as const;

/** Cola de clasificación rápida (panel oscuro): autoriza o rechaza lo más instalado de lo pendiente. */
function ClassifyQueue({ data, canWrite, onShowAll }: { data: DashboardData; canWrite: boolean; onShowAll: () => void }) {
  const queue = data.software.queue ?? [];
  const [rejecting, setRejecting] = useState<RankedProduct | null>(null);
  const decide = useAction(({ id, status }: { id: number; status: string }) => api.send<{ updated: number }>("POST", "/software/bulk-update",
    { product_ids: [id], authorization_status: status, reason: "Clasificación rápida desde la cola" }), {
    success: "Clasificación registrada", invalidate: [["software"], ["dashboard"], ["alerts"], ["alerts-count"]],
    onSuccess: () => setRejecting(null),
  });
  return (
    <section aria-label="Cola de clasificación"
      className="flex min-w-0 flex-[1_1_24rem] flex-col gap-4 rounded-panel border border-[#1C1917] bg-[#1C1917] p-6 text-[#F3F2F0]">
      <div className="flex items-center justify-between gap-2">
        <p className="eyebrow text-[#A39E98]">Cola de clasificación</p>
        <span className="font-mono text-2xs text-[#FF8A5C]">{data.software.pending} PENDIENTES</span>
      </div>
      <h2 className="disp text-lg font-semibold tracking-[-0.02em]">Decide qué se puede usar</h2>
      {queue.length === 0 ? <p className="text-[13px] text-[#B5B0AA]">No hay aplicaciones pendientes de clasificar.</p> : (
        <ul className="border-t border-[#33302D]">
          {queue.map((q) => (
            <li key={q.id} className="flex flex-wrap items-center gap-2.5 border-b border-[#33302D] py-3 last:border-b-0">
              <div className="min-w-0 flex-[1_1_10rem]">
                <Link to={`/software/${q.id}`} className="block truncate text-[13px] font-medium hover:underline hover:underline-offset-4" title={q.name}>{q.name}</Link>
                <p className="font-mono text-2xs uppercase text-[#A39E98]">{[q.publisher, `${q.devices} ${q.devices === 1 ? "equipo" : "equipos"}`].filter(Boolean).join(" · ")}</p>
              </div>
              {canWrite && <>
                <button type="button" onClick={() => setRejecting(q)} disabled={decide.isPending}
                  className="min-h-8 rounded-md border border-[#3A3734] px-3 text-xs font-medium text-[#D6D3CF] transition-colors hover:border-[#A39E98] hover:text-white disabled:opacity-50">
                  Rechazar</button>
                <button type="button" onClick={() => decide.mutate({ id: q.id, status: "authorized" })} disabled={decide.isPending}
                  className="min-h-8 rounded-md bg-[#F3F2F0] px-3 text-xs font-medium text-[#141312] transition-opacity hover:opacity-90 disabled:opacity-50">
                  Autorizar</button>
              </>}
            </li>
          ))}
        </ul>
      )}
      {data.software.pending > queue.length && (
        <button type="button" onClick={onShowAll}
          className="mt-auto self-start text-xs text-[#D6D3CF] underline decoration-[#5E5954] underline-offset-4 hover:decoration-[#D6D3CF]">
          Ver los {data.software.pending} pendientes</button>
      )}
      <ConfirmDialog open={!!rejecting} onClose={() => setRejecting(null)} title="Marcar como no autorizado" danger
        confirmLabel="No autorizar" busy={decide.isPending}
        onConfirm={() => rejecting && decide.mutate({ id: rejecting.id, status: "unauthorized" })}>
        Se abrirá una alerta por cada equipo que tenga instalado <strong>{rejecting?.name}</strong>.
      </ConfirmDialog>
    </section>
  );
}

function SoftwareSummary({ data, canWrite, onShowPending }: { data: DashboardData; canWrite: boolean; onShowPending: () => void }) {
  const sw = data.software;
  const auth = sw.by_status.authorized ?? 0;
  return (
    <div className="mb-6 flex flex-col gap-6">
      <StatStrip label="Catálogo por estado">
        <Stat label="Autorizado" value={fmtNumber(auth)} hint={`${fmtPct(pct(auth, sw.products))} % de las aplicaciones`} />
        <Stat label="Componentes" value={fmtNumber(sw.components ?? 0)} hint="paquetes de Microsoft / Windows" />
        <Stat label="Por clasificar" value={fmtNumber(sw.pending)} tone={sw.pending ? "warn" : undefined}
          hint={sw.pending ? "pendientes de autorizar o revisar" : "todo clasificado"} />
        <Stat label="No autorizado" value={fmtNumber(sw.unauthorized_products)} tone={sw.unauthorized_products ? "danger" : undefined}
          hint={sw.unauthorized_products ? "con alerta en cada equipo que lo tiene" : "ninguna aplicación bloqueada"} />
      </StatStrip>
      <div className="flex flex-wrap gap-6">
        <Panel title="Más instalado" className="flex-[2_1_30rem]"
          aside={<span className="text-[13px] text-muted">equipos con la aplicación, de {data.devices.total}</span>}>
          <RankedList items={sw.top ?? []} total={data.devices.total} />
        </Panel>
        <ClassifyQueue data={data} canWrite={canWrite} onShowAll={onShowPending} />
      </div>
    </div>
  );
}

export default function Software() {
  const can = useCan();
  const { values, set, page } = useUrlState(["q", "sort", "status", "category", "relevant", "department_id", "view"] as const);
  const [selected, setSelected] = useState<Set<number | string>>(new Set());
  const [classifying, setClassifying] = useState(false);
  const tableRef = useRef<HTMLDivElement>(null);
  // Mismo filtro que la URL actual no navega: además de filtrar, se lleva al usuario a la tabla.
  const showPending = () => {
    set({ status: "unclassified,pending_review" });
    tableRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const depts = useDepartments().data?.items ?? [];
  const view = (values.view ?? "all") as keyof typeof VIEWS;
  const relevant = values.relevant ?? "true";
  const params = { q: values.q, sort: values.sort, status: values.status, category: values.category,
    relevant: relevant === "all" ? undefined : relevant, department_id: values.department_id, ...VIEWS[view].params,
    page, page_size: PAGE_SIZE };
  const q = useQuery({ queryKey: ["software", params], queryFn: () => api.get<Paged<Product>>("/software", params),
    placeholderData: (prev) => prev });
  const dash = useDashboard().data;
  const fleet = Math.max(1, dash?.devices.total ?? 1);
  const cols = useMemo(() => columns(fleet), [fleet]);
  const tab = STATUS_TABS.find((t) => (t.status ?? "") === (values.status ?? ""))?.id ?? "all";
  const by = dash?.software.by_status ?? {};
  const tabCount: Record<string, number> | undefined = dash && {
    all: dash.software.products, authorized: by.authorized ?? 0, conditional: by.conditional ?? 0, pending: dash.software.pending,
    unauthorized: by.unauthorized ?? 0, exception: by.exception ?? 0,
  };

  return (
    <>
      <PageHeader eyebrow="Inventario · Software" title="Catálogo de software"
        description={dash ? `${fmtNumber(dash.software.products)} aplicaciones y ${fmtNumber(dash.software.installations)} instalaciones en ${dash.devices.total} equipos. Cada producto existe una vez, con sus versiones.`
          : "Catálogo global normalizado: cada producto existe una vez, con sus versiones e instalaciones."}
        actions={<>
          <Button icon={<Download className="size-4" />}
            onClick={() => api.download("/software/export", { format: "xlsx", q: values.q, status: values.status,
              category: values.category, relevant: params.relevant, department_id: values.department_id })}>Excel por departamento</Button>
          {can.write && !!dash?.software.pending && (
            <Button variant="primary" onClick={showPending}>Clasificar pendientes</Button>
          )}
        </>} />
      {dash && <SoftwareSummary data={dash} canWrite={can.write} onShowPending={showPending} />}
      <div ref={tableRef} className="scroll-mt-20">
      <DataTable
        header={<Tabs bare label="Autorización" value={tab} onChange={(id) => set({ status: STATUS_TABS.find((t) => t.id === id)?.status ?? null })}
          tabs={STATUS_TABS.map((t) => ({ id: t.id, label: t.label, count: tabCount?.[t.id] }))} />}
        columns={cols} rows={q.data?.items} total={q.data?.total} rowKey={(p) => p.id}
        loading={q.isLoading} error={q.error} retry={q.refetch}
        page={page} pageSize={PAGE_SIZE} onPage={(p) => set({ page: p }, false)}
        sort={values.sort} onSort={(s) => set({ sort: s })}
        search={values.q ?? ""} onSearch={(s) => set({ q: s })} searchPlaceholder="Producto o editor…"
        storageKey="software" selectable={can.write} selected={selected} onSelectedChange={setSelected}
        bulkActions={<Button size="sm" icon={<Tags className="size-4" />} onClick={() => setClassifying(true)}>Clasificar</Button>}
        toolbar={<>
          <select aria-label="Vista" className="field w-auto" value={view} onChange={(e) => set({ view: e.target.value === "all" ? null : e.target.value })}>
            {(Object.keys(VIEWS) as (keyof typeof VIEWS)[]).map((k) => <option key={k} value={k}>{VIEWS[k].label}</option>)}
          </select>
          <select aria-label="Tipo" className="field w-auto" value={relevant} onChange={(e) => set({ relevant: e.target.value === "true" ? null : e.target.value })}>
            <option value="true">Aplicaciones relevantes</option>
            <option value="false">Componentes, drivers y runtimes</option>
            <option value="all">Todo</option>
          </select>
          <select aria-label="Departamento" className="field w-auto" value={values.department_id ?? ""} onChange={(e) => set({ department_id: e.target.value || null })}>
            <option value="">Todos los departamentos</option>
            {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </>}
      />
      </div>
      {classifying && <BulkClassify ids={[...selected].map(Number)} onClose={() => setClassifying(false)}
        onDone={() => { setClassifying(false); setSelected(new Set()); }} />}
    </>
  );
}

function BulkClassify({ ids, onClose, onDone }: { ids: number[]; onClose: () => void; onDone: () => void }) {
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [relevant, setRelevant] = useState("");
  const [reason, setReason] = useState("");
  const body: Record<string, unknown> = { product_ids: ids, reason: reason || undefined };
  if (status) body.authorization_status = status;
  if (category) body.category = category;
  if (relevant) body.is_relevant = relevant === "true";
  const save = useAction(() => api.send<{ updated: number }>("POST", "/software/bulk-update", body), {
    success: (r) => `${r.updated} productos actualizados`, invalidate: [["software"], ["dashboard"]], onSuccess: onDone,
  });
  return (
    <Modal open onClose={onClose} title={`Clasificar ${ids.length} productos`} footer={<>
      <Button onClick={onClose}>Cancelar</Button>
      <Button variant="primary" loading={save.isPending} disabled={!status && !category && !relevant}
        onClick={() => save.mutate(undefined)}>Aplicar</Button>
    </>}>
      <div className="space-y-4">
        <Field label="Autorización global" hint="Las excepciones se conceden por departamento o dispositivo desde la ficha del producto.">
          {(id) => <select id={id} className="field" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Sin cambios</option>
            {["authorized", "conditional", "unauthorized", "pending_review", "unclassified"].map((s) => <option key={s} value={s}>{AUTH_LABEL[s]}</option>)}
          </select>}
        </Field>
        <Field label="Categoría">
          {(id) => <select id={id} className="field" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Sin cambios</option>
            {Object.entries(CATEGORY_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>}
        </Field>
        <Field label="Relevancia">
          {(id) => <select id={id} className="field" value={relevant} onChange={(e) => setRelevant(e.target.value)}>
            <option value="">Sin cambios</option>
            <option value="true">Aplicación relevante</option>
            <option value="false">Componente / no relevante</option>
          </select>}
        </Field>
        <Field label="Motivo (queda en auditoría)">
          {(id) => <input id={id} className="field" value={reason} onChange={(e) => setReason(e.target.value)} />}
        </Field>
        {status === "unauthorized" && <Badge tone="danger">Se abrirá una alerta por cada equipo que lo tenga instalado</Badge>}
      </div>
    </Modal>
  );
}
