import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";

import {
  createResourceType,
  getListResourceTypesQueryKey,
  updateResourceType,
} from "@/api/generated/resources/resources";
import type { ResourceTypeResponse } from "@/api/generated/model";
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
import { NativeSelect } from "@/components/NativeSelect";

const KEY = /^[a-z][a-z0-9_]{0,62}$/;
const attribute = z.object({
  key: z
    .string()
    .regex(KEY, "Lowercase letters, digits and _; start with a letter"),
  label: z.string().max(200),
  type: z.enum(["string", "integer", "number", "boolean", "enum", "tags"]),
  required: z.boolean(),
  enum_values: z.string(),
});
const schema = z.object({
  name: z.string().trim().min(1, "Enter a name").max(200),
  key: z
    .string()
    .regex(KEY, "Lowercase letters, digits and _; start with a letter"),
  kind: z.enum(["person", "space", "asset", "group"]),
  attributes: z.array(attribute).max(100),
});
type Values = z.infer<typeof schema>;

const toKey = (name: string) =>
  name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^[^a-z]+|_+$/g, "")
    .slice(0, 63);

function toBody(values: Values) {
  return {
    version: 1 as const,
    attributes: values.attributes.map((a) => ({
      key: a.key,
      label: a.label.trim() || null,
      type: a.type,
      required: a.required,
      enum_values:
        a.type === "enum"
          ? a.enum_values
              .split(",")
              .map((v) => v.trim())
              .filter(Boolean)
          : null,
    })),
  };
}

export function ResourceTypeDialog({
  open,
  onOpenChange,
  editing,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editing: ResourceTypeResponse | null;
}) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const [keyTouched, setKeyTouched] = useState(editing !== null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    values: editing
      ? {
          name: editing.name,
          key: editing.key,
          kind: editing.kind,
          attributes: (editing.attribute_schema.attributes ?? []).map((a) => ({
            key: a.key,
            label: a.label ?? "",
            type: a.type,
            required: a.required ?? false,
            enum_values: (a.enum_values ?? []).join(", "),
          })),
        }
      : { name: "", key: "", kind: "person", attributes: [] },
  });
  const attributes = useFieldArray({
    control: form.control,
    name: "attributes",
  });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (values) => {
    setMessage(null);
    try {
      if (editing)
        await updateResourceType(editing.id, {
          name: values.name,
          attribute_schema: toBody(values),
        });
      else
        await createResourceType({
          key: values.key,
          name: values.name,
          kind: values.kind,
          attribute_schema: toBody(values),
        });
      await queryClient.invalidateQueries({
        queryKey: getListResourceTypesQueryKey(),
      });
      onOpenChange(false);
    } catch (error) {
      setMessage(applyApiError(error, form.setError, ["name", "key", "kind"]));
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {editing ? `Edit ${editing.name}` : "New resource type"}
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
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rt-name">Name</Label>
              <Input
                id="rt-name"
                {...form.register("name", {
                  onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
                    if (!keyTouched)
                      form.setValue("key", toKey(e.target.value));
                  },
                })}
              />
              <FieldError message={errors.name?.message} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rt-key">Key</Label>
              <Input
                id="rt-key"
                readOnly={editing !== null}
                {...form.register("key", {
                  onChange: () => {
                    setKeyTouched(true);
                  },
                })}
              />
              <FieldError message={errors.key?.message} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rt-kind">Kind</Label>
              <NativeSelect
                id="rt-kind"
                disabled={editing !== null}
                {...form.register("kind")}
              >
                <option value="person">Person</option>
                <option value="space">Space</option>
                <option value="asset">Asset</option>
                <option value="group">Group</option>
              </NativeSelect>
            </div>
          </div>
          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-medium">Attributes</legend>
            {attributes.fields.map((field, i) => (
              <div
                key={field.id}
                className="grid grid-cols-[1fr_1fr_8rem_auto_auto] items-end gap-2"
              >
                <div className="flex flex-col gap-1">
                  <Label
                    htmlFor={`attr-${String(i)}-key`}
                  >{`Attribute ${String(i + 1)} key`}</Label>
                  <Input
                    id={`attr-${String(i)}-key`}
                    {...form.register(`attributes.${i}.key`)}
                  />
                  <FieldError message={errors.attributes?.[i]?.key?.message} />
                </div>
                <div className="flex flex-col gap-1">
                  <Label htmlFor={`attr-${String(i)}-label`}>Label</Label>
                  <Input
                    id={`attr-${String(i)}-label`}
                    {...form.register(`attributes.${i}.label`)}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label htmlFor={`attr-${String(i)}-type`}>Type</Label>
                  <NativeSelect
                    id={`attr-${String(i)}-type`}
                    {...form.register(`attributes.${i}.type`)}
                  >
                    {[
                      "string",
                      "integer",
                      "number",
                      "boolean",
                      "enum",
                      "tags",
                    ].map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </NativeSelect>
                </div>
                <label className="flex items-center gap-1.5 pb-2 text-sm">
                  <input
                    type="checkbox"
                    {...form.register(`attributes.${i}.required`)}
                  />{" "}
                  Required
                </label>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove attribute ${String(i + 1)}`}
                  onClick={() => {
                    attributes.remove(i);
                  }}
                >
                  <Trash2 className="size-4" aria-hidden />
                </Button>
                {form.watch(`attributes.${i}.type`) === "enum" && (
                  <div className="col-span-full flex flex-col gap-1">
                    <Label htmlFor={`attr-${String(i)}-enum`}>
                      Allowed values (comma separated)
                    </Label>
                    <Input
                      id={`attr-${String(i)}-enum`}
                      {...form.register(`attributes.${i}.enum_values`)}
                    />
                  </div>
                )}
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              className="self-start"
              onClick={() => {
                attributes.append({
                  key: "",
                  label: "",
                  type: "string",
                  required: false,
                  enum_values: "",
                });
              }}
            >
              Add attribute
            </Button>
          </fieldset>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                onOpenChange(false);
              }}
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
