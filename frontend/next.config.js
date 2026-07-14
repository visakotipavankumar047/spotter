/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*/",
        destination: `${backendUrl}/api/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*/`,
      },
    ];
  },
};

module.exports = nextConfig;
