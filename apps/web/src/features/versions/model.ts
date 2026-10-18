import type {
  SolveRunResponse,
  VersionDiff,
  VersionSummary,
} from "@/api/generated/model";

export type Origin = "Solve" | "Repair" | "Board edit";

export function originOf(
  v: VersionSummary,
  runs: Pick<SolveRunResponse, "id" | "kind">[],
): Origin {
  if (v.parent_version_id) return "Board edit";
  return runs.find((r) => r.id === v.solve_run_id)?.kind === "repair"
    ? "Repair"
    : "Solve";
}

export function compareTargetOf(
  v: VersionSummary,
  all: VersionSummary[],
): VersionSummary | null {
  const published = all.find((x) => x.status === "published");
  if (published && published.id !== v.id) return published;
  const earlier = all
    .filter((x) => x.number < v.number)
    .sort((a, b) => b.number - a.number);
  return earlier[0] ?? null;
}

export function diffSummary(d: VersionDiff) {
  const counts = {
    moved: d.moved.length,
    reassigned: d.reassigned.length,
    added: d.added.length,
    removed: d.removed.length,
  };
  return {
    ...counts,
    total: counts.moved + counts.reassigned + counts.added + counts.removed,
    text: `${String(counts.moved)} moved · ${String(counts.reassigned)} reassigned · ${String(counts.added)} added · ${String(counts.removed)} removed`,
  };
}
