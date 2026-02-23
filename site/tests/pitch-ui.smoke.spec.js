import { expect, test } from "@playwright/test";

test("pitch ui smoke: auto connect, tour, pitch mode, benchmark refresh", async ({ page }) => {
  await page.goto("/?api=http://127.0.0.1:8001&tour=1");

  await expect(page.locator("h1")).toContainText(
    "Move from manual trap placement to benchmark-backed decisions"
  );

  await expect(page.locator("#tourBackdrop")).toBeVisible();
  await page.click("#tourSkip");
  await expect(page.locator("#tourBackdrop")).toBeHidden();

  await expect
    .poll(async () => {
      return (await page.locator("#connectionPill").textContent())?.trim();
    }, { timeout: 20000 })
    .toBe("Connected");

  await page.fill("#mcRuns", "60");
  await page.click("#runBenchmark");

  await expect(page.locator("#benchmarkState")).toHaveText("Benchmark complete", {
    timeout: 70000,
  });
  await expect(page.locator("#upliftValue")).not.toHaveText("n/a");

  await page.click("#pitchModeBtn");
  await expect(page.locator("body")).toHaveClass(/pitch-mode/);

  await page.click("#helpBtn");
  await expect(page.locator("#tourBackdrop")).toBeVisible();
  await page.click("#tourSkip");
  await expect(page.locator("#tourBackdrop")).toBeHidden();
});
