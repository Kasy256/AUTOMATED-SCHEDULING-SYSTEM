import { autoResourceMapping, demandMappingFromTemplate } from "./mapping";

const lecturer = {
  id: "t1",
  key: "lecturer",
  name: "Lecturer",
  kind: "person" as const,
  attribute_schema: {
    version: 1 as const,
    attributes: [
      {
        key: "role",
        label: "Role",
        type: "enum" as const,
        required: true,
        enum_values: ["Full-Time"],
      },
      {
        key: "faculty",
        label: "Faculty",
        type: "string" as const,
        required: false,
        enum_values: null,
      },
    ],
  },
};

describe("autoResourceMapping", () => {
  it("matches columns named like fields and attributes", () => {
    expect(
      autoResourceMapping(
        ["code", "name", "role", "faculty", "subjects"],
        lecturer,
      ),
    ).toEqual({
      kind: "resources",
      code: "code",
      name: "name",
      tags: null,
      capacity: null,
      size: null,
      concurrency: null,
      attributes: { role: "role", faculty: "faculty" },
    });
  });
  it("falls back to the first column for code and name", () => {
    expect(
      autoResourceMapping(["ID", "Title"], {
        ...lecturer,
        attribute_schema: { version: 1, attributes: [] },
      }),
    ).toMatchObject({
      code: "ID",
      name: "ID",
    });
  });
});

describe("demandMappingFromTemplate", () => {
  it("fills ids and the chosen term", () => {
    const shape = {
      kind: "session" as const,
      slot_template: "Teaching periods",
      name_column: "subject",
      sessions_per_week_column: null,
      weekly_minutes_column: "weekly_minutes",
      requirements: [
        {
          role: "group",
          resource_type_key: "student_group",
          count_min: 1,
          count_max: 1,
          count_from_fixed: true,
          fixed_codes_column: "group",
          tags_column: null,
          attribute_columns: {},
        },
      ],
      term_split: {
        term_column: "term",
        unit_column: "unit",
        group_column: "group",
        merge_column: "subject",
        pair_column: "pair",
        prefer: { room_type: ["Lab", "Theory"] },
      },
    };
    expect(
      demandMappingFromTemplate(
        shape,
        { slotTemplateId: "st1", typeIdByKey: { student_group: "tg" } },
        "Term 1",
      ),
    ).toEqual({
      kind: "demands",
      demand_kind: "session",
      slot_template_id: "st1",
      name: "subject",
      sessions_per_week: null,
      weekly_minutes: "weekly_minutes",
      requirements: [
        {
          role: "group",
          resource_type_id: "tg",
          count_min: 1,
          count_max: 1,
          count_from_fixed: true,
          fixed_codes_column: "group",
          tags_column: null,
          attribute_columns: {},
        },
      ],
      term_split: {
        term_column: "term",
        unit_column: "unit",
        group_column: "group",
        merge_column: "subject",
        pair_column: "pair",
        prefer: { room_type: ["Lab", "Theory"] },
        term: "Term 1",
      },
    });
  });
});
