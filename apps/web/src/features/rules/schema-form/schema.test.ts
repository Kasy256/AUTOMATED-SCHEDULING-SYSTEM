import { SCHEMAS } from "./fixtures";
import { initialValues, parseSchema, toParams } from "./schema";

const parse = (key: keyof typeof SCHEMAS) => parseSchema(SCHEMAS[key]);

describe("parseSchema", () => {
  it("understands every v1 template without unsupported fields", () => {
    for (const key of Object.keys(SCHEMAS) as (keyof typeof SCHEMAS)[]) {
      const unsupported = JSON.stringify(parse(key)).includes(
        '"kind":"unsupported"',
      );
      expect({ key, unsupported }).toEqual({ key, unsupported: false });
    }
  });

  it("reads enums, nullable integers with units and window refs", () => {
    const nodes = parse("max_load");
    expect(nodes.map((n) => [n.name, n.kind])).toEqual([
      ["period", "enum"],
      ["window", "ref"],
      ["max_count", "integer"],
      ["max_minutes", "integer"],
    ]);
    expect(nodes[3]).toMatchObject({
      title: "Max time",
      unit: "minutes",
      nullable: true,
      required: false,
    });
    expect(nodes[1]).toMatchObject({ ref: "window", title: "Part of day" });
  });

  it("reads lists of objects with series refs and grouped refs", () => {
    const pairs = parse("precedence")[0];
    expect(pairs).toMatchObject({
      kind: "objectList",
      name: "pairs",
      minItems: 1,
    });
    expect(
      pairs?.kind === "objectList" && pairs.fields.map((f) => [f.name, f.kind]),
    ).toEqual([
      ["before", "ref"],
      ["after", "ref"],
    ]);
    expect(parse("same_time")[0]).toMatchObject({
      kind: "refGroups",
      ref: "series",
    });
    const filter = parse("fairness")[0];
    expect(filter).toMatchObject({ kind: "object", name: "activity_filter" });
  });
});

describe("toParams", () => {
  it("converts and validates values", () => {
    const nodes = parse("max_load");
    const values = initialValues(nodes);
    expect(values).toEqual({
      period: "",
      window: null,
      max_count: "",
      max_minutes: "",
    });
    expect(toParams(nodes, values).errors).toEqual([
      { path: "period", message: "Required" },
    ]);
    expect(
      toParams(nodes, { ...values, period: "day", max_count: "2" }),
    ).toEqual({
      params: { period: "day", max_count: 2 },
      errors: [],
    });
    expect(
      toParams(nodes, { ...values, period: "day", max_count: "2.5" }).errors,
    ).toEqual([{ path: "max_count", message: "Enter a whole number" }]);
  });

  it("round-trips stored params", () => {
    const nodes = parse("precedence");
    const stored = { pairs: [{ before: "d1", after: "d2" }], min_gap: 30 };
    expect(toParams(nodes, initialValues(nodes, stored))).toEqual({
      params: stored,
      errors: [],
    });
  });
});
