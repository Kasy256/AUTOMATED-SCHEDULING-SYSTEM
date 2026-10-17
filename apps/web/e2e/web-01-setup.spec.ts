import { expect, test } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y";
import { signUpAndConfirm } from "./support/accounts";
import { setUpIsbat } from "./support/isbat";

test("WEB-01 (part 1): sign up, Education wizard, ISBAT imports, feasibility", async ({
  page,
  isMobile,
}) => {
  test.skip(isMobile, "setup is desktop-first");
  await signUpAndConfirm(page);
  await expectNoA11yViolations(page);
  const scheduleId = await setUpIsbat(page);
  await expect(
    page.getByRole("heading", { name: "Check & finish" }),
  ).toBeVisible();
  await expect(
    page.getByText("No problems found. The schedule is ready to solve."),
  ).toBeVisible();
  await page.getByRole("link", { name: "Go to schedule" }).click();
  await expect(page).toHaveURL(`/schedules/${scheduleId}/overview`);
  await expect(
    page.getByRole("heading", { name: "ISBAT Term 1" }),
  ).toBeVisible();
  await expectNoA11yViolations(page);
});
