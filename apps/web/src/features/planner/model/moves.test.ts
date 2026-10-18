import { buildMove } from "./moves";

const item = {
  activityId: "x",
  start: "2026-01-12T06:00:00Z",
  resources: { lecturer: ["L1"], room: ["R1"], group: ["G1", "G2"] },
};

describe("buildMove", () => {
  it("moves time along the same row", () => {
    expect(
      buildMove(item, "L1", {
        resourceId: "L1",
        start: "2026-01-13T06:00:00Z",
      }),
    ).toEqual({
      activity_id: "x",
      start_at: "2026-01-13T06:00:00.000Z",
      resources: item.resources,
    });
  });

  it("swaps the resource in the role that holds the source row", () => {
    expect(
      buildMove(item, "G2", { resourceId: "G3", start: item.start })?.resources,
    ).toEqual({
      lecturer: ["L1"],
      room: ["R1"],
      group: ["G1", "G3"],
    });
  });

  it("returns null for the same cell", () => {
    expect(
      buildMove(item, "L1", {
        resourceId: "L1",
        start: "2026-01-12T06:00:00.000Z",
      }),
    ).toBeNull();
  });

  it("returns null when the target resource is already in that role", () => {
    expect(
      buildMove(item, "G1", { resourceId: "G2", start: item.start }),
    ).toBeNull();
  });
});
