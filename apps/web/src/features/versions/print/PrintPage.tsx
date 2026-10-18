import { Link, useParams, useSearchParams } from "react-router";

import {
  useListResources,
  useListResourceTypes,
} from "@/api/generated/resources/resources";
import {
  useGetSchedule,
  useListSlotTemplates,
} from "@/api/generated/schedules/schedules";
import { useGetVersion } from "@/api/generated/versions/versions";
import { NativeSelect } from "@/components/NativeSelect";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

import { buildSheets } from "./sheets";

export function PrintPage() {
  const { scheduleId = "", versionId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { data: schedule } = useGetSchedule(scheduleId);
  const { data: version } = useGetVersion(versionId);
  const { data: types = [] } = useListResourceTypes();
  const { data: resources = [] } = useListResources();
  const { data: templates = [] } = useListSlotTemplates(scheduleId);

  if (!schedule || !version)
    return (
      <div role="status" className="p-8 text-muted-foreground">
        Loading…
      </div>
    );

  const typeId =
    params.get("type") ??
    types.find((t) => resources.some((r) => r.resource_type_id === t.id))?.id ??
    "";
  const codes = new Map(resources.map((r) => [r.id, r.code]));
  const { sheets, idle } = buildSheets({
    resources: resources.filter((r) => r.resource_type_id === typeId),
    assignments: version.assignments,
    timeZone: schedule.timezone,
    slots: templates.flatMap((t) => t.definition.slots),
    codeOf: (id) => codes.get(id) ?? "?",
  });
  const versionText = `Version ${String(version.number)} (${version.status})`;

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 bg-background p-6 text-foreground print:max-w-none print:p-0">
      <div className="flex flex-wrap items-end gap-3 print:hidden">
        <Button asChild variant="ghost">
          <Link to={`/schedules/${scheduleId}/versions`}>Back to versions</Link>
        </Button>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="print-type">Resource type</Label>
          <NativeSelect
            id="print-type"
            value={typeId}
            onChange={(e) => setParams({ type: e.target.value })}
          >
            {types.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </NativeSelect>
        </div>
        <Button className="ml-auto" onClick={() => window.print()}>
          Print
        </Button>
      </div>
      {sheets.map((sheet) => (
        <section key={sheet.key} className="sheet flex flex-col gap-2">
          <h2 className="text-lg font-semibold">{sheet.title}</h2>
          <p className="text-sm text-muted-foreground">
            {`${schedule.name} · ${sheet.week} · ${versionText}`}
          </p>
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">{`Timetable for ${sheet.title}, ${sheet.week}`}</caption>
            <thead>
              <tr>
                <td className="border p-2" />
                {sheet.days.map((d) => (
                  <th
                    key={d.weekday}
                    scope="col"
                    className="border bg-muted p-2 text-left font-semibold"
                  >
                    {d.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sheet.rows.map((row) => (
                <tr key={row.minute}>
                  <th
                    scope="row"
                    className="border bg-muted p-2 text-left font-semibold whitespace-nowrap"
                  >
                    {row.label}
                  </th>
                  {sheet.days.map((d) => (
                    <td key={d.weekday} className="border p-2 align-top">
                      {(
                        sheet.cells.get(
                          `${String(d.weekday)}|${String(row.minute)}`,
                        ) ?? []
                      ).map((cell, i) => (
                        <div key={i}>
                          <div className="font-medium">{cell.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {cell.others}
                          </div>
                        </div>
                      ))}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      {idle.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {`Nothing scheduled: ${idle.join(", ")}`}
        </p>
      )}
    </main>
  );
}
