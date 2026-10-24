import { Trash2 } from "lucide-react";
import {
  Controller,
  get,
  useFieldArray,
  useFormContext,
} from "react-hook-form";

import { FieldError } from "@/components/FieldError";
import {
  MultiPicker,
  SinglePicker,
  type PickerOption,
} from "@/components/MultiPicker";
import { PredicateList } from "@/components/PredicateList";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { PredicateValue } from "@/lib/predicates";
import { NativeSelect } from "@/components/NativeSelect";

import { initialValues, type FieldNode, type RefKind } from "./schema";

type Refs = Record<RefKind, PickerOption[]>;

const idOf = (name: string) => name.replace(/\./g, "-");
const optionLabel = (v: string) =>
  (v.charAt(0).toUpperCase() + v.slice(1)).replace(/_/g, " ");
const singular = (title: string) => title.replace(/s$/, "").toLowerCase();

function Hint({ id, text }: { id: string; text: string | undefined }) {
  if (!text) return null;
  return (
    <p id={`${id}-hint`} className="text-xs text-muted-foreground">
      {text}
    </p>
  );
}

function useError(name: string): string | undefined {
  const { formState } = useFormContext();
  const error = get(formState.errors, name) as { message?: string } | undefined;
  return error?.message;
}

function Field({
  node,
  name,
  refs,
  readOnly,
}: {
  node: FieldNode;
  name: string;
  refs: Refs;
  readOnly: boolean;
}) {
  const form = useFormContext();
  const error = useError(name);
  const id = idOf(name);
  const describedBy =
    "description" in node && node.description ? `${id}-hint` : undefined;

  switch (node.kind) {
    case "enum":
      return (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={id}>{node.title}</Label>
          <NativeSelect
            id={id}
            disabled={readOnly}
            aria-describedby={describedBy}
            {...form.register(name)}
          >
            {!(node.required && node.options.length === 1) && (
              <option value="">Choose…</option>
            )}
            {node.options.map((o) => (
              <option key={o} value={o}>
                {optionLabel(o)}
              </option>
            ))}
          </NativeSelect>
          <Hint id={id} text={node.description} />
          <FieldError message={error} />
        </div>
      );
    case "integer":
    case "text":
      return (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={id}>{node.title}</Label>
          <div className="flex items-center gap-2">
            <Input
              id={id}
              inputMode={node.kind === "integer" ? "numeric" : undefined}
              disabled={readOnly}
              aria-invalid={!!error}
              aria-describedby={describedBy}
              {...form.register(name)}
            />
            {node.kind === "integer" && node.unit === "minutes" && (
              <span className="text-sm text-muted-foreground">min</span>
            )}
          </div>
          <Hint id={id} text={node.description} />
          <FieldError message={error} />
        </div>
      );
    case "ref":
      return (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={id}>{node.title}</Label>
          <Controller
            control={form.control}
            name={name}
            render={({ field }) => (
              <SinglePicker
                id={id}
                label={node.title}
                options={refs[node.ref]}
                value={(field.value as string | null) ?? null}
                onChange={field.onChange}
                allowClear={!node.required}
              />
            )}
          />
          <Hint id={id} text={node.description} />
          <FieldError message={error} />
        </div>
      );
    case "refList":
      return (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={id}>{node.title}</Label>
          <Controller
            control={form.control}
            name={name}
            render={({ field }) => (
              <MultiPicker
                id={id}
                label={node.title}
                options={refs[node.ref]}
                value={field.value as string[]}
                onChange={field.onChange}
                disabled={readOnly}
              />
            )}
          />
          <Hint id={id} text={node.description} />
          <FieldError message={error} />
        </div>
      );
    case "refGroups":
      return (
        <RefGroups node={node} name={name} refs={refs} readOnly={readOnly} />
      );
    case "predicates":
      return (
        <fieldset className="flex flex-col gap-1.5">
          <legend className="text-sm font-medium">{node.title}</legend>
          <Controller
            control={form.control}
            name={name}
            render={({ field }) => (
              <PredicateList
                idPrefix={id}
                value={field.value as PredicateValue[]}
                onChange={field.onChange}
                disabled={readOnly}
              />
            )}
          />
          <FieldError message={error} />
        </fieldset>
      );
    case "object":
      return (
        <ObjectField node={node} name={name} refs={refs} readOnly={readOnly} />
      );
    case "objectList":
      return (
        <ObjectList node={node} name={name} refs={refs} readOnly={readOnly} />
      );
    case "unsupported":
      return (
        <p
          role="alert"
          className="text-sm text-destructive"
        >{`This setting (${node.title}) can't be edited here yet.`}</p>
      );
  }
}

function RefGroups({
  node,
  name,
  refs,
  readOnly,
}: {
  node: Extract<FieldNode, { kind: "refGroups" }>;
  name: string;
  refs: Refs;
  readOnly: boolean;
}) {
  const form = useFormContext();
  const error = useError(name);
  return (
    <Controller
      control={form.control}
      name={name}
      render={({ field }) => {
        const groups = field.value as string[][];
        return (
          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-medium">{node.title}</legend>
            {groups.map((group, g) => (
              <div key={g} className="flex items-start gap-2">
                <div className="flex-1">
                  <MultiPicker
                    id={`${idOf(name)}-${g}`}
                    label={`${node.title} — group ${g + 1}`}
                    options={refs[node.ref]}
                    value={group}
                    disabled={readOnly}
                    onChange={(next) =>
                      field.onChange(groups.map((x, i) => (i === g ? next : x)))
                    }
                  />
                </div>
                {!readOnly && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Remove group ${g + 1}`}
                    onClick={() =>
                      field.onChange(groups.filter((_, i) => i !== g))
                    }
                  >
                    <Trash2 className="size-4" aria-hidden />
                  </Button>
                )}
              </div>
            ))}
            {!readOnly && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="self-start"
                onClick={() => field.onChange([...groups, []])}
              >
                Add group
              </Button>
            )}
            <FieldError message={error} />
          </fieldset>
        );
      }}
    />
  );
}

function ObjectField({
  node,
  name,
  refs,
  readOnly,
}: {
  node: Extract<FieldNode, { kind: "object" }>;
  name: string;
  refs: Refs;
  readOnly: boolean;
}) {
  const form = useFormContext();
  const value: unknown = form.watch(name);
  const id = idOf(name);
  const on = value !== null && value !== undefined;
  return (
    <fieldset className="flex flex-col gap-3 rounded-lg border p-3">
      <legend className="px-1 text-sm font-medium">{node.title}</legend>
      {node.nullable && (
        <div className="flex items-center gap-2">
          <Switch
            id={`${id}-on`}
            checked={on}
            disabled={readOnly}
            onCheckedChange={(checked) =>
              form.setValue(name, checked ? initialValues(node.fields) : null)
            }
          />
          <Label htmlFor={`${id}-on`}>Limit to specific activities</Label>
        </div>
      )}
      {on &&
        node.fields.map((f) => (
          <Field
            key={f.name}
            node={f}
            name={`${name}.${f.name}`}
            refs={refs}
            readOnly={readOnly}
          />
        ))}
    </fieldset>
  );
}

function ObjectList({
  node,
  name,
  refs,
  readOnly,
}: {
  node: Extract<FieldNode, { kind: "objectList" }>;
  name: string;
  refs: Refs;
  readOnly: boolean;
}) {
  const form = useFormContext();
  const rows = useFieldArray({ control: form.control, name });
  const error = useError(name);
  const one = singular(node.title);
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-medium">{node.title}</legend>
      {rows.fields.map((row, i) => (
        <div
          key={row.id}
          className="flex items-end gap-2 rounded-lg border p-3"
        >
          <div className="grid flex-1 gap-3 sm:grid-cols-2">
            {node.fields.map((f) => (
              <Field
                key={f.name}
                node={f}
                name={`${name}.${i}.${f.name}`}
                refs={refs}
                readOnly={readOnly}
              />
            ))}
          </div>
          {!readOnly && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Remove ${one} ${i + 1}`}
              disabled={rows.fields.length <= node.minItems}
              onClick={() => rows.remove(i)}
            >
              <Trash2 className="size-4" aria-hidden />
            </Button>
          )}
        </div>
      ))}
      {!readOnly && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start"
          onClick={() => rows.append(initialValues(node.fields))}
        >
          {`Add ${one}`}
        </Button>
      )}
      <FieldError message={error} />
    </fieldset>
  );
}

/** Renders a template's params inside a react-hook-form whose values hold them under `params`. */
export function SchemaForm({
  nodes,
  refs,
  readOnly = false,
}: {
  nodes: FieldNode[];
  refs: Refs;
  readOnly?: boolean;
}) {
  if (nodes.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        This rule has no settings.
      </p>
    );
  return (
    <div className="flex flex-col gap-4">
      {nodes.map((n) => (
        <Field
          key={n.name}
          node={n}
          name={`params.${n.name}`}
          refs={refs}
          readOnly={readOnly}
        />
      ))}
    </div>
  );
}
