import { compareTargetOf, diffSummary, originOf } from "./model";

const v = (
  number: number,
  status: string,
  extra: Record<string, unknown> = {},
) =>
  ({
    id: `v${String(number)}`,
    schedule_id: "s1",
    number,
    status,
    solver_status: "OPTIMAL",
    hard_violations: 0,
    soft_total: 0,
    created_at: "2026-01-01T00:00:00Z",
    published_at: null,
    archived_at: null,
    parent_version_id: null,
    solve_run_id: `r${String(number)}`,
    ...extra,
  }) as never;

describe("version helpers", () => {
  it("names where a version came from", () => {
    // A repair's output has the published version as parent; a board edit keeps its source's run.
    const runs = [
      { id: "r2", kind: "repair", version_id: "v2" },
      { id: "r1", kind: "solve", version_id: "v1" },
    ] as never;
    expect(originOf(v(1, "draft"), runs)).toBe("Solve");
    expect(originOf(v(2, "draft", { parent_version_id: "v1" }), runs)).toBe(
      "Repair",
    );
    expect(
      originOf(
        v(3, "draft", { parent_version_id: "v2", solve_run_id: "r2" }),
        runs,
      ),
    ).toBe("Board edit");
  });

  it("compares with the published version, else the previous one", () => {
    const [v1, v2, v3] = [v(1, "archived"), v(2, "published"), v(3, "draft")];
    const all = [v1, v2, v3];
    expect(compareTargetOf(v3, all)?.id).toBe("v2");
    expect(compareTargetOf(v2, all)?.id).toBe("v1");
    expect(compareTargetOf(v(1, "draft"), [v(1, "draft")])).toBeNull();
  });

  it("summarises a diff", () => {
    const change = { activity_id: "a", before: null, after: null };
    const s = diffSummary({
      added: [],
      removed: [change],
      moved: [change, change],
      reassigned: [change],
    });
    expect(s).toMatchObject({
      moved: 2,
      reassigned: 1,
      added: 0,
      removed: 1,
      total: 4,
    });
    expect(s.text).toBe("2 moved · 1 reassigned · 0 added · 1 removed");
  });
});
