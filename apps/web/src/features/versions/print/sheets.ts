import type { AssignmentOut } from "@/api/generated/model";
import { WEEKDAYS, formatMinuteOfDay, mondayOf, zonedParts } from "@/lib/time";

export interface SheetCell {
  name: string;
  others: string;
}

export interface Sheet {
  key: string;
  title: string;
  week: string;
  days: { weekday: number; label: string }[];
  rows: { minute: number; label: string }[];
  cells: Map<string, SheetCell[]>;
}

interface Placed {
  assignment: AssignmentOut;
  monday: string;
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

const weekLabel = (monday: string) =>
  `Week of ${String(Number(monday.slice(8, 10)))} ${MONTHS[Number(monday.slice(5, 7)) - 1] ?? ""}`;

export function buildSheets(input: {
  resources: { id: string; name: string; code: string }[];
  assignments: AssignmentOut[];
  timeZone: string;
  slots: { label: string; weekdays: number[]; start_minute: number }[];
  codeOf: (id: string) => string;
}): { sheets: Sheet[]; idle: string[] } {
  const { resources, assignments, timeZone, slots, codeOf } = input;
  const placed: Placed[] = assignments.map((assignment) => {
    const { date, weekday, minute } = zonedParts(assignment.start_at, timeZone);
    return { assignment, monday: mondayOf(date), weekday, minute };
  });
  // Every sheet of a week shares the week's slot rows and days, so pages line up when compared.
  const weekRows = new Map<string, Set<number>>();
  const weekDays = new Map<string, Set<number>>();
  for (const p of placed) {
    weekRows.set(p.monday, (weekRows.get(p.monday) ?? new Set()).add(p.minute));
    weekDays.set(
      p.monday,
      (weekDays.get(p.monday) ?? new Set()).add(p.weekday),
    );
  }
  const slotLabel = (minute: number) =>
    slots.find((s) => s.start_minute === minute)?.label ??
    formatMinuteOfDay(minute);

  const sheets: Sheet[] = [];
  const idle: string[] = [];
  const ordered = [...resources].sort((a, b) => a.name.localeCompare(b.name));
  for (const resource of ordered) {
    const title = `${resource.name} (${resource.code})`;
    const mine = placed.filter((p) =>
      Object.values(p.assignment.resources).some((ids) =>
        ids.includes(resource.id),
      ),
    );
    if (mine.length === 0) {
      idle.push(title);
      continue;
    }
    const mondays = [...new Set(mine.map((p) => p.monday))].sort();
    for (const monday of mondays) {
      const cells = new Map<string, SheetCell[]>();
      for (const p of mine.filter((x) => x.monday === monday)) {
        const key = `${String(p.weekday)}|${String(p.minute)}`;
        const others = Object.values(p.assignment.resources)
          .flat()
          .filter((id) => id !== resource.id)
          .map(codeOf)
          .join(" · ");
        cells.set(key, [
          ...(cells.get(key) ?? []),
          { name: p.assignment.activity_name ?? "Activity", others },
        ]);
      }
      sheets.push({
        key: `${resource.id}|${monday}`,
        title,
        week: weekLabel(monday),
        days: [...(weekDays.get(monday) ?? [])]
          .sort((a, b) => a - b)
          .map((weekday) => ({ weekday, label: WEEKDAYS[weekday] ?? "" })),
        rows: [...(weekRows.get(monday) ?? [])]
          .sort((a, b) => a - b)
          .map((minute) => ({ minute, label: slotLabel(minute) })),
        cells,
      });
    }
  }
  return { sheets, idle };
}
