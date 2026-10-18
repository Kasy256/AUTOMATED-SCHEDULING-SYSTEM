import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PendingTray } from "./PendingTray";

const changes = [
  { activity_id: "a1", start_at: "2026-01-13T06:00:00Z", resources: {} },
  { activity_id: "a2", start_at: "2026-01-13T06:00:00Z", resources: {} },
];

function tray(overrides: Partial<Parameters<typeof PendingTray>[0]> = {}) {
  const props = {
    changes,
    describe: (c: { activity_id: string }) => `${c.activity_id} → Tue P1`,
    onUndo: vi.fn(),
    onDiscard: vi.fn(),
    onSave: vi.fn(),
    saving: false,
    error: null,
    ...overrides,
  };
  render(<PendingTray {...props} />);
  return props;
}

describe("PendingTray", () => {
  it("lists the changes and wires undo, discard and save", async () => {
    const props = tray();
    expect(screen.getByText("2 unsaved changes")).toBeInTheDocument();
    expect(screen.getByText("a1 → Tue P1 · a2 → Tue P1")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Undo last" }));
    await userEvent.click(screen.getByRole("button", { name: "Discard" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Save as draft" }),
    );
    expect(props.onUndo).toHaveBeenCalledOnce();
    expect(props.onDiscard).toHaveBeenCalledOnce();
    expect(props.onSave).toHaveBeenCalledOnce();
  });

  it("shows a save error", () => {
    tray({ error: "These changes conflict with each other: CS 201" });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "These changes conflict with each other: CS 201",
    );
  });

  it("renders nothing without changes", () => {
    tray({ changes: [] });
    expect(screen.queryByRole("region")).toBeNull();
  });
});
