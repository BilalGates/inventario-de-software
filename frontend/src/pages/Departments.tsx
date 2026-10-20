import { Download, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, EmptyState, ErrorState, Field, Modal, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { useAction } from "@/lib/hooks";
import { useDepartments } from "@/lib/queries";
import type { Department } from "@/lib/types";

export default function Departments() {
  const can = useCan();
  const q = useDepartments();
  const [editing, setEditing] = useState<Department | "new" | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} retry={q.refetch} />;
  const items = (q.data?.items ?? []).filter((d) => showInactive || d.active);
  const inactive = (q.data?.items ?? []).filter((d) => !d.active).length;

  return (
    <>
      <PageHeader title="Departamentos" description="Estructura organizativa. Independiente del tipo de hardware y del catálogo de software."
        actions={<>
          <Button icon={<Download className="size-4" />} onClick={() => api.download("/users/export", { format: "xlsx" })}>Exportar usuarios</Button>
          {can.write && <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setEditing("new")}>Nuevo departamento</Button>}
        </>} />
      {inactive > 0 && (
        <label className="mb-3 flex items-center gap-2 text-sm text-muted">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} className="accent-[rgb(var(--accent))]" />
          Mostrar {inactive} inactivos
        </label>
      )}
      {items.length === 0 ? (
        <div className="card"><EmptyState title="Aún no hay departamentos">Cree los departamentos de Asserta para asignar dispositivos y usuarios.</EmptyState></div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((d) => (
            <Link key={d.id} to={`/departamentos/${d.id}`} className="card group p-4 transition-colors hover:border-muted/40">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="truncate font-semibold group-hover:text-accent">{d.name}</h2>
                  <p className="truncate text-xs text-muted">{d.manager ? `Responsable: ${d.manager}` : "Sin responsable"}</p>
                </div>
                {!d.active && <Badge>Inactivo</Badge>}
              </div>
              {d.description && <p className="mt-2 line-clamp-2 text-muted">{d.description}</p>}
              <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
                {[["Dispositivos", d.devices], ["Usuarios", d.users], ["Aplicaciones", d.software]].map(([k, v]) => (
                  <div key={k as string}><dd className="num text-lg font-semibold">{v ?? 0}</dd><dt className="text-2xs text-muted">{k}</dt></div>
                ))}
              </dl>
            </Link>
          ))}
          {!!q.data?.unassigned_devices && (
            <Link to="/dispositivos?unassigned=true" className="card flex flex-col justify-center border-dashed p-4 text-center hover:border-muted/40">
              <span className="num text-2xl font-semibold text-warn">{q.data.unassigned_devices}</span>
              <span className="text-sm text-muted">dispositivos sin departamento</span>
            </Link>
          )}
        </div>
      )}
      {editing && <DepartmentForm dept={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
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
