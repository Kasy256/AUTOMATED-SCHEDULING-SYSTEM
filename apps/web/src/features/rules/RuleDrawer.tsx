import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Controller, FormProvider, useForm } from "react-hook-form";
import { toast } from "sonner";

import { getListDemandsQueryKey } from "@/api/generated/activities/activities";
import {
  createConstraint,
  deleteConstraint,
  getListConstraintsQueryKey,
  replaceConstraint,
} from "@/api/generated/constraints/constraints";
import type {
  ConstraintResponse,
  ConstraintWrite,
  TemplateResponse,
} from "@/api/generated/model";
import {
  getListResourcesQueryKey,
  getListResourceTypesQueryKey,
} from "@/api/generated/resources/resources";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { FieldError } from "@/components/FieldError";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { describeFailure } from "@/lib/conflict";
import { applyApiError } from "@/lib/forms";
import { isApiError } from "@/lib/problem";

import { useRefOptions } from "./schema-form/RefOptions";
import {
  initialValues,
  parseSchema,
  renderedField,
  toParams,
  type FormParams,
  type JsonSchema,
} from "./schema-form/schema";
import { SchemaForm } from "./schema-form/SchemaForm";
import { emptyScope, type ScopeValue } from "./scope";
import { ScopeBuilder } from "./ScopeBuilder";

interface RuleForm {
  name: string;
  hard: boolean;
  weight: string;
  params: FormParams;
  scope: ScopeValue;
}

export function RuleDrawer({
  scheduleId,
  template,
  rule,
  open,
  onOpenChange,
  readOnly = false,
}: {
  scheduleId: string;
  template: TemplateResponse;
  rule: ConstraintResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  readOnly?: boolean;
}) {
  const queryClient = useQueryClient();
  const refs = useRefOptions(scheduleId);
  const [message, setMessage] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const nodes = useMemo(
    () => parseSchema(template.params_schema as JsonSchema),
    [template],
  );
  const form = useForm<RuleForm>({
    defaultValues: {
      name: rule?.name ?? template.title,
      hard: rule ? rule.hard : !template.soft_only,
      weight: String(rule && !rule.hard ? rule.weight : 10),
      params: initialValues(nodes, rule?.params),
      scope: rule ? { ...emptyScope(), ...rule.scope } : emptyScope(),
    },
  });
  const { errors, isSubmitting } = form.formState;
  const hard = form.watch("hard");
  const refresh = () =>
    queryClient.invalidateQueries({
      queryKey: getListConstraintsQueryKey(scheduleId),
    });

  const onSubmit = form.handleSubmit(async (values) => {
    setMessage(null);
    const { params, errors: paramErrors } = toParams(nodes, values.params);
    paramErrors.forEach((e) =>
      form.setError(`params.${e.path}` as "params", { message: e.message }),
    );
    const weight = Number(values.weight);
    let invalid = paramErrors.length > 0;
    if (!values.name.trim()) {
      form.setError("name", { message: "Enter a name" });
      invalid = true;
    }
    if (!values.hard && !(Number.isInteger(weight) && weight >= 1)) {
      form.setError("weight", {
        message: "A soft rule needs a weight of at least 1",
      });
      invalid = true;
    }
    if (invalid) return;
    const body: ConstraintWrite = {
      name: values.name.trim(),
      template_key: template.key,
      template_version: template.version,
      // toParams only emits JSON values built from the schema.
      params: params as ConstraintWrite["params"],
      scope: values.scope,
      hard: values.hard,
      weight: values.hard ? 0 : weight,
      enabled: rule?.enabled ?? true,
    };
    try {
      if (rule) await replaceConstraint(scheduleId, rule.id, body);
      else await createConstraint(scheduleId, body);
      await refresh();
      toast.success("Rule saved");
      onOpenChange(false);
    } catch (error) {
      if (isApiError(error) && error.status === 404) {
        // A demand, resource or type this rule names was deleted elsewhere; refresh the pickers so
        // the stale chips show as unknown, and say which kind is missing.
        await Promise.all(
          [
            getListDemandsQueryKey(scheduleId),
            getListResourcesQueryKey(),
            getListResourceTypesQueryKey(),
          ].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
        );
        setMessage(
          error.detail === "Unknown constraint instance"
            ? "This rule was deleted elsewhere. Close the drawer to see the current rules."
            : `${error.detail ?? error.title}: something this rule refers to no longer exists — check the pickers.`,
        );
        return;
      }
      const onField = renderedField(nodes);
      setMessage(
        applyApiError(
          error,
          form.setError,
          (n) => ["name", "weight", "hard"].includes(n) || onField(n),
        ),
      );
    }
  });

  async function remove() {
    if (!rule) return;
    try {
      await deleteConstraint(scheduleId, rule.id);
      await refresh();
      toast.success("Rule deleted");
      onOpenChange(false);
    } catch (error) {
      setMessage(describeFailure(error, rule.name));
    } finally {
      setConfirmDelete(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{template.title}</SheetTitle>
          <SheetDescription>{template.description}</SheetDescription>
        </SheetHeader>
        <FormProvider {...form}>
          <form
            className="flex flex-1 flex-col"
            onSubmit={(e) => void onSubmit(e)}
            noValidate
          >
            {message && (
              <Alert
                variant="destructive"
                role="alert"
                className="mx-6 mt-6 w-auto"
              >
                <AlertDescription>{message}</AlertDescription>
              </Alert>
            )}
            <fieldset
              className="flex flex-col gap-6 px-6 py-6"
              disabled={readOnly || isSubmitting}
            >
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="rule-name">Name</Label>
                <Input
                  id="rule-name"
                  aria-invalid={!!errors.name}
                  {...form.register("name")}
                />
                <FieldError message={errors.name?.message} />
              </div>
              <Controller
                control={form.control}
                name="hard"
                render={({ field }) => (
                  <fieldset className="flex flex-col gap-2">
                    <legend className="text-sm font-medium">Strength</legend>
                    <div className="flex flex-wrap gap-4">
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="radio"
                          name="rule-strength"
                          checked={field.value}
                          disabled={template.soft_only}
                          onChange={() => field.onChange(true)}
                        />
                        Hard — must
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="radio"
                          name="rule-strength"
                          checked={!field.value}
                          onChange={() => field.onChange(false)}
                        />
                        Soft — prefer
                      </label>
                    </div>
                    {template.soft_only && (
                      <p className="text-xs text-muted-foreground">
                        This kind of rule can only be soft.
                      </p>
                    )}
                  </fieldset>
                )}
              />
              {!hard && (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="rule-weight">Weight</Label>
                  <Input
                    id="rule-weight"
                    inputMode="numeric"
                    className="w-32"
                    aria-describedby="rule-weight-hint"
                    {...form.register("weight")}
                  />
                  <p
                    id="rule-weight-hint"
                    className="text-xs text-muted-foreground"
                  >
                    Higher weights matter more when soft rules compete.
                  </p>
                  <FieldError message={errors.weight?.message} />
                </div>
              )}
              <section
                aria-labelledby="rule-settings"
                className="flex flex-col gap-3"
              >
                <h3 id="rule-settings" className="text-sm font-semibold">
                  Settings
                </h3>
                <SchemaForm nodes={nodes} refs={refs} readOnly={readOnly} />
              </section>
              <Controller
                control={form.control}
                name="scope"
                render={({ field }) => (
                  <ScopeBuilder
                    scheduleId={scheduleId}
                    value={field.value}
                    onChange={field.onChange}
                    readOnly={readOnly}
                  />
                )}
              />
            </fieldset>
            {!readOnly && (
              <SheetFooter className="flex-row justify-between">
                {rule ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="text-destructive"
                    onClick={() => setConfirmDelete(true)}
                  >
                    Delete
                  </Button>
                ) : (
                  <span />
                )}
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => onOpenChange(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    Save rule
                  </Button>
                </div>
              </SheetFooter>
            )}
          </form>
        </FormProvider>
        <ConfirmDialog
          open={confirmDelete}
          onOpenChange={setConfirmDelete}
          title={`Delete ${rule?.name ?? "this rule"}?`}
          description="The schedule will no longer respect it on the next solve."
          confirmLabel="Delete"
          destructive
          onConfirm={() => void remove()}
        />
      </SheetContent>
    </Sheet>
  );
}
