import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import {
  createCalendarFeed,
  createMyCalendarFeed,
  getListCalendarFeedsQueryKey,
  getListMyCalendarFeedsQueryKey,
  revokeCalendarFeed,
  useListCalendarFeeds,
  useListMyCalendarFeeds,
} from "@/api/generated/calendar-feeds/calendar-feeds";
import type { FeedOut } from "@/api/generated/model";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { describeFailure } from "@/lib/conflict";
import { isApiError } from "@/lib/problem";
import { browserTimezone, formatInZone } from "@/lib/time";

function useFeeds(resourceId: string | undefined) {
  const own = useListMyCalendarFeeds({ query: { enabled: !resourceId } });
  const theirs = useListCalendarFeeds(resourceId ?? "", {
    query: { enabled: resourceId !== undefined },
  });
  return resourceId ? theirs : own;
}

export function CalendarLinks({ resourceId }: { resourceId?: string }) {
  const queryClient = useQueryClient();
  const { data: feeds = [], error } = useFeeds(resourceId);
  // A created link exists only here: the server keeps a hash, so it can't be shown again.
  const [created, setCreated] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revoking, setRevoking] = useState<FeedOut | null>(null);
  const zone = browserTimezone();
  const queryKey = resourceId
    ? getListCalendarFeedsQueryKey(resourceId)
    : getListMyCalendarFeedsQueryKey();

  async function create() {
    setBusy(true);
    try {
      const feed = resourceId
        ? await createCalendarFeed(resourceId)
        : await createMyCalendarFeed();
      setCreated(feed.url);
      await queryClient.invalidateQueries({ queryKey });
    } catch (e) {
      toast.error(describeFailure(e, "This calendar link"));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(feed: FeedOut) {
    try {
      await revokeCalendarFeed(feed.id);
      setRevoking(null);
      await queryClient.invalidateQueries({ queryKey });
    } catch (e) {
      toast.error(describeFailure(e, "This calendar link"));
    }
  }

  async function copy(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link copied");
    } catch {
      document.getElementById("calendar-link")?.focus();
      (
        document.getElementById("calendar-link") as HTMLInputElement | null
      )?.select();
      toast("Press Ctrl+C to copy");
    }
  }

  if (isApiError(error) && error.status === 404 && !resourceId)
    return (
      <section className="flex flex-col gap-2 rounded-xl border bg-card p-5 shadow-sm">
        <h2 className="text-sm font-semibold">Calendar link</h2>
        <p className="text-sm text-muted-foreground">
          Your account isn't linked to anyone on a timetable yet. Ask an
          organisation admin to link it.
        </p>
      </section>
    );

  const sorted = [...feeds].sort((a, b) =>
    b.created_at.localeCompare(a.created_at),
  );
  return (
    <section className="flex flex-col gap-3 rounded-xl border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-semibold">Calendar link</h2>
        <Button
          className="ml-auto"
          variant="outline"
          size="sm"
          disabled={busy}
          onClick={() => void create()}
        >
          Create calendar link
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">
        Subscribe to this timetable in Google Calendar, Outlook or Apple
        Calendar.
      </p>
      {created && (
        <div className="flex flex-col gap-2 rounded-lg border border-primary/40 bg-primary/5 p-3">
          <div className="flex gap-2">
            <Input
              id="calendar-link"
              aria-label="Calendar link"
              readOnly
              value={created}
              onFocus={(e) => e.target.select()}
            />
            <Button size="sm" onClick={() => void copy(created)}>
              Copy
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Anyone with this link can see this calendar. You won't see it again
            — create a new one if you lose it.
          </p>
        </div>
      )}
      {sorted.length > 0 && (
        <ul className="flex flex-col divide-y text-sm">
          {sorted.map((feed) => (
            <li
              key={feed.id}
              className={
                feed.revoked_at
                  ? "flex items-center gap-3 py-2 text-muted-foreground"
                  : "flex items-center gap-3 py-2"
              }
            >
              <span className="flex-1">
                {`Created ${formatInZone(feed.created_at, zone)}`}
              </span>
              {feed.revoked_at ? (
                <span>{`Revoked ${formatInZone(feed.revoked_at, zone)}`}</span>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setRevoking(feed)}
                >
                  Revoke
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={revoking !== null}
        onOpenChange={(open) => {
          if (!open) setRevoking(null);
        }}
        title="Revoke this link?"
        description="Calendars using it stop updating."
        confirmLabel="Revoke"
        destructive
        onConfirm={() => {
          if (revoking) void revoke(revoking);
        }}
      />
    </section>
  );
}
