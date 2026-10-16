import type { TemplateResponse } from "@/api/generated/model";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

// The fairness template needs the fairness ledger, which arrives with the Healthcare template.
const NOT_YET: Record<string, string> = {
  fairness: "Available with the Healthcare template",
};

export function TemplatePicker({
  templates,
  open,
  onOpenChange,
  onPick,
}: {
  templates: TemplateResponse[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (template: TemplateResponse) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Add a rule</DialogTitle>
          <DialogDescription>
            Pick the kind of rule; you set its details next.
          </DialogDescription>
        </DialogHeader>
        <ul className="grid gap-2 sm:grid-cols-2">
          {templates.map((t) => {
            const unavailable = NOT_YET[t.key];
            return (
              <li key={t.key}>
                <button
                  type="button"
                  disabled={unavailable !== undefined}
                  onClick={() => onPick(t)}
                  className="flex h-full w-full flex-col gap-1 rounded-lg border bg-card p-3 text-left hover:border-primary focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <span className="flex items-center gap-2 font-medium">
                    {t.title}
                    {t.soft_only && (
                      <Badge variant="secondary">Soft only</Badge>
                    )}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {unavailable ?? t.description}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
