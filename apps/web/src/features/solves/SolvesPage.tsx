import { Link, useParams } from "react-router";

import { useGetSchedule } from "@/api/generated/schedules/schedules";
import { useListSolves } from "@/api/generated/solves/solves";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatInZone } from "@/lib/time";

import { SolveButton } from "./SolveDialog";
import { STATUS_LABEL } from "./status";

const seconds = (
  from: string | null | undefined,
  to: string | null | undefined,
) =>
  from && to
    ? `${String(Math.round((Date.parse(to) - Date.parse(from)) / 1000))} s`
    : "—";

export function SolvesPage() {
  const { scheduleId = "" } = useParams();
  const { data: schedule } = useGetSchedule(scheduleId);
  const { data: runs = [], isPending } = useListSolves(scheduleId);
  const tz = schedule?.timezone ?? "UTC";
  const sorted = [...runs].sort((a, b) =>
    b.created_at.localeCompare(a.created_at),
  );

  return (
    <>
      <PageHeader
        title="Solves"
        description="Every solve of this schedule, newest first."
        actions={<SolveButton scheduleId={scheduleId} />}
      />
      <div className="px-4 py-6 sm:px-6 lg:px-8">
        {isPending ? (
          <TableSkeleton label="Loading solves" />
        ) : sorted.length === 0 ? (
          <EmptyState
            illustration="empty"
            title="No solves yet"
            description="Solve the schedule to create its first timetable."
          />
        ) : (
          <div className="rounded-xl border bg-card shadow-sm">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Started</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead>
                    <span className="sr-only">Open</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>{formatInZone(run.created_at, tz)}</TableCell>
                    <TableCell>
                      {run.kind === "repair" ? "Repair" : "Solve"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          run.status === "succeeded" ? "default" : "secondary"
                        }
                      >
                        {STATUS_LABEL[run.status] ?? run.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {seconds(run.started_at, run.finished_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link
                        className="text-sm font-medium text-primary hover:underline"
                        to={`/schedules/${scheduleId}/solves/${run.id}`}
                      >
                        View
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </>
  );
}
