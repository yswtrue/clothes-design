import { test, expect } from '@playwright/test';
import path from 'path';
import {
  TEST_EMAIL,
  TEST_PASSWORD,
  ensureBackendAvailable,
  loginAndSaveState,
  registerUser,
  uploadMaterial,
  selectFirstMaterial,
  getLatestDesignId,
  getLatestDesignName,
  ensureAuthDir,
  ensureFrontendAvailable,
} from './utils';

const TEST_IMAGE_PATH = process.env.E2E_IMAGE_PATH
  ? path.resolve(process.env.E2E_IMAGE_PATH)
  : path.resolve(__dirname, '../../../backend/uploads/2b32c7bf-a16b-42bf-ac68-dfd1995c126d.jpg');

test.describe('Resume flow', () => {
  test.use({ storageState: 'tests/.auth/user.json' });
  test.slow();
  test.setTimeout(120000);

  test.beforeAll(async ({ request, browser }) => {
    await ensureBackendAvailable(request);
    await ensureAuthDir();
    await registerUser(request, TEST_EMAIL, TEST_PASSWORD);
    const page = await browser.newPage();
    await loginAndSaveState(page, TEST_EMAIL, TEST_PASSWORD);
    await page.close();
  });

  test.beforeEach(async ({ request }) => {
    try {
      await ensureBackendAvailable(request);
      await ensureFrontendAvailable(request);
    } catch {
      test.skip(true, 'Services not running - skipping E2E tests');
    }
  });

  test('resume from history after closing browser', async ({ page, browser }) => {
    await uploadMaterial(page, TEST_IMAGE_PATH);
    await selectFirstMaterial(page);

    const designId = await getLatestDesignId(page);
    const designName = await getLatestDesignName(page);

    await page.context().close();

    const context = await browser.newContext({ storageState: 'tests/.auth/user.json' });
    const resumePage = await context.newPage();

    await resumePage.goto('/history');
    await expect(resumePage.getByText('Design History')).toBeVisible();
    await expect(resumePage.getByText(designName)).toBeVisible();

    await resumePage.goto(`/preview/${designId}`);
    await expect(resumePage.getByText('Preview Editor')).toBeVisible();

    await resumePage.screenshot({
      path: '../.sisyphus/evidence/task-23-resume.png',
      fullPage: true,
    });
  });
});
