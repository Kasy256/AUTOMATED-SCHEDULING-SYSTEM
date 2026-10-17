import type { ReactNode } from "react";

import { BrandMark } from "@/components/BrandMark";
import { ILLUSTRATIONS } from "@/components/illustrations";

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
    <div className="grid min-h-svh bg-background lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <div className="hidden flex-col justify-between bg-gradient-to-br from-teal-50 via-background to-teal-100/70 p-12 lg:flex dark:from-teal-950/40 dark:via-background dark:to-teal-900/30">
        <BrandMark tone="dark" className="text-lg" />
        <div className="flex flex-col items-center gap-8">
          <img
            src={ILLUSTRATIONS["sign-in"]}
            alt=""
            aria-hidden="true"
            className="w-full max-w-md"
          />
          <div className="max-w-md text-center">
            <p className="text-xl font-semibold tracking-tight">
              Schedules that respect every rule — and explain themselves.
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Universal scheduling for teams of any shape.
            </p>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">© Cartlyf</p>
      </div>
      <main className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-md rounded-2xl border bg-card p-8 shadow-sm sm:p-10">
          <BrandMark tone="dark" className="mb-8 lg:hidden" />
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {subtitle && (
            <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>
          )}
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}
