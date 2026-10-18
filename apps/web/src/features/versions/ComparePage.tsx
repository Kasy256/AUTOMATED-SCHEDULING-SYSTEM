import { useParams } from "react-router";

import type { AssignmentChange, AssignmentOut } from "@/api/generated/model";
import { useListResources } from "@/api/generated/resources/resources";
import { useGetSchedule } from "@/api/generated/schedules/schedules";
import {
  useDiffVersions,
  useListVersions,
} from "@/api/generated/versions/versions";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { TableSkeleton } from "@/components/TableSkeleton";
import { useAuth } from "@/lib/auth/AuthProvider";
import { isApiError } from "@/lib/problem";
import { formatInZone } from "@/lib/time";

import { diffSummary } from "./model";
import { PublishButton } from "./PublishDialog";

const SECTIONS = [
  ["moved", "Moved"],
  ["reassigned", "Reassigned"],
  ["added", "Added"],
  ["removed", "Removed"],
] as const;

export function ComparePage() {
  const { scheduleId = "", a = "", b = "" } = useParams();
  const { can } = useAuth();
  const { data: schedule } = useGetSchedule(scheduleId);
  const { data: versions = [] } = useListVersions(scheduleId);
  const { data: resources = [] } = useListResources();
  const { data: diff, error } = useDiffVersions(a, b);
  const tz = schedule?.timezone ?? "UTC";
  const codes = new Map(resources.map((r) => [r.id, r.code]));
  const from = versions.find((v) => v.id === a);
  const to = versions.find((v) => v.id === b);

  const side = (x: AssignmentOut | null) =>
    x
      ? `${formatInZone(x.start_at, tz)} · ${Object.values(x.resources)
          .flat()
          .map((id) => codes.get(id) ?? "?")
          .join(", ")}`
      : "—";

  if (error)
    return (
      <PageHeader
        title="Can't compare these versions"
        description={
          isApiError(error) ? (error.detail ?? error.title) : undefined
        }
      />
    );
  const summary = diff ? diffSummary(diff) : null;

  return (
    <>
      <PageHeader
        title={`Compare version ${String(from?.number ?? "?")} → ${String(to?.number ?? "?")}`}
        description={summary?.text}
        actions={
          to?.status === "draft" &&
          can("config.manage") && (
            <PublishButton
              version={to}
              versions={versions}
              scheduleId={scheduleId}
            />
          )
        }
      />
      <div className="flex flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        {!diff || !summary ? (
          <TableSkeleton label="Loading the changes" />
        ) : summary.total === 0 ? (
          <EmptyState
            title="No differences"
            description="These versions place every activity the same way."
          />
        ) : (
          SECTIONS.map(([key, title]) => {
            const changes: AssignmentChange[] = diff[key];
            return (
              <section
                key={key}
                className="rounded-xl border bg-card shadow-sm"
              >
                <h2 className="border-b px-5 py-3 text-sm font-semibold">
                  {`${title} (${String(changes.length)})`}
                </h2>
                <ul className="flex flex-col divide-y">
                  {changes.map((c) => (
                    <li
                      key={c.activity_id}
                      className="flex flex-col gap-1 px-5 py-3 text-sm sm:flex-row sm:items-center sm:gap-4"
                    >
                      <span className="min-w-40 font-medium">
                        {c.after?.activity_name ??
                          c.before?.activity_name ??
                          "Activity"}
                      </span>
                      <span className="text-muted-foreground">
                        {side(c.before)}
                      </span>
                      <span aria-hidden>→</span>
                      <span>{side(c.after)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })
        )}
      </div>
    </>
  );
}
