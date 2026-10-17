import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as auth from "@/lib/auth/AuthProvider";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { SCHEMAS } from "./schema-form/fixtures";
import { RulesPage } from "./RulesPage";

const templates = [
  {
    key: "max_load",
    version: 1,
    title: "Maximum workload",
    description: "Caps load.",
    soft_only: false,
    params_schema: SCHEMAS.max_load,
  },
  {
    key: "minimize_gaps",
    version: 1,
    title: "Compact days",
    description: "Penalises gaps.",
    soft_only: true,
    params_schema: SCHEMAS.minimize_gaps,
  },
];
const scope = {
  resource_type_ids: [],
  tags: [],
  attrs: [],
  resource_ids: [],
  series_ids: [],
};
const rules = [
  {
    id: "c1",
    schedule_id: "s1",
    name: "Max 2 a day",
    template_key: "max_load",
    template_version: 1,
    params: { period: "day", max_count: 2 },
    scope,
    hard: true,
    weight: 0,
    enabled: true,
    summary: "At most 2 activities per day",
  },
  {
    id: "c2",
    schedule_id: "s1",
    name: "Keep days compact",
    template_key: "minimize_gaps",
    template_version: 1,
    params: { per_minutes: 60 },
    scope,
    hard: false,
    weight: 35,
    enabled: true,
    summary: "Keep idle time short",
  },
];

describe("RulesPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("groups rules and toggles one off with a full PUT", async () => {
    vi.spyOn(auth, "useAuth").mockReturnValue({
      status: "signedIn",
      me: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganisation: vi.fn(),
      adoptSession: vi.fn(),
      can: () => true,
    });
    const puts: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (init?.method === "PUT") {
          puts.push(JSON.parse(init.body as string));
          return Promise.resolve(jsonResponse({ ...rules[1], enabled: false }));
        }
        if (url.includes("constraint-templates"))
          return Promise.resolve(jsonResponse(templates));
        if (url.includes("/constraints"))
          return Promise.resolve(jsonResponse(rules));
        if (url.endsWith("/schedules/s1"))
          return Promise.resolve(
            jsonResponse({
              id: "s1",
              name: "T",
              timezone: "UTC",
              start_date: "2026-01-12",
              end_date: "2026-01-16",
              day_parts: { version: 1, parts: [] },
            }),
          );
        return Promise.resolve(jsonResponse([]));
      }),
    );
    renderWithProviders(<RulesPage />, {
      route: "/schedules/s1/rules",
      path: "/schedules/:scheduleId/rules",
    });
    expect(
      await screen.findByText("Hard — must never break · 1"),
    ).toBeInTheDocument();
    expect(screen.getByText("Soft — avoid, weighted · 1")).toBeInTheDocument();
    expect(
      screen.getByText("At most 2 activities per day"),
    ).toBeInTheDocument();
    expect(screen.getByText("weight 35")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("switch", { name: "Enabled: Keep days compact" }),
    );
    await vi.waitFor(() => {
      expect(puts).toEqual([
        {
          name: "Keep days compact",
          template_key: "minimize_gaps",
          template_version: 1,
          params: { per_minutes: 60 },
          scope,
          hard: false,
          weight: 35,
          enabled: false,
        },
      ]);
    });
  });
});
