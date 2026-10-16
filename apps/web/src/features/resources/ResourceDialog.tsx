import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useNavigate } from "react-router";
import { z } from "zod";

import type { ResourceTypeResponse } from "@/api/generated/model";
import {
  createResource,
  getListResourcesQueryKey,
} from "@/api/generated/resources/resources";
import { FieldError } from "@/components/FieldError";
import { TagInput } from "@/components/TagInput";
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
import { SELECT_CLASS } from "@/lib/styles";

const optionalCount = z.preprocess(
  (v) => (v === "" || v === undefined ? undefined : Number(v)),
  z
    .number()
    .int("Enter a whole number")
    .positive("Must be at least 1")
    .optional(),
);

const schema = z.object({
  resource_type_id: z.string().min(1, "Choose a type"),
  code: z.string().trim().min(1, "Enter a code").max(100),
  name: z.string().trim().min(1, "Enter a name").max(200),
  tags: z.array(z.string()),
  capacity: optionalCount,
  size: optionalCount,
});
type Values = z.input<typeof schema>;
type Parsed = z.output<typeof schema>;

export function ResourceDialog({
  open,
  onOpenChange,
  types,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  types: ResourceTypeResponse[];
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [message, setMessage] = useState<string | null>(null);
  const form = useForm<Values, unknown, Parsed>({
    resolver: zodResolver(schema),
    defaultValues: {
      resource_type_id: types[0]?.id ?? "",
      code: "",
      name: "",
      tags: [],
    },
  });
  const { errors, isSubmitting } = form.formState;
  const kind = types.find((t) => t.id === form.watch("resource_type_id"))?.kind;

  const onSubmit = form.handleSubmit(async (values) => {
    setMessage(null);
    try {
      const created = await createResource({
        resource_type_id: values.resource_type_id,
        code: values.code,
        name: values.name,
        tags: values.tags,
        attributes: {},
        capacity:
          kind === "space" || kind === "asset"
            ? (values.capacity ?? null)
            : null,
        size: kind === "group" ? (values.size ?? null) : null,
      });
      await queryClient.invalidateQueries({
        queryKey: getListResourcesQueryKey(),
      });
      onOpenChange(false);
      void navigate(`/resources/${created.id}`);
    } catch (error) {
      setMessage(
        applyApiError(error, form.setError, [
          "code",
          "name",
          "capacity",
          "size",
          "resource_type_id",
        ]),
      );
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New resource</DialogTitle>
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
            <Label htmlFor="res-type">Type</Label>
            <select
              id="res-type"
              className={SELECT_CLASS}
              {...form.register("resource_type_id")}
            >
              {types.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <FieldError message={errors.resource_type_id?.message} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="res-code">Code</Label>
              <Input
                id="res-code"
                aria-invalid={!!errors.code}
                {...form.register("code")}
              />
              <FieldError message={errors.code?.message} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="res-name">Name</Label>
              <Input
                id="res-name"
                aria-invalid={!!errors.name}
                {...form.register("name")}
              />
              <FieldError message={errors.name?.message} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="res-tags">Tags</Label>
            <Controller
              control={form.control}
              name="tags"
              render={({ field }) => (
                <TagInput
                  id="res-tags"
                  value={field.value}
                  onChange={field.onChange}
                />
              )}
            />
          </div>
          {(kind === "space" || kind === "asset") && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="res-capacity">Capacity</Label>
              <Input
                id="res-capacity"
                inputMode="numeric"
                {...form.register("capacity")}
              />
              <FieldError message={errors.capacity?.message} />
            </div>
          )}
          {kind === "group" && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="res-size">Size</Label>
              <Input
                id="res-size"
                inputMode="numeric"
                {...form.register("size")}
              />
              <FieldError message={errors.size?.message} />
            </div>
          )}
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
