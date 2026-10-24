import { expect, test } from "@playwright/test";

import { signUpAndConfirm } from "./support/accounts";
import { solve } from "./support/board";
import { setUpIsbat } from "./support/isbat";

test("WEB-04 (part 2): a soft rule's penalty shows in the score breakdown", async ({
  page,
  isMobile,
}) => {
  test.skip(isMobile, "desktop flow");
  test.setTimeout(300_000);
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
  await drawer.getByLabel("Soft — prefer").check();
  await drawer.getByLabel("Weight").fill("40");
  await drawer.getByRole("button", { name: "Save rule" }).click();
  await expect(page.getByText("weight 40")).toBeVisible();

  await solve(page, scheduleId);
  await page.getByRole("button", { name: "Score" }).click();
  await expect(
    page.getByRole("dialog").getByText("PROG_C lecturers: at most 1 a day"),
  ).toBeVisible();
});
