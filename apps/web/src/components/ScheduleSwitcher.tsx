import { Check, ChevronsUpDown, Plus } from "lucide-react";
import { useNavigate } from "react-router";

import { useListSchedules } from "@/api/generated/schedules/schedules";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth/AuthProvider";
import { LAST_SCHEDULE_KEY } from "@/lib/landing";
import { writeStored } from "@/lib/storage";

export function ScheduleSwitcher({
  activeId,
}: {
  activeId: string | undefined;
}) {
  const { data: schedules = [] } = useListSchedules();
  const navigate = useNavigate();
  const { can } = useAuth();
  const active = schedules.find((s) => s.id === activeId);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center justify-between rounded-md border border-sidebar-border bg-sidebar-accent px-3 py-2 text-left text-sm text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none">
        <span className="min-w-0">
          <span className="block text-[10px] tracking-wider text-sidebar-foreground uppercase">
            Schedule
          </span>
          <span className="block truncate font-medium">
            {active?.name ?? "Choose a schedule"}
          </span>
        </span>
        <ChevronsUpDown className="size-4 shrink-0 opacity-60" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-60" align="start">
        <DropdownMenuLabel>Schedules</DropdownMenuLabel>
        {schedules.map((s) => (
          <DropdownMenuItem
            key={s.id}
            onSelect={() => {
              writeStored(LAST_SCHEDULE_KEY, s.id);
              void navigate(`/schedules/${s.id}/overview`);
            }}
          >
            <Check
              className={s.id === activeId ? "size-4" : "size-4 opacity-0"}
              aria-hidden
            />
            {s.name}
          </DropdownMenuItem>
        ))}
        {can("config.manage") && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => void navigate("/setup")}>
              <Plus className="size-4" aria-hidden /> New schedule
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
