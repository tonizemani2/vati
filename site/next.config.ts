import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export — emits an `out/` folder of plain HTML/CSS/JS for Cloudflare Pages (vaticinus.com).
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
