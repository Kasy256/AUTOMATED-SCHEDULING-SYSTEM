export const WEEKDAYS = [
  "Mon",
  "Tue",
  "Wed",
  "Thu",
  "Fri",
  "Sat",
  "Sun",
] as const;

const pad = (n: number) => String(n).padStart(2, "0");

export function formatMinuteOfDay(minute: number): string {
  return `${pad(Math.floor(minute / 60))}:${pad(minute % 60)}`;
}

export function parseTimeOfDay(text: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(text.trim());
  if (!match) return null;
  const minutes = Number(match[1]) * 60 + Number(match[2]);
  return Number(match[2]) < 60 && minutes <= 1440 ? minutes : null;
}

export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${String(m)} min`;
  return m === 0 ? `${String(h)} h` : `${String(h)} h ${String(m)} min`;
}

function zoneOffsetMinutes(utcMillis: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(utcMillis);
  const get = (type: string) =>
    Number(parts.find((p) => p.type === type)?.value);
  const asUtc = Date.UTC(
    get("year"),
    get("month") - 1,
    get("day"),
    get("hour"),
    get("minute"),
    get("second"),
  );
  return Math.round((asUtc - utcMillis) / 60_000);
}

export function toUtcIso(localDateTime: string, timeZone: string): string {
  const [date = "", time = "00:00"] = localDateTime.split("T");
  const [y, mo, d] = date.split("-").map(Number);
  const [h, mi] = time.split(":").map(Number);
  const wall = Date.UTC(y ?? 0, (mo ?? 1) - 1, d ?? 1, h ?? 0, mi ?? 0);
  // Two passes settle the offset across a DST change.
  let utc = wall - zoneOffsetMinutes(wall, timeZone) * 60_000;
  utc = wall - zoneOffsetMinutes(utc, timeZone) * 60_000;
  return new Date(utc).toISOString();
}

export function formatInZone(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(iso));
}

export function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}
export function isoInstant(iso: string): string {
  return new Date(iso).toISOString();
}

// Building an Intl formatter is far slower than using one; the board resolves thousands of starts.
const formats = new Map<string, Intl.DateTimeFormat>();
function zonedFormat(timeZone: string): Intl.DateTimeFormat {
  let format = formats.get(timeZone);
  if (!format) {
    format = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      weekday: "short",
    });
    formats.set(timeZone, format);
  }
  return format;
}

export function localInputNow(timeZone: string, now = new Date()): string {
  const { date, minute } = zonedParts(now.toISOString(), timeZone);
  return `${date}T${pad(Math.floor(minute / 60))}:${pad(minute % 60)}`;
}

export function zonedParts(
  iso: string,
  timeZone: string,
): { date: string; weekday: number; minute: number } {
  const parts = zonedFormat(timeZone).formatToParts(new Date(iso));
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return {
    date: `${get("year")}-${get("month")}-${get("day")}`,
    weekday: days.indexOf(get("weekday")),
    minute: Number(get("hour")) * 60 + Number(get("minute")),
  };
}

export function addDays(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function mondayOf(date: string): string {
  const weekday = (new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7;
  return addDays(date, -weekday);
}

export function scheduleWeeks(startDate: string, endDate: string): string[] {
  const weeks: string[] = [];
  for (
    let monday = mondayOf(startDate);
    monday <= endDate;
    monday = addDays(monday, 7)
  )
    weeks.push(monday);
  return weeks;
}
