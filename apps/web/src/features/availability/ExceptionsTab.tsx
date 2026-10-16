import { useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import type { AvailabilityExceptionResponse } from "@/api/generated/model";
import {
  createAvailabilityException,
  deleteAvailabilityException,
  getListAvailabilityExceptionsQueryKey,
  useListAvailabilityExceptions,
} from "@/api/generated/resources/resources";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { FieldError } from "@/components/FieldError";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { describeFailure } from "@/lib/conflict";
import { SELECT_CLASS } from "@/lib/styles";
import { browserTimezone, formatInZone, toUtcIso } from "@/lib/time";

import type { Kind } from "./grid";

const KIND_LABELS: Record<Kind, string> = {
  available: "Available",
  preferred: "Preferred",
  avoided: "Avoid if possible",
  unavailable: "Unavailable",
};

export function ExceptionsTab({
  resourceId,
  canEdit,
}: {
  resourceId: string;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();
  const tz = browserTimezone();
  const { data: exceptions = [] } = useListAvailabilityExceptions(resourceId);
  const [kind, setKind] = useState<Kind>("unavailable");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [deleting, setDeleting] =
    useState<AvailabilityExceptionResponse | null>(null);
  const refresh = () =>
    queryClient.invalidateQueries({
      queryKey: getListAvailabilityExceptionsQueryKey(resourceId),
    });

  async function add() {
    setError(null);
    setMessage(null);
    if (!from || !to) {
      setError("Enter a start and an end");
      return;
    }
    // ISO local date-times compare correctly as strings.
    if (to <= from) {
      setError("End must be after start");
      return;
    }
    try {
      await createAvailabilityException(resourceId, {
        kind,
        starts_at: toUtcIso(from, tz),
        ends_at: toUtcIso(to, tz),
        reason: reason.trim() || null,
      });
      setFrom("");
      setTo("");
      setReason("");
      await refresh();
      toast.success("Exception added");
    } catch (e) {
      setMessage(describeFailure(e, "This exception"));
    }
  }

  async function remove() {
    if (!deleting) return;
    try {
      await deleteAvailabilityException(resourceId, deleting.id);
      await refresh();
    } catch (e) {
      setMessage(describeFailure(e, "This exception"));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="flex flex-col gap-4 pt-2">
      {message && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}
      {canEdit && (
        <form
          className="grid items-end gap-3 rounded-lg border bg-card p-4 md:grid-cols-[10rem_1fr_1fr_1fr_auto]"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void add();
          }}
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="exc-kind">Kind</Label>
            <select
              id="exc-kind"
              className={SELECT_CLASS}
              value={kind}
              onChange={(e) => {
                setKind(e.target.value as Kind);
              }}
            >
              {Object.entries(KIND_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="exc-from">From</Label>
            <Input
              id="exc-from"
              type="datetime-local"
              value={from}
              onChange={(e) => {
                setFrom(e.target.value);
              }}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="exc-to">To</Label>
            <Input
              id="exc-to"
              type="datetime-local"
              value={to}
              onChange={(e) => {
                setTo(e.target.value);
              }}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="exc-reason">Reason</Label>
            <Input
              id="exc-reason"
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
              }}
            />
          </div>
          <Button type="submit">Add exception</Button>
          <p className="text-xs text-muted-foreground md:col-span-5">
            Times in {tz}.
          </p>
          <div className="md:col-span-5">
            <FieldError message={error ?? undefined} />
          </div>
        </form>
      )}
      {exceptions.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No exceptions. Add leave, holidays or one-off changes here.
        </p>
      ) : (
        <div className="rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Kind</TableHead>
                <TableHead>From</TableHead>
                <TableHead>To</TableHead>
                <TableHead>Reason</TableHead>
                {canEdit && (
                  <TableHead className="w-12">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {exceptions.map((exc) => (
                <TableRow key={exc.id}>
                  <TableCell>{KIND_LABELS[exc.kind]}</TableCell>
                  <TableCell>{formatInZone(exc.starts_at, tz)}</TableCell>
                  <TableCell>{formatInZone(exc.ends_at, tz)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {exc.reason ?? "—"}
                  </TableCell>
                  {canEdit && (
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete exception from ${formatInZone(exc.starts_at, tz)}`}
                        onClick={() => {
                          setDeleting(exc);
                        }}
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
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title="Delete this exception?"
        description="The resource's weekly availability applies again for this period."
        confirmLabel="Delete"
        destructive
        onConfirm={() => void remove()}
      />
    </div>
  );
}
