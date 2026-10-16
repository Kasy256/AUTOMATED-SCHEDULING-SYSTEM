import { useListResourceTypes } from "@/api/generated/resources/resources";
import { MultiPicker } from "@/components/MultiPicker";
import { PredicateList } from "@/components/PredicateList";
import { TagInput } from "@/components/TagInput";
import { Label } from "@/components/ui/label";

import { useRefOptions } from "./schema-form/RefOptions";
import { describeScope, type ScopeValue } from "./scope";

export function ScopeBuilder({
  scheduleId,
  value,
  onChange,
  readOnly = false,
}: {
  scheduleId: string;
  value: ScopeValue;
  onChange: (next: ScopeValue) => void;
  readOnly?: boolean;
}) {
  const { data: types = [] } = useListResourceTypes();
  const refs = useRefOptions(scheduleId);
  const typeOptions = types.map((t) => ({ value: t.id, label: t.name }));
  const label = (options: { value: string; label: string }[]) => (id: string) =>
    options.find((o) => o.value === id)?.label ?? "an unknown item";
  const summary = describeScope(value, {
    type: label(typeOptions),
    resource: label(refs.resource),
    demand: label(refs.series),
  });

  return (
    <fieldset className="flex flex-col gap-4" disabled={readOnly}>
      <legend className="text-sm font-medium">Applies to</legend>
      <p className="rounded-md bg-muted px-3 py-2 text-sm">{`Applies to: ${summary}`}</p>
      <p className="text-xs text-muted-foreground">
        Leave everything empty to apply the rule to the whole schedule.
      </p>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="scope-types">Resource types</Label>
        <MultiPicker
          id="scope-types"
          label="Resource types"
          options={typeOptions}
          value={value.resource_type_ids}
          onChange={(resource_type_ids) =>
            onChange({ ...value, resource_type_ids })
          }
          disabled={readOnly}
          placeholder="Any type"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="scope-tags">Tags</Label>
        <TagInput
          id="scope-tags"
          value={value.tags}
          onChange={(tags) => onChange({ ...value, tags })}
        />
      </div>
      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-sm">Conditions</legend>
        <PredicateList
          idPrefix="scope-attr"
          value={value.attrs}
          onChange={(attrs) => onChange({ ...value, attrs })}
          disabled={readOnly}
        />
      </fieldset>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="scope-resources">Specific resources</Label>
        <MultiPicker
          id="scope-resources"
          label="Specific resources"
          options={refs.resource}
          value={value.resource_ids}
          onChange={(resource_ids) => onChange({ ...value, resource_ids })}
          disabled={readOnly}
          placeholder="Any resource"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="scope-demands">Demands</Label>
        <MultiPicker
          id="scope-demands"
          label="Demands"
          options={refs.series}
          value={value.series_ids}
          onChange={(series_ids) => onChange({ ...value, series_ids })}
          disabled={readOnly}
          placeholder="Any demand"
        />
      </div>
    </fieldset>
  );
}
