import type { NextConfig } from "next";

// NEXT_OUTPUT=export builds a static site that the FastAPI app serves (Render single-service deploy).
// Static export has no server, so headers() is skipped there; the API middleware sets them instead.
const isExport = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = {
  output: isExport ? "export" : "standalone",
  trailingSlash: isExport,
  transpilePackages: ["@fogroom/shared"],
  poweredByHeader: false,
  reactStrictMode: true,
  ...(isExport
    ? {}
    : {
        async headers() {
          return [
            {
              source: "/:path*",
              headers: [
                { key: "X-Content-Type-Options", value: "nosniff" },
                { key: "X-Frame-Options", value: "DENY" },
                { key: "Referrer-Policy", value: "no-referrer" },
                { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
              ],
            },
          ];
        },
      }),
};

export default nextConfig;
