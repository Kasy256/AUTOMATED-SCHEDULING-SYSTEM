import { zodResolver } from "@hookform/resolvers/zod";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";

import type { ScheduleCreate } from "@/api/generated/model";
import { FieldError } from "@/components/FieldError";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { applyApiError } from "@/lib/forms";
import { parseTimeOfDay } from "@/lib/time";

const KEY = /^[a-z][a-z0-9_]{0,62}$/;

const schema = z
  .object({
    name: z.string().trim().min(1, "Enter a name").max(200),
    timezone: z.string().trim().min(1, "Choose a timezone"),
    start_date: z.string().min(1, "Choose a start date"),
    end_date: z.string().min(1, "Choose an end date"),
    day_parts: z.array(
      z.object({
        name: z
          .string()
          .regex(KEY, "Lowercase letters, digits and _; start with a letter"),
        start: z.string(),
        end: z.string(),
      }),
    ),
  })
  .superRefine((v, ctx) => {
    // ISO dates compare correctly as strings.
    if (v.start_date && v.end_date && v.end_date < v.start_date)
      ctx.addIssue({
        code: "custom",
        path: ["end_date"],
        message: "End date must be on or after the start date",
      });
    v.day_parts.forEach((p, i) => {
      const start = parseTimeOfDay(p.start);
      const end = parseTimeOfDay(p.end);
      if (start === null)
        ctx.addIssue({
          code: "custom",
          path: ["day_parts", i, "start"],
          message: "Enter a time",
        });
      if (end === null)
        ctx.addIssue({
          code: "custom",
          path: ["day_parts", i, "end"],
          message: "Enter a time",
        });
      if (start !== null && end !== null && end <= start)
        ctx.addIssue({
          code: "custom",
          path: ["day_parts", i, "end"],
          message: "End must be after start",
        });
    });
  });

export type ScheduleValues = z.infer<typeof schema>;

export function ScheduleForm({
  defaultValues,
  submitLabel,
  showDayParts = true,
  onSubmit,
}: {
  defaultValues: ScheduleValues;
  submitLabel: string;
  showDayParts?: boolean;
  onSubmit: (body: ScheduleCreate) => Promise<void>;
}) {
  const [message, setMessage] = useState<string | null>(null);
  const form = useForm<ScheduleValues>({
    resolver: zodResolver(schema),
    defaultValues,
  });
  const parts = useFieldArray({ control: form.control, name: "day_parts" });
  const { errors, isSubmitting } = form.formState;

  const submit = form.handleSubmit(async (values) => {
    setMessage(null);
    try {
      await onSubmit({
        name: values.name,
        timezone: values.timezone,
        start_date: values.start_date,
        end_date: values.end_date,
        day_parts: {
          version: 1,
          parts: values.day_parts.map((p) => ({
            name: p.name,
            start_minute: parseTimeOfDay(p.start) ?? 0,
            end_minute: parseTimeOfDay(p.end) ?? 0,
          })),
        },
      });
    } catch (error) {
      setMessage(
        applyApiError(error, form.setError, [
          "name",
          "timezone",
          "start_date",
          "end_date",
        ]),
      );
    }
  });

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => void submit(e)}
      noValidate
    >
      {message && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="sch-name">Name</Label>
        <Input
          id="sch-name"
          aria-invalid={!!errors.name}
          {...form.register("name")}
        />
        <FieldError message={errors.name?.message} />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="sch-start">Start date</Label>
          <Input
            id="sch-start"
            type="date"
            aria-invalid={!!errors.start_date}
            {...form.register("start_date")}
          />
          <FieldError message={errors.start_date?.message} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="sch-end">End date</Label>
          <Input
            id="sch-end"
            type="date"
            aria-invalid={!!errors.end_date}
            {...form.register("end_date")}
          />
          <FieldError message={errors.end_date?.message} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="sch-tz">Timezone</Label>
          <Input
            id="sch-tz"
            list="sch-timezones"
            aria-invalid={!!errors.timezone}
            {...form.register("timezone")}
          />
          <datalist id="sch-timezones">
            {Intl.supportedValuesOf("timeZone").map((tz) => (
              <option key={tz} value={tz} />
            ))}
          </datalist>
          <FieldError message={errors.timezone?.message} />
        </div>
      </div>
      {showDayParts && (
        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium">Parts of the day</legend>
          <p className="text-xs text-muted-foreground">
            Optional named windows, such as morning and afternoon, that rules
            can refer to.
          </p>
          {parts.fields.map((field, i) => (
            <div
              key={field.id}
              className="grid grid-cols-[1fr_8rem_8rem_auto] items-end gap-2"
            >
              <div className="flex flex-col gap-1">
                <Label htmlFor={`part-${i}-name`}>{`Part ${i + 1} name`}</Label>
                <Input
                  id={`part-${i}-name`}
                  {...form.register(`day_parts.${i}.name`)}
                />
                <FieldError message={errors.day_parts?.[i]?.name?.message} />
              </div>
              <div className="flex flex-col gap-1">
                <Label
                  htmlFor={`part-${i}-start`}
                >{`Part ${i + 1} start`}</Label>
                <Input
                  id={`part-${i}-start`}
                  type="time"
                  {...form.register(`day_parts.${i}.start`)}
                />
                <FieldError message={errors.day_parts?.[i]?.start?.message} />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor={`part-${i}-end`}>{`Part ${i + 1} end`}</Label>
                <Input
                  id={`part-${i}-end`}
                  type="time"
                  {...form.register(`day_parts.${i}.end`)}
                />
                <FieldError message={errors.day_parts?.[i]?.end?.message} />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Remove part ${i + 1}`}
                onClick={() => parts.remove(i)}
              >
                <Trash2 className="size-4" aria-hidden />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            className="self-start"
            onClick={() => parts.append({ name: "", start: "", end: "" })}
          >
            Add part of day
          </Button>
        </fieldset>
      )}
      <Button type="submit" className="self-start" disabled={isSubmitting}>
        {submitLabel}
      </Button>
    </form>
  );
}
