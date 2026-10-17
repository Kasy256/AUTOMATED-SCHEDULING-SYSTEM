import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { getGetSolveQueryKey, getSolve } from "@/api/generated/solves/solves";
import { streamSse } from "@/lib/sse";

export interface Progress {
  status: string;
  kind?: string;
  objective?: number | null;
  best_bound?: number | null;
  solutions?: number;
  wall_time_s?: number;
}

export const TERMINAL = new Set([
  "succeeded",
  "infeasible",
  "no_solution",
  "cancelled",
  "failed",
  "failed_verification",
]);

export function useSolveStream(
  runId: string,
  pollMs = 3000,
): { progress: Progress | null; done: boolean } {
  const queryClient = useQueryClient();
  const [progress, setProgress] = useState<Progress | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let finished = false;
    const finish = () => {
      finished = true;
      setDone(true);
      // Versions/runs are listed elsewhere; a finished run changes both.
      void queryClient.invalidateQueries({
        queryKey: getGetSolveQueryKey(runId),
      });
      void queryClient.invalidateQueries({
        predicate: (q) =>
          String(q.queryKey[0]).includes("/solves") ||
          String(q.queryKey[0]).includes("/versions"),
      });
    };
    const poll = async () => {
      if (abort.signal.aborted) return;
      try {
        const run = await getSolve(runId);
        setProgress({
          status: run.status,
          ...(run.progress as Omit<Progress, "status">),
        });
        if (TERMINAL.has(run.status)) {
          finish();
          return;
        }
      } catch {
        // keep polling through transient errors
      }
      timer = setTimeout(() => void poll(), pollMs);
    };
    streamSse(
      `/api/v1/solves/${runId}/events`,
      (e) => {
        const data = JSON.parse(e.data) as Progress;
        if (e.event === "progress") setProgress(data);
        if (e.event === "done") finish();
      },
      abort.signal,
    )
      // A stream that ends without "done" (server error, proxy close) is as good as a failure.
      .then(
        () => {
          if (!finished && !abort.signal.aborted) void poll();
        },
        () => {
          if (!abort.signal.aborted) void poll();
        },
      );
    return () => {
      abort.abort();
      if (timer) clearTimeout(timer);
    };
  }, [runId, pollMs, queryClient]);

  return { progress, done };
}
