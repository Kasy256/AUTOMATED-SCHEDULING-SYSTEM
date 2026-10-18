import { useState, type ReactNode } from "react";
import { useParams, useSearchParams } from "react-router";

import { useListActivities } from "@/api/generated/activities/activities";
import {
  useListResources,
  useListResourceTypes,
} from "@/api/generated/resources/resources";
import {
  useListVersions,
  useVersionReport,
} from "@/api/generated/versions/versions";
import { EmptyState } from "@/components/EmptyState";
import { NativeSelect } from "@/components/NativeSelect";
import { PageHeader } from "@/components/PageHeader";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { versionLabel } from "@/features/planner/labels";
import { WEEKDAYS } from "@/lib/time";

const MISSING = "an item that no longer exists";
const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

const hours = (minutes: number) => `${(minutes / 60).toFixed(1)} h`;

function dayLabel(date: string) {
  const weekday = (new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7;
  return `${WEEKDAYS[weekday] ?? ""} ${String(Number(date.slice(8, 10)))} ${MONTHS[Number(date.slice(5, 7)) - 1] ?? ""}`;
}

function Bar({ value }: { value: number }) {
  return (
    <div role="presentation" className="h-1.5 w-24 rounded-full bg-muted">
      <div
        className="h-full rounded-full bg-primary"
        style={{ width: `${String(Math.min(100, Math.round(value * 100)))}%` }}
      />
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export function ReportsPage() {
  const { scheduleId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { data: versions = [], isPending } = useListVersions(scheduleId);
  const { data: resources = [] } = useListResources();
  const { data: types = [] } = useListResourceTypes();
  const { data: activities = [] } = useListActivities(scheduleId);
  const [typeKey, setTypeKey] = useState("");
  const [ascending, setAscending] = useState(false);

  const newest = [...versions].sort((a, b) => b.number - a.number);
  const fallback =
    newest.find((v) => v.status === "published") ??
    newest.find((v) => v.status === "draft");
  const versionId = params.get("version") ?? fallback?.id ?? "";
  const { data: report } = useVersionReport(versionId, {
    query: { enabled: versionId !== "" },
  });

  const byId = new Map(resources.map((r) => [r.id, r]));
  const nameOf = (id: string) => {
    const r = byId.get(id);
    return r ? `${r.name} (${r.code})` : MISSING;
  };
  const typeName = (key: string) =>
    types.find((t) => t.key === key)?.name ?? key;
  const activityName = (id: string) =>
    activities.find((a) => a.id === id)?.name ?? MISSING;

  if (isPending) return <TableSkeleton label="Loading reports" />;
  if (versions.length === 0)
    return (
      <>
        <PageHeader title="Reports" />
        <div className="px-4 py-6 sm:px-6 lg:px-8">
          <EmptyState
            title="No versions yet"
            description="Solve the schedule to see how its timetable uses people and spaces."
          />
        </div>
      </>
    );

  const utilisation = (report?.utilisation ?? [])
    .filter((u) => !typeKey || u.type_key === typeKey)
    .sort((a, b) => (ascending ? a.ratio - b.ratio : b.ratio - a.ratio));
  const typeKeys = [
    ...new Set((report?.utilisation ?? []).map((u) => u.type_key)),
  ];

  return (
    <>
      <PageHeader
        title="Reports"
        description="How the chosen version uses people and spaces."
        actions={
          <NativeSelect
            aria-label="Version"
            value={versionId}
            onChange={(e) => setParams({ version: e.target.value })}
          >
            {newest.map((v) => (
              <option key={v.id} value={v.id}>
                {versionLabel(v)}
              </option>
            ))}
          </NativeSelect>
        }
      />
      <div className="flex flex-col gap-8 px-4 py-6 sm:px-6 lg:px-8">
        {!report ? (
          <TableSkeleton label="Loading the report" />
        ) : (
          <>
            <Section title="Utilisation">
              <div className="flex max-w-xs flex-col gap-1.5">
                <Label htmlFor="report-type">Resource type</Label>
                <NativeSelect
                  id="report-type"
                  value={typeKey}
                  onChange={(e) => setTypeKey(e.target.value)}
                >
                  <option value="">All types</option>
                  {typeKeys.map((k) => (
                    <option key={k} value={k}>
                      {typeName(k)}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
                <Table aria-label="Utilisation">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Resource</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead className="text-right">Assigned</TableHead>
                      <TableHead className="text-right">Available</TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setAscending((a) => !a)}
                        >
                          Used
                        </Button>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {utilisation.map((u) => (
                      <TableRow key={u.resource_id}>
                        <TableCell>{nameOf(u.resource_id)}</TableCell>
                        <TableCell>{typeName(u.type_key)}</TableCell>
                        <TableCell className="text-right tabular-nums">
                          {hours(u.assigned_minutes)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {hours(u.available_minutes)}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Bar value={u.ratio} />
                            <span className="tabular-nums">{`${String(Math.round(u.ratio * 100))}%`}</span>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </Section>

            <Section title="Load per person">
              <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
                <Table aria-label="Load per person">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Person</TableHead>
                      <TableHead className="text-right">Activities</TableHead>
                      <TableHead className="text-right">Hours</TableHead>
                      <TableHead>Busiest day</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {[...report.load]
                      .sort((a, b) => b.minutes - a.minutes)
                      .map((l) => (
                        <TableRow key={l.resource_id}>
                          <TableCell>{nameOf(l.resource_id)}</TableCell>
                          <TableCell className="text-right tabular-nums">
                            {l.activities}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {hours(l.minutes)}
                          </TableCell>
                          <TableCell>
                            {l.busiest_day
                              ? `${dayLabel(l.busiest_day)} · ${hours(l.busiest_day_minutes)}`
                              : "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </div>
            </Section>

            <Section title="Coverage gaps">
              {report.coverage_gaps.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No gaps — every requirement is met
                </p>
              ) : (
                <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
                  <Table aria-label="Coverage gaps">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Activity</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead className="text-right">Required</TableHead>
                        <TableHead className="text-right">Assigned</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {report.coverage_gaps.map((g) => (
                        <TableRow key={`${g.activity_id}|${g.role}`}>
                          <TableCell>{activityName(g.activity_id)}</TableCell>
                          <TableCell>{g.role}</TableCell>
                          <TableCell className="text-right tabular-nums">
                            {g.required_min}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {g.assigned}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </Section>

            <Section title="Fairness spread">
              <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
                <Table aria-label="Fairness spread">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead className="text-right">Resources</TableHead>
                      <TableHead className="text-right">Min</TableHead>
                      <TableHead className="text-right">Mean</TableHead>
                      <TableHead className="text-right">Max</TableHead>
                      <TableHead className="text-right">Spread</TableHead>
                      <TableHead>
                        <span className="sr-only">Range</span>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {report.fairness.map((f) => (
                      <TableRow key={f.type_key}>
                        <TableCell>{typeName(f.type_key)}</TableCell>
                        <TableCell className="text-right tabular-nums">
                          {f.resources}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {hours(f.min_minutes)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {hours(f.mean_minutes)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {hours(f.max_minutes)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {hours(f.spread)}
                        </TableCell>
                        <TableCell>
                          <Bar
                            value={f.max_minutes ? f.spread / f.max_minutes : 0}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </Section>
          </>
        )}
      </div>
    </>
  );
}
