# FRONTEND LIB (SHARED UTILITIES)

**Generated:** 2026-04-19

## OVERVIEW
Centralized API client library providing typed request helpers, auth flows, and polling utilities. Imported by pages and components via `@/lib/...` alias.

## STRUCTURE
- `api.ts`: Core `apiRequest()` helper with retry/error handling
- `auth.ts`: Register/login/logout flows, token management
- `token.ts`: Access/refresh token helpers (localStorage + cookies)
- `upload.ts`: File upload + analysis polling
- `generate.ts`: Submit generation + poll task status
- `history.ts`: Design history fetch + rollback
- `preview.ts`: Preview fetch/update helpers
- `export.ts`: Export trigger + polling

## CONVENTIONS
- **Import Alias**: All imports use `@/lib/...` (configured in tsconfig.json paths).
- **Credentials**: All `apiRequest()` calls use `credentials: 'include'` to send cookies.
- **Error Handling**: Functions throw typed errors. Components wrap in try/catch and display user-friendly messages.
- **Polling Pattern**: Functions like `pollForAnalysis()` and `pollTaskStatus()` use exponential backoff with max attempts.
- **Token Management**: Access tokens stored in cookies (httpOnly via server routes). Refresh tokens stored in localStorage for client-side refresh logic.
- **Retry Logic**: `apiRequest()` retries on network errors (max 3 attempts) with exponential backoff.

## ANTI-PATTERNS
- **NO Direct fetch() in Components**: Always use `apiRequest()` or specific helpers (uploadFile, submitGeneration, etc.).
- **NO Hardcoded API URLs**: Use environment variable `BACKEND_API_URL` or rely on server-side proxy (`/api/*`).
- **NO Token Manipulation**: Never manually set/read access_token cookie from client. Use server routes for auth.
- **NO Infinite Polling**: All polling functions have max attempts and timeout limits.

## USAGE EXAMPLES
**Upload & Poll:**
```typescript
import { uploadFile, pollForAnalysis } from '@/lib/upload';

const taskId = await uploadFile(file);
const result = await pollForAnalysis(taskId);
```

**Generate Pattern:**
```typescript
import { submitGeneration, pollTaskStatus } from '@/lib/generate';

const taskId = await submitGeneration({
  designId: 123,
  prompt: "floral",
  style: "watercolor"
});
const result = await pollTaskStatus(taskId);
```

**Auth Flow:**
```typescript
import { login, logout } from '@/lib/auth';

await login({ email, password }); // Sets cookies
await logout(); // Clears cookies
```

## NOTES
- **Server-Side Proxy**: Frontend uses `/api/[...path]/route.ts` to proxy requests to backend and attach Authorization header from cookies.
- **Polling Strategy**: Default max attempts: 60, interval: 2s with exponential backoff (up to 10s).
- **Error Codes**: Functions map HTTP status codes to user-friendly messages (401 → "Unauthorized", 404 → "Not Found", etc.).
- **Used By**: All frontend pages and components (UploadTab, GenerateTab, HistoryTab, preview page, export page, auth pages).
