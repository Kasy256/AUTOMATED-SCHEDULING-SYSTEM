import type {
  ImportResponse,
  IndustryTemplateDefinition,
  ResourceTypeResponse,
} from "@/api/generated/model";
import type { ImportTarget } from "@/features/imports/ImportFlow";

export function wizardStep(params: URLSearchParams): 1 | 2 | 3 | 4 {
  if (!params.get("template")) return 1;
  if (!params.get("schedule")) return 2;
  if (params.get("template") === "blank" || params.get("step") === "finish")
    return 4;
  return 3;
}

export function importRows(
  template: IndustryTemplateDefinition,
  types: ResourceTypeResponse[],
  imports: ImportResponse[],
  scheduleId: string,
) {
  const committed = imports.filter((i) => i.status === "committed");
  const resourceRows = template.resource_types.map((tt) => {
    const type = types.find((t) => t.key === tt.key) ?? null;
    return {
      key: tt.key,
      label: tt.name,
      target: type ? { kind: "resources" as const, resourceType: type } : null,
      done:
        committed.find(
          (i) => i.kind === "resources" && i.resource_type_id === type?.id,
        ) ?? null,
      blockedBy: [] as string[],
    };
  });
  const demandsRow = {
    key: "demands",
    label: "Demands",
    target: null as ImportTarget | null, // the step builds the preset target (needs slot template ids)
    done:
      committed.find(
        (i) => i.kind === "demands" && i.schedule_id === scheduleId,
      ) ?? null,
    blockedBy: resourceRows.filter((r) => r.done === null).map((r) => r.label),
  };
  return [...resourceRows, demandsRow];
}
