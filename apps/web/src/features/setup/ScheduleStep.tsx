import { useQueryClient } from "@tanstack/react-query";

import { createScheduleFromTemplate } from "@/api/generated/industry-templates/industry-templates";
import {
  createSchedule,
  getListSchedulesQueryKey,
} from "@/api/generated/schedules/schedules";
import { ScheduleForm } from "@/features/schedules/ScheduleForm";
import { LAST_SCHEDULE_KEY } from "@/lib/landing";
import { writeStored } from "@/lib/storage";
import { browserTimezone } from "@/lib/time";

export function ScheduleStep({
  templateKey,
  onCreated,
}: {
  templateKey: string;
  onCreated: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const blank = templateKey === "blank";
  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Create your schedule
        </h1>
        <p className="text-muted-foreground">
          The period you are planning and the timezone it runs in.
        </p>
      </div>
      <ScheduleForm
        submitLabel="Create schedule"
        showDayParts={blank}
        defaultValues={{
          name: "",
          timezone: browserTimezone(),
          start_date: "",
          end_date: "",
          day_parts: [],
        }}
        onSubmit={async (body) => {
          const id = blank
            ? (await createSchedule(body)).id
            : (
                await createScheduleFromTemplate({
                  template_key: templateKey,
                  name: body.name,
                  timezone: body.timezone,
                  start_date: body.start_date,
                  end_date: body.end_date,
                })
              ).schedule.id;
          writeStored(LAST_SCHEDULE_KEY, id);
          await queryClient.invalidateQueries({
            queryKey: getListSchedulesQueryKey(),
          });
          onCreated(id);
        }}
      />
    </section>
  );
}
