import { describeScope, emptyScope } from "./scope";

const names = {
  type: (id: string) => (id === "t1" ? "Lecturer" : "?"),
  resource: () => "R",
  demand: () => "D",
};

describe("describeScope", () => {
  it("says Everything for an empty scope", () => {
    expect(describeScope(emptyScope(), names)).toBe("Everything");
  });
  it("lists each part", () => {
    expect(
      describeScope(
        {
          ...emptyScope(),
          resource_type_ids: ["t1"],
          tags: ["full-time"],
          attrs: [{ attr: "contract", op: "eq", value: "part-time" }],
          series_ids: ["a", "b"],
        },
        names,
      ),
    ).toBe("Lecturer · tagged full-time · contract is part-time · 2 demands");
  });
});
