import { useQuery } from "@tanstack/react-query";
import { Download, FolderInput, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ComplianceBadge, DeviceStatusBadge, FreshnessBadge, SourceBadge } from "@/components/badges";
import { DataTable, type Column } from "@/components/DataTable";
import { DeviceForm, type DeviceFormValues } from "@/components/DeviceForm";
import { Button, Field, Modal, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { FRESHNESS_LABEL, fmtBytes, fmtRelative } from "@/lib/format";
import { useAction, useUrlState } from "@/lib/hooks";
import { useDepartments, useDeviceTypes } from "@/lib/queries";
import type { DeviceDetail, DeviceRow, Paged } from "@/lib/types";

const PAGE_SIZE = 50;

const columns: Column<DeviceRow>[] = [
  { id: "name", header: "Equipo", sortKey: "name", cell: (d) => (
    <Link to={`/dispositivos/${d.id}`} className="font-medium text-fg hover:text-accent hover:underline">{d.name}</Link>
  ) },
  { id: "serial", header: "Nº de serie", sortKey: "serial_number",
    cell: (d) => <span className="font-mono text-xs">{d.serial_number ?? "—"}</span> },
  { id: "type", header: "Tipo", cell: (d) => d.device_type ?? <span className="text-muted">Sin clasificar</span> },
  { id: "department", header: "Departamento", sortKey: "department",
    cell: (d) => d.department ?? <span className="text-muted">Sin asignar</span> },
  { id: "user", header: "Usuario", cell: (d) => <span className="block max-w-52 truncate" title={d.primary_user_upn ?? ""}>{d.primary_user ?? "—"}</span> },
  { id: "model", header: "Modelo", sortKey: "model", cell: (d) => <span className="block max-w-48 truncate">{[d.manufacturer, d.model].filter(Boolean).join(" ") || "—"}</span> },
  { id: "os", header: "Sistema", sortKey: "os_version", hidden: true, cell: (d) => <span className="whitespace-nowrap">{[d.os_name, d.os_version].filter(Boolean).join(" ") || "—"}</span> },
  { id: "ram", header: "RAM", align: "right", hidden: true, cell: (d) => fmtBytes(d.ram_bytes, true) },
  { id: "storage", header: "Disco", align: "right", hidden: true, cell: (d) => fmtBytes(d.storage_total_bytes) },
  { id: "compliance", header: "Cumplimiento", cell: (d) => <ComplianceBadge value={d.compliance_state} /> },
  { id: "software", header: "Apps", align: "right", cell: (d) => d.software_count ?? 0 },
  { id: "status", header: "Estado", sortKey: "status", hidden: true, cell: (d) => <DeviceStatusBadge status={d.status} /> },
  { id: "freshness", header: "Actualidad", cell: (d) => <FreshnessBadge value={d.freshness} /> },
  { id: "sources", header: "Fuentes", hidden: true,
    cell: (d) => <div className="flex gap-1">{d.sources?.map((s) => <SourceBadge key={s} source={s} />)}</div> },
  { id: "seen", header: "Última observación", sortKey: "last_seen_at",
    cell: (d) => <span className="whitespace-nowrap text-muted" title={d.last_seen_at ?? ""}>{fmtRelative(d.last_seen_at)}</span> },
  { id: "location", header: "Ubicación", hidden: true, cell: (d) => d.location ?? "—" },
];

export default function Devices() {
  const can = useCan();
  const nav = useNavigate();
  const { values, set, page } = useUrlState(["q", "sort", "department_id", "device_type_id", "freshness", "unassigned"] as const);
  const [selected, setSelected] = useState<Set<number | string>>(new Set());
  const [creating, setCreating] = useState(false);
  const [moving, setMoving] = useState(false);
  const depts = useDepartments().data?.items ?? [];
  const types = useDeviceTypes().data ?? [];
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
      <PageHeader title="Dispositivos" description="Activos tecnológicos con identidad única, de Intune, Panda o alta manual."
        actions={<>
          <Button icon={<Download className="size-4" />}
            onClick={() => api.download("/devices/export", { ...values, format: "xlsx", q: values.q })}>Exportar</Button>
          {can.write && <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>Nuevo dispositivo</Button>}
        </>} />
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
          <select aria-label="Actualidad" className="field w-auto" value={values.freshness ?? ""}
            onChange={(e) => set({ freshness: e.target.value || null })}>
            <option value="">Vigentes</option>
            {Object.entries(FRESHNESS_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
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
