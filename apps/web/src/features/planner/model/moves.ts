import type { MoveRequest } from "@/api/generated/model";
import { isoInstant } from "@/lib/time";

export function buildMove(
  item: {
    activityId: string;
    start: string;
    resources: Record<string, string[]>;
  },
  fromResourceId: string,
  to: { resourceId: string; start: string },
): MoveRequest | null {
  const start = isoInstant(to.start);
  let resources = item.resources;
  if (to.resourceId !== fromResourceId) {
    const role = Object.keys(item.resources).find((r) =>
      item.resources[r]?.includes(fromResourceId),
    );
    const ids = role ? (item.resources[role] ?? []) : [];
    if (!role || ids.includes(to.resourceId)) return null;
    resources = {
      ...item.resources,
      [role]: ids.map((id) => (id === fromResourceId ? to.resourceId : id)),
    };
  } else if (start === isoInstant(item.start)) {
    return null;
  }
  return { activity_id: item.activityId, start_at: start, resources };
}
