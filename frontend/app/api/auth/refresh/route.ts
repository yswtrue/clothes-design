import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get('refresh_token')?.value;

  if (!refreshToken) {
    return NextResponse.json(
      { detail: 'No refresh token' },
      { status: 401 }
    );
  }

  try {
    const response = await fetch(`${API_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${refreshToken}`,
      },
    });

    const data = await response.json();

    if (!response.ok) {
      const res = NextResponse.json(data, { status: response.status });
      if (response.status === 401) {
        res.cookies.delete('access_token');
        res.cookies.delete('refresh_token');
      }
      return res;
    }

    const nextResponse = NextResponse.json({ success: true }, { status: 200 });

    nextResponse.cookies.set('access_token', data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 604800,
      path: '/',
    });

    if (data.refresh_token) {
      nextResponse.cookies.set('refresh_token', data.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 604800,
        path: '/',
      });
    }

    return nextResponse;
  } catch {
    return NextResponse.json(
      { detail: 'Network error' },
      { status: 500 }
    );
  }
}
