import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import type { CellCheck } from "./model/highlight";

export function BoardCell({
  cellId,
  label,
  check,
  highlighting,
  over,
  pos,
  focused,
  onFocusCell,
  children,
}: {
  cellId: string;
  label: string;
  check: CellCheck | undefined;
  highlighting: boolean;
  over: boolean;
  pos: string;
  focused: boolean;
  onFocusCell: () => void;
  children: ReactNode;
}) {
  const reasons = check?.state === "invalid" ? check.reasons.join("; ") : "";
  return (
    <div
      role="gridcell"
      data-cell={cellId}
      data-pos={pos}
      data-check={highlighting ? (check?.state ?? "unchecked") : undefined}
      tabIndex={focused ? 0 : -1}
      onFocus={onFocusCell}
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
        over && "ring-2 ring-ring ring-inset",
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset",
      )}
    >
      {children}
    </div>
  );
}
