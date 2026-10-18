import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { localInputNow, toUtcIso } from "@/lib/time";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { RepairButton } from "./RepairDialog";

function api(reply: Response) {
  const calls: { url: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST")
        calls.push({ url, body: JSON.parse(init.body as string) as unknown });
      return Promise.resolve(reply);
    }),
  );
  return calls;
}

async function open() {
  renderWithProviders(
    <RepairButton scheduleId="s1" timeZone="Africa/Kampala" />,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Repair published timetable" }),
  );
}

describe("RepairButton", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("asks for a repair that keeps everything before the chosen time", async () => {
    const calls = api(jsonResponse({ id: "r9" }, 202));
    await open();
    const keep = screen.getByLabelText("Keep everything before");
    expect(keep).toHaveValue(localInputNow("Africa/Kampala"));
    await userEvent.click(screen.getByRole("button", { name: "Start repair" }));
    await vi.waitFor(() => {
      expect(calls[0]?.url).toBe("/api/v1/schedules/s1/repairs");
    });
    expect(calls[0]?.body).toMatchObject({
      freeze_before: toUtcIso(
        (keep as HTMLInputElement).value,
        "Africa/Kampala",
      ),
    });
  });

  it("explains that repair needs a stability rule", async () => {
    api(
      jsonResponse(
        {
          title: "Unprocessable",
          errors: [
            {
              loc: ["body"],
              msg: "the schedule needs an enabled stability rule to repair",
              type: "value_error",
            },
          ],
        },
        422,
      ),
    );
    await open();
    await userEvent.click(screen.getByRole("button", { name: "Start repair" }));
    expect(
      await screen.findByText(
        "Repair needs a Stability rule — add one in Rules.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Rules" })).toHaveAttribute(
      "href",
      "/schedules/s1/rules",
    );
  });

  it("says when nothing is published yet", async () => {
    api(jsonResponse({ title: "Conflict", status: 409 }, 409));
    await open();
    await userEvent.click(screen.getByRole("button", { name: "Start repair" }));
    expect(
      await screen.findByText("There is no published timetable to repair yet."),
    ).toBeInTheDocument();
  });
});
