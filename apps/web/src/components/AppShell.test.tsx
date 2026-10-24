import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as auth from "@/lib/auth/AuthProvider";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { AppShell } from "./AppShell";

function mockAuth(roles: ("org_admin" | "planner" | "viewer")[]) {
  vi.spyOn(auth, "useAuth").mockReturnValue({
    status: "signedIn",
    me: {
      user_id: "u",
      email: "a@b.c",
      name: "Ada",
      organisation_id: "o1",
      roles,
      platform_admin_session: false,
      organisations: [{ organisation_id: "o1", name: "ISBAT" }],
    },
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganisation: vi.fn(),
    adoptSession: vi.fn(),
    can: (action) =>
      action === "members.manage" ? roles.includes("org_admin") : true,
  });
}

describe("AppShell", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse([
            {
              id: "s1",
              name: "Term 1 2026",
              timezone: "Africa/Kampala",
              start_date: "2026-01-12",
              end_date: "2026-01-16",
              day_parts: { version: 1, parts: [] },
            },
          ]),
        ),
      ),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows schedule pages for the active schedule and organisation pages", async () => {
    mockAuth(["org_admin"]);
    renderWithProviders(<AppShell />, {
      route: "/schedules/s1/rules",
      path: "/schedules/:scheduleId/*",
    });
    expect(await screen.findByRole("link", { name: "Rules" })).toHaveAttribute(
      "href",
      "/schedules/s1/rules",
    );
    expect(screen.getByRole("link", { name: "Members" })).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: /Term 1 2026/ }),
    ).toBeInTheDocument();
  });

  it("hides Members from planners", async () => {
    mockAuth(["planner"]);
    renderWithProviders(<AppShell />, { route: "/resources" });
    expect(
      await screen.findByRole("link", { name: "Resources" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Members" })).toBeNull();
  });
  it("keeps the phone navigation open while its menus are used", async () => {
    mockAuth(["org_admin"]);
    renderWithProviders(<AppShell />, { route: "/resources" });
    await userEvent.click(
      screen.getByRole("button", { name: "Open navigation" }),
    );
    const sheet = await screen.findByRole("dialog");
    await userEvent.click(within(sheet).getByRole("button", { name: /ISBAT/ }));
    // The open menu hides everything else from assistive tech, so look past aria-hidden.
    expect(screen.getByRole("dialog", { hidden: true })).toBeInTheDocument();
    expect(
      await screen.findByRole("menuitem", { name: "Sign out" }),
    ).toBeInTheDocument();
  });
});
