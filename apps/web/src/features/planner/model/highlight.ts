import type { ExplanationOut } from "@/api/generated/model";

import { cellKey } from "./items";

export type CellCheck =
  { state: "valid" } | { state: "invalid"; reasons: string[] };

const same = (a: string[] = [], b: string[] = []) =>
  a.length === b.length && a.every((x, i) => x === b[i]);

export function highlightMap(
  explanation: ExplanationOut,
  current: { resources: Record<string, string[]> },
  draggedResourceId: string,
): Map<string, CellCheck> {
  const role = Object.keys(current.resources).find((r) =>
    current.resources[r]?.includes(draggedResourceId),
  );
  const map = new Map<string, CellCheck>();
  if (!role) return map;
  for (const alt of explanation.alternatives) {
    const others = Object.keys({
      ...current.resources,
      ...alt.resources,
    }).filter((r) => r !== role);
    if (!others.every((r) => same(alt.resources[r], current.resources[r])))
      continue;
    const before = current.resources[role] ?? [];
    const after = alt.resources[role] ?? [];
    const added = after.filter((id) => !before.includes(id));
    const removed = before.filter((id) => !after.includes(id));
    // Only "this row's resource replaced by one other" (or unchanged) is a drop target on this tab.
    if (
      removed.length > 1 ||
      added.length !== removed.length ||
      (removed.length === 1 && removed[0] !== draggedResourceId)
    )
      continue;
    const row = added[0] ?? draggedResourceId;
    map.set(
      cellKey(row, alt.start_at),
      alt.check.valid
        ? { state: "valid" }
        : { state: "invalid", reasons: alt.check.broken.map((b) => b.message) },
    );
  }
  return map;
}
