import { weekColumns } from "./columns";

const TZ = "Africa/Kampala"; // UTC+3
const slots = [
  { label: "P1", weekdays: [0, 1, 2, 3, 4], start_minute: 540 },
  { label: "P2", weekdays: [0, 1, 2, 3, 4], start_minute: 690 },
];

describe("weekColumns", () => {
  it("makes one sorted column per distinct start in the week, labelled by slot", () => {
    const starts = [
      "2026-01-13T06:00:00Z",
      "2026-01-12T08:30:00Z",
      "2026-01-12T06:00:00Z",
      "2026-01-12T06:00:00.000Z",
      "2026-01-19T06:00:00Z",
    ];
    const cols = weekColumns(starts, "2026-01-12", TZ, slots);
    expect(cols.map((c) => c.label)).toEqual(["Mon P1", "Mon P2", "Tue P1"]);
    expect(cols[0]).toMatchObject({
      start: "2026-01-12T06:00:00.000Z",
      weekday: 0,
      minute: 540,
      dayLabel: "Mon 12 Jan",
    });
  });

  it("labels starts that match no slot by time", () => {
    expect(
      weekColumns(["2026-01-14T07:15:00Z"], "2026-01-12", TZ, slots).map(
        (c) => c.label,
      ),
    ).toEqual(["Wed 10:15"]);
  });

  it("a week with no activities has no columns", () => {
    expect(
      weekColumns(["2026-01-12T06:00:00Z"], "2026-01-19", TZ, slots),
    ).toEqual([]);
  });
});
