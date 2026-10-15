import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, GitMerge, Pencil, Plus, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AuthBadge, SourceBadge } from "@/components/badges";
import { DataTable, type Column } from "@/components/DataTable";
import { Badge, Button, Card, DefinitionList, ErrorState, Field, Modal, Notice, PageHeader, Spinner, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { AUTH_LABEL, CATEGORY_LABEL, fmtDate, fmtDateTime } from "@/lib/format";
import { useAction } from "@/lib/hooks";
import { useDepartments } from "@/lib/queries";
import type { DeviceRow, Paged, Policy, Product } from "@/lib/types";

interface ProductDetail extends Product {
  version_list: { id: number; version: string | null; first_seen_at: string; devices: number }[];
  aliases: { id: number; raw_name: string; publisher_key: string; origin: string; created_by: string | null }[];
  by_department: { department: string; devices: number }[];
  policies: Policy[];
}
interface Inst { device_id: number; device: string; department: string | null; user: string | null; version: string | null;
  source: string; present: boolean; first_seen_at: string; last_seen_at: string; authorization_status: string; authorization_origin: string }

type Tab = "instalaciones" | "versiones" | "politicas" | "alias";

export default function SoftwareDetail() {
  const id = Number(useParams().id);
  const can = useCan();
  const [tab, setTab] = useState<Tab>("instalaciones");
  const [version, setVersion] = useState<string | null>(null);
  const [dialog, setDialog] = useState<null | "edit" | "policy" | "alias" | "merge">(null);
  const q = useQuery({ queryKey: ["product", id], queryFn: () => api.get<ProductDetail>(`/software/${id}`) });
  const inst = useQuery({ queryKey: ["product-inst", id, version], queryFn: () =>
    api.get<{ items: Inst[] }>(`/software/${id}/installations`, { version: version ?? undefined }) });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorState error={q.error} retry={q.refetch} />;
  const p = q.data;
  const instCols: Column<Inst>[] = [
    { id: "device", header: "Dispositivo", cell: (i) => <Link className="font-medium hover:text-accent hover:underline" to={`/dispositivos/${i.device_id}`}>{i.device}</Link> },
    { id: "dept", header: "Departamento", cell: (i) => i.department ?? "—" },
    { id: "user", header: "Usuario", cell: (i) => i.user ?? "—" },
    { id: "version", header: "Versión", cell: (i) => <span className="font-mono text-xs">{i.version ?? "—"}</span> },
    { id: "auth", header: "Autorización efectiva", cell: (i) => <span title={i.authorization_origin}><AuthBadge status={i.authorization_status} /></span> },
    { id: "source", header: "Fuente", cell: (i) => <SourceBadge source={i.source} /> },
    { id: "first", header: "Detectado desde", cell: (i) => fmtDate(i.first_seen_at) },
  ];

  return (
    <>
      <PageHeader title={p.name}
        description={<span className="flex flex-wrap items-center gap-2">
          <AuthBadge status={p.authorization_status} />
          <Badge>{CATEGORY_LABEL[p.category] ?? p.category}</Badge>
          {!p.is_relevant && <Badge>No relevante</Badge>}
          <span>{p.publisher ?? "Editor desconocido"}</span>
        </span>}
        actions={can.write && <>
          <Button icon={<GitMerge className="size-4" />} onClick={() => setDialog("merge")}>Fusionar</Button>
          <Button icon={<Pencil className="size-4" />} onClick={() => setDialog("edit")}>Editar</Button>
          <Button variant="primary" icon={<ShieldCheck className="size-4" />} onClick={() => setDialog("policy")}>Autorización</Button>
        </>}>
        <Link to="/software" className="mb-2 inline-flex items-center gap-1 text-xs text-muted hover:text-fg"><ArrowLeft className="size-3" /> Software</Link>
      </PageHeader>

      <div className="mb-4 grid gap-4 lg:grid-cols-3">
        <Card title="Resumen" className="lg:col-span-2">
          <DefinitionList items={[
            ["Dispositivos con el producto", p.devices], ["Versiones en uso", p.versions],
            ["Primera detección", fmtDate(p.first_seen_at)], ["Última detección", fmtDate(p.last_seen_at)],
            ["Clasificación ENS", p.ens_classification], ["Notas", p.notes],
          ]} />
        </Card>
        <Card title="Por departamento">
          {p.by_department.length === 0 ? <p className="text-muted">Sin instalaciones vigentes.</p> : (
            <ul className="space-y-1.5">{p.by_department.map((d) => (
              <li key={d.department} className="flex justify-between"><span>{d.department}</span><span className="num text-muted">{d.devices}</span></li>
            ))}</ul>
          )}
        </Card>
      </div>

      <Tabs value={tab} onChange={setTab} tabs={[
        { id: "instalaciones", label: `Instalaciones (${p.devices})` }, { id: "versiones", label: `Versiones (${p.version_list.length})` },
        { id: "politicas", label: `Autorizaciones (${p.policies.filter((x) => x.active).length})` }, { id: "alias", label: "Alias" },
      ]} />

      {tab === "instalaciones" && (
        <DataTable columns={instCols} rows={inst.data?.items} rowKey={(i) => `${i.device_id}-${i.version}-${i.source}`}
          loading={inst.isLoading} error={inst.error} storageKey="product-inst"
          toolbar={<select aria-label="Versión" className="field w-auto" value={version ?? "__all"}
            onChange={(e) => setVersion(e.target.value === "__all" ? null : e.target.value)}>
            <option value="__all">Todas las versiones</option>
            {p.version_list.filter((v) => v.devices > 0).map((v) => <option key={v.id} value={v.version ?? ""}>{v.version ?? "(desconocida)"} · {v.devices}</option>)}
          </select>} />
      )}
      {tab === "versiones" && (
        <DataTable rows={p.version_list} rowKey={(v) => v.id} columns={[
          { id: "v", header: "Versión", cell: (v) => <span className="font-mono">{v.version ?? "(desconocida)"}</span> },
          { id: "d", header: "Dispositivos", align: "right", cell: (v) => v.devices },
          { id: "f", header: "Vista por primera vez", cell: (v) => fmtDate(v.first_seen_at) },
          { id: "a", header: "", cell: (v) => v.devices > 0 && <button className="text-xs text-accent hover:underline"
            onClick={() => { setVersion(v.version ?? ""); setTab("instalaciones"); }}>Ver equipos</button> },
        ]} />
      )}
      {tab === "politicas" && <Policies product={p} />}
      {tab === "alias" && (
        <Card title="Nombres asociados" actions={can.write && <Button size="sm" icon={<Plus className="size-4" />} onClick={() => setDialog("alias")}>Añadir alias</Button>}>
          <p className="mb-3 text-xs text-muted">Nombres con los que las fuentes informan de este producto. Los alias manuales se aplican en futuras sincronizaciones.</p>
          <ul className="divide-y divide-border">{p.aliases.map((a) => (
            <li key={a.id} className="flex items-center gap-2 py-2"><span className="flex-1">{a.raw_name}</span>
              {a.publisher_key && <span className="text-xs text-muted">{a.publisher_key}</span>}
              <Badge tone={a.origin === "manual" ? "accent" : "neutral"}>{a.origin === "manual" ? "Manual" : "Automático"}</Badge></li>
          ))}</ul>
        </Card>
      )}

      {dialog === "edit" && <EditProduct p={p} onClose={() => setDialog(null)} />}
      {dialog === "policy" && <PolicyDialog product={p} onClose={() => setDialog(null)} />}
      {dialog === "alias" && <AliasDialog id={p.id} onClose={() => setDialog(null)} />}
      {dialog === "merge" && <MergeDialog target={p} onClose={() => setDialog(null)} />}
    </>
  );
}

function Policies({ product }: { product: ProductDetail }) {
  const can = useCan();
  const revoke = useAction((id: number) => api.send("POST", `/policies/${id}/revoke`), {
    success: "Política revocada", invalidate: [["product", product.id], ["software"], ["product-inst", product.id]],
  });
  const cols: Column<Policy>[] = [
    { id: "status", header: "Estado", cell: (x) => <AuthBadge status={x.status} /> },
    { id: "scope", header: "Ámbito", cell: (x) => x.scope === "global" ? "Global" : x.scope === "department" ? `Departamento · ${x.department}` : `Dispositivo · ${x.device}` },
    { id: "just", header: "Justificación", cell: (x) => <span className="block max-w-72 truncate" title={x.justification ?? ""}>{x.justification ?? "—"}</span> },
    { id: "by", header: "Aprobado por", cell: (x) => x.approved_by ?? x.created_by ?? "—" },
    { id: "until", header: "Vigencia", cell: (x) => x.valid_until ? <span className={x.expired ? "text-danger" : ""}>hasta {fmtDate(x.valid_until)}</span> : "Indefinida" },
    { id: "state", header: "", cell: (x) => !x.active ? <span className="text-xs text-muted">Revocada {fmtDateTime(x.revoked_at)}</span>
      : can.write && <Button size="sm" variant="ghost" loading={revoke.isPending} onClick={() => revoke.mutate(x.id)}>Revocar</Button> },
  ];
  return (
    <>
      <div className="mb-3"><Notice>La autorización efectiva se resuelve así: política del dispositivo › del departamento › global. Las políticas revocadas o caducadas se conservan como evidencia.</Notice></div>
      <DataTable columns={cols} rows={product.policies} rowKey={(x) => x.id} rowClassName={(x) => (x.active ? undefined : "opacity-60")} />
    </>
  );
}

function EditProduct({ p, onClose }: { p: ProductDetail; onClose: () => void }) {
  const [v, setV] = useState({ name: p.name, category: p.category, is_relevant: p.is_relevant,
    authorization_status: (p.authorization_status === "exception" ? "unclassified" : p.authorization_status) as string,
    ens_classification: p.ens_classification ?? "", notes: p.notes ?? "", reason: "" });
  const save = useAction(() => api.send("PATCH", `/software/${p.id}`, { ...v, ens_classification: v.ens_classification || null,
    notes: v.notes || null, reason: v.reason || null }), { success: "Producto actualizado",
    invalidate: [["product", p.id], ["software"], ["dashboard"]], onSuccess: onClose });
  return (
    <Modal open onClose={onClose} title="Editar producto" footer={<><Button onClick={onClose}>Cancelar</Button>
      <Button variant="primary" loading={save.isPending} onClick={() => save.mutate(undefined)}>Guardar</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2"><Field label="Nombre">{(id) => <input id={id} className="field" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />}</Field></div>
        <Field label="Autorización global">{(id) => <select id={id} className="field" value={v.authorization_status}
          onChange={(e) => setV({ ...v, authorization_status: e.target.value })}>
          {["authorized", "unauthorized", "pending_review", "unclassified"].map((s) => <option key={s} value={s}>{AUTH_LABEL[s]}</option>)}</select>}</Field>
        <Field label="Categoría">{(id) => <select id={id} className="field" value={v.category} onChange={(e) => setV({ ...v, category: e.target.value })}>
          {Object.entries(CATEGORY_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>}</Field>
        <Field label="Clasificación ENS">{(id) => <input id={id} className="field" value={v.ens_classification} onChange={(e) => setV({ ...v, ens_classification: e.target.value })} />}</Field>
        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={v.is_relevant}
          onChange={(e) => setV({ ...v, is_relevant: e.target.checked })} className="accent-[rgb(var(--accent))]" /> Aplicación relevante</label>
        <div className="sm:col-span-2"><Field label="Notas">{(id) => <textarea id={id} rows={3} className="field" value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} />}</Field></div>
        <div className="sm:col-span-2"><Field label="Motivo del cambio">{(id) => <input id={id} className="field" value={v.reason} onChange={(e) => setV({ ...v, reason: e.target.value })} />}</Field></div>
      </div>
    </Modal>
  );
}

function PolicyDialog({ product, onClose }: { product: ProductDetail; onClose: () => void }) {
  const depts = useDepartments().data?.items.filter((d) => d.active) ?? [];
  const [v, setV] = useState({ scope: "global", status: "authorized", department_id: "", device_id: "", justification: "", approved_by: "", valid_until: "" });
  const [deviceQuery, setDeviceQuery] = useState("");
  const devices = useQuery({ queryKey: ["device-search", deviceQuery], enabled: v.scope === "device" && deviceQuery.length > 1,
    queryFn: () => api.get<Paged<DeviceRow>>("/devices", { q: deviceQuery, page_size: 10 }) });
  const isException = v.status === "exception";
  const save = useAction(() => api.send("POST", "/policies", {
    product_id: product.id, scope: v.scope, status: v.status,
    department_id: v.scope === "department" ? Number(v.department_id) : null,
    device_id: v.scope === "device" ? Number(v.device_id) : null,
    justification: v.justification || null, approved_by: v.approved_by || null,
    valid_until: v.valid_until ? `${v.valid_until}T23:59:59` : null,
  }), { success: "Autorización registrada", invalidate: [["product", product.id], ["software"], ["product-inst", product.id], ["dashboard"]], onSuccess: onClose });
  const invalid = (v.scope === "department" && !v.department_id) || (v.scope === "device" && !v.device_id)
    || (isException && (!v.justification.trim() || !v.approved_by.trim()));
  return (
    <Modal open onClose={onClose} title={`Autorización · ${product.name}`} footer={<><Button onClick={onClose}>Cancelar</Button>
      <Button variant="primary" disabled={invalid} loading={save.isPending} onClick={() => save.mutate(undefined)}>Registrar</Button></>}>
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Ámbito">{(id) => <select id={id} className="field" value={v.scope}
            onChange={(e) => setV({ ...v, scope: e.target.value, status: e.target.value === "global" && v.status === "exception" ? "authorized" : v.status })}>
            <option value="global">Global</option><option value="department">Departamento</option><option value="device">Dispositivo</option></select>}</Field>
          <Field label="Estado">{(id) => <select id={id} className="field" value={v.status} onChange={(e) => setV({ ...v, status: e.target.value })}>
            {["authorized", "unauthorized", "pending_review", ...(v.scope !== "global" ? ["exception"] : [])].map((s) => <option key={s} value={s}>{AUTH_LABEL[s]}</option>)}</select>}</Field>
        </div>
        {v.scope === "department" && <Field label="Departamento">{(id) => <select id={id} className="field" value={v.department_id}
          onChange={(e) => setV({ ...v, department_id: e.target.value })}><option value="">Seleccione…</option>
          {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>}</Field>}
        {v.scope === "device" && <Field label="Dispositivo" hint={v.device_id ? `Seleccionado: ${devices.data?.items.find((d) => String(d.id) === v.device_id)?.name ?? v.device_id}` : "Escriba para buscar"}>
          {(id) => <div><input id={id} className="field" value={deviceQuery} onChange={(e) => setDeviceQuery(e.target.value)} placeholder="Nombre o serie…" />
            {devices.data && <ul className="mt-1 max-h-40 overflow-y-auto rounded-md border border-border">{devices.data.items.map((d) => (
              <li key={d.id}><button type="button" onClick={() => setV({ ...v, device_id: String(d.id) })}
                className={`w-full px-3 py-1.5 text-left hover:bg-subtle ${String(d.id) === v.device_id ? "bg-accent/10" : ""}`}>{d.name} <span className="text-muted">{d.department ?? ""}</span></button></li>
            ))}</ul>}</div>}</Field>}
        <Field label={isException ? "Justificación (obligatoria)" : "Justificación"}>{(id) => <textarea id={id} rows={2} className="field" value={v.justification} onChange={(e) => setV({ ...v, justification: e.target.value })} />}</Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={isException ? "Responsable que aprueba (obligatorio)" : "Responsable que aprueba"}>{(id) => <input id={id} className="field" value={v.approved_by} onChange={(e) => setV({ ...v, approved_by: e.target.value })} />}</Field>
          <Field label="Vigente hasta" hint="Vacío = indefinida">{(id) => <input id={id} type="date" className="field" value={v.valid_until} onChange={(e) => setV({ ...v, valid_until: e.target.value })} />}</Field>
        </div>
      </div>
    </Modal>
  );
}

function AliasDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const [name, setName] = useState("");
  const [publisher, setPublisher] = useState("");
  const save = useAction(() => api.send("POST", `/software/${id}/aliases`, { raw_name: name, raw_publisher: publisher || null }),
    { success: "Alias añadido", invalidate: [["product", id]], onSuccess: onClose });
  return (
    <Modal open onClose={onClose} title="Añadir alias" footer={<><Button onClick={onClose}>Cancelar</Button>
      <Button variant="primary" disabled={!name.trim()} loading={save.isPending} onClick={() => save.mutate(undefined)}>Añadir</Button></>}>
      <div className="space-y-4">
        <Field label="Nombre tal como lo informa la fuente">{(fid) => <input id={fid} className="field" value={name} onChange={(e) => setName(e.target.value)} />}</Field>
        <Field label="Editor (opcional)">{(fid) => <input id={fid} className="field" value={publisher} onChange={(e) => setPublisher(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}

function MergeDialog({ target, onClose }: { target: ProductDetail; onClose: () => void }) {
  const nav = useNavigate();
  const [search, setSearch] = useState("");
  const [ids, setIds] = useState<number[]>([]);
  const [reason, setReason] = useState("");
  const found = useQuery({ queryKey: ["merge-search", search], enabled: search.length > 1,
    queryFn: () => api.get<Paged<Product>>("/software", { q: search, page_size: 15 }) });
  const merge = useAction(() => api.send("POST", `/software/${target.id}/merge`, { source_ids: ids, reason }), {
    success: "Productos fusionados", invalidate: [["software"], ["product", target.id]], onSuccess: () => { onClose(); nav(`/software/${target.id}`); },
  });
  return (
    <Modal open onClose={onClose} title={`Fusionar en «${target.name}»`} wide footer={<><Button onClick={onClose}>Cancelar</Button>
      <Button variant="danger" disabled={!ids.length || reason.trim().length < 3} loading={merge.isPending} onClick={() => merge.mutate(undefined)}>Fusionar {ids.length || ""}</Button></>}>
      <div className="space-y-4">
        <Notice tone="warn">Use la fusión solo si son el mismo producto. Las instalaciones y alias pasan a este producto; los originales se conservan marcados como fusionados.</Notice>
        <Field label="Buscar productos duplicados">{(id) => <input id={id} className="field" value={search} onChange={(e) => setSearch(e.target.value)} />}</Field>
        <ul className="max-h-60 divide-y divide-border overflow-y-auto rounded-md border border-border">
          {(found.data?.items ?? []).filter((x) => x.id !== target.id).map((x) => (
            <li key={x.id}><label className="flex cursor-pointer items-center gap-2 px-3 py-2 hover:bg-subtle">
              <input type="checkbox" checked={ids.includes(x.id)} className="accent-[rgb(var(--accent))]"
                onChange={(e) => setIds(e.target.checked ? [...ids, x.id] : ids.filter((i) => i !== x.id))} />
              <span className="flex-1">{x.name}</span><span className="text-xs text-muted">{x.publisher} · {x.devices} equipos</span>
            </label></li>
          ))}
        </ul>
        <Field label="Motivo">{(id) => <input id={id} className="field" value={reason} onChange={(e) => setReason(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}
