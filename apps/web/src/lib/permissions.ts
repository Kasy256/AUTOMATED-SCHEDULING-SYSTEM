import type { Role } from "@/api/generated/model";

export type Action = "config.read" | "config.manage" | "members.manage";

// Hides controls the API would refuse anyway; the API stays the authority (Phase 01/02 matrix).
const ALLOWED: Record<Action, Role[]> = {
  "config.read": ["org_admin", "planner", "viewer"],
  "config.manage": ["org_admin", "planner"],
  "members.manage": ["org_admin"],
};

export function can(roles: readonly Role[], action: Action): boolean {
  return roles.some((role) => ALLOWED[action].includes(role));
}
