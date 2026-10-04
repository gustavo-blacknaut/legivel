import {
  BookOpen,
  CreditCard,
  FilePlus2,
  Files,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Receipt,
  ScanLine,
  ScrollText,
  Search,
  Settings,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth";

type NavEntry = { to: string; label: string; icon: LucideIcon };

const SEARCH: NavEntry[] = [{ to: "/busca", label: "Busca", icon: Search }];
const IDENTITY: NavEntry[] = [
  { to: "/pessoas", label: "Pessoas", icon: Users },
  { to: "/documentos", label: "Documentos", icon: Files },
  { to: "/novo", label: "Novo documento", icon: FilePlus2 },
];
const MODULES: NavEntry[] = [
  { to: "/modulos/cards", label: "Cartões", icon: CreditCard },
  { to: "/modulos/books", label: "Livros e textos", icon: BookOpen },
  { to: "/modulos/scanner", label: "Digitalização", icon: ScanLine },
  { to: "/modulos/finance", label: "Financeiro", icon: Receipt },
];
const SYSTEM: NavEntry[] = [
  { to: "/auditoria", label: "Auditoria", icon: ScrollText },
];
const COLLAPSED_KEY = "lince:sidebar-collapsed";

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="brand">
      <img src="/favicon.svg" alt="" width={compact ? 26 : 28} height={compact ? 26 : 28} />
      <span className="brand-name">Lince</span>
    </span>
  );
}

function NavItem({ entry, collapsed }: { entry: NavEntry; collapsed: boolean }) {
  const Icon = entry.icon;
  return (
    <NavLink to={entry.to} className="nav-item" title={collapsed ? entry.label : undefined}>
      <Icon size={18} strokeWidth={1.75} />
      <span className="nav-label">{entry.label}</span>
    </NavLink>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => setDrawerOpen(false), [location.pathname]);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    try {
      window.localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
    } catch {
      return;
    }
  };

  const className = ["shell", collapsed ? "collapsed" : "", drawerOpen ? "drawer-open" : ""].filter(Boolean).join(" ");

  return (
    <div className={className}>
      <aside className="sidebar" aria-label="Navegação principal">
        <div className="sidebar-head">
          <NavLink to="/busca" aria-label="Lince, página inicial">
            <Brand />
          </NavLink>
          <button
            className="icon-button collapse-button"
            type="button"
            onClick={toggleCollapsed}
            aria-label="Recolher menu"
            title="Recolher menu"
          >
            <PanelLeftClose size={18} strokeWidth={1.75} />
          </button>
          <button className="icon-button drawer-close" type="button" onClick={() => setDrawerOpen(false)} aria-label="Fechar menu">
            <X size={18} />
          </button>
        </div>
        <nav className="nav">
          {SEARCH.map((entry) => (
            <NavItem key={entry.to} entry={entry} collapsed={collapsed} />
          ))}
          <span className="nav-section">Identidade</span>
          {IDENTITY.map((entry) => (
            <NavItem key={entry.to} entry={entry} collapsed={collapsed} />
          ))}
          <span className="nav-section">Módulos</span>
          {MODULES.map((entry) => (
            <NavItem key={entry.to} entry={entry} collapsed={collapsed} />
          ))}
          <span className="nav-section">Sistema</span>
          {SYSTEM.map((entry) => (
            <NavItem key={entry.to} entry={entry} collapsed={collapsed} />
          ))}
        </nav>
        <div className="sidebar-foot">
          {collapsed && (
            <button className="nav-item nav-button" type="button" onClick={toggleCollapsed} aria-label="Expandir menu" title="Expandir menu">
              <PanelLeftOpen size={18} strokeWidth={1.75} />
            </button>
          )}
          <NavLink to="/configuracoes" className="sidebar-user" title={collapsed ? "Administração" : undefined}>
            <span className="avatar">{user?.username.slice(0, 1).toUpperCase()}</span>
            <span className="sidebar-user-text">
              <span className="sidebar-user-name">{user?.username}</span>
              <span className="sidebar-user-role">Administração</span>
            </span>
            <Settings size={16} strokeWidth={1.75} className="sidebar-user-icon" />
          </NavLink>
          <button
            className="nav-item nav-button"
            type="button"
            onClick={logout}
            title={collapsed ? "Sair" : undefined}
          >
            <LogOut size={18} strokeWidth={1.75} />
            <span className="nav-label">Sair</span>
          </button>
        </div>
      </aside>
      <div className="drawer-backdrop" onClick={() => setDrawerOpen(false)} />
      <div className="main">
        <header className="mobile-header">
          <button className="icon-button" type="button" onClick={() => setDrawerOpen(true)} aria-label="Abrir menu" aria-expanded={drawerOpen}>
            <Menu size={20} />
          </button>
          <Brand compact />
          <span className="spacer" />
          <NavLink to="/novo" className="icon-button" aria-label="Novo documento">
            <FilePlus2 size={20} strokeWidth={1.75} />
          </NavLink>
        </header>
        {children}
      </div>
    </div>
  );
}

type PageHeadProps = {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  back?: ReactNode;
};

export function PageHead({ title, description, actions, back }: PageHeadProps) {
  return (
    <div className="page-head">
      <div>
        {back}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions}
    </div>
  );
}
