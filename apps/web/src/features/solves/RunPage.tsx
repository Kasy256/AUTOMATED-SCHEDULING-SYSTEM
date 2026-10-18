import { CheckCircle2 } from "lucide-react";
import { Link, useParams } from "react-router";
import { toast } from "sonner";

import { cancelSolve, useGetSolve } from "@/api/generated/solves/solves";
import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth/AuthProvider";
import { describeFailure } from "@/lib/conflict";

import { InfeasibilityReport } from "./InfeasibilityReport";
import { SolveProgress } from "./SolveProgress";
import { STATUS_LABEL } from "./status";
import { TERMINAL, useSolveStream } from "./useSolveStream";

function Live({ runId, canCancel }: { runId: string; canCancel: boolean }) {
  const { progress } = useSolveStream(runId);
  return (
    <div className="flex flex-col gap-4">
      <SolveProgress progress={progress} />
      {canCancel && (
        <Button
          variant="outline"
          className="self-start"
          onClick={() => {
            cancelSolve(runId).then(
              () =>
                toast.info("Cancelling — the best result so far will be kept"),
              (e: unknown) => toast.error(describeFailure(e, "This solve")),
            );
          }}
        >
          Cancel
        </Button>
      )}
    </div>
  );
}

export function RunPage() {
  const { scheduleId = "", runId = "" } = useParams();
  const { can } = useAuth();
  const { data: run, error } = useGetSolve(runId, {
    query: { refetchInterval: false },
  });

  if (error)
    return (
      <PageHeader
        title="Solve not found"
        description="It may belong to another schedule."
      />
    );
  if (!run)
    return (
      <div role="status" className="p-8 text-muted-foreground">
        Loading…
      </div>
    );
  const terminal = TERMINAL.has(run.status);

  return (
    <>
      <PageHeader
        title={`Solve ${run.id.slice(0, 8)}`}
        description={
          run.kind === "repair"
            ? "Repair of the published timetable"
            : "Full solve"
        }
        actions={
          <Badge variant="secondary">
            {STATUS_LABEL[run.status] ?? run.status}
          </Badge>
        }
      />
      <div className="flex flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        {!terminal && <Live runId={run.id} canCancel={can("config.manage")} />}
        {terminal &&
          run.version_id &&
          (run.status === "succeeded" || run.status === "cancelled") && (
            <section className="flex flex-wrap items-center gap-4 rounded-xl border bg-card p-5 shadow-sm">
              <CheckCircle2 className="size-6 text-primary" aria-hidden />
              <div className="min-w-0 flex-1">
                <h2 className="font-semibold">Timetable ready</h2>
                <p className="text-sm text-muted-foreground">
                  {run.status === "cancelled"
                    ? "You cancelled the solve; the best timetable found so far was kept as a draft."
                    : "The new draft respects every hard rule."}
                </p>
              </div>
              <Button asChild>
                <Link
                  to={`/schedules/${scheduleId}/planner?version=${run.version_id}`}
                >
                  Open on the board
                </Link>
              </Button>
            </section>
          )}
        {terminal && run.status === "infeasible" && (
          <InfeasibilityReport
            scheduleId={scheduleId}
            report={run.infeasibility ?? { conflicts: [], relaxations: [] }}
          />
        )}
        {terminal && run.status !== "infeasible" && !run.version_id && (
          <Alert variant="destructive" role="alert">
            <AlertDescription>
              {run.error ?? "The solve stopped without a timetable."}
            </AlertDescription>
          </Alert>
        )}
      </div>
    </>
  );
}
