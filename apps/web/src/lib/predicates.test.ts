import { formatPredicateValue, parsePredicateValue } from "./predicates";

it("parses predicate values by operator", () => {
  expect(parsePredicateValue("eq", "part-time")).toBe("part-time");
  expect(parsePredicateValue("gte", "30")).toBe(30);
  expect(parsePredicateValue("eq", "true")).toBe(true);
  expect(parsePredicateValue("in", "lab, 2,")).toEqual(["lab", 2]);
  expect(formatPredicateValue(["lab", 2])).toBe("lab, 2");
});
