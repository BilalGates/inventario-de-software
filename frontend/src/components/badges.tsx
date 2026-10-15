import { AUTH_LABEL, DEVICE_STATUS_LABEL, FRESHNESS_LABEL, RUN_STATUS_LABEL, SNAPSHOT_STATUS_LABEL, SOURCE_LABEL } from "@/lib/format";
import { Badge, type Tone } from "./ui";

const AUTH_TONE: Record<string, Tone> = {
  authorized: "ok", unauthorized: "danger", pending_review: "warn", exception: "info", unclassified: "neutral",
};
export const AuthBadge = ({ status }: { status: string }) => (
  <Badge tone={AUTH_TONE[status] ?? "neutral"} dot>{AUTH_LABEL[status] ?? status}</Badge>
);

const FRESH_TONE: Record<string, Tone> = { current: "ok", stale: "warn", never_synced: "neutral", retired: "neutral" };
export const FreshnessBadge = ({ value }: { value: string }) => (
  <Badge tone={FRESH_TONE[value]} dot>{FRESHNESS_LABEL[value] ?? value}</Badge>
);

const STATUS_TONE: Record<string, Tone> = { active: "accent", in_stock: "neutral", repair: "warn", retired: "neutral", lost: "danger" };
export const DeviceStatusBadge = ({ status }: { status: string }) => (
  <Badge tone={STATUS_TONE[status] ?? "neutral"}>{DEVICE_STATUS_LABEL[status] ?? status}</Badge>
);

const RUN_TONE: Record<string, Tone> = { queued: "neutral", running: "info", succeeded: "ok", partial: "warn", failed: "danger", cancelled: "neutral" };
export const RunStatusBadge = ({ status }: { status: string }) => (
  <Badge tone={RUN_TONE[status] ?? "neutral"} dot>{RUN_STATUS_LABEL[status] ?? status}</Badge>
);

const SEV_TONE: Record<string, Tone> = { critical: "danger", warning: "warn", info: "info" };
const SEV_LABEL: Record<string, string> = { critical: "Crítica", warning: "Aviso", info: "Info" };
export const SeverityBadge = ({ severity }: { severity: string }) => (
  <Badge tone={SEV_TONE[severity] ?? "neutral"}>{SEV_LABEL[severity] ?? severity}</Badge>
);

const SNAP_TONE: Record<string, Tone> = { draft: "warn", approved: "ok", rejected: "danger", legacy: "neutral" };
export const SnapshotBadge = ({ status }: { status: string }) => (
  <Badge tone={SNAP_TONE[status] ?? "neutral"}>{SNAPSHOT_STATUS_LABEL[status] ?? status}</Badge>
);

export const SourceBadge = ({ source }: { source: string }) => <Badge>{SOURCE_LABEL[source] ?? source}</Badge>;

export function ComplianceBadge({ value }: { value: string | null }) {
  if (!value) return <span className="text-muted">—</span>;
  const tone: Tone = value === "compliant" ? "ok" : value === "noncompliant" ? "danger" : "neutral";
  const label: Record<string, string> = { compliant: "Conforme", noncompliant: "No conforme", inGracePeriod: "En gracia",
    unknown: "Desconocido", configManager: "ConfigMgr", error: "Error", conflict: "Conflicto" };
  return <Badge tone={tone}>{label[value] ?? value}</Badge>;
}
