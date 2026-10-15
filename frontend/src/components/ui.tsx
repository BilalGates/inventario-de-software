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
  primary: "bg-accent text-accent-fg hover:bg-accent/90 border-transparent",
  secondary: "bg-surface text-fg border-border hover:bg-subtle",
  ghost: "border-transparent text-muted hover:bg-subtle hover:text-fg",
  danger: "bg-danger text-white hover:bg-danger/90 border-transparent dark:text-black",
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
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-9 px-3.5 text-sm",
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
  neutral: "bg-subtle text-muted ring-border",
  ok: "bg-ok/10 text-ok ring-ok/25",
  warn: "bg-warn/10 text-warn ring-warn/25",
  danger: "bg-danger/10 text-danger ring-danger/25",
  info: "bg-info/10 text-info ring-info/25",
  accent: "bg-accent/10 text-accent ring-accent/25",
};

export function Badge({ tone = "neutral", children, dot, title }: { tone?: Tone; children: ReactNode; dot?: boolean;
  title?: string }) {
  return (
    <span title={title} className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-2xs font-medium ring-1 ring-inset", TONE[tone])}>
      {dot && <span className="size-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

// ---------------------------------------------------------------- Estructura
export function PageHeader({ title, description, actions, children }: { title: string; description?: ReactNode;
  actions?: ReactNode; children?: ReactNode }) {
  return (
    <header className="mb-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          {children}
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          {description && <p className="mt-1 text-muted">{description}</p>}
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
        <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-2.5">
          <h2 className="text-sm font-semibold">{title}</h2>
          {actions}
        </div>
      )}
      <div className={padded ? "p-4" : undefined}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint, tone, onClick }: { label: string; value: ReactNode; hint?: ReactNode;
  tone?: Tone; onClick?: () => void }) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag onClick={onClick} className={cx("card flex flex-col items-start p-4 text-left", onClick && "transition-colors hover:border-muted/40")}>
      <span className="text-xs font-medium text-muted">{label}</span>
      <span className={cx("num mt-1 text-2xl font-semibold tracking-tight", tone && tone !== "neutral" && TONE[tone].split(" ")[1])}>
        {value}
      </span>
      {hint && <span className="mt-0.5 text-xs text-muted">{hint}</span>}
    </Tag>
  );
}

export function DefinitionList({ items }: { items: [ReactNode, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {items.map(([k, v], i) => (
        <div key={i} className="min-w-0">
          <dt className="text-xs text-muted">{k}</dt>
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
      <div className="mb-3 rounded-full bg-subtle p-3 text-muted">{icon ?? <Inbox className="size-5" aria-hidden />}</div>
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 max-w-md text-muted">{children}</div>}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center px-6 py-10 text-center">
      <XCircle className="mb-2 size-6 text-danger" aria-hidden />
      <p className="font-medium">No se pudieron cargar los datos</p>
      <p className="mt-1 text-muted">{error instanceof Error ? error.message : String(error)}</p>
      {retry && <Button className="mt-3" size="sm" onClick={retry}>Reintentar</Button>}
    </div>
  );
}

export function Notice({ tone = "info", title, children }: { tone?: Tone; title?: string; children: ReactNode }) {
  return (
    <div className={cx("rounded-md px-3 py-2.5 text-sm ring-1 ring-inset", TONE[tone])}>
      {title && <p className="font-medium">{title}</p>}
      <div className={cx(title && "mt-0.5", "text-fg/80")}>{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------- Pestañas
export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: ReactNode }[]; value: T;
  onChange: (v: T) => void }) {
  return (
    <div role="tablist" className="mb-4 flex gap-1 overflow-x-auto border-b border-border">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            "-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors",
            value === t.id ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg",
          )}
        >
          {t.label}
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
      {error ? <p className="mt-1 text-xs text-danger">{error}</p> : hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
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
        <h2 id="modal-title" className="font-semibold">{title}</h2>
        <button onClick={onClose} className="rounded p-1 text-muted hover:bg-subtle hover:text-fg" aria-label="Cerrar">
          <X className="size-4" />
        </button>
      </div>
      <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
      {footer && <div className="flex justify-end gap-2 border-t border-border bg-subtle/50 px-5 py-3">{footer}</div>}
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
            className="card pointer-events-auto flex items-start gap-2 p-3 shadow-lg">
            {t.tone === "ok" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" aria-hidden />
              : t.tone === "danger" ? <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
              : <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin text-info" aria-hidden />}
            <p className="text-sm">{t.text}</p>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
