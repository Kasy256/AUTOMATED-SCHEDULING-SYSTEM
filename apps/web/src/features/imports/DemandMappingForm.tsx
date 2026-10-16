import { Trash2 } from "lucide-react";
import { useState } from "react";

import type {
  DemandMapping,
  RequirementMapping,
  TemplateDemandShape,
} from "@/api/generated/model";
import { useListResourceTypes } from "@/api/generated/resources/resources";
import { useListSlotTemplates } from "@/api/generated/schedules/schedules";
import { FieldError } from "@/components/FieldError";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SELECT_CLASS } from "@/lib/styles";

import { demandMappingFromTemplate } from "./mapping";

export interface DemandPreset {
  shape: TemplateDemandShape;
  slotTemplateId: string;
  typeIdByKey: Record<string, string>;
}

function Column({
  id,
  label,
  columns,
  value,
  onChange,
}: {
  id: string;
  label: string;
  columns: string[];
  value: string | null | undefined;
  onChange: (c: string | null) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <select
        id={id}
        className={SELECT_CLASS}
        value={value ?? ""}
        onChange={(e) =>
          onChange(e.target.value === "" ? null : e.target.value)
        }
      >
        <option value="">— not in this file —</option>
        {columns.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
    </div>
  );
}

function PresetForm({
  preset,
  busy,
  onSubmit,
}: {
  preset: DemandPreset;
  busy: boolean;
  onSubmit: (m: DemandMapping) => void;
}) {
  const [term, setTerm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const split = preset.shape.term_split;
  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (split && !term.trim()) {
          setError("Enter the term to import");
          return;
        }
        onSubmit(
          demandMappingFromTemplate(
            preset.shape,
            preset,
            split ? term.trim() : null,
          ),
        );
      }}
    >
      <p className="text-sm text-muted-foreground">
        Columns are matched by the industry template: names from{" "}
        <code>{preset.shape.name_column}</code>, and{" "}
        {preset.shape.requirements.map((r) => r.role).join(", ")} requirements.
      </p>
      {split && (
        <div className="flex max-w-xs flex-col gap-1.5">
          <Label htmlFor="map-term">Term</Label>
          <Input
            id="map-term"
            value={term}
            aria-describedby="map-term-hint"
            onChange={(e) => setTerm(e.target.value)}
          />
          <p id="map-term-hint" className="text-xs text-muted-foreground">
            {`As written in the ${split.term_column} column, for example ‘Term 1’.`}
          </p>
          <FieldError message={error ?? undefined} />
        </div>
      )}
      <Button type="submit" className="self-start" disabled={busy}>
        Run dry run
      </Button>
    </form>
  );
}

const emptyRequirement = (): RequirementMapping => ({
  role: "",
  resource_type_id: null,
  count_min: 1,
  count_max: 1,
  count_from_fixed: false,
  hard: true,
  weight: 0,
  tags_column: null,
  fixed_codes_column: null,
  attribute_columns: {},
});

function ManualForm({
  scheduleId,
  columns,
  busy,
  onSubmit,
}: {
  scheduleId: string;
  columns: string[];
  busy: boolean;
  onSubmit: (m: DemandMapping) => void;
}) {
  const { data: slotTemplates = [] } = useListSlotTemplates(scheduleId);
  const { data: types = [] } = useListResourceTypes();
  const [kind, setKind] = useState<"session" | "coverage">("session");
  const [slotTemplateId, setSlotTemplateId] = useState("");
  const [name, setName] = useState<string | null>(
    columns.find((c) => c.toLowerCase() === "name") ?? null,
  );
  const [sessions, setSessions] = useState<string | null>(null);
  const [weekly, setWeekly] = useState<string | null>(null);
  const [duration, setDuration] = useState<string | null>(null);
  const [labels, setLabels] = useState<string | null>(null);
  const [requirements, setRequirements] = useState<RequirementMapping[]>([
    emptyRequirement(),
  ]);
  const [error, setError] = useState<string | null>(null);
  const chosenTemplate =
    slotTemplateId !== "" ? slotTemplateId : (slotTemplates[0]?.id ?? "");
  const patch = (i: number, p: Partial<RequirementMapping>) =>
    setRequirements((rs) => rs.map((r, j) => (j === i ? { ...r, ...p } : r)));

  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (!name || !chosenTemplate) {
          setError("Choose a slot template and the name column");
          return;
        }
        if (requirements.some((r) => !/^[a-z][a-z0-9_]{0,62}$/.test(r.role))) {
          setError(
            "Each requirement needs a role key (lowercase letters, digits and _)",
          );
          return;
        }
        setError(null);
        onSubmit({
          kind: "demands",
          demand_kind: kind,
          slot_template_id: chosenTemplate,
          name,
          sessions_per_week: sessions,
          weekly_minutes: weekly,
          duration_minutes: duration,
          slot_labels: labels,
          requirements,
          term_split: null,
        });
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="map-kind">Demand kind</Label>
          <select
            id="map-kind"
            className={SELECT_CLASS}
            value={kind}
            onChange={(e) => setKind(e.target.value as "session" | "coverage")}
          >
            <option value="session">Weekly sessions</option>
            <option value="coverage">Cover every slot</option>
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="map-slot-template">Slot template</Label>
          <select
            id="map-slot-template"
            className={SELECT_CLASS}
            value={chosenTemplate}
            onChange={(e) => setSlotTemplateId(e.target.value)}
          >
            {slotTemplates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
        <Column
          id="map-name"
          label="Name column"
          columns={columns}
          value={name}
          onChange={setName}
        />
        {kind === "session" && (
          <>
            <Column
              id="map-sessions"
              label="Sessions per week column"
              columns={columns}
              value={sessions}
              onChange={setSessions}
            />
            <Column
              id="map-weekly"
              label="Weekly minutes column"
              columns={columns}
              value={weekly}
              onChange={setWeekly}
            />
            <Column
              id="map-duration"
              label="Duration column"
              columns={columns}
              value={duration}
              onChange={setDuration}
            />
          </>
        )}
        <Column
          id="map-labels"
          label="Slot labels column"
          columns={columns}
          value={labels}
          onChange={setLabels}
        />
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-medium">Requirements</legend>
        {requirements.map((r, i) => (
          <div
            key={i}
            className="grid items-end gap-2 rounded-lg border p-3 sm:grid-cols-3 lg:grid-cols-4"
          >
            <div className="flex flex-col gap-1.5">
              <Label
                htmlFor={`map-req-${i}-role`}
              >{`Requirement ${i + 1} role`}</Label>
              <Input
                id={`map-req-${i}-role`}
                value={r.role}
                onChange={(e) => patch(i, { role: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label
                htmlFor={`map-req-${i}-type`}
              >{`Requirement ${i + 1} resource type`}</Label>
              <select
                id={`map-req-${i}-type`}
                className={SELECT_CLASS}
                value={r.resource_type_id ?? ""}
                onChange={(e) =>
                  patch(i, { resource_type_id: e.target.value || null })
                }
              >
                <option value="">Any type</option>
                {types.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            <Column
              id={`map-req-${i}-tags`}
              label={`Requirement ${i + 1} tags column`}
              columns={columns}
              value={r.tags_column}
              onChange={(c) => patch(i, { tags_column: c })}
            />
            <Column
              id={`map-req-${i}-fixed`}
              label={`Requirement ${i + 1} fixed codes column`}
              columns={columns}
              value={r.fixed_codes_column}
              onChange={(c) => patch(i, { fixed_codes_column: c })}
            />
            <div className="flex flex-col gap-1.5">
              <Label
                htmlFor={`map-req-${i}-min`}
              >{`Requirement ${i + 1} min`}</Label>
              <Input
                id={`map-req-${i}-min`}
                type="number"
                min={0}
                value={r.count_min}
                onChange={(e) =>
                  patch(i, { count_min: Number(e.target.value) })
                }
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label
                htmlFor={`map-req-${i}-max`}
              >{`Requirement ${i + 1} max`}</Label>
              <Input
                id={`map-req-${i}-max`}
                type="number"
                min={1}
                value={r.count_max}
                onChange={(e) =>
                  patch(i, { count_max: Number(e.target.value) })
                }
              />
            </div>
            <label className="flex items-center gap-2 pb-2 text-sm">
              <input
                type="checkbox"
                checked={r.count_from_fixed}
                onChange={(e) =>
                  patch(i, { count_from_fixed: e.target.checked })
                }
              />
              Count from fixed codes
            </label>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Remove requirement ${i + 1}`}
              onClick={() =>
                setRequirements((rs) => rs.filter((_, j) => j !== i))
              }
            >
              <Trash2 className="size-4" aria-hidden />
            </Button>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start"
          onClick={() => setRequirements((rs) => [...rs, emptyRequirement()])}
        >
          Add requirement
        </Button>
      </fieldset>
      <FieldError message={error ?? undefined} />
      <Button type="submit" className="self-start" disabled={busy}>
        Run dry run
      </Button>
    </form>
  );
}

export function DemandMappingForm({
  scheduleId,
  columns,
  preset,
  busy,
  onSubmit,
}: {
  scheduleId: string;
  columns: string[];
  preset: DemandPreset | undefined;
  busy: boolean;
  onSubmit: (mapping: DemandMapping) => void;
}) {
  if (preset)
    return <PresetForm preset={preset} busy={busy} onSubmit={onSubmit} />;
  return (
    <ManualForm
      scheduleId={scheduleId}
      columns={columns}
      busy={busy}
      onSubmit={onSubmit}
    />
  );
}
