import { useState } from "react";
import { toast } from "sonner";

import { useListImports } from "@/api/generated/imports/imports";
import { useListResourceTypes } from "@/api/generated/resources/resources";
import { useListSchedules } from "@/api/generated/schedules/schedules";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/lib/auth/AuthProvider";
import { NativeSelect } from "@/components/NativeSelect";

import { ImportFlow, type ImportTarget } from "./ImportFlow";

const STATUS: Record<string, string> = {
  awaiting_file: "Waiting for file",
  uploaded: "Uploaded",
  validated: "Checked",
  invalid: "Has errors",
  committed: "Imported",
};

function NewImportDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: types = [] } = useListResourceTypes();
  const { data: schedules = [] } = useListSchedules();
  const [choice, setChoice] = useState("");
  const [target, setTarget] = useState<ImportTarget | null>(null);

  const options = [
    ...types.map((t) => ({
      value: `type:${t.id}`,
      label: `Resources — ${t.name}`,
    })),
    ...schedules.map((s) => ({
      value: `schedule:${s.id}`,
      label: `Demands — ${s.name}`,
    })),
  ];

  function start() {
    const [kind, id = ""] = choice.split(":");
    if (kind === "type") {
      const type = types.find((t) => t.id === id);
      if (type) setTarget({ kind: "resources", resourceType: type });
    } else if (kind === "schedule") {
      setTarget({ kind: "demands", scheduleId: id });
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>New import</DialogTitle>
        </DialogHeader>
        {target ? (
          <ImportFlow
            target={target}
            onCommitted={(report) => {
              toast.success(`${report.created} rows imported`);
              onOpenChange(false);
            }}
          />
        ) : (
          <div className="flex flex-col gap-3">
            <Label htmlFor="import-target">What are you importing?</Label>
            <NativeSelect
              id="import-target"
              value={choice}
              onChange={(e) => setChoice(e.target.value)}
            >
              <option value="">Choose…</option>
              {options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </NativeSelect>
            <Button className="self-start" disabled={!choice} onClick={start}>
              Continue
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function ImportsPage() {
  const { can } = useAuth();
  const { data: imports = [], isPending } = useListImports();
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader
        title="Imports"
        description="Bring resources and demands in from CSV files, checked before anything is saved."
        actions={
          can("config.manage") && (
            <Button onClick={() => setCreating(true)}>New import</Button>
          )
        }
      />
      <div className="px-4 py-6 sm:px-6 lg:px-8">
        {isPending ? (
          <TableSkeleton label="Loading imports" />
        ) : imports.length === 0 ? (
          <EmptyState
            illustration="import"
            title="No imports yet"
            description="Start one to bring in lecturers, rooms, staff or demands."
          />
        ) : (
          <div className="rounded-xl border bg-card shadow-sm">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>File</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Rows</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {imports.map((i) => (
                  <TableRow key={i.id}>
                    <TableCell className="font-medium">{i.filename}</TableCell>
                    <TableCell>
                      {i.kind === "resources" ? "Resources" : "Demands"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          i.status === "invalid" ? "destructive" : "secondary"
                        }
                      >
                        {STATUS[i.status] ?? i.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {i.report?.row_count ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
      {creating && (
        <NewImportDialog open={creating} onOpenChange={setCreating} />
      )}
    </>
  );
}
