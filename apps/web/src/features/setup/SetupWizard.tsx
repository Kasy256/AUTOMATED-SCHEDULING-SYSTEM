import { Check } from "lucide-react";
import { useSearchParams } from "react-router";

import { useListIndustryTemplates } from "@/api/generated/industry-templates/industry-templates";
import { useGetSchedule } from "@/api/generated/schedules/schedules";
import { BrandMark } from "@/components/BrandMark";
import { cn } from "@/lib/utils";

import { FinishStep } from "./FinishStep";
import { ImportStep } from "./ImportStep";
import { ScheduleStep } from "./ScheduleStep";
import { TemplateStep } from "./TemplateStep";
import { wizardStep } from "./wizardState";

const STEPS = [
  "Choose a template",
  "Create your schedule",
  "Import your data",
  "Check & finish",
];

export function SetupWizard() {
  const [params, setParams] = useSearchParams();
  const step = wizardStep(params);
  const templateKey = params.get("template");
  const scheduleId = params.get("schedule");
  const { data: templates = [], isPending: templatesLoading } =
    useListIndustryTemplates();
  const { data: schedule } = useGetSchedule(scheduleId ?? "", {
    query: { enabled: scheduleId !== null },
  });
  const template = templates.find((t) => t.key === templateKey);

  const go = (next: Record<string, string>) =>
    setParams({ ...Object.fromEntries(params), ...next });
  const done: (string | null)[] = [
    templateKey === "blank" ? "Start blank" : (template?.name ?? null),
    schedule ? `${schedule.name} · ${schedule.timezone}` : null,
    templateKey === "blank" ? "Skipped" : null,
    null,
  ];

  return (
    <div className="grid min-h-svh md:grid-cols-[18rem_minmax(0,1fr)]">
      <aside className="bg-sidebar p-8 text-sidebar-foreground">
        <BrandMark className="mb-10 text-lg" />
        <ol className="flex flex-col gap-5">
          {STEPS.map((label, i) => {
            const n = i + 1;
            const state = n < step ? "done" : n === step ? "current" : "todo";
            return (
              <li
                key={label}
                aria-current={state === "current" ? "step" : undefined}
                className="flex gap-3"
              >
                <span
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full border border-sidebar-border text-xs",
                    state === "done" &&
                      "border-sidebar-primary bg-sidebar-primary text-sidebar-primary-foreground",
                    state === "current" &&
                      "border-sidebar-primary font-semibold text-sidebar-primary",
                  )}
                >
                  {state === "done" ? (
                    <Check className="size-3.5" aria-hidden />
                  ) : (
                    n
                  )}
                </span>
                <span
                  className={cn(
                    "text-sm",
                    state === "current" &&
                      "font-semibold text-sidebar-accent-foreground",
                  )}
                >
                  {label}
                  {state === "done" && done[i] && (
                    <span className="block text-xs font-normal">{done[i]}</span>
                  )}
                </span>
              </li>
            );
          })}
        </ol>
      </aside>
      <main className="flex justify-center p-6 md:p-10">
        <div className="w-full max-w-3xl">
          {step === 1 && (
            <TemplateStep
              loading={templatesLoading}
              templates={templates}
              onPick={(key) => go({ template: key })}
            />
          )}
          {step === 2 && templateKey && (
            <ScheduleStep
              templateKey={templateKey}
              onCreated={(id) => go({ schedule: id })}
            />
          )}
          {step === 3 && template && scheduleId && (
            <ImportStep
              template={template}
              scheduleId={scheduleId}
              onContinue={() => go({ step: "finish" })}
            />
          )}
          {step === 4 && scheduleId && <FinishStep scheduleId={scheduleId} />}
        </div>
      </main>
    </div>
  );
}
