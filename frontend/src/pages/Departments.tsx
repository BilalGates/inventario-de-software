import { Download, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { DataTable, type Column } from "@/components/DataTable";
import { Bar, BigNum, Kpi, KpiStrip, ScreenHeader, StatusDot } from "@/components/kit";
import { Badge, Button, ConfirmDialog, EmptyState, ErrorState, Field, Modal, Spinner, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { useDashboard, type FleetDevice } from "@/lib/dashboard";
import { useAction } from "@/lib/hooks";
import { useDepartments } from "@/lib/queries";
import type { Department } from "@/lib/types";

const NO_DEPT = "Sin departamento";

export default function Departments() {
  const can = useCan();
  const nav = useNavigate();
  const toast = useToast();
  const q = useDepartments();
  const dash = useDashboard().data;
  const [editing, setEditing] = useState<Department | "new" | null>(null);
  const [toggling, setToggling] = useState<Department | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const toggle = useAction((d: Department) => api.send("PATCH", `/departments/${d.id}`, { active: !d.active }), {
    success: "Departamento actualizado", invalidate: [["departments"], ["dashboard"]], onSuccess: () => setToggling(null),
  });
  const fleet = useMemo(() => {
    const by = new Map<string, FleetDevice[]>();
    (dash?.devices.fleet ?? []).forEach((d) => by.set(d.department ?? NO_DEPT, [...(by.get(d.department ?? NO_DEPT) ?? []), d]));
    return by;
  }, [dash]);
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} retry={q.refetch} />;
  const all = q.data?.items ?? [];
  const items = all.filter((d) => showInactive || d.active);
  const inactive = all.filter((d) => !d.active).length;
  const unassigned = q.data?.unassigned_devices ?? 0;
  const clean = (list: FleetDevice[]) => {
    const work = list.filter((d) => d.state !== "infra");
    return work.length ? Math.round((work.filter((d) => d.state === "ok").length / work.length) * 100) : null;
  };
  const active = items.filter((d) => d.active);
  const maxDevices = Math.max(1, ...items.map((d) => d.devices ?? 0), unassigned);
  const noOwner = active.filter((d) => !d.manager).length;
  const users = items.reduce((a, d) => a + (d.users ?? 0), 0);
  const looseDevices = fleet.get(NO_DEPT) ?? [];

  const cols: Column<Department>[] = [
    { id: "name", header: "Departamento", cell: (d) => (
      <div className="min-w-0">
        <h3 className="flex items-center gap-2 text-[15px] font-semibold">
          <Link to={`/departamentos/${d.id}`} className="hover:underline hover:underline-offset-4">{d.name}</Link>
          {!d.active && <Badge>Inactivo</Badge>}
        </h3>
        <p className={d.manager ? "text-xs text-muted" : "text-xs text-signal"}>{d.manager ? `Responsable: ${d.manager}` : "Sin responsable"}</p>
      </div>
    ) },
    { id: "devices", header: "Sus equipos", cell: (d) => {
      const list = fleet.get(d.name) ?? [];
      return list.length === 0 ? <span className="text-muted">Sin equipos</span> : (
        <div className="flex max-w-80 flex-wrap gap-1 whitespace-normal">
          {list.map((x) => <StatusDot key={x.id} kind={x.state ?? "ok"} title={x.name} />)}
        </div>
      );
    } },
    { id: "users", header: "Usuarios", align: "right", cell: (d) => <span className="disp font-semibold">{d.users ?? 0}</span> },
    { id: "apps", header: "Apps", align: "right", cell: (d) => <span className="disp font-semibold">{d.software ?? 0}</span> },
    { id: "clean", header: "Limpios", align: "right", cell: (d) => {
      const pct = clean(fleet.get(d.name) ?? []);
      return pct === null ? <span className="text-muted">—</span>
        : <span className={pct < 50 ? "disp font-semibold text-signal" : "disp font-semibold"}>{pct} %</span>;
    } },
    { id: "cc", header: "Centro de coste", cell: (d) => <span className="code text-muted">{d.cost_center ?? "—"}</span> },
    { id: "desc", header: "Descripción", hidden: true, cell: (d) => <span className="block max-w-72 truncate text-muted">{d.description ?? "—"}</span> },
  ];

  const barRows = [...active.map((d) => ({ name: d.name, n: d.devices ?? 0, none: false })),
    ...(unassigned ? [{ name: NO_DEPT, n: unassigned, none: true }] : [])].sort((a, b) => b.n - a.n);
  const cleanRows = active.map((d) => ({ name: d.name, pct: clean(fleet.get(d.name) ?? []) }))
    .filter((r): r is { name: string; pct: number } => r.pct !== null);

  return (
    <>
      <ScreenHeader eyebrow="Organización · Departamentos" title={`${active.length} departamentos`}
        sub={unassigned ? `· ${unassigned} ${unassigned === 1 ? "equipo sin asignar" : "equipos sin asignar"}` : undefined}
        actions={<>
          <Button icon={<Download className="size-4" />} onClick={() => api.download("/users/export", { format: "xlsx" })}>Exportar usuarios</Button>
          {can.write && <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setEditing("new")}>Nuevo departamento</Button>}
        </>} />
      {items.length > 0 && (
        <KpiStrip label="Resumen" className="mb-6">
          <Kpi label="Equipos por departamento">
            <ul className="flex flex-col gap-2 text-xs">
              {barRows.map((r) => (
                <li key={r.name} className="grid grid-cols-[7rem_minmax(0,1fr)_1.75rem] items-center gap-2.5">
                  <span className="truncate text-fg-2">{r.name}</span>
                  <Bar value={r.n} max={maxDevices} className={r.none ? "bg-chart-3" : "bg-chart-1"} />
                  <b className="disp text-right">{r.n}</b>
                </li>
              ))}
            </ul>
          </Kpi>
          <Kpi label="Equipos limpios" footer="Sin incidencias: conformes y sin software no autorizado">
            <ul className="flex flex-col gap-2 text-xs">
              {cleanRows.map((r) => (
                <li key={r.name} className="grid grid-cols-[7rem_minmax(0,1fr)_2.5rem] items-center gap-2.5">
                  <span className="truncate text-fg-2">{r.name}</span>
                  <Bar value={r.pct} max={100} className={r.pct < 50 ? "bg-signal-fill" : "bg-chart-1"} />
                  <b className={r.pct < 50 ? "disp text-right text-signal" : "disp text-right"}>{r.pct} %</b>
                </li>
              ))}
            </ul>
          </Kpi>
          <Kpi label="Sin departamento">
            <BigNum value={unassigned}>{unassigned === 1 ? "equipo" : "equipos"}</BigNum>
            {looseDevices.length > 0 && <div className="flex flex-wrap gap-1">{looseDevices.map((x) => <StatusDot key={x.id} kind={x.state ?? "ok"} title={x.name} />)}</div>}
            {unassigned > 0 && <Link to="/dispositivos?unassigned=true" className="link mt-auto text-[13px]">Asignarlos ahora →</Link>}
          </Kpi>
          <Kpi label="Personas" footer={noOwner ? `${noOwner} ${noOwner === 1 ? "departamento" : "departamentos"} sin responsable` : "Todos con responsable"}>
            <BigNum value={users}>usuarios con equipo</BigNum>
          </Kpi>
        </KpiStrip>
      )}
      {inactive > 0 && (
        <label className="mb-3 flex items-center gap-2 text-sm text-muted">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Mostrar {inactive} inactivos
        </label>
      )}
      {items.length === 0 ? (
        <div className="card"><EmptyState title="Aún no hay departamentos">Cree los departamentos de Asserta para asignar dispositivos y usuarios.</EmptyState></div>
      ) : (
        <DataTable columns={cols} rows={items} rowKey={(d) => d.id} storageKey="departments"
          onRowClick={(d) => nav(`/departamentos/${d.id}`)}
          rowMenu={(d) => ({ title: d.name, entries: [
            { label: "Abrir departamento", hint: "Intro", onSelect: () => nav(`/departamentos/${d.id}`) },
            { label: "Ver sus equipos", onSelect: () => nav(`/dispositivos?department_id=${d.id}`) },
            { label: "Ver su software", onSelect: () => nav(`/software?department_id=${d.id}`) },
            ...(can.write ? ["separator" as const,
              { label: "Editar…", onSelect: () => setEditing(d) },
              { label: "Asignar responsable…", onSelect: () => setEditing(d) },
              { label: "Mover equipos aquí…", onSelect: () => nav("/dispositivos?unassigned=true") }] : []),
            { label: "Exportar Excel del departamento", onSelect: () => api.download("/software/export", { format: "xlsx", department_id: d.id })
              .catch((e: Error) => toast("danger", e.message)) },
            ...(can.write ? ["separator" as const, d.active
              ? { label: "Desactivar…", danger: true, onSelect: () => setToggling(d) }
              : { label: "Activar", onSelect: () => setToggling(d) }] : []),
          ] })}
          footer="Cada cuadro es un equipo del departamento, con la misma leyenda que el Panel. Clic derecho o ⋯ para las acciones." />
      )}
      {editing && <DepartmentForm dept={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      <ConfirmDialog open={!!toggling} onClose={() => setToggling(null)} busy={toggle.isPending}
        onConfirm={() => { if (toggling) toggle.mutate(toggling); }} danger={toggling?.active}
        title={toggling?.active ? `Desactivar ${toggling.name}` : `Activar ${toggling?.name ?? ""}`}
        confirmLabel={toggling?.active ? "Desactivar" : "Activar"}>
        {toggling?.active ? "No podrá asignarse a nuevos dispositivos. Solo es posible si no tiene dispositivos asignados; su histórico se conserva."
          : "Volverá a estar disponible para asignar dispositivos."}
      </ConfirmDialog>
    </>
  );
}

export function DepartmentForm({ dept, onClose }: { dept: Department | null; onClose: () => void }) {
  const [v, setV] = useState({ name: dept?.name ?? "", description: dept?.description ?? "", manager_upn: "",
    cost_center: dept?.cost_center ?? "" });
  const [attrs, setAttrs] = useState<[string, string][]>(Object.entries(dept?.attributes ?? {}));
  const body = { name: v.name.trim(), description: v.description || null, cost_center: v.cost_center || null,
    ...(v.manager_upn ? { manager_upn: v.manager_upn.trim() } : {}),
    attributes: Object.fromEntries(attrs.filter(([k]) => k.trim())) };
  const save = useAction(() => dept ? api.send("PATCH", `/departments/${dept.id}`, body) : api.send("POST", "/departments", body), {
    success: dept ? "Departamento actualizado" : "Departamento creado",
    invalidate: [["departments"], ["department", dept?.id], ["dashboard"]], onSuccess: onClose,
  });
  return (
    <Modal open onClose={onClose} title={dept ? `Editar ${dept.name}` : "Nuevo departamento"} footer={<>
      <Button onClick={onClose}>Cancelar</Button>
      <Button variant="primary" disabled={v.name.trim().length < 2} loading={save.isPending} onClick={() => save.mutate(undefined)}>Guardar</Button>
    </>}>
      <div className="space-y-4">
        <Field label="Nombre">{(id) => <input id={id} className="field" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} autoFocus />}</Field>
        <Field label="Descripción">{(id) => <textarea id={id} rows={2} className="field" value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} />}</Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Responsable (UPN)" hint={dept?.manager ? `Actual: ${dept.manager}` : undefined}>
            {(id) => <input id={id} type="email" className="field" placeholder="nombre@asserta.es" value={v.manager_upn} onChange={(e) => setV({ ...v, manager_upn: e.target.value })} />}
          </Field>
          <Field label="Centro de coste">{(id) => <input id={id} className="field" value={v.cost_center} onChange={(e) => setV({ ...v, cost_center: e.target.value })} />}</Field>
        </div>
        <div>
          <p className="label">Atributos adicionales</p>
          <div className="space-y-2">
            {attrs.map(([k, val], i) => (
              <div key={i} className="flex gap-2">
                <input aria-label="Atributo" className="field" placeholder="Atributo" value={k} onChange={(e) => setAttrs(attrs.map((a, j) => j === i ? [e.target.value, a[1]] : a))} />
                <input aria-label="Valor" className="field" placeholder="Valor" value={val} onChange={(e) => setAttrs(attrs.map((a, j) => j === i ? [a[0], e.target.value] : a))} />
                <Button variant="ghost" aria-label="Quitar" onClick={() => setAttrs(attrs.filter((_, j) => j !== i))}>×</Button>
              </div>
            ))}
            <Button size="sm" variant="ghost" icon={<Plus className="size-3.5" />} onClick={() => setAttrs([...attrs, ["", ""]])}>Añadir atributo</Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
