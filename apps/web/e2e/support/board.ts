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

/**
 * A highlighted cell to drop on, clear of the board's edges where dnd-kit auto-scrolls. When none is
 * on screen, the nearest one is scrolled to the centre in one native jump (no animation to fight).
 */
export async function visibleCell(
  page: Page,
  state: "valid" | "invalid",
): Promise<Locator | null> {
  const id = await page.evaluate<string | null, string>((wanted) => {
    const scroller = document.querySelector('[role="grid"]')?.parentElement;
    if (!scroller) return null;
    const view = scroller.getBoundingClientRect();
    const margin = 48;
    const cx = (view.left + view.right) / 2;
    const cy = (view.top + view.bottom) / 2;
    const cells = [
      ...document.querySelectorAll<HTMLElement>(`[data-check="${wanted}"]`),
    ];
    const onScreen = cells.find((cell) => {
      const r = cell.getBoundingClientRect();
      return (
        r.top >= view.top + margin &&
        r.bottom <= view.bottom - margin &&
        r.left >= view.left + margin &&
        r.right <= view.right - margin
      );
    });
    if (onScreen) return onScreen.dataset.cell ?? null;
    const distance = (cell: HTMLElement) => {
      const r = cell.getBoundingClientRect();
      return Math.hypot(r.left + r.width / 2 - cx, r.top + r.height / 2 - cy);
    };
    const nearest = cells.sort((a, b) => distance(a) - distance(b)).at(0);
    if (!nearest) return null;
    nearest.scrollIntoView({ block: "center", inline: "center" });
    return nearest.dataset.cell ?? null;
  }, state);
  return id ? page.locator(`[data-cell="${id}"]`) : null;
}

// Playwright's scrollIntoView during a drag fights dnd-kit's auto-scroll (see visibleCell); release
// only once the target has stopped moving under the pointer.
export async function dropOn(page: Page, cell: Locator): Promise<void> {
  for (let attempt = 0; attempt < 10; attempt++) {
    const box = await cell.boundingBox();
    if (!box) throw new Error("drop target not on screen");
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, {
      steps: 5,
    });
    await page.waitForTimeout(400);
    const settled = await cell.boundingBox();
    if (
      settled &&
      Math.abs(settled.x - box.x) < 1 &&
      Math.abs(settled.y - box.y) < 1
    ) {
      await page.mouse.up();
      return;
    }
  }
  throw new Error("drop target kept moving");
}
