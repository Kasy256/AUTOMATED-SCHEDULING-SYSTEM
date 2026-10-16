export type PredicateOp = "eq" | "ne" | "in" | "gte" | "lte" | "contains";
type Scalar = string | number | boolean;
export interface PredicateValue {
  attr: string;
  op: PredicateOp;
  value: Scalar | Scalar[];
}

const scalar = (text: string): Scalar => {
  const t = text.trim();
  if (t === "true") return true;
  if (t === "false") return false;
  return t !== "" && Number.isFinite(Number(t)) ? Number(t) : t;
};

export function parsePredicateValue(
  op: PredicateOp,
  text: string,
): PredicateValue["value"] {
  return op === "in"
    ? text
        .split(",")
        .map((part) => scalar(part))
        .filter((v) => v !== "")
    : scalar(text);
}

export function formatPredicateValue(value: PredicateValue["value"]): string {
  return Array.isArray(value) ? value.map(String).join(", ") : String(value);
}
