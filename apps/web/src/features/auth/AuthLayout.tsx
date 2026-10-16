import type { ReactNode } from "react";

export function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: ReactNode;
}) {
  return (
    <div className="grid min-h-svh md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <div className="hidden flex-col justify-between bg-sidebar p-10 text-sidebar-foreground md:flex">
        <div className="flex items-center gap-2 font-semibold text-sidebar-accent-foreground">
          <span className="size-5 rounded bg-sidebar-primary" aria-hidden />{" "}
          Cartlyf
        </div>
        <p className="max-w-sm text-lg text-sidebar-accent-foreground">
          Schedules that respect every rule — and explain themselves.
        </p>
        <p className="text-xs">Universal scheduling for teams of any shape.</p>
      </div>
      <main className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {subtitle && (
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          )}
          <div className="mt-6">{children}</div>
        </div>
      </main>
    </div>
  );
}
