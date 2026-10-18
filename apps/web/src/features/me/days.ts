import type { MyAssignment } from "@/api/generated/model";
import { WEEKDAYS, zonedParts } from "@/lib/time";

export interface Day {
  date: string;
  label: string;
  items: MyAssignment[];
}

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

function days(items: MyAssignment[]): Day[] {
  const byDate = new Map<string, Day>();
  for (const item of [...items].sort((a, b) =>
    a.start_at.localeCompare(b.start_at),
  )) {
    const { date, weekday } = zonedParts(item.start_at, item.schedule_timezone);
    const day = byDate.get(date) ?? {
      date,
      label: `${WEEKDAYS[weekday] ?? ""} ${String(Number(date.slice(8, 10)))} ${MONTHS[Number(date.slice(5, 7)) - 1] ?? ""}`,
      items: [],
    };
    day.items.push(item);
    byDate.set(date, day);
  }
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export function groupByDay(
  items: MyAssignment[],
  now: Date,
): { upcoming: Day[]; past: Day[] } {
  const done = (i: MyAssignment) => Date.parse(i.end_at) <= now.getTime();
  return {
    upcoming: days(items.filter((i) => !done(i))),
    past: days(items.filter(done)),
  };
}
