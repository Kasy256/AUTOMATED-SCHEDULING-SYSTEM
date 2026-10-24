// The tabs switch what the board shows, so they control it (there is no panel per tab).
export const BOARD_ID = "planner-board";

export const versionLabel = (v: { number: number; status: string }) =>
  `Version ${String(v.number)} · ${v.status}`;
