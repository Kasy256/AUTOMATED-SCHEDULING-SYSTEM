import { groupByDay } from "./days";

const item = (id: string, start: string, end: string) => ({
  activity_id: id,
  activity_name: id.toUpperCase(),
  start_at: start,
  end_at: end,
  resources: { lecturer: ["L1"], room: ["R1"] },
  version_id: "v1",
  schedule_id: "s1",
  schedule_name: "Term 1",
  schedule_timezone: "Africa/Kampala",
  roles: ["lecturer"],
});

describe("groupByDay", () => {
  it("groups by local date", () => {
    const { upcoming } = groupByDay(
      [
        item("late", "2026-01-12T21:30:00Z", "2026-01-12T23:00:00Z"),
        item("morning", "2026-01-13T06:00:00Z", "2026-01-13T08:00:00Z"),
      ],
      new Date("2026-01-10T00:00:00Z"),
    );
    expect(upcoming.map((d) => [d.date, d.label])).toEqual([
      ["2026-01-13", "Tue 13 Jan"],
    ]);
    expect(upcoming[0]?.items.map((i) => i.activity_id)).toEqual([
      "late",
      "morning",
    ]);
  });

  it("puts finished items in the past", () => {
    const { upcoming, past } = groupByDay(
      [
        item("done", "2026-01-12T06:00:00Z", "2026-01-12T08:00:00Z"),
        item("next", "2026-01-14T06:00:00Z", "2026-01-14T08:00:00Z"),
      ],
      new Date("2026-01-13T00:00:00Z"),
    );
    expect(past.map((d) => d.date)).toEqual(["2026-01-12"]);
    expect(upcoming.map((d) => d.date)).toEqual(["2026-01-14"]);
  });
});
