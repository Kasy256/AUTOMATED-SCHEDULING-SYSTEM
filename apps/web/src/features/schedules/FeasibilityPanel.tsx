import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { useCheckFeasibility } from "@/api/generated/problems/problems";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useNames } from "@/lib/names";

const TITLES: Record<string, string> = {
  unfillable_requirement: "A requirement no resource can fill",
  fixed_resource_mismatch: "A fixed resource doesn't fit",
  insufficient_capacity: "Not enough capacity",
  overloaded_resource: "A resource is over-committed",
};

export function FeasibilityPanel({ scheduleId }: { scheduleId: string }) {
  const { data, isFetching, refetch, error } = useCheckFeasibility(scheduleId);
  const name = useNames(scheduleId);
  return (
    <section
      aria-labelledby="feasibility"
      className="rounded-lg border bg-card p-4"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 id="feasibility" className="font-semibold">
          Pre-solve check
        </h2>
        <Button
          variant="outline"
          size="sm"
          disabled={isFetching}
          onClick={() => void refetch()}
        >
          {isFetching ? "Checking…" : "Check again"}
        </Button>
      </div>
      {error && (
        <p className="mt-3 text-sm text-destructive">
          The check could not run. Try again.
        </p>
      )}
      {data?.issues.length === 0 && (
        <p className="mt-3 flex items-center gap-2 text-sm">
          <CheckCircle2 className="size-4 text-primary" aria-hidden />
          No problems found. The schedule is ready to solve.
        </p>
      )}
      {data && data.issues.length > 0 && (
        <ul className="mt-3 flex flex-col gap-3">
          {data.issues.map((issue, i) => (
            <li key={i} className="flex gap-3">
              <AlertTriangle
                className="mt-0.5 size-4 shrink-0 text-amber-600"
                aria-hidden
              />
              <div className="flex flex-col gap-1">
                <p className="text-sm font-medium">
                  {TITLES[issue.code] ?? issue.code}
                </p>
                <p className="text-sm text-muted-foreground">{issue.message}</p>
                <div className="flex flex-wrap gap-1">
                  {[
                    ...(issue.resource_ids ?? []),
                    ...(issue.activity_ids ?? []),
                  ]
                    .slice(0, 12)
                    .map((id) => (
                      <Badge key={id} variant="secondary">
                        {name(id)}
                      </Badge>
                    ))}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
