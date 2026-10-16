import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { SCHEMAS } from "./schema-form/fixtures";
import { RuleDrawer } from "./RuleDrawer";

const maxLoad = {
  key: "max_load",
  version: 1,
  title: "Maximum workload",
  description: "Caps how much one resource does per day, week or schedule.",
  soft_only: false,
  params_schema: SCHEMAS.max_load,
};
const schedule = {
  id: "s1",
  name: "T1",
  timezone: "UTC",
  start_date: "2026-01-12",
  end_date: "2026-01-16",
  day_parts: { version: 1, parts: [] },
};

function api(onPost: (body: unknown) => Response) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST")
        return Promise.resolve(onPost(JSON.parse(init.body as string)));
      if (url.endsWith("/schedules/s1"))
        return Promise.resolve(jsonResponse(schedule));
      if (url.includes("resource-types"))
        return Promise.resolve(
          jsonResponse([
            {
              id: "t1",
              key: "lecturer",
              name: "Lecturer",
              kind: "person",
              attribute_schema: { version: 1, attributes: [] },
            },
          ]),
        );
      return Promise.resolve(jsonResponse([]));
    }),
  );
}

describe("RuleDrawer", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("saves a soft max_load scoped to a tag", async () => {
    const bodies: unknown[] = [];
    api((body) => {
      bodies.push(body);
      return jsonResponse(
        {
          ...(body as object),
          id: "c1",
          schedule_id: "s1",
          summary: "At most 2 activities per day",
        },
        201,
      );
    });
    const onOpenChange = vi.fn();
    renderWithProviders(
      <RuleDrawer
        scheduleId="s1"
        template={maxLoad}
        rule={null}
        open
        onOpenChange={onOpenChange}
      />,
    );
    await userEvent.selectOptions(
      await screen.findByLabelText("Period"),
      "day",
    );
    await userEvent.type(screen.getByLabelText("Max activities"), "2");
    await userEvent.click(screen.getByLabelText("Soft — prefer"));
    await userEvent.clear(screen.getByLabelText("Weight"));
    await userEvent.type(screen.getByLabelText("Weight"), "40");
    await userEvent.type(screen.getByLabelText("Tags"), "full-time{Enter}");
    await userEvent.click(screen.getByRole("button", { name: "Save rule" }));
    expect(bodies).toEqual([
      {
        name: "Maximum workload",
        template_key: "max_load",
        template_version: 1,
        params: { period: "day", max_count: 2 },
        scope: {
          resource_type_ids: [],
          tags: ["full-time"],
          attrs: [],
          resource_ids: [],
          series_ids: [],
        },
        hard: false,
        weight: 40,
        enabled: true,
      },
    ]);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("keeps the drawer open on 404", async () => {
    api(
      () =>
        new Response(
          JSON.stringify({
            title: "Not Found",
            status: 404,
            detail: "Unknown series",
          }),
          {
            status: 404,
            headers: { "Content-Type": "application/problem+json" },
          },
        ),
    );
    const onOpenChange = vi.fn();
    renderWithProviders(
      <RuleDrawer
        scheduleId="s1"
        template={maxLoad}
        rule={null}
        open
        onOpenChange={onOpenChange}
      />,
    );
    await userEvent.selectOptions(
      await screen.findByLabelText("Period"),
      "day",
    );
    await userEvent.type(screen.getByLabelText("Max activities"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Save rule" }));
    expect(await screen.findByText(/no longer exists/)).toBeInTheDocument();
    expect(screen.getByLabelText("Max activities")).toHaveValue("2");
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("blocks a missing required setting before calling the API", async () => {
    const onPost = vi.fn(() => jsonResponse({}, 201));
    api(onPost);
    renderWithProviders(
      <RuleDrawer
        scheduleId="s1"
        template={maxLoad}
        rule={null}
        open
        onOpenChange={vi.fn()}
      />,
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Save rule" }),
    );
    expect(await screen.findByText("Required")).toBeInTheDocument();
    expect(onPost).not.toHaveBeenCalled();
  });
});
