/** Menú de acciones común a todas las listas: clic derecho sobre una fila o el botón «⋯». */
import { ChevronRight } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cx } from "./ui";

export type MenuEntry =
  | "separator"
  | {
      label: ReactNode;
      onSelect?: () => void;
      /** Icono o cuadro de estado delante del texto. */
      icon?: ReactNode;
      /** Atajo o pista a la derecha (solo informativo). */
      hint?: string;
      danger?: boolean;
      disabled?: boolean;
      /** Marca la opción actual (p. ej. el estado de política vigente). */
      checked?: boolean;
      submenu?: MenuEntry[];
    };

/** Título opcional del menú (nombre del equipo o de la aplicación). */
export interface MenuState { x: number; y: number; title?: string; entries: MenuEntry[] }

export function useContextMenu() {
  const [menu, setMenu] = useState<MenuState | null>(null);
  return {
    menu,
    close: () => setMenu(null),
    /** Abre en la posición del ratón (clic derecho). */
    openAt: (e: { clientX: number; clientY: number; preventDefault: () => void }, entries: MenuEntry[], title?: string) => {
      e.preventDefault();
      setMenu({ x: e.clientX, y: e.clientY, entries, title });
    },
    /** Abre bajo un botón (el «⋯» de la fila, o teclado). */
    openFrom: (el: HTMLElement, entries: MenuEntry[], title?: string) => {
      const r = el.getBoundingClientRect();
      setMenu({ x: r.right, y: r.bottom + 4, entries, title });
    },
  };
}

export function ContextMenu({ menu, onClose }: { menu: MenuState | null; onClose: () => void }) {
  if (!menu) return null;
  return createPortal(<MenuPanel key={`${menu.x},${menu.y}`} x={menu.x} y={menu.y} title={menu.title}
    entries={menu.entries} onClose={onClose} root />, document.body);
}

function MenuPanel({ x, y, title, entries, onClose, root, onBack }: {
  x: number; y: number; title?: string; entries: MenuEntry[]; onClose: () => void; root?: boolean; onBack?: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: x, top: y });
  const [sub, setSub] = useState<{ index: number; x: number; y: number } | null>(null);

  // Que el menú nunca se salga de la ventana.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const w = el.offsetWidth, h = el.offsetHeight;
    setPos({ left: Math.max(8, Math.min(x, window.innerWidth - w - 8)), top: Math.max(8, Math.min(y, window.innerHeight - h - 8)) });
    el.querySelector<HTMLButtonElement>("[role=menuitem]:not([disabled])")?.focus();
  }, [x, y]);

  useEffect(() => {
    if (!root) return;
    const down = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest?.("[data-ctx-menu]")) onClose();
    };
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const away = () => onClose();
    document.addEventListener("mousedown", down);
    document.addEventListener("keydown", key);
    window.addEventListener("resize", away);
    window.addEventListener("scroll", away, true);
    return () => {
      document.removeEventListener("mousedown", down);
      document.removeEventListener("keydown", key);
      window.removeEventListener("resize", away);
      window.removeEventListener("scroll", away, true);
    };
  }, [root, onClose]);

  const items = () => [...(ref.current?.querySelectorAll<HTMLButtonElement>(":scope > div > [role=menuitem]:not([disabled])") ?? [])];
  const onKey = (e: React.KeyboardEvent) => {
    const list = items();
    const i = list.indexOf(document.activeElement as HTMLButtonElement);
    if (e.key === "ArrowDown") { e.preventDefault(); list[(i + 1) % list.length]?.focus(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); list[(i - 1 + list.length) % list.length]?.focus(); }
    else if (e.key === "Home") { e.preventDefault(); list[0]?.focus(); }
    else if (e.key === "End") { e.preventDefault(); list[list.length - 1]?.focus(); }
    else if (e.key === "ArrowLeft" && onBack) { e.preventDefault(); e.stopPropagation(); onBack(); }
  };

  const openSub = (index: number, el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    setSub({ index, x: r.right + 2, y: r.top - 6 });
  };
  const subEntry = sub ? entries[sub.index] : null;

  return (
    <>
      <div ref={ref} data-ctx-menu role="menu" aria-label={typeof title === "string" ? title : "Acciones"} onKeyDown={onKey}
        style={{ position: "fixed", left: pos.left, top: pos.top }}
        className="z-[60] min-w-56 max-w-80 rounded-[10px] border border-border-strong bg-surface p-1.5 text-[13px] shadow-[0_18px_48px_rgb(0_0_0/0.22)]">
        {title && <p className="code truncate px-2.5 pb-1.5 pt-1 text-2xs uppercase tracking-[0.08em] text-muted">{title}</p>}
        <div className="flex flex-col">
          {entries.map((e, i) => e === "separator"
            ? <div key={i} className="mx-1 my-1.5 h-px bg-border" role="separator" />
            : (
              <button key={i} data-i={i} type="button" role="menuitem" disabled={e.disabled}
                aria-haspopup={e.submenu ? "menu" : undefined} aria-expanded={e.submenu ? sub?.index === i : undefined}
                aria-checked={e.checked === undefined ? undefined : e.checked}
                onMouseEnter={(ev) => (e.submenu ? openSub(i, ev.currentTarget) : setSub(null))}
                onKeyDown={(ev) => {
                  if (e.submenu && (ev.key === "ArrowRight" || ev.key === "Enter" || ev.key === " ")) {
                    ev.preventDefault();
                    openSub(i, ev.currentTarget);
                  }
                }}
                onClick={(ev) => {
                  if (e.submenu) return openSub(i, ev.currentTarget);
                  onClose();
                  e.onSelect?.();
                }}
                className={cx("flex min-h-9 w-full items-center gap-2.5 rounded-[7px] px-2.5 text-left outline-none transition-colors",
                  "hover:bg-subtle focus-visible:bg-subtle disabled:cursor-not-allowed disabled:opacity-45",
                  e.danger ? "text-signal" : "text-fg", e.checked && "font-semibold")}>
                {e.icon && <span className="flex w-3.5 shrink-0 justify-center" aria-hidden>{e.icon}</span>}
                <span className="min-w-0 flex-1 truncate">{e.label}</span>
                {e.checked && <span className="code text-2xs text-muted">actual</span>}
                {e.hint && <span className="code text-2xs text-muted">{e.hint}</span>}
                {e.submenu && <ChevronRight className="size-3.5 text-muted" aria-hidden />}
              </button>
            ))}
        </div>
      </div>
      {sub && subEntry && subEntry !== "separator" && subEntry.submenu && (
        <MenuPanel x={sub.x} y={sub.y} entries={subEntry.submenu} onClose={onClose}
          onBack={() => {
            const i = sub.index;
            setSub(null);
            ref.current?.querySelector<HTMLButtonElement>(`[data-i="${i}"]`)?.focus();
          }} />
      )}
    </>
  );
}
