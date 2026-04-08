import type { ValidationErrors, LoginCredentials, RegisterCredentials } from '@/types/auth';

export function validateEmail(email: string): string | undefined {
  if (!email) return 'Email is required';
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) return 'Invalid email format';
  return undefined;
}

export function validatePassword(password: string): string | undefined {
  if (!password) return 'Password is required';
  if (password.length < 8) return 'Password must be at least 8 characters';
  if (!/[a-z]/.test(password)) return 'Password must contain a lowercase letter';
  if (!/[A-Z]/.test(password)) return 'Password must contain an uppercase letter';
  if (!/[0-9]/.test(password)) return 'Password must contain a number';
  return undefined;
}

export function validateLoginForm(credentials: LoginCredentials): ValidationErrors {
  const errors: ValidationErrors = {};
  
  const emailError = validateEmail(credentials.email);
  if (emailError) errors.email = emailError;
  
  if (!credentials.password) errors.password = 'Password is required';
  
  return errors;
}

export function validateRegisterForm(credentials: RegisterCredentials): ValidationErrors {
  const errors: ValidationErrors = {};
  
  const emailError = validateEmail(credentials.email);
  if (emailError) errors.email = emailError;
  
  const passwordError = validatePassword(credentials.password);
  if (passwordError) errors.password = passwordError;
  
  if (!credentials.confirmPassword) {
    errors.confirmPassword = 'Confirm password is required';
  } else if (credentials.password !== credentials.confirmPassword) {
    errors.confirmPassword = 'Passwords do not match';
  }
  
  return errors;
}

export async function login(email: string, password: string): Promise<{ success: boolean; error?: string }> {
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.detail || 'Login failed' };
    }

    return { success: true };
  } catch {
    return { success: false, error: 'Network error. Please try again.' };
  }
}

export async function register(email: string, password: string): Promise<{ success: boolean; error?: string }> {
  try {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.detail || 'Registration failed' };
    }

    return { success: true };
  } catch {
    return { success: false, error: 'Network error. Please try again.' };
  }
}

export async function logout(): Promise<void> {
  try {
    await fetch('/api/auth/logout', { method: 'POST' });
  } catch (error) {
    // Ignore logout errors - cookies will expire anyway
    console.error('Logout error:', error);
  }
}
