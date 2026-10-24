import type { Role } from "@/api/generated/model";

export const ROLE_LABELS: Record<Role, string> = {
  org_admin: "Admin",
  planner: "Planner",
  member: "Member",
  viewer: "Viewer",
};
