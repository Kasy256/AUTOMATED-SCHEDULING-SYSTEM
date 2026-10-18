import { formatEngineText } from "./engineText";

const A = "0f8fad5b-d9cb-469f-a165-70867728950e";
const B = "7c9e6679-7425-40de-944b-e07fc1f90ae7";

describe("formatEngineText", () => {
  it("replaces known ids with names and unknown ids with a placeholder", () => {
    const names: Record<string, string> = { [A]: "Dr. Okello (L005)" };
    expect(
      formatEngineText(
        `${A} has 3 activities in day 2; see ${B.toUpperCase()}`,
        (id) => names[id],
      ),
    ).toBe(
      "Dr. Okello (L005) has 3 activities in day 2; see an item that no longer exists",
    );
  });

  it("leaves text without ids unchanged", () => {
    expect(
      formatEngineText("At most 2 activities per day", () => undefined),
    ).toBe("At most 2 activities per day");
  });
});
