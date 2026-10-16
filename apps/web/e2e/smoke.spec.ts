import { expect, test, type Page } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y";
import { invitationLink } from "./support/mail";
import { signUpAndConfirm } from "./support/accounts";

test("sign up, start blank, sign out and back in", async ({
  page,
  isMobile,
}) => {
  const { email, password } = await signUpAndConfirm(page);
  await expectNoA11yViolations(page);
  await page.getByRole("button", { name: /Start blank/ }).click();
  await page.getByLabel("Name").fill("Smoke schedule");
  await page.getByLabel("Start date").fill("2026-02-02");
  await page.getByLabel("End date").fill("2026-02-06");
  await page.getByRole("button", { name: "Create schedule" }).click();
  await page.getByRole("link", { name: "Go to schedule" }).click();
  await expect(
    page.getByRole("heading", { name: "Smoke schedule" }),
  ).toBeVisible();
  await expectNoA11yViolations(page);

  // On phones the navigation, including the org menu, sits behind a menu button.
  if (isMobile)
    await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("button", { name: /E2E/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Smoke schedule" }),
  ).toBeVisible();
});

async function createNurse(page: Page) {
  await page.goto("/resource-types");
  await page.getByRole("button", { name: "New resource type" }).click();
  await page.getByLabel("Name").fill("Nurse");
  await page.getByRole("button", { name: "Save" }).click();
  await page.goto("/resources");
  await page.getByRole("button", { name: "New resource" }).click();
  await page.getByLabel("Code").fill("N1");
  await page.getByLabel("Name").fill("Nurse One");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("heading", { name: "Nurse One" })).toBeVisible();
}

async function invite(page: Page, email: string, role: string) {
  await page.goto("/members");
  await page.getByRole("button", { name: "Invite member" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Name").fill("Invitee");
  await page.getByLabel(role).check();
  await page.getByRole("button", { name: "Send invitation" }).click();
  await expect(page.getByText(`Invitation sent to ${email}`)).toBeVisible();
}

async function switchTo(page: Page, organisation: string) {
  const menu = page.getByRole("button", { name: /E2E/ });
  if ((await menu.textContent())?.includes(organisation)) return;
  await menu.click();
  await page.getByRole("menuitem", { name: organisation }).click();
  await expect(menu).toContainText(organisation);
}

test("edit availability and invite a member", async ({ page, isMobile }) => {
  test.skip(isMobile, "editing is desktop-first");
  await signUpAndConfirm(page);
  await createNurse(page);
  await page.getByRole("tab", { name: "Weekly availability" }).click();
  await page
    .getByRole("gridcell", { name: "Mon 09:00–09:30: not set" })
    .focus();
  await page.keyboard.press("Shift+ArrowDown");
  await page.keyboard.press("1");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Save availability" }).click();
  await page.reload();
  await page.getByRole("tab", { name: "Weekly availability" }).click();
  await expect(
    page.getByRole("gridcell", { name: "Mon 09:30–10:00: available" }),
  ).toBeVisible();
  await expectNoA11yViolations(page);

  const invitee = `e2e-invitee+${String(Date.now())}@example.com`;
  await invite(page, invitee, "Viewer");
  expect(await invitationLink(invitee)).toContain("/accept-invitation?token=");
});

test("switching organisation never shows the previous organisation's data", async ({
  page,
  browser,
  isMobile,
}) => {
  test.skip(isMobile, "editing is desktop-first");
  const a = await signUpAndConfirm(page);
  await createNurse(page);

  // A second organisation invites A; existing users accept with their own password.
  const other = await browser.newContext();
  const pageB = await other.newPage();
  const b = await signUpAndConfirm(pageB);
  await invite(pageB, a.email, "Viewer");
  await page.goto(await invitationLink(a.email));
  await page.getByLabel("Password").fill(a.password);
  await page.getByRole("button", { name: "Accept invitation" }).click();
  await expect(page.getByRole("heading", { name: "You're in" })).toBeVisible();
  await other.close();

  // Accepting returns a session in the organisation just joined; switch explicitly both ways.
  await page.goto("/resources");
  await switchTo(page, a.organisation);
  await expect(page.getByText("Nurse One")).toBeVisible();
  await switchTo(page, b.organisation);
  await expect(page.getByText("No resources yet")).toBeVisible();
  await expect(page.getByText("Nurse One")).toHaveCount(0);
});
