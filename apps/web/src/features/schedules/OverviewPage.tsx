import {
  Boxes,
  CalendarRange,
  Clock,
  ListChecks,
  type LucideIcon,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import {
  useListActivities,
  useListDemands,
} from "@/api/generated/activities/activities";
import { useListConstraints } from "@/api/generated/constraints/constraints";
import {
  useListResources,
  useListResourceTypes,
} from "@/api/generated/resources/resources";
import {
  deleteSchedule,
  getGetScheduleQueryKey,
  getListSchedulesQueryKey,
  updateSchedule,
  useGetSchedule,
} from "@/api/generated/schedules/schedules";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth/AuthProvider";
import { describeFailure } from "@/lib/conflict";
import { LAST_SCHEDULE_KEY } from "@/lib/landing";
import { writeStored } from "@/lib/storage";
import { formatMinuteOfDay } from "@/lib/time";

import { SolveButton } from "@/features/solves/SolveDialog";

import { FeasibilityPanel } from "./FeasibilityPanel";
import { ScheduleForm } from "./ScheduleForm";

function Stat({
  label,
  value,
  detail,
  to,
  icon: Icon,
}: {
  label: string;
  value: number;
  detail?: string;
  to: string;
  icon: LucideIcon;
}) {
  return (
    <Link
      to={to}
      className="flex items-start justify-between gap-4 rounded-xl border bg-card p-5 shadow-sm transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <span className="flex min-w-0 flex-col gap-1.5">
        <span className="text-sm font-medium text-muted-foreground">
          {label}
        </span>
        <span className="text-3xl font-semibold tracking-tight tabular-nums">
          {value}
        </span>
        {detail && (
          <span className="truncate text-xs text-muted-foreground">
            {detail}
          </span>
        )}
      </span>
      <span className="rounded-lg bg-primary/10 p-2.5 text-primary">
        <Icon className="size-5" aria-hidden />
      </span>
    </Link>
  );
}

export function OverviewPage() {
  const { scheduleId = "" } = useParams();
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { data: schedule, error } = useGetSchedule(scheduleId);
  const { data: resources = [] } = useListResources();
  const { data: types = [] } = useListResourceTypes();
  const { data: demands = [] } = useListDemands(scheduleId);
  const { data: activities = [] } = useListActivities(scheduleId);
  const { data: rules = [] } = useListConstraints(scheduleId);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (schedule) writeStored(LAST_SCHEDULE_KEY, schedule.id);
  }, [schedule]);

  if (error)
    return (
      <PageHeader
        title="Schedule not found"
        description="It may have been deleted."
        actions={
          <Button asChild variant="outline">
            <Link to="/">Go home</Link>
          </Button>
        }
      />
    );
  if (!schedule)
    return (
      <div role="status" className="p-8 text-muted-foreground">
        Loading…
      </div>
    );

  const byType = types
    .map(
      (t) =>
        `${resources.filter((r) => r.resource_type_id === t.id).length} ${t.name}`,
    )
    .join(" · ");
  const hard = rules.filter((r) => r.hard).length;

  async function remove() {
    try {
      await deleteSchedule(scheduleId);
      await queryClient.invalidateQueries({
        queryKey: getListSchedulesQueryKey(),
      });
      toast.success("Schedule deleted");
      void navigate("/");
    } catch (e) {
      setFailure(describeFailure(e, "This schedule"));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <PageHeader
        title={schedule.name}
        description={`${schedule.start_date} – ${schedule.end_date} · ${schedule.timezone}`}
        actions={
          can("config.manage") && (
            <>
              <SolveButton scheduleId={scheduleId} />
              <Button variant="outline" onClick={() => setEditing(true)}>
                Edit schedule
              </Button>
              <Button
                variant="outline"
                className="text-destructive"
                onClick={() => setDeleting(true)}
              >
                Delete
              </Button>
            </>
          )
        }
      />
      <div className="flex flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        {failure && (
          <Alert variant="destructive" role="alert">
            <AlertDescription>{failure}</AlertDescription>
          </Alert>
        )}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Stat
            label="Resources"
            icon={Boxes}
            value={resources.length}
            detail={byType}
            to="/resources"
          />
          <Stat
            label="Demands"
            icon={CalendarRange}
            value={demands.length}
            to={`/schedules/${scheduleId}/demands`}
          />
          <Stat
            label="Activities"
            icon={Clock}
            value={activities.length}
            to={`/schedules/${scheduleId}/demands`}
          />
          <Stat
            label="Rules"
            icon={ListChecks}
            value={rules.length}
            detail={`${hard} hard · ${rules.length - hard} soft`}
            to={`/schedules/${scheduleId}/rules`}
          />
        </div>
        {(schedule.day_parts.parts ?? []).length > 0 && (
          <p className="text-sm text-muted-foreground">
            Parts of the day:{" "}
            {(schedule.day_parts.parts ?? [])
              .map(
                (p) =>
                  `${p.name} ${formatMinuteOfDay(p.start_minute)}–${formatMinuteOfDay(p.end_minute)}`,
              )
              .join(" · ")}
          </p>
        )}
        <FeasibilityPanel scheduleId={scheduleId} />
      </div>
      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit schedule</DialogTitle>
          </DialogHeader>
          <ScheduleForm
            submitLabel="Save"
            defaultValues={{
              name: schedule.name,
              timezone: schedule.timezone,
              start_date: schedule.start_date,
              end_date: schedule.end_date,
              day_parts: (schedule.day_parts.parts ?? []).map((p) => ({
                name: p.name,
                start: formatMinuteOfDay(p.start_minute),
                end: formatMinuteOfDay(p.end_minute),
              })),
            }}
            onSubmit={async (body) => {
              await updateSchedule(scheduleId, body);
              await Promise.all([
                queryClient.invalidateQueries({
                  queryKey: getGetScheduleQueryKey(scheduleId),
                }),
                queryClient.invalidateQueries({
                  queryKey: getListSchedulesQueryKey(),
                }),
              ]);
              toast.success("Schedule saved");
              setEditing(false);
            }}
          />
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={`Delete ${schedule.name}?`}
        description="Its demands, rules and versions are removed with it. This cannot be undone."
        confirmLabel="Delete schedule"
        destructive
        onConfirm={() => void remove()}
      />
    </>
  );
}
