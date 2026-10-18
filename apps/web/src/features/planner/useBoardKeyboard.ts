import { useState, type KeyboardEvent } from "react";

import type { BoardItem } from "./model/items";

export interface CellPos {
  r: number;
  c: number;
}

const clamp = (n: number, max: number) => Math.max(0, Math.min(n, max - 1));

export function useBoardKeyboard({
  rowCount,
  colCount,
  itemAt,
  onOpen,
  onPickUp,
  onTarget,
  onDrop,
  onCancel,
  carrying,
}: {
  rowCount: number;
  colCount: number;
  itemAt: (r: number, c: number) => BoardItem | undefined;
  onOpen: (r: number, c: number) => void;
  onPickUp: (r: number, c: number) => void;
  onTarget: (r: number, c: number) => void;
  onDrop: (r: number, c: number) => void;
  onCancel: () => void;
  carrying: boolean;
}) {
  const [chosen, setFocus] = useState<CellPos>({ r: 0, c: 0 });
  // Filtering or switching weeks can shrink the board under the focused cell.
  const focus = { r: clamp(chosen.r, rowCount), c: clamp(chosen.c, colCount) };

  function moveTo(r: number, c: number) {
    const next = { r: clamp(r, rowCount), c: clamp(c, colCount) };
    setFocus(next);
    if (carrying) onTarget(next.r, next.c);
  }

  function onKeyDown(e: KeyboardEvent) {
    const { r, c } = focus;
    switch (e.key) {
      case "ArrowUp":
        moveTo(r - 1, c);
        break;
      case "ArrowDown":
        moveTo(r + 1, c);
        break;
      case "ArrowLeft":
        moveTo(r, c - 1);
        break;
      case "ArrowRight":
        moveTo(r, c + 1);
        break;
      case "Home":
        moveTo(r, 0);
        break;
      case "End":
        moveTo(r, colCount - 1);
        break;
      case "Enter":
        if (!itemAt(r, c)) return;
        onOpen(r, c);
        break;
      case " ":
        if (carrying) onDrop(r, c);
        else if (itemAt(r, c)) onPickUp(r, c);
        else return;
        break;
      case "Escape":
        if (!carrying) return;
        onCancel();
        break;
      default:
        return;
    }
    e.preventDefault();
  }

  return { focus, setFocus, onKeyDown };
}
