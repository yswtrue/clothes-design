import { expect, type Page, type APIRequestContext } from '@playwright/test';

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export const AUTH_STATE_PATH = 'tests/.auth/user.json';
export const DOWNLOAD_DIR = 'tests/.downloads';
export const AUTH_DIR = 'tests/.auth';

export const TEST_PASSWORD = process.env.E2E_PASSWORD || 'SecurePass123!';
export const TEST_EMAIL =
  process.env.E2E_EMAIL || `e2e-${Date.now()}@example.com`;

export async function ensureBackendAvailable(request: APIRequestContext) {
  try {
    const response = await request.get(`${API_BASE}/health`);
    expect(response.ok()).toBeTruthy();
  } catch {
    throw new Error('Backend not available');
  }
}

export async function ensureFrontendAvailable(request: APIRequestContext) {
  const response = await request.get('/');
  expect(response.ok()).toBeTruthy();
}

export async function registerUser(request: APIRequestContext, email: string, password: string) {
  const response = await request.post(`${API_BASE}/api/auth/register`, {
    data: { email, password },
  });
  if (!response.ok()) {
    const body = await response.json().catch(() => ({}));
    if (body.detail !== 'Email already registered') {
      throw new Error(`Register failed: ${body.detail || response.status()}`);
    }
  }
}

export async function loginAndSaveState(page: Page, email: string, password: string) {
  await page.goto('/login');
  await page.fill('[name="email"]', email);
  await page.fill('[name="password"]', password);
  await page.click('button[type="submit"]');
  const response = await page.waitForResponse(
    (res) => res.url().includes('/api/auth/login') && res.status() === 200,
    { timeout: 60000 }
  );
  await response.finished();
  const cookies = await page.context().cookies();
  expect(cookies).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ name: 'access_token' }),
      expect.objectContaining({ name: 'refresh_token' }),
    ])
  );
  await page.context().storageState({ path: AUTH_STATE_PATH });
}

export async function uploadMaterial(page: Page, filePath: string) {
  await page.goto('/upload');
  const input = page.locator('input[type="file"]');
  await input.setInputFiles(filePath);
  await expect(page.getByText('Analyzing style...')).toBeVisible({ timeout: 70000 });
  await expect(page.getByText('File Details')).toBeVisible({ timeout: 70000 });
}

export async function selectFirstMaterial(page: Page) {
  await page.goto('/generate');
  const materialCard = page.locator('button', { hasText: 'MB' }).first();
  await expect(materialCard).toBeVisible({ timeout: 20000 });
  await materialCard.click();
  const [response] = await Promise.all([
    page.waitForResponse((res) => res.url().includes('/api/generate') && res.status() === 201),
    page.getByRole('button', { name: 'Generate Pattern' }).click(),
  ]);
  const result = await response.json();
  const taskId = result.task_id as string;
  const statusResponse = await page.request.get(`/api/generate/tasks/${taskId}`);
  if (!statusResponse.ok()) {
    const body = await statusResponse.json().catch(() => ({}));
    throw new Error(`Generation failed: ${body.detail || statusResponse.status()}`);
  }
  await expect(page.getByText('Generating...')).toBeVisible({ timeout: 20000 });
  await expect(page.getByText('Your pattern is ready')).toBeVisible({ timeout: 70000 });
}

export async function getLatestDesignId(page: Page) {
  const response = await page.request.get('/api/designs?page=1&limit=1');
  if (!response.ok()) {
    const body = await response.json().catch(() => ({}));
    throw new Error(`Failed to fetch designs: ${body.detail || response.status()}`);
  }
  const data = await response.json();
  const design = data.designs?.[0];
  if (!design) {
    throw new Error('No designs found after generation');
  }
  return design.id as number;
}

export async function getLatestDesignName(page: Page) {
  const response = await page.request.get('/api/designs?page=1&limit=1');
  if (!response.ok()) {
    const body = await response.json().catch(() => ({}));
    throw new Error(`Failed to fetch designs: ${body.detail || response.status()}`);
  }
  const data = await response.json();
  const design = data.designs?.[0];
  if (!design) {
    throw new Error('No designs found after generation');
  }
  return design.name as string;
}

export async function updatePreviewState(page: Page) {
  const scale = page.locator('input[type="range"]').first();
  await scale.fill('1.2');
  await expect(page.getByText('Saving changes...')).toBeVisible();
  await expect(page.getByText('Saving changes...')).toBeHidden({ timeout: 20000 });
}

export async function selectFirstTemplate(page: Page) {
  const templateButton = page.locator('button:has(img)').first();
  await expect(templateButton).toBeVisible({ timeout: 20000 });
  await templateButton.click();
  await expect(page.getByText('Saving changes...')).toBeVisible();
  await expect(page.getByText('Saving changes...')).toBeHidden({ timeout: 20000 });
}

export async function startExportAndDownload(page: Page) {
  await page.getByRole('button', { name: 'Start Export' }).click();
  await expect(page.getByText('Exporting...')).toBeVisible({ timeout: 20000 });
  await expect(page.getByText('Export Complete!')).toBeVisible({ timeout: 180000 });
  const downloadPromise = page.waitForEvent('download', { timeout: 20000 });
  await page.getByRole('link', { name: 'Download TIF (CMYK, 12K)' }).click();
  const download = await downloadPromise;
  const suggested = download.suggestedFilename();
  const downloadPath = `${DOWNLOAD_DIR}/${suggested}`;
  await download.saveAs(downloadPath);
  return downloadPath;
}

export async function ensureDownloadDir() {
  const fs = await import('fs/promises');
  await fs.mkdir(DOWNLOAD_DIR, { recursive: true });
}

export async function ensureAuthDir() {
  const fs = await import('fs/promises');
  await fs.mkdir(AUTH_DIR, { recursive: true });
}
