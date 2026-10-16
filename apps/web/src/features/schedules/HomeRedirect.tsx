import { Navigate } from "react-router";

import { useListSchedules } from "@/api/generated/schedules/schedules";
import { useAuth } from "@/lib/auth/AuthProvider";
import { LAST_SCHEDULE_KEY, landingPath } from "@/lib/landing";
import { readStored } from "@/lib/storage";

export function HomeRedirect() {
  const { me } = useAuth();
  const { data, isPending } = useListSchedules();
  if (isPending || !me)
    return (
      <div role="status" className="p-8 text-muted-foreground">
        Loading…
      </div>
    );
  return (
    <Navigate
      replace
      to={landingPath({
        roles: me.roles,
        scheduleIds: (data ?? []).map((s) => s.id),
        lastScheduleId: readStored(LAST_SCHEDULE_KEY),
      })}
    />
  );
}
