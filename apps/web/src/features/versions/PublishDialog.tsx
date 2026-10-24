import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import type { VersionSummary } from "@/api/generated/model";
import {
  archive,
  publish,
  useDiffVersions,
} from "@/api/generated/versions/versions";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { describeFailure } from "@/lib/conflict";

import { diffSummary } from "./model";

function refreshVersions(queryClient: QueryClient) {
  return queryClient.invalidateQueries({
    predicate: (q) => String(q.queryKey[0]).includes("versions"),
  });
}

function ChangeSummary({
  from,
  to,
  scheduleId,
}: {
  from: VersionSummary;
  to: VersionSummary;
  scheduleId: string;
}) {
  const { data, isPending } = useDiffVersions(from.id, to.id);
  return (
    <p className="text-sm">
      {isPending || !data ? (
        "Loading changes…"
      ) : (
        <>
          {`Compared with version ${String(from.number)}: `}
          <span className="font-medium">{diffSummary(data).text}</span>.
        </>
      )}{" "}
      <Link
        className="font-medium text-primary hover:underline"
        to={`/schedules/${scheduleId}/versions/${from.id}/compare/${to.id}`}
      >
        See all changes
      </Link>
    </p>
  );
}

export function PublishButton({
  version,
  versions,
  scheduleId,
}: {
  version: VersionSummary;
  versions: VersionSummary[];
  scheduleId: string;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const published = versions.find((v) => v.status === "published");
  const newest = Math.max(...versions.map((v) => v.number));
  const n = String(version.number);

  async function confirm() {
    setBusy(true);
    try {
      await publish(version.id);
      await refreshVersions(queryClient);
      setOpen(false);
      toast.success(
        `Version ${n} published — affected people are being emailed`,
      );
    } catch (e) {
      toast.error(describeFailure(e, "This version"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        Publish
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{`Publish version ${n}?`}</DialogTitle>
            <DialogDescription>
              People affected will be emailed. The published version becomes
              read-only.
            </DialogDescription>
          </DialogHeader>
          {open && published && (
            <ChangeSummary
              from={published}
              to={version}
              scheduleId={scheduleId}
            />
          )}
          {version.number < newest && (
            <p className="text-sm font-medium text-amber-800">
              {`Version ${n} is not the newest version.`}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button disabled={busy} onClick={() => void confirm()}>
              Publish
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function ArchiveButton({
  version,
}: {
  version: VersionSummary;
  scheduleId: string;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const n = String(version.number);

  async function confirm() {
    setBusy(true);
    try {
      await archive(version.id);
      await refreshVersions(queryClient);
      setOpen(false);
      toast.success(`Version ${n} archived`);
    } catch (e) {
      toast.error(describeFailure(e, "This version"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        Archive
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={`Archive version ${n}?`}
        description="It stays viewable but can't be published."
        confirmLabel="Archive"
        destructive
        pending={busy}
        onConfirm={() => void confirm()}
      />
    </>
  );
}
