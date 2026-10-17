import { useDroppable } from "@dnd-kit/core";
import { useEffect, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import type { CellCheck } from "./model/highlight";

const HOVER_CHECK_MS = 300;

export function DroppableCell({
  cellId,
  rowId,
  start,
  label,
  check,
  highlighting,
  onHoverCheck,
  children,
}: {
  cellId: string;
  rowId: string;
  start: string;
  label: string;
  check: CellCheck | undefined;
  highlighting: boolean;
  onHoverCheck: (rowId: string, start: string) => void;
  children: ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: cellId,
    data: { rowId, start },
  });

  useEffect(() => {
    if (!isOver || check) return;
    const timer = setTimeout(() => onHoverCheck(rowId, start), HOVER_CHECK_MS);
    return () => clearTimeout(timer);
  }, [isOver, check, onHoverCheck, rowId, start]);

  const reasons = check?.state === "invalid" ? check.reasons.join("; ") : "";
  return (
    <div
      ref={setNodeRef}
      role="gridcell"
      data-cell={cellId}
      aria-label={label}
      title={reasons || undefined}
      className={cn(
        "relative border-l p-1",
        highlighting &&
          !check &&
          "bg-[repeating-linear-gradient(45deg,transparent_0_4px,var(--color-slate-100)_4px_8px)]",
        check?.state === "valid" &&
          "bg-[#dcfce7] shadow-[inset_0_0_0_2px_#16a34a]",
        check?.state === "invalid" &&
          "bg-[#fee2e2] shadow-[inset_0_0_0_2px_#dc2626]",
        isOver && "ring-2 ring-ring ring-inset",
      )}
    >
      {children}
    </div>
  );
}
