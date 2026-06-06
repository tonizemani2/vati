import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export — emits an `out/` folder of plain HTML/CSS/JS, deployable anywhere (vaticinus.com).
  output: "export",
  // Static export cannot use the on-demand image optimizer, so serve images as-is.
  images: { unoptimized: true },
};

export default nextConfig;
