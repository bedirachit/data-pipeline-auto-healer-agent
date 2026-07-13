import { test } from "@playwright/test";
import { readEnv } from "./env-helper";

test.describe("Client demo walkthrough", () => {
  test("show GitHub PRs for dbt fixes", async ({ page }) => {
    const env = readEnv();
    const repo = env.GITHUB_REPO || "bedirachit/snowflake-sales-aggregate-dbt";

    await page.goto(`https://github.com/${repo}/pulls`);
    await page.waitForTimeout(3000);

    console.log("Walkthrough: review GitHub PRs for dbt model fixes.");
  });
});
