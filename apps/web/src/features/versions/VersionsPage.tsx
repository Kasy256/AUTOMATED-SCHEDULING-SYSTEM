import { Link, useParams } from "react-router";
import { toast } from "sonner";

import type { VersionSummary } from "@/api/generated/model";
import { useGetSchedule } from "@/api/generated/schedules/schedules";
import { useListSolves } from "@/api/generated/solves/solves";
import {
  getExportCsvUrl,
  useListVersions,
} from "@/api/generated/versions/versions";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { versionLabel } from "@/features/planner/labels";
import { SolveButton } from "@/features/solves/SolveDialog";
import { useAuth } from "@/lib/auth/AuthProvider";
import { describeFailure } from "@/lib/conflict";
import { downloadFromApi } from "@/lib/download";
import { formatInZone } from "@/lib/time";

import { compareTargetOf, originOf } from "./model";
import { ArchiveButton, PublishButton } from "./PublishDialog";
import { RepairButton } from "./RepairDialog";

const STATUS_VARIANT = {
  published: "default",
  draft: "secondary",
  archived: "outline",
} as const;

export function VersionsPage() {
  const { scheduleId = "" } = useParams();
  const { can } = useAuth();
  const { data: schedule } = useGetSchedule(scheduleId);
  const { data: versions = [], isPending } = useListVersions(scheduleId);
  const { data: runs = [] } = useListSolves(scheduleId);
  const tz = schedule?.timezone ?? "UTC";
  const canEdit = can("config.manage");
  const sorted = [...versions].sort((a, b) => b.number - a.number);
  const published = versions.some((v) => v.status === "published");

  async function exportCsv(v: VersionSummary) {
    try {
      await downloadFromApi(
        getExportCsvUrl(v.id),
        `timetable-v${String(v.number)}.csv`,
      );
    } catch (e) {
      toast.error(describeFailure(e, "This export"));
    }
  }

  return (
    <>
      <PageHeader
        title="Versions"
        description="Every timetable this schedule has produced, newest first."
        actions={
          canEdit &&
          published &&
          schedule && (
            <RepairButton
              scheduleId={scheduleId}
              timeZone={schedule.timezone}
            />
          )
        }
      />
      <div className="px-4 py-6 sm:px-6 lg:px-8">
        {isPending ? (
          <TableSkeleton label="Loading versions" />
        ) : sorted.length === 0 ? (
          <EmptyState
            illustration="empty"
            title="No versions yet"
            description="Solve the schedule to create its first version."
            action={<SolveButton scheduleId={scheduleId} />}
          />
        ) : (
          <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Version</TableHead>
                  <TableHead>Origin</TableHead>
                  <TableHead>Solver</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Published</TableHead>
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((v) => {
                  const target = compareTargetOf(v, versions);
                  return (
                    <TableRow key={v.id}>
                      <TableCell>
                        <Badge variant={STATUS_VARIANT[v.status]}>
                          {versionLabel(v)}
                        </Badge>
                      </TableCell>
                      <TableCell>{originOf(v, runs)}</TableCell>
                      <TableCell>{v.solver_status}</TableCell>
                      <TableCell className="tabular-nums">
                        {`${String(v.hard_violations)} hard · ${String(v.soft_total)} soft`}
                      </TableCell>
                      <TableCell>{formatInZone(v.created_at, tz)}</TableCell>
                      <TableCell>
                        {v.published_at
                          ? formatInZone(v.published_at, tz)
                          : "—"}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap justify-end gap-1">
                          <Button asChild variant="ghost" size="sm">
                            <Link
                              to={`/schedules/${scheduleId}/planner?version=${v.id}`}
                            >
                              Open on board
                            </Link>
                          </Button>
                          {target && (
                            <Button asChild variant="ghost" size="sm">
                              <Link
                                to={`/schedules/${scheduleId}/versions/${target.id}/compare/${v.id}`}
                              >
                                Compare
                              </Link>
                            </Button>
                          )}
                          {canEdit && v.status === "draft" && (
                            <>
                              <PublishButton
                                version={v}
                                versions={versions}
                                scheduleId={scheduleId}
                              />
                              <ArchiveButton
                                version={v}
                                scheduleId={scheduleId}
                              />
                            </>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => void exportCsv(v)}
                          >
                            Export CSV
                          </Button>
                          <Button asChild variant="ghost" size="sm">
                            <Link
                              to={`/schedules/${scheduleId}/versions/${v.id}/print`}
                            >
                              Print
                            </Link>
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </>
  );
}
