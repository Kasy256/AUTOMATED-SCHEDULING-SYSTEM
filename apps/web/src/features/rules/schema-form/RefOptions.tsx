import { useListDemands } from "@/api/generated/activities/activities";
import {
  useListResources,
  useListResourceTypes,
} from "@/api/generated/resources/resources";
import { useGetSchedule } from "@/api/generated/schedules/schedules";
import type { PickerOption } from "@/components/MultiPicker";

export function useRefOptions(
  scheduleId: string,
): Record<"series" | "resource" | "window", PickerOption[]> {
  const { data: demands = [] } = useListDemands(scheduleId);
  const { data: resources = [] } = useListResources();
  const { data: types = [] } = useListResourceTypes();
  const { data: schedule } = useGetSchedule(scheduleId);
  const typeName = new Map(types.map((t) => [t.id, t.name]));
  return {
    series: demands.map((d) => ({ value: d.id, label: d.name })),
    resource: resources.map((r) => ({
      value: r.id,
      label: `${r.name} (${r.code})`,
      group: typeName.get(r.resource_type_id),
    })),
    window: (schedule?.day_parts.parts ?? []).map((p) => ({
      value: p.name,
      label: p.name,
    })),
  };
}
