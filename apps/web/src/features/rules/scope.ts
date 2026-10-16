import type { ScopeWrite } from "@/api/generated/model";
import { formatPredicateValue } from "@/lib/predicates";

export type ScopeValue = Required<ScopeWrite>;

export const emptyScope = (): ScopeValue => ({
  resource_type_ids: [],
  tags: [],
  attrs: [],
  resource_ids: [],
  series_ids: [],
});

const OPS: Record<string, string> = {
  eq: "is",
  ne: "is not",
  in: "is one of",
  gte: "is at least",
  lte: "is at most",
  contains: "contains",
};
const plural = (n: number, one: string, many: string) =>
  `${String(n)} ${n === 1 ? one : many}`;

export function describeScope(
  scope: ScopeValue,
  names: {
    type(id: string): string;
    resource(id: string): string;
    demand(id: string): string;
  },
): string {
  const parts = [
    ...scope.resource_type_ids.map((id) => names.type(id)),
    ...scope.tags.map((t) => `tagged ${t}`),
    ...scope.attrs.map(
      (a) => `${a.attr} ${OPS[a.op] ?? a.op} ${formatPredicateValue(a.value)}`,
    ),
    ...(scope.resource_ids.length === 1
      ? [names.resource(scope.resource_ids[0] ?? "")]
      : scope.resource_ids.length > 1
        ? [
            plural(
              scope.resource_ids.length,
              "specific resource",
              "specific resources",
            ),
          ]
        : []),
    ...(scope.series_ids.length === 1
      ? [names.demand(scope.series_ids[0] ?? "")]
      : scope.series_ids.length > 1
        ? [plural(scope.series_ids.length, "demand", "demands")]
        : []),
  ];
  return parts.length ? parts.join(" · ") : "Everything";
}
