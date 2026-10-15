import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Pencil, Power } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AuthBadge, DeviceStatusBadge, FreshnessBadge } from "@/components/badges";
import { DataTable, type Column } from "@/components/DataTable";
import { Badge, Button, Card, ConfirmDialog, DefinitionList, ErrorState, PageHeader, Spinner, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { fmtDateTime, fmtRelative } from "@/lib/format";
import { useAction } from "@/lib/hooks";
import type { Department, DeviceRow, Paged } from "@/lib/types";
import { DepartmentForm } from "./Departments";

interface Detail extends Omit<Department, "users" | "software"> {
  users: { id: number; upn: string; display_name: string | null }[];
  software: { product_id: number; name: string; authorization_status: string; devices: number }[];
  movements: { device_id: number; device: string; started_at: string; ended_at: string | null; reason: string | null; actor: string | null }[];
  history: { action: string; actor: string; summary: string; at: string }[];
}
type Tab = "dispositivos" | "software" | "usuarios" | "historial";

export default function DepartmentDetail() {
  const id = Number(useParams().id);
  const can = useCan();
  const [tab, setTab] = useState<Tab>("dispositivos");
  const [editing, setEditing] = useState(false);
  const [toggling, setToggling] = useState(false);
  const q = useQuery({ queryKey: ["department", id], queryFn: () => api.get<Detail>(`/departments/${id}`) });
  const devices = useQuery({ queryKey: ["devices", { department_id: id, all: true }],
    queryFn: () => api.get<Paged<DeviceRow>>("/devices", { department_id: id, page_size: 1000 }) });
  const toggle = useAction(() => api.send("PATCH", `/departments/${id}`, { active: !q.data?.active }), {
    success: "Estado actualizado", invalidate: [["department", id], ["departments"]], onSuccess: () => setToggling(false),
  });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorState error={q.error} retry={q.refetch} />;
  const d = q.data;
  const devCols: Column<DeviceRow>[] = [
    { id: "name", header: "Equipo", cell: (x) => <Link className="font-medium hover:text-accent hover:underline" to={`/dispositivos/${x.id}`}>{x.name}</Link> },
    { id: "type", header: "Tipo", cell: (x) => x.device_type ?? "—" },
    { id: "user", header: "Usuario", cell: (x) => x.primary_user ?? "—" },
    { id: "model", header: "Modelo", cell: (x) => x.model ?? "—" },
    { id: "status", header: "Estado", cell: (x) => <DeviceStatusBadge status={x.status} /> },
    { id: "fresh", header: "Actualidad", cell: (x) => <FreshnessBadge value={x.freshness} /> },
    { id: "seen", header: "Última observación", cell: (x) => <span className="text-muted">{fmtRelative(x.last_seen_at)}</span> },
  ];

  return (
    <>
      <PageHeader title={d.name} description={<span className="flex items-center gap-2">{!d.active && <Badge>Inactivo</Badge>}{d.description}</span>}
        actions={can.write && <>
          <Button icon={<Pencil className="size-4" />} onClick={() => setEditing(true)}>Editar</Button>
          <Button variant="ghost" icon={<Power className="size-4" />} onClick={() => setToggling(true)}>{d.active ? "Desactivar" : "Activar"}</Button>
        </>}>
        <Link to="/departamentos" className="mb-2 inline-flex items-center gap-1 text-xs text-muted hover:text-fg"><ArrowLeft className="size-3" /> Departamentos</Link>
      </PageHeader>
      <div className="mb-4 grid gap-4 lg:grid-cols-3">
        <Card title="Datos" className="lg:col-span-2">
          <DefinitionList items={[
            ["Responsable", d.manager], ["Centro de coste", d.cost_center], ["Código", <span key="c" className="font-mono">{d.code}</span>],
            ...Object.entries(d.attributes ?? {}).map(([k, v]) => [k, v] as [string, string]),
          ]} />
        </Card>
        <Card title="Inventario asignado">
          <DefinitionList items={[["Dispositivos", d.devices ?? devices.data?.total ?? 0], ["Usuarios", d.users.length],
            ["Aplicaciones distintas", d.software.length]]} />
        </Card>
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "dispositivos", label: "Dispositivos" }, { id: "software", label: "Software" },
        { id: "usuarios", label: "Usuarios" }, { id: "historial", label: "Movimientos e histórico" }]} />
      {tab === "dispositivos" && <DataTable columns={devCols} rows={devices.data?.items} rowKey={(x) => x.id} loading={devices.isLoading} error={devices.error} />}
      {tab === "software" && <DataTable rows={d.software} rowKey={(s) => s.product_id} columns={[
        { id: "n", header: "Aplicación", cell: (s) => <Link className="font-medium hover:text-accent hover:underline" to={`/software/${s.product_id}`}>{s.name}</Link> },
        { id: "a", header: "Autorización global", cell: (s) => <AuthBadge status={s.authorization_status} /> },
        { id: "d", header: "Dispositivos", align: "right", cell: (s) => s.devices },
      ]} />}
      {tab === "usuarios" && <DataTable rows={d.users} rowKey={(u) => u.id} columns={[
        { id: "n", header: "Nombre", cell: (u) => u.display_name ?? "—" }, { id: "u", header: "UPN", cell: (u) => u.upn },
      ]} />}
      {tab === "historial" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Movimientos de dispositivos" padded={false}>
            <ul className="divide-y divide-border">{d.movements.map((m, i) => (
              <li key={i} className="px-4 py-2.5"><Link className="hover:underline" to={`/dispositivos/${m.device_id}`}>{m.device}</Link>
                <span className="text-muted"> · {m.ended_at ? "salió" : "asignado"} · {fmtDateTime(m.ended_at ?? m.started_at)}</span>
                {m.reason && <p className="text-xs text-muted">{m.reason} — {m.actor}</p>}</li>
            ))}{d.movements.length === 0 && <li className="px-4 py-6 text-center text-muted">Sin movimientos</li>}</ul>
          </Card>
          <Card title="Cambios del departamento" padded={false}>
            <ul className="divide-y divide-border">{d.history.map((h, i) => (
              <li key={i} className="px-4 py-2.5">{h.summary}<p className="text-xs text-muted">{h.actor} · {fmtDateTime(h.at)}</p></li>
            ))}{d.history.length === 0 && <li className="px-4 py-6 text-center text-muted">Sin cambios</li>}</ul>
          </Card>
        </div>
      )}
      {editing && <DepartmentForm dept={d as unknown as Department} onClose={() => setEditing(false)} />}
      <ConfirmDialog open={toggling} onClose={() => setToggling(false)} busy={toggle.isPending} onConfirm={() => toggle.mutate(undefined)}
        title={d.active ? "Desactivar departamento" : "Activar departamento"} danger={d.active} confirmLabel={d.active ? "Desactivar" : "Activar"}>
        {d.active ? "No podrá asignarse a nuevos dispositivos. Solo es posible si no tiene dispositivos asignados; su histórico se conserva."
          : "Volverá a estar disponible para asignaciones."}
      </ConfirmDialog>
    </>
  );
}
