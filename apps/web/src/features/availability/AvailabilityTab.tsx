import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import {
  createAvailabilityRule,
  deleteAvailabilityRule,
  getListAvailabilityRulesQueryKey,
  useListAvailabilityRules,
} from "@/api/generated/resources/resources";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { describeFailure } from "@/lib/conflict";

import { AvailabilityGrid } from "./AvailabilityGrid";
import { planSave, rulesToGrid, type Grid } from "./grid";

export function AvailabilityTab({
  resourceId,
  canEdit,
}: {
  resourceId: string;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();
  const { data: rules = [], isPending } = useListAvailabilityRules(resourceId);
  const [draft, setDraft] = useState<{
    grid: Grid;
    touched: Set<number>;
  } | null>(null);
  const [saving, setSaving] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  if (isPending)
    return (
      <div role="status" className="py-8 text-muted-foreground">
        Loading…
      </div>
    );
  const grid = draft?.grid ?? rulesToGrid(rules);

  async function save() {
    if (!draft) return;
    setSaving(true);
    setFailure(null);
    const plan = planSave(rules, draft.grid, draft.touched);
    try {
      for (const id of plan.remove)
        await deleteAvailabilityRule(resourceId, id);
      for (const rule of plan.create)
        await createAvailabilityRule(resourceId, rule);
      toast.success("Availability saved");
      setDraft(null);
    } catch (error) {
      setFailure(
        `Some changes were not saved: ${describeFailure(error, "This availability rule")}`,
      );
      setDraft(null);
    } finally {
      await queryClient.invalidateQueries({
        queryKey: getListAvailabilityRulesQueryKey(resourceId),
      });
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 pt-2">
      {failure && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{failure}</AlertDescription>
        </Alert>
      )}
      <AvailabilityGrid
        grid={grid}
        readOnly={!canEdit || saving}
        onChange={(next, days) => {
          setDraft({
            grid: next,
            touched: new Set([...(draft?.touched ?? []), ...days]),
          });
        }}
      />
      {canEdit && (
        <div className="flex gap-2">
          <Button disabled={!draft || saving} onClick={() => void save()}>
            Save availability
          </Button>
          <Button
            variant="outline"
            disabled={!draft || saving}
            onClick={() => {
              setDraft(null);
            }}
          >
            Discard changes
          </Button>
        </div>
      )}
    </div>
  );
}
