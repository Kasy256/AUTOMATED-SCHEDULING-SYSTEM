import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { DemandDialog } from "./DemandDialog";

const slotTemplates = [
  {
    id: "st1",
    schedule_id: "s1",
    name: "Teaching periods",
    definition: {
      version: 1,
      slots: [
        {
          label: "P1",
          weekdays: [0, 1, 2, 3, 4],
          start_minute: 540,
          duration_minutes: 120,
        },
      ],
    },
  },
];
const types = [
  {
    id: "t1",
    key: "lecturer",
    name: "Lecturer",
    kind: "person",
    attribute_schema: { version: 1, attributes: [] },
  },
];

describe("DemandDialog", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a weekly session demand with one requirement", async () => {
    const posted: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          posted.push(JSON.parse(init.body as string));
          return Promise.resolve(
            jsonResponse({ id: "d1", pins_removed: 0, activity_count: 2 }, 201),
          );
        }
        if (url.includes("slot-templates"))
          return Promise.resolve(jsonResponse(slotTemplates));
        if (url.includes("resource-types"))
          return Promise.resolve(jsonResponse(types));
        return Promise.resolve(jsonResponse([]));
      }),
    );
    const onOpenChange = vi.fn();
    renderWithProviders(
      <DemandDialog
        scheduleId="s1"
        editing={null}
        open
        onOpenChange={onOpenChange}
      />,
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Name"), "CS 201");
    await within(dialog).findByRole("option", { name: "Teaching periods" });
    await userEvent.clear(within(dialog).getByLabelText("Sessions per week"));
    await userEvent.type(
      within(dialog).getByLabelText("Sessions per week"),
      "2",
    );
    await userEvent.type(
      within(dialog).getByLabelText("Requirement 1 role"),
      "lecturer",
    );
    await within(dialog).findByRole("option", { name: "Lecturer" });
    await userEvent.selectOptions(
      within(dialog).getByLabelText("Requirement 1 resource type"),
      "t1",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Save demand" }),
    );
    await vi.waitFor(() => {
      expect(posted).toEqual([
        {
          name: "CS 201",
          slot_template_id: "st1",
          spec: {
            kind: "session",
            sessions_per_week: 2,
            duration_minutes: null,
            slot_labels: null,
            requirements: [
              {
                role: "lecturer",
                resource_type_id: "t1",
                tags: [],
                attrs: [],
                count_min: 1,
                count_max: 1,
                fixed_resource_ids: [],
                hard: true,
                weight: 0,
              },
            ],
            attrs: {},
          },
        },
      ]);
    });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
