import { test, expect } from "@playwright/test";
import { readEnv, updateEnv } from "./env-helper";

test.describe("Snowflake bootstrap", () => {
  test("login and capture account identifier", async ({ page }) => {
    const env = readEnv();
    const user = env.SNOWFLAKE_USER || "DataAgent";
    const password = env.SNOWFLAKE_PASSWORD;
    const account = env.SNOWFLAKE_ACCOUNT || "";

    test.skip(!password, "SNOWFLAKE_PASSWORD required in .env");
    if (!account) {
      throw new Error(
        "SNOWFLAKE_ACCOUNT is empty in .env. Set your account identifier (e.g. orgname-accountname)."
      );
    }

    await page.goto("https://app.snowflake.com/");

    await page.getByRole("textbox", { name: /account identifier/i }).fill(account);
    await page.getByRole("button", { name: /^sign in$/i }).click();

    await page.getByRole("textbox", { name: /username|email|user/i }).fill(user, {
      timeout: 90_000,
    });
    await page.getByRole("textbox", { name: /password/i }).fill(password);
    await page.getByRole("button", { name: /sign in|log in|continue/i }).click();

    await page.waitForURL(/snowflakecomputing\.com|app\.snowflake\.com/, {
      timeout: 90_000,
    });

    const url = page.url();
    const accountMatch =
      url.match(/https:\/\/([^.]+)\.([^.]+)\.snowflakecomputing\.com/) ||
      url.match(/https:\/\/([^.]+)\.snowflakecomputing\.com/);

    let resolvedAccount = account;
    if (accountMatch) {
      resolvedAccount =
        accountMatch.length >= 3
          ? `${accountMatch[1]}.${accountMatch[2]}`
          : accountMatch[1];
    }

    updateEnv({
      SNOWFLAKE_ACCOUNT: resolvedAccount,
      SNOWFLAKE_USER: user,
      PROJECT_ROOT: process.cwd().replace(/\\/g, "/"),
    });

    await expect(page).not.toHaveTitle(/404|Not Found/i);
    console.log(`Snowflake login OK. Account: ${resolvedAccount}`);
  });
});
