import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Archive, Pencil, RotateCcw, Upload } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AuthBadge, ComplianceBadge, DeviceStatusBadge, FreshnessBadge, SourceBadge } from "@/components/badges";
import { DataTable, type Column } from "@/components/DataTable";
import { DeviceForm, type DeviceFormValues } from "@/components/DeviceForm";
import { UploadDialog } from "@/components/UploadDialog";
import { Badge, Button, Card, ConfirmDialog, DefinitionList, EmptyState, ErrorState, Field, PageHeader, Spinner, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { CATEGORY_LABEL, CHANGE_LABEL, FIELD_LABEL, SOURCE_LABEL, fmtBytes, fmtDate, fmtDateTime, fmtRelative } from "@/lib/format";
import { useAction } from "@/lib/hooks";
import type { Change, DeviceDetail as Device, InstalledSoftware } from "@/lib/types";

type Tab = "resumen" | "hardware" | "software" | "asignaciones" | "historial";

function Sourced({ d, field, children }: { d: Device; field: string; children: React.ReactNode }) {
  const src = d.field_sources?.[field];
  return (
    <span title={src ? `Fuente: ${SOURCE_LABEL[src.source] ?? src.source} · ${fmtDateTime(src.at)}` : undefined}>
      {children ?? "—"}
      {src && <span className="ml-1.5 text-2xs text-muted">{SOURCE_LABEL[src.source] ?? src.source}</span>}
    </span>
  );
}

export default function DeviceDetail() {
  const id = Number(useParams().id);
  const can = useCan();
  const [tab, setTab] = useState<Tab>("resumen");
  const [editing, setEditing] = useState(false);
  const [retiring, setRetiring] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [reason, setReason] = useState("");
  const q = useQuery({ queryKey: ["device", id], queryFn: () => api.get<Device>(`/devices/${id}`) });
  const inv = [["device", id], ["devices"], ["dashboard"], ["device-history", id], ["device-assignments", id]];
  const update = useAction((v: DeviceFormValues) => api.send<Device>("PATCH", `/devices/${id}`, v),
    { success: "Cambios guardados", invalidate: inv, onSuccess: () => setEditing(false) });
  const retire = useAction(() => api.send("POST", `/devices/${id}/${q.data?.status === "retired" ? "reactivate" : "retire"}`, { reason }),
    { success: "Estado actualizado", invalidate: inv, onSuccess: () => { setRetiring(false); setReason(""); } });

  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorState error={q.error} retry={q.refetch} />;
  const d = q.data;
  const retired = d.status === "retired";

  return (
    <>
      <PageHeader title={d.name}
        description={<span className="flex flex-wrap items-center gap-2">
          <DeviceStatusBadge status={d.status} /><FreshnessBadge value={d.freshness} />
          {d.device_type && <Badge>{d.device_type}</Badge>}
          <span className="font-mono text-2xs">{d.uid}</span>
        </span>}
        actions={can.write && <>
          {!retired && <Button icon={<Upload className="size-4" />} onClick={() => setUploading(true)}>Importar Panda</Button>}
          {!retired && <Button icon={<Pencil className="size-4" />} onClick={() => setEditing(true)}>Editar</Button>}
          <Button variant={retired ? "secondary" : "ghost"} icon={retired ? <RotateCcw className="size-4" /> : <Archive className="size-4" />}
            onClick={() => setRetiring(true)}>{retired ? "Reactivar" : "Dar de baja"}</Button>
        </>}>
        <Link to="/dispositivos" className="mb-2 inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
          <ArrowLeft className="size-3" /> Dispositivos
        </Link>
      </PageHeader>

      <Tabs value={tab} onChange={setTab} tabs={[
        { id: "resumen", label: "Resumen" }, { id: "hardware", label: "Hardware" },
        { id: "software", label: "Software" }, { id: "asignaciones", label: "Asignaciones" },
        { id: "historial", label: "Historial" },
      ]} />

      {tab === "resumen" && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card title="Asignación" className="lg:col-span-2">
            <DefinitionList items={[
              ["Departamento", d.department ? <Link className="hover:underline" to={`/departamentos/${d.department_id}`}>{d.department}</Link> : "Sin asignar"],
              ["Usuario principal", d.primary_user ? <span title={d.primary_user_upn ?? ""}>{d.primary_user}</span> : "—"],
              ["Ubicación", d.location],
              ["Propiedad", d.ownership],
              ["Alta en inventario", fmtDate(d.first_seen_at ?? d.created_at)],
              ["Baja", d.retired_at ? fmtDate(d.retired_at) : "—"],
            ]} />
            {d.notes && <div className="mt-4 whitespace-pre-line rounded-md bg-subtle p-3 text-sm">{d.notes}</div>}
          </Card>
          <Card title="Estado y procedencia">
            <DefinitionList items={[
              ["Cumplimiento", <ComplianceBadge key="c" value={d.compliance_state} />],
              ["Cifrado", d.encrypted == null ? "Desconocido" : d.encrypted ? "Sí" : "No"],
              ["Último check-in (fuente)", fmtRelative(d.source_last_sync_at)],
              ["Última observación", `${fmtRelative(d.last_seen_at)}${d.last_seen_source ? ` · ${SOURCE_LABEL[d.last_seen_source] ?? d.last_seen_source}` : ""}`],
              ["Inscripción", fmtDate(d.enrolled_at)],
              ["Gestión", d.management_state],
            ]} />
            {d.external_ids.length > 0 && (
              <div className="mt-4 space-y-1.5 border-t border-border pt-3">
                <p className="text-xs text-muted">Identificadores de origen</p>
                {d.external_ids.map((e) => (
                  <div key={`${e.source}${e.type}`} className="flex items-center gap-2 text-xs">
                    <SourceBadge source={e.source} />
                    <span className="text-muted">{e.type}</span>
                    <span className="truncate font-mono" title={e.value}>{e.value}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {tab === "hardware" && (
        <Card title="Características técnicas">
          <p className="mb-4 text-xs text-muted">Junto a cada dato se indica la fuente que lo aportó. Un dato corregido a mano prevalece sobre las fuentes automáticas.</p>
          <DefinitionList items={[
            ["Nombre", <Sourced key="h" d={d} field="hostname">{d.hostname}</Sourced>],
            ["Nº de serie", <Sourced key="s" d={d} field="serial_number"><span className="font-mono">{d.serial_number}</span></Sourced>],
            ["Fabricante", <Sourced key="m" d={d} field="manufacturer">{d.manufacturer}</Sourced>],
            ["Modelo", <Sourced key="mo" d={d} field="model">{d.model}</Sourced>],
            ["Sistema operativo", <Sourced key="o" d={d} field="os_name">{d.os_name}</Sourced>],
            ["Versión del SO", <Sourced key="ov" d={d} field="os_version">{d.os_version}</Sourced>],
            ["Procesador", d.processor],
            ["Memoria RAM", <Sourced key="r" d={d} field="ram_bytes">{d.ram_bytes ? fmtBytes(d.ram_bytes, true) : null}</Sourced>],
            ["Almacenamiento", <Sourced key="st" d={d} field="storage_total_bytes">
              {d.storage_total_bytes ? `${fmtBytes(d.storage_total_bytes)}${d.storage_free_bytes ? ` · ${fmtBytes(d.storage_free_bytes)} libres` : ""}` : null}
            </Sourced>],
            ["MAC Wi-Fi", <span key="w" className="font-mono">{d.mac_wifi ?? "—"}</span>],
            ["MAC Ethernet", <span key="e" className="font-mono">{d.mac_ethernet ?? "—"}</span>],
            ["Fecha de compra", fmtDate(d.purchase_date)],
          ]} />
        </Card>
      )}

      {tab === "software" && <DeviceSoftware id={id} />}
      {tab === "asignaciones" && <Assignments id={id} />}
      {tab === "historial" && <History id={id} />}

      {editing && <DeviceForm open title="Editar dispositivo" initial={d} busy={update.isPending}
        onClose={() => setEditing(false)} onSubmit={(v) => update.mutate(v)} />}
      <ConfirmDialog open={retiring} onClose={() => setRetiring(false)} busy={retire.isPending}
        title={retired ? "Reactivar dispositivo" : "Dar de baja el dispositivo"} danger={!retired}
        confirmLabel={retired ? "Reactivar" : "Dar de baja"}
        onConfirm={() => reason.trim().length >= 3 && retire.mutate(undefined)}>
        <p className="mb-3 text-muted">
          {retired ? "Volverá a contar en el inventario vigente." :
            "Es una baja lógica: el dispositivo y todo su historial se conservan y deja de contar en el inventario vigente."}
        </p>
        <Field label="Motivo (obligatorio)">
          {(fid) => <input id={fid} className="field" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />}
        </Field>
      </ConfirmDialog>
      {uploading && <UploadDialog source="panda" deviceId={id} deviceName={d.name} onClose={() => setUploading(false)} />}
    </>
  );
}

function DeviceSoftware({ id }: { id: number }) {
  const [removed, setRemoved] = useState(false);
  const [onlyRelevant, setOnlyRelevant] = useState(true);
  const [search, setSearch] = useState("");
  const q = useQuery({ queryKey: ["device-software", id, removed],
    queryFn: () => api.get<{ items: InstalledSoftware[] }>(`/devices/${id}/software`, { include_removed: removed }) });
  const rows = (q.data?.items ?? []).filter((s) => (!onlyRelevant || s.is_relevant) &&
    (!search || `${s.name} ${s.publisher ?? ""}`.toLowerCase().includes(search.toLowerCase())));
  const cols: Column<InstalledSoftware>[] = [
    { id: "name", header: "Aplicación", cell: (s) => <Link className="font-medium hover:text-accent hover:underline" to={`/software/${s.product_id}`}>{s.name}</Link> },
    { id: "publisher", header: "Editor", cell: (s) => s.publisher ?? "—" },
    { id: "version", header: "Versión", cell: (s) => <span className="font-mono text-xs">{s.version ?? "—"}</span> },
    { id: "category", header: "Categoría", hidden: true, cell: (s) => CATEGORY_LABEL[s.category] ?? s.category },
    { id: "auth", header: "Autorización", cell: (s) => <span title={s.authorization_origin}><AuthBadge status={s.authorization_status} /></span> },
    { id: "source", header: "Fuente", cell: (s) => <SourceBadge source={s.source} /> },
    { id: "first", header: "Detectado", cell: (s) => fmtDate(s.first_seen_at) },
    { id: "state", header: "Presente", cell: (s) => s.present ? "Sí" : <span className="text-muted">Retirado {fmtDate(s.removed_at)}</span> },
  ];
  return (
    <DataTable columns={cols} rows={rows} rowKey={(s) => s.installation_id} loading={q.isLoading} error={q.error}
      storageKey="device-software" onSearch={setSearch} search={search} searchPlaceholder="Filtrar aplicaciones…"
      rowClassName={(s) => (s.present ? undefined : "opacity-60")}
      toolbar={<>
        <label className="flex items-center gap-1.5 text-sm text-muted">
          <input type="checkbox" checked={onlyRelevant} onChange={(e) => setOnlyRelevant(e.target.checked)} className="accent-[rgb(var(--accent))]" />
          Solo aplicaciones (sin componentes del sistema)
        </label>
        <label className="flex items-center gap-1.5 text-sm text-muted">
          <input type="checkbox" checked={removed} onChange={(e) => setRemoved(e.target.checked)} className="accent-[rgb(var(--accent))]" />
          Incluir desinstalado
        </label>
      </>}
      empty={<EmptyState title="Sin software registrado">Sincronice Intune o importe una exportación de Panda.</EmptyState>} />
  );
}

function Assignments({ id }: { id: number }) {
  const q = useQuery({ queryKey: ["device-assignments", id], queryFn: () =>
    api.get<{ id: number; department: string | null; user: string | null; started_at: string; ended_at: string | null;
      reason: string | null; actor: string | null; source: string }[]>(`/devices/${id}/assignments`) });
  type A = NonNullable<typeof q.data>[number];
  const cols: Column<A>[] = [
    { id: "dept", header: "Departamento", cell: (a) => a.department ?? "Sin departamento" },
    { id: "user", header: "Usuario", cell: (a) => a.user ?? "—" },
    { id: "from", header: "Desde", cell: (a) => fmtDateTime(a.started_at) },
    { id: "to", header: "Hasta", cell: (a) => a.ended_at ? fmtDateTime(a.ended_at) : <Badge tone="accent">Vigente</Badge> },
    { id: "reason", header: "Motivo", cell: (a) => a.reason ?? "—" },
    { id: "actor", header: "Realizado por", cell: (a) => <span className="text-muted">{a.actor ?? SOURCE_LABEL[a.source] ?? a.source}</span> },
  ];
  return <DataTable columns={cols} rows={q.data} rowKey={(a) => a.id} loading={q.isLoading} error={q.error} />;
}

function History({ id }: { id: number }) {
  const q = useQuery({ queryKey: ["device-history", id], queryFn: () =>
    api.get<{ changes: Change[]; audit: { id: number; action: string; actor: string; summary: string; at: string }[] }>(`/devices/${id}/history`) });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const items = [
    ...(q.data?.changes ?? []).map((c) => ({ key: `c${c.id}`, at: c.at, who: SOURCE_LABEL[c.source ?? ""] ?? c.source,
      text: <>{CHANGE_LABEL[c.type] ?? c.type}{c.field && <> · {FIELD_LABEL[c.field] ?? c.field}</>}
        {c.product && <> · <Link className="hover:underline" to={`/software/${c.product_id}`}>{c.product}</Link></>}
        {(c.old || c.new) && c.type !== "software_baseline" && <span className="text-muted"> ({c.old ?? "—"} → {c.new ?? "—"})</span>}
        {c.type === "software_baseline" && <span className="text-muted"> ({c.new} programas)</span>}</> })),
    ...(q.data?.audit ?? []).map((a) => ({ key: `a${a.id}`, at: a.at, who: a.actor, text: <>{a.summary}</> })),
  ].sort((a, b) => b.at.localeCompare(a.at));
  if (!items.length) return <EmptyState title="Sin historial" />;
  return (
    <Card padded={false}>
      <ol className="divide-y divide-border">
        {items.map((i) => (
          <li key={i.key} className="flex gap-4 px-4 py-2.5">
            <time className="w-36 shrink-0 text-xs text-muted" dateTime={i.at}>{fmtDateTime(i.at)}</time>
            <span className="min-w-0 flex-1">{i.text}</span>
            <span className="shrink-0 text-xs text-muted">{i.who}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}
