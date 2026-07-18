import { test, expect, type Page } from "@playwright/test";

/**
 * End-to-end happy path: a brand-new visitor signs up, lands on the
 * dashboard, sees their email, and signs out.
 */

const uniqueEmail = () => `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@kepler.test`;
const strongPassword = "KeplerE2EPass!2026XYZ";

async function signUp(page: Page, email: string) {
  await page.goto("/sign-up");
  await expect(page.getByRole("heading", { name: /create your account/i })).toBeVisible();
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/^password$/i).fill(strongPassword);
  await page.getByLabel(/full name/i).fill("E2E User");
  await page.getByRole("button", { name: /create account/i }).click();
  await page.waitForURL(/\/home$/, { timeout: 10_000 });
}

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/sign-in");
  await expect(page.getByRole("heading", { name: /sign in to kepler vision/i })).toBeVisible();
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/^password$/i).fill(password);
  await page.getByRole("button", { name: /^sign in$/i }).click();
  await page.waitForURL(/\/home$/, { timeout: 10_000 });
}

test.describe("Auth flow", () => {
  test("sign up → dashboard → sign out", async ({ page }) => {
    const email = uniqueEmail();
    await signUp(page, email);
    await expect(page.getByText(email)).toBeVisible();
    await expect(page.getByText(/welcome to kepler vision/i)).toBeVisible();
    // Sign out via the top bar
    await page.getByRole("button", { name: /sign out/i }).click();
    await page.waitForURL(/\/sign-in$/, { timeout: 10_000 });
  });

  test("sign in with wrong password shows an error", async ({ page }) => {
    const email = uniqueEmail();
    await signUp(page, email);
    await page.getByRole("button", { name: /sign out/i }).click();
    await page.waitForURL(/\/sign-in$/);
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/^password$/i).fill("wrong-password-1234");
    await page.getByRole("button", { name: /^sign in$/i }).click();
    await expect(page.getByText(/sign-in failed|invalid credentials|invalid/i)).toBeVisible();
  });

  test("authed user visiting /sign-in is bounced", async ({ page }) => {
    const email = uniqueEmail();
    await signUp(page, email);
    await page.goto("/sign-in");
    // The auth guard should redirect signed-in users back to /home
    await page.waitForURL(/\/home$/, { timeout: 5_000 });
  });
});
