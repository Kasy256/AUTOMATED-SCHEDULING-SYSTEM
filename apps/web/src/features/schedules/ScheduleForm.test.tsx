import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ScheduleForm } from "./ScheduleForm";

describe("ScheduleForm", () => {
  it("sends dates, timezone and day parts in minutes", async () => {
    const onSubmit = vi.fn(() => Promise.resolve());
    render(
      <ScheduleForm
        submitLabel="Create schedule"
        defaultValues={{
          name: "",
          timezone: "Africa/Kampala",
          start_date: "",
          end_date: "",
          day_parts: [],
        }}
        onSubmit={onSubmit}
      />,
    );
    await userEvent.type(screen.getByLabelText("Name"), "Term 1 2026");
    await userEvent.type(screen.getByLabelText("Start date"), "2026-01-12");
    await userEvent.type(screen.getByLabelText("End date"), "2026-01-16");
    await userEvent.click(
      screen.getByRole("button", { name: "Add part of day" }),
    );
    await userEvent.type(screen.getByLabelText("Part 1 name"), "morning");
    await userEvent.type(screen.getByLabelText("Part 1 start"), "08:00");
    await userEvent.type(screen.getByLabelText("Part 1 end"), "13:00");
    await userEvent.click(
      screen.getByRole("button", { name: "Create schedule" }),
    );
    expect(onSubmit).toHaveBeenCalledWith({
      name: "Term 1 2026",
      timezone: "Africa/Kampala",
      start_date: "2026-01-12",
      end_date: "2026-01-16",
      day_parts: {
        version: 1,
        parts: [{ name: "morning", start_minute: 480, end_minute: 780 }],
      },
    });
  });

  it("rejects an end date before the start", async () => {
    const onSubmit = vi.fn(() => Promise.resolve());
    render(
      <ScheduleForm
        submitLabel="Save"
        defaultValues={{
          name: "T",
          timezone: "UTC",
          start_date: "2026-01-16",
          end_date: "2026-01-12",
          day_parts: [],
        }}
        onSubmit={onSubmit}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(
      await screen.findByText("End date must be on or after the start date"),
    ).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
