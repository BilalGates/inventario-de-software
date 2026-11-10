import { AUTH_LABEL, COMPLIANCE_LABEL, DEVICE_STATUS_LABEL, FRESHNESS_LABEL, RUN_STATUS_LABEL, SNAPSHOT_STATUS_LABEL,
  SOURCE_LABEL } from "@/lib/format";
import { Badge, cx, type Tone } from "./ui";

/** Estado como punto cuadrado + texto (tablas): tinta para lo normal, señal para lo que requiere atención. */
type Mark = "ink" | "signal" | "muted" | "hollow";
const MARK: Record<Mark, [string, string]> = {
  ink: ["bg-fg", "text-fg-2"],
  signal: ["bg-signal-fill", "font-medium text-signal"],
  muted: ["bg-chart-3", "text-muted"],
  hollow: ["border border-fg-2 bg-transparent", "text-fg-2"],
};
export function StatusText({ mark, children, title }: { mark: Mark; children: string; title?: string }) {
  const [dot, text] = MARK[mark];
  return (
    <span title={title} className={cx("inline-flex items-center gap-2 whitespace-nowrap text-[13px]", text)}>
      <span className={cx("size-[7px] shrink-0 rounded-[2px]", dot)} aria-hidden />{children}
    </span>
  );
}

const AUTH_MARK: Record<string, Mark> = {
  authorized: "ink", conditional: "muted", unauthorized: "signal", pending_review: "hollow", exception: "muted", unclassified: "hollow",
};
export const AuthBadge = ({ status }: { status: string }) => (
  <StatusText mark={AUTH_MARK[status] ?? "muted"}>{AUTH_LABEL[status] ?? status}</StatusText>
);

const FRESH_MARK: Record<string, Mark> = { current: "ink", stale: "signal", never_synced: "muted", retired: "muted" };
export const FreshnessBadge = ({ value }: { value: string }) => (
  <StatusText mark={FRESH_MARK[value] ?? "muted"}>{FRESHNESS_LABEL[value] ?? value}</StatusText>
);

const STATUS_TONE: Record<string, Tone> = { active: "accent", in_stock: "neutral", repair: "warn", retired: "neutral", lost: "danger" };
export const DeviceStatusBadge = ({ status }: { status: string }) => (
  <Badge tone={STATUS_TONE[status] ?? "neutral"}>{DEVICE_STATUS_LABEL[status] ?? status}</Badge>
);

const RUN_TONE: Record<string, Tone> = { queued: "neutral", running: "info", succeeded: "ok", partial: "warn", failed: "danger", cancelled: "neutral" };
export const RunStatusBadge = ({ status }: { status: string }) => (
  <Badge tone={RUN_TONE[status] ?? "neutral"} dot>{RUN_STATUS_LABEL[status] ?? status}</Badge>
);

/** Severidad como código monoespaciado: CRIT en señal, AVISO en tinta, INFO apagado. */
const SEV: Record<string, [string, string, string]> = {
  critical: ["CRIT", "Crítica", "text-signal"], warning: ["AVISO", "Aviso", "text-fg"], info: ["INFO", "Informativa", "text-muted"],
};
export function SeverityBadge({ severity }: { severity: string }) {
  const [code, label, tone] = SEV[severity] ?? [severity.toUpperCase(), severity, "text-muted"];
  return <span title={label} className={cx("code text-2xs font-medium tracking-[0.04em]", tone)}>
    <span aria-hidden>{code}</span><span className="sr-only">{label}</span>
  </span>;
}

const SNAP_TONE: Record<string, Tone> = { draft: "warn", approved: "ok", rejected: "danger", legacy: "neutral" };
export const SnapshotBadge = ({ status }: { status: string }) => (
  <Badge tone={SNAP_TONE[status] ?? "neutral"}>{SNAPSHOT_STATUS_LABEL[status] ?? status}</Badge>
);

/** Fuente de datos como etiqueta monoespaciada pequeña (INTUNE, PANDA…). */
export const SourceBadge = ({ source }: { source: string }) => (
  <span className="inline-block rounded-[3px] border border-border-strong px-1.5 py-px font-mono text-[10px] uppercase tracking-[0.04em] text-fg-2">
    {SOURCE_LABEL[source] ?? source}
  </span>
);

/** Cumplimiento de Intune; con `reasons`, el motivo aparece al pasar el ratón. */
export function ComplianceBadge({ value, reasons }: { value: string | null; reasons?: string[] }) {
  if (!value) return <span className="text-muted">—</span>;
  const mark: Mark = value === "compliant" ? "ink" : value === "noncompliant" ? "signal" : "muted";
  const title = reasons?.length ? `Motivo: ${reasons.join(" · ")}` : undefined;
  return <StatusText mark={mark} title={title}>{COMPLIANCE_LABEL[value] ?? value}</StatusText>;
}
