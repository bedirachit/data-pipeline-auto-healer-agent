import { defineConfig } from "@playwright/test";
import path from "path";
import dotenv from "dotenv";

dotenv.config({ path: path.resolve(__dirname, "../.env") });

export default defineConfig({
  testDir: "./playwright",
  timeout: 120_000,
  use: {
    headless: false,
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
});
