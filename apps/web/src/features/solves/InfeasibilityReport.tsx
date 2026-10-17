import { AlertTriangle, Lightbulb } from "lucide-react";
import { Link } from "react-router";

import { useListConstraints } from "@/api/generated/constraints/constraints";
import type { InfeasibilityReport as Report } from "@/api/generated/model";
import { Badge } from "@/components/ui/badge";
import { useEngineText } from "@/lib/engineText";
import { cn } from "@/lib/utils";

const KIND: Record<string, string> = {
  rule: "Rule",
  requirement: "Requirement",
  unavailable: "Unavailable",
  pin: "Pin",
};

function outcome(fixes: boolean | null | undefined): {
  label: string;
  className: string;
} {
  if (fixes === true)
    return { label: "Fixes it", className: "bg-[#dcfce7] text-[#14532d]" };
  if (fixes === false)
    return {
      label: "Doesn't fix it",
      className: "bg-muted text-muted-foreground",
    };
  return { label: "Untested", className: "bg-amber-100 text-amber-900" };
}

export function InfeasibilityReport({
  scheduleId,
  report,
}: {
  scheduleId: string;
  report: Report;
}) {
  const text = useEngineText(scheduleId);
  const { data: rules = [] } = useListConstraints(scheduleId);
  const ruleIds = new Set(rules.map((r) => r.id));
  const conflicts = report.conflicts ?? [];
  const relaxations = report.relaxations ?? [];

  if (conflicts.length === 0 && relaxations.length === 0)
    return (
      <p className="rounded-xl border bg-card p-5 text-sm text-muted-foreground shadow-sm">
        The solver could not explain this one. Try relaxing hard rules one at a
        time.
      </p>
    );

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-xl border bg-card shadow-sm">
        <header className="flex items-center gap-2 border-b px-5 py-4">
          <AlertTriangle className="size-4 text-amber-600" aria-hidden />
          <h2 className="text-sm font-semibold">What conflicts</h2>
        </header>
        <ul className="flex flex-col divide-y">
          {conflicts.map((c) => (
            <li key={c.id} className="flex items-start gap-3 px-5 py-3">
              <Badge variant="secondary" className="shrink-0">
                {KIND[c.kind] ?? c.kind}
              </Badge>
              <span className="text-sm">{text(c.text)}</span>
            </li>
          ))}
        </ul>
      </section>
      <section className="rounded-xl border bg-card shadow-sm">
        <header className="flex items-center gap-2 border-b px-5 py-4">
          <Lightbulb className="size-4 text-primary" aria-hidden />
          <h2 className="text-sm font-semibold">What would fix it</h2>
        </header>
        <ol className="flex flex-col divide-y">
          {relaxations.map((r, i) => {
            const o = outcome(r.fixes);
            return (
              <li
                key={i}
                className="flex flex-wrap items-center gap-3 px-5 py-3"
              >
                <span className="min-w-0 flex-1 text-sm">{text(r.text)}</span>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs font-medium",
                    o.className,
                  )}
                >
                  {o.label}
                </span>
                {ruleIds.has(r.target) && (
                  <Link
                    className="text-sm font-medium text-primary hover:underline"
                    to={`/schedules/${scheduleId}/rules`}
                  >
                    Open rule
                  </Link>
                )}
              </li>
            );
          })}
        </ol>
      </section>
    </div>
  );
}
