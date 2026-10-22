// Empty in dev (Vite proxies /api); set to the API's origin when web and API are on separate hosts.
export function apiUrl(path: string): string {
  const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
  return base + path;
}
