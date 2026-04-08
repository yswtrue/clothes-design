# FRONTEND WORKSPACE

**Generated:** 2026-04-05
**Workspace:** frontend (Next.js 16.2 + React 19)
**Package Manager:** Bun

## OVERVIEW
Next.js 16.2 App Router implementation using React 19 and Tailwind 4. Strict enforcement of modern async patterns and server-first architecture.

## STRUCTURE
- `app/`: Core App Router logic (layouts, pages, globals).
- `public/`: Static assets (SVG logos, favicons).
- `tsconfig.json`: Strict TypeScript configuration.
- `next.config.ts`: Native ESM configuration.
- `package.json`: Dependency manifest (Next 16, React 19).

## CONVENTIONS
- **App Router Only**: Use `app/` directory exclusively. No `pages/` directory.
- **Server Components**: Prefer Server Components by default. Use `"use client"` only for interactivity.
- **Tailwind 4**: Use modern utility classes with `@tailwindcss/postcss`. No legacy configuration files.
- **React 19 Hooks**: Utilize `use` and `Action` patterns for data handling.
- **ESM Native**: Use `.ts` or `.mjs` for configuration. No CommonJS.
- **Bun Runtime**: Execute all tasks via `bun`. Do not use `npm` or `yarn`.

## ANTI-PATTERNS
- **NO Pages Router**: Never create `pages/` directory or use `_app.tsx`/`_document.tsx`.
- **NO Legacy Hooks**: Avoid `useEffect` for data fetching; use Server Components or React 19 `use`.
- **NO Client-Side Fetching**: Minimize client-side `fetch`. Prefer Server Actions or server-side data fetching.
- **NO Legacy Tailwind**: Do not use `tailwind.config.js` if Tailwind 4 setup is active.
- **NO Global CSS**: Keep `globals.css` minimal; use Tailwind utilities for component styling.

## COMMANDS
- `bun install` - Install dependencies
- `bun run dev` - Start dev server
- `bun run build` - Production build
- `bun next lint` - Run ESLint checks

## NOTES
- **CRITICAL**: <!-- BEGIN:nextjs-agent-rules -->This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.<!-- END:nextjs-agent-rules -->
- **Metadata**: Define `metadata` objects in `layout.tsx` or `page.tsx`.
- **Fonts**: Use `next/font/google` for Geist and Geist Mono integration.
- **Styling**: `h-full antialiased` on `html` tag for consistent layout.

