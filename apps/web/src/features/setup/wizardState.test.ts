import { importRows, wizardStep } from "./wizardState";

describe("wizardStep", () => {
  it("derives the step from the URL", () => {
    expect(wizardStep(new URLSearchParams(""))).toBe(1);
    expect(wizardStep(new URLSearchParams("template=education"))).toBe(2);
    expect(
      wizardStep(new URLSearchParams("template=education&schedule=s1")),
    ).toBe(3);
    expect(wizardStep(new URLSearchParams("template=blank&schedule=s1"))).toBe(
      4,
    );
    expect(
      wizardStep(
        new URLSearchParams("template=education&schedule=s1&step=finish"),
      ),
    ).toBe(4);
  });
});

describe("importRows", () => {
  const template = {
    key: "education",
    version: 2,
    name: "Education",
    description: "d",
    resource_types: [
      {
        key: "lecturer",
        name: "Lecturer",
        kind: "person" as const,
        attribute_schema: { version: 1 as const, attributes: [] },
      },
      {
        key: "room",
        name: "Room",
        kind: "space" as const,
        attribute_schema: { version: 1 as const, attributes: [] },
      },
    ],
    day_parts: { version: 1 as const, parts: [] },
    slot_templates: [],
    demand_shape: null,
    constraints: [],
  };
  const types = [
    {
      id: "tl",
      key: "lecturer",
      name: "Lecturer",
      kind: "person" as const,
      attribute_schema: { version: 1 as const, attributes: [] },
    },
    {
      id: "tr",
      key: "room",
      name: "Room",
      kind: "space" as const,
      attribute_schema: { version: 1 as const, attributes: [] },
    },
  ];
  const committed = {
    id: "i1",
    kind: "resources" as const,
    status: "committed" as const,
    filename: "l.csv",
    resource_type_id: "tl",
    schedule_id: null,
    columns: null,
    size_bytes: 1,
    report: null,
    created_at: "2026-10-16T00:00:00Z",
    committed_at: "2026-10-16T00:00:00Z",
  };

  it("marks committed types done and blocks demands until all types are done", () => {
    const rows = importRows(template, types, [committed], "s1");
    expect(rows.map((r) => [r.key, r.done !== null, r.blockedBy])).toEqual([
      ["lecturer", true, []],
      ["room", false, []],
      ["demands", false, ["Room"]],
    ]);
  });
});
