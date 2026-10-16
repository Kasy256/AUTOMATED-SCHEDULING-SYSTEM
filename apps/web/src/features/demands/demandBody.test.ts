import { fromDemand, toDemandWrite, type DemandDraft } from "./demandBody";

const draft: DemandDraft = {
  name: "CS 201",
  slot_template_id: "st1",
  kind: "session",
  sessions_per_week: "2",
  duration_minutes: "",
  slot_labels: [],
  requirements: [
    {
      role: "lecturer",
      resource_type_id: "t1",
      tags: ["cs"],
      attrs: [],
      count_min: 1,
      count_max: 1,
      fixed_resource_ids: [],
      hard: true,
      weight: 0,
    },
  ],
  attrs: { headcount: 40 },
};

describe("demand body", () => {
  it("builds a session demand and omits empty optionals", () => {
    expect(toDemandWrite(draft)).toEqual({
      name: "CS 201",
      slot_template_id: "st1",
      spec: {
        kind: "session",
        sessions_per_week: 2,
        duration_minutes: null,
        slot_labels: null,
        requirements: [
          {
            role: "lecturer",
            resource_type_id: "t1",
            tags: ["cs"],
            attrs: [],
            count_min: 1,
            count_max: 1,
            fixed_resource_ids: [],
            hard: true,
            weight: 0,
          },
        ],
        attrs: { headcount: 40 },
      },
    });
  });

  it("builds a coverage demand without session fields", () => {
    const body = toDemandWrite({
      ...draft,
      kind: "coverage",
      slot_labels: ["Night"],
    });
    expect(body.spec).toEqual({
      kind: "coverage",
      slot_labels: ["Night"],
      requirements: body.spec.requirements,
      attrs: { headcount: 40 },
    });
  });

  it("round-trips a stored demand", () => {
    const stored = {
      ...toDemandWrite(draft),
      id: "d1",
      schedule_id: "s1",
      activity_count: 2,
      pins_removed: 0,
    };
    expect(fromDemand(stored)).toEqual(draft);
  });
});
