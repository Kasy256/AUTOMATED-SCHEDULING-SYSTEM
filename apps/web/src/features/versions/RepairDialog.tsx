import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";

import { requestRepair } from "@/api/generated/solves/solves";
import { FieldError } from "@/components/FieldError";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { isApiError } from "@/lib/problem";
import { localInputNow, toUtcIso } from "@/lib/time";

export function RepairButton({
  scheduleId,
  timeZone,
}: {
  scheduleId: string;
  timeZone: string;
}) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [keepBefore, setKeepBefore] = useState("");
  const [limit, setLimit] = useState("");
  const [seed, setSeed] = useState("0");
  const [busy, setBusy] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<ReactNode>(null);

  function show() {
    setKeepBefore(localInputNow(timeZone));
    setFieldError(null);
    setError(null);
    setOpen(true);
  }

  async function start() {
    setFieldError(null);
    setError(null);
    const time = limit.trim() ? Number(limit) : null;
    const seedValue = Number(seed);
    if (!keepBefore) {
      setFieldError("Choose a date and time.");
      return;
    }
    if (time !== null && !(Number.isInteger(time) && time >= 1)) {
      setError(
        "Enter a whole number of seconds, or leave it empty for the default.",
      );
      return;
    }
    if (!(Number.isInteger(seedValue) && seedValue >= 0)) {
      setError("The seed must be a whole number of 0 or more.");
      return;
    }
    setBusy(true);
    try {
      const run = await requestRepair(scheduleId, {
        freeze_before: toUtcIso(keepBefore, timeZone),
        time_limit_s: time,
        seed: seedValue,
      });
      setOpen(false);
      void navigate(`/schedules/${scheduleId}/solves/${run.id}`);
    } catch (e) {
      if (!isApiError(e))
        setError(
          "Could not reach the server. Check your connection and try again.",
        );
      else if (e.status === 422) {
        const messages = e.fieldErrors.map((f) => f.message);
        const onField = e.fieldErrors.find(
          (f) => f.path[0] === "freeze_before",
        );
        if (messages.some((m) => m.includes("stability")))
          setError(
            <>
              Repair needs a Stability rule — add one in Rules.{" "}
              <Link
                className="font-medium underline"
                to={`/schedules/${scheduleId}/rules`}
              >
                Open Rules
              </Link>
            </>,
          );
        else if (onField) setFieldError(onField.message);
        else setError(messages.join(" ") || (e.detail ?? e.title));
      } else if (e.status === 409)
        setError("There is no published timetable to repair yet.");
      else if (e.status === 429)
        setError(
          "Two solves are already running for this organisation; wait for one to finish or cancel it.",
        );
      else setError(e.detail ?? e.title);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="outline" onClick={show}>
        Repair published timetable
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Repair published timetable</DialogTitle>
            <DialogDescription>
              Re-solve with as few changes as possible. Everything before the
              time below stays exactly as published.
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
              <Label htmlFor="repair-keep">Keep everything before</Label>
              <Input
                id="repair-keep"
                type="datetime-local"
                value={keepBefore}
                aria-invalid={fieldError !== null}
                onChange={(e) => setKeepBefore(e.target.value)}
              />
              <FieldError message={fieldError ?? undefined} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="repair-limit">Time limit (seconds)</Label>
              <Input
                id="repair-limit"
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
                <Label htmlFor="repair-seed">Seed</Label>
                <Input
                  id="repair-seed"
                  inputMode="numeric"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                />
              </div>
            </details>
            {error && (
              <Alert variant="destructive" role="alert">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={busy}>
                Start repair
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
