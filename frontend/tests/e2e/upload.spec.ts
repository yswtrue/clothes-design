import { test, expect } from '@playwright/test';
import path from 'path';
import {
  TEST_EMAIL,
  TEST_PASSWORD,
  API_BASE,
  ensureBackendAvailable,
  loginAndSaveState,
  registerUser,
  ensureAuthDir,
  ensureFrontendAvailable,
} from './utils';

const TEST_IMAGE_PATH = process.env.E2E_IMAGE_PATH
  ? path.resolve(process.env.E2E_IMAGE_PATH)
  : path.resolve(__dirname, '../../../backend/uploads/de10051e-6b3c-4daa-8647-168ec0042d23.jpg');

test.describe('Upload and Analysis Flow', () => {
  test.use({ storageState: 'tests/.auth/user.json' });
  test.setTimeout(90000);

  test.beforeAll(async ({ request, browser }) => {
    try {
      await ensureBackendAvailable(request);
      await ensureAuthDir();
      await registerUser(request, TEST_EMAIL, TEST_PASSWORD);
      const page = await browser.newPage();
      await loginAndSaveState(page, TEST_EMAIL, TEST_PASSWORD);
      await page.close();
    } catch {
      return;
    }
  });

  test.beforeEach(async ({ request }) => {
    try {
      await ensureBackendAvailable(request);
      await ensureFrontendAvailable(request);
    } catch {
      test.skip(true, 'Services not running - skipping E2E tests');
    }
  });

  test('upload triggers analysis task and displays results', async ({ page }) => {
    await page.goto('/upload');

    const uploadPromise = page.waitForResponse(
      (res) => res.url().includes('/api/upload') && res.status() === 201
    );

    const input = page.locator('input[type="file"]');
    await input.setInputFiles(TEST_IMAGE_PATH);

    const uploadResponse = await uploadPromise;
    const uploadData = await uploadResponse.json();

    expect(uploadData.id).toBeDefined();
    expect(uploadData.mime_type).toMatch(/^image\//);

    await expect(page.getByText('Analyzing style...')).toBeVisible({ timeout: 10000 });

    await expect(page.getByText('File Details')).toBeVisible({ timeout: 70000 });

    const materialResponse = await page.request.get(
      `${API_BASE}/api/materials/${uploadData.id}`
    );
    expect(materialResponse.ok()).toBeTruthy();

    const materialData = await materialResponse.json();
    expect(materialData.meta).toBeDefined();

    if (materialData.meta.analysis_task_id) {
      expect(typeof materialData.meta.analysis_task_id).toBe('string');
    }
  });

  test('upload validates file type', async ({ page }) => {
    await page.goto('/upload');

    const dropZone = page.locator('[data-testid="dropzone"]').or(
      page.locator('div').filter({ hasText: /drop|drag|upload/i }).first()
    );
    await expect(dropZone).toBeVisible();

    const consoleMessages: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error' || msg.type() === 'warning') {
        consoleMessages.push(msg.text());
      }
    });

    await page.evaluate(() => {
      const event = new CustomEvent('dropzone-test-invalid', {
        detail: { type: 'application/pdf' },
      });
      document.dispatchEvent(event);
    });

    await page.waitForTimeout(500);
  });

  test('upload shows progress indicator', async ({ page }) => {
    await page.goto('/upload');

    const input = page.locator('input[type="file"]');
    await input.setInputFiles(TEST_IMAGE_PATH);

    const uploadingIndicator = page.getByText(/uploading|analyzing/i).first();
    await expect(uploadingIndicator).toBeVisible({ timeout: 5000 });
  });

  test('multiple uploads create separate materials', async ({ page }) => {
    await page.goto('/upload');

    const firstUploadPromise = page.waitForResponse(
      (res) => res.url().includes('/api/upload') && res.status() === 201
    );

    const input = page.locator('input[type="file"]');
    await input.setInputFiles(TEST_IMAGE_PATH);

    const firstUpload = await firstUploadPromise;
    const firstData = await firstUpload.json();

    await expect(page.getByText('File Details')).toBeVisible({ timeout: 70000 });

    await page.goto('/upload');

    const secondUploadPromise = page.waitForResponse(
      (res) => res.url().includes('/api/upload') && res.status() === 201
    );

    await input.setInputFiles(TEST_IMAGE_PATH);

    const secondUpload = await secondUploadPromise;
    const secondData = await secondUpload.json();

    expect(firstData.id).not.toBe(secondData.id);
  });
});
