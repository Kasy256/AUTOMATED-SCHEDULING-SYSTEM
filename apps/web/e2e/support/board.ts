import { expect, type Locator, type Page } from "@playwright/test";

export async function solve(page: Page, scheduleId: string): Promise<void> {
  await page.goto(`/schedules/${scheduleId}/overview`);
  await page.getByRole("button", { name: "Solve" }).click();
  await page.getByLabel("Time limit (seconds)").fill("20");
  await page.getByRole("button", { name: "Start solve" }).click();
  await expect(page.getByText("Timetable ready")).toBeVisible({
    timeout: 150_000,
  });
  await page.getByRole("link", { name: "Open on the board" }).click();
  await expect(page.getByRole("grid")).toBeVisible();
}

export const firstItem = (page: Page): Locator =>
  page.getByRole("grid").locator("button[data-activity]").first();

export async function pickUp(page: Page, item: Locator): Promise<void> {
  await item.scrollIntoViewIfNeeded();
  const box = await item.boundingBox();
  if (!box) throw new Error("item not visible");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box.x + box.width / 2 + 12,
    box.y + box.height / 2 + 4,
    { steps: 3 },
  );
  // Wait for the explanation's highlights, not just the drag starting.
  await expect(
    page.locator('[data-check="valid"], [data-check="invalid"]').first(),
  ).toBeAttached();
}

export async function dropOn(page: Page, cell: Locator): Promise<void> {
  await cell.scrollIntoViewIfNeeded();
  const box = await cell.boundingBox();
  if (!box) throw new Error("cell not visible");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, {
    steps: 5,
  });
  await page.waitForTimeout(400);
  await page.mouse.up();
}
