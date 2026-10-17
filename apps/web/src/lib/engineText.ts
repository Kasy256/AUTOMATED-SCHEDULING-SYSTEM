import { useListConstraints } from "@/api/generated/constraints/constraints";

import { useNames } from "./names";

const UUID =
  /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;
const MISSING = "an item that no longer exists";

export function formatEngineText(
  text: string,
  nameOf: (id: string) => string | undefined,
): string {
  return text.replace(UUID, (id) => nameOf(id.toLowerCase()) ?? MISSING);
}

export function useEngineText(scheduleId: string): (text: string) => string {
  const name = useNames(scheduleId);
  const { data: rules = [] } = useListConstraints(scheduleId);
  const ruleNames = new Map(rules.map((r) => [r.id, `“${r.name}”`]));
  return (text) =>
    formatEngineText(text, (id) => {
      const known = ruleNames.get(id) ?? name(id);
      return known === MISSING ? undefined : known;
    });
}
