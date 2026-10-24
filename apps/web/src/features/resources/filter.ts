import type { ResourceResponse } from "@/api/generated/model";

export function filterResources(
  resources: ResourceResponse[],
  { typeId, query }: { typeId: string; query: string },
): ResourceResponse[] {
  const q = query.trim().toLowerCase();
  return resources.filter(
    (r) =>
      (typeId === "all" || r.resource_type_id === typeId) &&
      (!q ||
        r.code.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        r.tags.some((t) => t.toLowerCase().includes(q))),
  );
}
