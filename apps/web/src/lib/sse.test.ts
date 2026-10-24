import { setAccessToken } from "@/lib/auth/session";

import { parseSse, streamSse, type SseEvent } from "./sse";

describe("parseSse", () => {
  it("splits complete events and keeps the remainder", () => {
    const { events, rest } = parseSse(
      'event: progress\ndata: {"a":1}\n\nevent: done\ndata: {"b"',
    );
    expect(events).toEqual([{ event: "progress", data: '{"a":1}' }]);
    expect(rest).toBe('event: done\ndata: {"b"');
  });

  it("joins multi-line data and defaults the event name", () => {
    expect(parseSse("data: one\ndata: two\n\n").events).toEqual([
      { event: "message", data: "one\ntwo" },
    ]);
  });

  it("ignores comments (keep-alives)", () => {
    expect(parseSse(": ping\n\n").events).toEqual([]);
  });
});

describe("streamSse", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the bearer token and delivers chunked events", async () => {
    setAccessToken("tok");
    const chunks = [
      'event: progress\ndata: {"solutions":1}\n',
      '\nevent: done\ndata: {"status":"succeeded"}\n\n',
    ];
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const c of chunks) controller.enqueue(new TextEncoder().encode(c));
        controller.close();
      },
    });
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) =>
      Promise.resolve(new Response(body, { status: 200 })),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test");
    const seen: SseEvent[] = [];
    await streamSse(
      "/api/v1/solves/r1/events",
      (e) => seen.push(e),
      new AbortController().signal,
    );
    expect(
      new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("Authorization"),
    ).toBe("Bearer tok");
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "https://api.example.test/api/v1/solves/r1/events",
    );
    expect(fetchMock.mock.calls[0]?.[1]?.credentials).toBe("include");
    vi.unstubAllEnvs();
    expect(seen.map((e) => e.event)).toEqual(["progress", "done"]);
  });

  it("rejects on an error status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 502 }))),
    );
    await expect(
      streamSse("/x", () => undefined, new AbortController().signal),
    ).rejects.toThrow();
  });
});
