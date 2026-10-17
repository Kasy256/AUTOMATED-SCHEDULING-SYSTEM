import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useRef, useState } from "react";

import type { ResourceResponse } from "@/api/generated/model";

import { BoardRow, ROW_HEIGHT } from "./BoardRow";
import type { Column } from "./model/columns";
import type { CellCheck } from "./model/highlight";
import { cellKey, type BoardItem } from "./model/items";
import { useBoardKeyboard } from "./useBoardKeyboard";

const HOVER_CHECK_MS = 300;

interface DragData {
  item: BoardItem;
  rowId: string;
}

// The drop target is the cell under the pointer. Cells are found by hit-testing rather than as
// dnd-kit droppables: registering a droppable per cell re-renders the whole board on every scroll.
// The pointer is tracked directly because dnd-kit's drag delta also absorbs scrolling.
function cellAtPoint(point: { x: number; y: number } | null): string | null {
  if (!point) return null;
  const el = document.elementFromPoint(point.x, point.y);
  return el?.closest<HTMLElement>("[data-cell]")?.dataset.cell ?? null;
}

function splitKey(key: string): { rowId: string; start: string } {
  const at = key.indexOf("|");
  return { rowId: key.slice(0, at), start: key.slice(at + 1) };
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
  onCheck,
}: {
  rows: ResourceResponse[];
  columns: Column[];
  index: Map<string, BoardItem[]>;
  codeOf: (id: string) => string;
  highlight: Map<string, CellCheck> | null;
  canDrag: boolean;
  onOpenItem: (item: BoardItem, rowId: string) => void;
  onPickUp: (item: BoardItem, rowId: string) => void;
  onDrop: (rowId: string, start: string) => Promise<boolean>;
  onCancel: () => void;
  onHoverCheck: (rowId: string, start: string) => void;
  onCheck: (rowId: string, start: string) => Promise<CellCheck | null>;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
    initialRect: { width: 1200, height: 800 },
  });
  // A small distance threshold keeps a plain click a click (it opens the item).
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );
  const template = `14rem repeat(${String(columns.length)}, minmax(7.5rem, 1fr))`;
  const [overKey, setOverKey] = useState<string | null>(null);

  const pointer = useRef<{ x: number; y: number } | null>(null);
  useEffect(() => {
    const track = (e: PointerEvent) => {
      pointer.current = { x: e.clientX, y: e.clientY };
    };
    window.addEventListener("pointermove", track);
    return () => window.removeEventListener("pointermove", track);
  }, []);

  function dragStart(e: DragStartEvent) {
    const data = e.active.data.current as DragData | undefined;
    if (data) onPickUp(data.item, data.rowId);
  }
  function dragEnd() {
    const key = cellAtPoint(pointer.current);
    setOverKey(null);
    if (key) {
      const { rowId, start } = splitKey(key);
      void onDrop(rowId, start);
    } else onCancel();
  }

  useEffect(() => {
    if (!overKey || highlight?.get(overKey)) return;
    const { rowId, start } = splitKey(overKey);
    const timer = setTimeout(() => onHoverCheck(rowId, start), HOVER_CHECK_MS);
    return () => clearTimeout(timer);
  }, [overKey, highlight, onHoverCheck]);

  const [carrying, setCarrying] = useState<BoardItem | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const cellAt = (r: number, c: number) => {
    const row = rows[r];
    const col = columns[c];
    return row && col ? { row, col } : null;
  };
  const itemAt = (r: number, c: number) => {
    const cell = cellAt(r, c);
    return cell
      ? index.get(cellKey(cell.row.id, cell.col.start))?.[0]
      : undefined;
  };
  const keyboard = useBoardKeyboard({
    rowCount: rows.length,
    colCount: columns.length,
    itemAt,
    carrying: carrying !== null,
    onOpen: (r, c) => {
      const item = itemAt(r, c);
      const cell = cellAt(r, c);
      if (item && cell) onOpenItem(item, cell.row.id);
    },
    onPickUp: (r, c) => {
      const item = itemAt(r, c);
      const cell = cellAt(r, c);
      if (!item || !cell) return;
      if (!canDrag || item.pinned) {
        setAnnouncement(`${item.name} can't be moved`);
        return;
      }
      setCarrying(item);
      onPickUp(item, cell.row.id);
      setAnnouncement(`Picked up ${item.name}`);
    },
    onTarget: (r, c) => {
      const cell = cellAt(r, c);
      if (!cell) return;
      onCheck(cell.row.id, cell.col.start).then(
        (check) =>
          setAnnouncement(
            check?.state === "invalid"
              ? `${cell.col.label}: breaks ${check.reasons[0] ?? "a rule"}`
              : check
                ? `${cell.col.label}: valid`
                : cell.col.label,
          ),
        () => setAnnouncement(cell.col.label),
      );
    },
    onDrop: (r, c) => {
      const cell = cellAt(r, c);
      const item = carrying;
      setCarrying(null);
      if (!cell || !item) return;
      void onDrop(cell.row.id, cell.col.start).then((moved) =>
        setAnnouncement(
          moved ? `${item.name} moved to ${cell.col.label}` : "Move cancelled",
        ),
      );
    },
    onCancel: () => {
      setCarrying(null);
      onCancel();
      setAnnouncement("Move cancelled");
    },
  });
  const { focus, setFocus } = keyboard;

  // Roving focus follows the keyboard position, but only while focus is already in the grid.
  useEffect(() => {
    const grid = scroller.current;
    if (!grid?.contains(document.activeElement)) return;
    virtual.scrollToIndex(focus.r);
    grid
      .querySelector<HTMLElement>(
        `[data-pos="${String(focus.r)}:${String(focus.c)}"]`,
      )
      ?.focus();
  }, [focus.r, focus.c, virtual]);

  return (
    <DndContext
      sensors={sensors}
      onDragStart={dragStart}
      onDragMove={() => setOverKey(cellAtPoint(pointer.current))}
      onDragEnd={dragEnd}
      onDragCancel={() => {
        setOverKey(null);
        onCancel();
      }}
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
          onKeyDown={keyboard.onKeyDown}
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
                <BoardRow
                  key={row.id}
                  row={row}
                  rowIndex={v.index}
                  top={v.start}
                  template={template}
                  columns={columns}
                  index={index}
                  codeOf={codeOf}
                  highlight={highlight}
                  canDrag={canDrag}
                  focusCol={focus.r === v.index ? focus.c : -1}
                  overKey={overKey?.startsWith(`${row.id}|`) ? overKey : null}
                  onOpenItem={onOpenItem}
                  setFocus={setFocus}
                />
              );
            })}
          </div>
        </div>
      </div>
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
    </DndContext>
  );
}
