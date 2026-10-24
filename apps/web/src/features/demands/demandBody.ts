import type {
  DemandResponse,
  DemandWrite,
  RequirementDefaults,
  RequirementSpec,
} from "@/api/generated/model";
import type { PredicateValue } from "@/lib/predicates";

export interface RequirementDraft {
  role: string;
  resource_type_id: string | null;
  tags: string[];
  attrs: PredicateValue[];
  count_min: number;
  count_max: number;
  fixed_resource_ids: string[];
  hard: boolean;
  weight: number;
}

export interface DemandDraft {
  name: string;
  slot_template_id: string;
  kind: "session" | "coverage";
  sessions_per_week: string;
  duration_minutes: string;
  slot_labels: string[];
  requirements: RequirementDraft[];
  // Set by imports (e.g. headcount); passed through untouched on edit.
  attrs: Record<string, unknown>;
}

const toRequirement = (r: RequirementDraft): RequirementSpec => ({ ...r });

export function toDemandWrite(d: DemandDraft): DemandWrite {
  const common = {
    slot_labels: d.slot_labels.length ? d.slot_labels : null,
    requirements: d.requirements.map(toRequirement),
    attrs: d.attrs,
  };
  const spec =
    d.kind === "session"
      ? {
          kind: "session" as const,
          sessions_per_week: Number(d.sessions_per_week),
          duration_minutes: d.duration_minutes.trim()
            ? Number(d.duration_minutes)
            : null,
          ...common,
        }
      : { kind: "coverage" as const, ...common };
  return { name: d.name, slot_template_id: d.slot_template_id, spec };
}

export function fromDemand(d: DemandResponse): DemandDraft {
  const spec = d.spec;
  return {
    name: d.name,
    slot_template_id: d.slot_template_id,
    kind: spec.kind,
    sessions_per_week:
      spec.kind === "session" ? String(spec.sessions_per_week) : "",
    duration_minutes:
      spec.kind === "session" && spec.duration_minutes != null
        ? String(spec.duration_minutes)
        : "",
    slot_labels: spec.slot_labels ?? [],
    requirements: spec.requirements.map((r) => ({
      role: r.role,
      resource_type_id: r.resource_type_id ?? null,
      tags: r.tags ?? [],
      attrs: r.attrs ?? [],
      count_min: r.count_min ?? 1,
      count_max: r.count_max ?? 1,
      fixed_resource_ids: r.fixed_resource_ids ?? [],
      hard: r.hard ?? true,
      weight: r.weight ?? 0,
    })),
    attrs: spec.attrs ?? {},
  };
}

export const emptyRequirement = (
  defaults?: RequirementDefaults | null,
): RequirementDraft => ({
  role: "",
  resource_type_id: null,
  tags: [],
  attrs: [],
  count_min: 1,
  count_max: 1,
  fixed_resource_ids: [],
  hard: defaults?.hard ?? true,
  weight: defaults?.weight ?? 0,
});
