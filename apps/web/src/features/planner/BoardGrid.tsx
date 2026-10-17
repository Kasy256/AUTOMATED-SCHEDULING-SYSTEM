import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";

import type { ResourceResponse } from "@/api/generated/model";

import { BoardItemView } from "./BoardItemView";
import { DraggableItem } from "./DraggableItem";
import { DroppableCell } from "./DroppableCell";
import type { Column } from "./model/columns";
import type { CellCheck } from "./model/highlight";
import { cellKey, type BoardItem } from "./model/items";

const ROW = 56;

interface DragData {
  item: BoardItem;
  rowId: string;
}
interface DropData {
  rowId: string;
  start: string;
}

export function BoardGrid({
  rows,
  columns,
  index,
  codeOf,
  highlight,
  canDrag,
  onOpenItem,
  onPickUp,
  onDrop,
  onCancel,
  onHoverCheck,
}: {
  rows: ResourceResponse[];
  columns: Column[];
  index: Map<string, BoardItem[]>;
  codeOf: (id: string) => string;
  highlight: Map<string, CellCheck> | null;
  canDrag: boolean;
  onOpenItem: (item: BoardItem, rowId: string) => void;
  onPickUp: (item: BoardItem, rowId: string) => void;
  onDrop: (rowId: string, start: string) => void;
  onCancel: () => void;
  onHoverCheck: (rowId: string, start: string) => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => ROW,
    overscan: 8,
    initialRect: { width: 1200, height: 800 },
  });
  // A small distance threshold keeps a plain click a click (it opens the item).
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );
  const template = `14rem repeat(${String(columns.length)}, minmax(7.5rem, 1fr))`;

  function dragStart(e: DragStartEvent) {
    const data = e.active.data.current as DragData | undefined;
    if (data) onPickUp(data.item, data.rowId);
  }
  function dragEnd(e: DragEndEvent) {
    const data = e.over?.data.current as DropData | undefined;
    if (data) onDrop(data.rowId, data.start);
    else onCancel();
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={dragStart}
      onDragEnd={dragEnd}
      onDragCancel={onCancel}
    >
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
                    return (
                      <DroppableCell
                        key={c.start}
                        cellId={key}
                        rowId={row.id}
                        start={c.start}
                        label={`${row.name}, ${c.label}: ${items.map((i) => i.name).join(", ") || "empty"}`}
                        check={highlight?.get(key)}
                        highlighting={highlight !== null}
                        onHoverCheck={onHoverCheck}
                      >
                        {items.map((item) =>
                          canDrag && !item.pinned ? (
                            <DraggableItem
                              key={item.activityId}
                              item={item}
                              rowId={row.id}
                              codeOf={codeOf}
                              onOpen={onOpenItem}
                            />
                          ) : (
                            <BoardItemView
                              key={item.activityId}
                              item={item}
                              rowId={row.id}
                              codeOf={codeOf}
                              draggable={false}
                              onOpen={onOpenItem}
                            />
                          ),
                        )}
                      </DroppableCell>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </DndContext>
  );
}
