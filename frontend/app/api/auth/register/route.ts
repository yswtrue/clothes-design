import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    const response = await fetch(`${API_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }

    const loginResponse = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: body.email, password: body.password }),
    });

    if (!loginResponse.ok) {
      return NextResponse.json(
        { detail: 'Registration successful but login failed. Please try logging in.' },
        { status: 201 }
      );
    }

    const tokens = await loginResponse.json();

    const nextResponse = NextResponse.json(
      { success: true },
      { status: 201 }
    );

    nextResponse.cookies.set('access_token', tokens.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 900,
      path: '/',
    });

    nextResponse.cookies.set('refresh_token', tokens.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 604800,
      path: '/',
    });

    return nextResponse;
  } catch {
    return NextResponse.json(
      { detail: 'Network error. Please try again.' },
      { status: 500 }
    );
  }
}
