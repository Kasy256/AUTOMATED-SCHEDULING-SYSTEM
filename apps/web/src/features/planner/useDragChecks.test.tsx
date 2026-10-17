import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";

import { jsonResponse } from "@/test/render";

import { cellKey } from "./model/items";
import { useDragChecks } from "./useDragChecks";

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>
    {children}
  </QueryClientProvider>
);
const item = {
  activityId: "a1",
  name: "CS 201",
  start: "2026-01-12T06:00:00.000Z",
  resources: { lecturer: ["L1"], room: ["R1"] },
  pending: false,
  pinned: false,
};

describe("useDragChecks", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("highlights explanation alternatives on pickup and validates unknown cells once", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        calls.push(url);
        if (url.includes("/explanation"))
          return Promise.resolve(
            jsonResponse({
              activity_id: "a1",
              binding: [],
              truncated: false,
              alternatives: [
                {
                  start_at: "2026-01-13T06:00:00Z",
                  resources: item.resources,
                  check: { valid: true, broken: [], penalties: [] },
                },
              ],
            }),
          );
        return Promise.resolve(
          jsonResponse({
            valid: false,
            broken: [
              {
                constraint_id: "c",
                rule: "r",
                message: "Room LH3 is busy",
                activity_ids: [],
                resource_ids: [],
              },
            ],
            penalties: [],
          }),
        );
      }),
    );
    const { result } = renderHook(() => useDragChecks("v1"), { wrapper });
    await act(() => result.current.pickUp(item, "L1"));
    expect(
      result.current.highlight?.get(cellKey("L1", "2026-01-13T06:00:00Z")),
    ).toEqual({ state: "valid" });
    let first: unknown;
    await act(async () => {
      first = await result.current.check("L1", "2026-01-14T06:00:00Z");
    });
    await act(async () => {
      await result.current.check("L1", "2026-01-14T06:00:00Z");
    });
    expect(first).toEqual({ state: "invalid", reasons: ["Room LH3 is busy"] });
    expect(calls.filter((u) => u.includes("validate-move"))).toHaveLength(1);
  });

  it("drop returns the move with its result and ends the drag; same cell returns null", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          jsonResponse(
            url.includes("/explanation")
              ? {
                  activity_id: "a1",
                  binding: [],
                  truncated: false,
                  alternatives: [],
                }
              : { valid: true, broken: [], penalties: [] },
          ),
        ),
      ),
    );
    const { result } = renderHook(() => useDragChecks("v1"), { wrapper });
    await act(() => result.current.pickUp(item, "L1"));
    let outcome: unknown;
    await act(async () => {
      outcome = await result.current.drop("L1", "2026-01-12T06:00:00Z");
    });
    expect(outcome).toBeNull();
    await act(() => result.current.pickUp(item, "L1"));
    await act(async () => {
      outcome = await result.current.drop("L2", "2026-01-12T06:00:00Z");
    });
    expect(outcome).toMatchObject({
      move: { resources: { lecturer: ["L2"], room: ["R1"] } },
      result: { state: "valid" },
    });
    expect(result.current.dragging).toBeNull();
  });
});
