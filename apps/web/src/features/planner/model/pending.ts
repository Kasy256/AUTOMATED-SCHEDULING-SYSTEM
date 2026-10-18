import type { AssignmentEdit } from "@/api/generated/model";

export type PendingAction =
  | { type: "add"; change: AssignmentEdit }
  | { type: "undo" }
  | { type: "discard" };

export function pendingReducer(
  state: AssignmentEdit[],
  action: PendingAction,
): AssignmentEdit[] {
  switch (action.type) {
    case "add":
      return [
        ...state.filter((c) => c.activity_id !== action.change.activity_id),
        action.change,
      ];
    case "undo":
      return state.slice(0, -1);
    case "discard":
      return [];
  }
}
