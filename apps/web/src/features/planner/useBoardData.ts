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
    types: types.data ?? [],
    resources: resources.data ?? [],
    activities: activities.data ?? [],
    slots: (slotTemplates.data ?? []).flatMap((t) => t.definition.slots),
    pinned: new Set((pins.data ?? []).map((p) => p.activity_id)),
  };
}
