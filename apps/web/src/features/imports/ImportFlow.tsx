import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  commitImport,
  createImport,
  dryRunImport,
  uploadImportFile,
} from "@/api/generated/imports/imports";
import type {
  DemandMapping,
  ImportReport,
  ImportResponse,
  ResourceMapping,
  ResourceTypeResponse,
} from "@/api/generated/model";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { describeFailure } from "@/lib/conflict";

import { DemandMappingForm, type DemandPreset } from "./DemandMappingForm";
import { ImportReportView } from "./ImportReportView";
import { ResourceMappingForm } from "./ResourceMappingForm";

export type ImportTarget =
  | { kind: "resources"; resourceType: ResourceTypeResponse }
  | { kind: "demands"; scheduleId: string; preset?: DemandPreset };

type Step =
  | { at: "file" }
  | { at: "map"; job: ImportResponse }
  | { at: "report"; job: ImportResponse; report: ImportReport };

export function ImportFlow({
  target,
  onCommitted,
}: {
  target: ImportTarget;
  onCommitted: (report: ImportReport) => void;
}) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<Step>({ at: "file" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setMessage(null);
    try {
      await work();
    } catch (error) {
      setMessage(describeFailure(error, "This import"));
    } finally {
      setBusy(false);
    }
  }

  const upload = (file: File) =>
    run(async () => {
      const job = await createImport({
        kind: target.kind,
        filename: file.name,
        resource_type_id:
          target.kind === "resources" ? target.resourceType.id : null,
        schedule_id: target.kind === "demands" ? target.scheduleId : null,
      });
      setStep({ at: "map", job: await uploadImportFile(job.id, file) });
    });

  const dryRun = (
    job: ImportResponse,
    mapping: ResourceMapping | DemandMapping,
  ) =>
    run(async () => {
      const checked = await dryRunImport(job.id, { mapping });
      if (checked.report)
        setStep({ at: "report", job: checked, report: checked.report });
    });

  const commit = (job: ImportResponse) =>
    run(async () => {
      const done = await commitImport(job.id);
      // An import touches resources or demands and activities; refresh everything cached.
      await queryClient.invalidateQueries();
      if (done.report) onCommitted(done.report);
    });

  return (
    <div className="flex flex-col gap-4">
      {message && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}
      {step.at === "file" && (
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">1. Choose a CSV file</h3>
          <Label htmlFor="csv-file" className="sr-only">
            CSV file
          </Label>
          <Input
            id="csv-file"
            type="file"
            accept=".csv,text/csv"
            disabled={busy}
            aria-describedby="csv-file-hint"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void upload(file);
            }}
          />
          <p id="csv-file-hint" className="text-xs text-muted-foreground">
            Up to 5 MB and 20,000 rows. The first row must hold column names.
          </p>
        </section>
      )}
      {step.at === "map" && (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-medium">2. Match columns</h3>
          {target.kind === "resources" ? (
            <ResourceMappingForm
              type={target.resourceType}
              columns={step.job.columns ?? []}
              busy={busy}
              onSubmit={(mapping) => void dryRun(step.job, mapping)}
            />
          ) : (
            <DemandMappingForm
              scheduleId={target.scheduleId}
              columns={step.job.columns ?? []}
              preset={target.preset}
              busy={busy}
              onSubmit={(mapping) => void dryRun(step.job, mapping)}
            />
          )}
        </section>
      )}
      {step.at === "report" && (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-medium">3. Check the dry run</h3>
          <ImportReportView
            report={step.report}
            busy={busy}
            onBack={() => setStep({ at: "map", job: step.job })}
            onCommit={() => void commit(step.job)}
          />
        </section>
      )}
    </div>
  );
}
