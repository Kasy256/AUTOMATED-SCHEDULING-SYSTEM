import { expect, type Page } from "@playwright/test";

import { confirmationLink } from "./mail";

export async function signUpAndConfirm(
  page: Page,
): Promise<{ email: string; password: string; organisation: string }> {
  const stamp = `${String(Date.now())}-${Math.random().toString(36).slice(2, 7)}`;
  const email = `e2e+${stamp}@example.com`;
  const password = "e2e-correct-horse-battery";
  const organisation = `E2E ${stamp}`;
  await page.goto("/signup");
  await page.getByLabel("Organisation name").fill(organisation);
  await page.getByLabel("Timezone").fill("Africa/Kampala");
  await page.getByLabel("Your name").fill("E2E Admin");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create organisation" }).click();
  await expect(
    page.getByText(`sent a confirmation link to ${email}`),
  ).toBeVisible({ timeout: 30_000 });
  await page.goto(await confirmationLink(email));
  await expect(
    page.getByRole("heading", { name: "Email confirmed" }),
  ).toBeVisible();
  // Confirming signs the new admin in.
  await page.getByRole("link", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/setup/);
  return { email, password, organisation };
}
