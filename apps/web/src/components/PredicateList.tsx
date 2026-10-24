import { Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  formatPredicateValue,
  parsePredicateValue,
  type PredicateOp,
  type PredicateValue,
} from "@/lib/predicates";
import { NativeSelect } from "@/components/NativeSelect";

const OPS: { op: PredicateOp; label: string }[] = [
  { op: "eq", label: "is" },
  { op: "ne", label: "is not" },
  { op: "in", label: "is one of" },
  { op: "gte", label: "at least" },
  { op: "lte", label: "at most" },
  { op: "contains", label: "contains" },
];

function Row({
  id,
  index,
  value,
  disabled,
  onChange,
  onRemove,
}: {
  id: string;
  index: number;
  value: PredicateValue;
  disabled: boolean;
  onChange: (next: PredicateValue) => void;
  onRemove: () => void;
}) {
  // The raw text is kept so typing "1," for a list isn't reformatted mid-keystroke.
  const [text, setText] = useState(formatPredicateValue(value.value));
  const n = index + 1;
  return (
    <div className="grid grid-cols-[1fr_9rem_1fr_auto] items-end gap-2">
      <div className="flex flex-col gap-1">
        <Label htmlFor={`${id}-attr`}>{`Condition ${n} attribute`}</Label>
        <Input
          id={`${id}-attr`}
          disabled={disabled}
          value={value.attr}
          onChange={(e) => onChange({ ...value, attr: e.target.value })}
        />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor={`${id}-op`}>{`Condition ${n} operator`}</Label>
        <NativeSelect
          id={`${id}-op`}
          disabled={disabled}
          value={value.op}
          onChange={(e) => {
            const op = e.target.value as PredicateOp;
            onChange({ ...value, op, value: parsePredicateValue(op, text) });
          }}
        >
          {OPS.map((o) => (
            <option key={o.op} value={o.op}>
              {o.label}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor={`${id}-value`}>{`Condition ${n} value`}</Label>
        <Input
          id={`${id}-value`}
          disabled={disabled}
          value={text}
          placeholder={value.op === "in" ? "a, b, c" : ""}
          onChange={(e) => {
            setText(e.target.value);
            onChange({
              ...value,
              value: parsePredicateValue(value.op, e.target.value),
            });
          }}
        />
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        disabled={disabled}
        aria-label={`Remove condition ${n}`}
        onClick={onRemove}
      >
        <Trash2 className="size-4" aria-hidden />
      </Button>
    </div>
  );
}

export function PredicateList({
  idPrefix,
  value,
  onChange,
  disabled = false,
}: {
  idPrefix: string;
  value: PredicateValue[];
  onChange: (next: PredicateValue[]) => void;
  disabled?: boolean;
}) {
  // Stable row keys: each row keeps its own text state, so keys must follow rows when one is removed.
  const [keys, setKeys] = useState(() => value.map((_, i) => i));
  if (keys.length !== value.length) {
    // The list changed from outside (a form reset); start fresh keys.
    const base = Math.max(-1, ...keys) + 1;
    setKeys(value.map((_, i) => base + i));
  }

  return (
    <div className="flex flex-col gap-2">
      {value.map((p, i) => (
        <Row
          key={keys[i] ?? i}
          id={`${idPrefix}-${i}`}
          index={i}
          value={p}
          disabled={disabled}
          onChange={(row) => onChange(value.map((v, j) => (j === i ? row : v)))}
          onRemove={() => {
            setKeys(keys.filter((_, j) => j !== i));
            onChange(value.filter((_, j) => j !== i));
          }}
        />
      ))}
      {!disabled && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start"
          onClick={() => {
            setKeys([...keys, Math.max(0, ...keys) + 1]);
            onChange([...value, { attr: "", op: "eq", value: "" }]);
          }}
        >
          Add condition
        </Button>
      )}
    </div>
  );
}
