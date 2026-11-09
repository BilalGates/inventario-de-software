import { useQuery } from "@tanstack/react-query";
import { ExternalLink, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { ComplianceBadge } from "@/components/badges";
import { Button, Card, ConfirmDialog, ErrorState, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { fmtDateTime } from "@/lib/format";
import { useAction } from "@/lib/hooks";
import type { DeviceCompliance, IntuneAction } from "@/lib/types";

const ACTION_HELP: Record<IntuneAction, string> = {
  sync: "El equipo contactará con Intune en cuanto esté encendido y con conexión, y volverá a evaluar sus directivas.",
  defender_signatures: "Microsoft Defender descargará las firmas de amenazas más recientes.",
  defender_scan: "Microsoft Defender hará un análisis rápido del equipo. El usuario puede notar algo de carga.",
};

const intuneUrl = (id: string) =>
  `https://intune.microsoft.com/#view/Microsoft_Intune_Devices/DeviceSettingsMenuBlade/~/overview/mdmDeviceId/${id}`;

/** Motivo de la no conformidad (directivas y ajustes que fallan) y acciones remotas de Intune. */
export function CompliancePanel({ deviceId, className }: { deviceId: number; className?: string }) {
  const can = useCan();
  const [pending, setPending] = useState<IntuneAction | null>(null);
  const key = ["device-compliance", deviceId];
  const q = useQuery({ queryKey: key, queryFn: () => api.get<DeviceCompliance>(`/devices/${deviceId}/compliance`) });
  const refresh = useAction(() => api.get<DeviceCompliance>(`/devices/${deviceId}/compliance`, { refresh: true }),
    { success: "Conformidad consultada en Intune", invalidate: [key, ["device", deviceId], ["devices"]] });
  const act = useAction((action: IntuneAction) =>
    api.send<{ message: string }>("POST", `/devices/${deviceId}/intune-actions`, { action }),
  { success: (r) => r.message, onSuccess: () => setPending(null) });

  if (q.isLoading) return <Card title="Conformidad" className={className}><Spinner /></Card>;
  if (q.error || !q.data) return <Card title="Conformidad" className={className}><ErrorState error={q.error} retry={q.refetch} /></Card>;
  const c = q.data;
  const label = (code: IntuneAction) => c.actions.find((a) => a.code === code)?.label ?? code;
  const failing = c.compliance_state != null && c.compliance_state !== "compliant";

  return (
    <Card title="Conformidad (Intune)" className={className} actions={c.intune_device_id && (
      <div className="flex flex-wrap items-center gap-2">
        <a className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg" href={intuneUrl(c.intune_device_id)}
          target="_blank" rel="noreferrer">Abrir en Intune <ExternalLink className="size-3" /></a>
        <Button size="sm" icon={<RefreshCw className="size-3.5" />} loading={refresh.isPending}
          onClick={() => refresh.mutate(undefined)}>Consultar ahora</Button>
      </div>
    )}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <ComplianceBadge value={c.compliance_state} />
        <span className="text-xs text-muted">
          {c.checked_at ? `Detalle comprobado ${fmtDateTime(c.checked_at)}` : "Detalle aún no consultado"}
        </span>
      </div>

      {!c.intune_device_id && <p className="mt-3 text-sm text-muted">Este equipo no está gestionado por Intune.</p>}

      {c.intune_device_id && c.policies.length > 0 && (
        <ul className="mt-4 space-y-3">
          {c.policies.map((p) => (
            <li key={p.name} className="rounded-md border border-border p-3">
              <p className="text-xs text-muted">Directiva · <span className="text-fg-2">{p.name}</span></p>
              {p.settings.length === 0 && <p className="mt-1 text-sm">Intune no detalla qué ajuste falla. Sincronice el equipo y vuelva a consultar.</p>}
              <ul className="mt-2 space-y-2">
                {p.settings.map((s) => (
                  <li key={`${p.name}-${s.setting ?? s.label}`} className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-signal">{s.label}</p>
                      {s.hint && <p className="text-xs text-fg-2">{s.hint}</p>}
                      {s.error && <p className="text-xs text-muted">Intune: {s.error}</p>}
                    </div>
                    {s.action && can.write && (
                      <Button size="sm" onClick={() => setPending(s.action)}>{label(s.action)}</Button>
                    )}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}

      {c.intune_device_id && c.policies.length === 0 && failing && (
        <p className="mt-3 text-sm text-fg-2">
          {c.checked_at ? "Intune no informa de ninguna directiva en fallo. Puede estar pendiente de evaluar: sincronice el equipo y vuelva a consultar."
            : "Pulse «Consultar ahora» para ver qué directiva falla."}
        </p>
      )}
      {c.intune_device_id && !failing && c.compliance_state && (
        <p className="mt-3 flex items-center gap-1.5 text-sm text-fg-2"><ShieldCheck className="size-4" /> Cumple todas las directivas asignadas.</p>
      )}

      {c.intune_device_id && can.write && (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-3">
          {c.actions.map((a) => <Button key={a.code} size="sm" variant="ghost" onClick={() => setPending(a.code)}>{a.label}</Button>)}
        </div>
      )}

      <ConfirmDialog open={pending !== null} onClose={() => setPending(null)} busy={act.isPending}
        title={pending ? label(pending) : ""} confirmLabel="Enviar a Intune" onConfirm={() => pending && act.mutate(pending)}>
        <p className="text-sm">{pending && ACTION_HELP[pending]}</p>
        <p className="mt-2 text-xs text-muted">La conformidad la evalúa el propio equipo: el estado puede tardar unos minutos en cambiar. Use «Consultar ahora» más tarde.</p>
      </ConfirmDialog>
    </Card>
  );
}
