import type { IndustryTemplateDefinition } from "@/api/generated/model";
import { Badge } from "@/components/ui/badge";

const CARD =
  "flex h-full w-full flex-col gap-1 rounded-lg border bg-card p-4 text-left hover:border-primary focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:cursor-not-allowed disabled:border-dashed disabled:bg-muted disabled:hover:border-border";

export function TemplateStep({
  templates,
  onPick,
}: {
  templates: IndustryTemplateDefinition[];
  onPick: (key: string) => void;
}) {
  const hasHealthcare = templates.some((t) => t.key === "healthcare");
  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Choose a template
        </h1>
        <p className="text-muted-foreground">
          A template sets up resource types, time slots and a starting set of
          rules. You can change everything later.
        </p>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2">
        {templates.map((t) => (
          <li key={t.key}>
            <button
              type="button"
              className={CARD}
              onClick={() => onPick(t.key)}
            >
              <span className="font-semibold">{t.name}</span>
              <span className="text-sm text-muted-foreground">
                {t.description}
              </span>
            </button>
          </li>
        ))}
        {!hasHealthcare && (
          <li>
            <button type="button" className={CARD} disabled>
              <span className="flex items-center gap-2 font-semibold">
                Healthcare rostering{" "}
                <Badge variant="secondary">Coming soon</Badge>
              </span>
              <span className="text-sm text-muted-foreground">
                Shifts, wards and fair rotas.
              </span>
            </button>
          </li>
        )}
        <li>
          <button
            type="button"
            className={CARD}
            onClick={() => onPick("blank")}
          >
            <span className="font-semibold">Start blank</span>
            <span className="text-sm text-muted-foreground">
              Skip templates and configure everything by hand.
            </span>
          </button>
        </li>
      </ul>
    </section>
  );
}
