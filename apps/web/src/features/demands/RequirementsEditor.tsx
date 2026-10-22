import { Trash2 } from "lucide-react";
import { Controller, useFieldArray, useFormContext } from "react-hook-form";

import type {
  RequirementDefaults,
  ResourceResponse,
  ResourceTypeResponse,
} from "@/api/generated/model";
import { FieldError } from "@/components/FieldError";
import { MultiPicker } from "@/components/MultiPicker";
import { PredicateList } from "@/components/PredicateList";
import { TagInput } from "@/components/TagInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { NativeSelect } from "@/components/NativeSelect";

import { emptyRequirement, type DemandDraft } from "./demandBody";

export function RequirementsEditor({
  types,
  resources,
  defaults,
}: {
  types: ResourceTypeResponse[];
  resources: ResourceResponse[];
  defaults: RequirementDefaults | null;
}) {
  const form = useFormContext<DemandDraft>();
  const rows = useFieldArray({ control: form.control, name: "requirements" });
  const errors = form.formState.errors.requirements;

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="text-sm font-medium">Requirements</legend>
      <p className="text-xs text-muted-foreground">
        What each activity needs, e.g. one lecturer and one room.
      </p>
      {rows.fields.map((field, i) => {
        const n = i + 1;
        const typeId = form.watch(`requirements.${i}.resource_type_id`);
        const hard = form.watch(`requirements.${i}.hard`);
        const candidates = resources
          .filter((r) => !typeId || r.resource_type_id === typeId)
          .map((r) => ({ value: r.id, label: `${r.name} (${r.code})` }));
        return (
          <div
            key={field.id}
            className="flex flex-col gap-3 rounded-lg border p-3"
          >
            <div className="grid gap-3 sm:grid-cols-[1fr_1fr_5.5rem_5.5rem_auto] sm:items-end">
              <div className="flex flex-col gap-1">
                <Label htmlFor={`req-${i}-role`}>
                  <span className="sr-only">{`Requirement ${n} `}</span>
                  <span className="inline-block first-letter:uppercase">
                    role
                  </span>
                </Label>
                <Input
                  id={`req-${i}-role`}
                  placeholder="e.g. lecturer"
                  {...form.register(`requirements.${i}.role`)}
                />
                <FieldError message={errors?.[i]?.role?.message} />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor={`req-${i}-type`}>
                  <span className="sr-only">{`Requirement ${n} `}</span>
                  <span className="inline-block first-letter:uppercase">
                    resource type
                  </span>
                </Label>
                <NativeSelect
                  id={`req-${i}-type`}
                  {...form.register(`requirements.${i}.resource_type_id`, {
                    setValueAs: (v: string) => (v === "" ? null : v),
                  })}
                >
                  <option value="">Any type</option>
                  {types.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor={`req-${i}-min`}>
                  <span className="sr-only">{`Requirement ${n} `}</span>
                  <span className="inline-block first-letter:uppercase">
                    min
                  </span>
                </Label>
                <Input
                  id={`req-${i}-min`}
                  type="number"
                  min={0}
                  {...form.register(`requirements.${i}.count_min`, {
                    valueAsNumber: true,
                  })}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor={`req-${i}-max`}>
                  <span className="sr-only">{`Requirement ${n} `}</span>
                  <span className="inline-block first-letter:uppercase">
                    max
                  </span>
                </Label>
                <Input
                  id={`req-${i}-max`}
                  type="number"
                  min={1}
                  {...form.register(`requirements.${i}.count_max`, {
                    valueAsNumber: true,
                  })}
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Remove requirement ${n}`}
                onClick={() => rows.remove(i)}
              >
                <Trash2 className="size-4" aria-hidden />
              </Button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1">
                <Label htmlFor={`req-${i}-tags`}>
                  <span className="sr-only">{`Requirement ${n} `}</span>
                  <span className="inline-block first-letter:uppercase">
                    tags
                  </span>
                </Label>
                <Controller
                  control={form.control}
                  name={`requirements.${i}.tags`}
                  render={({ field: tags }) => (
                    <TagInput
                      id={`req-${i}-tags`}
                      value={tags.value}
                      onChange={tags.onChange}
                    />
                  )}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor={`req-${i}-fixed`}>
                  <span className="sr-only">{`Requirement ${n} `}</span>
                  <span className="inline-block first-letter:uppercase">
                    fixed resources
                  </span>
                </Label>
                <Controller
                  control={form.control}
                  name={`requirements.${i}.fixed_resource_ids`}
                  render={({ field: fixed }) => (
                    <MultiPicker
                      id={`req-${i}-fixed`}
                      label={`Requirement ${n} fixed resources`}
                      options={candidates}
                      value={fixed.value}
                      onChange={fixed.onChange}
                      placeholder="None — the solver chooses"
                    />
                  )}
                />
              </div>
            </div>
            <Controller
              control={form.control}
              name={`requirements.${i}.attrs`}
              render={({ field: attrs }) => (
                <PredicateList
                  idPrefix={`req-${i}-attr`}
                  value={attrs.value}
                  onChange={attrs.onChange}
                />
              )}
            />
            <div className="flex flex-wrap items-center gap-4">
              <Controller
                control={form.control}
                name={`requirements.${i}.hard`}
                render={({ field: h }) => (
                  <div className="flex items-center gap-2">
                    <Switch
                      id={`req-${i}-hard`}
                      checked={h.value}
                      onCheckedChange={h.onChange}
                    />
                    <Label htmlFor={`req-${i}-hard`}>
                      <span className="sr-only">{`Requirement ${n} `}</span>
                      <span className="inline-block first-letter:uppercase">
                        must be met
                      </span>
                    </Label>
                  </div>
                )}
              />
              {!hard && (
                <div className="flex items-center gap-2">
                  <Label htmlFor={`req-${i}-weight`}>
                    <span className="sr-only">{`Requirement ${n} `}</span>
                    <span className="inline-block first-letter:uppercase">
                      weight
                    </span>
                  </Label>
                  <Input
                    id={`req-${i}-weight`}
                    type="number"
                    min={1}
                    className="w-24"
                    {...form.register(`requirements.${i}.weight`, {
                      valueAsNumber: true,
                    })}
                  />
                </div>
              )}
            </div>
          </div>
        );
      })}
      <FieldError message={errors?.message ?? errors?.root?.message} />
      <Button
        type="button"
        variant="outline"
        className="self-start"
        onClick={() => rows.append(emptyRequirement(defaults))}
      >
        Add requirement
      </Button>
    </fieldset>
  );
}
