import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Columns3, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
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
  const [q, setQ] = useState(p.search ?? "");
  const colsRef = useRef<HTMLDivElement>(null);
  const visible = useMemo(() => p.columns.filter((c) => !hidden.has(c.id)), [p.columns, hidden]);

  useEffect(() => {
    if (!p.onSearch) return;
    const t = setTimeout(() => q !== (p.search ?? "") && p.onSearch?.(q), 300);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!showCols) return;
    const close = (e: MouseEvent) => !colsRef.current?.contains(e.target as Node) && setShowCols(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
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
      <div className="flex flex-wrap items-center gap-2 border-b border-border p-2.5">
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
            <div className="flex items-center gap-2 rounded-md bg-accent/10 px-2 py-1">
              <span className="text-xs font-medium text-accent">{selected.size} seleccionados</span>
              {p.bulkActions}
            </div>
          )}
          <div className="relative" ref={colsRef}>
            <Button size="sm" variant="ghost" icon={<Columns3 className="size-4" />} aria-expanded={showCols}
              onClick={() => setShowCols((v) => !v)}>
              Columnas
            </Button>
            {showCols && (
              <div className="card absolute right-0 z-20 mt-1 w-56 p-1.5 shadow-lg">
                {p.columns.map((c) => (
                  <label key={c.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 hover:bg-subtle">
                    <input type="checkbox" checked={!hidden.has(c.id)} onChange={() => toggleCol(c.id)}
                      className="accent-[rgb(var(--accent))]" />
                    {c.header}
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-subtle/80 text-xs text-muted backdrop-blur">
            <tr>
              {p.selectable && (
                <th className="w-9 px-3 py-2">
                  <input type="checkbox" aria-label="Seleccionar todos" checked={allSelected} onChange={toggleAll}
                    className="accent-[rgb(var(--accent))]" />
                </th>
              )}
              {visible.map((c) => {
                const dir = p.sort === c.sortKey ? "asc" : p.sort === `-${c.sortKey}` ? "desc" : null;
                return (
                  <th key={c.id} scope="col" aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : undefined}
                    className={cx("whitespace-nowrap px-3 py-2 font-medium", c.align === "right" && "text-right", c.className)}>
                    {c.sortKey && p.onSort ? (
                      <button onClick={() => sortBy(c)} className="inline-flex items-center gap-1 hover:text-fg">
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
                <tr key={k} className={cx("border-t border-border transition-colors hover:bg-subtle/60",
                  selected.has(k) && "bg-accent/5", p.rowClassName?.(row))}>
                  {p.selectable && (
                    <td className="px-3 py-2">
                      <input type="checkbox" aria-label="Seleccionar fila" checked={selected.has(k)}
                        onChange={() => toggleRow(k)} className="accent-[rgb(var(--accent))]" />
                    </td>
                  )}
                  {visible.map((c) => (
                    <td key={c.id} className={cx("whitespace-nowrap px-3 py-2 align-middle", c.align === "right" && "num text-right", c.className)}>
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
        <div className="flex items-center justify-between gap-2 border-t border-border px-3 py-2 text-xs text-muted">
          <span className="num">
            {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} de {total.toLocaleString("es-ES")}
          </span>
          <div className="flex items-center gap-1">
            <Button size="sm" variant="ghost" aria-label="Página anterior" disabled={page <= 1}
              onClick={() => p.onPage!(page - 1)}><ChevronLeft className="size-4" /></Button>
            <span className="num px-1">{page} / {pages}</span>
            <Button size="sm" variant="ghost" aria-label="Página siguiente" disabled={page >= pages}
              onClick={() => p.onPage!(page + 1)}><ChevronRight className="size-4" /></Button>
          </div>
        </div>
      )}
    </div>
  );
}
