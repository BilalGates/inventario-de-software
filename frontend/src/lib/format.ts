/** Formateo y etiquetas en español. Las fechas de la API son UTC sin zona. */

export function parseUtc(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

const dateFmt = new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("es-ES", {
  day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
});

export const fmtDate = (v: string | null | undefined) => (parseUtc(v) ? dateFmt.format(parseUtc(v)!) : "—");
export const fmtDateTime = (v: string | null | undefined) => (parseUtc(v) ? dateTimeFmt.format(parseUtc(v)!) : "—");

export function fmtRelative(v: string | null | undefined, now: Date = new Date()): string {
  const d = parseUtc(v);
  if (!d) return "nunca";
  const s = Math.round((now.getTime() - d.getTime()) / 1000);
  if (s < 60) return "hace un momento";
  const m = Math.round(s / 60);
  if (m < 60) return `hace ${m} min`;
  const h = Math.round(m / 60);
  if (h < 24) return `hace ${h} h`;
  const days = Math.round(h / 24);
  if (days < 30) return `hace ${days} ${days === 1 ? "día" : "días"}`;
  return fmtDate(v);
}

export function fmtBytes(bytes: number | null | undefined, binary = false): string {
  if (!bytes) return "—";
  const base = binary ? 1024 : 1000;
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let n = bytes;
  while (n >= base && i < units.length - 1) {
    n /= base;
    i++;
  }
  return `${n >= 10 || i === 0 ? Math.round(n) : n.toFixed(1)} ${units[i]}`;
}

export const fmtNumber = (n: number | null | undefined) => (n == null ? "—" : n.toLocaleString("es-ES"));

export const AUTH_LABEL: Record<string, string> = {
  authorized: "Autorizado",
  unauthorized: "No autorizado",
  pending_review: "Pendiente de revisión",
  exception: "Excepción aprobada",
  unclassified: "No clasificado",
};

export const CATEGORY_LABEL: Record<string, string> = {
  application: "Aplicación",
  system_component: "Componente del sistema",
  driver: "Controlador",
  runtime: "Runtime / librería",
  update: "Actualización",
  unknown: "Desconocido",
};

export const DEVICE_STATUS_LABEL: Record<string, string> = {
  active: "En uso",
  in_stock: "En almacén",
  repair: "En reparación",
  retired: "Dado de baja",
  lost: "Perdido / robado",
};

export const FRESHNESS_LABEL: Record<string, string> = {
  current: "Sincronizado",
  stale: "No observado recientemente",
  never_synced: "Sin fuente automática",
  retired: "Dado de baja",
};

export const RUN_STATUS_LABEL: Record<string, string> = {
  queued: "En cola",
  running: "En curso",
  succeeded: "Completada",
  partial: "Parcial",
  failed: "Fallida",
  cancelled: "Cancelada",
};

export const TRIGGER_LABEL: Record<string, string> = {
  manual: "Manual",
  schedule: "Programada",
  upload: "Fichero",
  watcher: "Carpeta supervisada",
  retry: "Reintento",
  legacy: "Migración",
};

export const CHANGE_LABEL: Record<string, string> = {
  device_added: "Alta de dispositivo",
  device_updated: "Dato técnico modificado",
  device_retired: "Baja de dispositivo",
  device_reactivated: "Reactivación",
  device_not_observed: "Dispositivo no observado",
  device_merged: "Dispositivos fusionados",
  retired_device_observed: "Dispositivo retirado observado",
  department_changed: "Cambio de departamento",
  user_changed: "Cambio de usuario",
  software_installed: "Software instalado",
  software_removed: "Software desinstalado",
  software_version_changed: "Cambio de versión",
  software_baseline: "Carga inicial de software",
  software_new_product: "Nuevo producto en catálogo",
  authorization_changed: "Cambio de autorización",
};

export const FIELD_LABEL: Record<string, string> = {
  hostname: "Nombre",
  serial_number: "Nº de serie",
  manufacturer: "Fabricante",
  model: "Modelo",
  os_name: "Sistema operativo",
  os_version: "Versión del SO",
  ram_bytes: "RAM",
  storage_total_bytes: "Almacenamiento",
  encrypted: "Cifrado",
  compliance_state: "Cumplimiento",
  status: "Estado",
  department_id: "Departamento",
  primary_user_id: "Usuario",
};

export const SOURCE_LABEL: Record<string, string> = {
  intune: "Intune",
  panda: "Panda",
  legacy: "Sistema anterior",
  manual: "Manual",
};

export const SNAPSHOT_STATUS_LABEL: Record<string, string> = {
  draft: "Pendiente de revisión",
  approved: "Aprobado",
  rejected: "Rechazado",
  legacy: "Histórico importado",
};

export const ROLE_LABEL: Record<string, string> = { admin: "Administrador", technician: "Técnico IT", auditor: "Auditor" };

export function currentPeriod(d = new Date()): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function fmtPeriod(p: string): string {
  const [y, m] = p.split("-").map(Number);
  const text = new Intl.DateTimeFormat("es-ES", { month: "long", year: "numeric" }).format(new Date(y, m - 1, 1));
  return text.charAt(0).toUpperCase() + text.slice(1);
}
