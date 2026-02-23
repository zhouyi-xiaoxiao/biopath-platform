import { defineConfig } from "@playwright/test";

const reuseExistingServer = !process.env.CI;

export default defineConfig({
  testDir: "./site/tests",
  timeout: 120000,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:4173",
    headless: true,
  },
  reporter: [["list"], ["html", { open: "never" }]],
  webServer: [
    {
      command: "python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8001",
      url: "http://127.0.0.1:8001/",
      timeout: 120000,
      reuseExistingServer,
    },
    {
      command: "python3 -m http.server 4173 --directory site",
      url: "http://127.0.0.1:4173/",
      timeout: 120000,
      reuseExistingServer,
    },
  ],
});
