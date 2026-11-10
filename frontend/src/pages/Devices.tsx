import { useQuery } from "@tanstack/react-query";
import { Download, FolderInput, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ComplianceBadge, DeviceStatusBadge, FreshnessBadge, SourceBadge } from "@/components/badges";
import { DataTable, type Column } from "@/components/DataTable";
import { DeviceForm, type DeviceFormValues } from "@/components/DeviceForm";
import { Button, Field, Modal, PageHeader, Segmented, Stat, StatStrip } from "@/components/ui";
import { Meter, fmtPct, pct } from "@/components/viz";
import { useDashboard, type DashboardData } from "@/lib/dashboard";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { SOURCE_LABEL, fmtBytes, fmtDate, fmtRelative, isFailing, osFamily } from "@/lib/format";
import { useAction, useUrlState } from "@/lib/hooks";
import { useDepartments, useDeviceTypes } from "@/lib/queries";
import type { DeviceDetail, DeviceRow, Paged } from "@/lib/types";

const PAGE_SIZE = 50;

const columns: Column<DeviceRow>[] = [
  { id: "name", header: "Equipo", sortKey: "name", cell: (d) => {
    const model = [d.manufacturer, d.model].filter(Boolean).join(" ");
    return (
      <div className="min-w-0">
        <Link to={`/dispositivos/${d.id}`} className="code text-[13px] font-medium text-fg hover:underline hover:underline-offset-4">{d.name}</Link>
        {model && <p className="max-w-56 truncate text-xs text-muted" title={model}>{model}</p>}
      </div>
    );
  } },
  { id: "user", header: "Usuario", cell: (d) => <span className="block max-w-44 truncate" title={d.primary_user_upn ?? ""}>{d.primary_user ?? "—"}</span> },
  { id: "department", header: "Departamento", sortKey: "department",
    cell: (d) => d.department ?? <span className="italic text-muted">Sin asignar</span> },
  { id: "os", header: "Sistema", sortKey: "os_version", cell: (d) => {
    const fam = osFamily(d.os_name, d.os_version);
    return <span className={fam === "Windows 10" ? "text-signal" : "text-fg-2"} title={[d.os_name, d.os_version].filter(Boolean).join(" ")}>{fam}</span>;
  } },
  { id: "sources", header: "Fuentes",
    cell: (d) => d.sources?.length ? <div className="flex gap-1">{d.sources.map((s) => <SourceBadge key={s} source={s} />)}</div>
      : <SourceBadge source="manual" /> },
  { id: "compliance", header: "Cumplimiento", cell: (d) => (
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
    <div className="flex flex-col items-start gap-0.5">
      <FreshnessBadge value={d.freshness} />
      <span className="code text-2xs text-muted" title={d.last_seen_at ?? ""}>{fmtRelative(d.last_seen_at)}</span>
    </div>
  ) },
  { id: "software", header: "Apps", align: "right", cell: (d) => <span className="disp text-sm font-semibold">{d.software_count ?? 0}</span> },
  { id: "serial", header: "Nº de serie", sortKey: "serial_number", hidden: true,
    cell: (d) => <span className="font-mono text-xs">{d.serial_number ?? "—"}</span> },
  { id: "type", header: "Tipo", hidden: true, cell: (d) => d.device_type ?? <span className="text-muted">Sin clasificar</span> },
  { id: "model", header: "Modelo", sortKey: "model", hidden: true, cell: (d) => <span className="block max-w-48 truncate">{[d.manufacturer, d.model].filter(Boolean).join(" ") || "—"}</span> },
  { id: "ram", header: "RAM", align: "right", hidden: true, cell: (d) => fmtBytes(d.ram_bytes, true) },
  { id: "storage", header: "Disco", align: "right", hidden: true, cell: (d) => fmtBytes(d.storage_total_bytes) },
  { id: "status", header: "Estado", sortKey: "status", hidden: true, cell: (d) => <DeviceStatusBadge status={d.status} /> },
  { id: "seen", header: "Última observación", hidden: true,
    cell: (d) => <span className="whitespace-nowrap text-muted" title={d.last_seen_at ?? ""}>{fmtRelative(d.last_seen_at)}</span> },
  { id: "location", header: "Ubicación", hidden: true, cell: (d) => d.location ?? "—" },
  { id: "purchase", header: "Fecha de adquisición", hidden: true, cell: (d) => <span className="text-muted">{fmtDate(d.purchase_date)}</span> },
  { id: "cost", header: "Coste", align: "right", hidden: true, cell: (d) => d.cost ?? "—" },
  { id: "notes", header: "Observaciones", hidden: true, cell: (d) => (
    <span className="block max-w-72 truncate text-muted" title={d.notes ?? ""}>{d.notes ?? "—"}</span>
  ) },
];

const OS_ORDER = ["Windows 11", "Windows 10", "Windows Server", "macOS"];
const OS_COLOR: Record<string, string> = { "Windows 11": "bg-chart-1", "Windows 10": "bg-signal-fill", "Windows Server": "bg-chart-2", macOS: "bg-chart-3" };

/** Franja de resumen del parque (datos del Panel, ya en caché). */
function DeviceSummary({ data }: { data: DashboardData }) {
  const d = data.devices;
  const os = Object.entries(d.by_os ?? {}).sort((a, b) => {
    const ia = OS_ORDER.indexOf(a[0]), ib = OS_ORDER.indexOf(b[0]);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || b[1] - a[1];
  });
  const osTotal = os.reduce((a, [, n]) => a + n, 0);
  const win10 = d.by_os?.["Windows 10"] ?? 0;
  const sources = Object.entries(d.by_source ?? {}).sort((a, b) => (a[0] === "manual" ? 1 : b[0] === "manual" ? -1 : b[1] - a[1]));
  const comp = d.compliance;
  const known = Object.entries(comp).filter(([k]) => k !== "None" && k !== "null").reduce((a, [, n]) => a + n, 0);
  const ok = comp.compliant ?? 0;
  const nc = comp.noncompliant ?? 0;
  const grace = comp.inGracePeriod ?? 0;
  return (
    <StatStrip label="Resumen del parque" minCell="15rem" className="mb-6">
      <div className="flex flex-col gap-3 bg-surface px-5 py-5">
        <span className="eyebrow">Sistema operativo</span>
        <div role="img" aria-label={os.map(([n, c]) => `${n}: ${c}`).join(", ")} className="flex h-2 gap-0.5 overflow-hidden rounded-sm">
          {os.map(([n, c]) => <span key={n} className={OS_COLOR[n] ?? "bg-chart-4"} style={{ width: `${pct(c, osTotal)}%` }} />)}
        </div>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          {os.map(([n, c]) => (
            <li key={n} className="flex gap-2">
              <span className={n === "Windows 10" ? "flex-1 text-signal" : "flex-1 text-muted"}>{n}</span>
              <span className={n === "Windows 10" ? "disp font-semibold text-signal" : "disp font-semibold"}>{c}</span>
            </li>
          ))}
        </ul>
        {win10 > 0 && <p className="text-xs text-muted">Windows 10 sin soporte desde oct 2025</p>}
      </div>
      <div className="flex flex-col gap-3 bg-surface px-5 py-5">
        <span className="eyebrow">Cobertura por fuente</span>
        <ul className="flex flex-col gap-2.5 text-[13px]">
          {sources.map(([src, n]) => (
            <li key={src} className="flex flex-col gap-1.5">
              <div className="flex"><span className="flex-1">{SOURCE_LABEL[src] ?? src}</span><span className="code">{n}</span></div>
              <Meter value={n} max={d.total} className={src === "manual" ? "bg-chart-3" : "bg-fg"} />
            </li>
          ))}
        </ul>
      </div>
      <Stat label="Cumplimiento Intune" value={known ? <>{fmtPct(pct(ok, known))}<span className="text-[20px] text-muted"> %</span></> : "—"}
        hint={<>{ok} conformes · <span className={nc ? "font-medium text-signal" : ""}>{nc} no conformes</span>{grace ? ` · ${grace} en gracia` : ""}</>} />
      <Stat label="Sin observar" value={d.stale} tone={d.stale ? "warn" : undefined}
        hint={d.stale ? "sin datos recientes de ninguna fuente" : "todos los equipos con datos recientes"} />
    </StatStrip>
  );
}

export default function Devices() {
  const can = useCan();
  const nav = useNavigate();
  const { values, set, page } = useUrlState(["q", "sort", "department_id", "device_type_id", "freshness", "unassigned"] as const);
  const [selected, setSelected] = useState<Set<number | string>>(new Set());
  const [creating, setCreating] = useState(false);
  const [moving, setMoving] = useState(false);
  const depts = useDepartments().data?.items ?? [];
  const types = useDeviceTypes().data ?? [];
  const dash = useDashboard().data;
  const filters = { ...values, page, page_size: PAGE_SIZE };
  const q = useQuery({
    queryKey: ["devices", filters],
    queryFn: () => api.get<Paged<DeviceRow>>("/devices", filters),
    placeholderData: (prev) => prev,
  });
  const create = useAction((v: DeviceFormValues) => api.send<DeviceDetail>("POST", "/devices", v), {
    success: "Dispositivo creado", invalidate: [["devices"], ["dashboard"], ["departments"]],
    onSuccess: (d) => nav(`/dispositivos/${d.id}`),
  });

  return (
    <>
      <PageHeader eyebrow="Inventario · Dispositivos" title="Dispositivos"
        description={dash ? `${dash.devices.total} equipos registrados. Intune y Panda los observan en cada sincronización; el resto se da de alta a mano.`
          : "Activos tecnológicos con identidad única, de Intune, Panda o alta manual."}
        actions={<>
          <Button icon={<Download className="size-4" />}
            onClick={() => api.download("/devices/export", { ...values, format: "xlsx", q: values.q })}>Exportar</Button>
          {can.write && <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>Nuevo dispositivo</Button>}
        </>} />
      {dash && <DeviceSummary data={dash} />}
      <DataTable
        columns={columns}
        rows={q.data?.items}
        total={q.data?.total}
        rowKey={(d) => d.id}
        loading={q.isLoading}
        error={q.error}
        retry={q.refetch}
        page={page}
        pageSize={PAGE_SIZE}
        onPage={(p) => set({ page: p }, false)}
        sort={values.sort}
        onSort={(s) => set({ sort: s })}
        search={values.q ?? ""}
        onSearch={(s) => set({ q: s })}
        searchPlaceholder="Nombre, serie, usuario, modelo…"
        storageKey="devices"
        selectable={can.write}
        selected={selected}
        onSelectedChange={setSelected}
        bulkActions={<Button size="sm" icon={<FolderInput className="size-4" />} onClick={() => setMoving(true)}>Mover</Button>}
        toolbar={<>
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
          <Segmented label="Actualidad" value={values.freshness ?? "all"} onChange={(v) => set({ freshness: v === "all" ? null : v })}
            options={[
              { id: "all", label: "Vigentes", count: dash?.devices.total },
              { id: "current", label: "Al día", count: dash?.devices.current },
              { id: "stale", label: "Sin observar", count: dash?.devices.stale },
              { id: "never_synced", label: "Sin fuente", count: dash?.devices.never_synced },
              { id: "retired", label: "Bajas", count: dash?.devices.by_status.retired ?? 0 },
            ]} />
        </>}
      />
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
