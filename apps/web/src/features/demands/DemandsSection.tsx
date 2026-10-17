import { useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  deleteDemand,
  getListActivitiesQueryKey,
  getListDemandsQueryKey,
  useListDemands,
} from "@/api/generated/activities/activities";
import type { DemandResponse } from "@/api/generated/model";
import { useListSlotTemplates } from "@/api/generated/schedules/schedules";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { describeFailure } from "@/lib/conflict";

import { DemandDialog } from "./DemandDialog";

export function DemandsSection({
  scheduleId,
  canEdit,
}: {
  scheduleId: string;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();
  const { data: demands = [], isPending } = useListDemands(scheduleId);
  const { data: templates = [] } = useListSlotTemplates(scheduleId);
  const [editing, setEditing] = useState<DemandResponse | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState<DemandResponse | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const templateName = new Map(templates.map((t) => [t.id, t.name]));

  async function remove() {
    if (!deleting) return;
    try {
      await deleteDemand(scheduleId, deleting.id);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: getListDemandsQueryKey(scheduleId),
        }),
        queryClient.invalidateQueries({
          queryKey: getListActivitiesQueryKey(scheduleId),
        }),
      ]);
    } catch (e) {
      setFailure(describeFailure(e, deleting.name));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <section aria-labelledby="demands" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 id="demands" className="font-semibold">
            Demands
          </h2>
          <p className="text-sm text-muted-foreground">
            What needs scheduling and what each activity requires.
          </p>
        </div>
        {canEdit && templates.length > 0 && (
          <Button
            onClick={() => {
              setEditing(null);
              setDialogOpen(true);
            }}
          >
            New demand
          </Button>
        )}
      </div>
      {failure && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{failure}</AlertDescription>
        </Alert>
      )}
      {isPending ? (
        <TableSkeleton label="Loading demands" />
      ) : demands.length === 0 ? (
        <EmptyState
          illustration="empty"
          title="No demands yet"
          description="Import them from a CSV on the Imports page, or add one here once a slot template exists."
        />
      ) : (
        <div className="rounded-xl border bg-card shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Kind</TableHead>
                <TableHead>Slot template</TableHead>
                <TableHead className="text-right">Per week</TableHead>
                <TableHead className="text-right">Activities</TableHead>
                {canEdit && (
                  <TableHead className="w-24">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {demands.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="font-medium">{d.name}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">
                      {d.spec.kind === "session" ? "Sessions" : "Coverage"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {templateName.get(d.slot_template_id) ?? "—"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {d.spec.kind === "session"
                      ? d.spec.sessions_per_week
                      : "every slot"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {d.activity_count}
                  </TableCell>
                  {canEdit && (
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Edit ${d.name}`}
                        onClick={() => {
                          setEditing(d);
                          setDialogOpen(true);
                        }}
                      >
                        <Pencil className="size-4" aria-hidden />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete ${d.name}`}
                        onClick={() => setDeleting(d)}
                      >
                        <Trash2 className="size-4" aria-hidden />
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {dialogOpen && (
        <DemandDialog
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
        description="Its activities and pins are removed. Demands named by a rule cannot be deleted."
        confirmLabel="Delete"
        destructive
        onConfirm={() => void remove()}
      />
    </section>
  );
}
