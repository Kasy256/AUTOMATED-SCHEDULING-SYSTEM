import { Loader2 } from "lucide-react";

import type { Progress } from "./useSolveStream";

const gap = (p: Progress) =>
  p.objective != null && p.best_bound != null && p.objective !== 0
    ? `${((Math.abs(p.objective - p.best_bound) / Math.abs(p.objective)) * 100).toFixed(1)}%`
    : null;

export function SolveProgress({ progress }: { progress: Progress | null }) {
  const g = progress ? gap(progress) : null;
  return (
    <div className="grid gap-4 sm:grid-cols-4" aria-live="polite">
      <Stat
        label="Status"
        value={
          <span className="flex items-center gap-2 capitalize">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            {progress?.status ?? "queued"}
          </span>
        }
      />
      <Stat
        label="Elapsed"
        value={`${(progress?.wall_time_s ?? 0).toFixed(1)} s`}
      />
      <Stat
        label="Solutions"
        value={`${String(progress?.solutions ?? 0)} solutions`}
      />
      <Stat
        label="Score"
        value={
          progress?.objective != null
            ? `Best score ${String(progress.objective)}`
            : "—"
        }
        detail={g ? `Gap ${g}` : undefined}
      />
    </div>
  );
}

function Stat({
  label,
  value,
  detail,
}: {
  label: string;
  value: React.ReactNode;
  detail?: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="mt-1 text-lg font-semibold">{value}</div>
      {detail && <p className="text-xs text-muted-foreground">{detail}</p>}
    </div>
  );
}
