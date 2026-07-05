# FRONTEND COMPONENTS

**Generated:** 2026-04-19

## OVERVIEW
React 19 component library using Next.js App Router patterns. Mix of Server Components (presentational) and Client Components (interactive).

## STRUCTURE
```
components/
├── dashboard/
│   ├── OverviewTab.tsx      # Server Component (summary tiles)
│   ├── UploadTab.tsx         # Client (file upload + polling)
│   ├── GenerateTab.tsx       # Client (pattern generation)
│   ├── HistoryTab.tsx        # Client (design history)
│   └── TemplatesTab.tsx      # Client (template listing)
├── upload/
│   ├── DropZone.tsx          # Client (drag-drop)
│   ├── UploadProgress.tsx    # Client (progress bar)
│   └── AnalysisResult.tsx    # Client (analysis UI)
├── generate/
│   ├── MaterialSelector.tsx  # Client (needs "use client")
│   ├── GenerationProgress.tsx # Client (lazy loaded)
│   └── PatternResult.tsx     # Client (lazy loaded)
├── preview/
│   └── PreviewCanvas.tsx     # Client (Konva - lazy loaded, ssr:false)
├── history/
│   ├── VersionList.tsx       # Client (needs "use client" added)
│   ├── DesignCard.tsx        # Server Component
│   ├── Pagination.tsx        # Server Component
│   └── ConfirmModal.tsx      # Server Component
├── export/
│   ├── ExportProgress.tsx    # Client
│   └── DownloadButton.tsx    # Client
├── ErrorBoundary/
│   ├── index.tsx             # Client ErrorBoundary
│   └── ErrorDisplay.tsx      # Client error UI
├── LazyComponents.tsx        # Dynamic imports (ssr:false)
└── RouteGuard.tsx            # Client auth guard
```

## CONVENTIONS
- **Server Components First**: Default to Server Components (no "use client"). Only add "use client" when using hooks, event handlers, or browser APIs.
- **Client Component Rule**: Add "use client" directive if component uses:
  - React hooks (useState, useEffect, useContext, etc.)
  - Event handlers (onClick, onChange, etc.)
  - Browser APIs (window, document, localStorage, etc.)
  - 3rd-party browser-only libraries (Konva, canvas, etc.)
- **Lazy Loading**: Heavy or browser-only components use `LazyComponents.tsx` with `dynamic(..., { ssr: false })`:
  - PreviewCanvas (Konva)
  - VersionList (large list)
  - GenerationProgress (polling UI)
  - PatternResult (result UI)
- **Tab Pattern**: Dashboard tabs (UploadTab, GenerateTab, HistoryTab) are stateful containers. They:
  - Manage state (useState)
  - Fetch/poll data
  - Compose presentational children
- **Presentational Children**: DesignCard, Pagination, ConfirmModal, OverviewTab are pure presentation—prefer Server Components.
- **Import Alias**: Use `@/lib/...` for library imports, `@/components/...` for cross-component imports.

## ANTI-PATTERNS
- **NO Missing "use client"**: Components with hooks/events must have "use client". Known issues:
  - `history/VersionList.tsx` uses useState/useEffect but lacks "use client" directive—**MUST FIX**
  - `generate/MaterialSelector.tsx` has onClick but lacks "use client"—**MUST FIX**
- **NO Server-Side Konva**: PreviewCanvas must always be lazy-loaded with `ssr: false`.
- **NO Global State**: Use React Context (AuthContext) sparingly. Prefer prop drilling or server-side data fetching.
- **NO Legacy Hooks**: Avoid `useEffect` for data fetching. Prefer Server Components or React 19 `use()` for async data.

## CLIENT/SERVER SPLIT
**Client Components** (has "use client"):
- ErrorBoundary, RouteGuard, LazyComponents
- All dashboard tabs (Upload, Generate, History, Templates)
- upload/* (DropZone, UploadProgress, AnalysisResult)
- preview/* (PreviewCanvas)
- generate/* (GenerationProgress, PatternResult)
- export/* (ExportProgress, DownloadButton)

**Server Components** (no "use client"):
- dashboard/OverviewTab
- history/* (DesignCard, Pagination, ConfirmModal, VersionList*)
- generate/* (MaterialSelector*)

*Note: VersionList and MaterialSelector should be Client Components but currently lack directive—needs fix.

## USAGE EXAMPLES
**Dashboard Composition:**
```tsx
// app/dashboard/page.tsx
import OverviewTab from '@/components/dashboard/OverviewTab';
import UploadTab from '@/components/dashboard/UploadTab';
// ...

export default function DashboardPage() {
  return (
    <div>
      <OverviewTab />
      <UploadTab />
      {/* other tabs */}
    </div>
  );
}
```

**Lazy Loading:**
```tsx
// components/LazyComponents.tsx
import dynamic from 'next/dynamic';

export const LazyPreviewCanvas = dynamic(
  () => import('./preview/PreviewCanvas'),
  { ssr: false, loading: () => <div>Loading canvas...</div> }
);
```

## NOTES
- **Tailwind 4**: Use utility classes. Avoid custom CSS in `globals.css`.
- **next/image**: Use for all images. Configure `remotePatterns` in `next.config.ts`.
- **Error Boundaries**: Wrap layout with ErrorBoundary to catch runtime errors.
- **Route Guard**: `RouteGuard` checks auth tokens and redirects to /login if missing.
- **Known Issues**: 2 components need "use client" added (VersionList, MaterialSelector).
