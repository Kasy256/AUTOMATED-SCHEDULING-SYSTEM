import type { TokenResponse } from "@/api/generated/model";

let accessToken: string | null = null;
let inFlight: Promise<string | null> | null = null;
const listeners = new Set<() => void>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  listeners.forEach((listener) => {
    listener();
  });
}

export function subscribeToken(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// Two tabs presenting the same refresh cookie revoke the whole token family, so every tab
// refreshes under one browser-wide lock; the next holder sends the already-rotated cookie.
function withRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  if ("locks" in navigator)
    return navigator.locks.request("cartlyf-refresh", fn);
  return fn();
}

async function refreshOnce(): Promise<string | null> {
  const res = await fetch("/api/v1/auth/refresh", {
    method: "POST",
    credentials: "same-origin",
  });
  if (!res.ok) {
    setAccessToken(null);
    return null;
  }
  const body = (await res.json()) as TokenResponse;
  setAccessToken(body.access_token);
  return body.access_token;
}

export function refreshAccessToken(): Promise<string | null> {
  inFlight ??= withRefreshLock(refreshOnce).finally(() => {
    inFlight = null;
  });
  return inFlight;
}
