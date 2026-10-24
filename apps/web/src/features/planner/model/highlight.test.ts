import { cellKey } from "./items";
import { highlightMap } from "./highlight";

const current = { resources: { lecturer: ["L1"], room: ["R1"] } };
const ok = { valid: true, broken: [], penalties: [] };
const bad = (rule: string) => ({
  valid: false,
  broken: [
    {
      constraint_id: "c",
      rule,
      message: `${rule} broken`,
      activity_ids: [],
      resource_ids: [],
    },
  ],
  penalties: [],
});
const explanation = {
  activity_id: "x",
  binding: [],
  truncated: false,
  alternatives: [
    {
      start_at: "2026-01-13T06:00:00Z",
      resources: { lecturer: ["L1"], room: ["R1"] },
      check: ok,
    },
    {
      start_at: "2026-01-13T08:30:00Z",
      resources: { lecturer: ["L2"], room: ["R1"] },
      check: bad("Lecturer at most 2 a day"),
    },
    {
      start_at: "2026-01-13T06:00:00Z",
      resources: { lecturer: ["L1"], room: ["R9"] },
      check: ok,
    },
  ],
};

describe("highlightMap", () => {
  it("keeps alternatives that only change the dragged role, keyed by target row", () => {
    const map = highlightMap(explanation, current, "L1");
    expect(map.get(cellKey("L1", "2026-01-13T06:00:00Z"))).toEqual({
      state: "valid",
    });
    expect(map.get(cellKey("L2", "2026-01-13T08:30:00Z"))).toEqual({
      state: "invalid",
      reasons: ["Lecturer at most 2 a day broken"],
    });
    expect(map.size).toBe(2); // the room change is not a lecturer-row move
  });

  it("on the room tab, only room changes count", () => {
    const map = highlightMap(explanation, current, "R1");
    expect([...map.keys()]).toEqual([
      cellKey("R1", "2026-01-13T06:00:00Z"),
      cellKey("R9", "2026-01-13T06:00:00Z"),
    ]);
  });
});
