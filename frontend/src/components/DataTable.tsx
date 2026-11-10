import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Columns3, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Button, EmptyState, ErrorState, Spinner, cx } from "./ui";

export interface Column<T> {
  id: string;
  header: string;
  cell: (row: T) => ReactNode;
  /** Clave de ordenación en la API; si falta, la columna no se ordena. */
  sortKey?: string;
  hidden?: boolean;
  className?: string;
  align?: "right";
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string | number;
  total?: number;
  loading?: boolean;
  error?: unknown;
  retry?: () => void;
  page?: number;
  pageSize?: number;
  onPage?: (page: number) => void;
  sort?: string | null;
  onSort?: (sort: string | null) => void;
  selectable?: boolean;
  selected?: Set<number | string>;
  onSelectedChange?: (s: Set<number | string>) => void;
  storageKey?: string;
  toolbar?: ReactNode;
  search?: string;
  onSearch?: (q: string) => void;
  searchPlaceholder?: string;
  empty?: ReactNode;
  rowClassName?: (row: T) => string | undefined;
  bulkActions?: ReactNode;
  /** Fila superior opcional (p. ej. pestañas de estado), sobre la barra de herramientas. */
  header?: ReactNode;
}

function readHidden(key: string | undefined, cols: Column<unknown>[]): Set<string> {
  const fallback = new Set(cols.filter((c) => c.hidden).map((c) => c.id));
  if (!key) return fallback;
  try {
    const raw = localStorage.getItem(`cols:${key}`);
    return raw ? new Set(JSON.parse(raw) as string[]) : fallback;
  } catch {
    return fallback;
  }
}

export function DataTable<T>(p: Props<T>) {
  const [hidden, setHidden] = useState<Set<string>>(() => readHidden(p.storageKey, p.columns as Column<unknown>[]));
  const [showCols, setShowCols] = useState(false);
  const [menuPos, setMenuPos] = useState<CSSProperties>();
  const [q, setQ] = useState(p.search ?? "");
  const colsRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const visible = useMemo(() => p.columns.filter((c) => !hidden.has(c.id)), [p.columns, hidden]);

  useEffect(() => {
    if (!p.onSearch) return;
    const t = setTimeout(() => q !== (p.search ?? "") && p.onSearch?.(q), 300);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!showCols) return;
    // El menú se pinta fuera de la tarjeta (que recorta su contenido) y se coloca bajo el botón.
    const place = () => {
      const r = colsRef.current?.getBoundingClientRect();
      if (!r) return;
      const below = window.innerHeight - r.bottom - 12;
      const above = r.top - 12;
      const up = below < 240 && above > below;
      setMenuPos({
        position: "fixed", right: Math.max(8, window.innerWidth - r.right),
        ...(up ? { bottom: window.innerHeight - r.top + 4 } : { top: r.bottom + 4 }),
        maxHeight: Math.max(160, up ? above : below),
      });
    };
    place();
    const close = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!colsRef.current?.contains(t) && !menuRef.current?.contains(t)) setShowCols(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setShowCols(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [showCols]);

  const toggleCol = (id: string) => {
    const next = new Set(hidden);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setHidden(next);
    try {
      if (p.storageKey) localStorage.setItem(`cols:${p.storageKey}`, JSON.stringify([...next]));
    } catch {
      /* almacenamiento no disponible */
    }
  };

  const rows = p.rows ?? [];
  const keys = rows.map(p.rowKey);
  const selected = p.selected ?? new Set();
  const allSelected = keys.length > 0 && keys.every((k) => selected.has(k));
  const toggleAll = () => {
    const next = new Set(selected);
    keys.forEach((k) => (allSelected ? next.delete(k) : next.add(k)));
    p.onSelectedChange?.(next);
  };
  const toggleRow = (k: number | string) => {
    const next = new Set(selected);
    if (next.has(k)) next.delete(k);
    else next.add(k);
    p.onSelectedChange?.(next);
  };

  const sortBy = (c: Column<T>) => {
    if (!c.sortKey || !p.onSort) return;
    if (p.sort === c.sortKey) p.onSort(`-${c.sortKey}`);
    else if (p.sort === `-${c.sortKey}`) p.onSort(null);
    else p.onSort(c.sortKey);
  };

  const page = p.page ?? 1;
  const pageSize = p.pageSize ?? rows.length;
  const total = p.total ?? rows.length;
  const pages = Math.max(1, Math.ceil(total / Math.max(pageSize, 1)));

  return (
    <div className="card overflow-hidden">
      {p.header && <div className="border-b border-border px-4">{p.header}</div>}
      <div className="flex flex-wrap items-center gap-2 border-b border-border p-3">
        {p.onSearch && (
          <div className="relative min-w-52 flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted" aria-hidden />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={p.searchPlaceholder ?? "Buscar…"}
              aria-label="Buscar"
              className="field pl-8"
            />
          </div>
        )}
        {p.toolbar}
        <div className="ml-auto flex items-center gap-2">
          {selected.size > 0 && p.bulkActions && (
            <div className="flex items-center gap-2 rounded-md bg-fg px-2 py-1 text-bg [&_button]:text-bg">
              <span className="text-xs font-medium">{selected.size} seleccionados</span>
              {p.bulkActions}
            </div>
          )}
          <div className="relative" ref={colsRef}>
            <Button size="sm" variant="ghost" icon={<Columns3 className="size-4" />} aria-expanded={showCols}
              onClick={() => setShowCols((v) => !v)}>
              Columnas
            </Button>
            {showCols && menuPos && createPortal(
              <div ref={menuRef} style={menuPos}
                className="z-50 w-56 overflow-y-auto overscroll-contain rounded-md border border-border bg-surface p-1.5 text-[13px] shadow-[0_8px_24px_rgb(0_0_0/0.12)]">
                {p.columns.map((c) => (
                  <label key={c.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 hover:bg-subtle">
                    <input type="checkbox" checked={!hidden.has(c.id)} onChange={() => toggleCol(c.id)} />
                    {c.header}
                  </label>
                ))}
              </div>,
              document.body,
            )}
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-surface/95 font-mono text-2xs uppercase tracking-[0.06em] text-muted backdrop-blur">
            <tr>
              {p.selectable && (
                <th className="w-10 py-3 pl-4 pr-1">
                  <input type="checkbox" aria-label="Seleccionar todos" checked={allSelected} onChange={toggleAll} />
                </th>
              )}
              {visible.map((c) => {
                const dir = p.sort === c.sortKey ? "asc" : p.sort === `-${c.sortKey}` ? "desc" : null;
                return (
                  <th key={c.id} scope="col" aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : undefined}
                    className={cx("whitespace-nowrap border-b border-border px-3 py-3 font-medium first:pl-4 last:pr-4", c.align === "right" && "text-right", c.className)}>
                    {c.sortKey && p.onSort ? (
                      <button onClick={() => sortBy(c)} className="inline-flex items-center gap-1 uppercase hover:text-fg">
                        {c.header}
                        {dir === "asc" && <ArrowUp className="size-3" aria-hidden />}
                        {dir === "desc" && <ArrowDown className="size-3" aria-hidden />}
                      </button>
                    ) : c.header}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {!p.loading && !p.error && rows.map((row) => {
              const k = p.rowKey(row);
              return (
                <tr key={k} className={cx("border-t border-border first:border-t-0 transition-colors hover:bg-bg",
                  selected.has(k) && "bg-fg/[0.04]", p.rowClassName?.(row))}>
                  {p.selectable && (
                    <td className="py-3 pl-4 pr-1">
                      <input type="checkbox" aria-label="Seleccionar fila" checked={selected.has(k)}
                        onChange={() => toggleRow(k)} />
                    </td>
                  )}
                  {visible.map((c) => (
                    <td key={c.id} className={cx("whitespace-nowrap px-3 py-3 align-middle first:pl-4 last:pr-4", c.align === "right" && "num text-right", c.className)}>
                      {c.cell(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
        {p.loading && <Spinner />}
        {!p.loading && p.error != null && <ErrorState error={p.error} retry={p.retry} />}
        {!p.loading && !p.error && rows.length === 0 && (p.empty ?? <EmptyState title="Sin resultados">
          Ajuste la búsqueda o los filtros.</EmptyState>)}
      </div>

      {p.onPage && total > 0 && (
        <div className="flex items-center justify-between gap-2 border-t border-border px-4 py-2.5 text-xs text-muted">
          <span className="code">
            {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} de {total.toLocaleString("es-ES")}
          </span>
          <div className="flex items-center gap-1">
            <Button size="sm" variant="ghost" aria-label="Página anterior" disabled={page <= 1}
              onClick={() => p.onPage!(page - 1)}><ChevronLeft className="size-4" /></Button>
            <span className="code px-1">{page} / {pages}</span>
            <Button size="sm" variant="ghost" aria-label="Página siguiente" disabled={page >= pages}
              onClick={() => p.onPage!(page + 1)}><ChevronRight className="size-4" /></Button>
          </div>
        </div>
      )}
    </div>
  );
}
