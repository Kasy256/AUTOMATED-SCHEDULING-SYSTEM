import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { PrintPage } from "./PrintPage";

const schedule = {
  id: "s1",
  name: "Term 1",
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
  resource("L2", "tl", "L002", "Nalu"),
  resource("R1", "tr", "LH3", "Hall 3"),
];
const version = {
  id: "v1",
  schedule_id: "s1",
  number: 1,
  status: "published",
  solver_status: "OPTIMAL",
  hard_violations: 0,
  soft_total: 0,
  created_at: "2026-01-01T00:00:00Z",
  published_at: null,
  archived_at: null,
  parent_version_id: null,
  solve_run_id: "r1",
  score: {},
  assignments: [
    {
      activity_id: "a1",
      activity_name: "CS 201",
      start_at: "2026-01-12T06:00:00Z",
      end_at: "2026-01-12T08:00:00Z",
      resources: { lecturer: ["L1"], room: ["R1"] },
    },
    {
      activity_id: "a2",
      activity_name: "CS 202",
      start_at: "2026-01-19T06:00:00Z",
      end_at: "2026-01-19T08:00:00Z",
      resources: { lecturer: ["L1"], room: ["R1"] },
    },
  ],
};
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

describe("PrintPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("prints a sheet per resource per week and lists idle resources", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.endsWith("/schedules/s1"))
          return Promise.resolve(jsonResponse(schedule));
        if (url.includes("resource-types"))
          return Promise.resolve(jsonResponse(types));
        if (url.endsWith("/resources"))
          return Promise.resolve(jsonResponse(resources));
        if (url.includes("slot-templates"))
          return Promise.resolve(jsonResponse(slotTemplates));
        if (url.endsWith("/solution-versions/v1"))
          return Promise.resolve(jsonResponse(version));
        return Promise.resolve(jsonResponse([]));
      }),
    );
    const { container } = renderWithProviders(<PrintPage />, {
      route: "/schedules/s1/versions/v1/print",
      path: "/schedules/:scheduleId/versions/:versionId/print",
    });
    expect(
      await screen.findAllByRole("heading", { name: "Kato (L001)" }),
    ).toHaveLength(2);
    expect(container.querySelectorAll("section.sheet")).toHaveLength(2);
    expect(
      screen.getByText("Term 1 · Week of 12 Jan · Version 1 (published)"),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("rowheader", { name: "P1" })).toHaveLength(2);
    expect(
      screen.getByText("Nothing scheduled: Nalu (L002)"),
    ).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Resource type"), "tr");
    expect(
      await screen.findAllByRole("heading", { name: "Hall 3 (LH3)" }),
    ).toHaveLength(2);
  });
});
