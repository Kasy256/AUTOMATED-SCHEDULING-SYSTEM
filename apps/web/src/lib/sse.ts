import { apiUrl } from "@/api/base";
import { getAccessToken } from "@/lib/auth/session";
import { parseProblem } from "@/lib/problem";

export interface SseEvent {
  event: string;
  data: string;
}

export function parseSse(buffer: string): { events: SseEvent[]; rest: string } {
  const blocks = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = blocks.pop() ?? "";
  const events = blocks.flatMap((block) => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith(":")) continue;
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:"))
        data.push(line.slice(5).replace(/^ /, ""));
    }
    return data.length ? [{ event, data: data.join("\n") }] : [];
  });
  return { events, rest };
}

// EventSource can't send an Authorization header, so the stream is read with fetch.
export async function streamSse(
  url: string,
  onEvent: (e: SseEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const headers = new Headers({ Accept: "text/event-stream" });
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(apiUrl(url), {
    headers,
    signal,
    credentials: "include",
  });
  if (!res.ok || !res.body) throw await parseProblem(res);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSse(buffer);
    buffer = parsed.rest;
    parsed.events.forEach(onEvent);
  }
}
