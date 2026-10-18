import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y";
import { signUpAndConfirm } from "./support/accounts";
import { firstItem, solve } from "./support/board";
import { setUpIsbat } from "./support/isbat";

test.describe.serial("versions and distribution", () => {
  let context: BrowserContext;
  let page: Page;
  let scheduleId: string;

  test.beforeAll(async ({ browser }) => {
    test.setTimeout(420_000);
    // axe needs a page from a context it can open its own frames in.
    context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    page = await context.newPage();
    await signUpAndConfirm(page);
    scheduleId = await setUpIsbat(page);
    await solve(page, scheduleId);
  });

  test.afterAll(async () => {
    await context.close();
  });

  test("WEB-05: publish with a change summary", async () => {
    await page.goto(`/schedules/${scheduleId}/versions`);
    await page.getByRole("button", { name: "Publish" }).first().click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Publish version 1?");
    await dialog.getByRole("button", { name: "Publish" }).click();
    await expect(page.getByText("Version 1 · published")).toBeVisible();
    await expectNoA11yViolations(page);
  });

  test("WEB-05: a board edit compared with the published version", async () => {
    await page.goto(`/schedules/${scheduleId}/planner`);
    await firstItem(page).click();
    await page.getByRole("button", { name: "Move here" }).first().click();
    await page
      .getByRole("region", { name: "Unsaved changes" })
      .getByRole("button", { name: "Save as draft" })
      .click();
    await page.goto(`/schedules/${scheduleId}/versions`);
    await page.getByRole("link", { name: "Compare" }).first().click();
    await expect(
      page.getByRole("heading", { name: /^Moved \(1\)/ }),
    ).toBeVisible();
    await expectNoA11yViolations(page);
  });

  test("WEB-05: export CSV and print view", async () => {
    await page.goto(`/schedules/${scheduleId}/versions`);
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export CSV" }).first().click();
    const file = await (await download).path();
    const { readFileSync } = await import("node:fs");
    // Python's csv module ends rows with \r\n.
    const lines = readFileSync(file, "utf8").trim().split(/\r?\n/);
    expect(lines[0]).toBe(
      "activity_id,activity,start,end,role,resource_code,resource",
    );
    expect(lines.length).toBeGreaterThan(1);
    await page.getByRole("link", { name: "Print" }).first().click();
    await page
      .getByLabel("Resource type")
      .selectOption({ label: "Student group" });
    await expect(page.locator("section.sheet").first()).toBeVisible();
    expect(await page.locator("section.sheet").count()).toBeGreaterThan(0);
    await expectNoA11yViolations(page);
  });

  test("WEB-05: copy a resource's calendar link", async () => {
    await page.goto("/resources");
    await page.getByRole("row").nth(1).getByRole("link").click();
    await page.getByRole("button", { name: "Create calendar link" }).click();
    const url = await page.getByLabel("Calendar link").inputValue();
    const body = await (await page.request.get(url)).text();
    expect(body).toContain("BEGIN:VCALENDAR");
  });

  test("repair the published timetable and review it", async () => {
    await page.goto(`/schedules/${scheduleId}/versions`);
    await page
      .getByRole("button", { name: "Repair published timetable" })
      .click();
    await page
      .getByRole("dialog")
      .getByLabel("Time limit (seconds)")
      .fill("20");
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Start repair" })
      .click();
    await expect(
      page.getByText("Repair ready — review the changes"),
    ).toBeVisible({ timeout: 150_000 });
    await page.getByRole("link", { name: "Compare with published" }).click();
    await expect(
      page.getByRole("heading", { name: /^Compare version/ }),
    ).toBeVisible();
  });

  test("reports show all four sections", async () => {
    await page.goto(`/schedules/${scheduleId}/reports`);
    for (const name of [
      "Utilisation",
      "Load per person",
      "Coverage gaps",
      "Fairness spread",
    ])
      await expect(page.getByRole("heading", { name })).toBeVisible();
    await expectNoA11yViolations(page);
  });
});
