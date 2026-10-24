import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

export async function expectNoA11yViolations(page: Page): Promise<void> {
  // Mid-transition colours (a toast fading in) blend with the background and read as low contrast.
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  );
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(
    results.violations.map(
      (v) =>
        `${v.id}: ${v.nodes.map((n) => `${n.target.join(" ")} ${n.html.slice(0, 160)} — ${n.failureSummary ?? ""}`).join(" | ")}`,
    ),
  ).toEqual([]);
}
