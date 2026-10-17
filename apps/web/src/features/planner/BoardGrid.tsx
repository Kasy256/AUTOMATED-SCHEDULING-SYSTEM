import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";

import type { ResourceResponse } from "@/api/generated/model";
import { cn } from "@/lib/utils";

import type { Column } from "./model/columns";
import type { CellCheck } from "./model/highlight";
import { cellKey, type BoardItem } from "./model/items";
import { BoardItemView } from "./BoardItemView";

const ROW = 56;

export function BoardGrid({
  rows,
  columns,
  index,
  codeOf,
  highlight,
  canDrag,
  onOpenItem,
}: {
  rows: ResourceResponse[];
  columns: Column[];
  index: Map<string, BoardItem[]>;
  codeOf: (id: string) => string;
  highlight: Map<string, CellCheck> | null;
  canDrag: boolean;
  onOpenItem: (item: BoardItem, rowId: string) => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => ROW,
    overscan: 8,
    // jsdom has no layout; a starting size lets tests (and first paint) render rows.
    initialRect: { width: 1200, height: 800 },
  });
  const template = `14rem repeat(${String(columns.length)}, minmax(7.5rem, 1fr))`;
  return (
    <div
      ref={scroller}
      className="relative max-h-[calc(100svh-15rem)] overflow-auto rounded-xl border bg-card shadow-sm"
    >
      <div
        role="grid"
        aria-rowcount={rows.length + 1}
        aria-colcount={columns.length + 1}
        className="min-w-max"
      >
        <div
          role="row"
          aria-rowindex={1}
          className="sticky top-0 z-10 grid border-b bg-muted/80 backdrop-blur"
          style={{ gridTemplateColumns: template }}
        >
          <div
            role="columnheader"
            className="sticky left-0 bg-muted/80 px-3 py-2 text-xs font-medium text-muted-foreground"
          >
            Resource
          </div>
          {columns.map((c) => (
            <div
              key={c.start}
              role="columnheader"
              aria-label={c.label}
              className="px-2 py-2 text-center text-xs font-semibold tracking-wide text-muted-foreground uppercase"
            >
              {c.label}
            </div>
          ))}
        </div>
        <div className="relative" style={{ height: virtual.getTotalSize() }}>
          {virtual.getVirtualItems().map((v) => {
            const row = rows[v.index];
            if (!row) return null;
            return (
              <div
                key={row.id}
                role="row"
                aria-rowindex={v.index + 2}
                className="absolute inset-x-0 grid border-b"
                style={{
                  gridTemplateColumns: template,
                  height: ROW,
                  transform: `translateY(${String(v.start)}px)`,
                }}
              >
                <div
                  role="rowheader"
                  className="sticky left-0 z-[1] flex flex-col justify-center bg-card px-3"
                >
                  <span className="truncate text-sm font-medium">
                    {row.name}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {row.code}
                  </span>
                </div>
                {columns.map((c) => {
                  const key = cellKey(row.id, c.start);
                  const items = index.get(key) ?? [];
                  const check = highlight?.get(key);
                  return (
                    <div
                      key={c.start}
                      role="gridcell"
                      data-cell={key}
                      aria-label={`${row.name}, ${c.label}: ${items.map((i) => i.name).join(", ") || "empty"}`}
                      className={cn(
                        "relative border-l p-1",
                        highlight &&
                          !check &&
                          "bg-[repeating-linear-gradient(45deg,transparent_0_4px,var(--color-slate-100)_4px_8px)]",
                        check?.state === "valid" &&
                          "bg-[#dcfce7] shadow-[inset_0_0_0_2px_#16a34a]",
                        check?.state === "invalid" &&
                          "bg-[#fee2e2] shadow-[inset_0_0_0_2px_#dc2626]",
                      )}
                    >
                      {items.map((item) => (
                        <BoardItemView
                          key={item.activityId}
                          item={item}
                          rowId={row.id}
                          codeOf={codeOf}
                          draggable={canDrag && !item.pinned}
                          onOpen={onOpenItem}
                        />
                      ))}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
