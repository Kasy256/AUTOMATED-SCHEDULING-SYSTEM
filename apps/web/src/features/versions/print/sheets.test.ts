import { buildSheets } from "./sheets";

const TZ = "Africa/Kampala"; // UTC+3
const slots = [
  { label: "P1", weekdays: [0, 1, 2, 3, 4], start_minute: 540 },
  { label: "P2", weekdays: [0, 1, 2, 3, 4], start_minute: 690 },
];
const resources = [
  { id: "L1", name: "Kato", code: "L001" },
  { id: "L2", name: "Nalu", code: "L002" },
];
const codes = new Map([
  ["L1", "L001"],
  ["L2", "L002"],
  ["R1", "LH3"],
]);
const a = (id: string, start: string, room = "R1") => ({
  activity_id: id,
  activity_name: id.toUpperCase(),
  start_at: start,
  end_at: start,
  resources: { lecturer: ["L1"], room: [room] },
});

const assignments = [
  a("x", "2026-01-12T06:00:00Z"), // Mon 09:00
  a("y", "2026-01-13T08:30:00Z"), // Tue 11:30
  a("z", "2026-01-19T06:00:00Z"), // next Mon 09:00
];

function build(list = assignments) {
  return buildSheets({
    resources,
    assignments: list,
    timeZone: TZ,
    slots,
    codeOf: (id) => codes.get(id) ?? "?",
  });
}

describe("buildSheets", () => {
  it("makes one sheet per resource per week with work, and lists idle resources", () => {
    const { sheets, idle } = build();
    expect(sheets.map((s) => [s.title, s.week])).toEqual([
      ["Kato (L001)", "Week of 12 Jan"],
      ["Kato (L001)", "Week of 19 Jan"],
    ]);
    expect(idle).toEqual(["Nalu (L002)"]);
  });

  it("lays out days and slot rows with the activity and its other resources", () => {
    const [first] = build().sheets;
    expect(first?.days.map((d) => d.label)).toEqual(["Mon", "Tue"]);
    expect(first?.rows).toEqual([
      { minute: 540, label: "P1" },
      { minute: 690, label: "P2" },
    ]);
    expect(first?.cells.get("0|540")).toEqual([{ name: "X", others: "LH3" }]);
    expect(first?.cells.get("1|690")).toEqual([{ name: "Y", others: "LH3" }]);
  });

  it("falls back for unknown resources", () => {
    const { sheets } = build([a("x", "2026-01-12T06:00:00Z", "GONE")]);
    expect(sheets[0]?.cells.get("0|540")).toEqual([{ name: "X", others: "?" }]);
  });
});
