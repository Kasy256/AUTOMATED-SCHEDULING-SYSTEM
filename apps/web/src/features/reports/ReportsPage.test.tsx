import { screen, within } from "@testing-library/react";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { ReportsPage } from "./ReportsPage";

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
const resource = (id: string, type: string, code: string, name: string) => ({
  id,
  resource_type_id: type,
  code,
  name,
  tags: [],
  attributes: {},
  capacity: null,
  size: null,
  concurrency: 1,
  user_id: null,
});
const resources = [
  resource("L1", "tl", "L001", "Kato"),
  resource("R1", "tr", "LH3", "Hall 3"),
];
const activities = [
  {
    id: "a1",
    schedule_id: "s1",
    demand_id: "d1",
    series_id: "d1",
    name: "CS 201",
    duration_minutes: 120,
    candidate_starts: [],
    requirements: [],
    attrs: {},
  },
];
const report = {
  version_id: "v2",
  utilisation: [
    {
      resource_id: "L1",
      type_key: "lecturer",
      assigned_minutes: 120,
      available_minutes: 240,
      ratio: 0.5,
    },
    {
      resource_id: "R1",
      type_key: "room",
      assigned_minutes: 240,
      available_minutes: 240,
      ratio: 1,
    },
  ],
  load: [
    {
      resource_id: "L1",
      activities: 1,
      minutes: 120,
      busiest_day: "2026-01-12",
      busiest_day_minutes: 120,
    },
  ],
  coverage_gaps: [
    { activity_id: "a1", role: "nurse", required_min: 2, assigned: 1 },
  ],
  fairness: [
    {
      type_key: "lecturer",
      resources: 2,
      min_minutes: 0,
      max_minutes: 240,
      mean_minutes: 120,
      spread: 240,
    },
  ],
};

function api(versions: unknown[]) {
  const reportUrls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/report")) {
        reportUrls.push(url);
        return Promise.resolve(jsonResponse(report));
      }
      if (url.endsWith("/versions"))
        return Promise.resolve(jsonResponse(versions));
      if (url.includes("resource-types"))
        return Promise.resolve(jsonResponse(types));
      if (url.endsWith("/resources"))
        return Promise.resolve(jsonResponse(resources));
      if (url.includes("/activities"))
        return Promise.resolve(jsonResponse(activities));
      return Promise.resolve(jsonResponse([]));
    }),
  );
  return reportUrls;
}

const route = {
  route: "/schedules/s1/reports",
  path: "/schedules/:scheduleId/reports",
};

describe("ReportsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the four reports", async () => {
    api([summary(1, "published"), summary(2, "draft")]);
    renderWithProviders(<ReportsPage />, route);
    for (const name of [
      "Utilisation",
      "Load per person",
      "Coverage gaps",
      "Fairness spread",
    ])
      expect(await screen.findByRole("heading", { name })).toBeInTheDocument();
    expect(await screen.findByText("100%")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "nurse" })).toBeInTheDocument();
    const fairness = screen.getByRole("table", { name: "Fairness spread" });
    expect(
      within(fairness).getAllByRole("cell", { name: "4.0 h" }),
    ).toHaveLength(2); // max and spread
  });

  it("defaults to the newest published version", async () => {
    const urls = api([summary(1, "published"), summary(2, "draft")]);
    renderWithProviders(<ReportsPage />, route);
    await screen.findByRole("heading", { name: "Utilisation" });
    await vi.waitFor(() => {
      expect(urls[0]).toBe("/api/v1/solution-versions/v1/report");
    });
  });

  it("defaults to the newest draft", async () => {
    const urls = api([summary(1, "draft"), summary(2, "draft")]);
    renderWithProviders(<ReportsPage />, route);
    await vi.waitFor(() => {
      expect(urls[0]).toBe("/api/v1/solution-versions/v2/report");
    });
  });
});
