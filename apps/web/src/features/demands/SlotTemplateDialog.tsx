import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";

import { getListDemandsQueryKey } from "@/api/generated/activities/activities";
import type { SlotTemplateResponse } from "@/api/generated/model";
import {
  createSlotTemplate,
  getListSlotTemplatesQueryKey,
  replaceSlotTemplate,
} from "@/api/generated/schedules/schedules";
import { FieldError } from "@/components/FieldError";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { applyApiError } from "@/lib/forms";
import { WEEKDAYS, formatMinuteOfDay, parseTimeOfDay } from "@/lib/time";

const slot = z.object({
  label: z.string().trim().min(1, "Enter a label").max(50),
  weekdays: z.array(z.number()).min(1, "Pick at least one day"),
  start: z.string().refine((t) => parseTimeOfDay(t) !== null, "Enter a time"),
  duration: z
    .string()
    .refine(
      (t) => /^\d+$/.test(t.trim()) && Number(t) >= 1 && Number(t) <= 1440,
      "Enter minutes (1–1440)",
    ),
});

const schema = z
  .object({
    name: z.string().trim().min(1, "Enter a name").max(200),
    slots: z.array(slot).min(1, "Add at least one slot"),
  })
  .superRefine((v, ctx) => {
    const seen = new Set<string>();
    v.slots.forEach((s, i) => {
      if (seen.has(s.label.trim()))
        ctx.addIssue({
          code: "custom",
          path: ["slots", i, "label"],
          message: "Labels must be unique",
        });
      seen.add(s.label.trim());
    });
  });
type Values = z.infer<typeof schema>;

function toValues(editing: SlotTemplateResponse | null): Values {
  if (!editing) return { name: "", slots: [] };
  return {
    name: editing.name,
    slots: editing.definition.slots.map((s) => ({
      label: s.label,
      weekdays: s.weekdays,
      start: formatMinuteOfDay(s.start_minute),
      duration: String(s.duration_minutes),
    })),
  };
}

export function SlotTemplateDialog({
  scheduleId,
  editing,
  open,
  onOpenChange,
}: {
  scheduleId: string;
  editing: SlotTemplateResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: toValues(editing),
  });
  const slots = useFieldArray({ control: form.control, name: "slots" });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (values) => {
    setMessage(null);
    const body = {
      name: values.name,
      definition: {
        version: 1 as const,
        slots: values.slots.map((s) => ({
          label: s.label.trim(),
          weekdays: [...s.weekdays].sort((a, b) => a - b),
          start_minute: parseTimeOfDay(s.start) ?? 0,
          duration_minutes: Number(s.duration),
        })),
      },
    };
    try {
      if (editing) await replaceSlotTemplate(scheduleId, editing.id, body);
      else await createSlotTemplate(scheduleId, body);
      // Activities regenerate when slots change, so demand counts move too.
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: getListSlotTemplatesQueryKey(scheduleId),
        }),
        queryClient.invalidateQueries({
          queryKey: getListDemandsQueryKey(scheduleId),
        }),
      ]);
      onOpenChange(false);
    } catch (error) {
      setMessage(applyApiError(error, form.setError, ["name"]));
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {editing ? `Edit ${editing.name}` : "New slot template"}
          </DialogTitle>
        </DialogHeader>
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => void onSubmit(e)}
          noValidate
        >
          {message && (
            <Alert variant="destructive" role="alert">
              <AlertDescription>{message}</AlertDescription>
            </Alert>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="st-name">Name</Label>
            <Input
              id="st-name"
              aria-invalid={!!errors.name}
              {...form.register("name")}
            />
            <FieldError message={errors.name?.message} />
          </div>
          {slots.fields.map((field, i) => (
            <fieldset
              key={field.id}
              className="flex flex-col gap-3 rounded-lg border p-3"
            >
              <legend className="px-1 text-sm font-medium">{`Slot ${i + 1}`}</legend>
              <div className="grid gap-3 sm:grid-cols-[1fr_8rem_10rem_auto] sm:items-end">
                <div className="flex flex-col gap-1">
                  <Label
                    htmlFor={`slot-${i}-label`}
                  >{`Slot ${i + 1} label`}</Label>
                  <Input
                    id={`slot-${i}-label`}
                    {...form.register(`slots.${i}.label`)}
                  />
                  <FieldError message={errors.slots?.[i]?.label?.message} />
                </div>
                <div className="flex flex-col gap-1">
                  <Label
                    htmlFor={`slot-${i}-start`}
                  >{`Slot ${i + 1} start`}</Label>
                  <Input
                    id={`slot-${i}-start`}
                    type="time"
                    {...form.register(`slots.${i}.start`)}
                  />
                  <FieldError message={errors.slots?.[i]?.start?.message} />
                </div>
                <div className="flex flex-col gap-1">
                  <Label
                    htmlFor={`slot-${i}-duration`}
                  >{`Slot ${i + 1} duration (minutes)`}</Label>
                  <Input
                    id={`slot-${i}-duration`}
                    inputMode="numeric"
                    {...form.register(`slots.${i}.duration`)}
                  />
                  <FieldError message={errors.slots?.[i]?.duration?.message} />
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove slot ${i + 1}`}
                  onClick={() => slots.remove(i)}
                >
                  <Trash2 className="size-4" aria-hidden />
                </Button>
              </div>
              <Controller
                control={form.control}
                name={`slots.${i}.weekdays`}
                render={({ field: days }) => (
                  <fieldset className="flex flex-wrap gap-3">
                    <legend className="sr-only">{`Slot ${i + 1} days`}</legend>
                    {WEEKDAYS.map((day, d) => (
                      <label
                        key={day}
                        className="flex items-center gap-1.5 text-sm"
                      >
                        <input
                          type="checkbox"
                          checked={days.value.includes(d)}
                          onChange={(e) =>
                            days.onChange(
                              e.target.checked
                                ? [...days.value, d]
                                : days.value.filter((x) => x !== d),
                            )
                          }
                        />
                        {day}
                      </label>
                    ))}
                  </fieldset>
                )}
              />
              <FieldError message={errors.slots?.[i]?.weekdays?.message} />
            </fieldset>
          ))}
          <FieldError
            message={errors.slots?.message ?? errors.slots?.root?.message}
          />
          <Button
            type="button"
            variant="outline"
            className="self-start"
            onClick={() =>
              slots.append({ label: "", weekdays: [], start: "", duration: "" })
            }
          >
            Add slot
          </Button>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
