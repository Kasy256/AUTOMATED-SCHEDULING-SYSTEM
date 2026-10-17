import { cn } from "@/lib/utils";

/** Calendar-grid glyph plus the product name. */
export function BrandMark({
  className,
  tone = "light",
}: {
  className?: string;
  tone?: "light" | "dark";
}) {
  return (
    <span
      className={cn(
        "flex items-center gap-2 font-semibold tracking-tight",
        className,
      )}
    >
      <svg viewBox="0 0 24 24" className="size-6" aria-hidden="true">
        <rect x="2" y="3.5" width="20" height="18" rx="4" fill="#0f766e" />
        <rect x="2" y="3.5" width="20" height="5" rx="2" fill="#14b8a6" />
        <rect x="6" y="11.5" width="4" height="3" rx="1" fill="#ccfbf1" />
        <rect
          x="14"
          y="11.5"
          width="4"
          height="3"
          rx="1"
          fill="#ccfbf1"
          opacity="0.6"
        />
        <rect
          x="6"
          y="16"
          width="4"
          height="3"
          rx="1"
          fill="#ccfbf1"
          opacity="0.6"
        />
        <rect x="14" y="16" width="4" height="3" rx="1" fill="#ccfbf1" />
      </svg>
      <span
        className={
          tone === "light"
            ? "text-sidebar-accent-foreground"
            : "text-foreground"
        }
      >
        Cartlyf
      </span>
    </span>
  );
}
