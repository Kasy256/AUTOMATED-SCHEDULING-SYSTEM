import { screen, within } from "@testing-library/react";

import * as auth from "@/lib/auth/AuthProvider";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { VersionsPage } from "./VersionsPage";

const summary = (
  number: number,
  status: string,
  extra: Record<string, unknown> = {},
) => ({
  id: `v${String(number)}`,
  schedule_id: "s1",
  number,
  status,
  solver_status: "OPTIMAL",
  hard_violations: 0,
  soft_total: 10 * number,
  created_at: "2026-01-0" + String(number) + "T08:00:00Z",
  published_at: status === "published" ? "2026-01-05T08:00:00Z" : null,
  archived_at: null,
  parent_version_id: null,
  solve_run_id: `r${String(number)}`,
  ...extra,
});
const schedule = {
  id: "s1",
  name: "T1",
  timezone: "Africa/Kampala",
  start_date: "2026-01-12",
  end_date: "2026-01-23",
  day_parts: { version: 1, parts: [] },
};

function api(versions: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/schedules/s1"))
        return Promise.resolve(jsonResponse(schedule));
      if (url.endsWith("/versions"))
        return Promise.resolve(jsonResponse(versions));
      if (url.endsWith("/solves"))
        return Promise.resolve(jsonResponse([{ id: "r3", kind: "repair" }]));
      return Promise.resolve(jsonResponse([]));
    }),
  );
}

function signedIn(manage: boolean) {
  vi.spyOn(auth, "useAuth").mockReturnValue({
    status: "signedIn",
    me: null,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganisation: vi.fn(),
    adoptSession: vi.fn(),
    can: (a) => (a === "config.manage" ? manage : true),
  });
}

const route = {
  route: "/schedules/s1/versions",
  path: "/schedules/:scheduleId/versions",
};

describe("VersionsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists versions newest first with origin and compare targets", async () => {
    signedIn(true);
    api([summary(1, "archived"), summary(2, "published"), summary(3, "draft")]);
    renderWithProviders(<VersionsPage />, route);
    const rows = (await screen.findAllByRole("row")).map((r) => within(r));
    expect(rows[1]?.getByText("Version 3 · draft")).toBeInTheDocument();
    expect(rows[1]?.getByText("Repair")).toBeInTheDocument();
    expect(rows[1]?.getByRole("link", { name: "Compare" })).toHaveAttribute(
      "href",
      "/schedules/s1/versions/v2/compare/v3",
    );
    expect(
      screen.getByRole("button", { name: "Repair published timetable" }),
    ).toBeInTheDocument();
  });

  it("without a published version: no Repair, compare with the previous version, none for v1", async () => {
    signedIn(true);
    api([summary(1, "draft"), summary(2, "draft")]);
    renderWithProviders(<VersionsPage />, route);
    const rows = (await screen.findAllByRole("row")).map((r) => within(r));
    expect(rows[1]?.getByRole("link", { name: "Compare" })).toHaveAttribute(
      "href",
      "/schedules/s1/versions/v1/compare/v2",
    );
    expect(rows[2]?.queryByRole("link", { name: "Compare" })).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Repair published timetable" }),
    ).toBeNull();
  });

  it("viewers see no write actions", async () => {
    signedIn(false);
    api([summary(1, "published"), summary(2, "draft")]);
    renderWithProviders(<VersionsPage />, route);
    await screen.findAllByRole("row");
    expect(screen.queryByRole("button", { name: /Publish/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Archive/ })).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Repair published timetable" }),
    ).toBeNull();
    expect(screen.getAllByRole("button", { name: "Export CSV" })).toHaveLength(
      2,
    );
  });
});
