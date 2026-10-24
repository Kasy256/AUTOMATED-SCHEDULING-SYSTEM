import { Link } from "react-router";

import { useGetSchedule } from "@/api/generated/schedules/schedules";
import { Button } from "@/components/ui/button";
import { FeasibilityPanel } from "@/features/schedules/FeasibilityPanel";

export function FinishStep({ scheduleId }: { scheduleId: string }) {
  const { error } = useGetSchedule(scheduleId);
  if (error)
    return (
      <section className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">
          That schedule no longer exists
        </h1>
        <Button asChild variant="outline" className="self-start">
          <Link to="/setup">Start again</Link>
        </Button>
      </section>
    );
  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Check & finish
        </h1>
        <p className="text-muted-foreground">
          A quick check for anything that would stop a solve.
        </p>
      </div>
      <FeasibilityPanel scheduleId={scheduleId} />
      <Button asChild className="self-start">
        <Link to={`/schedules/${scheduleId}/overview`}>Go to schedule</Link>
      </Button>
    </section>
  );
}
