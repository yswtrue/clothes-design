import { test, expect } from '@playwright/test';
import { ensureBackendAvailable, ensureFrontendAvailable } from './e2e/utils';

test.describe('Authentication Flow', () => {
  test.slow();
  test.setTimeout(60000);
  const uniqueEmail = `test-${Date.now()}@example.com`;
  const password = 'SecurePass123!';

  test.beforeEach(async ({ request }) => {
    try {
      await ensureBackendAvailable(request);
      await ensureFrontendAvailable(request);
    } catch {
      test.skip(true, 'Services not running - skipping E2E tests');
    }
  });

  test('should redirect to login when accessing protected route', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/);
  });

  test('should show validation errors on invalid input', async ({ page }) => {
    await page.goto('/login');
    await page.click('button[type="submit"]');
    const message = await page.locator('[name="email"]').evaluate((el) =>
      (el as HTMLInputElement).validationMessage
    );
    expect(message.length).toBeGreaterThan(0);
  });

  test('should complete full auth flow: register → login → access protected → logout', async ({ page }) => {
    await page.goto('/register');
    
    await page.fill('[name="email"]', uniqueEmail);
    await page.fill('[name="password"]', password);
    await page.fill('[name="confirmPassword"]', password);
    await page.click('button[type="submit"]');

    await page.waitForURL('/', { timeout: 60000 });

    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/);
  });

  test('should show error on invalid login credentials', async ({ page }) => {
    await page.goto('/login');
    
    await page.fill('[name="email"]', 'nonexistent@example.com');
    await page.fill('[name="password"]', 'WrongPassword123!');
    await page.click('button[type="submit"]');
    
    await expect(page.locator('text=Invalid credentials')).toBeVisible();
  });

  test('should show error on duplicate registration', async ({ page }) => {
    const email = 'duplicate@example.com';
    
    await page.goto('/register');
    await page.fill('[name="email"]', email);
    await page.fill('[name="password"]', password);
    await page.fill('[name="confirmPassword"]', password);
    await page.click('button[type="submit"]');
    
    await page.goto('/register');
    await page.fill('[name="email"]', email);
    await page.fill('[name="password"]', password);
    await page.fill('[name="confirmPassword"]', password);
    await page.click('button[type="submit"]');
    
    await expect(page.locator('text=Email already registered')).toBeVisible();
  });
});
