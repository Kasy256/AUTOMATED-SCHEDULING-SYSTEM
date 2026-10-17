import { expect, test, type Page } from "@playwright/test";

import { signUpAndConfirm } from "./support/accounts";
import { dropOn, firstItem, pickUp, solve } from "./support/board";
import { setUpIsbat } from "./support/isbat";

test.describe.serial("planner board", () => {
  let page: Page;
  let scheduleId: string;

  test.beforeAll(async ({ browser }) => {
    test.setTimeout(360_000);
    page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await signUpAndConfirm(page);
    scheduleId = await setUpIsbat(page);
    await solve(page, scheduleId);
  });

  test.afterAll(async () => {
    await page.close();
  });

  test("WEB-02: invalid drop explains, valid drop goes to the tray and saves a draft", async () => {
    const item = firstItem(page);
    await pickUp(page, item);
    const invalid = page.locator('[data-check="invalid"]').first();
    if (await invalid.count()) {
      await dropOn(page, invalid);
      await expect(page.getByText("Can't move here")).toBeVisible();
      await expect(
        page.getByRole("region", { name: "Unsaved changes" }),
      ).toHaveCount(0);
      await page.keyboard.press("Escape");
      await pickUp(page, item);
    }
    const valid = page.locator('[data-check="valid"]').first();
    await expect(valid).toBeAttached();
    await dropOn(page, valid);
    const tray = page.getByRole("region", { name: "Unsaved changes" });
    await expect(tray).toContainText("1 unsaved change");
    const before = await page.getByLabel("Version").inputValue();
    await tray.getByRole("button", { name: "Save as draft" }).click();
    await expect(tray).toHaveCount(0);
    await expect(page.getByLabel("Version")).not.toHaveValue(before);
  });

  test("WEB-03: a pinned item stays put after a re-solve", async () => {
    const item = firstItem(page);
    const activity = await item.getAttribute("data-activity");
    const cell = await page
      .locator(`[data-cell]:has(button[data-activity="${String(activity)}"])`)
      .first()
      .getAttribute("data-cell");
    await item.click();
    await page.getByRole("button", { name: "Pin" }).click();
    await expect(page.getByRole("button", { name: "Unpin" })).toBeVisible();
    await page.keyboard.press("Escape");
    await solve(page, scheduleId);
    await expect(
      page.locator(
        `[data-cell="${String(cell)}"] button[data-activity="${String(activity)}"]`,
      ),
    ).toBeVisible();
  });

  test("WEB-07: keyboard reaches an item and opens its explanation", async () => {
    await page.getByRole("gridcell").first().focus();
    for (let i = 0; i < 60; i++) {
      const label = await page.evaluate(
        () => document.activeElement?.getAttribute("aria-label") ?? "",
      );
      if (!label.endsWith(": empty")) break;
      await page.keyboard.press(i % 12 === 11 ? "ArrowDown" : "ArrowRight");
    }
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("heading", { name: "Why it's here" }),
    ).toBeVisible();
  });
});
