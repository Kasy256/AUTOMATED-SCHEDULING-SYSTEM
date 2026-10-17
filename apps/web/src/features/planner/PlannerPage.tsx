import { useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";
import { useBlocker, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";

import type { AssignmentEdit } from "@/api/generated/model";
import {
  createDraft,
  getListVersionsQueryKey,
} from "@/api/generated/versions/versions";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { TableSkeleton } from "@/components/TableSkeleton";
import { SolveButton } from "@/features/solves/SolveDialog";
import { useAuth } from "@/lib/auth/AuthProvider";
import { describeFailure } from "@/lib/conflict";
import { useEngineText } from "@/lib/engineText";
import { isApiError } from "@/lib/problem";
import {
  addDays,
  formatInZone,
  isoInstant,
  mondayOf,
  scheduleWeeks,
  zonedParts,
} from "@/lib/time";

import { BoardGrid } from "./BoardGrid";
import { BoardToolbar } from "./BoardToolbar";
import { BOARD_ID, versionLabel } from "./labels";
import { weekColumns } from "./model/columns";
import { ExplanationPanel } from "./ExplanationPanel";
import { applyPending, cellIndex, type BoardItem } from "./model/items";
import { pendingReducer } from "./model/pending";
import { PendingTray } from "./PendingTray";
import { ScorePanel } from "./ScorePanel";
import { useBoardData } from "./useBoardData";
import { useDragChecks } from "./useDragChecks";

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
  const [pending, dispatch] = useReducer(pendingReducer, []);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{
    item: BoardItem;
    rowId: string;
  } | null>(null);
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const text = useEngineText(scheduleId);

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

  // Memoised: the board's rows only skip re-rendering while these keep their identity.
  const { activities, slots, pinned } = data;
  const assignments = useMemo(
    () => applyPending(version?.assignments ?? [], pending),
    [version, pending],
  );
  const columns = useMemo(
    () =>
      !week
        ? []
        : weekColumns(
            [
              ...activities.flatMap((a) => a.candidate_starts),
              ...assignments.map((a) => a.start_at),
            ],
            week,
            tz,
            slots,
          ),
    [week, activities, assignments, tz, slots],
  );
  const needle = query.trim().toLowerCase();
  const rows = useMemo(
    () =>
      resources.filter(
        (r) =>
          r.resource_type_id === typeId &&
          (!needle ||
            r.name.toLowerCase().includes(needle) ||
            r.code.toLowerCase().includes(needle)),
      ),
    [resources, typeId, needle],
  );
  const index = useMemo(
    () => cellIndex(assignments, new Set(rows.map((r) => r.id)), pinned),
    [assignments, rows, pinned],
  );
  const codeOf = useMemo(() => {
    const codes = new Map(resources.map((r) => [r.id, r.code]));
    return (id: string) => codes.get(id) ?? "";
  }, [resources]);
  const openItem = useCallback(
    (item: BoardItem, rowId: string) => setSelected({ item, rowId }),
    [],
  );
  const names = new Map(
    (version?.assignments ?? []).map((a) => [
      a.activity_id,
      a.activity_name ?? "Activity",
    ]),
  );
  const labelAt = (start: string) =>
    columns.find((col) => col.start === isoInstant(start))?.label ??
    formatInZone(start, tz);
  const describe = (c: AssignmentEdit) =>
    `${names.get(c.activity_id) ?? "Activity"} → ${labelAt(c.start_at)}`;
  const canEdit = can("config.manage");

  const drag = useDragChecks(version?.id ?? "");
  const { check } = drag;
  const hoverCheck = useCallback(
    (rowId: string, start: string) => {
      check(rowId, start).catch(() => undefined);
    },
    [check],
  );
  async function dropAt(rowId: string, start: string): Promise<boolean> {
    try {
      const out = await drag.drop(rowId, start);
      if (!out) return false;
      if (out.result.state === "valid") {
        setSaveError(null);
        dispatch({ type: "add", change: out.move });
        return true;
      }
      toast.error("Can't move here", {
        description: out.result.reasons.map(text).join(" "),
      });
    } catch (e) {
      toast.error(describeFailure(e, "This move"));
    }
    return false;
  }

  // The blocker reads a ref so a save can navigate to the new draft without tripping it.
  const unsaved = useRef(0);
  useEffect(() => {
    unsaved.current = pending.length;
  });
  const blocker = useBlocker(() => unsaved.current > 0);

  async function save() {
    if (!version) return;
    setSaving(true);
    setSaveError(null);
    try {
      const draft = await createDraft(version.id, { changes: pending });
      unsaved.current = 0;
      dispatch({ type: "discard" });
      await queryClient.invalidateQueries({
        queryKey: getListVersionsQueryKey(scheduleId),
      });
      setParams({ version: draft.id });
      toast.success(`Saved as ${versionLabel(draft)}`);
    } catch (e) {
      if (isApiError(e) && e.status === 422) {
        const indexes = e.fieldErrors
          .map((f) => (f.path[0] === "changes" ? f.path[1] : undefined))
          .filter((i): i is number => typeof i === "number");
        const culprits = indexes.length
          ? indexes.flatMap((i) => (pending[i] ? [pending[i]] : []))
          : pending;
        const list = [
          ...new Set(
            culprits.map((c) => names.get(c.activity_id) ?? "Activity"),
          ),
        ];
        setSaveError(
          `These changes conflict with each other: ${list.join(", ")}`,
        );
      } else setSaveError(describeFailure(e, "This draft"));
    } finally {
      setSaving(false);
    }
  }

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
          actions={
            <>
              {version && (
                <ScorePanel scheduleId={scheduleId} score={version.score} />
              )}
              <SolveButton scheduleId={scheduleId} variant="outline" />
            </>
          }
        />
        <div id={BOARD_ID}>
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
              highlight={drag.highlight}
              canDrag={data.editable && canEdit}
              onOpenItem={openItem}
              onPickUp={(item, rowId) => void drag.pickUp(item, rowId)}
              onDrop={dropAt}
              onCheck={check}
              onCancel={drag.cancel}
              onHoverCheck={hoverCheck}
            />
          )}
        </div>
        <PendingTray
          changes={pending}
          describe={describe}
          onUndo={() => dispatch({ type: "undo" })}
          onDiscard={() => {
            setSaveError(null);
            dispatch({ type: "discard" });
          }}
          onSave={() => void save()}
          saving={saving}
          error={saveError}
        />
      </div>
      {version && (
        <ExplanationPanel
          scheduleId={scheduleId}
          versionId={version.id}
          item={selected?.item ?? null}
          rowId={selected?.rowId ?? ""}
          editable={data.editable}
          canEdit={canEdit}
          columnLabel={labelAt}
          codeOf={codeOf}
          onClose={() => setSelected(null)}
          onMoveHere={(change) => {
            setSelected(null);
            setSaveError(null);
            dispatch({ type: "add", change });
          }}
        />
      )}
      <ConfirmDialog
        open={blocker.state === "blocked"}
        onOpenChange={(open) => {
          if (!open) blocker.reset?.();
        }}
        title={`Discard ${String(pending.length)} unsaved ${pending.length === 1 ? "change" : "changes"}?`}
        description="Your moves have not been saved as a draft yet."
        confirmLabel="Discard"
        destructive
        onConfirm={() => {
          unsaved.current = 0;
          dispatch({ type: "discard" });
          blocker.proceed?.();
        }}
      />
    </>
  );
}
