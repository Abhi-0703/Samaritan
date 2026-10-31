"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "@/components/theme-provider";
import { useState } from "react";
import {
  CircleHelp,
  Gauge,
  LayoutDashboard,
  ListChecks,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  PhoneCall,
  Sun,
  Users,
} from "lucide-react";
import { AboutDialog } from "@/components/about-dialog";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { usePersistentFlag } from "@/lib/hooks/use-persistent-flag";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/calls", label: "Calls", icon: PhoneCall },
  { href: "/agents", label: "Agents", icon: Users },
  { href: "/rules", label: "Rules", icon: ListChecks },
  { href: "/accuracy", label: "Accuracy", icon: Gauge },
] as const;

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function ThemeToggle({ collapsed }: { collapsed: boolean }) {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size={collapsed ? "icon" : "sm"}
      className={cn("text-muted-foreground", !collapsed && "justify-start")}
      aria-label="Toggle light and dark theme"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    >
      <Moon aria-hidden className="dark:hidden" />
      <Sun aria-hidden className="hidden dark:block" />
      {!collapsed && <span>Theme</span>}
    </Button>
  );
}

function CurrentNav({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  return <NavList pathname={usePathname()} collapsed={collapsed} onNavigate={onNavigate} />;
}

function NavList({ pathname, collapsed, onNavigate }: { pathname: string | null; collapsed: boolean; onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="flex-1 space-y-0.5 p-2">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname !== null && isActive(pathname, href);
        const link = (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            aria-label={collapsed ? label : undefined}
            className={cn(
              "flex h-8 items-center gap-2 rounded-lg px-2 font-medium text-foreground transition-colors duration-150 hover:bg-sidebar-accent aria-[current=page]:bg-brand-subtle aria-[current=page]:text-brand-text",
              collapsed && "justify-center",
            )}
          >
            <Icon aria-hidden className="size-4 shrink-0" />
            {!collapsed && <span>{label}</span>}
          </Link>
        );
        return collapsed ? (
          <Tooltip key={href}>
            <TooltipTrigger render={link} />
            <TooltipContent side="right">{label}</TooltipContent>
          </Tooltip>
        ) : (
          link
        );
      })}
    </nav>
  );
}

function SidebarBody({
  collapsed,
  onNavigate,
  onToggleCollapsed,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
  onToggleCollapsed?: () => void;
}) {
  const [aboutOpen, setAboutOpen] = useState(false);
  return (
    <div className="flex h-full flex-col">
      <div className={cn("flex h-14 shrink-0 items-center border-b border-sidebar-border", collapsed ? "justify-center" : "px-4")}>
        {collapsed ? (
          <span className="font-semibold" aria-label="Samaritan">
            S
          </span>
        ) : (
          <div className="min-w-0">
            <p className="font-semibold leading-5">Samaritan</p>
            <p className="truncate text-xs text-muted-foreground">Sahyog Finance · Collections QA</p>
          </div>
        )}
      </div>

      <CurrentNav collapsed={collapsed} onNavigate={onNavigate} />

      <div className="space-y-1 border-t border-sidebar-border p-2">
        <ThemeToggle collapsed={collapsed} />
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "sm"}
          className={cn("text-muted-foreground", !collapsed && "w-full justify-start")}
          aria-label="About Samaritan"
          onClick={() => setAboutOpen(true)}
        >
          <CircleHelp aria-hidden />
          {!collapsed && <span>About</span>}
        </Button>
        {onToggleCollapsed && (
          <Button
            variant="ghost"
            size={collapsed ? "icon" : "sm"}
            className={cn("text-muted-foreground", !collapsed && "w-full justify-start")}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={onToggleCollapsed}
          >
            {collapsed ? <PanelLeftOpen aria-hidden /> : <PanelLeftClose aria-hidden />}
            {!collapsed && <span>Collapse</span>}
          </Button>
        )}
        {!collapsed && <p className="px-2 pt-1 text-xs text-muted-foreground">Demo workspace · synthetic data</p>}
      </div>
      <AboutDialog open={aboutOpen} onOpenChange={setAboutOpen} />
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = usePersistentFlag("samaritan.sidebar.collapsed");
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      <aside
        aria-label="Sidebar"
        className={cn(
          "no-print sticky top-0 hidden h-screen shrink-0 border-r border-sidebar-border bg-sidebar transition-[width] duration-150 md:block",
          collapsed ? "w-14" : "w-58",
        )}
      >
        <SidebarBody collapsed={collapsed} onToggleCollapsed={() => setCollapsed(!collapsed)} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="no-print sticky top-0 z-30 flex h-12 items-center gap-2 border-b bg-background px-4 md:hidden">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger render={<Button variant="ghost" size="icon" aria-label="Open navigation" />}>
              <Menu aria-hidden />
            </SheetTrigger>
            <SheetContent side="left" showCloseButton={false} className="w-58 p-0 sm:max-w-58">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <SidebarBody collapsed={false} onNavigate={() => setMobileOpen(false)} />
            </SheetContent>
          </Sheet>
          <span className="font-semibold">Samaritan</span>
        </div>
        <div className="flex-1">{children}</div>
      </div>
    </div>
  );
}
