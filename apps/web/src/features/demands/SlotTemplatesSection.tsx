import { useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import type { SlotTemplateResponse } from "@/api/generated/model";
import {
  deleteSlotTemplate,
  getListSlotTemplatesQueryKey,
  useListSlotTemplates,
} from "@/api/generated/schedules/schedules";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { describeFailure } from "@/lib/conflict";
import { WEEKDAYS, formatDuration, formatMinuteOfDay } from "@/lib/time";

import { SlotTemplateDialog } from "./SlotTemplateDialog";

const DAY_START = 6 * 60;
const DAY_END = 22 * 60;

function WeekPreview({ template }: { template: SlotTemplateResponse }) {
  return (
    <div className="grid grid-cols-7 gap-1" aria-hidden>
      {WEEKDAYS.map((day, d) => (
        <div key={day} className="flex flex-col gap-1">
          <span className="text-center text-[10px] font-medium text-muted-foreground uppercase">
            {day}
          </span>
          <div className="relative h-20 rounded bg-muted">
            {template.definition.slots
              .filter((s) => s.weekdays.includes(d))
              .map((s) => {
                const top =
                  ((Math.max(s.start_minute, DAY_START) - DAY_START) /
                    (DAY_END - DAY_START)) *
                  100;
                const height =
                  (Math.min(s.duration_minutes, DAY_END - s.start_minute) /
                    (DAY_END - DAY_START)) *
                  100;
                return (
                  <span
                    key={s.label}
                    className="absolute inset-x-0.5 rounded-sm bg-primary/70"
                    style={{
                      top: `${top}%`,
                      height: `${Math.max(height, 3)}%`,
                    }}
                  />
                );
              })}
          </div>
        </div>
      ))}
    </div>
  );
}

export function SlotTemplatesSection({
  scheduleId,
  canEdit,
}: {
  scheduleId: string;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();
  const { data: templates = [], isPending } = useListSlotTemplates(scheduleId);
  const [editing, setEditing] = useState<SlotTemplateResponse | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState<SlotTemplateResponse | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  async function remove() {
    if (!deleting) return;
    try {
      await deleteSlotTemplate(scheduleId, deleting.id);
      await queryClient.invalidateQueries({
        queryKey: getListSlotTemplatesQueryKey(scheduleId),
      });
    } catch (e) {
      setFailure(describeFailure(e, deleting.name));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <section aria-labelledby="slot-templates" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 id="slot-templates" className="font-semibold">
            Slot templates
          </h2>
          <p className="text-sm text-muted-foreground">
            The times activities may start, week by week.
          </p>
        </div>
        {canEdit && (
          <Button
            variant="outline"
            onClick={() => {
              setEditing(null);
              setDialogOpen(true);
            }}
          >
            New slot template
          </Button>
        )}
      </div>
      {failure && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{failure}</AlertDescription>
        </Alert>
      )}
      {!isPending && templates.length === 0 ? (
        <EmptyState
          title="No slot templates yet"
          description="Add the periods or shifts activities can use."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {templates.map((t) => (
            <article
              key={t.id}
              className="flex flex-col gap-3 rounded-lg border bg-card p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="font-medium">{t.name}</h3>
                  <p className="text-xs text-muted-foreground">
                    {t.definition.slots
                      .map(
                        (s) =>
                          `${s.label} ${formatMinuteOfDay(s.start_minute)} · ${formatDuration(s.duration_minutes)}`,
                      )
                      .join(", ")}
                  </p>
                </div>
                {canEdit && (
                  <div className="flex shrink-0">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Edit ${t.name}`}
                      onClick={() => {
                        setEditing(t);
                        setDialogOpen(true);
                      }}
                    >
                      <Pencil className="size-4" aria-hidden />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete ${t.name}`}
                      onClick={() => setDeleting(t)}
                    >
                      <Trash2 className="size-4" aria-hidden />
                    </Button>
                  </div>
                )}
              </div>
              <WeekPreview template={t} />
            </article>
          ))}
        </div>
      )}
      {dialogOpen && (
        <SlotTemplateDialog
          scheduleId={scheduleId}
          editing={editing}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        />
      )}
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title={`Delete ${deleting?.name ?? ""}?`}
        description="Templates still used by demands cannot be deleted."
        confirmLabel="Delete"
        destructive
        onConfirm={() => void remove()}
      />
    </section>
  );
}
