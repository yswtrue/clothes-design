const MAX_RETRIES = 3;
const INITIAL_DELAY_MS = 1000;

interface RetryOptions {
  maxRetries?: number;
  initialDelay?: number;
}

export class NetworkError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public response?: unknown
  ) {
    super(message);
    this.name = 'NetworkError';
  }
}

async function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetriableError(error: unknown): boolean {
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return true;
  }

  if (error instanceof NetworkError) {
    const retriableStatusCodes = [408, 429, 500, 502, 503, 504];
    return (
      error.statusCode !== undefined &&
      retriableStatusCodes.includes(error.statusCode)
    );
  }

  return false;
}

export async function fetchWithRetry<T = unknown>(
  url: string,
  options?: RequestInit,
  retryOptions?: RetryOptions
): Promise<T> {
  const maxRetries = retryOptions?.maxRetries ?? MAX_RETRIES;
  const initialDelay = retryOptions?.initialDelay ?? INITIAL_DELAY_MS;

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new NetworkError(
          errorData.detail || `HTTP ${response.status}: ${response.statusText}`,
          response.status,
          errorData
        );
      }

      return (await response.json()) as T;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      if (attempt < maxRetries && isRetriableError(error)) {
        const delayMs = initialDelay * 2 ** attempt;
        console.warn(
          `Request failed (attempt ${attempt + 1}/${maxRetries + 1}), retrying in ${delayMs}ms...`,
          error
        );
        await delay(delayMs);
        continue;
      }

      throw lastError;
    }
  }

  throw lastError || new Error('Max retries exceeded');
}

export async function postWithRetry<T = unknown>(
  url: string,
  body: unknown,
  retryOptions?: RetryOptions
): Promise<T> {
  return fetchWithRetry<T>(
    url,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    },
    retryOptions
  );
}
