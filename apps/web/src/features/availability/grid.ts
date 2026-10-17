export type Kind = "available" | "preferred" | "avoided" | "unavailable";
export type Grid = (Kind | null)[][];
export const CELL_MINUTES = 30;
export const CELLS_PER_DAY = 48;

export interface RuleLike {
  id?: string;
  kind: Kind;
  weekday: number;
  start_minute: number;
  end_minute: number;
}

const PRIORITY: Record<Kind, number> = {
  available: 0,
  preferred: 1,
  avoided: 2,
  unavailable: 3,
};

const emptyGrid = (): Grid =>
  Array.from({ length: 7 }, () => Array<Kind | null>(CELLS_PER_DAY).fill(null));

export function rulesToGrid(rules: RuleLike[]): Grid {
  const grid = emptyGrid();
  for (const r of rules) {
    const row = grid[r.weekday];
    if (!row) continue;
    const first = Math.floor(r.start_minute / CELL_MINUTES);
    const last = Math.ceil(r.end_minute / CELL_MINUTES) - 1;
    for (let c = first; c <= last && c < CELLS_PER_DAY; c++) {
      const current = row[c];
      if (current == null || PRIORITY[r.kind] > PRIORITY[current])
        row[c] = r.kind;
    }
  }
  return grid;
}

export function paint(
  grid: Grid,
  from: { day: number; cell: number },
  to: { day: number; cell: number },
  kind: Kind | null,
): Grid {
  const [d0, d1] = [Math.min(from.day, to.day), Math.max(from.day, to.day)];
  const [c0, c1] = [Math.min(from.cell, to.cell), Math.max(from.cell, to.cell)];
  return grid.map((row, d) =>
    d < d0 || d > d1
      ? row
      : row.map((cell, c) => (c < c0 || c > c1 ? cell : kind)),
  );
}

function runs(row: (Kind | null)[], weekday: number): Omit<RuleLike, "id">[] {
  const found: Omit<RuleLike, "id">[] = [];
  let start = 0;
  for (let c = 1; c <= row.length; c++) {
    if (c === row.length || row[c] !== row[start]) {
      const kind = row[start];
      if (kind)
        found.push({
          kind,
          weekday,
          start_minute: start * CELL_MINUTES,
          end_minute: c * CELL_MINUTES,
        });
      start = c;
    }
  }
  return found;
}

export function planSave(
  rules: RuleLike[],
  grid: Grid,
  touchedDays: ReadonlySet<number>,
): { create: Omit<RuleLike, "id">[]; remove: string[] } {
  // In the API, once any `available` rule exists only available windows count, and preferred or
  // avoided windows are not themselves available. A painted preference means "available, with a
  // preference", so the save adds an available layer underneath it.
  const layered = grid.some((row) => row.includes("available"));
  const create: Omit<RuleLike, "id">[] = [];
  const remove: string[] = [];
  for (const day of [...touchedDays].sort((a, b) => a - b)) {
    const row = grid[day] ?? [];
    const target = layered
      ? [
          ...runs(row, day).filter((r) => r.kind !== "available"),
          ...runs(
            row.map((cell) =>
              cell === null || cell === "unavailable" ? null : "available",
            ),
            day,
          ),
        ]
      : runs(row, day);
    const existing = rules.filter((r) => r.weekday === day);
    const same = (a: Omit<RuleLike, "id">, b: RuleLike) =>
      a.kind === b.kind &&
      a.start_minute === b.start_minute &&
      a.end_minute === b.end_minute;
    for (const r of existing)
      if (r.id && !target.some((t) => same(t, r))) remove.push(r.id);
    for (const t of target)
      if (!existing.some((r) => same(t, r))) create.push(t);
  }
  return { create, remove };
}
