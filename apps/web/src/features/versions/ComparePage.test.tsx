import { screen } from "@testing-library/react";

import * as auth from "@/lib/auth/AuthProvider";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { ComparePage } from "./ComparePage";

const schedule = {
  id: "s1",
  name: "T1",
  timezone: "Africa/Kampala",
  start_date: "2026-01-12",
  end_date: "2026-01-23",
  day_parts: { version: 1, parts: [] },
};
const summary = (number: number, status: string) => ({
  id: `v${String(number)}`,
  schedule_id: "s1",
  number,
  status,
  solver_status: "OPTIMAL",
  hard_violations: 0,
  soft_total: 0,
  created_at: "2026-01-01T00:00:00Z",
  published_at: null,
  archived_at: null,
  parent_version_id: null,
  solve_run_id: `r${String(number)}`,
});
const resources = [
  {
    id: "R1",
    resource_type_id: "tr",
    code: "LH3",
    name: "Hall 3",
    tags: [],
    attributes: {},
    capacity: 90,
    size: null,
    concurrency: 1,
    user_id: null,
  },
];
const at = (start: string) => ({
  activity_id: "a1",
  activity_name: "CS 201",
  start_at: start,
  end_at: start,
  resources: { room: ["R1"] },
});

function api(diff: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/diff/")) return Promise.resolve(jsonResponse(diff));
      if (url.endsWith("/schedules/s1"))
        return Promise.resolve(jsonResponse(schedule));
      if (url.endsWith("/versions"))
        return Promise.resolve(
          jsonResponse([summary(2, "published"), summary(3, "draft")]),
        );
      if (url.endsWith("/resources"))
        return Promise.resolve(jsonResponse(resources));
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
  route: "/schedules/s1/versions/v2/compare/v3",
  path: "/schedules/:scheduleId/versions/:a/compare/:b",
};

describe("ComparePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists each change with times and resource codes", async () => {
    signedIn(true);
    api({
      added: [],
      removed: [],
      reassigned: [],
      moved: [
        {
          activity_id: "a1",
          before: at("2026-01-12T06:00:00Z"),
          after: at("2026-01-13T06:00:00Z"),
        },
      ],
    });
    renderWithProviders(<ComparePage />, route);
    expect(
      await screen.findByRole("heading", { name: "Moved (1)" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Reassigned (0)" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("1 moved · 0 reassigned · 0 added · 0 removed"),
    ).toBeInTheDocument();
    expect(screen.getByText("CS 201")).toBeInTheDocument();
    expect(screen.getAllByText(/LH3/)).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Publish" })).toBeInTheDocument();
  });

  it("says when there are no differences", async () => {
    signedIn(false);
    api({ added: [], removed: [], moved: [], reassigned: [] });
    renderWithProviders(<ComparePage />, route);
    expect(await screen.findByText("No differences")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Publish" })).toBeNull();
  });
});
