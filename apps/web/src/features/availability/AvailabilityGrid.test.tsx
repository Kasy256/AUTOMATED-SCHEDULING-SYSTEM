import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AvailabilityGrid } from "./AvailabilityGrid";
import { rulesToGrid, type Grid } from "./grid";

describe("AvailabilityGrid", () => {
  it("paints with the keyboard", async () => {
    let latest: Grid = rulesToGrid([]);
    let touched = new Set<number>();
    const { rerender } = render(
      <AvailabilityGrid
        grid={latest}
        onChange={(g, t) => {
          latest = g;
          touched = t;
        }}
        readOnly={false}
      />,
    );
    const start = screen.getByRole("gridcell", {
      name: "Mon 09:00–09:30: not set",
    });
    start.focus();
    await userEvent.keyboard("{Shift>}{ArrowDown}{/Shift}2{Enter}");
    rerender(
      <AvailabilityGrid
        grid={latest}
        onChange={() => undefined}
        readOnly={false}
      />,
    );
    expect(
      screen.getByRole("gridcell", { name: "Mon 09:00–09:30: preferred" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("gridcell", { name: "Mon 09:30–10:00: preferred" }),
    ).toBeInTheDocument();
    expect([...touched]).toEqual([0]);
  });

  it("does nothing when read-only", async () => {
    const onChange = vi.fn();
    render(
      <AvailabilityGrid grid={rulesToGrid([])} onChange={onChange} readOnly />,
    );
    screen.getByRole("gridcell", { name: "Mon 09:00–09:30: not set" }).focus();
    await userEvent.keyboard("1{Enter}");
    expect(onChange).not.toHaveBeenCalled();
  });
});
