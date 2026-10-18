import { expect, test } from "@playwright/test";

import { signUpAndConfirm } from "./support/accounts";
import { solve } from "./support/board";
import { setUpIsbat } from "./support/isbat";
import { invitationLink } from "./support/mail";

test("a member reads their timetable on a phone", async ({ page, browser }) => {
  test.setTimeout(420_000);
  const admin = await browser.newPage({
    viewport: { width: 1440, height: 900 },
  });
  await signUpAndConfirm(admin);
  const scheduleId = await setUpIsbat(admin);
  await solve(admin, scheduleId);
  await admin.goto(`/schedules/${scheduleId}/versions`);
  await admin.getByRole("button", { name: "Publish" }).first().click();
  await admin
    .getByRole("dialog")
    .getByRole("button", { name: "Publish" })
    .click();
  await expect(admin.getByText("Version 1 · published")).toBeVisible();

  const email = `e2e-member+${String(Date.now())}@example.com`;
  await admin.goto("/members");
  await admin.getByRole("button", { name: "Invite member" }).click();
  await admin.getByLabel("Email").fill(email);
  await admin.getByLabel("Name").fill("Phone Member");
  await admin.getByLabel("Member", { exact: true }).check();
  await admin.getByRole("button", { name: "Send invitation" }).click();
  await expect(admin.getByText(`Invitation sent to ${email}`)).toBeVisible();

  await page.goto(await invitationLink(email));
  await page.getByLabel("Password").fill("e2e-correct-horse-battery");
  await page.getByRole("button", { name: "Accept invitation" }).click();
  await expect(page.getByRole("heading", { name: "You're in" })).toBeVisible();

  // Link the member to the board's first lecturer row: the planner sorts nothing, so its first row is the
  // first lecturer, and with ISBAT every lecturer row on the default week has items.
  await admin.goto(`/schedules/${scheduleId}/planner`);
  const lecturerName =
    (await admin
      .getByRole("rowheader")
      .first()
      .locator("span")
      .first()
      .textContent()) ?? "";
  await admin.goto("/resources");
  await admin.getByRole("link", { name: lecturerName, exact: true }).click();
  await admin
    .getByLabel("Linked account")
    .selectOption({ label: `Phone Member (${email})` });
  await expect(admin.getByText("Linked account saved")).toBeVisible();

  await page.getByRole("link", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/me$/);
  await expect(
    page.getByRole("heading", { name: "My timetable" }),
  ).toBeVisible();
  await expect(page.locator("main section h2").first()).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  await page.getByRole("button", { name: "Create calendar link" }).click();
  await expect(page.getByLabel("Calendar link")).toHaveValue(/\.ics$/);
});
