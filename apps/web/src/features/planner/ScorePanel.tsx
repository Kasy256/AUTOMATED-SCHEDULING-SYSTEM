import { useListConstraints } from "@/api/generated/constraints/constraints";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useEngineText } from "@/lib/engineText";

interface Term {
  constraint_id: string;
  penalty: number;
  details: string;
}

const num = (v: unknown) => (typeof v === "number" ? v : 0);

// The score is stored as free-form JSON on the version, so read it defensively.
function parseScore(score: unknown) {
  const s = (typeof score === "object" && score !== null ? score : {}) as {
    hard_violations?: unknown;
    soft_total?: unknown;
    terms?: unknown;
  };
  const totals = new Map<string, Term>();
  for (const raw of Array.isArray(s.terms) ? (s.terms as unknown[]) : []) {
    if (typeof raw !== "object" || raw === null) continue;
    const t = raw as {
      constraint_id?: unknown;
      penalty?: unknown;
      details?: unknown;
    };
    if (typeof t.constraint_id !== "string") continue;
    const prev = totals.get(t.constraint_id);
    const details = typeof t.details === "string" ? t.details : "";
    totals.set(t.constraint_id, {
      constraint_id: t.constraint_id,
      penalty: (prev?.penalty ?? 0) + num(t.penalty),
      // Several terms for one rule: their details no longer describe the sum.
      details: prev ? "" : details,
    });
  }
  return {
    hard: num(s.hard_violations),
    soft: num(s.soft_total),
    terms: [...totals.values()]
      .filter((t) => t.penalty > 0)
      .sort((a, b) => b.penalty - a.penalty),
  };
}

export function ScorePanel({
  scheduleId,
  score,
}: {
  scheduleId: string;
  score: unknown;
}) {
  const { data: rules = [] } = useListConstraints(scheduleId);
  const text = useEngineText(scheduleId);
  const names = new Map(rules.map((r) => [r.id, r.name]));
  const { hard, soft, terms } = parseScore(score);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline">Score</Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96">
        <div className="flex flex-col gap-3">
          <div className="flex justify-between text-sm">
            <span className={hard > 0 ? "font-semibold text-destructive" : ""}>
              {`Hard rules broken: ${String(hard)}`}
            </span>
            <span className="font-medium">{`Soft penalty: ${String(soft)}`}</span>
          </div>
          {terms.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No soft penalties — every preference is met.
            </p>
          ) : (
            <ul className="flex max-h-80 flex-col gap-3 overflow-y-auto">
              {terms.map((t) => (
                <li key={t.constraint_id} className="flex flex-col gap-1">
                  <div className="flex items-baseline justify-between gap-2 text-sm">
                    <span className="truncate font-medium">
                      {names.get(t.constraint_id) ?? "A deleted rule"}
                    </span>
                    <span className="tabular-nums">{t.penalty}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{
                        width: `${String(soft > 0 ? Math.min(100, (t.penalty / soft) * 100) : 0)}%`,
                      }}
                    />
                  </div>
                  {t.details && (
                    <p className="text-xs text-muted-foreground">
                      {text(t.details)}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
