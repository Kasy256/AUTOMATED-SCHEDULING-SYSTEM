import { applyPending, cellIndex, cellKey } from "./items";

const a = (id: string, start: string, resources: Record<string, string[]>) => ({
  activity_id: id,
  activity_name: id.toUpperCase(),
  start_at: start,
  end_at: start,
  resources,
});

describe("board items", () => {
  const assignments = [
    a("x", "2026-01-12T06:00:00Z", { lecturer: ["L1"], room: ["R1"] }),
    a("y", "2026-01-12T06:00:00Z", { lecturer: ["L2"], room: ["R2"] }),
  ];

  it("overrides assignments with pending changes", () => {
    const rows = applyPending(assignments, [
      {
        activity_id: "x",
        start_at: "2026-01-13T06:00:00Z",
        resources: { lecturer: ["L1"], room: ["R1"] },
      },
    ]);
    expect(rows.find((r) => r.activity_id === "x")).toMatchObject({
      start_at: "2026-01-13T06:00:00Z",
      pending: true,
    });
    expect(rows.find((r) => r.activity_id === "y")?.pending).toBe(false);
  });

  it("indexes items by row resource and start for the visible type", () => {
    const index = cellIndex(
      applyPending(assignments, []),
      new Set(["L1", "L2"]),
      new Set(["y"]),
    );
    expect(
      index
        .get(cellKey("L1", "2026-01-12T06:00:00Z"))
        ?.map((i) => i.activityId),
    ).toEqual(["x"]);
    expect(
      index.get(cellKey("L2", "2026-01-12T06:00:00.000Z"))?.[0]?.pinned,
    ).toBe(true);
    expect(index.has(cellKey("R1", "2026-01-12T06:00:00Z"))).toBe(false);
  });
});
