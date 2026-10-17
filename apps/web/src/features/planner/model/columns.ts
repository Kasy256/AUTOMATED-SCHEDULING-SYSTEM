import {
  WEEKDAYS,
  addDays,
  formatMinuteOfDay,
  isoInstant,
  zonedParts,
} from "@/lib/time";

export interface Column {
  start: string;
  label: string;
  dayLabel: string;
  weekday: number;
  minute: number;
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

export function weekColumns(
  starts: string[],
  monday: string,
  timeZone: string,
  slots: { label: string; weekdays: number[]; start_minute: number }[],
): Column[] {
  const sunday = addDays(monday, 6);
  const seen = new Map<string, Column>();
  // Activities share a handful of starts; resolve each distinct instant once.
  for (const start of new Set([...new Set(starts)].map(isoInstant))) {
    const { date, weekday, minute } = zonedParts(start, timeZone);
    if (date < monday || date > sunday) continue;
    const slot = slots.find(
      (s) => s.start_minute === minute && s.weekdays.includes(weekday),
    );
    const day = WEEKDAYS[weekday] ?? "";
    seen.set(start, {
      start,
      weekday,
      minute,
      label: `${day} ${slot ? slot.label : formatMinuteOfDay(minute)}`,
      dayLabel: `${day} ${String(Number(date.slice(8, 10)))} ${MONTHS[Number(date.slice(5, 7)) - 1] ?? ""}`,
    });
  }
  return [...seen.values()].sort((a, b) => a.start.localeCompare(b.start));
}
