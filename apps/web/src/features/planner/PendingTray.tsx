import { Button } from "@/components/ui/button";

import type { AssignmentEdit } from "@/api/generated/model";

export function PendingTray({
  changes,
  describe,
  onUndo,
  onDiscard,
  onSave,
  saving,
  error,
}: {
  changes: AssignmentEdit[];
  describe: (c: AssignmentEdit) => string;
  onUndo: () => void;
  onDiscard: () => void;
  onSave: () => void;
  saving: boolean;
  error: string | null;
}) {
  if (changes.length === 0) return null;
  return (
    <div
      role="region"
      aria-label="Unsaved changes"
      className="sticky bottom-4 z-20 mx-auto mt-4 flex max-w-4xl flex-col gap-2 rounded-xl bg-sidebar px-4 py-3 text-sidebar-accent-foreground shadow-xl"
    >
      <div className="flex flex-wrap items-center gap-3">
        <strong>{`${String(changes.length)} unsaved ${changes.length === 1 ? "change" : "changes"}`}</strong>
        <span className="min-w-0 flex-1 truncate text-sm text-sidebar-foreground">
          {changes.map(describe).join(" · ")}
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="text-sidebar-accent-foreground hover:bg-sidebar-accent"
          onClick={onUndo}
        >
          Undo last
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="text-sidebar-accent-foreground hover:bg-sidebar-accent"
          onClick={onDiscard}
        >
          Discard
        </Button>
        <Button size="sm" disabled={saving} onClick={onSave}>
          Save as draft
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}
