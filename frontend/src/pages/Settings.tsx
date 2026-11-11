import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Badge, Button, Card, DefinitionList, ErrorState, Field, Notice, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth, useCan } from "@/lib/auth";
import { ROLE_LABEL, fmtRelative } from "@/lib/format";
import { useAction } from "@/lib/hooks";
import type { Source } from "@/lib/types";
import { Avatar } from "@/components/Avatar";

interface SettingsData {
  "schedule.monthly": { enabled: boolean; day: number; hour: number; sources: string[] };
  "alerts.stale_source_days": number;
  "worker.heartbeat": { at: string } | null;
  runtime: { environment: string; auth_mode: string; graph_configured: boolean; stale_device_days: number };
}

export default function SettingsPage() {
  const can = useCan();
  const { me, config } = useAuth();
  const q = useQuery({ queryKey: ["settings"], queryFn: () => api.get<SettingsData>("/settings") });
  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api.get<Source[]>("/sources") });
  const users = useQuery({ queryKey: ["users", "app"], queryFn: () => api.get<{ id: number; upn: string; display_name: string | null; role: string; last_login_at: string | null }[]>("/users", { app_only: true }) });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorState error={q.error} retry={q.refetch} />;
  const s = q.data;
  const rt = s.runtime;

  return (
    <>
      <PageHeader eyebrow="Sistema · Configuración" title="Configuración" description="Automatizaciones, conectores, accesos y estado del sistema." />
      {!can.admin && <div className="mb-4"><Notice>Solo los administradores pueden modificar la configuración.</Notice></div>}
      <div className="grid gap-4 lg:grid-cols-2">
        <Schedule data={s["schedule.monthly"]} sources={(sources.data ?? []).filter((x) => x.kind === "api")} disabled={!can.admin} />
        <Card title="Estado del sistema">
          <DefinitionList items={[
            ["Entorno", rt.environment], ["Versión", config.version],
            ["Autenticación", rt.auth_mode === "entra" ? "Microsoft Entra ID" : <Badge key="a" tone="warn">Modo desarrollo</Badge>],
            ["Credenciales de Graph", rt.graph_configured ? <Badge key="g" tone="ok">Configuradas</Badge> : <Badge key="g" tone="warn">Pendientes</Badge>],
            ["Worker", s["worker.heartbeat"] ? `Activo ${fmtRelative(s["worker.heartbeat"].at)}` : <Badge key="w" tone="danger">Sin actividad</Badge>],
            ["Dispositivo «no observado» tras", `${rt.stale_device_days} días`],
            ["Alerta de fuente sin sincronizar tras", `${s["alerts.stale_source_days"]} días`],
          ]} />
          <p className="mt-4 text-xs text-muted">Las credenciales y secretos se configuran en variables de entorno del servidor, nunca desde la aplicación (Vercel y GitHub; ver docs/despliegue-nube.md).</p>
        </Card>
        {(sources.data ?? []).filter((x) => x.code === "intune").map((src) => <IntuneConfig key={src.code} src={src} disabled={!can.admin} />)}
        <NotifySettings disabled={!can.admin} canTest={can.write} me={me.upn} />
        <Card title="Usuarios y permisos" actions={can.write && <RefreshPhotos />}>
          <p className="mb-3 text-muted">
            Los roles se asignan en Microsoft Entra ID (roles de aplicación) a usuarios o grupos; la aplicación no gestiona contraseñas.
            Su sesión: <strong className="text-fg">{me.upn}</strong> · {ROLE_LABEL[me.role]}.
          </p>
          <ul className="divide-y divide-border">
            {(users.data ?? []).map((u) => (
              <li key={u.id} className="flex items-center gap-2 py-2">
                <Avatar upn={u.upn} name={u.display_name ?? u.upn} />
                <span className="min-w-0 flex-1 truncate">{u.display_name ?? u.upn}<span className="block text-xs text-muted">{u.upn}</span></span>
                <Badge tone={u.role === "admin" ? "accent" : "neutral"}>{ROLE_LABEL[u.role] ?? u.role}</Badge>
                <span className="w-28 text-right text-xs text-muted">{fmtRelative(u.last_login_at)}</span>
              </li>
            ))}
            {users.data?.length === 0 && <li className="py-3 text-muted">Ningún usuario ha iniciado sesión todavía.</li>}
          </ul>
        </Card>
      </div>
    </>
  );
}

function Schedule({ data, sources, disabled }: { data: SettingsData["schedule.monthly"]; sources: Source[]; disabled: boolean }) {
  const [v, setV] = useState(data);
  useEffect(() => setV(data), [data]);
  const save = useAction(() => api.send("PUT", "/settings/schedule", v), { success: "Programación guardada", invalidate: [["settings"]] });
  return (
    <Card title="Inventario mensual automático">
      <div className="space-y-4">
        <label className="flex items-center gap-2"><input type="checkbox" disabled={disabled} checked={v.enabled} onChange={(e) => setV({ ...v, enabled: e.target.checked })} />
          Ejecutar automáticamente cada mes</label>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Día del mes">{(id) => <input id={id} type="number" min={1} max={28} disabled={disabled} className="field" value={v.day} onChange={(e) => setV({ ...v, day: Number(e.target.value) })} />}</Field>
          <Field label="Hora (UTC)">{(id) => <input id={id} type="number" min={0} max={23} disabled={disabled} className="field" value={v.hour} onChange={(e) => setV({ ...v, hour: Number(e.target.value) })} />}</Field>
        </div>
        <fieldset><legend className="label">Fuentes a sincronizar</legend>
          {sources.map((s) => <label key={s.code} className="flex items-center gap-2 py-0.5"><input type="checkbox" disabled={disabled}
            checked={v.sources.includes(s.code)} onChange={(e) => setV({ ...v, sources: e.target.checked ? [...v.sources, s.code] : v.sources.filter((x) => x !== s.code) })} />{s.name}</label>)}
        </fieldset>
        <p className="text-xs text-muted">Tras las sincronizaciones se genera el borrador del inventario del mes, que IT revisa y aprueba en Auditoría.</p>
        {!disabled && <Button variant="primary" loading={save.isPending} disabled={v.day < 1 || v.day > 28 || v.hour < 0 || v.hour > 23} onClick={() => save.mutate(undefined)}>Guardar</Button>}
      </div>
    </Card>
  );
}

function RefreshPhotos() {
  const run = useAction(() => api.send<{ updated: number; found: number }>("POST", "/users/photos/refresh"), {
    success: (r) => `${r.found} fotos de perfil actualizadas`, invalidate: [["user-photos"]] });
  return <Button size="sm" loading={run.isPending} onClick={() => run.mutate(undefined)}
    title="Descarga las fotos de perfil de Microsoft 365 (requiere el permiso de fotos)">Actualizar fotos</Button>;
}

interface NotifyData { sender: string; cc: string; template: { subject: string; body: string } }

function NotifySettings({ disabled, canTest, me }: { disabled: boolean; canTest: boolean; me: string }) {
  const q = useQuery({ queryKey: ["settings", "notify"], queryFn: () => api.get<NotifyData>("/settings/notify") });
  const [v, setV] = useState<{ sender: string; cc: string; subject: string; body: string } | null>(null);
  useEffect(() => { if (q.data) setV({ sender: q.data.sender, cc: q.data.cc, ...q.data.template }); }, [q.data]);
  const save = useAction(() => api.send("PUT", "/settings/notify", v), { success: "Avisos guardados", invalidate: [["settings"]] });
  const test = useAction(() => api.send<{ sent_to: string }>("POST", "/notifications/test"), { success: (r) => `Correo de prueba enviado a ${r.sent_to}` });
  if (!v) return <Card title="Avisos por correo"><Spinner /></Card>;
  const validSender = !v.sender || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.sender);
  return (
    <Card title="Avisos por correo">
      <div className="space-y-4">
        <p className="text-muted">Correo al usuario de un equipo con software no autorizado. Se envía solo cuando un técnico lo pide, desde una alerta, una aplicación o un equipo.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Buzón remitente" hint="Buzón compartido; la cuenta conectada necesita «Enviar como» en Exchange." error={validSender ? null : "Formato usuario@dominio"}>
            {(id) => <input id={id} type="email" className="field" disabled={disabled} placeholder="it@asserta.es" value={v.sender} onChange={(e) => setV({ ...v, sender: e.target.value })} />}
          </Field>
          <Field label="Copia a (opcional)" hint="Varias direcciones separadas por comas">
            {(id) => <input id={id} className="field" disabled={disabled} value={v.cc} onChange={(e) => setV({ ...v, cc: e.target.value })} />}
          </Field>
        </div>
        <Field label="Asunto" hint="Campos: {nombre}, {equipo}, {programas}, {fecha}">
          {(id) => <input id={id} className="field" disabled={disabled} value={v.subject} onChange={(e) => setV({ ...v, subject: e.target.value })} />}
        </Field>
        <Field label="Texto">
          {(id) => <textarea id={id} rows={9} className="field font-mono text-xs" disabled={disabled} value={v.body} onChange={(e) => setV({ ...v, body: e.target.value })} />}
        </Field>
        <div className="flex flex-wrap gap-2">
          {!disabled && <Button variant="primary" loading={save.isPending} disabled={!validSender || v.subject.trim().length < 3 || v.body.trim().length < 10}
            onClick={() => save.mutate(undefined)}>Guardar</Button>}
          {canTest && <Button loading={test.isPending} disabled={!q.data?.sender} onClick={() => test.mutate(undefined)}
            title={q.data?.sender ? undefined : "Guarde primero el buzón remitente"}>Enviar prueba a {me}</Button>}
        </div>
      </div>
    </Card>
  );
}

function IntuneConfig({ src, disabled }: { src: Source; disabled: boolean }) {
  const [strategy, setStrategy] = useState(String(src.config.software_strategy ?? "per_device"));
  const [enabled, setEnabled] = useState(src.enabled);
  const save = useAction(() => api.send("PATCH", `/sources/${src.code}`, { enabled, config: { software_strategy: strategy } }),
    { success: "Conector actualizado", invalidate: [["sources"]] });
  return (
    <Card title="Conector Microsoft Intune">
      <div className="space-y-4">
        <label className="flex items-center gap-2"><input type="checkbox" disabled={disabled} checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />Conector activo</label>
        <Field label="Lectura de software (Discovered apps)" hint="«Por aplicación» es la técnica del script PowerShell actual. «Por dispositivo» hace menos llamadas; valídela con el tenant antes de usarla.">
          {(id) => <select id={id} className="field" disabled={disabled} value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            <option value="per_app">Por aplicación (lento: una llamada por programa)</option>
            <option value="per_device">Por dispositivo (rápido, recomendado)</option>
          </select>}
        </Field>
        <p className="text-xs text-muted">Permiso de aplicación necesario: DeviceManagementManagedDevices.Read.All (solo lectura).</p>
        {!disabled && <Button variant="primary" loading={save.isPending} onClick={() => save.mutate(undefined)}>Guardar</Button>}
      </div>
    </Card>
  );
}
