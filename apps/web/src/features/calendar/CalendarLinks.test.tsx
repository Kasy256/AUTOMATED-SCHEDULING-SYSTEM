import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { CalendarLinks } from "./CalendarLinks";

const feed = (id: string, revoked: string | null = null) => ({
  id,
  resource_id: "R1",
  created_at: "2026-01-10T08:00:00Z",
  revoked_at: revoked,
});

function api(feeds: unknown[], selfStatus = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url.includes("/me/calendar-feeds") && selfStatus !== 200)
        return Promise.resolve(
          jsonResponse({ title: "Not Found", status: selfStatus }, selfStatus),
        );
      if (init?.method === "POST")
        return Promise.resolve(
          jsonResponse({
            ...feed("f9"),
            url: "https://x/api/v1/calendar/tok.ics",
          }),
        );
      return Promise.resolve(jsonResponse(feeds));
    }),
  );
}

describe("CalendarLinks", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the link once", async () => {
    api([feed("f1")]);
    const { unmount } = renderWithProviders(<CalendarLinks resourceId="R1" />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Create calendar link" }),
    );
    expect(await screen.findByLabelText("Calendar link")).toHaveValue(
      "https://x/api/v1/calendar/tok.ics",
    );
    expect(screen.getByText(/You won't see it again/)).toBeInTheDocument();
    unmount();
    renderWithProviders(<CalendarLinks resourceId="R1" />);
    expect(
      await screen.findByRole("button", { name: "Create calendar link" }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Calendar link")).toBeNull();
  });

  it("keeps revoked links listed without a revoke button", async () => {
    api([feed("f1", "2026-01-11T08:00:00Z")]);
    renderWithProviders(<CalendarLinks resourceId="R1" />);
    expect(await screen.findByText(/^Revoked/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Revoke" })).toBeNull();
  });

  it("tells an unlinked person to ask an admin", async () => {
    api([], 404);
    renderWithProviders(<CalendarLinks />);
    expect(
      await screen.findByText(
        "Your account isn't linked to anyone on a timetable yet. Ask an organisation admin to link it.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Create calendar link" }),
    ).toBeNull();
  });
});
