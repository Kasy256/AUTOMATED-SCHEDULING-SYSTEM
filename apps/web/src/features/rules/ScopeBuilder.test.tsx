import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { emptyScope } from "./scope";
import { ScopeBuilder } from "./ScopeBuilder";

describe("ScopeBuilder", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("adds a resource type and a tag", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          jsonResponse(
            url.includes("resource-types")
              ? [
                  {
                    id: "t1",
                    key: "lecturer",
                    name: "Lecturer",
                    kind: "person",
                    attribute_schema: { version: 1, attributes: [] },
                  },
                ]
              : url.endsWith("/schedules/s1")
                ? {
                    id: "s1",
                    name: "T",
                    timezone: "UTC",
                    start_date: "2026-01-12",
                    end_date: "2026-01-16",
                    day_parts: { version: 1, parts: [] },
                  }
                : [],
          ),
        ),
      ),
    );
    const onChange = vi.fn();
    renderWithProviders(
      <ScopeBuilder scheduleId="s1" value={emptyScope()} onChange={onChange} />,
    );
    expect(screen.getByText("Applies to: Everything")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Resource types" }),
    );
    await userEvent.click(
      await screen.findByRole("option", { name: "Lecturer" }),
    );
    expect(onChange).toHaveBeenLastCalledWith({
      ...emptyScope(),
      resource_type_ids: ["t1"],
    });

    await userEvent.type(screen.getByLabelText("Tags"), "full-time{Enter}");
    expect(onChange).toHaveBeenLastCalledWith({
      ...emptyScope(),
      tags: ["full-time"],
    });
  });
});
