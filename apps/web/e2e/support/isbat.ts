import path from "node:path";

import { expect, type Page } from "@playwright/test";

export const ISBAT_DIR = path.resolve(
  import.meta.dirname,
  "../../../../packages/engine/tests/fixtures/isbat/v1",
);

export async function importResources(
  page: Page,
  rowLabel: string,
  file: string,
  columns: Record<string, string>,
) {
  const row = page.getByRole("region", { name: rowLabel });
  await row.getByRole("button", { name: "Upload CSV" }).click();
  await row.getByLabel("CSV file").setInputFiles(path.join(ISBAT_DIR, file));
  for (const [label, column] of Object.entries(columns))
    await row.getByLabel(label).selectOption(column);
  await row.getByRole("button", { name: "Run dry run" }).click();
  await expect(row.getByText(/ 0 errors/)).toBeVisible();
  await row.getByRole("button", { name: /^Import \d+ rows$/ }).click();
  await expect(row.getByText(/^Imported/)).toBeVisible();
}

export async function importDemands(page: Page, term: string) {
  const row = page.getByRole("region", { name: "Demands" });
  await row.getByRole("button", { name: "Upload CSV" }).click();
  await row
    .getByLabel("CSV file")
    .setInputFiles(path.join(ISBAT_DIR, "course_units.csv"));
  await row.getByLabel("Term").fill(term);
  await row.getByRole("button", { name: "Run dry run" }).click();
  await expect(row.getByText(/ 0 errors/)).toBeVisible();
  await row.getByRole("button", { name: /^Import \d+ rows$/ }).click();
  await expect(row.getByText(/^Imported/)).toBeVisible();
}

export async function setUpIsbat(page: Page): Promise<string> {
  await page.getByRole("button", { name: /Education/ }).click();
  await page.getByLabel("Name").fill("ISBAT Term 1");
  await page.getByLabel("Timezone").fill("Africa/Kampala");
  await page.getByLabel("Start date").fill("2026-01-12");
  await page.getByLabel("End date").fill("2026-01-16");
  await page.getByRole("button", { name: "Create schedule" }).click();
  await expect(
    page.getByRole("heading", { name: "Import your data" }),
  ).toBeVisible();
  await importResources(page, "Lecturer", "lecturers.csv", {
    Tags: "subjects",
  });
  await importResources(page, "Room", "rooms.csv", { Tags: "specialisations" });
  await importResources(page, "Student group", "student_groups.csv", {});
  await importDemands(page, "Term 1");
  await page.getByRole("button", { name: "Continue" }).click();
  const id = new URL(page.url()).searchParams.get("schedule");
  if (!id) throw new Error("wizard did not record the schedule id");
  return id;
}
