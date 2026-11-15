import { expect, test } from "@playwright/test";

test.describe("public page without scripts", () => {
  test.use({ javaScriptEnabled: false });

  test("shows the promise, a finished plan and the proof", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toContainText("Map in. Traps");
    await expect(page.locator("#fieldStage svg .trap")).toHaveCount(6);
    await expect(page.locator("#coords li")).toHaveCount(6);
    await expect(page.locator("#proofBody tr")).toHaveCount(4);
    await expect(page.locator("#status")).toContainText("10 Jun 2026");
    await expect(page.locator("footer")).toContainText("zhouyixiaoxiao.com");
  });
});

test("demo re-solves for a new budget, an edited map and the other layout", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#instrument")).toHaveClass(/is-live/);

  await page.locator("#budget").fill("3");
  await expect(page.locator("#budgetOut")).toHaveText("3");
  await expect(page.locator("#coords li")).toHaveCount(3);
  await expect(page.locator("#fieldStage svg .trap")).toHaveCount(3);

  await page.locator('#fieldStage rect.open[data-r="2"][data-c="8"]').click();
  await expect(page.locator("#editNote")).toContainText("Edited map");
  await expect(page.locator('#fieldStage rect.wall[data-r="2"][data-c="8"]')).toHaveCount(1);
  await expect(page.locator("#resetMap")).toBeVisible();

  await page.locator('[data-layer="baseline"]').click();
  await expect(page.locator('[data-layer="baseline"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#coordsTitle")).toHaveText("Rule-of-thumb coordinates");

  await page.locator("#resetMap").click();
  await expect(page.locator('#fieldStage rect.open[data-r="2"][data-c="8"]')).toHaveCount(1);

  const download = page.waitForEvent("download");
  await page.locator("#downloadPlan").click();
  expect((await download).suggestedFilename()).toBe("biopath-plan.json");
});

test("phone width has no horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBe(0);
});
