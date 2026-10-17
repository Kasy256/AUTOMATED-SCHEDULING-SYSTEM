const DAYS = [
  "2026-01-12",
  "2026-01-13",
  "2026-01-14",
  "2026-01-15",
  "2026-01-16",
  "2026-01-19",
  "2026-01-20",
  "2026-01-21",
  "2026-01-22",
  "2026-01-23",
];
const STARTS = DAYS.flatMap((d) =>
  ["06:00", "08:30", "11:00", "13:30"].map((t) => `${d}T${t}:00.000Z`),
);
const id = (prefix: string, n: number) =>
  `${prefix}${String(n).padStart(11, "0")}`.replace(
    /^(.{8})(.{4})(.{4})(.{4})(.{12}).*$/,
    "$1-$2-$3-$4-$5",
  );

export function syntheticBoard() {
  const lecturers = Array.from({ length: 150 }, (_, i) => ({
    id: id("10000000000000000000", i),
    resource_type_id: "type-lecturer",
    code: `L${String(i).padStart(3, "0")}`,
    name: `Lecturer ${String(i)}`,
    tags: [],
    attributes: {},
    capacity: null,
    size: null,
    concurrency: 1,
    user_id: null,
  }));
  const activities = Array.from({ length: 2000 }, (_, i) => ({
    id: id("20000000000000000000", i),
    schedule_id: "s1",
    demand_id: null,
    series_id: null,
    name: `Class ${String(i)}`,
    duration_minutes: 120,
    candidate_starts: STARTS,
    requirements: [],
    attrs: {},
  }));
  const assignments = activities.map((a, i) => ({
    activity_id: a.id,
    activity_name: a.name,
    start_at: STARTS[i % STARTS.length],
    end_at: STARTS[i % STARTS.length],
    resources: {
      lecturer: [
        lecturers[Math.floor(i / STARTS.length) % lecturers.length]?.id ?? "",
      ],
    },
  }));
  const summary = {
    id: "v1",
    schedule_id: "s1",
    number: 1,
    status: "draft",
    solver_status: "FEASIBLE",
    hard_violations: 0,
    soft_total: 0,
    created_at: "2026-01-01T00:00:00Z",
    published_at: null,
    archived_at: null,
    parent_version_id: null,
    solve_run_id: "r1",
  };
  return {
    "/api/v1/auth/refresh": {
      access_token: "t",
      token_type: "bearer",
      expires_in: 900,
      organisation_id: "o1",
    },
    "/api/v1/auth/me": {
      user_id: "u1",
      email: "perf@example.com",
      name: "Perf",
      organisation_id: "o1",
      roles: ["org_admin"],
      platform_admin_session: false,
      organisations: [{ organisation_id: "o1", name: "Perf org" }],
    },
    "/api/v1/schedules/s1": {
      id: "s1",
      name: "Perf",
      timezone: "Africa/Kampala",
      start_date: "2026-01-12",
      end_date: "2026-01-23",
      day_parts: { version: 1, parts: [] },
    },
    "/api/v1/schedules": [
      {
        id: "s1",
        name: "Perf",
        timezone: "Africa/Kampala",
        start_date: "2026-01-12",
        end_date: "2026-01-23",
        day_parts: { version: 1, parts: [] },
      },
    ],
    "/api/v1/resource-types": [
      {
        id: "type-lecturer",
        key: "lecturer",
        name: "Lecturer",
        kind: "person",
        attribute_schema: { version: 1, attributes: [] },
      },
    ],
    "/api/v1/resources": lecturers,
    "/api/v1/schedules/s1/activities": activities,
    "/api/v1/schedules/s1/slot-templates": [
      {
        id: "st",
        schedule_id: "s1",
        name: "Periods",
        definition: {
          version: 1,
          slots: [540, 690, 840, 990].map((m, i) => ({
            label: `P${String(i + 1)}`,
            weekdays: [0, 1, 2, 3, 4],
            start_minute: m,
            duration_minutes: 120,
          })),
        },
      },
    ],
    "/api/v1/schedules/s1/versions": [summary],
    "/api/v1/solution-versions/v1": {
      ...summary,
      score: { hard_violations: 0, soft_total: 0, terms: [], violations: [] },
      assignments,
    },
    explanation: {
      activity_id: activities[0]?.id,
      binding: [],
      truncated: false,
      alternatives: STARTS.map((s) => ({
        start_at: s,
        resources: assignments[0]?.resources ?? {},
        check: { valid: true, broken: [], penalties: [] },
      })),
    },
  };
}
