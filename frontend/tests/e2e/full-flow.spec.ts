import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs/promises';
import {
  TEST_EMAIL,
  TEST_PASSWORD,
  ensureBackendAvailable,
  loginAndSaveState,
  registerUser,
  uploadMaterial,
  selectFirstMaterial,
  getLatestDesignId,
  selectFirstTemplate,
  updatePreviewState,
  startExportAndDownload,
  ensureDownloadDir,
  ensureAuthDir,
  ensureFrontendAvailable,
} from './utils';

const TEST_IMAGE_PATH = process.env.E2E_IMAGE_PATH
  ? path.resolve(process.env.E2E_IMAGE_PATH)
  : path.resolve(__dirname, '../../../backend/uploads/de10051e-6b3c-4daa-8647-168ec0042d23.jpg');

declare global {
  interface Window {
    __e2eErrors?: string[];
  }
}

test.describe('Full user journey', () => {
  test.use({ storageState: 'tests/.auth/user.json' });
  test.slow();
  test.setTimeout(120000);

  test.beforeAll(async ({ request, browser }) => {
    try {
      await ensureBackendAvailable(request);
      await ensureAuthDir();
      await registerUser(request, TEST_EMAIL, TEST_PASSWORD);
      const page = await browser.newPage();
      await loginAndSaveState(page, TEST_EMAIL, TEST_PASSWORD);
      await page.close();
      await ensureDownloadDir();
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

  test('login → upload → generate → preview → export', async ({ page, context }) => {
    const timings: Record<string, number> = {};
    const mark = (label: string) => {
      timings[label] = Date.now();
    };
    const span = (start: string, end: string) => {
      if (timings[start] && timings[end]) {
        const seconds = Math.round((timings[end] - timings[start]) / 100) / 10;
        console.log(`Timing ${start}→${end}: ${seconds}s`);
      }
    };

    await context.addInitScript(() => {
      window.addEventListener('error', (event) => {
        window.__e2eErrors = window.__e2eErrors || [];
        window.__e2eErrors.push(event.message);
      });
      window.addEventListener('unhandledrejection', (event) => {
        window.__e2eErrors = window.__e2eErrors || [];
        window.__e2eErrors.push(String(event.reason));
      });
    });

    const consoleErrors: string[] = [];
    page.on('pageerror', (err) => consoleErrors.push(err.message));
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto('/');
    mark('upload_start');
    await uploadMaterial(page, TEST_IMAGE_PATH);
    mark('upload_done');
    span('upload_start', 'upload_done');

    mark('generate_start');
    await selectFirstMaterial(page);
    mark('generate_done');
    span('generate_start', 'generate_done');

    const designId = await getLatestDesignId(page);

    mark('preview_start');
    await page.goto(`/preview/${designId}`);
    await expect(page.getByText('Preview Editor')).toBeVisible();
    await selectFirstTemplate(page);
    await updatePreviewState(page);
    mark('preview_done');
    span('preview_start', 'preview_done');

    mark('export_start');
    await page.goto(`/export/${designId}`);
    await expect(page.getByText('Export Design')).toBeVisible();
    const downloadPath = await startExportAndDownload(page);
    mark('export_done');
    span('export_start', 'export_done');

    const stats = await fs.stat(downloadPath);
    expect(stats.size).toBeGreaterThan(0);
    expect(downloadPath).toMatch(/\.tif$/i);

    const buffer = await fs.readFile(downloadPath);
    const ascii = buffer.toString('ascii', 0, 16);
    expect(ascii.includes('II') || ascii.includes('MM')).toBeTruthy();

    const clientErrors = await page.evaluate(() => window.__e2eErrors || []);
    expect(consoleErrors, `Console errors: ${consoleErrors.join('\n')}`).toEqual([]);
    expect(clientErrors, `Client errors: ${clientErrors.join('\n')}`).toEqual([]);
  });
});
