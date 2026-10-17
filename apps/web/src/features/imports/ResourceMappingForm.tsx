import { useState } from "react";

import type {
  ResourceMapping,
  ResourceTypeResponse,
} from "@/api/generated/model";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/NativeSelect";

import { autoResourceMapping } from "./mapping";

const NONE = "";

function ColumnSelect({
  id,
  label,
  columns,
  value,
  required = false,
  onChange,
}: {
  id: string;
  label: string;
  columns: string[];
  value: string | null | undefined;
  required?: boolean;
  onChange: (column: string | null) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <NativeSelect
        id={id}
        value={value ?? NONE}
        aria-required={required}
        onChange={(e) =>
          onChange(e.target.value === NONE ? null : e.target.value)
        }
      >
        {!required && <option value={NONE}>— not in this file —</option>}
        {columns.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </NativeSelect>
    </div>
  );
}

export function ResourceMappingForm({
  type,
  columns,
  busy,
  onSubmit,
}: {
  type: ResourceTypeResponse;
  columns: string[];
  busy: boolean;
  onSubmit: (mapping: ResourceMapping) => void;
}) {
  const [mapping, setMapping] = useState(() =>
    autoResourceMapping(columns, type),
  );
  const set = (patch: Partial<ResourceMapping>) =>
    setMapping((m) => ({ ...m, ...patch }));
  const attributes: Record<string, string> = Object.fromEntries(
    Object.entries(mapping.attributes ?? {}).filter(
      (e): e is [string, string] => typeof e[1] === "string",
    ),
  );

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(mapping);
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <ColumnSelect
          id="map-code"
          label="Code"
          columns={columns}
          value={mapping.code}
          required
          onChange={(c) => set({ code: c ?? "" })}
        />
        <ColumnSelect
          id="map-name"
          label="Name"
          columns={columns}
          value={mapping.name}
          required
          onChange={(c) => set({ name: c ?? "" })}
        />
        <ColumnSelect
          id="map-tags"
          label="Tags"
          columns={columns}
          value={mapping.tags}
          onChange={(c) => set({ tags: c })}
        />
        {(type.kind === "space" || type.kind === "asset") && (
          <ColumnSelect
            id="map-capacity"
            label="Capacity"
            columns={columns}
            value={mapping.capacity}
            onChange={(c) => set({ capacity: c })}
          />
        )}
        {type.kind === "group" && (
          <ColumnSelect
            id="map-size"
            label="Size"
            columns={columns}
            value={mapping.size}
            onChange={(c) => set({ size: c })}
          />
        )}
        <ColumnSelect
          id="map-concurrency"
          label="Concurrency"
          columns={columns}
          value={mapping.concurrency}
          onChange={(c) => set({ concurrency: c })}
        />
        {(type.attribute_schema.attributes ?? []).map((def) => (
          <ColumnSelect
            key={def.key}
            id={`map-attr-${def.key}`}
            label={def.label ?? def.key}
            columns={columns}
            value={attributes[def.key]}
            onChange={(c) => {
              const rest = Object.fromEntries(
                Object.entries(attributes).filter(([k]) => k !== def.key),
              );
              set({ attributes: c ? { ...rest, [def.key]: c } : rest });
            }}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Tags may hold several values separated by semicolons.
      </p>
      <Button type="submit" className="self-start" disabled={busy}>
        Run dry run
      </Button>
    </form>
  );
}
