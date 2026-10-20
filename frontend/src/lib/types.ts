export type Role = "admin" | "technician" | "auditor";

export interface Me {
  upn: string;
  name: string | null;
  role: Role;
  permissions: { read: boolean; write: boolean; admin: boolean };
}

export interface Paged<T> {
  total: number;
  items: T[];
}

export type Freshness = "current" | "stale" | "never_synced" | "retired";

export interface DeviceRow {
  id: number;
  uid: string;
  name: string;
  hostname: string | null;
  serial_number: string | null;
  manufacturer: string | null;
  model: string | null;
  os_name: string | null;
  os_version: string | null;
  device_type_id: number | null;
  device_type: string | null;
  status: string;
  freshness: Freshness;
  department_id: number | null;
  department: string | null;
  primary_user_id: number | null;
  primary_user: string | null;
  primary_user_upn: string | null;
  location: string | null;
  compliance_state: string | null;
  encrypted: boolean | null;
  ram_bytes: number | null;
  storage_total_bytes: number | null;
  last_seen_at: string | null;
  last_seen_source: string | null;
  source_last_sync_at: string | null;
  software_count?: number;
  sources?: string[];
}

export interface DeviceDetail extends DeviceRow {
  notes: string | null;
  processor: string | null;
  storage_free_bytes: number | null;
  mac_wifi: string | null;
  mac_ethernet: string | null;
  management_state: string | null;
  ownership: string | null;
  enrolled_at: string | null;
  first_seen_at: string | null;
  retired_at: string | null;
  purchase_date: string | null;
  cost: string | null;
  created_at: string;
  updated_at: string;
  field_sources: Record<string, { source: string; at: string; by?: string }>;
  external_ids: { source: string; type: string; value: string; first_seen_at: string; last_seen_at: string }[];
}

export type AuthStatus = "authorized" | "unauthorized" | "pending_review" | "exception" | "unclassified";

export interface InstalledSoftware {
  installation_id: number;
  product_id: number;
  name: string;
  publisher: string | null;
  category: string;
  is_relevant: boolean;
  version: string | null;
  source: string;
  present: boolean;
  first_seen_at: string;
  last_seen_at: string;
  removed_at: string | null;
  authorization_status: AuthStatus;
  authorization_origin: string;
}

export interface Product {
  id: number;
  name: string;
  publisher: string | null;
  category: string;
  is_relevant: boolean;
  authorization_status: AuthStatus;
  ens_classification: string | null;
  notes: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  devices: number;
  versions: number;
}

export interface Policy {
  id: number;
  product_id: number;
  product: string | null;
  scope: "global" | "department" | "device";
  department_id: number | null;
  department: string | null;
  device_id: number | null;
  device: string | null;
  status: AuthStatus;
  justification: string | null;
  approved_by: string | null;
  valid_from: string;
  valid_until: string | null;
  active: boolean;
  expired: boolean;
  created_by: string | null;
  created_at: string;
  revoked_at: string | null;
  revoked_by: string | null;
}

export interface Department {
  id: number;
  code: string;
  name: string;
  description: string | null;
  manager_id: number | null;
  manager: string | null;
  cost_center: string | null;
  attributes: Record<string, string>;
  active: boolean;
  devices?: number;
  users?: number;
  software?: number;
}

export interface Run {
  id: number;
  source: string;
  source_name: string;
  trigger: string;
  status: "queued" | "running" | "succeeded" | "partial" | "failed" | "cancelled";
  /** Última línea del registro mientras se ejecuta. */
  progress?: string;
  is_complete: boolean;
  requested_by: string | null;
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
  attempt: number;
  retry_of_id: number | null;
  period: string | null;
  error: string | null;
  stats: Record<string, unknown>;
  filename: string | null;
  log?: string[];
  changes?: Record<string, number>;
}

export interface Source {
  id: number;
  code: string;
  name: string;
  kind: "api" | "file";
  enabled: boolean;
  priority: number;
  config: Record<string, unknown>;
  configured: boolean;
  last_success_at: string | null;
  last_error: string | null;
  last_run: Run | null;
  devices: number;
  devices_with_software: number;
  watch_folder: boolean | null;
  /** Solo Intune: "app" (credenciales INV_GRAPH_*), "delegated" (sesión iniciada desde la web) o null. */
  graph_auth?: "app" | "delegated" | null;
  graph_account?: string | null;
}

export interface DeviceCodeStart {
  user_code: string;
  verification_uri: string;
  expires_in: number;
  interval: number;
}

export interface DeviceCodeStatus {
  status: "idle" | "pending" | "connected" | "expired" | "error";
  account?: string;
  error?: string;
}

export interface Change {
  id: number;
  type: string;
  device_id: number | null;
  device: string | null;
  product_id: number | null;
  product: string | null;
  field: string | null;
  old: string | null;
  new: string | null;
  source: string | null;
  at: string;
  run_id: number | null;
}

export interface Alert {
  id: number;
  type: string;
  severity: "info" | "warning" | "critical";
  status: "open" | "acknowledged" | "resolved";
  title: string;
  detail: string | null;
  device_id: number | null;
  product_id: number | null;
  run_id: number | null;
  created_at: string;
  last_seen_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution: string | null;
}

export interface Coverage {
  complete: boolean;
  sources: Record<string, { name: string; essential: boolean; ok: boolean; runs: number;
    last_complete_run_id: number | null; failed_after_last_complete: boolean }>;
}

export interface Snapshot {
  id: number;
  period: string;
  version: number;
  status: "draft" | "approved" | "rejected" | "legacy";
  is_complete: boolean;
  coverage: Coverage | null;
  totals: { devices: number; installations: number; products: number; by_status: Record<string, number> } | null;
  created_at: string;
  created_by: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
}
