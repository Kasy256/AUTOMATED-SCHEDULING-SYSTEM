import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import type { AttributeDef, ResourceResponse } from "@/api/generated/model";
import {
  deleteResource,
  getGetResourceQueryKey,
  getListResourcesQueryKey,
  updateResource,
} from "@/api/generated/resources/resources";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { FieldError } from "@/components/FieldError";
import { TagInput } from "@/components/TagInput";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { describeFailure } from "@/lib/conflict";
import { isApiError } from "@/lib/problem";
import { SELECT_CLASS } from "@/lib/styles";

import { fromFormValues, toFormValues, type FormValue } from "./attributes";

const countOrNull = (text: string): number | null | "invalid" => {
  if (!text.trim()) return null;
  return /^\d+$/.test(text.trim()) && Number(text) > 0
    ? Number(text)
    : "invalid";
};

function AttributeField({
  def,
  value,
  error,
  disabled,
  onChange,
}: {
  def: AttributeDef;
  value: FormValue | undefined;
  error: string | undefined;
  disabled: boolean;
  onChange: (value: FormValue) => void;
}) {
  const id = `attr-${def.key}`;
  const label = def.label ?? def.key;
  if (def.type === "boolean")
    return (
      <div className="flex items-center gap-2">
        <Switch
          id={id}
          checked={value === true}
          disabled={disabled}
          onCheckedChange={onChange}
        />
        <Label htmlFor={id}>{label}</Label>
      </div>
    );
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {def.type === "tags" ? (
        <TagInput
          id={id}
          value={Array.isArray(value) ? value : []}
          onChange={onChange}
        />
      ) : def.type === "enum" ? (
        <select
          id={id}
          className={SELECT_CLASS}
          disabled={disabled}
          value={typeof value === "string" ? value : ""}
          onChange={(e) => {
            onChange(e.target.value);
          }}
        >
          <option value="">—</option>
          {(def.enum_values ?? []).map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      ) : (
        <Input
          id={id}
          inputMode={
            def.type === "integer" || def.type === "number"
              ? "decimal"
              : undefined
          }
          disabled={disabled}
          aria-invalid={!!error}
          value={typeof value === "string" ? value : ""}
          onChange={(e) => {
            onChange(e.target.value);
          }}
        />
      )}
      <FieldError message={error} />
    </div>
  );
}

export function AttributeForm({
  defs,
  kind,
  resource,
  canEdit,
}: {
  defs: AttributeDef[];
  kind: string;
  resource: ResourceResponse;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [name, setName] = useState(resource.name);
  const [code, setCode] = useState(resource.code);
  const [tags, setTags] = useState(resource.tags);
  const [count, setCount] = useState(
    String(resource.capacity ?? resource.size ?? ""),
  );
  const [values, setValues] = useState(() =>
    toFormValues(defs, resource.attributes),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const countLabel =
    kind === "group"
      ? "Size"
      : kind === "space" || kind === "asset"
        ? "Capacity"
        : null;

  async function save() {
    setMessage(null);
    const result = fromFormValues(defs, values);
    const parsedCount = countLabel ? countOrNull(count) : null;
    const next = { ...result.errors };
    if (!name.trim()) next.name = "Enter a name";
    if (!code.trim()) next.code = "Enter a code";
    if (parsedCount === "invalid")
      next.count = "Enter a whole number of at least 1";
    setErrors(next);
    if (Object.keys(next).length || parsedCount === "invalid") return;
    setSaving(true);
    try {
      await updateResource(resource.id, {
        name: name.trim(),
        code: code.trim(),
        tags,
        attributes: result.attributes,
        capacity: countLabel === "Capacity" ? parsedCount : null,
        size: countLabel === "Size" ? parsedCount : null,
      });
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: getGetResourceQueryKey(resource.id),
        }),
        queryClient.invalidateQueries({ queryKey: getListResourcesQueryKey() }),
      ]);
      toast.success("Saved");
    } catch (error) {
      // API locations look like ["attributes", "<key>"].
      if (
        isApiError(error) &&
        error.fieldErrors.some((f) => f.path[0] === "attributes")
      ) {
        setErrors(
          Object.fromEntries(
            error.fieldErrors
              .filter((f) => f.path[0] === "attributes")
              .map((f) => [String(f.path[1]), f.message]),
          ),
        );
      } else {
        setMessage(describeFailure(error, resource.name));
      }
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    try {
      await deleteResource(resource.id);
      await queryClient.invalidateQueries({
        queryKey: getListResourcesQueryKey(),
      });
      toast.success(`${resource.name} deleted`);
      void navigate("/resources");
    } catch (error) {
      setMessage(describeFailure(error, resource.name));
    } finally {
      setConfirmDelete(false);
    }
  }

  return (
    <form
      className="flex max-w-3xl flex-col gap-5 pt-2"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      {message && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}
      <fieldset
        disabled={!canEdit || saving}
        className="grid gap-4 rounded-lg border bg-card p-4 sm:grid-cols-2"
      >
        <legend className="px-1 text-sm font-medium">Resource</legend>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="res-name">Name</Label>
          <Input
            id="res-name"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
            }}
          />
          <FieldError message={errors.name} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="res-code">Code</Label>
          <Input
            id="res-code"
            value={code}
            onChange={(e) => {
              setCode(e.target.value);
            }}
          />
          <FieldError message={errors.code} />
        </div>
        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <Label htmlFor="res-tags">Tags</Label>
          <TagInput id="res-tags" value={tags} onChange={setTags} />
        </div>
        {countLabel && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="res-count">{countLabel}</Label>
            <Input
              id="res-count"
              inputMode="numeric"
              value={count}
              onChange={(e) => {
                setCount(e.target.value);
              }}
            />
            <FieldError message={errors.count} />
          </div>
        )}
      </fieldset>
      {defs.length > 0 && (
        <fieldset
          disabled={!canEdit || saving}
          className="grid gap-4 rounded-lg border bg-card p-4 sm:grid-cols-2"
        >
          <legend className="px-1 text-sm font-medium">Attributes</legend>
          {defs.map((def) => (
            <AttributeField
              key={def.key}
              def={def}
              value={values[def.key]}
              error={errors[def.key]}
              disabled={!canEdit || saving}
              onChange={(value) => {
                setValues((v) => ({ ...v, [def.key]: value }));
              }}
            />
          ))}
        </fieldset>
      )}
      {canEdit && (
        <div className="flex justify-between gap-2">
          <Button type="submit" disabled={saving}>
            Save changes
          </Button>
          <Button
            type="button"
            variant="outline"
            className="text-destructive"
            onClick={() => {
              setConfirmDelete(true);
            }}
          >
            Delete resource
          </Button>
        </div>
      )}
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete ${resource.name}?`}
        description="Resources used by demands, pins or rules cannot be deleted."
        confirmLabel="Delete"
        destructive
        onConfirm={() => void remove()}
      />
    </form>
  );
}
