import { useVersionReport } from "@/api/generated/versions/versions";
import { WEEKDAYS, formatMinuteOfDay, zonedParts } from "@/lib/time";

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

function localStart(iso: string, timezone: string) {
  const { date, weekday, minute } = zonedParts(iso, timezone);
  const day = `${Number(date.slice(8, 10))} ${MONTHS[Number(date.slice(5, 7)) - 1] ?? ""}`;
  return {
    date,
    label: `${WEEKDAYS[weekday] ?? ""} ${day}, ${formatMinuteOfDay(minute)}`,
  };
}

export function CoverageGapsPanel({
  versionId,
  weekStart,
  weekEnd,
  activityNames,
  timezone,
}: {
  versionId: string;
  weekStart: string;
  weekEnd: string;
  activityNames: Record<string, string>;
  timezone: string;
}) {
  const { data: report, isError } = useVersionReport(versionId, {
    query: { enabled: versionId !== "" },
  });

  const gaps = (report?.coverage_gaps ?? [])
    .map((g) => ({ gap: g, at: localStart(g.starts_at, timezone) }))
    .filter(({ at }) => at.date >= weekStart && at.date <= weekEnd)
    .sort((a, b) => a.gap.starts_at.localeCompare(b.gap.starts_at));

  return (
    <section aria-labelledby="coverage-gaps-heading" className="text-sm">
      <h2 id="coverage-gaps-heading" className="font-medium">
        Coverage gaps
      </h2>
      {isError ? (
        <p role="alert" className="text-destructive">
          Couldn&apos;t load coverage gaps
        </p>
      ) : !report ? (
        <p className="text-muted-foreground">Loading coverage gaps…</p>
      ) : gaps.length === 0 ? (
        <p className="text-muted-foreground">
          Every shift is fully staffed this week
        </p>
      ) : (
        <ul className="mt-1 grid gap-1">
          {gaps.map(({ gap, at }) => (
            <li key={`${gap.activity_id}-${gap.role}`}>
              {activityNames[gap.activity_id] ?? "Shift"} · {at.label} —{" "}
              {gap.role} {gap.assigned} of {gap.required_min}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
