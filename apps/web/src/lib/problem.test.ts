import { isApiError, parseProblem } from "./problem";

const json = (
  status: number,
  body: unknown,
  type = "application/problem+json",
) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": type },
  });

describe("parseProblem", () => {
  it("reads title, detail and field errors without the body prefix", async () => {
    const error = await parseProblem(
      json(422, {
        title: "Unprocessable Content",
        status: 422,
        detail: "Invalid rule",
        errors: [
          {
            loc: ["body", "params", "period"],
            msg: "Input should be 'day'",
            type: "x",
          },
        ],
      }),
    );
    expect(isApiError(error)).toBe(true);
    expect(error.status).toBe(422);
    expect(error.detail).toBe("Invalid rule");
    expect(error.fieldErrors).toEqual([
      { path: ["params", "period"], message: "Input should be 'day'" },
    ]);
  });

  it("falls back to a generic message when the body is not a problem", async () => {
    const error = await parseProblem(
      new Response("<html>bad gateway</html>", { status: 502 }),
    );
    expect(error.status).toBe(502);
    expect(error.title).toBe("Something went wrong");
    expect(error.detail).toBeNull();
    expect(error.fieldErrors).toEqual([]);
  });
});
