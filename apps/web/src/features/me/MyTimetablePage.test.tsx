import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { MyTimetablePage } from "./MyTimetablePage";

const item = (id: string, start: string, end: string) => ({
  activity_id: id,
  activity_name: id,
  start_at: start,
  end_at: end,
  resources: { lecturer: ["L1"], room: ["R1"] },
  version_id: "v1",
  schedule_id: "s1",
  schedule_name: "Term 1",
  schedule_timezone: "Africa/Kampala",
  roles: ["lecturer"],
});

function api(items: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(
        jsonResponse(url.endsWith("/me/assignments") ? items : []),
      ),
    ),
  );
}

describe("MyTimetablePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("lists upcoming days and reveals past ones", async () => {
    vi.useFakeTimers({
      shouldAdvanceTime: true,
      now: new Date("2026-01-13T00:00:00Z"),
    });
    api([
      item("Old class", "2026-01-12T06:00:00Z", "2026-01-12T08:00:00Z"),
      item("CS 201", "2026-01-14T06:00:00Z", "2026-01-14T08:00:00Z"),
    ]);
    renderWithProviders(<MyTimetablePage />);
    expect(
      await screen.findByRole("heading", { name: "Wed 14 Jan" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/CS 201/)).toBeInTheDocument();
    expect(screen.getByText("09:00–11:00")).toBeInTheDocument();
    expect(screen.queryByText(/Old class/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Show past" }));
    expect(await screen.findByText(/Old class/)).toBeInTheDocument();
  });

  it("says when nothing is scheduled", async () => {
    api([]);
    renderWithProviders(<MyTimetablePage />);
    expect(
      await screen.findByText("Nothing scheduled for you yet."),
    ).toBeInTheDocument();
  });
});
