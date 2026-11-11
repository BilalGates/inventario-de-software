import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Alert, Coverage, Run, Snapshot } from "./types";

export interface DayActivity { date: string; installed: number; removed: number; updated: number }
export interface WeekActivity { week_start: string; installed: number; removed: number; updated: number }
/** Estado común de un equipo (misma leyenda en todas las pantallas). */
export type HealthState = "ok" | "alert" | "nc" | "alertnc" | "infra";
export interface FleetDevice {
  id: number; name: string; freshness: string; compliance: string | null; department: string | null;
  type?: string | null; model?: string | null; unauthorized?: boolean; state?: HealthState; reasons?: string[];
}
export interface RankedProduct { id: number; name: string; publisher: string | null; devices: number }
export interface QueueProduct extends RankedProduct {
  first_seen_at?: string | null; status?: string; notes?: string | null; departments?: string[];
}
export interface AlertCause { product_id: number; name: string; devices: number; alerts: number; alternative: string | null }
export interface Health { workstations: number; clean: number; unauthorized: number; noncompliant: number; both: number; infra: number }

/** Respuesta de /dashboard. La comparten el Panel y las franjas de resumen de las demás páginas. */
export interface DashboardData {
  generated_at: string;
  devices: { total: number; current: number; stale: number; never_synced: number; unassigned: number;
    by_status: Record<string, number>; compliance: Record<string, number>;
    by_os?: Record<string, number>; by_source?: Record<string, number>; by_type?: Record<string, number>; fleet?: FleetDevice[] };
  health?: Health;
  compliance_reasons?: { reason: string; devices: string[] }[];
  software: { products: number; installations: number; pending: number; unauthorized_products: number;
    by_status: Record<string, number>; components?: number; top?: RankedProduct[]; queue?: QueueProduct[];
    versions_spread?: { count: number; top: { id: number; name: string; versions: number }[] };
    new_30d?: number; gone_30d?: number; new_daily?: number[] };
  alerts: { open: number; by_severity: Record<string, number>; top: Alert[]; resolved_30d?: number;
    causes?: AlertCause[]; causes_total?: number; rest?: { products: number; alerts: number };
    unauthorized_devices?: number; weekly?: { week_start: string; opened: number; resolved: number }[] };
  monthly: { period: string; snapshot: Snapshot | null; coverage: Coverage };
  runs: Run[];
  changes_daily?: DayActivity[];
  changes_weekly?: WeekActivity[];
  departments: { name: string; devices: number }[];
  worker_heartbeat: { at: string } | null;
  /** Cada cuánto pasa el worker (1 = continuo en local; 60 = cada hora en la nube). */
  worker_interval_minutes?: number;
  open_review_cases: number;
}

export const useDashboard = () =>
  useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get<DashboardData>("/dashboard"),
    refetchInterval: 60_000,
  });
