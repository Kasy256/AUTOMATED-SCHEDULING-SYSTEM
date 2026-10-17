import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import type { PredicateValue } from "@/lib/predicates";

import { PredicateList } from "./PredicateList";

function Harness({ initial }: { initial: PredicateValue[] }) {
  const [value, setValue] = useState(initial);
  return <PredicateList idPrefix="p" value={value} onChange={setValue} />;
}

describe("PredicateList", () => {
  it("keeps each row's text when an earlier row is removed", async () => {
    render(
      <Harness
        initial={[
          { attr: "role", op: "eq", value: "Dean" },
          { attr: "faculty", op: "eq", value: "CS" },
        ]}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Remove condition 1" }),
    );
    expect(screen.getByLabelText("Condition 1 attribute")).toHaveValue(
      "faculty",
    );
    expect(screen.getByLabelText("Condition 1 value")).toHaveValue("CS");
  });

  it("parses list values for 'is one of'", async () => {
    render(<Harness initial={[{ attr: "room_type", op: "in", value: [] }]} />);
    await userEvent.type(
      screen.getByLabelText("Condition 1 value"),
      "Lab, Theory",
    );
    expect(screen.getByLabelText("Condition 1 value")).toHaveValue(
      "Lab, Theory",
    );
  });
});
