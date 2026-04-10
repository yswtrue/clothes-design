import type { ValidationErrors, LoginCredentials, RegisterCredentials } from '@/types/auth';

export function validateUsername(username: string): string | undefined {
  if (!username) return '用户名不能为空';
  if (username.length < 3) return '用户名至少需要3个字符';
  if (username.length > 50) return '用户名不能超过50个字符';
  if (!/^[a-zA-Z0-9_]+$/.test(username)) return '用户名只能包含字母、数字和下划线';
  return undefined;
}

export function validatePassword(password: string): string | undefined {
  if (!password) return '密码不能为空';
  if (password.length < 8) return '密码至少需要8个字符';
  if (!/[a-z]/.test(password)) return '密码必须包含小写字母';
  if (!/[A-Z]/.test(password)) return '密码必须包含大写字母';
  if (!/[0-9]/.test(password)) return '密码必须包含数字';
  return undefined;
}

export function validateLoginForm(credentials: LoginCredentials): ValidationErrors {
  const errors: ValidationErrors = {};
  
  const usernameError = validateUsername(credentials.username);
  if (usernameError) errors.username = usernameError;
  
  if (!credentials.password) errors.password = '密码不能为空';
  
  return errors;
}

export function validateRegisterForm(credentials: RegisterCredentials): ValidationErrors {
  const errors: ValidationErrors = {};
  
  const usernameError = validateUsername(credentials.username);
  if (usernameError) errors.username = usernameError;
  
  const passwordError = validatePassword(credentials.password);
  if (passwordError) errors.password = passwordError;
  
  if (!credentials.confirmPassword) {
    errors.confirmPassword = '确认密码不能为空';
  } else if (credentials.password !== credentials.confirmPassword) {
    errors.confirmPassword = '两次输入的密码不一致';
  }
  
  return errors;
}

export async function login(
  username: string, 
  password: string, 
  rememberMe: boolean = false
): Promise<{ success: boolean; data?: { access_token: string; refresh_token: string }; error?: string }> {
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.detail || '登录失败' };
    }

    const storage = rememberMe ? localStorage : sessionStorage;
    storage.setItem('access_token', data.access_token);
    storage.setItem('refresh_token', data.refresh_token);

    return { success: true, data };
  } catch {
    return { success: false, error: '网络错误，请重试' };
  }
}

export async function register(username: string, password: string): Promise<{ success: boolean; data?: { id: number; username: string }; error?: string }> {
  try {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.detail || '注册失败' };
    }

    return { success: true, data };
  } catch {
    return { success: false, error: '网络错误，请重试' };
  }
}

export async function logout(): Promise<void> {
  try {
    const accessToken = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token') || sessionStorage.getItem('refresh_token');
    
    if (refreshToken) {
      await fetch('/api/auth/logout', { 
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...(accessToken && { 'Authorization': `Bearer ${accessToken}` })
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    }

    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('refresh_token');
  } catch (error) {
    console.error('Logout error:', error);
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('refresh_token');
  }
}
