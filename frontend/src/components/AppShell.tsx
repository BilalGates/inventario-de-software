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
  PanelLeft,
  RefreshCw,
  Settings,
  Sun,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL } from "@/lib/format";
import { GlobalSearch } from "./GlobalSearch";
import { cx } from "./ui";
import { Avatar } from "./Avatar";

interface NavItem { to: string; label: string; icon: LucideIcon; end?: boolean }

const NAV: NavItem[] = [
  { to: "/", label: "Panel", icon: LayoutDashboard, end: true },
  { to: "/dispositivos", label: "Dispositivos", icon: Monitor },
  { to: "/software", label: "Software", icon: Package },
  { to: "/departamentos", label: "Departamentos", icon: Building2 },
  { to: "/auditoria", label: "Auditoría", icon: ClipboardCheck },
  { to: "/sincronizacion", label: "Sincronización", icon: RefreshCw },
];
const SETTINGS: NavItem = { to: "/configuracion", label: "Configuración", icon: Settings };

function readPref(key: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(key);
    return v == null ? fallback : v === "1";
  } catch {
    return fallback;
  }
}
function writePref(key: string, value: boolean) {
  try {
    localStorage.setItem(key, value ? "1" : "0");
  } catch {
    /* sin almacenamiento */
  }
}

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

/** Logo de Asserta (blanco sobre transparente). Plegado muestra solo el globo; desplegado, el logotipo completo. */
function Logo({ full }: { full: boolean }) {
  return (
    <div className={cx("relative h-9 shrink-0 overflow-hidden", full ? "w-[138px]" : "w-9")}>
      <img src="/logo.png" alt="Asserta" width={1351} height={501}
        className="absolute -left-3 -top-3 h-[60px] w-auto max-w-none" />
    </div>
  );
}

function SideLink({ item, expanded, badge }: { item: NavItem; expanded: boolean; badge?: number }) {
  const Icon = item.icon;
  return (
    <NavLink to={item.to} end={item.end} title={expanded ? undefined : item.label}
      aria-label={badge ? `${item.label}, ${badge} alertas abiertas` : item.label}
      className={({ isActive }) => cx(
        "relative flex h-11 items-center gap-3 rounded-md px-[13px] text-[13px] font-medium transition-colors",
        isActive
          ? "bg-white/[0.09] text-white before:absolute before:-left-3.5 before:bottom-3 before:top-3 before:w-0.5 before:rounded before:bg-[#E4572E]"
          : "text-[#9C968F] hover:bg-white/[0.06] hover:text-[#F3F2F0]",
      )}>
      <Icon className="size-[18px] shrink-0" strokeWidth={1.6} aria-hidden />
      {expanded && <span className="flex-1 truncate">{item.label}</span>}
      {!!badge && (expanded
        ? <span className="font-mono text-2xs text-[#FF8A5C]">{badge}</span>
        : <span className="absolute right-2.5 top-2.5 size-1.5 rounded-full bg-[#E4572E]" aria-hidden />)}
    </NavLink>
  );
}

function Sidebar({ expanded, onToggle, alerts, mobile }: { expanded: boolean; onToggle?: () => void; alerts?: number;
  mobile?: boolean }) {
  return (
    <div className="flex h-full flex-col gap-1 bg-side px-3.5 py-5">
      <div className="mb-5 flex h-10 items-center px-1"><Logo full={expanded} /></div>
      {expanded && <p className="eyebrow mb-2 px-[13px] text-[#8A847E]">Inventario</p>}
      <nav aria-label="Principal" className="flex flex-col gap-0.5">
        {NAV.map((item) => (
          <SideLink key={item.to} item={item} expanded={expanded} badge={item.to === "/auditoria" ? alerts : undefined} />
        ))}
      </nav>
      <div className="mt-auto flex flex-col gap-0.5 border-t border-white/[0.07] pt-3">
        <SideLink item={SETTINGS} expanded={expanded} />
        {!mobile && onToggle && (
          <button type="button" onClick={onToggle} aria-expanded={expanded}
            aria-label={expanded ? "Contraer menú" : "Expandir menú"} title={expanded ? undefined : "Expandir menú"}
            className="flex h-11 items-center gap-3 rounded-md px-[13px] text-[13px] font-medium text-[#9C968F] transition-colors hover:bg-white/[0.06] hover:text-[#F3F2F0]">
            <PanelLeft className="size-[18px] shrink-0" strokeWidth={1.6} aria-hidden />
            {expanded && <span>Contraer</span>}
          </button>
        )}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { me, signOut, config } = useAuth();
  const [dark, toggleTheme] = useTheme();
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(() => readPref("sidebar.expanded", false));
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  const { data: alerts } = useQuery({
    queryKey: ["alerts-count"],
    queryFn: () => api.get<{ total: number }>("/alerts", { page_size: 1 }),
    refetchInterval: 60_000,
  });
  const toggleSidebar = () => {
    writePref("sidebar.expanded", !expanded);
    setExpanded(!expanded);
  };
  const displayName = me.name ?? me.upn;
  const iconBtn = "relative inline-flex size-10 items-center justify-center rounded-md text-muted transition-colors hover:bg-bg hover:text-fg";

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:p-2">
        Saltar al contenido
      </a>
      <aside className={cx("sticky top-0 hidden h-screen shrink-0 transition-[width] duration-200 lg:block",
        expanded ? "w-60" : "w-[72px]")}>
        <Sidebar expanded={expanded} onToggle={toggleSidebar} alerts={alerts?.total} />
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} aria-hidden />
          <aside className="relative h-full w-64">
            <button className="absolute right-3 top-6 z-10 rounded p-1.5 text-[#9C968F] hover:text-white" onClick={() => setOpen(false)}
              aria-label="Cerrar menú"><X className="size-4" /></button>
            <Sidebar expanded mobile alerts={alerts?.total} />
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex min-h-16 items-center gap-3 border-b border-border bg-surface/95 px-4 backdrop-blur lg:px-8">
          <button onClick={() => setOpen(true)} className={cx(iconBtn, "lg:hidden")} aria-label="Abrir menú">
            <Menu className="size-5" />
          </button>
          <GlobalSearch />
          <div className="ml-auto flex items-center gap-1">
            <button onClick={toggleTheme} className={iconBtn} aria-label={dark ? "Usar tema claro" : "Usar tema oscuro"}>
              {dark ? <Sun className="size-[18px]" strokeWidth={1.6} /> : <Moon className="size-[18px]" strokeWidth={1.6} />}
            </button>
            <NavLink to="/auditoria?tab=alertas" className={iconBtn}
              aria-label={alerts?.total ? `Alertas, ${alerts.total} abiertas` : "Alertas"}>
              <Bell className="size-[18px]" strokeWidth={1.6} />
              {!!alerts?.total && <span className="absolute right-2.5 top-2.5 size-1.5 rounded-full bg-signal-fill" aria-hidden />}
            </NavLink>
            <div className="ml-2 flex items-center gap-2.5 border-l border-border pl-4">
              <Avatar upn={me.upn} name={displayName} size="md" inverted className="disp" />
              <div className="hidden leading-tight sm:block">
                <p className="max-w-40 truncate text-[13px] font-medium" title={me.upn}>{displayName}</p>
                <p className="text-2xs text-muted">{ROLE_LABEL[me.role]}{config.auth_mode === "dev" && " · desarrollo"}</p>
              </div>
              {config.auth_mode === "entra" && (
                <button onClick={signOut} className={iconBtn} aria-label="Cerrar sesión" title="Cerrar sesión">
                  <LogOut className="size-4" strokeWidth={1.6} />
                </button>
              )}
            </div>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-[1760px] flex-1 px-4 py-8 lg:px-8 lg:py-9">{children}</main>
      </div>
    </div>
  );
}
