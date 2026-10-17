import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { isApiError } from "./problem";

export function applyApiError<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly string[] | ((name: string) => boolean),
): string | null {
  if (!isApiError(error))
    return "Could not reach the server. Check your connection and try again.";
  const known =
    typeof fields === "function"
      ? fields
      : (name: string) => fields.includes(name);
  const unmapped: string[] = [];
  for (const issue of error.fieldErrors) {
    const name = issue.path.join(".");
    if (known(name)) setError(name as Path<T>, { message: issue.message });
    else unmapped.push(issue.message);
  }
  if (error.fieldErrors.length === 0) return error.detail ?? error.title;
  return unmapped.length ? unmapped.join(" ") : null;
}
