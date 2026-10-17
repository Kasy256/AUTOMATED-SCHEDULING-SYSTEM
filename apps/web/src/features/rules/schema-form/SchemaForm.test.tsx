import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormProvider, useForm } from "react-hook-form";

import { SCHEMAS } from "./fixtures";
import { initialValues, parseSchema, type JsonSchema } from "./schema";
import { SchemaForm } from "./SchemaForm";

const refs = {
  series: [
    { value: "d1", label: "CS 201" },
    { value: "d2", label: "CS 210" },
  ],
  resource: [],
  window: [{ value: "morning", label: "morning" }],
};

function Harness({
  schema,
  apiError,
}: {
  schema: JsonSchema;
  apiError?: { name: string; message: string };
}) {
  const nodes = parseSchema(schema);
  const form = useForm({ defaultValues: { params: initialValues(nodes) } });
  return (
    <FormProvider {...form}>
      <SchemaForm nodes={nodes} refs={refs} />
      <button
        type="button"
        onClick={() =>
          apiError &&
          form.setError(apiError.name as "params", {
            message: apiError.message,
          })
        }
      >
        fail
      </button>
    </FormProvider>
  );
}

describe("SchemaForm", () => {
  it("renders labelled fields with units and pickers", () => {
    render(<Harness schema={SCHEMAS.max_load as unknown as JsonSchema} />);
    expect(screen.getByLabelText("Period")).toBeInTheDocument();
    expect(screen.getByLabelText("Max time")).toBeInTheDocument();
    expect(screen.getByText("min")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Part of day" }),
    ).toBeInTheDocument();
  });

  it("maps a 422 params location onto the field", async () => {
    render(
      <Harness
        schema={SCHEMAS.max_load as unknown as JsonSchema}
        apiError={{
          name: "params.max_count",
          message: "Input should be greater than or equal to 0",
        }}
      />,
    );
    await userEvent.click(screen.getByText("fail"));
    expect(
      await screen.findByText("Input should be greater than or equal to 0"),
    ).toBeInTheDocument();
  });

  it("adds and removes rows in a list of pairs", async () => {
    render(<Harness schema={SCHEMAS.precedence as unknown as JsonSchema} />);
    expect(screen.getAllByRole("button", { name: /^Before/ })).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Add pair" }));
    expect(screen.getAllByRole("button", { name: /^Before/ })).toHaveLength(2);
    await userEvent.click(
      screen.getByRole("button", { name: "Remove pair 2" }),
    );
    expect(screen.getAllByRole("button", { name: /^Before/ })).toHaveLength(1);
  });
});
