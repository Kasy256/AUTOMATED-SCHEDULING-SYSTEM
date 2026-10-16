export interface FieldIssue {
  path: (string | number)[];
  message: string;
}

export const GENERIC_TITLE = "Something went wrong";

export class ApiError extends Error {
  readonly status: number;
  readonly title: string;
  readonly detail: string | null;
  readonly fieldErrors: FieldIssue[];

  constructor(
    status: number,
    title: string,
    detail: string | null,
    fieldErrors: FieldIssue[],
  ) {
    super(detail ?? title);
    this.name = "ApiError";
    this.status = status;
    this.title = title;
    this.detail = detail;
    this.fieldErrors = fieldErrors;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

interface ProblemBody {
  title?: unknown;
  detail?: unknown;
  errors?: unknown;
}

function issues(errors: unknown): FieldIssue[] {
  if (!Array.isArray(errors)) return [];
  return errors.flatMap((raw: unknown) => {
    if (typeof raw !== "object" || raw === null) return [];
    const { loc, msg } = raw as { loc?: unknown; msg?: unknown };
    if (!Array.isArray(loc) || typeof msg !== "string") return [];
    const path = loc.filter(
      (p): p is string | number =>
        typeof p === "string" || typeof p === "number",
    );
    return [{ path: path[0] === "body" ? path.slice(1) : path, message: msg }];
  });
}

export async function parseProblem(res: Response): Promise<ApiError> {
  let body: ProblemBody = {};
  try {
    body = (await res.json()) as ProblemBody;
  } catch {
    // Proxies and crashes can return HTML or nothing; the status still tells the story.
  }
  const title = typeof body.title === "string" ? body.title : GENERIC_TITLE;
  const detail = typeof body.detail === "string" ? body.detail : null;
  return new ApiError(res.status, title, detail, issues(body.errors));
}
