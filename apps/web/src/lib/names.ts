import {
  useListActivities,
  useListDemands,
} from "@/api/generated/activities/activities";
import { useListResources } from "@/api/generated/resources/resources";

export function useNames(scheduleId?: string): (id: string) => string {
  const enabled = scheduleId !== undefined;
  const { data: resources = [] } = useListResources();
  const { data: demands = [] } = useListDemands(scheduleId ?? "", {
    query: { enabled },
  });
  const { data: activities = [] } = useListActivities(scheduleId ?? "", {
    query: { enabled },
  });
  const names = new Map<string, string>([
    ...resources.map((r): [string, string] => [r.id, `${r.name} (${r.code})`]),
    ...demands.map((d): [string, string] => [d.id, d.name]),
    ...activities.map((a): [string, string] => [a.id, a.name]),
  ]);
  return (id) => names.get(id) ?? "an item that no longer exists";
}
