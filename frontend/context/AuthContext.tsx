'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { UserResponse } from '@/types/auth';

interface AuthContextType {
  user: UserResponse | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (accessToken: string, refreshToken: string, rememberMe?: boolean) => void;
  logout: () => void;
  setUser: (user: UserResponse | null) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 初始化时从 localStorage 加载认证信息
  useEffect(() => {
    const storedAccessToken = localStorage.getItem('access_token');
    const storedRefreshToken = localStorage.getItem('refresh_token');
    const storedUser = localStorage.getItem('user');

    if (storedAccessToken && storedRefreshToken) {
      setAccessToken(storedAccessToken);
      setRefreshToken(storedRefreshToken);
      if (storedUser) {
        try {
          setUser(JSON.parse(storedUser));
        } catch {
          // 解析失败，清除无效数据
          localStorage.removeItem('user');
        }
      }
    }
    setIsLoading(false);
  }, []);

  const login = (newAccessToken: string, newRefreshToken: string, rememberMe: boolean = false) => {
    setAccessToken(newAccessToken);
    setRefreshToken(newRefreshToken);

    if (rememberMe) {
      // 记住我：保存到 localStorage
      localStorage.setItem('access_token', newAccessToken);
      localStorage.setItem('refresh_token', newRefreshToken);
    } else {
      // 不记住：保存到 sessionStorage（浏览器关闭后清除）
      sessionStorage.setItem('access_token', newAccessToken);
      sessionStorage.setItem('refresh_token', newRefreshToken);
    }
  };

  const logout = () => {
    setUser(null);
    setAccessToken(null);
    setRefreshToken(null);

    // 清除所有存储
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('refresh_token');
  };

  const handleSetUser = (newUser: UserResponse | null) => {
    setUser(newUser);
    if (newUser) {
      // 同步保存用户信息
      const storage = localStorage.getItem('access_token') ? localStorage : sessionStorage;
      storage.setItem('user', JSON.stringify(newUser));
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        refreshToken,
        isAuthenticated: !!accessToken,
        isLoading,
        login,
        logout,
        setUser: handleSetUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
