import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Download, FileSpreadsheet, GitCompare, Plus, ShieldCheck, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { SnapshotBadge } from "@/components/badges";
import { DataTable, type Column, type TableGroup } from "@/components/DataTable";
import type { MenuEntry } from "@/components/ContextMenu";
import { NotifyDialog, UninstallDialog } from "@/components/RemoteActionDialogs";
import { BigNum, FilterChips, HATCH, Kpi, KpiStrip, ScreenHeader, StackBar, StatusDot, Stepper, Swatch, groupByDay, hhmm, type DotKind } from "@/components/kit";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, Segmented, Spinner, Tabs } from "@/components/ui";
import { useDashboard, type DashboardData } from "@/lib/dashboard";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { CHANGE_LABEL, FIELD_LABEL, SOURCE_LABEL, currentPeriod, fmtDateTime, fmtPeriod, fmtRelative } from "@/lib/format";
import { useAction, useUrlState } from "@/lib/hooks";
import type { Alert, Change, Paged, Snapshot } from "@/lib/types";
import { REMOTE_STATUS_LABEL, type NotifyScope, type RemoteAction } from "@/lib/actions";

type Tab = "mensual" | "cambios" | "alertas" | "acciones" | "revision" | "registro";

const weekFmt = new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "short" });
const PHASES = ["Recogida", "Revisión", "Cierre", "Informe"];

function AuditSummary({ dash }: { dash: DashboardData }) {
  const sev = dash.alerts.by_severity;
  const weeks = dash.alerts.weekly ?? [];
  const maxW = Math.max(1, ...weeks.map((w) => Math.max(w.opened, w.resolved)));
  const days = dash.changes_daily ?? [];
  const t = days.reduce((a, d) => ({ i: a.i + d.installed, u: a.u + d.updated, r: a.r + d.removed }), { i: 0, u: 0, r: 0 });
  const m = dash.monthly;
  const status = m.snapshot?.status;
  const phase = status === "approved" ? 3 : status === "draft" ? 1 : m.coverage.complete ? 1 : 0;
  const [y, mo] = m.period.split("-").map(Number);
  const daysLeft = Math.max(0, Math.ceil((new Date(y, mo, 1).getTime() - Date.now()) / 864e5));
  return (
    <KpiStrip label="Resumen de auditoría" className="mb-6">
      <Kpi label="Alertas por severidad"
        footer={dash.alerts.unauthorized_devices ? `${dash.alerts.unauthorized_devices} equipos con software no autorizado` : undefined}>
        <BigNum value={dash.alerts.open}>{`${sev.critical ?? 0} críticas · ${sev.warning ?? 0} avisos · ${sev.info ?? 0} info`}</BigNum>
        <StackBar label={`${sev.critical ?? 0} críticas, ${sev.warning ?? 0} avisos, ${sev.info ?? 0} informativas`} segments={[
          { label: "Críticas", value: sev.critical ?? 0, className: "bg-signal-fill" },
          { label: "Avisos", value: sev.warning ?? 0, className: "bg-signal-fill/40" },
          { label: "Informativas", value: sev.info ?? 0, className: HATCH },
        ]} />
      </Kpi>
      <Kpi label="Abiertas y resueltas · 8 semanas" footer={`${dash.alerts.resolved_30d ?? 0} resueltas en 30 días`}>
        <div role="img" aria-label={weeks.map((w) => `Semana del ${w.week_start}: ${w.opened} abiertas, ${w.resolved} resueltas`).join("; ")}
          className="flex h-[72px] items-end gap-2">
          {weeks.map((w) => (
            <span key={w.week_start} className="flex h-full flex-1 items-end gap-px"
              title={`Semana del ${weekFmt.format(new Date(`${w.week_start}T12:00:00`))}: ${w.opened} abiertas · ${w.resolved} resueltas`}>
              <span className="flex-1 rounded-t-[2px] bg-signal-fill" style={{ height: `${Math.max(3, (w.opened / maxW) * 100)}%` }} />
              <span className="flex-1 rounded-t-[2px] bg-chart-1" style={{ height: `${Math.max(3, (w.resolved / maxW) * 100)}%` }} />
            </span>
          ))}
        </div>
        <p className="flex gap-4 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5"><Swatch className="bg-signal-fill" />abiertas</span>
          <span className="inline-flex items-center gap-1.5"><Swatch className="bg-chart-1" />resueltas</span>
        </p>
      </Kpi>
      <Kpi label="Cambios · 30 días">
        <BigNum value={t.i + t.u + t.r}>cambios detectados</BigNum>
        <StackBar label={`${t.u} actualizaciones, ${t.i} instalaciones, ${t.r} desinstalaciones`} segments={[
          { label: "Actualizaciones", value: t.u, className: "bg-chart-2" },
          { label: "Instalaciones", value: t.i, className: "bg-chart-1" },
          { label: "Desinstalaciones", value: t.r, className: "bg-signal-fill" },
        ]} />
        <p className="text-xs text-muted">{t.u} actualizaciones · {t.i} instalaciones · {t.r} bajas</p>
      </Kpi>
      <Kpi label={`Cierre de ${fmtPeriod(m.period).toLowerCase()}`}
        footer={status === "approved" ? "Cierre completado" : daysLeft === 1 ? "Falta 1 día" : `Faltan ${daysLeft} días`}>
        <BigNum value={PHASES[phase]} />
        <Stepper steps={PHASES} current={phase} />
      </Kpi>
    </KpiStrip>
  );
}

export default function Audit() {
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") ?? "mensual") as Tab;
  const dash = useDashboard().data;
  const snap = dash?.monthly.snapshot;
  const causes = dash?.alerts.causes_total ?? 0;
  return (
    <>
      <ScreenHeader eyebrow="Control · Auditoría"
        title={dash ? `${dash.alerts.open} ${dash.alerts.open === 1 ? "alerta abierta" : "alertas abiertas"}` : "Auditoría"}
        sub={causes ? `por ${causes} ${causes === 1 ? "causa" : "causas"}` : undefined}
        actions={snap && <Button variant="primary" icon={<FileSpreadsheet className="size-4" />}
          onClick={() => api.download(`/snapshots/${snap.id}/report`)}>Informe mensual (Excel)</Button>} />
      {dash && <AuditSummary dash={dash} />}
      <Tabs value={tab} onChange={(t) => setParams({ tab: t })} tabs={[
        { id: "mensual", label: "Inventarios mensuales" }, { id: "cambios", label: "Cambios" },
        { id: "alertas", label: "Alertas", count: dash?.alerts.open },
        { id: "acciones", label: "Acciones remotas" },
        { id: "revision", label: "Casos de revisión", count: dash?.open_review_cases || undefined },
        { id: "registro", label: "Registro de auditoría" },
      ]} />
      {tab === "mensual" && <Monthly />}
      {tab === "cambios" && <Changes />}
      {tab === "alertas" && <Alerts />}
      {tab === "acciones" && <RemoteActions />}
      {tab === "revision" && <ReviewCases />}
      {tab === "registro" && <AuditLog />}
    </>
  );
}

// ------------------------------------------------------------------ inventarios mensuales
function Monthly() {
  const can = useCan();
  const q = useQuery({ queryKey: ["snapshots"], queryFn: () => api.get<Snapshot[]>("/snapshots") });
  const [period, setPeriod] = useState(currentPeriod());
  const [reviewing, setReviewing] = useState<Snapshot | null>(null);
  const [compare, setCompare] = useState<[number, number] | null>(null);
  const generate = useAction(() => api.send<Snapshot>("POST", "/snapshots", { period }), {
    success: "Inventario generado como borrador", invalidate: [["snapshots"], ["dashboard"]],
  });
  if (q.isLoading) return <Spinner />;
  const snaps = q.data ?? [];
  const cols: Column<Snapshot>[] = [
    { id: "p", header: "Periodo", cell: (s) => (
      <span className="flex items-center gap-3 font-semibold">
        <StatusDot kind={s.status === "approved" ? "success" : s.status === "rejected" ? "failed" : s.status === "legacy" ? "muted" : "pending"} />
        {fmtPeriod(s.period)}{s.version > 1 && <span className="font-normal text-muted"> · v{s.version}</span>}
      </span>
    ) },
    { id: "st", header: "Estado", cell: (s) => <SnapshotBadge status={s.status} /> },
    { id: "c", header: "Recogida", cell: (s) => s.status === "legacy" ? <span className="text-muted">Importado</span>
      : s.is_complete ? <Badge tone="ok">Completa</Badge> : <Badge tone="warn">Incompleta</Badge> },
    { id: "d", header: "Dispositivos", align: "right", cell: (s) => s.totals?.devices ?? "—" },
    { id: "i", header: "Instalaciones", align: "right", cell: (s) => s.totals?.installations ?? "—" },
    { id: "u", header: "No autorizadas", align: "right", cell: (s) => s.totals?.by_status?.unauthorized ?? 0 },
    { id: "r", header: "Revisión", cell: (s) => s.reviewed_by ? <span className="text-xs text-muted">{s.reviewed_by} · {fmtDateTime(s.reviewed_at)}</span> : "—" },
    { id: "a", header: "", cell: (s) => {
      const prev = snaps.find((x) => x.period < s.period && x.status !== "rejected");
      return (
        <div className="flex justify-end gap-1">
          {prev && <Button size="sm" variant="ghost" icon={<GitCompare className="size-3.5" />} onClick={() => setCompare([prev.id, s.id])}>Comparar</Button>}
          <Button size="sm" variant="ghost" icon={<FileSpreadsheet className="size-3.5" />} onClick={() => api.download(`/snapshots/${s.id}/report`)}>Informe</Button>
          {can.write && s.status === "draft" && <Button size="sm" variant="primary" onClick={() => setReviewing(s)}>Revisar</Button>}
        </div>
      );
    } },
  ];
  return (
    <>
      <div className="mb-4">
        <Notice>
          La recogida automática y la aprobación son pasos separados: el worker genera el borrador mensual cuando terminan las
          sincronizaciones programadas, y un técnico lo revisa y aprueba. Un inventario solo es «completo» si todas las fuentes
          esenciales terminaron sin errores.
        </Notice>
      </div>
      <DataTable columns={cols} rows={snaps} rowKey={(s) => s.id} error={q.error}
        rowMenu={(s) => {
          const prev = snaps.find((x) => x.period < s.period && x.status !== "rejected");
          return { title: fmtPeriod(s.period), entries: [
            ...(can.write && s.status === "draft" ? [{ label: "Revisar y aprobar…", onSelect: () => setReviewing(s) }] : []),
            { label: "Comparar con el mes anterior", disabled: !prev, onSelect: () => { if (prev) setCompare([prev.id, s.id]); } },
            { label: "Descargar informe (Excel)", onSelect: () => api.download(`/snapshots/${s.id}/report`) },
          ] };
        }}
        toolbar={can.write && <div className="flex items-center gap-2">
          <input type="month" aria-label="Periodo" className="field w-40" value={period} onChange={(e) => setPeriod(e.target.value)} />
          <Button icon={<Plus className="size-4" />} loading={generate.isPending} onClick={() => generate.mutate(undefined)}>Generar inventario</Button>
        </div>}
        empty={<EmptyState title="Aún no hay inventarios mensuales">Se generan automáticamente tras la sincronización programada o manualmente desde aquí.</EmptyState>} />
      {reviewing && <ReviewSnapshot snap={reviewing} onClose={() => setReviewing(null)} />}
      {compare && <CompareDialog ids={compare} onClose={() => setCompare(null)} />}
    </>
  );
}

function ReviewSnapshot({ snap, onClose }: { snap: Snapshot; onClose: () => void }) {
  const [notes, setNotes] = useState("");
  const [accept, setAccept] = useState(false);
  const review = useAction((approve: boolean) => api.send("POST", `/snapshots/${snap.id}/review`,
    { approve, notes: notes || null, accept_incomplete: accept }), { success: "Revisión registrada", invalidate: [["snapshots"], ["dashboard"]], onSuccess: onClose });
  const sources = Object.values(snap.coverage?.sources ?? {});
  return (
    <Modal open onClose={onClose} title={`Revisar inventario de ${fmtPeriod(snap.period)}`} footer={<>
      <Button onClick={() => review.mutate(false)} loading={review.isPending}>Rechazar</Button>
      <Button variant="primary" disabled={!snap.is_complete && (!accept || !notes.trim())} loading={review.isPending}
        onClick={() => review.mutate(true)}>Aprobar</Button>
    </>}>
      <div className="space-y-4">
        <ul className="space-y-1.5">{sources.map((s) => (
          <li key={s.name} className="flex items-center gap-2">
            {s.ok ? <ShieldCheck className="size-4 text-ok" aria-hidden /> : <ShieldAlert className="size-4 text-warn" aria-hidden />}
            {s.name}{!s.essential && <span className="text-xs text-muted">(complementaria)</span>}
            <span className="ml-auto text-xs text-muted">{s.ok ? "completa" : s.runs ? "con errores" : "sin ejecuciones"}</span>
          </li>
        ))}</ul>
        <p className="text-muted">{snap.totals?.devices} dispositivos · {snap.totals?.installations} instalaciones · {snap.totals?.products} productos</p>
        {!snap.is_complete && (
          <Notice tone="warn" title="Inventario incompleto">
            Alguna fuente esencial no completó la recogida. Lo recomendable es reintentar la sincronización y regenerar el inventario.
            <label className="mt-2 flex items-center gap-2"><input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} />
              Acepto aprobarlo incompleto (requiere justificación)</label>
          </Notice>
        )}
        <Field label="Notas de revisión">{(id) => <textarea id={id} rows={3} className="field" value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}

interface Diff {
  devices_added: { id: number; name: string }[]; devices_removed: { id: number; name: string }[];
  products_new: { id: number; name: string }[]; products_gone: { id: number; name: string }[];
  installs_added: { device_id: number; device: string; product_id: number; product: string; versions: string[] }[];
  installs_removed: { device_id: number; device: string; product_id: number; product: string; versions: string[] }[];
  versions_changed: { device_id: number; device: string; product_id: number; product: string; from: string[]; to: string[] }[];
}

function CompareDialog({ ids, onClose }: { ids: [number, number]; onClose: () => void }) {
  const q = useQuery({ queryKey: ["compare", ids], queryFn: () => api.get<Diff>("/snapshots/compare", { base: ids[0], target: ids[1] }) });
  const d = q.data;
  const list = (title: string, items: { key: string; text: React.ReactNode }[]) => (
    <Card title={`${title} (${items.length})`} padded={false}>
      {items.length === 0 ? <p className="px-4 py-3 text-muted">Ninguno</p> : (
        <ul className="max-h-56 divide-y divide-border overflow-y-auto">{items.map((i) => <li key={i.key} className="px-4 py-1.5">{i.text}</li>)}</ul>
      )}
    </Card>
  );
  return (
    <Modal open onClose={onClose} title="Comparación de inventarios" wide>
      {!d ? <Spinner /> : (
        <div className="grid gap-3 md:grid-cols-2">
          {list("Dispositivos nuevos", d.devices_added.map((x) => ({ key: `${x.id}`, text: <Link to={`/dispositivos/${x.id}`}>{x.name}</Link> })))}
          {list("Dispositivos que ya no figuran", d.devices_removed.map((x) => ({ key: `${x.id}`, text: x.name })))}
          {list("Productos nuevos", d.products_new.map((x) => ({ key: `${x.id}`, text: <Link to={`/software/${x.id}`}>{x.name}</Link> })))}
          {list("Productos desaparecidos", d.products_gone.map((x) => ({ key: `${x.id}`, text: x.name })))}
          {list("Instalaciones nuevas", d.installs_added.map((x) => ({ key: `${x.device_id}-${x.product_id}`, text: <>{x.product} <span className="text-muted">· {x.device}</span></> })))}
          {list("Desinstalaciones", d.installs_removed.map((x) => ({ key: `${x.device_id}-${x.product_id}`, text: <>{x.product} <span className="text-muted">· {x.device}</span></> })))}
          <div className="md:col-span-2">{list("Cambios de versión", d.versions_changed.map((x) => ({ key: `${x.device_id}-${x.product_id}`,
            text: <>{x.product} <span className="text-muted">· {x.device} · {x.from.join(", ")} → {x.to.join(", ")}</span></> })))}</div>
        </div>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ cambios
const CHANGE_DOT: Record<string, DotKind> = {
  software_installed: "ok", software_removed: "alert", software_version_changed: "muted", authorization_changed: "warning",
  device_added: "info", device_retired: "failed", device_reactivated: "ok", device_updated: "info", device_not_observed: "warning",
  department_changed: "info", user_changed: "info",
};

const CHANGE_GROUPS: Record<string, string> = {
  "": "Todos los cambios",
  "software_installed,software_removed,software_version_changed": "Software",
  "device_added,device_retired,device_not_observed,device_updated,device_reactivated,device_merged": "Dispositivos",
  "department_changed,user_changed": "Asignaciones",
  "authorization_changed": "Autorizaciones",
};

function Changes() {
  const { values, set, page } = useUrlState(["type", "since"] as const);
  const params = { type: values.type, since: values.since, page, page_size: 50 };
  const q = useQuery({ queryKey: ["changes", params], queryFn: () => api.get<Paged<Change>>("/changes", params), placeholderData: (p) => p });
  const nav = useNavigate();
  const cols: Column<Change>[] = [
    { id: "at", header: "Hora", cell: (c) => <span className="code whitespace-nowrap text-muted" title={fmtDateTime(c.at)}>{hhmm(c.at)}</span> },
    { id: "type", header: "Cambio", cell: (c) => <span className="flex items-center gap-2.5"><StatusDot kind={CHANGE_DOT[c.type] ?? "muted"} />{CHANGE_LABEL[c.type] ?? c.type}</span> },
    { id: "device", header: "Dispositivo", cell: (c) => c.device ? <Link className="hover:underline" to={`/dispositivos/${c.device_id}`}>{c.device}</Link> : "—" },
    { id: "product", header: "Software / campo", cell: (c) => c.product ? <Link className="hover:underline" to={`/software/${c.product_id}`}>{c.product}</Link> : c.field ? FIELD_LABEL[c.field] ?? c.field : "—" },
    { id: "diff", header: "Detalle", cell: (c) => (c.old || c.new) ? <span className="font-mono text-xs">{c.old ?? "—"} → {c.new ?? "—"}</span> : "—" },
    { id: "src", header: "Fuente", cell: (c) => <span className="text-muted">{SOURCE_LABEL[c.source ?? ""] ?? c.source}</span> },
  ];
  return (
    <DataTable columns={cols} rows={q.data?.items} total={q.data?.total} rowKey={(c) => c.id} loading={q.isLoading} error={q.error}
      groups={groupByDay(q.data?.items ?? [], (c) => c.at)}
      rowMenu={(c) => ({ entries: [
        { label: "Abrir equipo", disabled: !c.device_id, onSelect: () => nav(`/dispositivos/${c.device_id}`) },
        { label: "Ver historial del equipo", disabled: !c.device_id, onSelect: () => nav(`/dispositivos/${c.device_id}?tab=historial`) },
        { label: "Abrir aplicación", disabled: !c.product_id, onSelect: () => nav(`/software/${c.product_id}`) },
      ] })}
      page={page} pageSize={50} onPage={(p) => set({ page: p }, false)} storageKey="changes"
      toolbar={<>
        <select aria-label="Tipo de cambio" className="field w-auto" value={values.type ?? ""} onChange={(e) => set({ type: e.target.value || null })}>
          {Object.entries(CHANGE_GROUPS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <input type="date" aria-label="Desde" className="field w-40" value={values.since?.slice(0, 10) ?? ""}
          onChange={(e) => set({ since: e.target.value ? `${e.target.value}T00:00:00` : null })} />
        <Button size="sm" icon={<Download className="size-4" />} onClick={() => api.download("/changes/export", { format: "xlsx", type: values.type, since: values.since })}>Exportar</Button>
      </>} />
  );
}

// ------------------------------------------------------------------ alertas
const TITLE = /^Software no autorizado: (.+) en (.+)$/;
const TYPE_LABEL: Record<string, string> = {
  unauthorized_software: "Software no autorizado", new_software: "Software nuevo sin clasificar", stale_source: "Fuente sin datos recientes",
};
type AlertChip = "open" | "critical" | "warning" | "info" | "resolved";
const CHIP_PARAMS: Record<AlertChip, { status: string; severity?: string }> = {
  open: { status: "open,acknowledged" }, critical: { status: "open,acknowledged", severity: "critical" },
  warning: { status: "open,acknowledged", severity: "warning" }, info: { status: "open,acknowledged", severity: "info" },
  resolved: { status: "resolved" },
};
const sevDot = (a: Alert): DotKind => (a.status === "resolved" ? "success" : a.severity === "critical" ? "critical"
  : a.severity === "warning" ? "warning" : "info");

function Alerts() {
  const can = useCan();
  const nav = useNavigate();
  const dash = useDashboard().data;
  const { values, set } = useUrlState(["chip", "by", "status", "severity"] as const);
  // Compatibilidad con enlaces antiguos (?status=resolved, ?severity=critical).
  const chip = (values.chip ?? (values.status === "resolved" ? "resolved" : values.severity ?? "open")) as AlertChip;
  const byDevice = values.by === "device";
  const params = { ...CHIP_PARAMS[chip], page_size: 500 };
  const q = useQuery({ queryKey: ["alerts", params], queryFn: () => api.get<Paged<Alert>>("/alerts", params), placeholderData: (p) => p });
  const [resolving, setResolving] = useState<Alert[] | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number | string>>(new Set());
  const [notifying, setNotifying] = useState<NotifyScope | null>(null);
  const [uninstalling, setUninstalling] = useState<{ productId: number; deviceIds: number[] } | null>(null);
  const [note, setNote] = useState("");
  const act = useAction(async ({ ids, action, note }: { ids: number[]; action: string; note?: string }) => {
    for (const id of ids) await api.send("POST", `/alerts/${id}`, { action, note });
    return ids.length;
  }, {
    success: (n) => (n === 1 ? "Alerta actualizada" : `${n} alertas actualizadas`), invalidate: [["alerts"], ["alerts-count"], ["dashboard"]],
    onSuccess: () => { setResolving(null); setNote(""); setSelectedIds(new Set()); },
  });
  const items = q.data?.items ?? [];
  const parse = (a: Alert) => {
    const m = TITLE.exec(a.title);
    return { product: m?.[1] ?? null, device: m?.[2] ?? null };
  };
  const groupKey = (a: Alert) => (byDevice
    ? (a.device_id ? `d${a.device_id}` : "none")
    : a.type === "unauthorized_software" && a.product_id ? `p${a.product_id}` : `t${a.type}`);
  const map = new Map<string, Alert[]>();
  items.forEach((a) => map.set(groupKey(a), [...(map.get(groupKey(a)) ?? []), a]));
  const groups: TableGroup<Alert>[] = [...map.entries()].sort((a, b) => b[1].length - a[1].length).map(([key, list]) => {
    const first = list[0];
    const p = parse(first);
    const cause = dash?.alerts.causes?.find((c) => `p${c.product_id}` === key);
    const label = byDevice ? (p.device ?? (first.device_id ? `Equipo #${first.device_id}` : "Sin equipo"))
      : p.product ?? (TYPE_LABEL[first.type] ?? first.type);
    return { key, label, rows: list, lead: <StatusDot kind={sevDot(first)} />,
      summary: cause?.alternative ? `Alternativa: ${cause.alternative}` : `${list.length} ${list.length === 1 ? "alerta" : "alertas"}` };
  });
  const cols: Column<Alert>[] = [
    { id: "title", header: byDevice ? "Incidencia" : "Equipo", cell: (a) => {
      const p = parse(a);
      return (
        <div className="flex min-w-0 items-center gap-3">
          <StatusDot kind={sevDot(a)} />
          <div className="min-w-0 max-w-[36rem] whitespace-normal">
            {!byDevice && a.device_id
              ? <Link to={`/dispositivos/${a.device_id}`} className="font-semibold hover:underline hover:underline-offset-4">{p.device ?? `Equipo #${a.device_id}`}</Link>
              : <p className="font-semibold">{byDevice && p.product ? p.product : TYPE_LABEL[a.type] ?? a.type}</p>}
            <p className="text-xs text-muted">{a.title}</p>
            {a.detail && <p className="line-clamp-1 text-xs text-muted">{a.detail}</p>}
          </div>
        </div>
      );
    } },
    { id: "when", header: "Detectada", cell: (a) => <span className="whitespace-nowrap text-muted" title={`Vista por última vez ${fmtDateTime(a.last_seen_at)}`}>{fmtRelative(a.created_at)}</span> },
    { id: "status", header: "Estado", cell: (a) => (
      <div className="flex flex-col items-start gap-0.5">
        {a.status === "resolved"
          ? <span className="text-xs text-muted" title={a.resolution ?? ""}>Resuelta por {a.resolved_by}</span>
          : a.status === "acknowledged" ? <span className="text-fg-2">En curso</span> : <span className="font-medium text-signal">Abierta</span>}
        {a.last_action && a.status !== "resolved" && (
          <span className={a.last_action.status === "failed" || a.last_action.status === "manual_required" ? "text-2xs text-signal" : "text-2xs text-muted"}
            title={`${a.last_action.by} · ${fmtDateTime(a.last_action.at)}`}>
            {a.last_action.kind === "notify"
              ? (a.last_action.status === "failed" ? "Aviso fallido" : `Avisado ${fmtRelative(a.last_action.at)}`)
              : `Desinstalación: ${REMOTE_STATUS_LABEL[a.last_action.status as keyof typeof REMOTE_STATUS_LABEL]?.toLowerCase() ?? a.last_action.status}`}
          </span>
        )}
      </div>
    ) },
  ];
  const pending = (list: Alert[]) => list.filter((x) => x.status !== "resolved");
  const menu = (a: Alert, sel: Alert[]): MenuEntry[] => {
    const group = groups.find((g) => g.rows.includes(a));
    const out: MenuEntry[] = [];
    if (can.write && a.status !== "resolved") {
      out.push({ label: sel.length > 1 ? `Resolver ${pending(sel).length} alertas…` : "Resolver…", hint: "R", onSelect: () => setResolving(pending(sel)) });
      if (sel.length === 1 && a.status === "open") out.push({ label: "Marcar en curso", onSelect: () => act.mutate({ ids: [a.id], action: "acknowledge" }) });
      if (a.product_id && a.device_id) out.push({ label: "Excepción para este equipo…", onSelect: () => nav(`/software/${a.product_id}?tab=politicas`) });
      const soft = pending(sel).filter((x) => x.type === "unauthorized_software" && x.device_id && x.product_id);
      if (soft.length) {
        out.push("separator",
          { label: soft.length > 1 ? `Avisar a los usuarios (${soft.length} alertas)…` : "Avisar al usuario…",
            onSelect: () => setNotifying({ alert_ids: soft.map((x) => x.id) }) });
        const products = new Set(soft.map((x) => x.product_id));
        if (products.size === 1) {
          out.push({ label: soft.length > 1 ? `Desinstalar de estos ${soft.length} equipos…` : "Desinstalar de este equipo…", danger: true,
            onSelect: () => setUninstalling({ productId: soft[0].product_id!, deviceIds: soft.map((x) => x.device_id!) }) });
        }
      }
      out.push("separator");
    }
    out.push(
      { label: "Abrir equipo", disabled: !a.device_id, onSelect: () => nav(`/dispositivos/${a.device_id}`) },
      { label: "Abrir aplicación", disabled: !a.product_id, onSelect: () => nav(`/software/${a.product_id}`) },
      { label: "Ver historial del equipo", disabled: !a.device_id, onSelect: () => nav(`/dispositivos/${a.device_id}?tab=historial`) },
    );
    if (a.run_id) out.push({ label: `Ver ejecución #${a.run_id}`, onSelect: () => nav(`/sincronizacion?run=${a.run_id}`) });
    if (can.write && group && pending(group.rows).length > 1 && sel.length === 1) {
      const rows = pending(group.rows);
      out.push("separator", { label: `Resolver las ${rows.length} de este grupo…`, onSelect: () => setResolving(rows) });
      const soft = rows.filter((x) => x.type === "unauthorized_software" && x.device_id && x.product_id);
      if (!byDevice && soft.length > 1) {
        out.push({ label: `Avisar a los usuarios de los ${soft.length} equipos…`, onSelect: () => setNotifying({ alert_ids: soft.map((x) => x.id) }) },
          { label: `Desinstalar de los ${soft.length} equipos…`, danger: true,
            onSelect: () => setUninstalling({ productId: soft[0].product_id!, deviceIds: soft.map((x) => x.device_id!) }) });
      }
    }
    return out;
  };
  const counts = dash?.alerts.by_severity ?? {};
  return (
    <>
      <DataTable columns={cols} rows={items} groups={groups} rowKey={(a) => a.id} loading={q.isLoading} error={q.error}
        rowMenu={(a, sel) => ({ title: parse(a).device ?? a.title, entries: menu(a, sel) })}
        selectable={can.write} selected={selectedIds} onSelectedChange={setSelectedIds}
        bulkActions={<Button size="sm" onClick={() => setResolving(pending(items.filter((a) => selectedIds.has(a.id))))}>Resolver</Button>}
        empty={<EmptyState title="Sin alertas" icon={<CheckCircle2 className="size-5 text-ok" />} />}
        footer="Las alertas de software se agrupan por la aplicación que las causa: al retirarla del equipo, la alerta se cierra en la próxima sincronización."
        header={<div className="py-3"><FilterChips label="Estado" value={chip} onChange={(v) => set({ chip: v === "open" ? null : v, status: null, severity: null })} options={[
          { id: "open", label: "Abiertas", count: dash?.alerts.open },
          { id: "critical", label: "Críticas", count: counts.critical ?? 0, dot: "critical" },
          { id: "warning", label: "Avisos", count: counts.warning ?? 0, dot: "warning" },
          { id: "info", label: "Informativas", count: counts.info ?? 0, dot: "info" },
          { id: "resolved", label: "Resueltas", dot: "success" },
        ]} /></div>}
        toolbar={<Segmented label="Agrupar" value={byDevice ? "device" : "cause"} onChange={(v) => set({ by: v === "cause" ? null : "device" })}
          options={[{ id: "cause", label: "Por causa" }, { id: "device", label: "Por equipo" }]} />} />
      {notifying && <NotifyDialog scope={notifying} onClose={() => setNotifying(null)} />}
      {uninstalling && <UninstallDialog productId={uninstalling.productId} deviceIds={uninstalling.deviceIds} onClose={() => setUninstalling(null)} />}
      {resolving && (
        <Modal open onClose={() => setResolving(null)} title={resolving.length === 1 ? "Resolver alerta" : `Resolver ${resolving.length} alertas`} footer={<>
          <Button onClick={() => setResolving(null)}>Cancelar</Button>
          <Button variant="primary" disabled={!note.trim() || resolving.length === 0} loading={act.isPending}
            onClick={() => act.mutate({ ids: resolving.map((a) => a.id), action: "resolve", note })}>Resolver</Button>
        </>}>
          {resolving.length === 1 && <p className="mb-3 font-medium">{resolving[0].title}</p>}
          <Field label="¿Cómo se ha resuelto?" hint="Si la condición persiste, la próxima sincronización volverá a abrir la alerta.">
            {(id) => <textarea id={id} rows={3} className="field" value={note} onChange={(e) => setNote(e.target.value)} />}
          </Field>
        </Modal>
      )}
    </>
  );
}

// ------------------------------------------------------------------ acciones remotas
const ACTION_DOT: Record<string, DotKind> = {
  sent: "running", running: "running", succeeded: "success", failed: "failed", manual_required: "warning", expired: "warning",
};

function RemoteActions() {
  const can = useCan();
  const nav = useNavigate();
  const { values, set, page } = useUrlState(["kind", "rstatus"] as const);
  const params = { kind: values.kind ?? undefined, status: values.rstatus ?? undefined, page, page_size: 50 };
  const q = useQuery({ queryKey: ["remote-actions", params], queryFn: () => api.get<Paged<RemoteAction>>("/remote-actions", params),
    placeholderData: (p) => p,
    refetchInterval: (s) => (s.state.data?.items.some((a) => a.kind === "uninstall" && ["sent", "running"].includes(a.status)) ? 30_000 : false) });
  const retry = useAction((id: number) => api.send("POST", `/remote-actions/${id}/retry`), {
    success: "Desinstalación relanzada", invalidate: [["remote-actions"], ["alerts"]] });
  const cols: Column<RemoteAction>[] = [
    { id: "at", header: "Hora", cell: (a) => <span className="code whitespace-nowrap text-muted" title={fmtDateTime(a.requested_at)}>{hhmm(a.requested_at)}</span> },
    { id: "what", header: "Acción", cell: (a) => (
      <span className="flex items-center gap-2.5">
        <StatusDot kind={ACTION_DOT[a.status] ?? "muted"} />
        <span className="font-semibold">{a.kind === "notify" ? "Aviso por correo" : "Desinstalación"}</span>
      </span>
    ) },
    { id: "target", header: "Equipo · aplicación", cell: (a) => (
      <div className="min-w-0">
        {a.device_id ? <Link to={`/dispositivos/${a.device_id}`} className="font-medium hover:underline">{a.device}</Link> : "—"}
        <p className="text-xs text-muted">{a.product ?? ""}{a.recipient ? ` · ${a.recipient}` : ""}</p>
      </div>
    ) },
    { id: "status", header: "Resultado", cell: (a) => (
      <div className="max-w-[28rem] whitespace-normal">
        <span className={["failed", "manual_required", "expired"].includes(a.status) ? "font-medium text-signal" : "text-fg-2"}>
          {a.kind === "notify" && a.status === "sent" ? "Enviado" : REMOTE_STATUS_LABEL[a.status]}</span>
        {(a.detail.output || a.detail.error) && <p className="line-clamp-2 font-mono text-2xs text-muted" title={a.detail.output ?? a.detail.error}>{a.detail.output ?? a.detail.error}</p>}
      </div>
    ) },
    { id: "by", header: "Pedida por", cell: (a) => <span className="text-muted">{a.requested_by}</span> },
  ];
  return (
    <DataTable columns={cols} rows={q.data?.items} total={q.data?.total} rowKey={(a) => a.id} loading={q.isLoading} error={q.error}
      groups={groupByDay(q.data?.items ?? [], (a) => a.requested_at)}
      page={page} pageSize={50} onPage={(p) => set({ page: p }, false)} storageKey="remote-actions"
      rowMenu={(a) => ({ title: a.kind === "notify" ? "Aviso por correo" : "Desinstalación", entries: [
        ...(can.write && a.kind === "uninstall" && ["failed", "expired", "manual_required"].includes(a.status)
          ? [{ label: "Reintentar", onSelect: () => retry.mutate(a.id) }, "separator" as const] : []),
        { label: "Abrir equipo", disabled: !a.device_id, onSelect: () => nav(`/dispositivos/${a.device_id}`) },
        { label: "Abrir aplicación", disabled: !a.product_id, onSelect: () => nav(`/software/${a.product_id}`) },
        { label: "Copiar el resultado", disabled: !(a.detail.output || a.detail.error),
          onSelect: () => navigator.clipboard?.writeText(a.detail.output ?? a.detail.error ?? "") },
      ] })}
      empty={<EmptyState title="Aún no se ha avisado ni desinstalado nada desde el inventario">
        Se lanzan con el clic derecho sobre una alerta, una aplicación no autorizada o un equipo.</EmptyState>}
      footer="Las desinstalaciones las ejecuta Intune cuando el equipo está conectado; el resultado se actualiza solo. Si sale bien, la alerta se cierra en la próxima sincronización."
      header={<div className="flex flex-wrap items-center gap-3 py-3">
        <FilterChips label="Tipo" value={values.kind ?? "all"} onChange={(v) => set({ kind: v === "all" ? null : v })} options={[
          { id: "all", label: "Todas" }, { id: "notify", label: "Avisos" }, { id: "uninstall", label: "Desinstalaciones" },
        ]} />
        <FilterChips label="Resultado" value={values.rstatus ?? "all"} onChange={(v) => set({ rstatus: v === "all" ? null : v })} options={[
          { id: "all", label: "Cualquier resultado" }, { id: "sent,running", label: "En curso", dot: "running" },
          { id: "succeeded", label: "Hechas", dot: "success" }, { id: "failed,manual_required,expired", label: "Requieren atención", dot: "failed" },
        ]} />
      </div>} />
  );
}

// ------------------------------------------------------------------ casos de revisión
interface Case { id: number; type: string; summary: string; data: Record<string, unknown>; created_at: string; run_id: number | null }

function ReviewCases() {
  const can = useCan();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["review-cases"], queryFn: () => api.get<Case[]>("/review-cases") });
  const [open, setOpen] = useState<Case | null>(null);
  const [form, setForm] = useState({ action: "dismiss", note: "", keep: "", merge: "" });
  const resolve = useAction(() => api.send("POST", `/review-cases/${open!.id}`, { action: form.action, note: form.note,
    keep_device_id: form.keep ? Number(form.keep) : null, merge_device_id: form.merge ? Number(form.merge) : null }), {
    success: "Caso resuelto", invalidate: [["review-cases"], ["devices"], ["dashboard"]], onSuccess: () => setOpen(null),
  });
  const ids = (c: Case) => [c.data.existing_device_id, ...(Array.isArray(c.data.device_ids) ? c.data.device_ids : [])].filter(Boolean) as number[];
  return (
    <>
      <div className="mb-3"><Notice>Cuando la conciliación no tiene información suficiente para decidir si dos registros son el mismo equipo, no fusiona nada y abre un caso aquí.</Notice></div>
      <DataTable rows={q.data} rowKey={(c) => c.id} loading={q.isLoading} error={q.error}
        rowMenu={(c) => ({ title: c.summary, entries: [
          ...(can.write ? [{ label: "Resolver…", onSelect: () => { setOpen(c); setForm({ action: "dismiss", note: "", keep: String(ids(c)[0] ?? ""), merge: String(ids(c)[1] ?? "") }); } }, "separator" as const] : []),
          ...ids(c).map((i) => ({ label: `Abrir equipo #${i}`, onSelect: () => nav(`/dispositivos/${i}`) })),
        ] })}
        empty={<EmptyState title="No hay casos pendientes" icon={<CheckCircle2 className="size-5 text-ok" />} />}
        columns={[
          { id: "s", header: "Caso", cell: (c) => <span className="font-medium">{c.summary}</span> },
          { id: "d", header: "Dispositivos", cell: (c) => <div className="flex gap-2">{ids(c).map((i) => <Link key={i} className="link" to={`/dispositivos/${i}`}>#{i}</Link>)}</div> },
          { id: "w", header: "Detectado", cell: (c) => <span className="text-muted">{fmtRelative(c.created_at)}</span> },
          { id: "a", header: "", cell: (c) => can.write && <Button size="sm" onClick={() => { setOpen(c); setForm({ action: "dismiss", note: "", keep: String(ids(c)[0] ?? ""), merge: String(ids(c)[1] ?? "") }); }}>Resolver</Button> },
        ]} />
      {open && (
        <Modal open onClose={() => setOpen(null)} title="Resolver caso de conciliación" footer={<>
          <Button onClick={() => setOpen(null)}>Cancelar</Button>
          <Button variant={form.action === "merge_devices" ? "danger" : "primary"} disabled={form.note.trim().length < 3} loading={resolve.isPending}
            onClick={() => resolve.mutate(undefined)}>{form.action === "merge_devices" ? "Fusionar" : "Descartar"}</Button>
        </>}>
          <div className="space-y-4">
            <p>{open.summary}</p>
            <pre className="max-h-40 overflow-auto rounded-md bg-subtle p-3 font-mono text-2xs">{JSON.stringify(open.data, null, 2)}</pre>
            <Field label="Decisión">{(id) => <select id={id} className="field" value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })}>
              <option value="dismiss">Son equipos distintos (descartar)</option><option value="merge_devices">Son el mismo equipo (fusionar)</option></select>}</Field>
            {form.action === "merge_devices" && <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Conservar dispositivo #">{(id) => <input id={id} className="field" value={form.keep} onChange={(e) => setForm({ ...form, keep: e.target.value })} />}</Field>
              <Field label="Fusionar y retirar #">{(id) => <input id={id} className="field" value={form.merge} onChange={(e) => setForm({ ...form, merge: e.target.value })} />}</Field>
            </div>}
            <Field label="Justificación">{(id) => <input id={id} className="field" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />}</Field>
          </div>
        </Modal>
      )}
    </>
  );
}

// ------------------------------------------------------------------ registro
interface Event { id: number; at: string; actor: string; action: string; entity_type: string; entity_id: string | null; summary: string | null; hash: string }

function AuditLog() {
  const { values, set, page } = useUrlState(["actor", "entity_type"] as const);
  const params = { actor: values.actor, entity_type: values.entity_type, page, page_size: 50 };
  const q = useQuery({ queryKey: ["audit", params], queryFn: () => api.get<Paged<Event>>("/audit", params), placeholderData: (p) => p });
  const verify = useQuery({ queryKey: ["audit-verify"], queryFn: () => api.get<{ valid: boolean; checked: number; broken_event_id: number | null }>("/audit/verify"), enabled: false });
  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Button icon={<ShieldCheck className="size-4" />} loading={verify.isFetching} onClick={() => verify.refetch()}>Verificar integridad</Button>
        {verify.data && (verify.data.valid
          ? <Badge tone="ok">Cadena íntegra · {verify.data.checked} eventos verificados</Badge>
          : <Badge tone="danger">Manipulación detectada en el evento #{verify.data.broken_event_id}</Badge>)}
        <Button className="ml-auto" icon={<Download className="size-4" />} onClick={() => api.download("/audit/export", { format: "xlsx" })}>Exportar evidencias</Button>
      </div>
      <DataTable rows={q.data?.items} total={q.data?.total} rowKey={(e) => e.id} loading={q.isLoading} error={q.error}
        groups={groupByDay(q.data?.items ?? [], (e) => e.at)}
        rowMenu={(e) => ({ entries: [
          { label: `Ver solo las acciones de ${e.actor}`, onSelect: () => set({ actor: e.actor }) },
          { label: "Copiar hash", onSelect: () => navigator.clipboard?.writeText(e.hash) },
        ] })}
        page={page} pageSize={50} onPage={(p) => set({ page: p }, false)} search={values.actor ?? ""} onSearch={(s) => set({ actor: s })}
        searchPlaceholder="Filtrar por actor…" storageKey="audit"
        toolbar={<select aria-label="Entidad" className="field w-auto" value={values.entity_type ?? ""} onChange={(e) => set({ entity_type: e.target.value || null })}>
          <option value="">Todas las entidades</option>
          {["device", "department", "software_product", "software_policy", "inventory_run", "inventory_snapshot", "alert", "review_case", "app_setting", "inventory_source", "user"].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>}
        columns={[
          { id: "at", header: "Hora", cell: (e) => <span className="code whitespace-nowrap text-muted" title={fmtDateTime(e.at)}>{hhmm(e.at)}</span> },
          { id: "actor", header: "Actor", cell: (e) => e.actor },
          { id: "action", header: "Acción", cell: (e) => <span className="font-mono text-xs">{e.action}</span> },
          { id: "summary", header: "Resumen", cell: (e) => e.summary ?? "—" },
          { id: "hash", header: "Hash", hidden: true, cell: (e) => <span className="font-mono text-2xs" title={e.hash}>{e.hash.slice(0, 12)}…</span> },
        ]} />
    </>
  );
}
