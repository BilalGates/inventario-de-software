import { useQuery } from "@tanstack/react-query";
import { Download, FolderInput, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ComplianceBadge, DeviceStatusBadge, SourceBadge } from "@/components/badges";
import { DataTable, type Column, type TableGroup } from "@/components/DataTable";
import { useDeviceActions, type DeviceLike } from "@/components/DeviceActions";
import { DeviceForm, type DeviceFormValues } from "@/components/DeviceForm";
import {
  BigNum, DOT_LABEL, Donut, FilterChips, Gauge, HATCH, Kpi, KpiStrip, Legend, ScreenHeader, StackBar, StatusDot, Swatch, Waffle,
  type DotKind, type Segment,
} from "@/components/kit";
import { Button, Field, Modal, Segmented } from "@/components/ui";
import { useDashboard, type DashboardData } from "@/lib/dashboard";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { fmtBytes, fmtDate, fmtNumber, fmtRelative, isFailing, osFamily } from "@/lib/format";
import { useAction, useUrlState } from "@/lib/hooks";
import { useDepartments, useDeviceTypes } from "@/lib/queries";
import type { DeviceDetail, DeviceRow, Paged } from "@/lib/types";
import { Avatar } from "@/components/Avatar";

const INFRA = "Infraestructura";
const NO_DEPT = "Sin departamento";
/** El parque son decenas de equipos: se cargan todos para agrupar y filtrar por estado en el cliente. */
const ALL = 1000;

const state = (d: DeviceRow): DotKind => d.state ?? "ok";

const columns = (grouped: boolean): Column<DeviceRow>[] => [
  { id: "name", header: "Equipo", sortKey: "name", cell: (d) => {
    const model = [[d.manufacturer, d.model].filter(Boolean).join(" "), d.device_type].filter(Boolean).join(" · ");
    return (
      <div className="flex min-w-0 items-center gap-3">
        <StatusDot kind={state(d)} title={DOT_LABEL[state(d)]} />
        <div className="min-w-0">
          <Link to={`/dispositivos/${d.id}`} className="block text-[13px] font-semibold text-fg hover:underline hover:underline-offset-4">{d.name}</Link>
          {model && <p className="max-w-60 truncate text-xs text-muted" title={model}>{model}</p>}
        </div>
      </div>
    );
  } },
  { id: "user", header: "Usuario", cell: (d) => d.primary_user ? (
    <span className="flex max-w-52 items-center gap-2.5" title={d.primary_user_upn ?? ""}>
      <Avatar upn={d.primary_user_upn} name={d.primary_user} />
      <span className="truncate">{d.primary_user}</span>
    </span>
  ) : <span className="text-muted">Sin usuario</span> },
  ...(grouped ? [] : [{ id: "department", header: "Departamento", sortKey: "department",
    cell: (d: DeviceRow) => d.department ?? <span className="italic text-muted">Sin asignar</span> }]),
  { id: "os", header: "Sistema", sortKey: "os_version", cell: (d) => {
    const fam = osFamily(d.os_name, d.os_version);
    return <span className={fam === "Windows 10" ? "text-signal" : "text-fg-2"} title={[d.os_name, d.os_version].filter(Boolean).join(" ")}>{fam}</span>;
  } },
  { id: "sources", header: "Fuentes",
    cell: (d) => d.sources?.length ? <div className="flex gap-1">{d.sources.map((s) => <SourceBadge key={s} source={s} />)}</div>
      : <SourceBadge source="manual" /> },
  { id: "compliance", header: "Cumplimiento", cell: (d) => d.state === "infra" ? <span className="text-muted">—</span> : (
    <div className="flex flex-col items-start gap-0.5">
      <ComplianceBadge value={d.compliance_state} reasons={d.compliance_reasons} />
      {isFailing(d.compliance_state) && d.compliance_reasons?.[0] && (
        <span className="block max-w-44 truncate text-2xs text-muted" title={d.compliance_reasons.join(" · ")}>
          {d.compliance_reasons[0]}{d.compliance_reasons.length > 1 ? ` +${d.compliance_reasons.length - 1}` : ""}
        </span>
      )}
    </div>
  ) },
  { id: "freshness", header: "Actualidad", sortKey: "last_seen_at", cell: (d) => (
    <span className={d.freshness === "stale" ? "text-signal" : "text-muted"} title={d.last_seen_at ?? ""}>
      {d.freshness === "never_synced" ? "Sin fuente" : fmtRelative(d.last_seen_at)}</span>
  ) },
  { id: "software", header: "Apps", align: "right", cell: (d) => <span className="disp text-sm font-semibold">{d.software_count ?? 0}</span> },
  { id: "serial", header: "Nº de serie", sortKey: "serial_number", hidden: true,
    cell: (d) => <span className="font-mono text-xs">{d.serial_number ?? "—"}</span> },
  { id: "type", header: "Tipo", hidden: true, cell: (d) => d.device_type ?? <span className="text-muted">Sin clasificar</span> },
  { id: "model", header: "Modelo", sortKey: "model", hidden: true, cell: (d) => <span className="block max-w-48 truncate">{[d.manufacturer, d.model].filter(Boolean).join(" ") || "—"}</span> },
  { id: "ram", header: "RAM", align: "right", hidden: true, cell: (d) => fmtBytes(d.ram_bytes, true) },
  { id: "storage", header: "Disco", align: "right", hidden: true, cell: (d) => fmtBytes(d.storage_total_bytes) },
  { id: "status", header: "Estado", sortKey: "status", hidden: true, cell: (d) => <DeviceStatusBadge status={d.status} /> },
  { id: "location", header: "Ubicación", hidden: true, cell: (d) => d.location ?? "—" },
  { id: "purchase", header: "Fecha de adquisición", hidden: true, cell: (d) => <span className="text-muted">{fmtDate(d.purchase_date)}</span> },
  { id: "cost", header: "Coste", align: "right", hidden: true, cell: (d) => d.cost ?? "—" },
  { id: "notes", header: "Observaciones", hidden: true, cell: (d) => (
    <span className="block max-w-72 truncate text-muted" title={d.notes ?? ""}>{d.notes ?? "—"}</span>
  ) },
];

// ------------------------------------------------------------------ KPI visuales
const OS_STROKE: Record<string, string> = { "Windows 11": "stroke-chart-1", "Windows Server": "stroke-chart-2", "Windows 10": "stroke-signal-fill",
  Desconocido: "stroke-border-strong" };
const OS_SWATCH: Record<string, string> = { "Windows 11": "bg-chart-1", "Windows Server": "bg-chart-2", "Windows 10": "bg-signal-fill",
  Desconocido: "bg-border-strong" };
const TYPE: Record<string, [string, string]> = {
  laptop: ["Portátil", "bg-chart-1"], desktop: ["Sobremesa", "bg-chart-2"], server: ["Servidor", "bg-chart-3"],
  peripheral: ["Red / otros", "border-[1.5px] border-dashed border-muted"], mobile: ["Móvil", "bg-chart-2/60"],
  unknown: ["Sin clasificar", "bg-chart-4"],
};

function DeviceSummary({ data, rows }: { data: DashboardData; rows: DeviceRow[] }) {
  const d = data.devices;
  const os = Object.entries(d.by_os ?? {}).sort((a, b) => b[1] - a[1]);
  const top = os[0];
  const osSeg: Segment[] = os.map(([n, c]) => ({ label: n, value: c, className: "", strokeClass: OS_STROKE[n] ?? "stroke-chart-3" }));
  const c = d.compliance;
  const ok = c.compliant ?? 0;
  const grace = c.inGracePeriod ?? 0;
  const nc = (c.noncompliant ?? 0) + (c.error ?? 0) + (c.conflict ?? 0);
  const known = ok + grace + nc;
  const cov = { both: 0, intune: 0, panda: 0, manual: 0 };
  rows.forEach((r) => {
    const s = new Set(r.sources ?? []);
    if (s.has("intune") && s.has("panda")) cov.both++;
    else if (s.has("intune")) cov.intune++;
    else if (s.has("panda")) cov.panda++;
    else cov.manual++;
  });
  const covSeg: Segment[] = [
    { label: "Intune + Panda", value: cov.both, className: "bg-chart-1" },
    { label: "Solo Intune", value: cov.intune, className: "bg-chart-2" },
    { label: "Solo Panda", value: cov.panda, className: "bg-chart-3" },
    { label: "Inventario manual", value: cov.manual, className: HATCH },
  ];
  const typeCounts = rows.reduce<Record<string, number>>((a, r) => ({ ...a, [r.type_code ?? "unknown"]: (a[r.type_code ?? "unknown"] ?? 0) + 1 }), {});
  const typeOrder = Object.keys(TYPE).filter((k) => typeCounts[k]);
  const waffle = typeOrder.flatMap((k) => Array.from({ length: typeCounts[k] }, (_, i) => ({ key: `${k}${i}`, className: TYPE[k][1], title: TYPE[k][0] })));
  return (
    <KpiStrip label="Resumen del parque" className="mb-6">
      <Kpi label="Sistema operativo" footer={d.by_os?.["Windows 10"] ? "Windows 10 sin soporte desde oct. 2025" : undefined}>
        <div className="flex items-center gap-4">
          <Donut segments={osSeg} center={top?.[1] ?? 0} caption={top?.[0]} label={os.map(([n, v]) => `${n}: ${v}`).join(", ")} />
          <Legend className="flex-1" items={os.slice(1).map(([n, v]) => ({ label: n, value: v, tone: n === "Windows 10" ? "signal" : undefined,
            swatch: <Swatch className={OS_SWATCH[n] ?? "bg-chart-3"} /> }))} />
        </div>
      </Kpi>
      <Kpi label="Cumplimiento Intune">
        {known === 0 ? <p className="text-sm text-muted">Sin datos de Intune</p> : <>
          <Gauge label={`${ok} conformes, ${grace} en gracia, ${nc} no conformes`}
            segments={[{ label: "Conformes", value: ok, className: "", strokeClass: "stroke-chart-1" },
              { label: "En gracia", value: grace, className: "", strokeClass: "stroke-chart-2" },
              { label: "No conformes", value: nc, className: "", strokeClass: "stroke-signal-fill" }]}
            center={<span className="disp text-[32px] font-semibold">{Math.round((ok / known) * 100)}<span className="text-base text-muted"> %</span></span>} />
          <p className="text-center text-xs text-muted">
            <b className="text-fg">{ok}</b> conformes{grace ? <> · <b className="text-fg">{grace}</b> en gracia</> : null} ·{" "}
            <Link to="/dispositivos?state=nc" className={nc ? "font-semibold text-signal hover:underline" : ""}>{nc} no conformes</Link>
          </p>
        </>}
      </Kpi>
      <Kpi label="Cobertura por fuente">
        <BigNum value={rows.length - cov.manual}>de {rows.length} con fuente automática</BigNum>
        <StackBar segments={covSeg} label={covSeg.map((s) => `${s.label}: ${s.value}`).join(", ")} />
        <Legend items={covSeg.filter((s) => s.value).map((s) => ({ label: s.label, value: s.value, swatch: <Swatch className={s.className} /> }))} />
      </Kpi>
      <Kpi label="Tipo de equipo">
        <Waffle items={waffle} label={typeOrder.map((k) => `${typeCounts[k]} ${TYPE[k][0].toLowerCase()}`).join(", ")} />
        <ul className="grid grid-cols-2 gap-x-3.5 gap-y-1.5 text-xs">
          {typeOrder.map((k) => (
            <li key={k} className="flex items-center gap-2"><Swatch className={TYPE[k][1]} /><span className="flex-1 text-fg-2">{TYPE[k][0]}</span><b className="disp">{typeCounts[k]}</b></li>
          ))}
        </ul>
      </Kpi>
    </KpiStrip>
  );
}

// ------------------------------------------------------------------ Página
type StateFilter = "all" | "clean" | "alert" | "nc" | "manual" | "retired";
const MATCH: Record<StateFilter, (d: DeviceRow) => boolean> = {
  all: () => true, retired: () => true,
  clean: (d) => state(d) === "ok",
  alert: (d) => state(d) === "alert" || state(d) === "alertnc",
  nc: (d) => state(d) === "nc" || state(d) === "alertnc",
  manual: (d) => state(d) === "infra",
};

export default function Devices() {
  const can = useCan();
  const nav = useNavigate();
  const { values, set } = useUrlState(["q", "sort", "state", "view", "department_id", "device_type_id", "unassigned"] as const);
  const [selected, setSelected] = useState<Set<number | string>>(new Set());
  const [creating, setCreating] = useState(false);
  const [moving, setMoving] = useState(false);
  const depts = useDepartments().data?.items ?? [];
  const types = useDeviceTypes().data ?? [];
  const dash = useDashboard().data;
  const actions = useDeviceActions();
  const filter = (values.state ?? "all") as StateFilter;
  const grouped = values.view !== "list";
  const params = { q: values.q, sort: values.sort, department_id: values.department_id, device_type_id: values.device_type_id,
    unassigned: values.unassigned, freshness: filter === "retired" ? "retired" : undefined, page_size: ALL };
  const q = useQuery({ queryKey: ["devices", params], queryFn: () => api.get<Paged<DeviceRow>>("/devices", params),
    placeholderData: (prev) => prev });
  const all = q.data?.items ?? [];
  const rows = useMemo(() => all.filter(MATCH[filter]), [all, filter]);
  const create = useAction((v: DeviceFormValues) => api.send<DeviceDetail>("POST", "/devices", v), {
    success: "Dispositivo creado", invalidate: [["devices"], ["dashboard"], ["departments"]],
    onSuccess: (d) => nav(`/dispositivos/${d.id}`),
  });

  const groups: TableGroup<DeviceRow>[] | undefined = useMemo(() => {
    if (!grouped) return undefined;
    const by = new Map<string, DeviceRow[]>();
    rows.forEach((d) => {
      const g = state(d) === "infra" ? INFRA : d.department ?? NO_DEPT;
      by.set(g, [...(by.get(g) ?? []), d]);
    });
    const rank = (n: string) => (n === INFRA ? 2 : n === NO_DEPT ? 1 : 0);
    return [...by.entries()].sort((a, b) => rank(a[0]) - rank(b[0]) || b[1].length - a[1].length || a[0].localeCompare(b[0]))
      .map(([name, list]) => {
        const n = (k: DotKind[]) => list.filter((d) => k.includes(state(d))).length;
        const issues = n(["alert", "nc", "alertnc"]);
        return {
          key: name, label: name, rows: list,
          summary: <>
            {name === INFRA ? `${list.length} equipos con inventario manual` : issues ? `${issues} con incidencias` : "todo limpio"}
            <span className="w-32"><StackBar height="h-2" label={`Estado de ${name}`} segments={[
              { label: "Limpios", value: n(["ok"]), className: "bg-chart-1" },
              { label: "No autorizado", value: n(["alert", "alertnc"]), className: "bg-signal-fill" },
              { label: "No conformes", value: n(["nc"]), className: "bg-signal-fill/40" },
              { label: "Manual", value: n(["infra"]), className: HATCH },
            ]} /></span>
          </>,
        };
      });
  }, [rows, grouped]);

  const count = (f: StateFilter) => all.filter(MATCH[f]).length;
  const like = (d: DeviceRow): DeviceLike => ({ id: d.id, name: d.name, serial_number: d.serial_number, status: d.status,
    intune: d.sources?.includes("intune"), unauthorized: d.unauthorized });
  const total = dash?.devices.total ?? all.length;
  const deptCount = dash?.departments.length;

  return (
    <>
      <ScreenHeader eyebrow="Inventario · Dispositivos" title={`${fmtNumber(total)} equipos`}
        sub={deptCount ? `en ${deptCount} departamentos` : undefined}
        actions={<>
          <Button icon={<Download className="size-4" />}
            onClick={() => api.download("/devices/export", { format: "xlsx", q: values.q, department_id: values.department_id,
              device_type_id: values.device_type_id })}>Exportar</Button>
          {can.write && <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>Nuevo dispositivo</Button>}
        </>} />
      {dash && <DeviceSummary data={dash} rows={filter === "retired" ? [] : all} />}
      <DataTable
        columns={columns(grouped)}
        rows={rows}
        groups={groups}
        rowKey={(d) => d.id}
        loading={q.isLoading}
        error={q.error}
        retry={q.refetch}
        sort={values.sort}
        onSort={(s) => set({ sort: s })}
        search={values.q ?? ""}
        onSearch={(s) => set({ q: s })}
        searchPlaceholder="Nombre, serie, usuario, modelo…"
        storageKey="devices"
        selectable={can.write}
        selected={selected}
        onSelectedChange={setSelected}
        onRowClick={(d) => nav(`/dispositivos/${d.id}`)}
        rowMenu={(d, sel) => ({ title: sel.length > 1 ? `${sel.length} equipos` : d.name, entries: actions.entries(like(d), sel.map(like)) })}
        bulkActions={<Button size="sm" icon={<FolderInput className="size-4" />} onClick={() => setMoving(true)}>Mover</Button>}
        footer="Clic derecho sobre cualquier equipo, o el botón ⋯, para ver sus acciones. Con varios seleccionados, la acción se aplica a todos."
        header={<div className="flex flex-wrap items-center gap-3 py-3">
          <FilterChips label="Estado" value={filter} onChange={(v) => set({ state: v === "all" ? null : v })} options={[
            { id: "all", label: "Todos", count: filter === "retired" ? undefined : all.length },
            { id: "clean", label: "Limpios", count: count("clean"), dot: "ok" },
            { id: "alert", label: "No autorizado", count: count("alert"), dot: "alert" },
            { id: "nc", label: "No conformes", count: count("nc"), dot: "nc" },
            { id: "manual", label: "Manuales", count: count("manual"), dot: "infra" },
            { id: "retired", label: "Bajas", count: dash?.devices.by_status.retired ?? 0 },
          ]} />
        </div>}
        toolbar={<>
          <Segmented label="Vista" value={grouped ? "dept" : "list"} onChange={(v) => set({ view: v === "dept" ? null : "list" })}
            options={[{ id: "dept", label: "Por departamento" }, { id: "list", label: "Lista" }]} />
          <select aria-label="Departamento" className="field w-auto" value={values.unassigned ? "none" : values.department_id ?? ""}
            onChange={(e) => set(e.target.value === "none" ? { unassigned: "true", department_id: null }
              : { department_id: e.target.value || null, unassigned: null })}>
            <option value="">Todos los departamentos</option>
            <option value="none">Sin departamento</option>
            {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <select aria-label="Tipo" className="field w-auto" value={values.device_type_id ?? ""}
            onChange={(e) => set({ device_type_id: e.target.value || null })}>
            <option value="">Todos los tipos</option>
            {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </>}
      />
      {actions.dialogs}
      {creating && <DeviceForm open title="Nuevo dispositivo" onClose={() => setCreating(false)} busy={create.isPending}
        onSubmit={(v) => create.mutate(v)} />}
      {moving && <BulkMove ids={[...selected].map(Number)} onClose={() => setMoving(false)}
        onDone={() => { setMoving(false); setSelected(new Set()); }} />}
    </>
  );
}

function BulkMove({ ids, onClose, onDone }: { ids: number[]; onClose: () => void; onDone: () => void }) {
  const depts = useDepartments().data?.items.filter((d) => d.active) ?? [];
  const [dept, setDept] = useState<string>("");
  const [reason, setReason] = useState("");
  const move = useAction(() => api.send<{ moved: number }>("POST", "/devices/bulk-assign",
    { device_ids: ids, department_id: dept === "none" ? null : Number(dept), reason }), {
    success: (r) => `${r.moved} dispositivos movidos`, invalidate: [["devices"], ["departments"], ["dashboard"]],
    onSuccess: onDone,
  });
  return (
    <Modal open onClose={onClose} title={`Mover ${ids.length} dispositivos`} footer={<>
      <Button onClick={onClose}>Cancelar</Button>
      <Button variant="primary" loading={move.isPending} disabled={!dept || reason.trim().length < 3}
        onClick={() => move.mutate(undefined)}>Mover</Button>
    </>}>
      <div className="space-y-4">
        <Field label="Departamento de destino">
          {(id) => (
            <select id={id} className="field" value={dept} onChange={(e) => setDept(e.target.value)}>
              <option value="" disabled>Seleccione…</option>
              <option value="none">Sin departamento</option>
              {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          )}
        </Field>
        <Field label="Motivo" hint="Queda registrado en el historial de cada dispositivo.">
          {(id) => <input id={id} className="field" value={reason} onChange={(e) => setReason(e.target.value)} />}
        </Field>
      </div>
    </Modal>
  );
}
