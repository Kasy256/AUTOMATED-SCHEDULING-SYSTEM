import { useMemo } from "react";

import {
  useListActivities,
  useListPins,
} from "@/api/generated/activities/activities";
import type { VersionSummary } from "@/api/generated/model";
import {
  useListResources,
  useListResourceTypes,
} from "@/api/generated/resources/resources";
import {
  useGetSchedule,
  useListSlotTemplates,
} from "@/api/generated/schedules/schedules";
import {
  useGetVersion,
  useListVersions,
} from "@/api/generated/versions/versions";

const NONE: never[] = [];

function pickVersion(
  versions: VersionSummary[],
  param: string | null,
): VersionSummary | undefined {
  if (param) return versions.find((v) => v.id === param);
  const newest = [...versions].sort((a, b) => b.number - a.number);
  return (
    newest.find((v) => v.status === "draft") ??
    newest.find((v) => v.status === "published")
  );
}

export function useBoardData(scheduleId: string, versionParam: string | null) {
  const schedule = useGetSchedule(scheduleId);
  const versions = useListVersions(scheduleId);
  const chosen = pickVersion(versions.data ?? [], versionParam);
  const version = useGetVersion(chosen?.id ?? "", {
    query: { enabled: chosen !== undefined },
  });
  const types = useListResourceTypes();
  const resources = useListResources();
  const activities = useListActivities(scheduleId);
  const slotTemplates = useListSlotTemplates(scheduleId);
  const pins = useListPins(scheduleId);
  // Stable identities, so the board's memoised rows don't re-render on unrelated state.
  const slots = useMemo(
    () => (slotTemplates.data ?? []).flatMap((t) => t.definition.slots),
    [slotTemplates.data],
  );
  const pinned = useMemo(
    () => new Set((pins.data ?? []).map((p) => p.activity_id)),
    [pins.data],
  );
  const newestNumber = Math.max(
    0,
    ...(versions.data ?? []).map((v) => v.number),
  );
  return {
    loading:
      schedule.isPending ||
      versions.isPending ||
      types.isPending ||
      resources.isPending ||
      activities.isPending ||
      (chosen !== undefined && version.isPending),
    schedule: schedule.data,
    versions: versions.data ?? [],
    version: chosen ? (version.data ?? null) : null,
    editable: chosen?.number === newestNumber && chosen.status !== "archived",
    types: types.data ?? NONE,
    resources: resources.data ?? NONE,
    activities: activities.data ?? NONE,
    slots,
    pinned,
  };
}
