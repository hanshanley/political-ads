import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: process.env.TEST_BASE_URL ?? "http://127.0.0.1:4178/political-ads/" },
  webServer: process.env.TEST_BASE_URL ? undefined : {
    command: "npm run preview -- --port 4178 --strictPort",
    url: "http://127.0.0.1:4178/political-ads/",
    reuseExistingServer: false,
  },
});
