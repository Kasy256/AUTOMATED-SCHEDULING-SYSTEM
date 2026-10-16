import { useState } from "react";

import { useListImports } from "@/api/generated/imports/imports";
import type { IndustryTemplateDefinition } from "@/api/generated/model";
import { useListResourceTypes } from "@/api/generated/resources/resources";
import { useListSlotTemplates } from "@/api/generated/schedules/schedules";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ImportFlow, type ImportTarget } from "@/features/imports/ImportFlow";

import { importRows } from "./wizardState";

export function ImportStep({
  template,
  scheduleId,
  onContinue,
}: {
  template: IndustryTemplateDefinition;
  scheduleId: string;
  onContinue: () => void;
}) {
  const { data: types = [] } = useListResourceTypes();
  const { data: imports = [] } = useListImports();
  const { data: slotTemplates = [] } = useListSlotTemplates(scheduleId);
  const [open, setOpen] = useState<string | null>(null);
  const rows = importRows(template, types, imports, scheduleId);
  const shape = template.demand_shape;
  const slotTemplate = shape
    ? slotTemplates.find((t) => t.name === shape.slot_template)
    : undefined;
  const demandTarget: ImportTarget | null =
    shape && slotTemplate
      ? {
          kind: "demands",
          scheduleId,
          preset: {
            shape,
            slotTemplateId: slotTemplate.id,
            typeIdByKey: Object.fromEntries(types.map((t) => [t.key, t.id])),
          },
        }
      : shape
        ? null
        : { kind: "demands", scheduleId };

  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Import your data
        </h1>
        <p className="text-muted-foreground">
          Upload one CSV per type. The column mapping is pre-filled where it can
          be, and nothing is saved until you confirm the dry run. Every step can
          be skipped and done later from Imports.
        </p>
      </div>
      {rows.map((row) => {
        const target = row.key === "demands" ? demandTarget : row.target;
        const blocked = row.blockedBy.length > 0;
        return (
          <section
            key={row.key}
            aria-label={row.label}
            className="flex flex-col gap-3 rounded-lg border bg-card p-4"
          >
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="flex-1 font-medium">{row.label}</h2>
              {row.done ? (
                <Badge>{`Imported · ${row.done.report?.row_count ?? 0} rows`}</Badge>
              ) : blocked ? (
                <Badge variant="secondary">{`Waiting for: ${row.blockedBy.join(", ")}`}</Badge>
              ) : (
                <Badge variant="secondary">Not started</Badge>
              )}
              {!row.done && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={blocked || target === null}
                  onClick={() => setOpen(open === row.key ? null : row.key)}
                >
                  Upload CSV
                </Button>
              )}
            </div>
            {open === row.key && target && (
              <ImportFlow target={target} onCommitted={() => setOpen(null)} />
            )}
          </section>
        );
      })}
      <div className="flex justify-between gap-2">
        <Button variant="outline" onClick={onContinue}>
          Skip for now
        </Button>
        <Button onClick={onContinue}>Continue</Button>
      </div>
    </section>
  );
}
