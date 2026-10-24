import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";

import { NativeSelect } from "./NativeSelect";

function Harness({ onValue }: { onValue: (v: string) => void }) {
  const form = useForm({ defaultValues: { kind: "person" } });
  return (
    <form onSubmit={(e) => void form.handleSubmit((v) => onValue(v.kind))(e)}>
      <label htmlFor="kind">Kind</label>
      <NativeSelect id="kind" {...form.register("kind")}>
        <option value="person">Person</option>
        <option value="space">Space</option>
      </NativeSelect>
      <button type="submit">go</button>
    </form>
  );
}

describe("NativeSelect", () => {
  it("works with react-hook-form register and keeps its label", async () => {
    const onValue = vi.fn();
    render(<Harness onValue={onValue} />);
    await userEvent.selectOptions(screen.getByLabelText("Kind"), "space");
    await userEvent.click(screen.getByText("go"));
    await vi.waitFor(() => {
      expect(onValue).toHaveBeenCalledWith("space");
    });
  });

  it("matches the other controls' height and hides its chevron from assistive tech", () => {
    const { container } = render(
      <NativeSelect aria-label="Period">
        <option>Day</option>
      </NativeSelect>,
    );
    expect(screen.getByLabelText("Period")).toHaveClass("h-10");
    expect(container.querySelector("svg")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });
});
