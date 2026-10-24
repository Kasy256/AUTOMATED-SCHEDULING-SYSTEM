import { LogOut } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth/AuthProvider";

export function OrgMenu() {
  const { me, logout, switchOrganisation } = useAuth();
  if (!me) return null;
  const current = me.organisations.find(
    (o) => o.organisation_id === me.organisation_id,
  );
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="w-full rounded-md px-3 py-2 text-left text-sm hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none">
        <span className="block truncate font-medium text-sidebar-accent-foreground">
          {current?.name ?? "No organisation"}
        </span>
        <span className="block truncate text-xs">{me.email}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-60" align="start" side="top">
        {me.organisations.length > 1 && (
          <>
            <DropdownMenuLabel>Switch organisation</DropdownMenuLabel>
            {me.organisations
              .filter((o) => o.organisation_id !== me.organisation_id)
              .map((o) => (
                <DropdownMenuItem
                  key={o.organisation_id}
                  onSelect={() => void switchOrganisation(o.organisation_id)}
                >
                  {o.name}
                </DropdownMenuItem>
              ))}
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem onSelect={() => void logout()}>
          <LogOut className="size-4" aria-hidden /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
