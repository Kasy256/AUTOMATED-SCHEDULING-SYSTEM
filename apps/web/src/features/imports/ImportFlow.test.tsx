import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { ResourceTypeResponse } from "@/api/generated/model";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { ImportFlow } from "./ImportFlow";

const lecturer: ResourceTypeResponse = {
  id: "t1",
  key: "lecturer",
  name: "Lecturer",
  kind: "person",
  attribute_schema: {
    version: 1,
    attributes: [
      {
        key: "role",
        label: "Role",
        type: "enum",
        required: true,
        enum_values: ["Full-Time"],
      },
      {
        key: "faculty",
        label: "Faculty",
        type: "string",
        required: false,
        enum_values: null,
      },
    ],
  },
};
const job = {
  id: "i1",
  kind: "resources",
  status: "awaiting_file",
  filename: "lecturers.csv",
  resource_type_id: "t1",
  schedule_id: null,
  columns: null,
  size_bytes: null,
  report: null,
};
const goodReport = {
  valid: true,
  row_count: 42,
  created: 42,
  errors: [],
  error_count: 0,
  feasibility: [],
  skipped: 0,
};

function api(report: object, dryRuns: unknown[], commits: string[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith("/imports") && init?.method === "POST")
        return Promise.resolve(jsonResponse(job, 201));
      if (url.endsWith("/file"))
        return Promise.resolve(
          jsonResponse({
            ...job,
            status: "uploaded",
            columns: ["code", "name", "role", "faculty", "subjects"],
          }),
        );
      if (url.endsWith("/dry-run")) {
        dryRuns.push(JSON.parse(init?.body as string));
        return Promise.resolve(
          jsonResponse({ ...job, status: "validated", report }),
        );
      }
      if (url.endsWith("/commit")) {
        commits.push(url);
        return Promise.resolve(
          jsonResponse({ ...job, status: "committed", report }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    }),
  );
}

const csv = () =>
  new File(["code,name\nL1,A"], "lecturers.csv", { type: "text/csv" });

describe("ImportFlow", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uploads, maps, dry-runs and commits", async () => {
    const dryRuns: unknown[] = [];
    const commits: string[] = [];
    api(goodReport, dryRuns, commits);
    const onCommitted = vi.fn();
    renderWithProviders(
      <ImportFlow
        target={{ kind: "resources", resourceType: lecturer }}
        onCommitted={onCommitted}
      />,
    );
    await userEvent.upload(screen.getByLabelText("CSV file"), csv());
    expect(
      await screen.findByRole("heading", { name: "2. Match columns" }),
    ).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Tags"), "subjects");
    await userEvent.click(screen.getByRole("button", { name: "Run dry run" }));
    expect(
      await screen.findByText("42 rows · 42 will be created · 0 errors"),
    ).toBeInTheDocument();
    expect(dryRuns).toEqual([
      {
        mapping: {
          kind: "resources",
          code: "code",
          name: "name",
          tags: "subjects",
          capacity: null,
          size: null,
          concurrency: null,
          attributes: { role: "role", faculty: "faculty" },
        },
      },
    ]);
    await userEvent.click(
      screen.getByRole("button", { name: "Import 42 rows" }),
    );
    await vi.waitFor(() => {
      expect(onCommitted).toHaveBeenCalledWith(goodReport);
    });
    expect(commits).toHaveLength(1);
  });

  it("blocks the commit when the dry run finds errors", async () => {
    const bad = {
      ...goodReport,
      valid: false,
      created: 41,
      error_count: 1,
      errors: [{ row: 3, column: "code", message: "duplicate code" }],
    };
    api(bad, [], []);
    renderWithProviders(
      <ImportFlow
        target={{ kind: "resources", resourceType: lecturer }}
        onCommitted={vi.fn()}
      />,
    );
    await userEvent.upload(screen.getByLabelText("CSV file"), csv());
    await userEvent.click(
      await screen.findByRole("button", { name: "Run dry run" }),
    );
    expect(
      await screen.findByText("Row 3 · code · duplicate code"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Import 41 rows" }),
    ).toBeDisabled();
    expect(
      screen.getByText(
        "Fix the file or the mapping, then run the dry run again.",
      ),
    ).toBeInTheDocument();
  });
});
