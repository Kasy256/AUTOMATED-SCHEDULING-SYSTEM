import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router";
import { toast } from "sonner";

import {
  getListConstraintsQueryKey,
  replaceConstraint,
  useListConstraints,
  useListConstraintTemplates,
} from "@/api/generated/constraints/constraints";
import type {
  ConstraintResponse,
  TemplateResponse,
} from "@/api/generated/model";
import { useListResourceTypes } from "@/api/generated/resources/resources";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/lib/auth/AuthProvider";
import { describeFailure } from "@/lib/conflict";
import { cn } from "@/lib/utils";

import { RuleDrawer } from "./RuleDrawer";
import { useRefOptions } from "./schema-form/RefOptions";
import { describeScope, emptyScope } from "./scope";
import { TemplatePicker } from "./TemplatePicker";

type Drawer = {
  template: TemplateResponse;
  rule: ConstraintResponse | null;
} | null;

export function RulesPage() {
  const { scheduleId = "" } = useParams();
  const { can } = useAuth();
  const canEdit = can("config.manage");
  const queryClient = useQueryClient();
  const { data: templates = [] } = useListConstraintTemplates();
  const { data: rules = [], isPending } = useListConstraints(scheduleId);
  const { data: types = [] } = useListResourceTypes();
  const refs = useRefOptions(scheduleId);
  const [picking, setPicking] = useState(false);
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [toggling, setToggling] = useState<string | null>(null);

  const templateOf = (rule: ConstraintResponse) =>
    templates.find(
      (t) => t.key === rule.template_key && t.version === rule.template_version,
    );
  const nameIn =
    (options: { value: string; label: string }[]) => (id: string) =>
      options.find((o) => o.value === id)?.label ?? "an unknown item";
  const scopeText = (rule: ConstraintResponse) =>
    describeScope(
      { ...emptyScope(), ...rule.scope },
      {
        type: nameIn(types.map((t) => ({ value: t.id, label: t.name }))),
        resource: nameIn(refs.resource),
        demand: nameIn(refs.series),
      },
    );

  async function toggle(rule: ConstraintResponse) {
    setToggling(rule.id);
    try {
      await replaceConstraint(scheduleId, rule.id, {
        name: rule.name,
        template_key: rule.template_key,
        template_version: rule.template_version,
        params: rule.params,
        scope: rule.scope,
        hard: rule.hard,
        weight: rule.weight,
        enabled: !rule.enabled,
      });
      await queryClient.invalidateQueries({
        queryKey: getListConstraintsQueryKey(scheduleId),
      });
    } catch (error) {
      toast.error(describeFailure(error, rule.name));
    } finally {
      setToggling(null);
    }
  }

  const groups: [string, ConstraintResponse[]][] = [
    ["Hard — must never break", rules.filter((r) => r.hard)],
    ["Soft — avoid, weighted", rules.filter((r) => !r.hard)],
  ];

  return (
    <>
      <PageHeader
        title="Rules"
        description="What every timetable must respect, and what it should prefer."
        actions={
          canEdit && <Button onClick={() => setPicking(true)}>Add rule</Button>
        }
      />
      <div className="flex flex-col gap-6 p-6">
        {!isPending && rules.length === 0 && (
          <EmptyState
            title="No rules yet"
            description="Rules come with an industry template, or add your own."
          />
        )}
        {rules.length > 0 &&
          groups.map(([label, items]) => (
            <section
              key={label}
              aria-label={label}
              className="flex flex-col gap-2"
            >
              <h2 className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
                {`${label} · ${items.length}`}
              </h2>
              <ul className="flex flex-col gap-2">
                {items.map((rule) => {
                  const template = templateOf(rule);
                  return (
                    <li
                      key={rule.id}
                      className={cn(
                        "flex items-center gap-3 rounded-lg border bg-card p-3",
                        !rule.enabled && "opacity-60",
                      )}
                    >
                      <button
                        type="button"
                        aria-label={rule.name}
                        aria-describedby={`rule-${rule.id}-summary`}
                        disabled={!template}
                        className="flex min-w-0 flex-1 flex-col text-left focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                        onClick={() =>
                          template && setDrawer({ template, rule })
                        }
                      >
                        <span className="truncate font-medium">
                          {rule.name}
                        </span>
                        <span
                          id={`rule-${rule.id}-summary`}
                          className="truncate text-sm text-muted-foreground"
                        >
                          {rule.summary}
                        </span>
                      </button>
                      <Badge
                        variant="secondary"
                        className="hidden max-w-60 truncate sm:inline-flex"
                      >
                        {scopeText(rule)}
                      </Badge>
                      {!rule.hard && (
                        <span className="text-xs font-medium text-primary">{`weight ${rule.weight}`}</span>
                      )}
                      <Switch
                        checked={rule.enabled}
                        disabled={!canEdit || toggling === rule.id}
                        aria-label={`Enabled: ${rule.name}`}
                        onCheckedChange={() => void toggle(rule)}
                      />
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
      </div>
      <TemplatePicker
        templates={templates}
        open={picking}
        onOpenChange={setPicking}
        onPick={(template) => {
          setPicking(false);
          setDrawer({ template, rule: null });
        }}
      />
      {drawer && (
        <RuleDrawer
          key={drawer.rule?.id ?? drawer.template.key}
          scheduleId={scheduleId}
          template={drawer.template}
          rule={drawer.rule}
          readOnly={!canEdit}
          open
          onOpenChange={(open) => {
            if (!open) setDrawer(null);
          }}
        />
      )}
    </>
  );
}
