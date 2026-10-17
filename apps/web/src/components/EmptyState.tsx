import type { ReactNode } from "react";

import { ILLUSTRATIONS, type IllustrationName } from "./illustrations";

export function EmptyState({
  title,
  description,
  action,
  illustration = "empty",
}: {
  title: string;
  description: string;
  action?: ReactNode;
  illustration?: IllustrationName;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed bg-card px-6 py-12 text-center">
      <img
        src={ILLUSTRATIONS[illustration]}
        alt=""
        aria-hidden="true"
        className="mb-2 h-32 w-auto"
      />
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="max-w-md text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
