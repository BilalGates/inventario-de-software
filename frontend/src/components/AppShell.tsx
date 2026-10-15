import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  Building2,
  ClipboardCheck,
  LayoutDashboard,
  LogOut,
  Menu,
  Monitor,
  Moon,
  Package,
  RefreshCw,
  Settings,
  Sun,
  X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL } from "@/lib/format";
import { cx } from "./ui";

const NAV = [
  { to: "/", label: "Panel", icon: LayoutDashboard, end: true },
  { to: "/dispositivos", label: "Dispositivos", icon: Monitor },
  { to: "/software", label: "Software", icon: Package },
  { to: "/departamentos", label: "Departamentos", icon: Building2 },
  { to: "/auditoria", label: "Auditoría", icon: ClipboardCheck },
  { to: "/sincronizacion", label: "Sincronización", icon: RefreshCw },
  { to: "/configuracion", label: "Configuración", icon: Settings },
];

function useTheme(): [boolean, () => void] {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const toggle = () => {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      /* sin almacenamiento */
    }
    setDark(next);
  };
  return [dark, toggle];
}

function Logo() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <svg viewBox="0 0 32 32" className="size-7 shrink-0" aria-hidden>
        <rect width="32" height="32" rx="7" className="fill-accent" />
        <path d="M9 21V11l7-4 7 4v10l-7 4zM9 11l7 4 7-4M16 15v10" fill="none" className="stroke-accent-fg"
          strokeWidth="2.2" strokeLinejoin="round" />
      </svg>
      <div className="leading-tight">
        <p className="text-sm font-semibold">Inventario</p>
        <p className="text-2xs text-muted">Asserta IT</p>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { me, signOut, config } = useAuth();
  const [dark, toggleTheme] = useTheme();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  const { data: alerts } = useQuery({
    queryKey: ["alerts-count"],
    queryFn: () => api.get<{ total: number }>("/alerts", { page_size: 1 }),
    refetchInterval: 60_000,
  });

  const sidebar = (
    <nav aria-label="Principal" className="flex h-full flex-col gap-1 p-3">
      <div className="mb-4 mt-1"><Logo /></div>
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end}
          className={({ isActive }) => cx(
            "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
            isActive ? "bg-subtle font-medium text-fg" : "text-muted hover:bg-subtle/60 hover:text-fg",
          )}>
          <Icon className="size-4" aria-hidden />
          {label}
          {to === "/auditoria" && !!alerts?.total && (
            <span className="num ml-auto rounded-full bg-danger/15 px-1.5 text-2xs font-semibold text-danger">
              {alerts.total}
            </span>
          )}
        </NavLink>
      ))}
      <div className="mt-auto border-t border-border pt-3">
        <div className="px-2.5 pb-2">
          <p className="truncate text-sm font-medium" title={me.upn}>{me.name ?? me.upn}</p>
          <p className="text-2xs text-muted">{ROLE_LABEL[me.role]}{config.auth_mode === "dev" && " · modo desarrollo"}</p>
        </div>
        <div className="flex gap-1">
          <button onClick={toggleTheme} className="rounded-md p-2 text-muted hover:bg-subtle hover:text-fg"
            aria-label={dark ? "Usar tema claro" : "Usar tema oscuro"}>
            {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
          {config.auth_mode === "entra" && (
            <button onClick={signOut} className="rounded-md p-2 text-muted hover:bg-subtle hover:text-fg"
              aria-label="Cerrar sesión"><LogOut className="size-4" /></button>
          )}
          <NavLink to="/auditoria?tab=alertas" className="ml-auto rounded-md p-2 text-muted hover:bg-subtle hover:text-fg"
            aria-label="Alertas"><Bell className="size-4" /></NavLink>
        </div>
      </div>
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:p-2">
        Saltar al contenido
      </a>
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 border-r border-border bg-surface lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} aria-hidden />
          <aside className="relative h-full w-64 border-r border-border bg-surface">
            <button className="absolute right-2 top-3 rounded p-1.5 text-muted hover:bg-subtle" onClick={() => setOpen(false)}
              aria-label="Cerrar menú"><X className="size-4" /></button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-12 items-center gap-2 border-b border-border bg-surface/90 px-4 backdrop-blur lg:hidden">
          <button onClick={() => setOpen(true)} className="rounded p-1.5 text-muted hover:bg-subtle" aria-label="Abrir menú">
            <Menu className="size-5" />
          </button>
          <Logo />
        </header>
        <main id="main" className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
