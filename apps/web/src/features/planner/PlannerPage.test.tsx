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

// An override body may carry `__status` to answer with an error.
function reply(body: unknown) {
  if (typeof body === "object" && body !== null && "__status" in body) {
    const { __status, ...rest } = body as { __status: number };
    return jsonResponse(rest, __status);
  }
  return jsonResponse(body);
}

const report = {
  version_id: "v1",
  utilisation: [],
  load: [],
  coverage_gaps: [],
  fairness: [],
};

export function boardApi(overrides: Record<string, unknown> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/solution-versions/v1/report"))
        return Promise.resolve(jsonResponse(report));
      for (const [suffix, body] of Object.entries(overrides))
        if (url.includes(suffix)) return Promise.resolve(reply(body));
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
  it("keyboard: arrow to the item and open its explanation", async () => {
    signedIn(true);
    boardApi({
      "/explanation": {
        activity_id: "a1",
        binding: [],
        alternatives: [],
        truncated: false,
      },
    });
    renderWithProviders(<PlannerPage />, route);
    const first = await screen.findByRole("gridcell", {
      name: "Kato, Mon P1: CS 201",
    });
    first.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(
      screen.getByRole("gridcell", { name: "Kato, Tue P1: empty" }),
    ).toHaveFocus();
    await userEvent.keyboard("{ArrowLeft}{Enter}");
    expect(
      await screen.findByRole("heading", { name: "CS 201" }),
    ).toBeInTheDocument();
  });

  describe("pending changes", () => {
    const explanation = {
      activity_id: "a1",
      binding: [],
      truncated: false,
      alternatives: [
        {
          start_at: "2026-01-13T06:00:00Z",
          resources: { lecturer: ["L1"], room: ["R1"] },
          check: { valid: true, broken: [], penalties: [] },
        },
      ],
    };

    async function movePending(overrides: Record<string, unknown> = {}) {
      signedIn(true);
      boardApi({ "/explanation": explanation, ...overrides });
      const view = renderWithProviders(<PlannerPage />, route);
      await userEvent.click(
        await screen.findByRole("button", { name: "CS 201, LH3" }),
      );
      await userEvent.click(
        await screen.findByRole("button", { name: "Move here" }),
      );
      expect(
        await screen.findByRole("region", { name: "Unsaved changes" }),
      ).toHaveTextContent("1 unsaved change");
      return view;
    }

    it("stays on the version the changes were made against", async () => {
      const versions: unknown[] = [versionSummary];
      const { queryClient } = await movePending({
        "/versions": versions,
        "/solution-versions/v2": { ...version, id: "v2", number: 2 },
      });
      versions.push({ ...versionSummary, id: "v2", number: 2 });
      await queryClient.invalidateQueries();
      await screen.findByRole("option", { name: "Version 2 · draft" });
      expect(
        screen.getByText(/^Version \d · draft/, { selector: "p" }),
      ).toHaveTextContent("Version 1 · draft");
      expect(
        screen.getByRole("region", { name: "Unsaved changes" }),
      ).toBeInTheDocument();
    });

    it("warns before the tab closes", async () => {
      await movePending();
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(true);
    });

    it("shows the server's reason when the draft is rejected", async () => {
      await movePending({
        "/drafts": {
          __status: 422,
          title: "Unprocessable",
          errors: [
            {
              loc: ["body", "changes"],
              msg: "Kato is double-booked on Tue P1",
              type: "conflict",
            },
          ],
        },
      });
      await userEvent.click(
        screen.getByRole("button", { name: "Save as draft" }),
      );
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Kato is double-booked on Tue P1",
      );
    });
  });

  it("keyboard: Tab reaches every item stacked in a cell", async () => {
    signedIn(true);
    const second = {
      activity_id: "a2",
      activity_name: "CS 202",
      start_at: "2026-01-12T06:00:00Z",
      end_at: "2026-01-12T08:00:00Z",
      resources: { lecturer: ["L1"], room: ["R1"] },
    };
    boardApi({
      "/explanation": {
        activity_id: "a2",
        binding: [],
        alternatives: [],
        truncated: false,
      },
      "/solution-versions/v1": {
        ...version,
        assignments: [...version.assignments, second],
      },
    });
    renderWithProviders(<PlannerPage />, route);
    const cell = await screen.findByRole("gridcell", {
      name: "Kato, Mon P1: CS 201, CS 202",
    });
    cell.focus();
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "CS 201, LH3" })).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "CS 202, LH3" })).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    expect(
      await screen.findByRole("heading", { name: "CS 202" }),
    ).toBeInTheDocument();
  });

  it("keyboard: the grid keeps a tab stop when the focused row scrolls away", async () => {
    signedIn(true);
    const many = Array.from({ length: 80 }, (_, i) => ({
      ...resources[0],
      id: `L${String(i + 1)}`,
      code: `L${String(i + 1).padStart(3, "0")}`,
      name: `Lecturer ${String(i + 1)}`,
    }));
    boardApi({ "/resources": [...many, resources[1]] });
    renderWithProviders(<PlannerPage />, route);
    const first = await screen.findByRole("gridcell", {
      name: /^Lecturer 1, Mon P1/,
    });
    first.focus();
    const scroller = first.closest<HTMLElement>(".overflow-auto");
    if (!scroller) throw new Error("no scroller");
    scroller.scrollTop = 3000;
    scroller.dispatchEvent(new Event("scroll"));
    await screen.findByRole("gridcell", { name: /^Lecturer 60, Mon P1/ });
    expect(
      document.querySelectorAll('[role="gridcell"][tabindex="0"]'),
    ).toHaveLength(1);
  });
});
