import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import type { ReactNode } from "react";

import type {
  ResourceTypeResponse,
  VersionSummary,
} from "@/api/generated/model";
import { NativeSelect } from "@/components/NativeSelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { BOARD_ID, versionLabel } from "./labels";

export function BoardToolbar({
  types,
  typeId,
  onType,
  query,
  onQuery,
  weekLabel,
  onPrevWeek,
  onNextWeek,
  versions,
  versionId,
  onVersion,
  actions,
}: {
  types: ResourceTypeResponse[];
  typeId: string;
  onType: (id: string) => void;
  query: string;
  onQuery: (q: string) => void;
  weekLabel: string;
  onPrevWeek: (() => void) | null;
  onNextWeek: (() => void) | null;
  versions: VersionSummary[];
  versionId: string;
  onVersion: (id: string) => void;
  actions?: ReactNode;
}) {
  const sorted = [...versions].sort((a, b) => b.number - a.number);
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Tabs value={typeId} onValueChange={onType}>
        <TabsList>
          {types.map((t) => (
            <TabsTrigger key={t.id} value={t.id} aria-controls={BOARD_ID}>
              {t.name}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <div className="relative">
        <Search
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          aria-label="Filter rows"
          placeholder="Filter rows"
          className="w-48 pl-8"
          value={query}
          onChange={(e) => onQuery(e.target.value)}
        />
      </div>
      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="icon"
          aria-label="Previous week"
          disabled={!onPrevWeek}
          onClick={() => onPrevWeek?.()}
        >
          <ChevronLeft />
        </Button>
        <span className="min-w-36 text-center text-sm font-medium">
          {weekLabel}
        </span>
        <Button
          variant="outline"
          size="icon"
          aria-label="Next week"
          disabled={!onNextWeek}
          onClick={() => onNextWeek?.()}
        >
          <ChevronRight />
        </Button>
      </div>
      <div className="ml-auto flex items-center gap-2">
        {sorted.length > 0 && (
          <NativeSelect
            aria-label="Version"
            value={versionId}
            onChange={(e) => onVersion(e.target.value)}
          >
            {sorted.map((v) => (
              <option key={v.id} value={v.id}>
                {versionLabel(v)}
              </option>
            ))}
          </NativeSelect>
        )}
        {actions}
      </div>
    </div>
  );
}
