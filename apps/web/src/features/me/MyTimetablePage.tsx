import { useState } from "react";

import type { MyAssignment } from "@/api/generated/model";
import { useListResources } from "@/api/generated/resources/resources";
import { useMyAssignments } from "@/api/generated/versions/versions";
import { PageHeader } from "@/components/PageHeader";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Button } from "@/components/ui/button";
import { CalendarLinks } from "@/features/calendar/CalendarLinks";
import { formatMinuteOfDay, zonedParts } from "@/lib/time";

import { groupByDay, type Day } from "./days";

const clock = (iso: string, tz: string) =>
  formatMinuteOfDay(zonedParts(iso, tz).minute);

function DayList({
  days,
  codeOf,
}: {
  days: Day[];
  codeOf: (id: string) => string | undefined;
}) {
  return (
    <>
      {days.map((day) => (
        <section key={day.date} className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-muted-foreground">
            {day.label}
          </h2>
          <ul className="flex flex-col divide-y rounded-xl border bg-card shadow-sm">
            {day.items.map((item) => (
              <Row key={item.activity_id} item={item} codeOf={codeOf} />
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}

function Row({
  item,
  codeOf,
}: {
  item: MyAssignment;
  codeOf: (id: string) => string | undefined;
}) {
  const others = Object.entries(item.resources)
    .filter(([role]) => !item.roles.includes(role))
    .flatMap(([, ids]) => ids)
    .map(codeOf)
    .filter((c): c is string => c !== undefined);
  return (
    <li className="flex flex-col gap-0.5 px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <span className="text-sm tabular-nums">
          {`${clock(item.start_at, item.schedule_timezone)}–${clock(item.end_at, item.schedule_timezone)}`}
        </span>
        <span className="font-medium">{item.activity_name ?? "Activity"}</span>
      </div>
      <span className="text-xs text-muted-foreground">
        {[...others, item.schedule_name].join(" · ")}
      </span>
    </li>
  );
}

export function MyTimetablePage() {
  const { data: items = [], isPending } = useMyAssignments();
  // Members can't list resources; then codes are simply left out.
  const { data: resources = [] } = useListResources({
    query: { retry: false },
  });
  const [showPast, setShowPast] = useState(false);
  const codes = new Map(resources.map((r) => [r.id, r.code]));
  const { upcoming, past } = groupByDay(items, new Date());

  return (
    <>
      <PageHeader title="My timetable" />
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-6">
        {isPending ? (
          <TableSkeleton label="Loading your timetable" />
        ) : items.length === 0 ? (
          <p className="rounded-xl border bg-card p-5 text-sm text-muted-foreground shadow-sm">
            Nothing scheduled for you yet.
          </p>
        ) : (
          <>
            <DayList days={upcoming} codeOf={(id) => codes.get(id)} />
            {past.length > 0 && (
              <Button
                variant="ghost"
                className="self-start"
                onClick={() => setShowPast((s) => !s)}
              >
                {showPast ? "Hide past" : "Show past"}
              </Button>
            )}
            {showPast && <DayList days={past} codeOf={(id) => codes.get(id)} />}
          </>
        )}
        <CalendarLinks />
      </div>
    </>
  );
}
