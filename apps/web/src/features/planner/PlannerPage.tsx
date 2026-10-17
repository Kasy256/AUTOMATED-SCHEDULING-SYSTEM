import { useState } from "react";
import { useParams, useSearchParams } from "react-router";

import type { AssignmentEdit } from "@/api/generated/model";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { TableSkeleton } from "@/components/TableSkeleton";
import { SolveButton } from "@/features/solves/SolveDialog";
import { addDays, mondayOf, scheduleWeeks, zonedParts } from "@/lib/time";

import { BoardGrid } from "./BoardGrid";
import { BoardToolbar } from "./BoardToolbar";
import { versionLabel } from "./labels";
import { weekColumns } from "./model/columns";
import { applyPending, cellIndex } from "./model/items";
import { useBoardData } from "./useBoardData";

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
const dayMonth = (date: string) =>
  `${String(Number(date.slice(8, 10)))} ${MONTHS[Number(date.slice(5, 7)) - 1] ?? ""}`;

export function PlannerPage() {
  const { scheduleId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const data = useBoardData(scheduleId, params.get("version"));
  const [typeChoice, setTypeChoice] = useState<string | null>(null);
  const [weekChoice, setWeekChoice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const pending: AssignmentEdit[] = [];

  const { schedule, version, types, resources } = data;
  const tz = schedule?.timezone ?? "UTC";
  const typeId =
    typeChoice ??
    types.find((t) => resources.some((r) => r.resource_type_id === t.id))?.id ??
    types[0]?.id ??
    "";
  const weeks = schedule
    ? scheduleWeeks(schedule.start_date, schedule.end_date)
    : [];
  const firstStart = [...(version?.assignments ?? [])]
    .map((a) => a.start_at)
    .sort()[0];
  const week =
    weekChoice ??
    (firstStart ? mondayOf(zonedParts(firstStart, tz).date) : (weeks[0] ?? ""));
  const weekAt = weeks.indexOf(week);

  const assignments = applyPending(version?.assignments ?? [], pending);
  const columns = !week
    ? []
    : weekColumns(
        [
          ...data.activities.flatMap((a) => a.candidate_starts),
          ...assignments.map((a) => a.start_at),
        ],
        week,
        tz,
        data.slots,
      );
  const needle = query.trim().toLowerCase();
  const rows = resources.filter(
    (r) =>
      r.resource_type_id === typeId &&
      (!needle ||
        r.name.toLowerCase().includes(needle) ||
        r.code.toLowerCase().includes(needle)),
  );
  const index = cellIndex(
    assignments,
    new Set(rows.map((r) => r.id)),
    data.pinned,
  );
  const codes = new Map(resources.map((r) => [r.id, r.code]));
  const codeOf = (id: string) => codes.get(id) ?? "";

  return (
    <>
      <PageHeader
        title="Planner"
        description={
          version
            ? `${versionLabel(version)}${data.editable ? "" : " — read-only"}`
            : undefined
        }
      />
      <div className="flex flex-col gap-4 px-4 py-6 sm:px-6 lg:px-8">
        <BoardToolbar
          types={types}
          typeId={typeId}
          onType={setTypeChoice}
          query={query}
          onQuery={setQuery}
          weekLabel={week ? `Week of ${dayMonth(week)}` : ""}
          onPrevWeek={
            weekAt > 0 ? () => setWeekChoice(addDays(week, -7)) : null
          }
          onNextWeek={
            weekAt >= 0 && weekAt < weeks.length - 1
              ? () => setWeekChoice(addDays(week, 7))
              : null
          }
          versions={data.versions}
          versionId={version?.id ?? ""}
          onVersion={(id) => setParams({ version: id })}
          actions={<SolveButton scheduleId={scheduleId} variant="outline" />}
        />
        {data.loading ? (
          <TableSkeleton label="Loading the board" />
        ) : !version ? (
          <EmptyState
            illustration="setup"
            title="Solve to create the first timetable"
            description="The board shows a solved timetable. Run a solve to make one."
            action={<SolveButton scheduleId={scheduleId} />}
          />
        ) : columns.length === 0 ? (
          <EmptyState
            title="Nothing is scheduled this week."
            description="Use the week picker to find scheduled weeks."
          />
        ) : (
          <BoardGrid
            rows={rows}
            columns={columns}
            index={index}
            codeOf={codeOf}
            highlight={null}
            canDrag={false}
            onOpenItem={() => undefined}
          />
        )}
      </div>
    </>
  );
}
