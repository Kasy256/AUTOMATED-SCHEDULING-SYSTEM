import { screen, within } from "@testing-library/react";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { CoverageGapsPanel } from "./CoverageGapsPanel";

const gap = (activity_id: string, starts_at: string, assigned = 1) => ({
  activity_id,
  role: "rn",
  required_min: 2,
  assigned,
  starts_at,
});

function renderPanel(gaps: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          version_id: "v1",
          utilisation: [],
          load: [],
          coverage_gaps: gaps,
          fairness: [],
        }),
      ),
    ),
  );
  renderWithProviders(
    <CoverageGapsPanel
      versionId="v1"
      weekStart="2027-01-04"
      weekEnd="2027-01-10"
      activityNames={{ a1: "Ward night", a2: "Ward day", a3: "Next week" }}
      timezone="Africa/Kampala"
    />,
  );
}

describe("CoverageGapsPanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists this week's gaps in start order with names and counts", async () => {
    renderPanel([
      gap("a1", "2027-01-05T19:00:00Z"),
      gap("a2", "2027-01-04T04:00:00Z", 0),
    ]);
    const list = await screen.findByRole("list");
    const items = within(list).getAllByRole("listitem");
    expect(items.map((i) => i.textContent)).toEqual([
      "Ward day · Mon 4 Jan, 07:00 — rn 0 of 2",
      "Ward night · Tue 5 Jan, 22:00 — rn 1 of 2",
    ]);
    expect(
      screen.getByRole("region", { name: "Coverage gaps" }),
    ).toBeInTheDocument();
  });

  it("hides gaps outside the shown week", async () => {
    renderPanel([
      gap("a1", "2027-01-05T19:00:00Z"),
      gap("a3", "2027-01-12T04:00:00Z"),
    ]);
    await screen.findByRole("list");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.queryByText(/Next week/)).not.toBeInTheDocument();
  });

  it("says so when every shift is staffed", async () => {
    renderPanel([gap("a3", "2027-01-12T04:00:00Z")]);
    expect(
      await screen.findByText("Every shift is fully staffed this week"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });
});
