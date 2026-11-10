import { useQuery } from "@tanstack/react-query";
import { Building2, Loader2, Monitor, Package, Search, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useDepartments } from "@/lib/queries";
import type { DeviceRow, Paged, Product } from "@/lib/types";
import { cx } from "./ui";

const LIMIT = 5;

interface Hit { key: string; to: string; title: string; sub?: string }
interface Group { id: "devices" | "software" | "departments"; label: string; icon: LucideIcon; hits: Hit[]; total: number;
  all?: string }

const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** Buscador de la cabecera: busca a la vez en equipos, software y departamentos. */
export function GlobalSearch() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();
  const box = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const term = useDebounced(q.trim(), 200);
  const enabled = term.length >= 2;

  // Cierra el desplegable al cambiar de página.
  useEffect(() => setOpen(false), [location.pathname, location.search]);
  useEffect(() => {
    const onDown = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "/" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement
        || e.target instanceof HTMLSelectElement || (e.target as HTMLElement)?.isContentEditable)) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const devices = useQuery({
    queryKey: ["global-search", "devices", term],
    queryFn: () => api.get<Paged<DeviceRow>>("/devices", { q: term, page_size: LIMIT }),
    enabled, staleTime: 30_000,
  });
  const software = useQuery({
    queryKey: ["global-search", "software", term],
    queryFn: () => api.get<Paged<Product>>("/software", { q: term, page_size: LIMIT }),
    enabled, staleTime: 30_000,
  });
  const depts = useDepartments();

  const groups = useMemo<Group[]>(() => {
    if (!enabled) return [];
    const enc = encodeURIComponent(term);
    const n = norm(term);
    const deptHits = (depts.data?.items ?? []).filter((d) =>
      [d.name, d.code, d.manager ?? "", d.cost_center ?? ""].some((s) => norm(s).includes(n)));
    const out: Group[] = [
      { id: "devices", label: "Equipos", icon: Monitor, total: devices.data?.total ?? 0, all: `/dispositivos?q=${enc}`,
        hits: (devices.data?.items ?? []).map((d) => ({
          key: `d${d.id}`, to: `/dispositivos/${d.id}`, title: d.name,
          sub: [d.primary_user, d.serial_number, d.department].filter(Boolean).join(" · ") || undefined,
        })) },
      { id: "software", label: "Software", icon: Package, total: software.data?.total ?? 0, all: `/software?q=${enc}`,
        hits: (software.data?.items ?? []).map((p) => ({
          key: `s${p.id}`, to: `/software/${p.id}`, title: p.name,
          sub: [p.publisher, `${p.devices} equipo${p.devices === 1 ? "" : "s"}`].filter(Boolean).join(" · "),
        })) },
      { id: "departments", label: "Departamentos", icon: Building2, total: deptHits.length,
        hits: deptHits.slice(0, LIMIT).map((d) => ({
          key: `p${d.id}`, to: `/departamentos/${d.id}`, title: d.name, sub: d.manager ?? d.code,
        })) },
    ];
    return out.filter((g) => g.hits.length > 0);
  }, [enabled, term, devices.data, software.data, depts.data]);

  // Lista plana navegable con teclado: resultados + «Ver todos» de cada grupo.
  const flat = useMemo(() => groups.flatMap((g) => [
    ...g.hits.map((h) => h.to),
    ...(g.all && g.total > g.hits.length ? [g.all] : []),
  ]), [groups]);
  useEffect(() => setActive(0), [term]);

  const loading = enabled && (devices.isFetching || software.isFetching);
  const go = (to: string) => {
    setOpen(false);
    input.current?.blur();
    navigate(to);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = q.trim();
    if (!t) return;
    if (open && flat[active] && term === t) return go(flat[active]);
    // Sin resultados cargados aún: ir a la lista que tenga coincidencias, o a equipos por defecto.
    const best = term === t ? groups.find((g) => g.all)?.all : undefined;
    go(best ?? `/dispositivos?q=${encodeURIComponent(t)}`);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      if (open) setOpen(false); else setQ("");
      return;
    }
    if (!flat.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => (a + 1) % flat.length); }
    if (e.key === "ArrowUp") { e.preventDefault(); setOpen(true); setActive((a) => (a - 1 + flat.length) % flat.length); }
  };

  const show = open && enabled;
  let idx = -1;
  const optionCls = (i: number) => cx("flex w-full items-center gap-3 px-3 py-2 text-left text-[13px]",
    i === active ? "bg-bg text-fg" : "text-fg-2 hover:bg-bg");

  return (
    <div ref={box} className="relative flex min-w-0 max-w-md flex-1">
      <form role="search" onSubmit={submit} className="w-full">
        <label htmlFor="global-search" className="sr-only">Buscar en el inventario</label>
        <div className="flex h-10 w-full items-center gap-2.5 rounded-md border border-border-strong px-3 text-muted focus-within:border-fg">
          {loading ? <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden />
            : <Search className="size-4 shrink-0" aria-hidden />}
          <input ref={input} id="global-search" type="search" value={q} autoComplete="off"
            role="combobox" aria-expanded={show} aria-controls="global-search-results" aria-autocomplete="list"
            onChange={(e) => { setQ(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)} onKeyDown={onKeyDown}
            placeholder="Buscar equipos, software, usuarios…"
            className="min-w-0 flex-1 bg-transparent text-[13px] text-fg outline-none placeholder:text-muted" />
          <kbd className="hidden rounded border border-border px-1.5 font-mono text-2xs text-muted md:inline">/</kbd>
        </div>
      </form>
      {show && (
        <div id="global-search-results" role="listbox"
          className="absolute left-0 right-0 top-full z-40 mt-1 max-h-[70vh] overflow-y-auto rounded-md border border-border bg-surface py-1 shadow-lg">
          {groups.length === 0 ? (
            <p className="px-3 py-4 text-center text-[13px] text-muted">
              {loading || term !== q.trim() ? "Buscando…" : `Sin resultados para «${term}»`}
            </p>
          ) : groups.map((g) => {
            const Icon = g.icon;
            return (
              <div key={g.id} className="border-b border-border py-1 last:border-b-0">
                <p className="eyebrow flex items-center justify-between px-3 py-1.5 text-muted">
                  <span>{g.label}</span><span className="font-mono">{g.total}</span>
                </p>
                {g.hits.map((h) => {
                  const i = ++idx;
                  return (
                    <button key={h.key} type="button" role="option" aria-selected={i === active}
                      onMouseEnter={() => setActive(i)} onClick={() => go(h.to)} className={optionCls(i)}>
                      <Icon className="size-4 shrink-0 text-muted" strokeWidth={1.6} aria-hidden />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-fg">{h.title}</span>
                        {h.sub && <span className="block truncate text-2xs text-muted">{h.sub}</span>}
                      </span>
                    </button>
                  );
                })}
                {g.all && g.total > g.hits.length && (() => {
                  const i = ++idx;
                  return (
                    <button type="button" role="option" aria-selected={i === active}
                      onMouseEnter={() => setActive(i)} onClick={() => go(g.all!)}
                      className={cx(optionCls(i), "pl-10 text-2xs")}>
                      Ver los {g.total} resultados en {g.label.toLowerCase()} →
                    </button>
                  );
                })()}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
