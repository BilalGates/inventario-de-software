import { useQuery } from "@tanstack/react-query";
import { Download, Tags } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { AuthBadge } from "@/components/badges";
import { DataTable, type Column } from "@/components/DataTable";
import { Badge, Button, Field, Modal, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { AUTH_LABEL, CATEGORY_LABEL, fmtDate } from "@/lib/format";
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

const columns: Column<Product>[] = [
  { id: "name", header: "Producto", sortKey: "name", cell: (p) => (
    <Link to={`/software/${p.id}`} className="font-medium hover:text-accent hover:underline">{p.name}</Link>
  ) },
  { id: "publisher", header: "Editor", sortKey: "publisher", cell: (p) => <span className="block max-w-56 truncate">{p.publisher ?? "—"}</span> },
  { id: "category", header: "Categoría", cell: (p) => <span className="text-muted">{CATEGORY_LABEL[p.category] ?? p.category}</span> },
  { id: "status", header: "Autorización", sortKey: "status", cell: (p) => <AuthBadge status={p.authorization_status} /> },
  { id: "devices", header: "Dispositivos", sortKey: "devices", align: "right", cell: (p) => p.devices },
  { id: "versions", header: "Versiones", align: "right", cell: (p) => p.versions },
  { id: "ens", header: "Clasificación ENS", hidden: true, cell: (p) => p.ens_classification ?? "—" },
  { id: "first", header: "Primera detección", sortKey: "first_seen_at", cell: (p) => <span className="text-muted">{fmtDate(p.first_seen_at)}</span> },
];

export default function Software() {
  const can = useCan();
  const { values, set, page } = useUrlState(["q", "sort", "status", "category", "relevant", "department_id", "view"] as const);
  const [selected, setSelected] = useState<Set<number | string>>(new Set());
  const [classifying, setClassifying] = useState(false);
  const depts = useDepartments().data?.items ?? [];
  const view = (values.view ?? "all") as keyof typeof VIEWS;
  const relevant = values.relevant ?? "true";
  const params = { q: values.q, sort: values.sort, status: values.status, category: values.category,
    relevant: relevant === "all" ? undefined : relevant, department_id: values.department_id, ...VIEWS[view].params,
    page, page_size: PAGE_SIZE };
  const q = useQuery({ queryKey: ["software", params], queryFn: () => api.get<Paged<Product>>("/software", params),
    placeholderData: (prev) => prev });

  return (
    <>
      <PageHeader title="Software" description="Catálogo global normalizado: cada producto existe una vez, con sus versiones e instalaciones."
        actions={<Button icon={<Download className="size-4" />}
          onClick={() => api.download("/software/export", { format: "xlsx", q: values.q, status: values.status,
            category: values.category, relevant: params.relevant, department_id: values.department_id })}>Exportar</Button>} />
      <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Vistas">
        {Object.entries(VIEWS).map(([k, v]) => (
          <button key={k} onClick={() => set({ view: k === "all" ? null : k })}
            className={`rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition-colors ${view === k ? "bg-accent/10 text-accent ring-accent/30" : "text-muted ring-border hover:text-fg"}`}>
            {v.label}
          </button>
        ))}
      </div>
      <DataTable
        columns={columns} rows={q.data?.items} total={q.data?.total} rowKey={(p) => p.id}
        loading={q.isLoading} error={q.error} retry={q.refetch}
        page={page} pageSize={PAGE_SIZE} onPage={(p) => set({ page: p }, false)}
        sort={values.sort} onSort={(s) => set({ sort: s })}
        search={values.q ?? ""} onSearch={(s) => set({ q: s })} searchPlaceholder="Producto o editor…"
        storageKey="software" selectable={can.write} selected={selected} onSelectedChange={setSelected}
        bulkActions={<Button size="sm" icon={<Tags className="size-4" />} onClick={() => setClassifying(true)}>Clasificar</Button>}
        toolbar={<>
          <select aria-label="Autorización" className="field w-auto" value={values.status ?? ""} onChange={(e) => set({ status: e.target.value || null })}>
            <option value="">Cualquier autorización</option>
            <option value="unclassified,pending_review">Pendientes (sin clasificar o en revisión)</option>
            {Object.entries(AUTH_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
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
            {["authorized", "unauthorized", "pending_review", "unclassified"].map((s) => <option key={s} value={s}>{AUTH_LABEL[s]}</option>)}
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
