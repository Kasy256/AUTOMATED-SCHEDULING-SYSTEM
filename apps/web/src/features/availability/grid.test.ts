import { paint, planSave, rulesToGrid, type RuleLike } from "./grid";

const rule = (
  id: string,
  weekday: number,
  start: number,
  end: number,
  kind: RuleLike["kind"] = "available",
): RuleLike => ({
  id,
  kind,
  weekday,
  start_minute: start,
  end_minute: end,
});

describe("availability grid", () => {
  it("maps rules onto 30-minute cells with priority on overlap", () => {
    const grid = rulesToGrid([
      rule("a", 0, 480, 600),
      rule("b", 0, 540, 570, "unavailable"),
    ]);
    expect(grid[0]?.slice(16, 20)).toEqual([
      "available",
      "available",
      "unavailable",
      "available",
    ]);
    expect(grid[1]?.every((c) => c === null)).toBe(true);
  });

  it("paints a rectangle across days", () => {
    const grid = paint(
      rulesToGrid([]),
      { day: 1, cell: 18 },
      { day: 0, cell: 16 },
      "preferred",
    );
    expect(grid[0]?.slice(16, 19)).toEqual([
      "preferred",
      "preferred",
      "preferred",
    ]);
    expect(grid[1]?.slice(16, 19)).toEqual([
      "preferred",
      "preferred",
      "preferred",
    ]);
    expect(grid[2]?.[16]).toBeNull();
  });

  it("creates merged runs and removes replaced rules on touched days", () => {
    const rules = [rule("a", 0, 480, 600)];
    let grid = rulesToGrid(rules);
    grid = paint(grid, { day: 0, cell: 20 }, { day: 0, cell: 21 }, "available"); // extend to 11:00
    expect(planSave(rules, grid, new Set([0]))).toEqual({
      create: [
        { kind: "available", weekday: 0, start_minute: 480, end_minute: 660 },
      ],
      remove: ["a"],
    });
  });

  it("keeps rules on untouched cells exactly", () => {
    // A 10-minute rule on Tuesday, created through the API, must survive a Monday edit.
    const rules = [rule("fine", 1, 485, 495), rule("mon", 0, 480, 540)];
    const grid = paint(
      rulesToGrid(rules),
      { day: 0, cell: 18 },
      { day: 0, cell: 18 },
      "available",
    );
    const plan = planSave(rules, grid, new Set([0]));
    // Monday 08:00-09:00 plus the painted 09:00-09:30 cell is one run; Tuesday is untouched.
    expect(plan.remove).toEqual(["mon"]);
    expect(plan.create).toEqual([
      { kind: "available", weekday: 0, start_minute: 480, end_minute: 570 },
    ]);
  });

  it("keeps an existing rule that already matches a run", () => {
    const rules = [rule("a", 2, 480, 600)];
    expect(planSave(rules, rulesToGrid(rules), new Set([2]))).toEqual({
      create: [],
      remove: [],
    });
  });

  it("erasing a whole day removes its rules", () => {
    const rules = [rule("a", 3, 480, 600)];
    const grid = paint(
      rulesToGrid(rules),
      { day: 3, cell: 0 },
      { day: 3, cell: 47 },
      null,
    );
    expect(planSave(rules, grid, new Set([3]))).toEqual({
      create: [],
      remove: ["a"],
    });
  });
  it("keeps preferred time available once the grid uses Available blocks", () => {
    let grid = paint(
      rulesToGrid([]),
      { day: 0, cell: 18 },
      { day: 0, cell: 33 },
      "available",
    ); // Mon 09-17
    grid = paint(grid, { day: 1, cell: 20 }, { day: 1, cell: 23 }, "preferred"); // Tue 10-12
    const plan = planSave([], grid, new Set([0, 1]));
    expect(plan.create).toEqual([
      { kind: "available", weekday: 0, start_minute: 540, end_minute: 1020 },
      { kind: "preferred", weekday: 1, start_minute: 600, end_minute: 720 },
      { kind: "available", weekday: 1, start_minute: 600, end_minute: 720 },
    ]);
  });

  it("does not split an available window around a preference when repainting the day", () => {
    const rules = [
      rule("avail", 0, 540, 1020),
      rule("pref", 0, 600, 660, "preferred"),
    ];
    const grid = paint(
      rulesToGrid(rules),
      { day: 0, cell: 17 },
      { day: 0, cell: 17 },
      "available",
    ); // add 08:30
    const plan = planSave(rules, grid, new Set([0]));
    expect(plan.remove).toEqual(["avail"]);
    expect(plan.create).toEqual([
      { kind: "available", weekday: 0, start_minute: 510, end_minute: 1020 },
    ]);
  });

  it("adds no availability when the grid has no Available blocks", () => {
    const grid = paint(
      rulesToGrid([]),
      { day: 2, cell: 20 },
      { day: 2, cell: 21 },
      "avoided",
    );
    expect(planSave([], grid, new Set([2])).create).toEqual([
      { kind: "avoided", weekday: 2, start_minute: 600, end_minute: 660 },
    ]);
  });
});
