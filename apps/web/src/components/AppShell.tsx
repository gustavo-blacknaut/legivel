"use client";

import {
  FilePlus2,
  Files,
  Library,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  ScanText,
  ScrollText,
  Search,
  Settings,
  UserCog,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "@/lib/api/endpoints";
import { initials } from "@/lib/format";
import { useWorkflowText } from "@/lib/workflow-text";
import { useWords } from "@/lib/maintenance-text";
import { workflowJson } from "@/lib/workflow";
import { useT } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import { useStoredValue } from "@/lib/storage";
import { useInstance } from "./Providers";
import styles from "./AppShell.module.css";
import { Brand } from "./Brand";
import { useToast } from "./Toast";

type NavEntry = { href: string; label: string; icon: LucideIcon; permission?: string };
const COLLAPSED_KEY = "legivel:sidebar-collapsed";
const isFlag = (value: unknown): value is "0" | "1" => value === "0" || value === "1";

function NavItem({ entry, collapsed, active }: { entry: NavEntry; collapsed: boolean; active: boolean }) {
  const Icon = entry.icon;
  return (
    <Link
      href={entry.href}
      className={`${styles.item} ${active ? styles.active : ""}`}
      aria-current={active ? "page" : undefined}
      title={collapsed ? entry.label : undefined}
    >
      <Icon size={18} strokeWidth={1.75} />
      <span className={styles.label}>{entry.label}</span>
    </Link>
  );
}

function VerificationBanner() {
  const t = useT();
  const toast = useToast();
  const { user } = useSession();
  const [busy, setBusy] = useState(false);
  if (user.email_verified && !user.pending_email) return null;
  const resend = async () => {
    setBusy(true);
    try {
      const result = await api.resendVerification();
      toast(result.detail, result.emailed ? "ok" : "error");
    } catch (error) {
      toast(error instanceof Error ? error.message : t.common.error, "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={styles.banner} role="status">
      <span>{user.pending_email ? t.banner.pending(user.pending_email) : t.banner.unverified(user.email)}</span>
      <button className="button button-secondary" type="button" onClick={resend} disabled={busy}>
        {t.banner.resend}
      </button>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const t = useT();
  const w = useWorkflowText();
  const words = useWords();
  const sidebar = useRef<HTMLElement>(null);
  const { user, can, logout } = useSession();
  const expirations = useQuery({ queryKey: ["expirations"], queryFn: () => workflowJson<{ total: number }>("/api/expirations"), refetchInterval: 60_000, staleTime: 30_000, enabled: can("documents.view") });
  const instance = useInstance();
  const pathname = usePathname();
  const [collapsedFlag, setCollapsedFlag] = useStoredValue(COLLAPSED_KEY, "0", isFlag);
  const collapsed = collapsedFlag === "1";
  const [drawerPath, setDrawerPath] = useState<string | null>(null);
  const drawerOpen = drawerPath === pathname;
  const setDrawerOpen = (open: boolean) => setDrawerPath(open ? pathname : null);
  useEffect(() => {
    if (!drawerOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sidebar.current?.querySelector<HTMLElement>("a, button")?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerPath(null);
      if (event.key !== "Tab") return;
      const targets = Array.from(sidebar.current?.querySelectorAll<HTMLElement>("a, button:not([disabled])") ?? []).filter((element) => element.getClientRects().length > 0);
      const first = targets[0], last = targets[targets.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = overflow; previous?.focus(); };
  }, [drawerOpen]);

  const toggleCollapsed = () => setCollapsedFlag(collapsed ? "0" : "1");

  const primary: NavEntry[] = [
    { href: "/revisar", label: words("Revisão em lote", "Batch review"), icon: Files, permission: "documents.review" },
    { href: "/vencimentos", label: `${words("Vencimentos", "Expiry alerts")}${expirations.data?.total ? ` (${expirations.data.total})` : ""}`, icon: ScrollText },
    { href: "/fila", label: w.queue, icon: ScanText, permission: "documents.upload" },
    { href: "/organizar", label: w.organize, icon: Library },
    { href: "/pessoas", label: t.nav.people, icon: Users },
    { href: "/documentos", label: t.nav.documents, icon: Files },
    { href: "/novo", label: t.nav.newDocument, icon: FilePlus2, permission: "documents.upload" },
  ];
  const reading: NavEntry[] = [
    { href: "/modelos", label: words("Modelos de documentos", "Document templates"), icon: Library },
    { href: "/importar", label: words("Importar PDF", "Import PDF"), icon: FilePlus2, permission: "documents.upload" },
    { href: "/exportar", label: words("Exportar em lote", "Batch export"), icon: Files, permission: "data.reveal" },
    { href: "/registros", label: t.nav.readings, icon: Library },
    { href: "/leitura", label: t.nav.newReading, icon: ScanText, permission: "documents.upload" },
    { href: "/busca", label: t.nav.search, icon: Search },
  ];
  const secondary: NavEntry[] = [
    { href: "/manutencao", label: words("Manutenção e backups", "Maintenance and backups"), icon: Settings, permission: "settings.manage" },
    { href: "/auditoria", label: t.nav.audit, icon: ScrollText, permission: "audit.view" },
    { href: "/usuarios", label: t.nav.users, icon: UserCog, permission: "users.manage" },
    { href: "/configuracoes", label: t.nav.settings, icon: Settings, permission: "settings.manage" },
  ].filter((entry) => can(entry.permission));
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);
  const shellClass = [styles.shell, collapsed ? styles.collapsed : "", drawerOpen ? styles.drawerOpen : ""].join(" ");

  return (
    <div className={shellClass}>
      <a className="skip-link" href="#conteudo">{words("Ir para o conteúdo", "Skip to content")}</a>
      <aside ref={sidebar} className={styles.sidebar} aria-label={t.nav.main}>
        <div className={styles.head}>
          <Link href="/pessoas" aria-label={t.nav.home(instance.name)}>
            <Brand className={styles.brand} nameClassName={styles.brandName} />
          </Link>
          <button className={`icon-button ${styles.collapseButton}`} type="button" onClick={toggleCollapsed} aria-label={t.nav.collapse} title={t.nav.collapse}>
            <PanelLeftClose size={18} strokeWidth={1.75} />
          </button>
          <button className={`icon-button ${styles.drawerClose}`} type="button" onClick={() => setDrawerOpen(false)} aria-label={t.nav.close}>
            <X size={18} />
          </button>
        </div>
        <nav className={styles.nav}>
          <span className={styles.section}>{t.nav.records}</span>
          {primary
            .filter((entry) => !entry.permission || can(entry.permission))
            .map((entry) => (
              <NavItem key={entry.href} entry={entry} collapsed={collapsed} active={isActive(entry.href)} />
            ))}
          <span className={styles.section}>{t.nav.reading}</span>
          {reading
            .filter((entry) => !entry.permission || can(entry.permission))
            .map((entry) => (
              <NavItem key={entry.href} entry={entry} collapsed={collapsed} active={isActive(entry.href)} />
            ))}
          {secondary.length > 0 && <span className={styles.section}>{t.nav.system}</span>}
          {secondary.map((entry) => (
            <NavItem key={entry.href} entry={entry} collapsed={collapsed} active={isActive(entry.href)} />
          ))}
        </nav>
        <div className={styles.foot}>
          {collapsed && (
            <button className={`${styles.item} ${styles.expandButton}`} type="button" onClick={toggleCollapsed} aria-label={t.nav.expand} title={t.nav.expand}>
              <PanelLeftOpen size={18} strokeWidth={1.75} />
            </button>
          )}
          <Link
            href="/conta"
            className={`${styles.user} ${isActive("/conta") ? styles.userActive : ""}`}
            title={collapsed ? t.nav.account : undefined}
          >
            <span className="avatar">{initials(user.name || user.email)}</span>
            <span className={styles.userText}>
              <span className={styles.userName}>{user.name || user.email}</span>
              <span className={styles.userRole}>{t.roles[user.role]}</span>
            </span>
          </Link>
          <button className={styles.item} type="button" onClick={logout} title={collapsed ? t.nav.logout : undefined}>
            <LogOut size={18} strokeWidth={1.75} />
            <span className={styles.label}>{t.nav.logout}</span>
          </button>
        </div>
      </aside>
      <div className={styles.backdrop} onClick={() => setDrawerOpen(false)} aria-hidden="true" />
      <div className={styles.main} inert={drawerOpen || undefined}>
        <header className={styles.mobileHeader}>
          <button className="icon-button" type="button" onClick={() => setDrawerOpen(true)} aria-label={t.nav.open} aria-expanded={drawerOpen}>
            <Menu size={20} />
          </button>
          <Brand className={styles.brand} nameClassName={styles.brandName} size={26} />
          <span className={styles.spacer} />
          {can("documents.upload") && (
            <Link href="/novo" className="icon-button" aria-label={t.nav.newDocument}>
              <FilePlus2 size={20} strokeWidth={1.75} />
            </Link>
          )}
        </header>
        <VerificationBanner />
        <main id="conteudo" tabIndex={-1}>{children}</main>
      </div>
    </div>
  );
}
