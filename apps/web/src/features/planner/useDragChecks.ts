import { useCallback, useEffect, useRef, useState } from "react";

import type { MoveRequest } from "@/api/generated/model";
import {
  explainAssignment,
  validateMove,
} from "@/api/generated/versions/versions";

import { highlightMap, type CellCheck } from "./model/highlight";
import { cellKey, type BoardItem } from "./model/items";
import { buildMove } from "./model/moves";

export function useDragChecks(versionId: string) {
  const [dragging, setDragging] = useState<{
    item: BoardItem;
    rowId: string;
  } | null>(null);
  const [highlight, setHighlight] = useState<Map<string, CellCheck> | null>(
    null,
  );
  // Latest values for async callbacks without re-creating them on every render.
  const live = useRef({ dragging, highlight });
  useEffect(() => {
    live.current = { dragging, highlight };
  });

  const pickUp = useCallback(
    async (item: BoardItem, rowId: string) => {
      live.current = { dragging: { item, rowId }, highlight: new Map() };
      setDragging({ item, rowId });
      setHighlight(new Map());
      try {
        const explanation = await explainAssignment(versionId, item.activityId);
        const map = highlightMap(explanation, item, rowId);
        live.current.highlight = map;
        setHighlight(map);
      } catch {
        // Without an explanation every cell is checked on hover instead.
      }
    },
    [versionId],
  );

  const check = useCallback(
    async (rowId: string, start: string): Promise<CellCheck | null> => {
      const current = live.current.dragging;
      if (!current) return null;
      const key = cellKey(rowId, start);
      const known = live.current.highlight?.get(key);
      if (known) return known;
      const move = buildMove(current.item, current.rowId, {
        resourceId: rowId,
        start,
      });
      if (!move) return null;
      const out = await validateMove(versionId, move);
      const result: CellCheck = out.valid
        ? { state: "valid" }
        : { state: "invalid", reasons: out.broken.map((b) => b.message) };
      setHighlight((h) => new Map(h ?? []).set(key, result));
      live.current.highlight = new Map(live.current.highlight ?? []).set(
        key,
        result,
      );
      return result;
    },
    [versionId],
  );

  const cancel = useCallback(() => {
    live.current = { dragging: null, highlight: null };
    setDragging(null);
    setHighlight(null);
  }, []);

  const drop = useCallback(
    async (
      rowId: string,
      start: string,
    ): Promise<{ move: MoveRequest; result: CellCheck } | null> => {
      const current = live.current.dragging;
      const move = current
        ? buildMove(current.item, current.rowId, { resourceId: rowId, start })
        : null;
      const result = move ? await check(rowId, start) : null;
      cancel();
      return move && result ? { move, result } : null;
    },
    [check, cancel],
  );

  return { dragging, highlight, pickUp, check, drop, cancel };
}
