import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { jsonResponse } from "@/test/render";

import { useSolveStream } from "./useSolveStream";

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>
    {children}
  </QueryClientProvider>
);

describe("useSolveStream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("reports progress events and finishes on done", async () => {
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(
          new TextEncoder().encode(
            'event: progress\ndata: {"status":"running","solutions":2,"objective":40}\n\n',
          ),
        );
        c.enqueue(
          new TextEncoder().encode(
            'event: done\ndata: {"status":"succeeded","version_id":"v1"}\n\n',
          ),
        );
        c.close();
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(body))),
    );
    const { result } = renderHook(() => useSolveStream("r1"), { wrapper });
    await waitFor(() => {
      expect(result.current.done).toBe(true);
    });
    expect(result.current.progress).toMatchObject({
      solutions: 2,
      objective: 40,
    });
  });

  it("falls back to polling when the stream fails", async () => {
    let polls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.endsWith("/events"))
          return Promise.reject(new TypeError("network"));
        polls += 1;
        return Promise.resolve(
          jsonResponse({
            id: "r1",
            status: polls < 2 ? "running" : "succeeded",
            progress: { solutions: polls },
          }),
        );
      }),
    );
    const { result } = renderHook(() => useSolveStream("r1", 10), { wrapper });
    await waitFor(() => {
      expect(result.current.done).toBe(true);
    });
    expect(polls).toBeGreaterThanOrEqual(2);
  });
});
