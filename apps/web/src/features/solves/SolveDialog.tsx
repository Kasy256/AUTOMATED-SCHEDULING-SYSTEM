import { useState } from "react";
import { useNavigate } from "react-router";

import { requestSolve } from "@/api/generated/solves/solves";
import { FieldError } from "@/components/FieldError";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth/AuthProvider";
import { isApiError } from "@/lib/problem";

export function SolveButton({
  scheduleId,
  variant = "default",
}: {
  scheduleId: string;
  variant?: "default" | "outline";
}) {
  const { can } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [limit, setLimit] = useState("");
  const [seed, setSeed] = useState("0");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!can("config.manage")) return null;

  async function start() {
    setError(null);
    const time = limit.trim() ? Number(limit) : null;
    const seedValue = Number(seed);
    if (time !== null && !(Number.isInteger(time) && time >= 1)) {
      setError(
        "Enter a whole number of seconds, or leave it empty for the default.",
      );
      return;
    }
    if (!(
      Number.isInteger(seedValue) &&
      seedValue >= 0 &&
      seedValue <= 2147483647
    )) {
      setError("The seed must be a whole number from 0 to 2147483647.");
      return;
    }
    setBusy(true);
    try {
      const run = await requestSolve(scheduleId, {
        time_limit_s: time,
        seed: seedValue,
      });
      setOpen(false);
      void navigate(`/schedules/${scheduleId}/solves/${run.id}`);
    } catch (e) {
      setError(
        isApiError(e) && e.status === 429
          ? "Two solves are already running for this organisation; wait for one to finish or cancel it."
          : isApiError(e)
            ? (e.detail ?? e.title)
            : "Could not reach the server. Check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant={variant} onClick={() => setOpen(true)}>
        Solve
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Solve this schedule</DialogTitle>
            <DialogDescription>
              The solver builds a new draft timetable that respects every hard
              rule.
            </DialogDescription>
          </DialogHeader>
          <form
            className="flex flex-col gap-4"
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              void start();
            }}
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="solve-limit">Time limit (seconds)</Label>
              <Input
                id="solve-limit"
                inputMode="numeric"
                placeholder="Server default"
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
              />
            </div>
            <details className="text-sm">
              <summary className="cursor-pointer text-muted-foreground">
                Advanced
              </summary>
              <div className="mt-3 flex flex-col gap-1.5">
                <Label htmlFor="solve-seed">Seed</Label>
                <Input
                  id="solve-seed"
                  inputMode="numeric"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  The same seed gives the same result for the same data.
                </p>
              </div>
            </details>
            <FieldError message={error ?? undefined} />
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={busy}>
                Start solve
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
