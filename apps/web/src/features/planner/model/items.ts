import type { AssignmentEdit, AssignmentOut } from "@/api/generated/model";
import { isoInstant } from "@/lib/time";

export interface BoardItem {
  activityId: string;
  name: string;
  start: string;
  resources: Record<string, string[]>;
  pending: boolean;
  pinned: boolean;
}

export const cellKey = (resourceId: string, start: string) =>
  `${resourceId}|${isoInstant(start)}`;

export function applyPending(
  assignments: AssignmentOut[],
  changes: AssignmentEdit[],
): (AssignmentOut & { pending: boolean })[] {
  const byActivity = new Map(changes.map((c) => [c.activity_id, c]));
  return assignments.map((a) => {
    const change = byActivity.get(a.activity_id);
    return change
      ? {
          ...a,
          start_at: change.start_at,
          resources: change.resources,
          pending: true,
        }
      : { ...a, pending: false };
  });
}

export function cellIndex(
  assignments: (AssignmentOut & { pending: boolean })[],
  rowIds: ReadonlySet<string>,
  pinned: ReadonlySet<string>,
): Map<string, BoardItem[]> {
  const index = new Map<string, BoardItem[]>();
  for (const a of assignments) {
    const item: BoardItem = {
      activityId: a.activity_id,
      name: a.activity_name ?? "Activity",
      start: isoInstant(a.start_at),
      resources: a.resources,
      pending: a.pending,
      pinned: pinned.has(a.activity_id),
    };
    for (const ids of Object.values(a.resources))
      for (const id of ids)
        if (rowIds.has(id)) {
          const key = cellKey(id, a.start_at);
          index.set(key, [...(index.get(key) ?? []), item]);
        }
  }
  return index;
}
