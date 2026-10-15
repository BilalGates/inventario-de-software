import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, CircleDashed, XCircle } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { RunStatusBadge, SeverityBadge, SnapshotBadge } from "@/components/badges";
import { Card, EmptyState, ErrorState, Notice, PageHeader, Spinner, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { CHANGE_LABEL, TRIGGER_LABEL, fmtNumber, fmtPeriod, fmtRelative } from "@/lib/format";
import type { Alert, Change, Coverage, Run, Snapshot } from "@/lib/types";

interface DashboardData {
  generated_at: string;
  devices: { total: number; current: number; stale: number; never_synced: number; unassigned: number;
    compliance: Record<string, number> };
  software: { products: number; installations: number; pending: number; unauthorized_products: number;
    by_status: Record<string, number> };
  alerts: { open: number; by_severity: Record<string, number>; top: Alert[] };
  monthly: { period: string; snapshot: Snapshot | null; coverage: Coverage };
  runs: Run[];
  changes: Change[];
  changes_30d: Record<string, number>;
  departments: { name: string; devices: number }[];
  worker_heartbeat: { at: string } | null;
  open_review_cases: number;
}

function Bar({ label, value, max }: { label: string; value: number; max: number }) {
  return (
    <div className="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-3 text-sm">
      <span className="truncate text-muted" title={label}>{label}</span>
      <div className="h-1.5 overflow-hidden rounded-full bg-subtle" aria-hidden>
        <div className="h-full rounded-full bg-accent/70" style={{ width: `${max ? (value / max) * 100 : 0}%` }} />
      </div>
      <span className="num text-right">{value}</span>
    </div>
  );
}

function MonthlyStatus({ m }: { m: DashboardData["monthly"] }) {
  const sources = Object.entries(m.coverage.sources).filter(([, s]) => s.essential);
  return (
    <Card title={`Inventario de ${fmtPeriod(m.period)}`}
      actions={<Link to="/auditoria?tab=mensual" className="text-xs text-accent hover:underline">Gestionar</Link>}>
      <div className="flex items-center gap-3">
        {m.snapshot ? <SnapshotBadge status={m.snapshot.status} /> : <span className="text-muted">Sin generar</span>}
        {m.coverage.complete
          ? <span className="text-xs text-ok">Recogida completa</span>
          : <span className="text-xs text-warn">Recogida incompleta</span>}
      </div>
      <ul className="mt-3 space-y-1.5">
        {sources.length === 0 && <li className="text-muted">No hay fuentes automáticas activas.</li>}
        {sources.map(([code, s]) => (
          <li key={code} className="flex items-center gap-2">
            {s.ok ? <CheckCircle2 className="size-4 text-ok" aria-hidden />
              : s.runs ? <XCircle className="size-4 text-danger" aria-hidden />
              : <CircleDashed className="size-4 text-muted" aria-hidden />}
            <span>{s.name}</span>
            <span className="ml-auto text-xs text-muted">
              {s.ok ? "completa" : s.runs ? "con errores" : "sin ejecutar este mes"}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function Dashboard() {
  const nav = useNavigate();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get<DashboardData>("/dashboard"),
    refetchInterval: 60_000,
  });
  if (isLoading) return <Spinner />;
  if (error || !data) return <ErrorState error={error} retry={refetch} />;
  const d = data.devices;
  const maxDept = Math.max(1, ...data.departments.map((x) => x.devices));
  const workerAge = data.worker_heartbeat ? Date.now() - new Date(`${data.worker_heartbeat.at}Z`).getTime() : null;

  return (
    <>
      <PageHeader title="Panel" description={`Estado del parque tecnológico · actualizado ${fmtRelative(data.generated_at)}`} />
      {(workerAge === null || workerAge > 10 * 60_000) && (
        <div className="mb-4">
          <Notice tone="warn" title="El proceso de sincronización no está activo">
            Las sincronizaciones y la programación mensual necesitan el worker en ejecución
            ({workerAge === null ? "nunca se ha ejecutado" : `último latido ${fmtRelative(data.worker_heartbeat!.at)}`}).
          </Notice>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Dispositivos" value={fmtNumber(d.total)} hint={`${d.unassigned} sin departamento`}
          onClick={() => nav("/dispositivos")} />
        <Stat label="Sincronizados" value={fmtNumber(d.current)} tone="ok"
          hint={d.total ? `${Math.round((d.current / d.total) * 100)}% del parque` : undefined}
          onClick={() => nav("/dispositivos?freshness=current")} />
        <Stat label="Sin observar" value={fmtNumber(d.stale)} tone={d.stale ? "warn" : undefined}
          hint={`${d.never_synced} sin fuente automática`} onClick={() => nav("/dispositivos?freshness=stale")} />
        <Stat label="Aplicaciones" value={fmtNumber(data.software.products)}
          hint={`${fmtNumber(data.software.installations)} instalaciones`} onClick={() => nav("/software")} />
        <Stat label="Pendientes de clasificar" value={fmtNumber(data.software.pending)}
          tone={data.software.pending ? "warn" : undefined}
          onClick={() => nav("/software?status=unclassified,pending_review")} />
        <Stat label="Alertas abiertas" value={fmtNumber(data.alerts.open)}
          tone={data.alerts.by_severity.critical ? "danger" : data.alerts.open ? "warn" : undefined}
          hint={data.alerts.by_severity.critical ? `${data.alerts.by_severity.critical} críticas` : undefined}
          onClick={() => nav("/auditoria?tab=alertas")} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Incidencias que requieren atención" className="lg:col-span-2" padded={false}
          actions={<Link to="/auditoria?tab=alertas" className="text-xs text-accent hover:underline">Ver todas</Link>}>
          {data.alerts.top.length === 0 ? (
            <EmptyState title="Sin incidencias abiertas" icon={<CheckCircle2 className="size-5 text-ok" />} />
          ) : (
            <ul className="divide-y divide-border">
              {data.alerts.top.map((a) => (
                <li key={a.id} className="flex items-center gap-3 px-4 py-2.5">
                  <SeverityBadge severity={a.severity} />
                  <span className="min-w-0 flex-1 truncate">{a.title}</span>
                  <span className="whitespace-nowrap text-xs text-muted">{fmtRelative(a.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
          {data.open_review_cases > 0 && (
            <Link to="/auditoria?tab=revision" className="flex items-center gap-2 border-t border-border px-4 py-2.5 text-sm text-warn hover:bg-subtle">
              {data.open_review_cases} casos de conciliación pendientes de revisión <ArrowRight className="size-4" />
            </Link>
          )}
        </Card>
        <MonthlyStatus m={data.monthly} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Últimas sincronizaciones" padded={false}
          actions={<Link to="/sincronizacion" className="text-xs text-accent hover:underline">Historial</Link>}>
          {data.runs.length === 0 ? <EmptyState title="Aún no hay ejecuciones" /> : (
            <ul className="divide-y divide-border">
              {data.runs.map((r) => (
                <li key={r.id} className="flex items-center gap-2 px-4 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate">{r.source_name}</p>
                    <p className="text-xs text-muted">{TRIGGER_LABEL[r.trigger] ?? r.trigger} · {fmtRelative(r.requested_at)}</p>
                  </div>
                  <RunStatusBadge status={r.status} />
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Cambios recientes" padded={false}
          actions={<Link to="/auditoria?tab=cambios" className="text-xs text-accent hover:underline">Ver todos</Link>}>
          {data.changes.length === 0 ? <EmptyState title="Sin cambios registrados" /> : (
            <ul className="divide-y divide-border">
              {data.changes.map((c) => (
                <li key={c.id} className="px-4 py-2.5">
                  <p className="truncate">
                    {CHANGE_LABEL[c.type] ?? c.type}
                    {c.product && <span className="text-muted"> · {c.product}</span>}
                  </p>
                  <p className="truncate text-xs text-muted">
                    {c.device ? <Link className="hover:underline" to={`/dispositivos/${c.device_id}`}>{c.device}</Link> : "—"}
                    {" · "}{fmtRelative(c.at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Dispositivos por departamento"
          actions={<Link to="/departamentos" className="text-xs text-accent hover:underline">Departamentos</Link>}>
          <div className="space-y-2.5">
            {data.departments.length === 0 && <p className="text-muted">Ningún dispositivo asignado todavía.</p>}
            {data.departments.map((x) => <Bar key={x.name} label={x.name} value={x.devices} max={maxDept} />)}
            {d.unassigned > 0 && <Bar label="Sin departamento" value={d.unassigned} max={maxDept} />}
          </div>
        </Card>
      </div>
    </>
  );
}
