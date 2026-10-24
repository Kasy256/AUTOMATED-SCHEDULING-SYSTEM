import { expect, test } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y";
import { signUpAndConfirm } from "./support/accounts";
import { setUpIsbat } from "./support/isbat";

test("WEB-04 (part 1): add max_load for a tag, make it soft with a weight", async ({
  page,
  isMobile,
}) => {
  test.skip(isMobile, "editing is desktop-first");
  await signUpAndConfirm(page);
  const scheduleId = await setUpIsbat(page);
  await page.goto(`/schedules/${scheduleId}/rules`);
  await page.getByRole("button", { name: "Add rule" }).click();
  await page.getByRole("button", { name: /Maximum workload/ }).click();
  const drawer = page.getByRole("dialog");
  await drawer.getByLabel("Name").fill("PROG_C lecturers: at most 1 a day");
  await drawer.getByLabel("Period").selectOption("day");
  await drawer.getByLabel("Max activities").fill("1");
  await drawer.getByLabel("Tags").fill("PROG_C");
  await drawer.getByLabel("Tags").press("Enter");
  await drawer.getByRole("button", { name: "Save rule" }).click();
  const row = page.getByRole("button", {
    name: "PROG_C lecturers: at most 1 a day",
  });
  await expect(row).toBeVisible();
  await expect(
    page.getByText("At most 1 activity per day").first(),
  ).toBeVisible();

  await row.click();
  await drawer.getByLabel("Soft — prefer").check();
  await drawer.getByLabel("Weight").fill("40");
  await drawer.getByRole("button", { name: "Save rule" }).click();
  await expect(page.getByText(/Soft — avoid, weighted/)).toBeVisible();
  await expect(page.getByText("weight 40")).toBeVisible();
  await page.reload();
  await expect(page.getByText("weight 40")).toBeVisible();
  await expectNoA11yViolations(page);
});
