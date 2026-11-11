/** Avisos por correo y desinstalaciones remotas (acciones sobre el software no autorizado). */

export interface NotifyScope { alert_ids?: number[]; product_id?: number; device_ids?: number[] }

export interface NotifyPreview {
  sender: string | null;
  cc: string | null;
  template: { subject: string; body: string };
  recipients: { upn: string; name: string; devices: string[]; programs: string[]; alerts: number; subject: string; body: string }[];
  no_user: string[];
}

export interface UninstallPreview {
  product: { id: number; name: string };
  blocked: string | null;
  method?: string;
  names?: string[];
  devices: { id: number; name: string; user: string | null }[];
  skipped: { id: number; name: string; reason: string }[];
  recipients?: number;
  no_user?: string[];
  detection?: string;
  remediation?: string;
  connected?: boolean;
}

export type RemoteStatus = "sent" | "running" | "succeeded" | "failed" | "manual_required" | "expired";

export interface RemoteAction {
  id: number;
  kind: "notify" | "uninstall";
  status: RemoteStatus;
  device_id: number | null;
  device: string | null;
  product_id: number | null;
  product: string | null;
  alert_id: number | null;
  recipient: string | null;
  requested_by: string;
  requested_at: string;
  finished_at: string | null;
  reason: string | null;
  detail: { subject?: string; error?: string; output?: string; method?: string };
}

export const REMOTE_STATUS_LABEL: Record<RemoteStatus, string> = {
  sent: "Enviada", running: "En curso", succeeded: "Hecha", failed: "Fallida", manual_required: "Requiere desinstalación manual",
  expired: "Sin respuesta de Intune",
};
