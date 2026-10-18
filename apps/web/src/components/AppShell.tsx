import {
  BarChart3,
  Boxes,
  CalendarDays,
  CalendarRange,
  Cpu,
  History,
  FileUp,
  LayoutDashboard,
  ListChecks,
  Menu,
  Shapes,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation, useParams } from "react-router";

import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth/AuthProvider";
import { cn } from "@/lib/utils";

import { BrandMark } from "./BrandMark";
import { OrgMenu } from "./OrgMenu";
import { ScheduleSwitcher } from "./ScheduleSwitcher";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none",
    isActive &&
      "bg-sidebar-accent text-sidebar-accent-foreground shadow-[inset_3px_0_0_var(--sidebar-primary)]",
  );

function Item({
  to,
  icon: Icon,
  children,
}: {
  to: string;
  icon: LucideIcon;
  children: ReactNode;
}) {
  return (
    <NavLink className={linkClass} to={to}>
      <Icon className="size-[18px] shrink-0" aria-hidden />
      {children}
    </NavLink>
  );
}

function NavGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="px-3 pt-3 pb-1.5 text-[11px] font-medium tracking-wider text-sidebar-foreground uppercase">
        {label}
      </p>
      {children}
    </div>
  );
}

function Sidebar() {
  const { scheduleId } = useParams();
  const { can } = useAuth();
  const base = scheduleId ? `/schedules/${scheduleId}` : null;
  return (
    <nav
      aria-label="Main"
      className="flex h-full flex-col gap-3 overflow-y-auto bg-sidebar p-4 text-sidebar-foreground"
    >
      <BrandMark className="px-2 py-2 text-lg" />
      <ScheduleSwitcher activeId={scheduleId} />
      {base && (
        <NavGroup label="Schedule">
          <Item to={`${base}/planner`} icon={CalendarDays}>
            Planner
          </Item>
          <Item to={`${base}/overview`} icon={LayoutDashboard}>
            Overview
          </Item>
          <Item to={`${base}/demands`} icon={CalendarRange}>
            Demands &amp; slots
          </Item>
          <Item to={`${base}/rules`} icon={ListChecks}>
            Rules
          </Item>
          <Item to={`${base}/solves`} icon={Cpu}>
            Solves
          </Item>
          <Item to={`${base}/versions`} icon={History}>
            Versions
          </Item>
          <Item to={`${base}/reports`} icon={BarChart3}>
            Reports
          </Item>
        </NavGroup>
      )}
      <NavGroup label="Organisation">
        <Item to="/resources" icon={Boxes}>
          Resources
        </Item>
        <Item to="/resource-types" icon={Shapes}>
          Resource types
        </Item>
        {can("config.manage") && (
          <Item to="/imports" icon={FileUp}>
            Imports
          </Item>
        )}
        {can("members.manage") && (
          <Item to="/members" icon={Users}>
            Members
          </Item>
        )}
      </NavGroup>
      <div className="mt-auto border-t border-sidebar-border pt-3">
        <OrgMenu />
      </div>
    </nav>
  );
}

export function AppShell() {
  const { pathname } = useLocation();
  // The phone navigation sheet closes when the route changes, not on any click inside it:
  // its menus (schedule switcher, organisation) open from inside the sheet.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const setOpen = (next: boolean) => setOpenOn(next ? pathname : null);
  return (
    <div className="flex min-h-svh">
      <aside className="hidden w-64 shrink-0 md:block">
        <div className="sticky top-0 h-svh">
          <Sidebar />
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b bg-card px-4 md:hidden">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger
              aria-label="Open navigation"
              className="rounded-md p-2 hover:bg-muted"
            >
              <Menu className="size-5" aria-hidden />
            </SheetTrigger>
            <SheetContent side="left" className="w-72 p-0">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <Sidebar />
            </SheetContent>
          </Sheet>
          <BrandMark tone="dark" />
        </div>
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
