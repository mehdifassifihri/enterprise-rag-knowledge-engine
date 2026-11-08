"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { z } from "zod";
import {
  Activity,
  ArrowRight,
  Command,
  Layers3,
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  Database,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Moon,
  Search,
  Settings2,
  ShieldCheck,
  Sun,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "./ui/button";
import { Modal } from "./ui/dialog";
const navigation = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/knowledge", label: "Knowledge base", icon: BookOpen },
  { href: "/assistant", label: "AI assistant", icon: MessageSquare },
  { href: "/playground", label: "Retrieval playground", icon: Search },
  { href: "/evaluation", label: "Evaluation lab", icon: FlaskConical },
  { href: "/settings", label: "Settings & integrations", icon: Settings2 },
];
export function Brand() {
  return (
    <div className="wordmark">
      <span className="brand-symbol" aria-hidden="true">
        <Layers3 size={21} strokeWidth={2} />
      </span>
      <span>
        Knowledge<span className="brand-suffix"> Engine</span>
      </span>
    </div>
  );
}
export function AppSidebar({
  mobile = false,
  onNavigate,
}: {
  mobile?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <aside className={`sidebar ${mobile ? "mobile-sidebar" : ""}`}>
      <Link
        href="/dashboard"
        onClick={onNavigate}
        aria-label="Knowledge Engine overview"
      >
        <Brand />
      </Link>
      <div className="workspace-picker">
        <div className="workspace-icon">
          <Database size={17} />
        </div>
        <div>
          <strong style={{ fontSize: 13, fontWeight: 600 }}>
            Demo workspace
          </strong>
          <div className="muted" style={{ fontSize: 11 }}>
            Private knowledge space
          </div>
        </div>
      </div>
      {[
        { title: "Workspace", items: navigation.slice(0, 3) },
        { title: "Explore & manage", items: navigation.slice(3) },
      ].map((group) => (
        <div className="nav-section" key={group.title}>
          <p className="eyebrow">{group.title}</p>
          <nav aria-label={`${group.title} navigation`}>
            {group.items.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`nav-link ${pathname === href ? "active" : ""}`}
                aria-label={label}
                title={label}
                aria-current={pathname === href ? "page" : undefined}
                onClick={onNavigate}
              >
                <Icon />
                <span>{label}</span>
                {pathname === href && <span className="nav-active-dot" />}
              </Link>
            ))}
          </nav>
        </div>
      ))}
      <div className="sidebar-bottom">
        <div className="local-note">
          <ShieldCheck
            size={16}
            className="text-primary"
            style={{ marginBottom: 8 }}
          />
          <p className="sidebar-note-title">Private by design</p>
          <p style={{ fontSize: 12, marginTop: 6 }}>
            Your documents stay within your authorized workspace.
          </p>
        </div>
        <Link className="nav-link" href="/settings" onClick={onNavigate}>
          <Database />
          Integration guide
          <ArrowUpRight size={12} style={{ marginLeft: "auto" }} />
        </Link>
      </div>
    </aside>
  );
}
export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { resolvedTheme, setTheme } = useTheme();
  const [menu, setMenu] = useState(false);
  const [command, setCommand] = useState(false);
  const [filter, setFilter] = useState("");
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommand((value) => !value);
      }
    };
    document.addEventListener("keydown", keydown);
    return () => document.removeEventListener("keydown", keydown);
  }, []);
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api("ready", z.object({ status: z.string() })),
    refetchInterval: 30000,
    retry: false,
  });
  return (
    <>
      <header className="app-header">
        <div className="row">
          <Button
            className="mobile-menu"
            variant="ghost"
            size="icon"
            aria-label="Open navigation"
            onClick={() => setMenu(true)}
          >
            <Menu size={18} />
          </Button>
          <div className="breadcrumb">
            <span className="crumb-workspace">Workspace</span>
            <ChevronRight size={12} className="muted" />
            <span>
              {navigation.find((n) => n.href === pathname)?.label ||
                "Workspace"}
            </span>
          </div>
        </div>
        <button
          className="workspace-search"
          onClick={() => {
            setFilter("");
            setCommand(true);
          }}
          aria-label="Search workspace navigation"
        >
          <Search size={17} />
          <span>Find your way around...</span>
          <kbd>
            <Command size={11} /> K
          </kbd>
        </button>
        <div className="header-actions">
          <span
            className={`pill ${health.isSuccess ? "ready" : ""}`}
            title="Database readiness; external providers are not probed"
          >
            <span className="dot" />
            <span className="health-label">
              {health.isPending
                ? "Connecting"
                : health.isSuccess
                  ? "Backend ready"
                  : "Backend unavailable"}
            </span>
          </span>
          <span className="header-divider" />
          <Button
            variant="ghost"
            size="icon"
            aria-label="Toggle color theme"
            onClick={() =>
              setTheme(resolvedTheme === "dark" ? "light" : "dark")
            }
          >
            <Sun size={16} className="hidden dark:block" />
            <Moon size={16} className="dark:hidden" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Sign out"
            onClick={async () => {
              await fetch("/api/session", { method: "DELETE" });
              queryClient.clear();
              router.push("/login");
            }}
          >
            <LogOut size={16} />
          </Button>
          <div className="header-profile" title="Shared demo session">
            <div className="avatar">KE</div>
            <div>
              <strong>Demo workspace</strong>
              <span>Shared session</span>
            </div>
          </div>
        </div>
      </header>
      <Modal
        open={command}
        onOpenChange={setCommand}
        title="Go to your workspace"
        description="Find a page. Use ⌘K or Ctrl+K to open this menu."
      >
        <div className="input-wrap">
          <Search size={17} />
          <input
            className="input"
            aria-label="Find a workspace page"
            placeholder="Search pages..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <nav className="command-results" aria-label="Workspace page results">
          {navigation
            .filter((item) =>
              item.label.toLowerCase().includes(filter.toLowerCase()),
            )
            .map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href} onClick={() => setCommand(false)}>
                <Icon size={18} />
                <span className="spacer">{label}</span>
                <ArrowRight size={15} />
              </Link>
            ))}
          {!navigation.some((item) =>
            item.label.toLowerCase().includes(filter.toLowerCase()),
          ) && (
            <p className="muted small">
              No matching pages. Try “knowledge” or “settings”.
            </p>
          )}
        </nav>
      </Modal>
      <Modal
        open={menu}
        onOpenChange={setMenu}
        title="Navigation"
        description="Your knowledge workspace"
      >
        <AppSidebar mobile onNavigate={() => setMenu(false)} />
      </Modal>
    </>
  );
}
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: async () =>
      z
        .object({ authenticated: z.boolean() })
        .parse(
          await (await fetch("/api/session", { cache: "no-store" })).json(),
        ),
    retry: false,
  });
  if (pathname === "/login") return <>{children}</>;
  if (!session.data?.authenticated)
    return (
      <main className="login-page">
        <div className="card login-card">
          <Brand />
          <h1>
            {session.isPending
              ? "Opening your workspace"
              : "Sign in to your workspace"}
          </h1>
          <p>
            {session.isError
              ? "The session service is unavailable. Please try again."
              : "Knowledge access is protected by a server-side demo session."}
          </p>
          {!session.isPending && (
            <Button onClick={() => router.push("/login")}>
              Continue to sign in
            </Button>
          )}
        </div>
      </main>
    );
  return (
    <div
      className={`app-shell ${pathname === "/assistant" ? "assistant-shell" : ""}`}
    >
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <AppSidebar />
      <div className="main-shell">
        <AppHeader />
        <main className="content" id="main">
          {children}
          <footer className="page-footer">
            <span>Enterprise Knowledge Engine</span>
            <span className="row">
              <Activity size={11} /> Evidence first. Answers second.
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
