import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** A titled card that groups related fields; `disabled` disables every control inside. */
export function FormSection({
  title,
  description,
  disabled,
  className,
  children,
}: {
  title: string;
  description?: string;
  disabled?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border bg-card shadow-sm">
      <header className="border-b px-5 py-4">
        <h2 className="text-sm font-semibold">{title}</h2>
        {description && (
          <p className="mt-1 text-xs text-muted-foreground">{description}</p>
        )}
      </header>
      <fieldset
        disabled={disabled}
        className={cn("grid gap-x-4 gap-y-5 p-5 sm:grid-cols-2", className)}
      >
        {children}
      </fieldset>
    </section>
  );
}
