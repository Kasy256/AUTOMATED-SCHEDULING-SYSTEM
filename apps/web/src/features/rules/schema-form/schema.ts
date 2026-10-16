export interface JsonSchema {
  type?: string;
  title?: string;
  description?: string;
  enum?: readonly string[];
  const?: string;
  default?: unknown;
  minimum?: number;
  exclusiveMinimum?: number;
  minItems?: number;
  items?: JsonSchema;
  properties?: Record<string, JsonSchema>;
  required?: readonly string[];
  anyOf?: readonly JsonSchema[];
  $ref?: string;
  $defs?: Record<string, JsonSchema>;
  "x-ref"?: string;
  "x-unit"?: string;
}
export type RefKind = "series" | "resource" | "window";
export type FieldNode =
  | {
      kind: "enum";
      name: string;
      title: string;
      description?: string;
      required: boolean;
      nullable: boolean;
      options: string[];
      default?: string;
    }
  | {
      kind: "integer";
      name: string;
      title: string;
      description?: string;
      required: boolean;
      nullable: boolean;
      unit?: "minutes";
      min?: number;
      default?: number;
    }
  | {
      kind: "text";
      name: string;
      title: string;
      description?: string;
      required: boolean;
      nullable: boolean;
      default?: string;
    }
  | {
      kind: "ref";
      name: string;
      title: string;
      description?: string;
      required: boolean;
      nullable: boolean;
      ref: RefKind;
    }
  | {
      kind: "refList";
      name: string;
      title: string;
      description?: string;
      required: boolean;
      ref: RefKind;
    }
  | {
      kind: "refGroups";
      name: string;
      title: string;
      description?: string;
      required: boolean;
      ref: RefKind;
    }
  | {
      kind: "predicates";
      name: string;
      title: string;
      description?: string;
      required: boolean;
    }
  | {
      kind: "object";
      name: string;
      title: string;
      description?: string;
      required: boolean;
      nullable: boolean;
      fields: FieldNode[];
    }
  | {
      kind: "objectList";
      name: string;
      title: string;
      description?: string;
      required: boolean;
      minItems: number;
      fields: FieldNode[];
    }
  | { kind: "unsupported"; name: string; title: string; reason: string };
export type FormParams = Record<string, unknown>;

const isRef = (v: unknown): v is RefKind =>
  v === "series" || v === "resource" || v === "window";

function resolve(
  schema: JsonSchema,
  defs: Record<string, JsonSchema>,
): JsonSchema {
  return schema.$ref
    ? (defs[schema.$ref.split("/").pop() ?? ""] ?? {})
    : schema;
}

function node(
  name: string,
  raw: JsonSchema,
  required: boolean,
  defs: Record<string, JsonSchema>,
): FieldNode {
  // Pydantic puts title/description/x-unit on the property; the type may sit in anyOf [T, null].
  const options = raw.anyOf ?? [];
  const nullable = options.some((o) => o.type === "null");
  const inner = resolve(options.find((o) => o.type !== "null") ?? raw, defs);
  const base = {
    name,
    title: raw.title ?? inner.title ?? name,
    description: raw.description ?? inner.description,
    required,
  };
  const unit =
    (raw["x-unit"] ?? inner["x-unit"]) === "minutes"
      ? ("minutes" as const)
      : undefined;
  if (inner.enum)
    return {
      ...base,
      kind: "enum",
      nullable,
      options: [...inner.enum],
      default: typeof raw.default === "string" ? raw.default : undefined,
    };
  if (inner.type === "integer")
    return {
      ...base,
      kind: "integer",
      nullable,
      unit,
      min:
        inner.minimum ??
        (inner.exclusiveMinimum !== undefined
          ? inner.exclusiveMinimum + 1
          : undefined),
      default: typeof raw.default === "number" ? raw.default : undefined,
    };
  if (inner.type === "string") {
    const ref = inner["x-ref"];
    return isRef(ref)
      ? { ...base, kind: "ref", nullable, ref }
      : {
          ...base,
          kind: "text",
          nullable,
          default: typeof raw.default === "string" ? raw.default : undefined,
        };
  }
  if (inner.type === "array" && inner.items) {
    const item = resolve(inner.items, defs);
    if (isRef(item["x-ref"]))
      return { ...base, kind: "refList", ref: item["x-ref"] };
    if (item.type === "array" && item.items && isRef(item.items["x-ref"]))
      return { ...base, kind: "refGroups", ref: item.items["x-ref"] };
    if (item.title === "AttributePredicate")
      return { ...base, kind: "predicates" };
    if (item.type === "object" && item.properties)
      return {
        ...base,
        kind: "objectList",
        minItems: inner.minItems ?? 0,
        fields: fields(item, defs),
      };
  }
  if (inner.type === "object" && inner.properties)
    return { ...base, kind: "object", nullable, fields: fields(inner, defs) };
  return {
    name,
    title: base.title,
    kind: "unsupported",
    reason: JSON.stringify(inner).slice(0, 120),
  };
}

function fields(
  schema: JsonSchema,
  defs: Record<string, JsonSchema>,
): FieldNode[] {
  const required = new Set(schema.required ?? []);
  return Object.entries(schema.properties ?? {}).map(([name, raw]) =>
    node(name, raw, required.has(name), defs),
  );
}

export function parseSchema(schema: JsonSchema): FieldNode[] {
  return fields(schema, schema.$defs ?? {});
}

export function initialValues(
  nodes: FieldNode[],
  params: Record<string, unknown> = {},
): FormParams {
  return Object.fromEntries(
    nodes.map((n) => [n.name, initialValue(n, params[n.name])]),
  );
}

function initialValue(n: FieldNode, stored: unknown): unknown {
  switch (n.kind) {
    case "enum":
      return typeof stored === "string"
        ? stored
        : (n.default ??
            (n.required && n.options.length === 1 ? n.options[0] : ""));
    case "integer":
      return typeof stored === "number"
        ? String(stored)
        : n.default !== undefined
          ? String(n.default)
          : "";
    case "text":
      return typeof stored === "string" ? stored : (n.default ?? "");
    case "ref":
      return typeof stored === "string" ? stored : null;
    case "refList":
      return Array.isArray(stored) ? stored : [];
    case "refGroups":
      return Array.isArray(stored) ? stored : n.required ? [[]] : [];
    case "predicates":
      return Array.isArray(stored) ? stored : [];
    case "object":
      return stored && typeof stored === "object"
        ? initialValues(n.fields, stored as Record<string, unknown>)
        : n.nullable
          ? null
          : initialValues(n.fields);
    case "objectList":
      return Array.isArray(stored)
        ? stored.map((item) =>
            initialValues(n.fields, item as Record<string, unknown>),
          )
        : Array.from({ length: n.minItems }, () => initialValues(n.fields));
    case "unsupported":
      return stored;
  }
}

interface Issue {
  path: string;
  message: string;
}

function convert(
  n: FieldNode,
  value: unknown,
  path: string,
  errors: Issue[],
): { present: boolean; value?: unknown } {
  const missing = () => {
    if ("required" in n && n.required)
      errors.push({ path, message: "Required" });
    return { present: false };
  };
  switch (n.kind) {
    case "enum":
    case "text":
      return typeof value === "string" && value !== ""
        ? { present: true, value }
        : missing();
    case "integer": {
      const text = typeof value === "string" ? value.trim() : "";
      if (!text) return missing();
      if (!/^-?\d+$/.test(text)) {
        errors.push({ path, message: "Enter a whole number" });
        return { present: false };
      }
      return { present: true, value: Number(text) };
    }
    case "ref":
      return typeof value === "string" ? { present: true, value } : missing();
    case "refList":
    case "predicates":
      return { present: true, value: Array.isArray(value) ? value : [] };
    case "refGroups":
      return { present: true, value: Array.isArray(value) ? value : [] };
    case "object": {
      if (value === null) return missing();
      const out = convertAll(n.fields, value as FormParams, `${path}.`, errors);
      return { present: true, value: out };
    }
    case "objectList": {
      const items = Array.isArray(value) ? value : [];
      return {
        present: true,
        value: items.map((item, i) =>
          convertAll(
            n.fields,
            item as FormParams,
            `${path}.${String(i)}.`,
            errors,
          ),
        ),
      };
    }
    case "unsupported":
      return value === undefined
        ? { present: false }
        : { present: true, value };
  }
}

function convertAll(
  nodes: FieldNode[],
  values: FormParams,
  prefix: string,
  errors: Issue[],
): Record<string, unknown> {
  const params: Record<string, unknown> = {};
  for (const n of nodes) {
    const result = convert(n, values[n.name], `${prefix}${n.name}`, errors);
    if (result.present) params[n.name] = result.value;
  }
  return params;
}

export function toParams(
  nodes: FieldNode[],
  values: FormParams,
): { params: Record<string, unknown>; errors: Issue[] } {
  const errors: Issue[] = [];
  return { params: convertAll(nodes, values, "", errors), errors };
}
