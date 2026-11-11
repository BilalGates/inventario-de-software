/** Diálogos para avisar al usuario por correo y desinstalar software no autorizado con Intune. */
import { useQuery } from "@tanstack/react-query";
import { Mail, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type { NotifyPreview, NotifyScope, UninstallPreview } from "@/lib/actions";
import { useAction } from "@/lib/hooks";
import { StatusDot } from "./kit";
import { Button, ErrorState, Field, Modal, Notice, Spinner } from "./ui";

const INVALIDATE = [["alerts"], ["remote-actions"], ["dashboard"], ["alerts-count"]];

// ------------------------------------------------------------------ Avisar al usuario
export function NotifyDialog({ scope, onClose }: { scope: NotifyScope; onClose: () => void }) {
  const q = useQuery({ queryKey: ["notify-preview", scope], queryFn: () => api.send<NotifyPreview>("POST", "/notifications/preview", scope),
    staleTime: 0, gcTime: 0 });
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (q.data) { setSubject(q.data.template.subject); setBody(q.data.template.body); }
  }, [q.data]);
  const send = useAction(() => api.send<{ sent: number; failed: number }>("POST", "/notifications/send", { ...scope, subject, body }), {
    success: (r) => (r.failed ? `${r.sent} enviados · ${r.failed} fallidos` : `${r.sent} ${r.sent === 1 ? "aviso enviado" : "avisos enviados"}`),
    invalidate: INVALIDATE, onSuccess: onClose,
  });
  const d = q.data;
  const n = d?.recipients.length ?? 0;
  const sample = d?.recipients[shown];
  return (
    <Modal open onClose={onClose} wide title="Avisar al usuario por correo" footer={<>
      <Button onClick={onClose}>Cancelar</Button>
      <Button variant="primary" icon={<Mail className="size-4" />} loading={send.isPending}
        disabled={!d || n === 0 || !d.sender || subject.trim().length < 3 || body.trim().length < 10}
        onClick={() => send.mutate(undefined)}>{n === 1 ? "Enviar 1 correo" : `Enviar ${n} correos`}</Button>
    </>}>
      {q.isLoading ? <Spinner /> : q.error || !d ? <ErrorState error={q.error} /> : (
        <div className="space-y-4">
          {!d.sender && (
            <Notice tone="warn" title="Falta el buzón remitente">
              Indique en <Link className="link" to="/configuracion">Configuración</Link> desde qué buzón compartido se envían los avisos.
            </Notice>
          )}
          {n === 0 ? <Notice>No hay a quién avisar: ninguno de estos equipos tiene un usuario asignado con alertas abiertas.</Notice> : (
            <div>
              <p className="eyebrow mb-2">{n === 1 ? "1 destinatario" : `${n} destinatarios`} · un correo por persona con todos sus programas</p>
              <ul className="max-h-40 divide-y divide-border overflow-y-auto rounded-md border border-border">
                {d.recipients.map((r, i) => (
                  <li key={r.upn}>
                    <button type="button" onClick={() => setShown(i)}
                      className={`flex w-full items-start gap-3 px-3 py-2 text-left text-[13px] hover:bg-subtle ${i === shown ? "bg-subtle" : ""}`}>
                      <StatusDot kind="alert" size="sm" className="mt-1" />
                      <span className="min-w-0 flex-1"><b>{r.name}</b> <span className="text-muted">· {r.upn}</span>
                        <span className="block truncate text-xs text-muted">{r.devices.join(", ")} · {r.programs.join(", ")}</span></span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {d.no_user.length > 0 && (
            <p className="text-xs text-muted"><b className="text-signal">Sin destinatario:</b> {d.no_user.join(", ")} no {d.no_user.length === 1 ? "tiene" : "tienen"} usuario asignado; no se avisará.</p>
          )}
          {n > 0 && <>
            <Field label="Asunto" hint="Campos: {nombre}, {equipo}, {programas}, {fecha}">
              {(id) => <input id={id} className="field" value={subject} onChange={(e) => setSubject(e.target.value)} />}
            </Field>
            <Field label="Texto">
              {(id) => <textarea id={id} rows={8} className="field font-mono text-xs" value={body} onChange={(e) => setBody(e.target.value)} />}
            </Field>
            {sample && (
              <div className="rounded-md border border-border bg-subtle p-3">
                <p className="eyebrow mb-1.5">Así lo recibirá {sample.name} (con la plantilla guardada)</p>
                <p className="mb-2 text-[13px] font-semibold">{sample.subject}</p>
                <p className="whitespace-pre-line text-[13px] text-fg-2">{sample.body}</p>
              </div>
            )}
            <p className="text-xs text-muted">Remitente: {d.sender ?? "—"}{d.cc ? ` · copia a ${d.cc}` : ""}. Queda registrado en Auditoría › Acciones remotas.</p>
          </>}
        </div>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ Desinstalar con Intune
export function UninstallDialog({ productId, deviceIds, onClose }: { productId: number; deviceIds?: number[]; onClose: () => void }) {
  const q = useQuery({ queryKey: ["uninstall-preview", productId, deviceIds],
    queryFn: () => api.send<UninstallPreview>("POST", "/uninstalls/preview", { product_id: productId, device_ids: deviceIds }),
    staleTime: 0, gcTime: 0 });
  const [step, setStep] = useState<1 | 2>(1);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [notifyFirst, setNotifyFirst] = useState(true);
  const [reason, setReason] = useState("");
  useEffect(() => { if (q.data) setPicked(new Set(q.data.devices.map((d) => d.id))); }, [q.data]);
  const run = useAction(() => api.send<{ launched: number; failed: number; notified: { sent: number } | null }>("POST", "/uninstalls",
    { product_id: productId, device_ids: [...picked], reason, notify_first: notifyFirst }), {
    success: (r) => `Desinstalación lanzada en ${r.launched} ${r.launched === 1 ? "equipo" : "equipos"}${r.failed ? ` · ${r.failed} no se pudieron lanzar` : ""}${r.notified ? ` · ${r.notified.sent} avisos` : ""}. Sigue el resultado en Auditoría › Acciones remotas.`,
    invalidate: INVALIDATE, onSuccess: onClose,
  });
  const d = q.data;
  const n = picked.size;
  const toggle = (id: number) => setPicked((s) => { const x = new Set(s); if (x.has(id)) x.delete(id); else x.add(id); return x; });
  return (
    <Modal open onClose={onClose} wide title={d ? `Desinstalar ${d.product.name}` : "Desinstalar"} footer={step === 1 ? <>
      <Button onClick={onClose}>Cancelar</Button>
      <Button variant="primary" disabled={!d || !!d.blocked || n === 0 || !d.connected} onClick={() => setStep(2)}>Continuar</Button>
    </> : <>
      <Button onClick={() => setStep(1)}>Atrás</Button>
      <Button variant="danger" icon={<Trash2 className="size-4" />} loading={run.isPending} disabled={reason.trim().length < 3}
        onClick={() => run.mutate(undefined)}>{n === 1 ? "Desinstalar de 1 equipo" : `Desinstalar de ${n} equipos`}</Button>
    </>}>
      {q.isLoading ? <Spinner /> : q.error || !d ? <ErrorState error={q.error} /> : d.blocked ? (
        <Notice tone="warn" title="No se puede desinstalar desde el inventario">{d.blocked}</Notice>
      ) : step === 1 ? (
        <div className="space-y-4">
          <p className="text-[13px] text-muted">
            Simulación: todavía no se ha hecho nada. Intune ejecutará en cada equipo un script que busca <b className="text-fg">{d.names?.join(", ")}</b> y
            lo desinstala en silencio ({d.method}). Si el programa no tiene desinstalación silenciosa, no se toca y se indicará «manual».
          </p>
          {!d.connected && <Notice tone="warn">No hay conexión con Microsoft: conéctese desde Sincronización antes de lanzar la desinstalación.</Notice>}
          <div>
            <p className="eyebrow mb-2">Equipos ({n} de {d.devices.length} seleccionados)</p>
            {d.devices.length === 0 ? <p className="text-[13px] text-muted">Ningún equipo con este programa admite desinstalación remota.</p> : (
              <ul className="max-h-52 divide-y divide-border overflow-y-auto rounded-md border border-border">
                {d.devices.map((x) => (
                  <li key={x.id}>
                    <label className="flex cursor-pointer items-center gap-3 px-3 py-2 text-[13px] hover:bg-subtle">
                      <input type="checkbox" checked={picked.has(x.id)} onChange={() => toggle(x.id)} />
                      <span className="flex-1 font-medium">{x.name}</span>
                      <span className="text-xs text-muted">{x.user ?? "sin usuario"}</span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {d.skipped.length > 0 && (
            <p className="text-xs text-muted"><b>No admiten desinstalación remota:</b> {d.skipped.map((s) => `${s.name} (${s.reason.toLowerCase()})`).join(", ")}</p>
          )}
          <label className="flex items-start gap-2.5 text-[13px]">
            <input type="checkbox" className="mt-0.5" checked={notifyFirst} onChange={(e) => setNotifyFirst(e.target.checked)} />
            <span>Avisar antes al usuario por correo{d.recipients !== undefined && <span className="text-muted"> · {d.recipients} {d.recipients === 1 ? "destinatario" : "destinatarios"}{d.no_user?.length ? `, ${d.no_user.length} sin usuario` : ""}</span>}</span>
          </label>
          <details className="rounded-md border border-border">
            <summary className="cursor-pointer px-3 py-2 text-[13px] text-muted">Ver el script que se ejecutará</summary>
            <pre className="max-h-64 overflow-auto border-t border-border bg-subtle p-3 font-mono text-2xs">{d.remediation}</pre>
          </details>
        </div>
      ) : (
        <div className="space-y-4">
          <Notice tone="danger" title={`Se desinstalará ${d.product.name} de ${n} ${n === 1 ? "equipo" : "equipos"}`}>
            Intune lo ejecutará en cuanto el equipo esté conectado (suele tardar minutos; si está apagado, al encenderse).
            {notifyFirst ? " Antes se enviará el aviso por correo a sus usuarios." : " No se avisará al usuario."}
          </Notice>
          <Field label="Motivo (obligatorio, queda en auditoría)">
            {(id) => <input id={id} className="field" autoFocus value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder="p. ej. Política de software autorizado 2026-11-10" />}
          </Field>
        </div>
      )}
    </Modal>
  );
}
