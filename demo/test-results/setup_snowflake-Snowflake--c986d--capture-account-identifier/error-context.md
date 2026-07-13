# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: setup_snowflake.spec.ts >> Snowflake bootstrap >> login and capture account identifier
- Location: playwright\setup_snowflake.spec.ts:5:7

# Error details

```
TimeoutError: locator.fill: Timeout 90000ms exceeded.
Call log:
  - waiting for getByRole('textbox', { name: /username|email|user/i })

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - complementary "Skip to main content" [ref=e4]:
    - link "Skip to main content" [ref=e5] [cursor=pointer]
  - status [ref=e9]
```

# Test source

```ts
  1  | import { test, expect } from "@playwright/test";
  2  | import { readEnv, updateEnv } from "./env-helper";
  3  | 
  4  | test.describe("Snowflake bootstrap", () => {
  5  |   test("login and capture account identifier", async ({ page }) => {
  6  |     const env = readEnv();
  7  |     const user = env.SNOWFLAKE_USER || "DataAgent";
  8  |     const password = env.SNOWFLAKE_PASSWORD;
  9  |     const account = env.SNOWFLAKE_ACCOUNT || "";
  10 | 
  11 |     test.skip(!password, "SNOWFLAKE_PASSWORD required in .env");
  12 |     if (!account) {
  13 |       throw new Error(
  14 |         "SNOWFLAKE_ACCOUNT is empty in .env. Set your account identifier (e.g. orgname-accountname)."
  15 |       );
  16 |     }
  17 | 
  18 |     await page.goto("https://app.snowflake.com/");
  19 | 
  20 |     await page.getByRole("textbox", { name: /account identifier/i }).fill(account);
  21 |     await page.getByRole("button", { name: /^sign in$/i }).click();
  22 | 
> 23 |     await page.getByRole("textbox", { name: /username|email|user/i }).fill(user, {
     |                                                                       ^ TimeoutError: locator.fill: Timeout 90000ms exceeded.
  24 |       timeout: 90_000,
  25 |     });
  26 |     await page.getByRole("textbox", { name: /password/i }).fill(password);
  27 |     await page.getByRole("button", { name: /sign in|log in|continue/i }).click();
  28 | 
  29 |     await page.waitForURL(/snowflakecomputing\.com|app\.snowflake\.com/, {
  30 |       timeout: 90_000,
  31 |     });
  32 | 
  33 |     const url = page.url();
  34 |     const accountMatch =
  35 |       url.match(/https:\/\/([^.]+)\.([^.]+)\.snowflakecomputing\.com/) ||
  36 |       url.match(/https:\/\/([^.]+)\.snowflakecomputing\.com/);
  37 | 
  38 |     let resolvedAccount = account;
  39 |     if (accountMatch) {
  40 |       resolvedAccount =
  41 |         accountMatch.length >= 3
  42 |           ? `${accountMatch[1]}.${accountMatch[2]}`
  43 |           : accountMatch[1];
  44 |     }
  45 | 
  46 |     updateEnv({
  47 |       SNOWFLAKE_ACCOUNT: resolvedAccount,
  48 |       SNOWFLAKE_USER: user,
  49 |       PROJECT_ROOT: process.cwd().replace(/\\/g, "/"),
  50 |     });
  51 | 
  52 |     await expect(page).not.toHaveTitle(/404|Not Found/i);
  53 |     console.log(`Snowflake login OK. Account: ${resolvedAccount}`);
  54 |   });
  55 | });
  56 | 
```