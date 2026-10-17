import { fromFormValues, toFormValues } from "./attributes";

const defs = [
  {
    key: "faculty",
    label: "Faculty",
    type: "string" as const,
    required: true,
    enum_values: null,
  },
  {
    key: "max_hours",
    label: null,
    type: "integer" as const,
    required: false,
    enum_values: null,
  },
  {
    key: "part_time",
    label: null,
    type: "boolean" as const,
    required: false,
    enum_values: null,
  },
  {
    key: "contract",
    label: null,
    type: "enum" as const,
    required: false,
    enum_values: ["full", "part"],
  },
  {
    key: "skills",
    label: null,
    type: "tags" as const,
    required: false,
    enum_values: null,
  },
];

describe("attribute values", () => {
  it("round-trips typed values", () => {
    const form = toFormValues(defs, {
      faculty: "CS",
      max_hours: 20,
      part_time: true,
      contract: "part",
      skills: ["ai"],
    });
    expect(form).toEqual({
      faculty: "CS",
      max_hours: "20",
      part_time: true,
      contract: "part",
      skills: ["ai"],
    });
    expect(fromFormValues(defs, form)).toEqual({
      attributes: {
        faculty: "CS",
        max_hours: 20,
        part_time: true,
        contract: "part",
        skills: ["ai"],
      },
      errors: {},
    });
  });

  it("reports bad numbers and missing required values and omits empty optionals", () => {
    const result = fromFormValues(defs, {
      faculty: "",
      max_hours: "2.5",
      part_time: false,
      contract: "",
      skills: [],
    });
    expect(result.errors).toEqual({
      faculty: "Required",
      max_hours: "Enter a whole number",
    });
    expect(result.attributes).toEqual({ part_time: false, skills: [] });
  });
});
