import type { Role } from "@/api/generated/model";

import { can } from "./permissions";

export const LAST_SCHEDULE_KEY = "cartlyf.lastSchedule";

export function landingPath(input: {
  roles: Role[];
  scheduleIds: string[];
  lastScheduleId: string | null;
}): string {
  const { roles, scheduleIds, lastScheduleId } = input;
  if (scheduleIds.length === 0)
    return can(roles, "config.manage") ? "/setup" : "/resources";
  const id =
    lastScheduleId && scheduleIds.includes(lastScheduleId)
      ? lastScheduleId
      : scheduleIds[0];
  return `/schedules/${String(id)}/overview`;
}
