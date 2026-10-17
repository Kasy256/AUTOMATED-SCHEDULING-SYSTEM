import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  Controller,
  FormProvider,
  useForm,
  type FieldPath,
} from "react-hook-form";
import { toast } from "sonner";

import {
  createDemand,
  getListActivitiesQueryKey,
  getListDemandsQueryKey,
  replaceDemand,
} from "@/api/generated/activities/activities";
import type { DemandResponse } from "@/api/generated/model";
import {
  useListResources,
  useListResourceTypes,
} from "@/api/generated/resources/resources";
import { useListSlotTemplates } from "@/api/generated/schedules/schedules";
import { FieldError } from "@/components/FieldError";
import { MultiPicker } from "@/components/MultiPicker";
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
import { isApiError } from "@/lib/problem";
import { NativeSelect } from "@/components/NativeSelect";

import {
  emptyRequirement,
  fromDemand,
  toDemandWrite,
  type DemandDraft,
} from "./demandBody";
import { RequirementsEditor } from "./RequirementsEditor";

const blank = (slotTemplateId: string): DemandDraft => ({
  name: "",
  slot_template_id: slotTemplateId,
  kind: "session",
  sessions_per_week: "1",
  duration_minutes: "",
  slot_labels: [],
  requirements: [emptyRequirement()],
  attrs: {},
});

function clientErrors(d: DemandDraft): [FieldPath<DemandDraft>, string][] {
  const errors: [FieldPath<DemandDraft>, string][] = [];
  if (!d.name.trim()) errors.push(["name", "Enter a name"]);
  if (!d.slot_template_id)
    errors.push(["slot_template_id", "Choose a slot template"]);
  if (d.kind === "session" && !/^\d+$/.test(d.sessions_per_week.trim()))
    errors.push(["sessions_per_week", "Enter a whole number"]);
  if (d.duration_minutes.trim() && !/^\d+$/.test(d.duration_minutes.trim()))
    errors.push(["duration_minutes", "Enter minutes"]);
  d.requirements.forEach((r, i) => {
    if (!/^[a-z][a-z0-9_]{0,62}$/.test(r.role))
      errors.push([
        `requirements.${i}.role`,
        "Lowercase letters, digits and _; start with a letter",
      ]);
  });
  return errors;
}

export function DemandDialog({
  scheduleId,
  editing,
  open,
  onOpenChange,
}: {
  scheduleId: string;
  editing: DemandResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const { data: slotTemplates = [] } = useListSlotTemplates(scheduleId);
  const { data: types = [] } = useListResourceTypes();
  const { data: resources = [] } = useListResources();
  const [message, setMessage] = useState<string | null>(null);
  const form = useForm<DemandDraft>({
    defaultValues: editing ? fromDemand(editing) : blank(""),
  });
  const { errors, isSubmitting } = form.formState;
  const kind = form.watch("kind");
  const slotTemplateId = form.watch("slot_template_id");
  const labels = (
    slotTemplates.find((t) => t.id === slotTemplateId)?.definition.slots ?? []
  ).map((s) => ({
    value: s.label,
    label: s.label,
  }));

  // A new demand defaults to the first slot template once the list has loaded.
  useEffect(() => {
    if (!editing && !form.getValues("slot_template_id") && slotTemplates[0])
      form.setValue("slot_template_id", slotTemplates[0].id);
  }, [editing, form, slotTemplates]);

  const onSubmit = form.handleSubmit(async (values) => {
    setMessage(null);
    const problems = clientErrors(values);
    problems.forEach(([name, msg]) => form.setError(name, { message: msg }));
    if (problems.length) return;
    try {
      const body = toDemandWrite(values);
      const saved = editing
        ? await replaceDemand(scheduleId, editing.id, body)
        : await createDemand(scheduleId, body);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: getListDemandsQueryKey(scheduleId),
        }),
        queryClient.invalidateQueries({
          queryKey: getListActivitiesQueryKey(scheduleId),
        }),
      ]);
      const removed = saved.pins_removed ?? 0;
      if (removed > 0)
        toast.warning(
          `${removed} pinned item(s) no longer fit and were unpinned`,
        );
      else toast.success("Demand saved");
      onOpenChange(false);
    } catch (error) {
      if (!isApiError(error)) {
        setMessage(
          "Could not reach the server. Check your connection and try again.",
        );
        return;
      }
      // API locations look like spec.requirements.0.role; the form has no spec. prefix.
      const unmapped: string[] = [];
      for (const issue of error.fieldErrors) {
        const name = issue.path.join(".").replace(/^spec\./, "");
        if (
          name === "name" ||
          name.startsWith("requirements.") ||
          name in values
        )
          form.setError(name as FieldPath<DemandDraft>, {
            message: issue.message,
          });
        else unmapped.push(issue.message);
      }
      setMessage(
        unmapped.length || error.fieldErrors.length === 0
          ? unmapped.join(" ") || (error.detail ?? error.title)
          : null,
      );
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {editing ? `Edit ${editing.name}` : "New demand"}
          </DialogTitle>
        </DialogHeader>
        <FormProvider {...form}>
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
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="dem-name">Name</Label>
                <Input
                  id="dem-name"
                  aria-invalid={!!errors.name}
                  {...form.register("name")}
                />
                <FieldError message={errors.name?.message} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="dem-slots">Slot template</Label>
                <NativeSelect
                  id="dem-slots"
                  {...form.register("slot_template_id")}
                >
                  {slotTemplates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </NativeSelect>
                <FieldError message={errors.slot_template_id?.message} />
              </div>
            </div>
            <fieldset className="flex flex-wrap gap-4">
              <legend className="mb-1 text-sm font-medium">Kind</legend>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  value="session"
                  {...form.register("kind")}
                />{" "}
                Weekly sessions
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  value="coverage"
                  {...form.register("kind")}
                />{" "}
                Cover every slot
              </label>
            </fieldset>
            {kind === "session" && (
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="dem-sessions">Sessions per week</Label>
                  <Input
                    id="dem-sessions"
                    inputMode="numeric"
                    {...form.register("sessions_per_week")}
                  />
                  <FieldError message={errors.sessions_per_week?.message} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="dem-duration">Duration (minutes)</Label>
                  <Input
                    id="dem-duration"
                    inputMode="numeric"
                    aria-describedby="dem-duration-hint"
                    {...form.register("duration_minutes")}
                  />
                  <p
                    id="dem-duration-hint"
                    className="text-xs text-muted-foreground"
                  >
                    Leave empty to use the slot's length.
                  </p>
                  <FieldError message={errors.duration_minutes?.message} />
                </div>
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dem-labels">Slots</Label>
              <Controller
                control={form.control}
                name="slot_labels"
                render={({ field }) => (
                  <MultiPicker
                    id="dem-labels"
                    label="Slots"
                    options={labels}
                    value={field.value}
                    onChange={field.onChange}
                    placeholder="Any slot of the template"
                  />
                )}
              />
            </div>
            <RequirementsEditor types={types} resources={resources} />
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                Save demand
              </Button>
            </DialogFooter>
          </form>
        </FormProvider>
      </DialogContent>
    </Dialog>
  );
}
