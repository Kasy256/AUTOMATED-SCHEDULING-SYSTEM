import { useDraggable } from "@dnd-kit/core";

import { BoardItemView } from "./BoardItemView";
import type { BoardItem } from "./model/items";

export function DraggableItem({
  item,
  rowId,
  codeOf,
  tabbable,
  onOpen,
}: {
  item: BoardItem;
  rowId: string;
  codeOf: (id: string) => string;
  tabbable: boolean;
  onOpen: (item: BoardItem, rowId: string) => void;
}) {
  const { setNodeRef, listeners, attributes, transform, isDragging } =
    useDraggable({
      id: `${rowId}|${item.activityId}`,
      data: { item, rowId },
    });
  return (
    <BoardItemView
      ref={setNodeRef}
      item={item}
      rowId={rowId}
      codeOf={codeOf}
      draggable
      tabbable={tabbable}
      onOpen={onOpen}
      {...attributes}
      {...listeners}
      className={
        isDragging
          ? "pointer-events-none relative z-30 opacity-90 shadow-lg"
          : undefined
      }
      style={
        transform
          ? {
              transform: `translate3d(${String(transform.x)}px, ${String(transform.y)}px, 0)`,
            }
          : undefined
      }
    />
  );
}
