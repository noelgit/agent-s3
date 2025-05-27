import { defineConfig, devices } from "@playwright/test";
declare const process: any;

export default defineConfig({
  testDir: "./specs",
  timeout: 60000,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 1,
  reporter: "html",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    video: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "vscode",
      use: {
        ...devices["Desktop Chrome"],
        // Custom setup for VS Code browser simulation
        viewport: { width: 1280, height: 720 },
      },
    },
  ],
  webServer: {
    command:
      'echo "Note: VS Code extension tests will run against actual VS Code instance"',
    url: "http://localhost:3000",
    reuseExistingServer: true,
    ignoreHTTPSErrors: true,
  },
});
