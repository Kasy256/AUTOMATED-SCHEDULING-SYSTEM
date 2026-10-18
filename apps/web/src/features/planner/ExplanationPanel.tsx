import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import {
  deletePin,
  getListPinsQueryKey,
  putPin,
} from "@/api/generated/activities/activities";
import type { AssignmentEdit } from "@/api/generated/model";
import { useExplainAssignment } from "@/api/generated/versions/versions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { describeFailure } from "@/lib/conflict";
import { useEngineText } from "@/lib/engineText";

import type { BoardItem } from "./model/items";

export function ExplanationPanel({
  scheduleId,
  versionId,
  item,
  rowId,
  editable,
  canEdit,
  columnLabel,
  codeOf,
  onClose,
  onMoveHere,
}: {
  scheduleId: string;
  versionId: string;
  item: BoardItem | null;
  rowId: string;
  editable: boolean;
  canEdit: boolean;
  columnLabel: (start: string) => string;
  codeOf: (id: string) => string;
  onClose: () => void;
  onMoveHere: (move: AssignmentEdit) => void;
}) {
  return (
    <Sheet
      open={item !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        {item && (
          <Body
            key={item.activityId}
            scheduleId={scheduleId}
            versionId={versionId}
            item={item}
            rowId={rowId}
            editable={editable}
            canEdit={canEdit}
            columnLabel={columnLabel}
            codeOf={codeOf}
            onMoveHere={onMoveHere}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}

function Body({
  scheduleId,
  versionId,
  item,
  rowId,
  editable,
  canEdit,
  columnLabel,
  codeOf,
  onMoveHere,
}: {
  scheduleId: string;
  versionId: string;
  item: BoardItem;
  rowId: string;
  editable: boolean;
  canEdit: boolean;
  columnLabel: (start: string) => string;
  codeOf: (id: string) => string;
  onMoveHere: (move: AssignmentEdit) => void;
}) {
  const text = useEngineText(scheduleId);
  const queryClient = useQueryClient();
  const [pinned, setPinned] = useState(item.pinned);
  const [busy, setBusy] = useState(false);
  const { data, isPending, error } = useExplainAssignment(
    versionId,
    item.activityId,
  );
  const binding = [...(data?.binding ?? [])].sort(
    (a, b) =>
      Number(b.hard) - Number(a.hard) ||
      b.blocks + b.penalises - (a.blocks + a.penalises),
  );
  const codes = (resources: Record<string, string[]>) =>
    Object.values(resources)
      .flat()
      .filter((id) => id !== rowId)
      .map(codeOf)
      .join(" · ");

  async function togglePin() {
    setBusy(true);
    try {
      if (pinned) await deletePin(scheduleId, item.activityId);
      else
        await putPin(scheduleId, item.activityId, {
          start_at: item.start,
          resources: item.resources,
        });
      setPinned(!pinned);
      await queryClient.invalidateQueries({
        queryKey: getListPinsQueryKey(scheduleId),
      });
    } catch (e) {
      toast.error(describeFailure(e, "This pin"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <SheetHeader>
        <SheetTitle>{item.name}</SheetTitle>
        <SheetDescription>
          {columnLabel(item.start)}
          {codes(item.resources) ? ` · ${codes(item.resources)}` : ""}
        </SheetDescription>
      </SheetHeader>
      <div className="flex flex-col gap-6 px-4 pb-6">
        {canEdit && (
          <Button
            variant="outline"
            className="self-start"
            disabled={busy}
            onClick={() => void togglePin()}
          >
            {pinned ? "Unpin" : "Pin"}
          </Button>
        )}
        {isPending ? (
          <div
            role="status"
            aria-label="Loading the explanation"
            className="flex flex-col gap-2"
          >
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-5 w-1/2" />
            <Skeleton className="h-5 w-3/4" />
          </div>
        ) : error ? (
          <p role="alert" className="text-sm text-destructive">
            {describeFailure(error, "This explanation")}
          </p>
        ) : (
          <>
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold">Why it's here</h3>
              {binding.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No rule holds it here; other places are equally good.
                </p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {binding.map((b) => (
                    <li
                      key={b.constraint_id}
                      className="flex flex-col gap-0.5 rounded-lg border px-3 py-2"
                    >
                      <span className="text-sm font-medium">
                        {text(b.rule)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {b.hard
                          ? `Blocks ${String(b.blocks)} alternatives`
                          : `Adds ${String(b.penalises)} penalty`}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold">Alternatives</h3>
              {data.alternatives.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No other placement was checked.
                </p>
              )}
              <ul className="flex flex-col gap-2">
                {data.alternatives.map((alt, i) => (
                  <li
                    key={i}
                    className="flex flex-col gap-1 rounded-lg border px-3 py-2"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium">
                        {columnLabel(alt.start_at)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {codes(alt.resources)}
                      </span>
                      {alt.check.valid && (
                        <Badge className="ml-auto">Valid</Badge>
                      )}
                    </div>
                    {alt.check.valid ? (
                      canEdit &&
                      editable && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="self-start"
                          onClick={() =>
                            onMoveHere({
                              activity_id: item.activityId,
                              start_at: alt.start_at,
                              resources: alt.resources,
                            })
                          }
                        >
                          Move here
                        </Button>
                      )
                    ) : (
                      <ul className="text-xs text-destructive">
                        {alt.check.broken.map((b, j) => (
                          <li key={j}>{text(b.message)}</li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
              {data.truncated && (
                <p className="text-xs text-muted-foreground">
                  Showing the first 100 checked alternatives.
                </p>
              )}
            </section>
          </>
        )}
      </div>
    </>
  );
}
