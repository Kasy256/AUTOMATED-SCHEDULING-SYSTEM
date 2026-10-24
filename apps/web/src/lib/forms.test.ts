import { ApiError } from "./problem";
import { applyApiError } from "./forms";

describe("applyApiError", () => {
  it("puts known field errors on fields and returns the rest", () => {
    const setError = vi.fn();
    const error = new ApiError(422, "Unprocessable Content", "Check the form", [
      { path: ["email"], message: "not an email" },
      { path: ["params", "period"], message: "bad period" },
    ]);
    const message = applyApiError(error, setError, ["email", "params.period"]);
    expect(setError).toHaveBeenCalledWith("email", { message: "not an email" });
    expect(setError).toHaveBeenCalledWith("params.period", {
      message: "bad period",
    });
    expect(message).toBeNull();
  });

  it("returns a page message for unmapped problems and non-API errors", () => {
    const setError = vi.fn();
    expect(
      applyApiError(
        new ApiError(409, "Conflict", "Code already used", []),
        setError,
        [],
      ),
    ).toBe("Code already used");
    expect(applyApiError(new TypeError("Failed to fetch"), setError, [])).toBe(
      "Could not reach the server. Check your connection and try again.",
    );
  });
});
