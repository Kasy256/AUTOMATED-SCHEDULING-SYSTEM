import { screen } from "@testing-library/react";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { InfeasibilityReport } from "./InfeasibilityReport";

describe("InfeasibilityReport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists conflicts and ranked relaxations with their outcome", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse([]))),
    );
    renderWithProviders(
      <InfeasibilityReport
        scheduleId="s1"
        report={{
          conflicts: [
            { id: "c-rule", kind: "rule", text: "At most 1 per day" },
            {
              id: "core:pin:a1",
              kind: "pin",
              text: "Pinned CS 201 can't move",
            },
          ],
          relaxations: [
            {
              kind: "switch_to_soft",
              target: "c-rule",
              text: "Make it soft",
              fixes: true,
            },
            {
              kind: "change_param",
              target: "c-rule",
              text: "Raise the limit",
              fixes: null,
            },
          ],
        }}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "What conflicts" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "What would fix it" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("At most 1 per day")).toBeInTheDocument();
    expect(screen.getByText("Rule")).toBeInTheDocument();
    expect(screen.getByText("Fixes it")).toBeInTheDocument();
    expect(screen.getByText("Untested")).toBeInTheDocument();
  });

  it("says so when the solver could not explain", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse([]))),
    );
    renderWithProviders(
      <InfeasibilityReport
        scheduleId="s1"
        report={{ conflicts: [], relaxations: [] }}
      />,
    );
    expect(screen.getByText(/could not explain this one/)).toBeInTheDocument();
  });
});
