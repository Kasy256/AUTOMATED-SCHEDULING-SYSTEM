import {
  formatDuration,
  formatInZone,
  formatMinuteOfDay,
  parseTimeOfDay,
  toUtcIso,
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
