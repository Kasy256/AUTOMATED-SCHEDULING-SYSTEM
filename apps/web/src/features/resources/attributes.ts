import type { AttributeDef, JsonValue } from "@/api/generated/model";

export type FormValue = string | boolean | string[];

export function toFormValues(
  defs: AttributeDef[],
  attributes: Record<string, JsonValue>,
): Record<string, FormValue> {
  const values: Record<string, FormValue> = {};
  for (const def of defs) {
    const value: unknown = attributes[def.key];
    if (def.type === "boolean") values[def.key] = value === true;
    else if (def.type === "tags")
      values[def.key] = Array.isArray(value) ? value.map((v) => String(v)) : [];
    else
      values[def.key] =
        typeof value === "string" || typeof value === "number"
          ? String(value)
          : "";
  }
  return values;
}

export function fromFormValues(
  defs: AttributeDef[],
  values: Record<string, FormValue>,
): { attributes: Record<string, JsonValue>; errors: Record<string, string> } {
  const attributes: Record<string, JsonValue> = {};
  const errors: Record<string, string> = {};
  for (const def of defs) {
    const raw = values[def.key];
    if (def.type === "boolean") {
      attributes[def.key] = raw === true;
      continue;
    }
    if (def.type === "tags") {
      attributes[def.key] = Array.isArray(raw) ? raw : [];
      continue;
    }
    const text = typeof raw === "string" ? raw.trim() : "";
    if (!text) {
      if (def.required) errors[def.key] = "Required";
      continue;
    }
    if (def.type === "integer") {
      if (/^-?\d+$/.test(text)) attributes[def.key] = Number(text);
      else errors[def.key] = "Enter a whole number";
    } else if (def.type === "number") {
      const n = Number(text);
      if (Number.isFinite(n)) attributes[def.key] = n;
      else errors[def.key] = "Enter a number";
    } else {
      attributes[def.key] = text;
    }
  }
  return { attributes, errors };
}
