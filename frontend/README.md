# Clothes Design Frontend

A modern, high-performance web interface for the Clothes Design platform, built with Next.js 16.2 and React 19.

## 🚀 Features

- **App Router Architecture**: Leveraging Next.js 16.2's modern routing and layout patterns.
- **React 19**: Using the latest React features including improved hooks and server components.
- **Tailwind CSS v4**: Utility-first styling with the latest generation of Tailwind.
- **Konva integration**: Advanced canvas manipulation for design placement and previews.
- **Type-Safe**: Full TypeScript implementation for robust development.
- **Bun Support**: Fast dependency management and script execution with Bun.

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| **Framework** | Next.js 16.2 |
| **UI Library** | React 19 |
| **Styling** | Tailwind CSS v4 |
| **Runtime** | Bun |
| **Canvas** | react-konva / konva |
| **Testing** | Playwright |

## 🏗 Directory Structure

```text
frontend/
├── app/              # Next.js App Router (pages, layouts, actions)
├── components/       # Reusable UI components
├── public/           # Static assets (images, fonts)
└── tests/            # E2E and unit tests
```

## ⚡ Quick Start

### 1. Prerequisites

Ensure you have `bun` installed (v1.3.10 or later). If using the project's `devenv`, enter the shell.

```bash
devenv shell
cd frontend
```

### 2. Configure Environment Variables

Create a `.env.local` file in the `frontend/` directory (or use the root `.env`):

```bash
BACKEND_API_URL=http://localhost:8000
```

### 3. Install Dependencies

```bash
bun install
```

### 4. Run Development Server

```bash
bun run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser.

### 5. Build for Production

```bash
bun run build
bun run start
```

## 🧪 Testing

We use Playwright for End-to-End testing.

```bash
# Run all tests
bun run test:e2e

# Run tests in headed mode
bun run test:headed
```

## 🎨 Development Guide

- **Server Components**: Prefer Server Components for data fetching. Use `"use client"` only when interactivity is required.
- **Styling**: Follow Tailwind v4 patterns. Avoid adding custom CSS to `globals.css` unless necessary.
- **Canvas**: For design manipulation, use the `react-konva` components.

## 📄 Related Documentation

- [Project Root README](../README.md)
- [Backend Documentation](../backend/README.md)
