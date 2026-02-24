import { expect, test } from "@playwright/test";

test("offline pitch-safe mode is usable and has no raw fetch errors", async ({ page }) => {
  await page.goto("/?pitch=1");

  await expect(page.locator("h1")).toContainText("farm impact");
  await expect(page.locator("body")).toHaveClass(/ui-pitch-safe/);
  await expect(page.locator("#connectionPill")).toHaveText(/Disconnected|Checking/);

  await expect(page.locator("#compareBox")).not.toContainText(/Failed to fetch/i);
  await expect(page.locator("#summaryFallback")).toContainText(/one-page guide|Summary link|Pitch Safe/i);
});

test("live mode benchmark flow still works", async ({ page }) => {
  await page.goto("/?api=http://127.0.0.1:8001&tour=1");

  await expect(page.locator("#tourBackdrop")).toBeVisible();
  await page.click("#tourSkip");
  await expect(page.locator("#tourBackdrop")).toBeHidden();

  await expect
    .poll(async () => (await page.locator("#connectionPill").textContent())?.trim(), { timeout: 20000 })
    .toBe("Connected");

  await page.click("#pitchModeBtn");
  await expect(page.locator("body")).toHaveClass(/ui-ops/);

  await page.fill("#mcRuns", "40");
  await page.click("#runBenchmark");

  await expect(page.locator("#benchmarkState")).toHaveText("Benchmark complete", { timeout: 70000 });
  await expect(page.locator("#upliftValue")).not.toHaveText("n/a");
  await expect(page.locator("#compareBox")).not.toContainText(/Failed to fetch/i);

  await page.click("#liveModeBtn");
  await expect(page.locator("body")).toHaveClass(/ui-pitch-live/);

  await page.click("#pitchModeBtn");
  await expect(page.locator("body")).toHaveClass(/ui-ops/);
});
