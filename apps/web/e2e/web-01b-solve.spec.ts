import { expect, test } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y";
import { signUpAndConfirm } from "./support/accounts";
import { firstItem, solve } from "./support/board";
import { setUpIsbat } from "./support/isbat";

test("WEB-01 (part 2): solve the ISBAT schedule and see the timetable", async ({
  page,
  isMobile,
}) => {
  test.skip(isMobile, "desktop flow");
  test.setTimeout(300_000);
  await signUpAndConfirm(page);
  const scheduleId = await setUpIsbat(page);
  await solve(page, scheduleId);
  await expect(firstItem(page)).toBeVisible();
  await expectNoA11yViolations(page);
  await page.goto(`/schedules/${scheduleId}/solves`);
  await expect(
    page
      .getByRole("cell", { name: "Succeeded" })
      .or(page.getByText("Succeeded"))
      .first(),
  ).toBeVisible();
  await expectNoA11yViolations(page);
});
