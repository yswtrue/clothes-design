import type { NextConfig } from "next";

const API_HOST = process.env.NEXT_PUBLIC_API_URL 
  ? new URL(process.env.NEXT_PUBLIC_API_URL).hostname 
  : 'localhost';

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8000',
        pathname: '/api/files/**',
      },
      {
        protocol: 'https',
        hostname: 'localhost',
        port: '8000',
        pathname: '/api/files/**',
      },
      ...(API_HOST !== 'localhost' ? [{
        protocol: 'https' as const,
        hostname: API_HOST,
        pathname: '/api/files/**',
      }] : []),
    ],
  },
};

export default nextConfig;
