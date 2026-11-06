import { AlertTriangle, CheckCircle2, Inbox, Loader2, X, XCircle } from "lucide-react";
import {
  createContext,
  forwardRef,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

// ---------------------------------------------------------------- Botón
type Variant = "primary" | "secondary" | "ghost" | "danger";
const VARIANT: Record<Variant, string> = {
  primary: "bg-accent text-accent-fg hover:bg-accent/85 border-accent",
  secondary: "bg-surface text-fg-2 border-border-strong hover:border-muted hover:text-fg",
  ghost: "border-transparent text-muted hover:bg-subtle hover:text-fg",
  danger: "bg-signal text-white hover:bg-signal/90 border-transparent dark:text-black",
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md"; loading?: boolean; icon?: ReactNode }
>(function Button({ variant = "secondary", size = "md", loading, icon, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      type="button"
      disabled={disabled || loading}
      className={cx(
        "inline-flex select-none items-center justify-center gap-1.5 whitespace-nowrap rounded-md border font-medium",
        "transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-8 px-2.5 text-xs" : "h-10 px-3.5 text-[13px]",
        VARIANT[variant],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
});

// ---------------------------------------------------------------- Insignias
export type Tone = "neutral" | "ok" | "warn" | "danger" | "info" | "accent";
const TONE: Record<Tone, string> = {
  neutral: "border-border bg-surface text-muted",
  ok: "border-ok/25 bg-ok/[0.06] text-ok",
  warn: "border-warn/30 bg-warn/[0.07] text-warn",
  danger: "border-signal/30 bg-signal/10 text-signal",
  info: "border-border bg-surface text-fg-2",
  accent: "border-fg/20 bg-fg/[0.05] text-fg",
};

export function Badge({ tone = "neutral", children, dot, title }: { tone?: Tone; children: ReactNode; dot?: boolean;
  title?: string }) {
  return (
    <span title={title} className={cx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-[3px] border px-1.5 py-px text-2xs font-medium", TONE[tone])}>
      {dot && <span className="size-1.5 rounded-[1px] bg-current" aria-hidden />}
      {children}
    </span>
  );
}

// ---------------------------------------------------------------- Estructura
export function PageHeader({ title, description, actions, children, eyebrow }: { title: string; description?: ReactNode;
  actions?: ReactNode; children?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <header className="mb-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          {children}
          {eyebrow && <p className="eyebrow mb-2.5">{eyebrow}</p>}
          <h1 className="disp text-[28px] font-semibold leading-tight sm:text-[32px]">{title}</h1>
          {description && <p className="mt-1.5 text-muted">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}

export function Card({ title, actions, children, className, padded = true }: { title?: ReactNode; actions?: ReactNode;
  children: ReactNode; className?: string; padded?: boolean }) {
  return (
    <section className={cx("card", className)}>
      {(title || actions) && (
        <div className={cx("flex items-baseline justify-between gap-3 px-5 pt-5", padded ? "pb-1" : "border-b border-border pb-3")}>
          <h2 className="disp text-base font-semibold tracking-[-0.02em]">{title}</h2>
          {actions}
        </div>
      )}
      <div className={padded ? "p-5" : undefined}>{children}</div>
    </section>
  );
}

/** Franja de indicadores: celdas separadas por líneas finas dentro de un único panel. */
export function StatStrip({ children, className, label = "Indicadores", minCell = "11rem" }: { children: ReactNode;
  className?: string; label?: string; minCell?: string }) {
  return (
    <section aria-label={label} className={cx("card overflow-hidden", className)}>
      {/* Cada celda pinta su borde derecho e inferior; el margen negativo esconde los del límite exterior. */}
      <div className="-mb-px -mr-px grid [&>*]:border-b [&>*]:border-r [&>*]:border-border"
        style={{ gridTemplateColumns: `repeat(auto-fit, minmax(min(100%, ${minCell}), 1fr))` }}>
        {children}
      </div>
    </section>
  );
}

/** Celda de indicador. Los tonos de alerta (warn/danger) usan el color de señal. */
export function Stat({ label, value, hint, tone, onClick, children }: { label: string; value: ReactNode; hint?: ReactNode;
  tone?: Tone; onClick?: () => void; children?: ReactNode }) {
  const Tag = onClick ? "button" : "div";
  const alert = tone === "danger" || tone === "warn";
  return (
    <Tag onClick={onClick} className={cx("flex flex-col items-start gap-1.5 px-5 py-5 text-left transition-colors",
      alert ? "bg-[rgb(var(--signal)/0.07)]" : "bg-surface", onClick && "hover:bg-bg")}>
      <span className={cx("eyebrow", alert && "text-signal")}>{label}</span>
      <span className={cx("disp text-[34px] font-semibold leading-none", alert && "text-signal")}>{value}</span>
      {hint && <span className={cx("text-xs", alert ? "text-fg-2" : "text-muted")}>{hint}</span>}
      {children}
    </Tag>
  );
}

export function DefinitionList({ items }: { items: [ReactNode, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {items.map(([k, v], i) => (
        <div key={i} className="min-w-0">
          <dt className="eyebrow">{k}</dt>
          <dd className="mt-0.5 truncate">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

// ---------------------------------------------------------------- Estados
export function Spinner({ label = "Cargando…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-10 text-muted">
      <Loader2 className="size-4 animate-spin" aria-hidden /> {label}
    </div>
  );
}

export function EmptyState({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 rounded-md border border-border p-2.5 text-muted">{icon ?? <Inbox className="size-5" aria-hidden />}</div>
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 max-w-md text-muted">{children}</div>}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center px-6 py-10 text-center">
      <XCircle className="mb-2 size-6 text-signal" aria-hidden />
      <p className="font-medium">No se pudieron cargar los datos</p>
      <p className="mt-1 text-muted">{error instanceof Error ? error.message : String(error)}</p>
      {retry && <Button className="mt-3" size="sm" onClick={retry}>Reintentar</Button>}
    </div>
  );
}

export function Notice({ tone = "info", title, children }: { tone?: Tone; title?: string; children: ReactNode }) {
  return (
    <div className={cx("rounded-md border border-l-2 px-4 py-3 text-sm", TONE[tone],
      tone === "warn" || tone === "danger" ? "border-l-signal" : "border-l-fg-2")}>
      {title && <p className="font-medium">{title}</p>}
      <div className={cx(title && "mt-0.5", "text-fg-2")}>{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------- Pestañas
export function Tabs<T extends string>({ tabs, value, onChange, bare, label }: { tabs: { id: T; label: ReactNode; count?: ReactNode }[];
  value: T; onChange: (v: T) => void; /** Sin margen ni borde: para usar dentro de otro contenedor. */ bare?: boolean; label?: string }) {
  return (
    <div role="tablist" aria-label={label} className={cx("flex gap-6 overflow-x-auto", !bare && "mb-5 border-b border-border")}>
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            "-mb-px min-h-11 whitespace-nowrap border-b-2 px-0.5 text-[13px] font-medium transition-colors",
            value === t.id ? "border-fg text-fg" : "border-transparent text-muted hover:text-fg",
          )}
        >
          {t.label}
          {t.count != null && <span className="code ml-2 text-2xs text-muted">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

/** Grupo de botones excluyentes (filtros rápidos). */
export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: { id: T; label: ReactNode; count?: ReactNode }[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap overflow-hidden rounded-md border border-border-strong">
      {options.map((o) => (
        <button key={o.id} type="button" aria-pressed={value === o.id} onClick={() => onChange(o.id)}
          className={cx("inline-flex min-h-9 items-center gap-2 border-r border-border-strong px-3 text-xs font-medium transition-colors last:border-r-0",
            value === o.id ? "bg-fg text-bg" : "bg-surface text-muted hover:text-fg")}>
          {o.label}
          {o.count != null && <span className="code text-2xs opacity-80">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- Formularios
export function Field({ label, children, hint, error }: { label: string; children: (id: string) => ReactNode;
  hint?: ReactNode; error?: string | null }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      {children(id)}
      {error ? <p className="mt-1 text-xs text-signal">{error}</p> : hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

// ---------------------------------------------------------------- Diálogos
export function Modal({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void;
  title: string; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      if (typeof d.showModal === "function") d.showModal();
      else d.setAttribute("open", ""); // entornos sin <dialog> modal (tests)
    }
  }, [open]);
  if (!open) return null;
  return (
    <dialog
      ref={ref}
      onCancel={(e) => { e.preventDefault(); onClose(); }}
      aria-labelledby="modal-title"
      className={cx("card m-auto w-[calc(100%-2rem)] p-0 text-fg shadow-2xl", wide ? "max-w-3xl" : "max-w-lg")}
    >
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <h2 id="modal-title" className="disp text-base font-semibold tracking-[-0.02em]">{title}</h2>
        <button onClick={onClose} className="rounded p-1 text-muted hover:bg-subtle hover:text-fg" aria-label="Cerrar">
          <X className="size-4" />
        </button>
      </div>
      <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
      {footer && <div className="flex justify-end gap-2 border-t border-border bg-bg px-5 py-3">{footer}</div>}
    </dialog>
  );
}

export function ConfirmDialog({ open, title, children, confirmLabel = "Confirmar", danger, onConfirm, onClose, busy }: {
  open: boolean; title: string; children: ReactNode; confirmLabel?: string; danger?: boolean; busy?: boolean;
  onConfirm: () => void; onClose: () => void }) {
  return (
    <Modal open={open} onClose={onClose} title={title} footer={<>
      <Button onClick={onClose}>Cancelar</Button>
      <Button variant={danger ? "danger" : "primary"} loading={busy} onClick={onConfirm}>{confirmLabel}</Button>
    </>}>
      {children}
    </Modal>
  );
}

// ---------------------------------------------------------------- Avisos (toasts)
interface Toast { id: number; tone: "ok" | "danger" | "info"; text: string }
const ToastCtx = createContext<(tone: Toast["tone"], text: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((tone: Toast["tone"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-3), { id, tone, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === "danger" ? 8000 : 4000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} role={t.tone === "danger" ? "alert" : "status"}
            className="pointer-events-auto flex items-start gap-2 rounded-md border border-border bg-surface p-3 shadow-[0_8px_24px_rgb(0_0_0/0.08)]">
            {t.tone === "ok" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" aria-hidden />
              : t.tone === "danger" ? <AlertTriangle className="mt-0.5 size-4 shrink-0 text-signal" aria-hidden />
              : <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin text-muted" aria-hidden />}
            <p className="text-sm">{t.text}</p>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
