import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Download, Tags } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { DataTable, type Column, type TableGroup } from "@/components/DataTable";
import {
  Bar, BigNum, Donut, FilterChips, HATCH, Kpi, KpiStrip, Legend, ScreenHeader, Spark, StackBar, StatusDot, authDot,
} from "@/components/kit";
import { POLICY_LABEL, useClassify, useProductActions, type ProductLike } from "@/components/SoftwareActions";
import { Badge, Button, Field, Modal, Segmented } from "@/components/ui";
import { useDashboard, type DashboardData, type QueueProduct } from "@/lib/dashboard";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { AUTH_LABEL, CATEGORY_LABEL, fmtDate, fmtNumber, parseUtc } from "@/lib/format";
import { useAction, useUrlState } from "@/lib/hooks";
import { useDepartments } from "@/lib/queries";
import type { Paged, Product } from "@/lib/types";

/** El catálogo relevante son cientos de productos: se carga entero para agruparlo por política. */
const ALL = 1000;

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

type Policy = "unauthorized" | "pending" | "conditional" | "authorized";
const ORDER: Policy[] = ["unauthorized", "pending", "conditional", "authorized"];
const policyOf = (s: string): Policy =>
  s === "unauthorized" ? "unauthorized" : s === "conditional" ? "conditional" : s === "authorized" || s === "exception" ? "authorized" : "pending";
const GROUP_LABEL: Record<Policy, string> = {
  unauthorized: "No autorizado", pending: "Por decidir", conditional: "Con condiciones", authorized: "Autorizado",
};

function columns(fleet: number): Column<Product>[] {
  return [
    { id: "name", header: "Producto", sortKey: "name", cell: (p) => (
      <div className="flex min-w-0 items-center gap-3">
        <StatusDot kind={authDot(p.authorization_status)} />
        <div className="min-w-0">
          <Link to={`/software/${p.id}`} title={p.name}
            className="block max-w-[22rem] truncate text-[13px] font-semibold hover:underline hover:underline-offset-4 2xl:max-w-xl">{p.name}</Link>
          <p className="max-w-[22rem] truncate text-xs text-muted" title={p.publisher ?? ""}>{p.publisher ?? "Editor desconocido"}</p>
        </div>
      </div>
    ) },
    { id: "publisher", header: "Editor", sortKey: "publisher", hidden: true,
      cell: (p) => <span className="block max-w-48 truncate text-muted" title={p.publisher ?? ""}>{p.publisher ?? "—"}</span> },
    { id: "category", header: "Categoría", cell: (p) => <span className="text-fg-2">{CATEGORY_LABEL[p.category] ?? p.category}</span> },
    { id: "versions", header: "Versiones", align: "right", cell: (p) => <span className="code">{p.versions}</span> },
    { id: "devices", header: "Equipos", sortKey: "devices", cell: (p) => (
      <div className="flex items-center gap-3">
        <span className="disp w-7 text-right text-sm font-semibold">{p.devices}</span>
        <span className="w-28"><Bar value={p.devices} max={fleet} className={p.authorization_status === "unauthorized" ? "bg-signal-fill" : "bg-chart-2"} /></span>
      </div>
    ) },
    { id: "status", header: "Política", sortKey: "status", cell: (p) => (
      <span className={p.authorization_status === "unauthorized" ? "font-medium text-signal" : "text-fg-2"}>{POLICY_LABEL[p.authorization_status] ?? p.authorization_status}</span>
    ) },
    { id: "ens", header: "Clasificación ENS", hidden: true, cell: (p) => p.ens_classification ?? "—" },
    { id: "first", header: "Primera detección", sortKey: "first_seen_at", hidden: true, cell: (p) => <span className="text-muted">{fmtDate(p.first_seen_at)}</span> },
  ];
}

// ------------------------------------------------------------------ KPI visuales
function CatalogSummary({ data }: { data: DashboardData }) {
  const sw = data.software;
  const by = sw.by_status;
  const pending = (by.unclassified ?? 0) + (by.pending_review ?? 0);
  const policy = [
    { label: "Autorizadas", value: (by.authorized ?? 0) + (by.exception ?? 0), strokeClass: "stroke-chart-1", className: "", dot: "authorized" as const },
    { label: "Con condiciones", value: by.conditional ?? 0, strokeClass: "stroke-chart-2", className: "", dot: "conditional" as const },
    { label: "No autorizadas", value: by.unauthorized ?? 0, strokeClass: "stroke-signal-fill", className: "", dot: "unauthorized" as const },
    { label: "Por decidir", value: pending, strokeClass: "stroke-chart-3", className: "", dot: "pending" as const },
  ];
  const spread = sw.versions_spread;
  const maxV = Math.max(1, ...(spread?.top ?? []).map((t) => t.versions));
  const components = sw.components ?? 0;
  return (
    <KpiStrip label="Resumen del catálogo" className="mb-6">
      <Kpi label="Política">
        <div className="flex items-center gap-4">
          <Donut segments={policy} center={fmtNumber(sw.products)} caption="aplicaciones"
            label={policy.map((p) => `${p.value} ${p.label.toLowerCase()}`).join(", ")} />
          <Legend className="flex-1" items={policy.map((p) => ({ label: p.label, value: p.value, tone: p.dot === "unauthorized" ? "signal" : undefined,
            swatch: <StatusDot kind={p.dot} size="sm" /> }))} />
        </div>
      </Kpi>
      <Kpi label="Versiones dispersas">
        <BigNum value={spread?.count ?? 0}>apps con 5 o más versiones</BigNum>
        <ul className="flex flex-col gap-2 text-xs">
          {(spread?.top ?? []).map((t) => (
            <li key={t.id} className="grid grid-cols-[minmax(0,1fr)_5.5rem_1.5rem] items-center gap-2.5">
              <Link to={`/software/${t.id}?tab=versiones`} className="truncate text-fg-2 hover:underline">{t.name}</Link>
              <Bar value={t.versions} max={maxV} />
              <b className="disp text-right">{t.versions}</b>
            </li>
          ))}
        </ul>
      </Kpi>
      <Kpi label="Novedades · 30 días">
        <BigNum value={`+${sw.new_30d ?? 0}`}>nuevas · −{sw.gone_30d ?? 0} desaparecidas</BigNum>
        <Spark values={sw.new_daily ?? []} height={44} label="Aplicaciones nuevas por día en los últimos 30 días" />
      </Kpi>
      <Kpi label="Qué se muestra" footer={`${fmtNumber(components)} componentes, drivers y runtimes ocultos por defecto`}>
        <BigNum value={fmtNumber(sw.products)}>de {fmtNumber(sw.products + components)} paquetes</BigNum>
        <StackBar label={`${sw.products} aplicaciones relevantes y ${components} componentes`} segments={[
          { label: "Aplicaciones", value: sw.products, className: "bg-chart-1" },
          { label: "Componentes", value: components, className: HATCH },
        ]} />
      </Kpi>
    </KpiStrip>
  );
}

// ------------------------------------------------------------------ Por decidir: una fila con desplazamiento lateral
function DecisionLane({ queue, total, canWrite, fleet }: { queue: QueueProduct[]; total: number; canWrite: boolean; fleet: number }) {
  const { classify, busy } = useClassify();
  const lane = useRef<HTMLDivElement>(null);
  const scroll = (dir: number) => lane.current?.scrollBy({ left: dir * 316, behavior: "smooth" });
  const decide = (q: QueueProduct, status: string) => classify([{ id: q.id, name: q.name, status: q.status ?? "unclassified" }], status);
  const age = (v?: string | null) => {
    const d = parseUtc(v);
    if (!d) return null;
    const days = Math.floor((Date.now() - d.getTime()) / 864e5);
    return days < 7 ? "NUEVA" : `${days} DÍAS`;
  };
  return (
    <section aria-label="Por decidir" className="mb-6 flex flex-col gap-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="disp text-lg font-semibold">Por decidir
          <span className="font-sans text-sm font-normal text-muted"> · {fmtNumber(total)} {total === 1 ? "aplicación" : "aplicaciones"}, ordenadas por equipos afectados</span></h2>
        {queue.length > 1 && (
          <div className="flex gap-1.5">
            <Button variant="secondary" aria-label="Anterior" onClick={() => scroll(-1)}><ChevronLeft className="size-4" /></Button>
            <Button variant="secondary" aria-label="Siguiente" onClick={() => scroll(1)}><ChevronRight className="size-4" /></Button>
          </div>
        )}
      </div>
      {queue.length === 0 ? (
        <p className="rounded-panel border border-dashed border-border-strong p-6 text-center text-sm text-muted">Todo el catálogo está clasificado.</p>
      ) : (
        <div ref={lane} role="list" className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2.5">
          {queue.map((q) => (
            <article key={q.id} role="listitem" tabIndex={0} aria-label={`${q.name}: ${q.devices} equipos. Teclas A, C o N para decidir.`}
              onKeyDown={(e) => {
                if (!canWrite || busy || e.target !== e.currentTarget) return;
                const s = ({ a: "authorized", c: "conditional", n: "unauthorized" } as Record<string, string>)[e.key.toLowerCase()];
                if (s) { e.preventDefault(); decide(q, s); }
              }}
              className="card flex w-[300px] shrink-0 snap-start flex-col gap-3 p-[18px] outline-none focus-visible:ring-2 focus-visible:ring-fg/60">
              <div className="flex items-start gap-3">
                <StatusDot kind="pending" className="mt-1" />
                <div className="min-w-0 flex-1">
                  <Link to={`/software/${q.id}`} className="block truncate text-[15px] font-semibold hover:underline hover:underline-offset-4" title={q.name}>{q.name}</Link>
                  <p className="truncate text-xs text-muted">{q.publisher ?? "Editor desconocido"}</p>
                </div>
                {age(q.first_seen_at) && <span className="code shrink-0 text-2xs text-muted">{age(q.first_seen_at)}</span>}
              </div>
              <div className="flex items-center gap-3">
                <span className="disp text-[15px] font-semibold">{q.devices}</span>
                <span className="flex-1"><Bar value={q.devices} max={fleet} /></span>
                <span className="text-xs text-muted">{q.devices === 1 ? "equipo" : "equipos"}</span>
              </div>
              <p className="line-clamp-2 min-h-8 text-xs text-muted">{q.departments?.length ? q.departments.join(", ") : "Sin instalaciones vigentes"}</p>
              {canWrite && (
                <div className="mt-auto flex gap-1.5">
                  <Button size="sm" disabled={busy} onClick={() => decide(q, "authorized")}>Autorizar</Button>
                  <Button size="sm" disabled={busy} onClick={() => decide(q, "conditional")}>Con condiciones</Button>
                  <Button size="sm" disabled={busy} title={`Abrirá ${q.devices} ${q.devices === 1 ? "alerta" : "alertas"}`}
                    className="hover:!border-signal hover:!text-signal" onClick={() => decide(q, "unauthorized")}>No</Button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ Página
type ChipId = "all" | Policy;

export default function Software() {
  const can = useCan();
  const nav = useNavigate();
  const { values, set } = useUrlState(["q", "sort", "status", "category", "relevant", "department_id", "view", "group"] as const);
  const [selected, setSelected] = useState<Set<number | string>>(new Set());
  const [classifying, setClassifying] = useState(false);
  const depts = useDepartments().data?.items ?? [];
  const actions = useProductActions();
  const view = (values.view ?? "all") as keyof typeof VIEWS;
  const relevant = values.relevant ?? "true";
  const grouped = values.group !== "list";
  // Compatibilidad con enlaces antiguos (?status=unclassified,pending_review).
  const chip: ChipId = !values.status ? "all" : values.status.includes("unclassified") || values.status.includes("pending") ? "pending"
    : (values.status as ChipId);
  const params = { q: values.q, sort: values.sort, category: values.category,
    relevant: relevant === "all" ? undefined : relevant, department_id: values.department_id, ...VIEWS[view].params, page_size: ALL };
  const q = useQuery({ queryKey: ["software", params], queryFn: () => api.get<Paged<Product>>("/software", params),
    placeholderData: (prev) => prev });
  const dash = useDashboard().data;
  const fleet = Math.max(1, dash?.devices.total ?? 1);
  const all = useMemo(() => q.data?.items ?? [], [q.data]);
  const rows = useMemo(() => (chip === "all" ? all : all.filter((p) => policyOf(p.authorization_status) === chip)), [all, chip]);
  const cols = useMemo(() => columns(fleet), [fleet]);
  const counts = useMemo(() => ORDER.reduce<Record<Policy, number>>((a, k) => ({ ...a, [k]: all.filter((p) => policyOf(p.authorization_status) === k).length }),
    { unauthorized: 0, pending: 0, conditional: 0, authorized: 0 }), [all]);

  const SUMMARY: Record<Policy, string> = {
    unauthorized: dash?.alerts.unauthorized_devices ? `alertas abiertas en ${dash.alerts.unauthorized_devices} equipos` : "sin alertas abiertas",
    pending: "decide arriba, en «Por decidir»",
    conditional: "uso permitido solo con aprobación",
    authorized: "base corporativa",
  };
  const groups: TableGroup<Product>[] | undefined = grouped ? ORDER
    .map((k) => ({ key: k, label: GROUP_LABEL[k], rows: rows.filter((p) => policyOf(p.authorization_status) === k),
      lead: <StatusDot kind={k} />, summary: SUMMARY[k], defaultCollapsed: k === "authorized" }))
    .filter((g) => g.rows.length > 0) : undefined;
  const like = (p: Product): ProductLike => ({ id: p.id, name: p.name, status: p.authorization_status, devices: p.devices });

  return (
    <>
      <ScreenHeader eyebrow="Inventario · Software" title={`${fmtNumber(dash?.software.products ?? all.length)} aplicaciones`}
        sub={dash ? `en ${dash.devices.total} equipos` : undefined}
        actions={<Button icon={<Download className="size-4" />}
          onClick={() => api.download("/software/export", { format: "xlsx", q: values.q, category: values.category,
            relevant: params.relevant, department_id: values.department_id })}>Excel por departamento</Button>} />
      {dash && <CatalogSummary data={dash} />}
      {dash && <DecisionLane queue={dash.software.queue ?? []} total={dash.software.pending} canWrite={can.write} fleet={fleet} />}
      <DataTable
        columns={cols} rows={rows} groups={groups} rowKey={(p) => p.id}
        loading={q.isLoading} error={q.error} retry={q.refetch}
        sort={values.sort} onSort={(s) => set({ sort: s })}
        search={values.q ?? ""} onSearch={(s) => set({ q: s })} searchPlaceholder="Producto o editor…"
        storageKey="software" selectable={can.write} selected={selected} onSelectedChange={setSelected}
        onRowClick={(p) => nav(`/software/${p.id}`)}
        rowMenu={(p, sel) => ({ title: sel.length > 1 ? `${sel.length} aplicaciones` : p.name, entries: actions.entries(like(p), sel.map(like)) })}
        bulkActions={<Button size="sm" icon={<Tags className="size-4" />} onClick={() => setClassifying(true)}>Clasificar</Button>}
        footer="Clic derecho sobre cualquier aplicación, o el botón ⋯, para ver sus acciones. Con varias seleccionadas, la acción se aplica a todas."
        header={<div className="py-3">
          <FilterChips label="Política" value={chip} onChange={(v) => set({ status: v === "all" ? null : v })} options={[
            { id: "all", label: "Todas", count: all.length },
            ...ORDER.map((k) => ({ id: k, label: GROUP_LABEL[k], count: counts[k], dot: k })),
          ]} />
        </div>}
        toolbar={<>
          <Segmented label="Agrupar" value={grouped ? "policy" : "list"} onChange={(v) => set({ group: v === "policy" ? null : "list" })}
            options={[{ id: "policy", label: "Por política" }, { id: "list", label: "Lista" }]} />
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
      {actions.dialogs}
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
