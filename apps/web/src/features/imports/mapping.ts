import type {
  DemandMapping,
  ResourceMapping,
  ResourceTypeResponse,
  TemplateDemandShape,
} from "@/api/generated/model";

const find = (columns: string[], name: string) =>
  columns.find((c) => c.toLowerCase() === name.toLowerCase()) ?? null;

export function autoResourceMapping(
  columns: string[],
  type: ResourceTypeResponse,
): ResourceMapping {
  const first = columns[0] ?? "";
  const attributes: Record<string, string> = {};
  for (const def of type.attribute_schema.attributes ?? []) {
    const column = find(columns, def.key);
    if (column) attributes[def.key] = column;
  }
  return {
    kind: "resources",
    code: find(columns, "code") ?? first,
    name: find(columns, "name") ?? first,
    tags: find(columns, "tags"),
    capacity: find(columns, "capacity"),
    size: find(columns, "size"),
    concurrency: find(columns, "concurrency"),
    attributes,
  };
}

export function demandMappingFromTemplate(
  shape: TemplateDemandShape,
  ids: { slotTemplateId: string; typeIdByKey: Record<string, string> },
  term: string | null,
): DemandMapping {
  return {
    kind: "demands",
    demand_kind: shape.kind,
    slot_template_id: ids.slotTemplateId,
    name: shape.name_column,
    sessions_per_week: shape.sessions_per_week_column ?? null,
    weekly_minutes: shape.weekly_minutes_column ?? null,
    requirements: shape.requirements.map((r) => ({
      role: r.role,
      resource_type_id: ids.typeIdByKey[r.resource_type_key] ?? null,
      count_min: r.count_min ?? 1,
      count_max: r.count_max ?? 1,
      count_from_fixed: r.count_from_fixed ?? false,
      fixed_codes_column: r.fixed_codes_column ?? null,
      tags_column: r.tags_column ?? null,
      attribute_columns: r.attribute_columns ?? {},
    })),
    term_split: shape.term_split && term ? { ...shape.term_split, term } : null,
  };
}
