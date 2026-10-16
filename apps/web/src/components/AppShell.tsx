import { Menu } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useParams } from "react-router";

import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth/AuthProvider";
import { cn } from "@/lib/utils";

import { OrgMenu } from "./OrgMenu";
import { ScheduleSwitcher } from "./ScheduleSwitcher";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "block rounded-md px-3 py-1.5 text-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none",
    isActive &&
      "bg-sidebar-accent font-medium text-sidebar-accent-foreground shadow-[inset_2px_0_0_var(--sidebar-primary)]",
  );

function NavGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <p className="px-3 pt-4 pb-1 text-[10px] font-medium tracking-wider text-sidebar-foreground uppercase">
        {label}
      </p>
      {children}
    </div>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { scheduleId } = useParams();
  const { can } = useAuth();
  const base = scheduleId ? `/schedules/${scheduleId}` : null;
  return (
    <nav
      aria-label="Main"
      className="flex h-full flex-col gap-2 bg-sidebar p-3 text-sidebar-foreground"
      onClick={onNavigate}
    >
      <div className="flex items-center gap-2 px-2 py-1 font-semibold text-sidebar-accent-foreground">
        <span className="size-4 rounded bg-sidebar-primary" aria-hidden />{" "}
        Cartlyf
      </div>
      <ScheduleSwitcher activeId={scheduleId} />
      {base && (
        <NavGroup label="Schedule">
          <NavLink className={linkClass} to={`${base}/overview`}>
            Overview
          </NavLink>
          <NavLink className={linkClass} to={`${base}/demands`}>
            Demands &amp; slots
          </NavLink>
          <NavLink className={linkClass} to={`${base}/rules`}>
            Rules
          </NavLink>
        </NavGroup>
      )}
      <NavGroup label="Organisation">
        <NavLink className={linkClass} to="/resources">
          Resources
        </NavLink>
        <NavLink className={linkClass} to="/resource-types">
          Resource types
        </NavLink>
        {can("config.manage") && (
          <NavLink className={linkClass} to="/imports">
            Imports
          </NavLink>
        )}
        {can("members.manage") && (
          <NavLink className={linkClass} to="/members">
            Members
          </NavLink>
        )}
      </NavGroup>
      <div className="mt-auto">
        <OrgMenu />
      </div>
    </nav>
  );
}

export function AppShell() {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-svh">
      <aside className="hidden w-60 shrink-0 md:block">
        <div className="sticky top-0 h-svh">
          <Sidebar />
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b bg-card px-4 py-2 md:hidden">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger
              aria-label="Open navigation"
              className="rounded-md p-2 hover:bg-muted"
            >
              <Menu className="size-5" aria-hidden />
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <Sidebar
                onNavigate={() => {
                  setOpen(false);
                }}
              />
            </SheetContent>
          </Sheet>
          <span className="font-semibold">Cartlyf</span>
        </div>
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
