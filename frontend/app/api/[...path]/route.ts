import { NextRequest, NextResponse } from 'next/server';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function refreshAccessToken(refreshToken: string): Promise<string | null> {
  try {
    const response = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${refreshToken}`,
      },
    });

    if (!response.ok) return null;

    const data = await response.json();
    return data.access_token || null;
  } catch {
    return null;
  }
}

async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const targetPath = pathname.replace(/^\/api\//, '');
  const targetUrl = `${API_BASE}/api/${targetPath}${search}`;

  const headers = new Headers(request.headers);
  headers.delete('host');
  headers.delete('content-length');

  let accessToken = request.cookies.get('access_token')?.value;
  const refreshToken = request.cookies.get('refresh_token')?.value;
  let newAccessToken: string | null = null;

  if (!accessToken && refreshToken) {
    newAccessToken = await refreshAccessToken(refreshToken);
    if (newAccessToken) {
      accessToken = newAccessToken;
    }
  }

  if (accessToken) {
    headers.set('authorization', `Bearer ${accessToken}`);
  }

  let body: BodyInit | null = null;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    const contentType = request.headers.get('content-type') || '';
    if (contentType.includes('multipart/form-data')) {
      body = await request.formData();
      headers.delete('content-type');
    } else {
      body = await request.arrayBuffer();
    }
  }

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      signal: AbortSignal.timeout(30000),
    });

    const nextResponse = new NextResponse(response.body, {
      status: response.status,
      headers: response.headers,
    });

    if (newAccessToken) {
      nextResponse.cookies.set('access_token', newAccessToken, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 604800,
        path: '/',
      });
    }

    return nextResponse;
  } catch (error) {
    if (error instanceof Error && error.name === 'TimeoutError') {
      return NextResponse.json(
        { detail: 'Gateway timeout', code: 'gateway_timeout' },
        { status: 504 }
      );
    }
    console.error('[Proxy Error]', error);
    return NextResponse.json(
      { detail: 'Bad gateway', code: 'bad_gateway' },
      { status: 502 }
    );
  }
}

export async function GET(request: NextRequest) {
  return proxy(request);
}

export async function POST(request: NextRequest) {
  return proxy(request);
}

export async function PATCH(request: NextRequest) {
  return proxy(request);
}

export async function DELETE(request: NextRequest) {
  return proxy(request);
}
