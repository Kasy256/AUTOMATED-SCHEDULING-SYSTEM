import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as auth from "@/lib/auth/AuthProvider";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { PlannerPage } from "./PlannerPage";

const schedule = {
  id: "s1",
  name: "T1",
  timezone: "Africa/Kampala",
  start_date: "2026-01-12",
  end_date: "2026-01-23",
  day_parts: { version: 1, parts: [] },
};
const types = [
  {
    id: "tl",
    key: "lecturer",
    name: "Lecturer",
    kind: "person",
    attribute_schema: { version: 1, attributes: [] },
  },
  {
    id: "tr",
    key: "room",
    name: "Room",
    kind: "space",
    attribute_schema: { version: 1, attributes: [] },
  },
];
const resources = [
  {
    id: "L1",
    resource_type_id: "tl",
    code: "L001",
    name: "Kato",
    tags: [],
    attributes: {},
    capacity: null,
    size: null,
    concurrency: 1,
    user_id: null,
  },
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
const activities = [
  {
    id: "a1",
    schedule_id: "s1",
    demand_id: "d1",
    series_id: "d1",
    name: "CS 201",
    duration_minutes: 120,
    candidate_starts: ["2026-01-12T06:00:00Z", "2026-01-13T06:00:00Z"],
    requirements: [],
    attrs: {},
  },
];
const slotTemplates = [
  {
    id: "st",
    schedule_id: "s1",
    name: "Periods",
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
const versionSummary = {
  id: "v1",
  schedule_id: "s1",
  number: 1,
  status: "draft",
  solver_status: "OPTIMAL",
  hard_violations: 0,
  soft_total: 3,
  created_at: "2026-01-01T00:00:00Z",
  published_at: null,
  archived_at: null,
  parent_version_id: null,
  solve_run_id: "r1",
};
const version = {
  ...versionSummary,
  score: { hard_violations: 0, soft_total: 3, terms: [], violations: [] },
  assignments: [
    {
      activity_id: "a1",
      activity_name: "CS 201",
      start_at: "2026-01-12T06:00:00Z",
      end_at: "2026-01-12T08:00:00Z",
      resources: { lecturer: ["L1"], room: ["R1"] },
    },
  ],
};

export function boardApi(overrides: Record<string, unknown> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      for (const [suffix, body] of Object.entries(overrides))
        if (url.includes(suffix)) return Promise.resolve(jsonResponse(body));
      if (url.endsWith("/schedules/s1"))
        return Promise.resolve(jsonResponse(schedule));
      if (url.includes("resource-types"))
        return Promise.resolve(jsonResponse(types));
      if (url.endsWith("/resources"))
        return Promise.resolve(jsonResponse(resources));
      if (url.includes("/activities"))
        return Promise.resolve(jsonResponse(activities));
      if (url.includes("slot-templates"))
        return Promise.resolve(jsonResponse(slotTemplates));
      if (url.endsWith("/versions"))
        return Promise.resolve(jsonResponse([versionSummary]));
      if (url.includes("/solution-versions/v1"))
        return Promise.resolve(jsonResponse(version));
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
  route: "/schedules/s1/planner",
  path: "/schedules/:scheduleId/planner",
};

describe("PlannerPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows the week's slot columns and the item in its lecturer's row", async () => {
    signedIn(true);
    boardApi();
    renderWithProviders(<PlannerPage />, route);
    expect(
      await screen.findByRole("columnheader", { name: "Mon P1" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Tue P1" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("gridcell", { name: "Kato, Mon P1: CS 201" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "CS 201, LH3" }),
    ).toBeInTheDocument();
  });

  it("switches tabs to rooms", async () => {
    signedIn(true);
    boardApi();
    renderWithProviders(<PlannerPage />, route);
    await userEvent.click(await screen.findByRole("tab", { name: "Room" }));
    expect(
      await screen.findByRole("gridcell", { name: "Hall 3, Mon P1: CS 201" }),
    ).toBeInTheDocument();
  });

  it("shows an empty-week message", async () => {
    signedIn(true);
    boardApi();
    renderWithProviders(<PlannerPage />, route);
    await userEvent.click(
      await screen.findByRole("button", { name: "Next week" }),
    );
    expect(
      await screen.findByText("Nothing is scheduled this week."),
    ).toBeInTheDocument();
  });

  it("asks for a solve when there is no version", async () => {
    signedIn(true);
    boardApi({ "/versions": [] });
    renderWithProviders(<PlannerPage />, route);
    expect(
      await screen.findByText("Solve to create the first timetable"),
    ).toBeInTheDocument();
  });

  it("viewers cannot drag", async () => {
    signedIn(false);
    boardApi();
    renderWithProviders(<PlannerPage />, route);
    const item = await screen.findByRole("button", { name: "CS 201, LH3" });
    expect(item).not.toHaveAttribute("aria-roledescription", "draggable");
    expect(screen.queryByRole("button", { name: "Solve" })).toBeNull();
  });
});
