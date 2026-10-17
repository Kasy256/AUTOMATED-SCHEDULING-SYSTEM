import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { SlotTemplateDialog } from "./SlotTemplateDialog";

describe("SlotTemplateDialog", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a template with weekday slots in minutes", async () => {
    const posted: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        if (init?.method === "POST")
          posted.push(JSON.parse(init.body as string));
        return Promise.resolve(jsonResponse({ id: "st1" }, 201));
      }),
    );
    const onOpenChange = vi.fn();
    renderWithProviders(
      <SlotTemplateDialog
        scheduleId="s1"
        editing={null}
        open
        onOpenChange={onOpenChange}
      />,
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(
      within(dialog).getByLabelText("Name"),
      "Teaching periods",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Add slot" }),
    );
    await userEvent.type(within(dialog).getByLabelText("Slot 1 label"), "P1");
    for (const day of ["Mon", "Tue", "Wed", "Thu", "Fri"])
      await userEvent.click(
        within(dialog).getByRole("checkbox", { name: day }),
      );
    await userEvent.type(
      within(dialog).getByLabelText("Slot 1 start"),
      "08:00",
    );
    await userEvent.type(
      within(dialog).getByLabelText("Slot 1 duration (minutes)"),
      "120",
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await vi.waitFor(() => {
      expect(posted).toEqual([
        {
          name: "Teaching periods",
          definition: {
            version: 1,
            slots: [
              {
                label: "P1",
                weekdays: [0, 1, 2, 3, 4],
                start_minute: 480,
                duration_minutes: 120,
              },
            ],
          },
        },
      ]);
    });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("requires at least one weekday per slot", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse({}))),
    );
    renderWithProviders(
      <SlotTemplateDialog
        scheduleId="s1"
        editing={null}
        open
        onOpenChange={vi.fn()}
      />,
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Name"), "T");
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Add slot" }),
    );
    await userEvent.type(within(dialog).getByLabelText("Slot 1 label"), "P1");
    await userEvent.type(
      within(dialog).getByLabelText("Slot 1 start"),
      "08:00",
    );
    await userEvent.type(
      within(dialog).getByLabelText("Slot 1 duration (minutes)"),
      "60",
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(
      await within(dialog).findByText("Pick at least one day"),
    ).toBeInTheDocument();
  });
});
