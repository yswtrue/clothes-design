import { NextRequest, NextResponse } from 'next/server';

const API_BASE = process.env.BACKEND_API_URL || 'http://localhost:8000';
const ALLOWED_IMAGE_HOSTS = new Set([
  'cloth-cdn.yswtrue.com',
  'localhost',
  '127.0.0.1',
]);

function apiBaseHost(): string | null {
  try {
    return new URL(API_BASE).hostname;
  } catch {
    return null;
  }
}

function isAllowedImageUrl(url: URL): boolean {
  if (!['http:', 'https:'].includes(url.protocol)) {
    return false;
  }

  const backendHost = apiBaseHost();
  return ALLOWED_IMAGE_HOSTS.has(url.hostname) || (backendHost !== null && url.hostname === backendHost);
}

export async function GET(request: NextRequest) {
  const rawUrl = request.nextUrl.searchParams.get('url');
  if (!rawUrl) {
    return NextResponse.json({ detail: 'Missing image url' }, { status: 400 });
  }

  let targetUrl: URL;
  try {
    targetUrl = new URL(rawUrl);
  } catch {
    return NextResponse.json({ detail: 'Invalid image url' }, { status: 400 });
  }

  if (!isAllowedImageUrl(targetUrl)) {
    return NextResponse.json({ detail: 'Image host is not allowed' }, { status: 403 });
  }

  try {
    const response = await fetch(targetUrl, {
      headers: { accept: 'image/*,*/*;q=0.8' },
      signal: AbortSignal.timeout(30000),
    });

    if (!response.ok || !response.body) {
      return NextResponse.json({ detail: `Image fetch failed: HTTP ${response.status}` }, { status: 502 });
    }

    const contentType = response.headers.get('content-type') || 'application/octet-stream';
    if (!contentType.startsWith('image/') && contentType !== 'application/octet-stream') {
      return NextResponse.json({ detail: 'Unsupported proxied content type' }, { status: 415 });
    }

    return new NextResponse(response.body, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=3600, stale-while-revalidate=86400',
      },
    });
  } catch (error) {
    console.error('[Image Proxy Error]', error);
    return NextResponse.json({ detail: 'Image proxy failed' }, { status: 502 });
  }
}
