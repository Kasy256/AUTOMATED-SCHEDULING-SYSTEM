import { AlertTriangle } from "lucide-react";

import type { ImportReport } from "@/api/generated/model";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function reportSummary(report: ImportReport): string {
  const parts = [
    `${report.row_count} rows`,
    `${report.created} will be created`,
    `${report.error_count} errors`,
  ];
  if ((report.skipped ?? 0) > 0) parts.push(`${report.skipped ?? 0} skipped`);
  return parts.join(" · ");
}

export function ImportReportView({
  report,
  busy,
  onBack,
  onCommit,
}: {
  report: ImportReport;
  busy: boolean;
  onBack: () => void;
  onCommit: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <p className="font-medium">{reportSummary(report)}</p>
      {report.errors.length > 0 && (
        <div className="max-h-64 overflow-y-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Problem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {report.errors.slice(0, 200).map((e, i) => (
                <TableRow key={i}>
                  <TableCell>{`Row ${e.row}${e.column ? ` · ${e.column}` : ""} · ${e.message}`}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {(report.feasibility ?? []).length > 0 && (
        <ul className="flex flex-col gap-1 text-sm">
          {(report.feasibility ?? []).map((issue, i) => (
            <li key={i} className="flex gap-2">
              <AlertTriangle
                className="mt-0.5 size-4 shrink-0 text-amber-600"
                aria-hidden
              />
              <span>{`Warning: ${issue.message}`}</span>
            </li>
          ))}
        </ul>
      )}
      {!report.valid && (
        <p className="text-sm text-muted-foreground">
          Fix the file or the mapping, then run the dry run again.
        </p>
      )}
      <div className="flex gap-2">
        <Button variant="outline" onClick={onBack} disabled={busy}>
          Change mapping
        </Button>
        <Button onClick={onCommit} disabled={busy || !report.valid}>
          {`Import ${report.created} rows`}
        </Button>
      </div>
    </div>
  );
}
