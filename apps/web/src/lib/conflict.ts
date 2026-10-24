import { isApiError } from "./problem";

export function describeFailure(error: unknown, what: string): string {
  if (!isApiError(error))
    return "Could not reach the server. Check your connection and try again.";
  if (error.status === 409)
    return `${what} is still used: ${error.detail ?? "other items refer to it"}`;
  if (error.status === 404)
    return `${what} no longer exists. Refresh the page.`;
  return error.detail ?? error.title;
}
