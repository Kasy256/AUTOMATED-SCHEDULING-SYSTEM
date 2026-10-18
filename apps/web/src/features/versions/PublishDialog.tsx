import type { VersionSummary } from "@/api/generated/model";

export function PublishButton(_: {
  version: VersionSummary;
  versions: VersionSummary[];
  scheduleId: string;
}) {
  return null;
}

export function ArchiveButton(_: {
  version: VersionSummary;
  scheduleId: string;
}) {
  return null;
}
