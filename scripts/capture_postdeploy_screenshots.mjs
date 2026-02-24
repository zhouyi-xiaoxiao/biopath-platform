#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import { chromium, devices } from "playwright";

const baseArg = process.argv[2] || process.env.BIOPATH_PUBLIC_URL;
if (!baseArg) {
  console.error("Usage: node scripts/capture_postdeploy_screenshots.mjs <public-base-url>");
  process.exit(1);
}

const base = baseArg.replace(/\/+$/, "");
const outDir = path.resolve("docs/postdeploy-screenshots");
await fs.mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const ipad = await browser.newContext({ ...devices["iPad Pro 11"] });

async function shot(ctx, relUrl, file, options = {}) {
  const page = await ctx.newPage();
  await page.addInitScript(() => {
    localStorage.setItem("biopath_tour_completed", "1");
  });
  await page.goto(`${base}${relUrl}`, { waitUntil: "networkidle" });
  if (options.waitMs) await page.waitForTimeout(options.waitMs);
  if (options.click) await page.click(options.click);
  if (options.waitText) await page.waitForSelector(`text=${options.waitText}`);
  await page.screenshot({ path: path.join(outDir, file), fullPage: options.fullPage ?? true });
  await page.close();
}

await shot(desktop, "/", "studio-home-desktop.png", { waitMs: 800 });
await shot(desktop, "/?pitch=1", "studio-pitch-safe-desktop.png", { waitMs: 800 });
await shot(desktop, "/pitch-deck.html#s1", "deck-s1-desktop.png", { waitMs: 500 });
await shot(desktop, "/pitch-deck.html#s6", "deck-s6-desktop.png", { waitMs: 500 });
await shot(desktop, "/pitch-deck.html#s8", "deck-s8-desktop.png", { waitMs: 500 });
await shot(desktop, "/pitch-script.html", "script-top-desktop.png", { waitMs: 500 });
await shot(desktop, "/finance-pricing.html", "finance-top-desktop.png", { waitMs: 500 });

await shot(ipad, "/", "studio-home-ipad.png", { waitMs: 700, fullPage: true });
await shot(ipad, "/pitch-deck.html#s1", "deck-s1-ipad.png", { waitMs: 700, fullPage: true });
await shot(ipad, "/pitch-script.html", "script-top-ipad.png", { waitMs: 700, fullPage: true });

await browser.close();
console.log(`Saved screenshots to ${outDir}`);
