'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { getAccessToken } from '@/lib/token';

const protectedRoutes = [
  '/dashboard', 
  '/materials', 
  '/designs', 
  '/admin',
  '/preview',
  '/export',
];
const authRoutes = ['/login', '/register'];

const redirectToDashboard = ['/upload', '/generate', '/history', '/templates'];

export function RouteGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isChecking, setIsChecking] = useState(true);
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const checkAuth = () => {
      const accessToken = getAccessToken();
      const isAuthenticated = !!accessToken;

      const shouldRedirectToDashboard = redirectToDashboard.some((route) =>
        pathname.startsWith(route)
      );

      if (shouldRedirectToDashboard) {
        setAuthorized(false);
        setIsChecking(false);
        router.replace('/dashboard');
        return;
      }

      const isProtectedRoute = protectedRoutes.some((route) => 
        pathname.startsWith(route)
      );
      const isAuthRoute = authRoutes.some((route) => 
        pathname.startsWith(route)
      );

      if (isProtectedRoute && !isAuthenticated) {
        setAuthorized(false);
        setIsChecking(false);
        router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
        return;
      }

      if (isAuthRoute && isAuthenticated) {
        setAuthorized(false);
        setIsChecking(false);
        router.replace('/dashboard');
        return;
      }

      setAuthorized(true);
      setIsChecking(false);
    };

    checkAuth();
  }, [pathname, router]);

  if (isChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <div className="text-zinc-600 dark:text-zinc-400">加载中...</div>
      </div>
    );
  }

  if (!authorized) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <div className="text-zinc-600 dark:text-zinc-400">跳转中...</div>
      </div>
    );
  }

  return <>{children}</>;
}
