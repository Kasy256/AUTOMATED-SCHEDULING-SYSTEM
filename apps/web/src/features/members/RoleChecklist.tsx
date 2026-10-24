import type { Role } from "@/api/generated/model";

import { ROLE_LABELS } from "./roles";

const ROLE_HINTS: Record<Role, string> = {
  org_admin: "Manages members and everything else",
  planner: "Configures and solves schedules",
  member: "Sees their own published assignments",
  viewer: "Reads everything, changes nothing",
};

export function RoleChecklist({
  idPrefix,
  value,
  onChange,
}: {
  idPrefix: string;
  value: Role[];
  onChange: (roles: Role[]) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-sm font-medium">Roles</legend>
      {(Object.keys(ROLE_LABELS) as Role[]).map((role) => (
        <div key={role} className="flex items-start gap-2">
          <input
            id={`${idPrefix}-${role}`}
            type="checkbox"
            className="mt-1"
            checked={value.includes(role)}
            aria-describedby={`${idPrefix}-${role}-hint`}
            onChange={(e) =>
              onChange(
                e.target.checked
                  ? [...value, role]
                  : value.filter((r) => r !== role),
              )
            }
          />
          <div>
            <label
              htmlFor={`${idPrefix}-${role}`}
              className="text-sm font-medium"
            >
              {ROLE_LABELS[role]}
            </label>
            <p
              id={`${idPrefix}-${role}-hint`}
              className="text-xs text-muted-foreground"
            >
              {ROLE_HINTS[role]}
            </p>
          </div>
        </div>
      ))}
    </fieldset>
  );
}
