import { useState, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { WEEKDAYS, formatMinuteOfDay } from "@/lib/time";

import {
  CELL_MINUTES,
  CELLS_PER_DAY,
  paint,
  type Grid,
  type Kind,
} from "./grid";

const KINDS: {
  kind: Kind | null;
  label: string;
  key: string;
  className: string;
}[] = [
  {
    kind: "available",
    label: "Available",
    key: "1",
    className: "bg-teal-200 dark:bg-teal-800",
  },
  {
    kind: "preferred",
    label: "Preferred",
    key: "2",
    className: "bg-teal-600 dark:bg-teal-400",
  },
  {
    kind: "avoided",
    label: "Avoid if possible",
    key: "3",
    className: "bg-amber-200 dark:bg-amber-700",
  },
  {
    kind: "unavailable",
    label: "Unavailable",
    key: "4",
    className:
      "bg-[repeating-linear-gradient(45deg,var(--color-slate-200)_0_3px,var(--color-slate-50)_3px_6px)] dark:bg-[repeating-linear-gradient(45deg,var(--color-slate-700)_0_3px,var(--color-slate-900)_3px_6px)]",
  },
  { kind: null, label: "Clear", key: "0", className: "bg-card" },
];
const style = (kind: Kind | null) =>
  KINDS.find((k) => k.kind === kind)?.className ?? "bg-card";

interface Pos {
  day: number;
  cell: number;
}

export function AvailabilityGrid({
  grid,
  onChange,
  readOnly,
}: {
  grid: Grid;
  onChange: (grid: Grid, touchedDays: Set<number>) => void;
  readOnly: boolean;
}) {
  const [active, setActive] = useState<Kind | null>("available");
  const [fullDay, setFullDay] = useState(false);
  const [focus, setFocus] = useState<Pos>({ day: 0, cell: 18 });
  const [anchor, setAnchor] = useState<Pos | null>(null);
  const [drag, setDrag] = useState<{ from: Pos; to: Pos } | null>(null);
  const firstCell = fullDay ? 0 : 12;
  const lastCell = fullDay ? CELLS_PER_DAY - 1 : 43;

  const apply = (from: Pos, to: Pos) => {
    if (readOnly) return;
    const days = new Set<number>();
    for (
      let d = Math.min(from.day, to.day);
      d <= Math.max(from.day, to.day);
      d++
    )
      days.add(d);
    onChange(paint(grid, from, to, active), days);
  };

  const inSelection = (p: Pos) => {
    const sel = drag ?? (anchor ? { from: anchor, to: focus } : null);
    if (!sel) return false;
    return (
      p.day >= Math.min(sel.from.day, sel.to.day) &&
      p.day <= Math.max(sel.from.day, sel.to.day) &&
      p.cell >= Math.min(sel.from.cell, sel.to.cell) &&
      p.cell <= Math.max(sel.from.cell, sel.to.cell)
    );
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, Pos> = {
      ArrowUp: { day: focus.day, cell: Math.max(firstCell, focus.cell - 1) },
      ArrowDown: { day: focus.day, cell: Math.min(lastCell, focus.cell + 1) },
      ArrowLeft: { day: Math.max(0, focus.day - 1), cell: focus.cell },
      ArrowRight: { day: Math.min(6, focus.day + 1), cell: focus.cell },
    };
    const next = moves[e.key];
    if (next) {
      e.preventDefault();
      if (e.shiftKey) setAnchor((a) => a ?? focus);
      else setAnchor(null);
      setFocus(next);
      document.getElementById(cellId(next))?.focus();
      return;
    }
    const picked = KINDS.find((k) => k.key === e.key);
    if (picked) {
      setActive(picked.kind);
      return;
    }
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      apply(anchor ?? focus, focus);
      setAnchor(null);
    }
  };

  const cellId = (p: Pos) => `avail-${String(p.day)}-${String(p.cell)}`;
  const rows = Array.from(
    { length: lastCell - firstCell + 1 },
    (_, i) => firstCell + i,
  );

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <div
        role="grid"
        aria-label="Weekly availability"
        aria-readonly={readOnly}
        className="grid flex-1 touch-none grid-cols-[3.5rem_repeat(7,minmax(2.25rem,1fr))] gap-px overflow-hidden rounded-lg border bg-border text-xs select-none"
        onKeyDown={onKeyDown}
        onPointerUp={() => {
          if (drag) apply(drag.from, drag.to);
          setDrag(null);
        }}
        onPointerLeave={() => {
          setDrag(null);
        }}
      >
        <div role="row" className="contents">
          <span role="columnheader" className="bg-muted" />
          {WEEKDAYS.map((d) => (
            <span
              role="columnheader"
              key={d}
              className="bg-muted py-1 text-center font-medium tracking-wide uppercase"
            >
              {d}
            </span>
          ))}
        </div>
        {rows.map((cell) => (
          <div role="row" key={cell} className="contents">
            <span
              role="rowheader"
              className="bg-card pr-1 text-right text-muted-foreground tabular-nums"
            >
              {cell % 2 === 0 ? formatMinuteOfDay(cell * CELL_MINUTES) : ""}
            </span>
            {WEEKDAYS.map((dayName, day) => {
              const pos = { day, cell };
              const kind = grid[day]?.[cell] ?? null;
              const label = `${dayName} ${formatMinuteOfDay(cell * CELL_MINUTES)}–${formatMinuteOfDay((cell + 1) * CELL_MINUTES)}: ${kind ?? "not set"}`;
              return (
                <div
                  key={day}
                  id={cellId(pos)}
                  role="gridcell"
                  aria-label={label}
                  aria-selected={inSelection(pos)}
                  tabIndex={focus.day === day && focus.cell === cell ? 0 : -1}
                  className={cn(
                    "h-4 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring",
                    style(kind),
                    inSelection(pos) && "ring-2 ring-ring ring-inset",
                  )}
                  onFocus={() => {
                    setFocus(pos);
                  }}
                  onPointerDown={(e) => {
                    if (readOnly) return;
                    (e.target as HTMLElement).releasePointerCapture(
                      e.pointerId,
                    );
                    setFocus(pos);
                    setDrag({ from: pos, to: pos });
                  }}
                  onPointerEnter={() => {
                    setDrag((d) => (d ? { ...d, to: pos } : d));
                  }}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-3 lg:w-56">
        {!readOnly && (
          <div
            className="flex flex-col gap-1 rounded-lg border bg-card p-3"
            role="toolbar"
            aria-label="Paint with"
          >
            <p className="text-xs font-medium text-muted-foreground uppercase">
              Paint with
            </p>
            {KINDS.map((k) => (
              <button
                key={k.label}
                type="button"
                aria-pressed={active === k.kind}
                onClick={() => {
                  setActive(k.kind);
                }}
                className={cn(
                  "flex items-center gap-2 rounded-md border border-transparent px-2 py-1 text-left text-sm",
                  active === k.kind && "border-primary bg-accent font-medium",
                )}
              >
                <span
                  className={cn("h-3 w-4 rounded-sm border", k.className)}
                  aria-hidden
                />
                {k.label}
                <kbd className="ml-auto text-xs text-muted-foreground">
                  {k.key}
                </kbd>
              </button>
            ))}
          </div>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setFullDay((v) => !v);
          }}
        >
          {fullDay ? "Show 06:00–22:00" : "Show full day"}
        </Button>
        <p className="text-xs text-muted-foreground">
          Empty means always available. Once any Available block exists, only
          Available blocks count. Keyboard: arrows move, Shift+arrows select,
          1–4 or 0 pick, Enter applies.
        </p>
      </div>
    </div>
  );
}
