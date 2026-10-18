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

  it("ignores answers that arrive after their drag ended", async () => {
    const pending: ((r: Response) => void)[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            pending.push(resolve);
          }),
      ),
    );
    const explanationFor = (activity: string, start: string) =>
      jsonResponse({
        activity_id: activity,
        binding: [],
        truncated: false,
        alternatives: [
          {
            start_at: start,
            resources: item.resources,
            check: { valid: true, broken: [], penalties: [] },
          },
        ],
      });
    const { result } = renderHook(() => useDragChecks("v1"), { wrapper });

    // A is picked up, then dropped before its explanation arrives.
    let pickA!: Promise<void>;
    act(() => {
      pickA = result.current.pickUp(item, "L1");
    });
    act(() => {
      result.current.cancel();
    });
    await act(async () => {
      pending[0]?.(explanationFor("a1", "2026-01-13T06:00:00Z"));
      await pickA;
    });
    expect(result.current.highlight).toBeNull();

    // B is picked up while A's (second) explanation is still in flight.
    const other = { ...item, activityId: "a2", name: "CS 202" };
    let pickA2!: Promise<void>;
    act(() => {
      pickA2 = result.current.pickUp(item, "L1");
    });
    let pickB!: Promise<void>;
    act(() => {
      pickB = result.current.pickUp(other, "L1");
    });
    await act(async () => {
      pending[2]?.(explanationFor("a2", "2026-01-15T06:00:00Z"));
      await pickB;
      pending[1]?.(explanationFor("a1", "2026-01-14T06:00:00Z"));
      await pickA2;
    });
    expect(
      result.current.highlight?.has(cellKey("L1", "2026-01-14T06:00:00Z")),
    ).toBe(false);
    expect(
      result.current.highlight?.get(cellKey("L1", "2026-01-15T06:00:00Z")),
    ).toEqual({ state: "valid" });

    // A hover check that lands after the drag ended doesn't bring highlights back.
    let late!: Promise<unknown>;
    act(() => {
      late = result.current.check("L1", "2026-01-16T06:00:00Z");
    });
    act(() => {
      result.current.cancel();
    });
    await act(async () => {
      pending[3]?.(jsonResponse({ valid: true, broken: [], penalties: [] }));
      await late;
    });
    expect(result.current.highlight).toBeNull();
  });
});
