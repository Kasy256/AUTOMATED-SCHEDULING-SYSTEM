import { expect, test } from "@playwright/test";

import { syntheticBoard } from "./support/synthetic";

// The production preview server from playwright.config.ts.
const PREVIEW = "http://localhost:4173";

test("WEB-06: board with 2,000 activities stays responsive", async ({
  page,
  isMobile,
}) => {
  test.skip(isMobile, "desktop performance budget");
  const data = syntheticBoard() as Record<string, unknown>;
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path.includes("/explanation")
      ? data.explanation
      : (data[path] ?? []);
    return route.fulfill({ json: body });
  });
  await page.addInitScript(() => {
    const w = window as unknown as { __longTasks: number[] };
    w.__longTasks = [];
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) w.__longTasks.push(e.duration);
    }).observe({ type: "longtask", buffered: false });
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${PREVIEW}/schedules/s1/planner`);
  const grid = page.getByRole("grid");
  await expect(grid).toBeVisible({ timeout: 30_000 });
  const reset = () =>
    page.evaluate(() => {
      (window as unknown as { __longTasks: number[] }).__longTasks = [];
    });
  const worst = () =>
    page.evaluate(() =>
      Math.max(
        0,
        ...(window as unknown as { __longTasks: number[] }).__longTasks,
      ),
    );

  await reset();
  const scroller = page.locator("div:has(> [role=grid])").first();
  for (let i = 0; i < 10; i++)
    await scroller.evaluate((el) => el.scrollBy(0, 600));
  expect(await worst()).toBeLessThan(200);

  // One week in this data set, so a full re-render via the type tab stands in for a week switch.
  await reset();
  await page.getByRole("tab", { name: "Lecturer" }).click();
  expect(await worst()).toBeLessThan(200);

  // Lecturers past 100 teach nothing in this data set, so go back to the busy rows. Overscan rows
  // sit under the sticky header, so pick an item in plain view.
  await scroller.evaluate((el) => el.scrollTo(0, 0));
  await expect(page.locator("button[data-activity]").first()).toBeVisible();
  const activity = await scroller.evaluate((el) => {
    const view = el.getBoundingClientRect();
    const visible = [
      ...el.querySelectorAll<HTMLElement>("button[data-activity]"),
    ].find((b) => {
      const r = b.getBoundingClientRect();
      return r.top > view.top + 80 && r.bottom < view.bottom - 20;
    });
    return visible?.dataset.activity ?? "";
  });
  const item = page.locator(`button[data-activity="${activity}"]`).first();
  await reset();
  const box = await item.boundingBox();
  if (!box) throw new Error("no item");
  await page.mouse.move(box.x + 10, box.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + 30, box.y + 14, { steps: 4 });
  await expect(page.locator("[data-check]").first()).toBeAttached();
  await page.mouse.up();
  expect(await worst()).toBeLessThan(200);
});
