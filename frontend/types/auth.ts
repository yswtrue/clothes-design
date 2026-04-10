export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: number;
  username: string;
  created_at: string | null;
}

export interface AuthError {
  detail: string;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterCredentials {
  username: string;
  password: string;
  confirmPassword: string;
}

export interface ValidationErrors {
  username?: string;
  password?: string;
  confirmPassword?: string;
  general?: string;
}
