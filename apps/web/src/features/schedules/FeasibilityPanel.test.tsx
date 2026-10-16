import { screen } from "@testing-library/react";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { FeasibilityPanel } from "./FeasibilityPanel";

describe("FeasibilityPanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("names the resources an issue affects", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/feasibility"))
          return Promise.resolve(
            jsonResponse({
              problem_hash: "h",
              issues: [
                {
                  code: "overloaded_resource",
                  message: "Needed for 50 hours but available 40",
                  activity_ids: [],
                  resource_ids: ["r1"],
                },
              ],
            }),
          );
        if (url.endsWith("/resources"))
          return Promise.resolve(
            jsonResponse([
              {
                id: "r1",
                resource_type_id: "t",
                code: "L005",
                name: "Dr. Okello",
                tags: [],
                attributes: {},
                capacity: null,
                size: null,
                concurrency: 1,
                user_id: null,
              },
            ]),
          );
        return Promise.resolve(jsonResponse([]));
      }),
    );
    renderWithProviders(<FeasibilityPanel scheduleId="s1" />);
    expect(
      await screen.findByText("Needed for 50 hours but available 40"),
    ).toBeInTheDocument();
    expect(await screen.findByText("Dr. Okello (L005)")).toBeInTheDocument();
  });

  it("says when nothing blocks a solve", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          jsonResponse(
            url.includes("/feasibility")
              ? { problem_hash: "h", issues: [] }
              : [],
          ),
        ),
      ),
    );
    renderWithProviders(<FeasibilityPanel scheduleId="s1" />);
    expect(
      await screen.findByText(
        "No problems found. The schedule is ready to solve.",
      ),
    ).toBeInTheDocument();
  });
});
