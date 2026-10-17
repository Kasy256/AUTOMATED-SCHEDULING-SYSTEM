import { Skeleton } from "@/components/ui/skeleton";

export function TableSkeleton({
  rows = 6,
  columns = 4,
  label,
}: {
  rows?: number;
  columns?: number;
  label: string;
}) {
  return (
    <div
      role="status"
      aria-label={label}
      className="rounded-xl border bg-card p-4 shadow-sm"
    >
      <div className="flex flex-col gap-3">
        {Array.from({ length: rows }, (_, r) => (
          <div
            key={r}
            data-skeleton-row
            className="grid gap-4"
            style={{
              gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
            }}
          >
            {Array.from({ length: columns }, (_, c) => (
              <Skeleton key={c} className="h-5" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
