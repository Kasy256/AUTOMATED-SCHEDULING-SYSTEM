import { Pin } from "lucide-react";
import { forwardRef, type ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/utils";

import type { BoardItem } from "./model/items";

type Props = {
  item: BoardItem;
  rowId: string;
  codeOf: (id: string) => string;
  draggable: boolean;
  onOpen: (item: BoardItem, rowId: string) => void;
} & Omit<ComponentPropsWithoutRef<"button">, "onClick">;

export const BoardItemView = forwardRef<HTMLButtonElement, Props>(
  function BoardItemView(
    { item, rowId, codeOf, draggable, onOpen, className, ...rest },
    ref,
  ) {
    const codes = Object.values(item.resources)
      .flat()
      .filter((id) => id !== rowId)
      .map(codeOf)
      .join(" · ");
    return (
      <button
        ref={ref}
        type="button"
        {...rest}
        tabIndex={-1}
        data-activity={item.activityId}
        aria-label={codes ? `${item.name}, ${codes}` : item.name}
        onClick={() => onOpen(item, rowId)}
        className={cn(
          "flex h-full w-full flex-col overflow-hidden rounded-md bg-primary px-2 py-1 text-left text-primary-foreground shadow-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
          item.pending &&
            "outline-2 outline-offset-1 outline-dashed outline-foreground",
          draggable ? "cursor-grab touch-none" : "cursor-pointer",
          className,
        )}
      >
        <span className="flex items-center gap-1 truncate text-xs font-semibold">
          {item.name}
          {item.pinned && (
            <Pin className="size-3 shrink-0" aria-label="pinned" />
          )}
        </span>
        <span className="truncate text-[11px]">{codes}</span>
      </button>
    );
  },
);
