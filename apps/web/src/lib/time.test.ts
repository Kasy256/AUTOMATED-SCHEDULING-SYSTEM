import {
  formatDuration,
  formatInZone,
  formatMinuteOfDay,
  parseTimeOfDay,
  toUtcIso,
} from "./time";
import {
  addDays,
  isoInstant,
  localInputNow,
  mondayOf,
  scheduleWeeks,
  zonedParts,
} from "./time";

describe("time helpers", () => {
  it("formats and parses minutes of the day", () => {
    expect(formatMinuteOfDay(570)).toBe("09:30");
    expect(formatMinuteOfDay(1440)).toBe("24:00");
    expect(parseTimeOfDay("09:30")).toBe(570);
    expect(parseTimeOfDay("24:00")).toBe(1440);
    expect(parseTimeOfDay("24:30")).toBeNull();
    expect(parseTimeOfDay("9h")).toBeNull();
  });

  it("formats durations", () => {
    expect(formatDuration(120)).toBe("2 h");
    expect(formatDuration(90)).toBe("1 h 30 min");
    expect(formatDuration(45)).toBe("45 min");
  });

  it("converts a local wall time in a zone to UTC and back", () => {
    expect(toUtcIso("2026-03-02T09:00", "Africa/Kampala")).toBe(
      "2026-03-02T06:00:00.000Z",
    );
    expect(toUtcIso("2026-07-01T09:00", "Europe/London")).toBe(
      "2026-07-01T08:00:00.000Z",
    );
    expect(formatInZone("2026-03-02T06:00:00Z", "Africa/Kampala")).toBe(
      "2 Mar 2026, 09:00",
    );
  });
});

describe("zoned calendar helpers", () => {
  it("normalises instants", () => {
    expect(isoInstant("2026-01-12T09:00:00+03:00")).toBe(
      "2026-01-12T06:00:00.000Z",
    );
  });

  it("reads local date, weekday and minute in a zone", () => {
    expect(zonedParts("2026-01-12T06:00:00Z", "Africa/Kampala")).toEqual({
      date: "2026-01-12",
      weekday: 0,
      minute: 540,
    });
    expect(zonedParts("2026-01-11T22:30:00Z", "Africa/Kampala")).toEqual({
      date: "2026-01-12",
      weekday: 0,
      minute: 90,
    });
  });

  it("does calendar arithmetic and finds Mondays", () => {
    expect(addDays("2026-01-30", 3)).toBe("2026-02-02");
    expect(mondayOf("2026-01-15")).toBe("2026-01-12");
    expect(mondayOf("2026-01-12")).toBe("2026-01-12");
    expect(mondayOf("2026-01-18")).toBe("2026-01-12");
  });

  it("lists the Mondays covering a horizon", () => {
    expect(scheduleWeeks("2026-01-14", "2026-01-27")).toEqual([
      "2026-01-12",
      "2026-01-19",
      "2026-01-26",
    ]);
    expect(scheduleWeeks("2026-01-12", "2026-01-16")).toEqual(["2026-01-12"]);
  });
});

describe("localInputNow", () => {
  it("is the wall-clock time in the zone, ready for a datetime-local input", () => {
    expect(
      localInputNow("Africa/Kampala", new Date("2026-01-12T06:05:00Z")),
    ).toBe("2026-01-12T09:05");
  });
});
