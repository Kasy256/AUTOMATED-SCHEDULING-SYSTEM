import { Pin } from "lucide-react";

import { cn } from "@/lib/utils";

import type { BoardItem } from "./model/items";

export function BoardItemView({
  item,
  rowId,
  codeOf,
  draggable,
  onOpen,
}: {
  item: BoardItem;
  rowId: string;
  codeOf: (id: string) => string;
  draggable: boolean;
  onOpen: (item: BoardItem, rowId: string) => void;
}) {
  const codes = Object.values(item.resources)
    .flat()
    .filter((id) => id !== rowId)
    .map(codeOf)
    .join(" · ");
  return (
    <button
      type="button"
      tabIndex={-1}
      data-activity={item.activityId}
      aria-label={codes ? `${item.name}, ${codes}` : item.name}
      onClick={() => onOpen(item, rowId)}
      className={cn(
        "flex h-full w-full flex-col overflow-hidden rounded-md bg-primary px-2 py-1 text-left text-primary-foreground shadow-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        item.pending &&
          "outline-2 outline-offset-1 outline-dashed outline-foreground",
        draggable ? "cursor-grab" : "cursor-pointer",
      )}
    >
      <span className="flex items-center gap-1 truncate text-xs font-semibold">
        {item.name}
        {item.pinned && <Pin className="size-3 shrink-0" aria-label="pinned" />}
      </span>
      <span className="truncate text-[11px] opacity-90">{codes}</span>
    </button>
  );
}
