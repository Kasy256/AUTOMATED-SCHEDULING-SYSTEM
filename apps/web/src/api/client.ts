import { getAccessToken, refreshAccessToken } from "@/lib/auth/session";
import { parseProblem, type ApiError } from "@/lib/problem";

// orval types every generated hook's error with this: the mutator throws ApiError for any non-2xx.
// eslint-disable-next-line @typescript-eslint/no-unused-vars -- orval passes the documented error type
export type ErrorType<_Documented> = ApiError;

// Endpoints where a 401 means "wrong credentials or link", not "access token expired".
const NO_REFRESH = [
  "/auth/login",
  "/auth/refresh",
  "/auth/signup",
  "/auth/confirm-email",
  "/auth/accept-invitation",
  "/auth/logout",
];

const signedOutListeners = new Set<() => void>();

export function onSignedOut(listener: () => void): () => void {
  signedOutListeners.add(listener);
  return () => signedOutListeners.delete(listener);
}

function send(url: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(url, { ...init, headers, credentials: "same-origin" });
}

export async function apiFetch<T>(
  url: string,
  init: RequestInit = {},
): Promise<T> {
  let res = await send(url, init);
  if (res.status === 401 && !NO_REFRESH.some((path) => url.includes(path))) {
    if (await refreshAccessToken()) {
      res = await send(url, init);
    } else {
      signedOutListeners.forEach((listener) => {
        listener();
      });
    }
  }
  if (!res.ok) throw await parseProblem(res);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}
