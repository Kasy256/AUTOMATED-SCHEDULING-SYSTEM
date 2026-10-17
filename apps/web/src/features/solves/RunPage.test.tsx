import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as auth from "@/lib/auth/AuthProvider";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { RunPage } from "./RunPage";

const run = {
  id: "r1",
  schedule_id: "s1",
  status: "running",
  kind: "solve",
  problem_hash: "h",
  progress: {},
  conflicts: [],
  error: null,
  version_id: null,
  created_at: "2026-01-01T00:00:00Z",
  started_at: "2026-01-01T00:00:01Z",
  finished_at: null,
  baseline_version_id: null,
  freeze_before: null,
  infeasibility: null,
};

describe("RunPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("streams progress and cancels", async () => {
    vi.spyOn(auth, "useAuth").mockReturnValue({
      status: "signedIn",
      me: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganisation: vi.fn(),
      adoptSession: vi.fn(),
      can: () => true,
    });
    const posts: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          posts.push(url);
          return Promise.resolve(jsonResponse({ ...run, status: "running" }));
        }
        if (url.endsWith("/events"))
          return Promise.resolve(
            new Response(
              new ReadableStream<Uint8Array>({
                start(c) {
                  c.enqueue(
                    new TextEncoder().encode(
                      'event: progress\ndata: {"status":"running","solutions":3,"objective":12,"best_bound":10,"wall_time_s":4.2}\n\n',
                    ),
                  );
                },
              }),
            ),
          );
        if (url.endsWith("/solves/r1"))
          return Promise.resolve(jsonResponse(run));
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
      }),
    );
    renderWithProviders(<RunPage />, {
      route: "/schedules/s1/solves/r1",
      path: "/schedules/:scheduleId/solves/:runId",
    });
    expect(await screen.findByText("3 solutions")).toBeInTheDocument();
    expect(screen.getByText("Best score 12")).toBeInTheDocument();
    expect(screen.getByText("Gap 16.7%")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await vi.waitFor(() => {
      expect(posts.some((u) => u.endsWith("/api/v1/solves/r1/cancel"))).toBe(
        true,
      );
    });
  });
});
