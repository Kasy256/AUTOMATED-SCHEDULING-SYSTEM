import type { TokenResponse } from "@/api/generated/model";

let accessToken: string | null = null;
// The organisation the current access token acts in; the refresh cookie decides it server-side.
let tokenOrganisation: string | null = null;
let inFlight: Promise<string | null> | null = null;
const listeners = new Set<() => void>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function getTokenOrganisation(): string | null {
  return tokenOrganisation;
}

export function setAccessToken(
  token: string | null,
  organisationId: string | null = null,
): void {
  accessToken = token;
  tokenOrganisation = token ? organisationId : null;
  listeners.forEach((listener) => {
    listener();
  });
}

export function setSession(token: TokenResponse): void {
  setAccessToken(token.access_token, token.organisation_id ?? null);
}

export function subscribeToken(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// Two tabs presenting the same refresh cookie revoke the whole token family, so everything that
// spends the cookie (refresh, organisation switch) runs under one browser-wide lock; the next
// holder sends the already-rotated cookie.
export function withSessionLock<T>(fn: () => Promise<T>): Promise<T> {
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
  setSession(body);
  return body.access_token;
}

export function refreshAccessToken(): Promise<string | null> {
  inFlight ??= withSessionLock(refreshOnce).finally(() => {
    inFlight = null;
  });
  return inFlight;
}
