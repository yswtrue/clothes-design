import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // 增加中间件/代理的请求体大小限制到 50MB
    proxyClientMaxBodySize: '50mb',
  },
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8000',
        pathname: '/api/files/**',
        search: '',
      },
      {
        protocol: 'http',
        hostname: '127.0.0.1',
        port: '8000',
        pathname: '/api/files/**',
        search: '',
      },
    ],
  },
};

export default nextConfig;

import('@opennextjs/cloudflare').then(m => m.initOpenNextCloudflareForDev());
