import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { SetupWizard } from "./SetupWizard";

const education = {
  key: "education",
  version: 2,
  name: "Education",
  description: "Lecturers, rooms, student groups, weekly sessions.",
  resource_types: [],
  day_parts: { version: 1, parts: [] },
  slot_templates: [],
  demand_shape: null,
  constraints: [],
};

describe("SetupWizard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("offers Education, marks Healthcare as coming soon, and moves to the schedule step", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          jsonResponse(url.includes("industry-templates") ? [education] : []),
        ),
      ),
    );
    renderWithProviders(<SetupWizard />, { route: "/setup" });
    const healthcare = await screen.findByRole("button", {
      name: /Healthcare rostering/,
    });
    expect(healthcare).toBeDisabled();
    expect(screen.getByText("Coming soon")).toBeInTheDocument();
    await userEvent.click(
      await screen.findByRole("button", { name: /Education/ }),
    );
    expect(
      await screen.findByRole("heading", { name: "Create your schedule" }),
    ).toBeInTheDocument();
  });
});
