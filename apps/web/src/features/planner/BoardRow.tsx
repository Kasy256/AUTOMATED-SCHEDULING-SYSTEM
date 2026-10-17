import { memo } from "react";

import type { ResourceResponse } from "@/api/generated/model";

import { BoardCell } from "./BoardCell";
import { BoardItemView } from "./BoardItemView";
import { DraggableItem } from "./DraggableItem";
import type { Column } from "./model/columns";
import type { CellCheck } from "./model/highlight";
import { cellKey, type BoardItem } from "./model/items";
import type { CellPos } from "./useBoardKeyboard";

export const ROW_HEIGHT = 56;

// Memoised so scrolling only renders the rows that mount, not every visible row.
export const BoardRow = memo(function BoardRow({
  row,
  rowIndex,
  top,
  template,
  columns,
  index,
  codeOf,
  highlight,
  canDrag,
  focusCol,
  overKey,
  onOpenItem,
  setFocus,
}: {
  row: ResourceResponse;
  rowIndex: number;
  top: number;
  template: string;
  columns: Column[];
  index: Map<string, BoardItem[]>;
  codeOf: (id: string) => string;
  highlight: Map<string, CellCheck> | null;
  canDrag: boolean;
  focusCol: number;
  overKey: string | null;
  onOpenItem: (item: BoardItem, rowId: string) => void;
  setFocus: (pos: CellPos) => void;
}) {
  return (
    <div
      role="row"
      aria-rowindex={rowIndex + 2}
      className="absolute inset-x-0 grid border-b"
      style={{
        gridTemplateColumns: template,
        height: ROW_HEIGHT,
        transform: `translateY(${String(top)}px)`,
      }}
    >
      <div
        role="rowheader"
        className="sticky left-0 z-[1] flex flex-col justify-center bg-card px-3"
      >
        <span className="truncate text-sm font-medium">{row.name}</span>
        <span className="text-xs text-muted-foreground">{row.code}</span>
      </div>
      {columns.map((c, ci) => {
        const key = cellKey(row.id, c.start);
        const items = index.get(key) ?? [];
        return (
          <BoardCell
            key={c.start}
            cellId={key}
            label={`${row.name}, ${c.label}: ${items.map((i) => i.name).join(", ") || "empty"}`}
            check={highlight?.get(key)}
            highlighting={highlight !== null}
            over={overKey === key}
            pos={`${String(rowIndex)}:${String(ci)}`}
            focused={focusCol === ci}
            onFocusCell={() => setFocus({ r: rowIndex, c: ci })}
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
          </BoardCell>
        );
      })}
    </div>
  );
});
