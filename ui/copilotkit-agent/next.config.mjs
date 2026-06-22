import { dirname } from "path";
import { fileURLToPath } from "url";

const projectRoot = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["10.72.26.31", "HF-9CSMGR3-P"],
  turbopack: {
    root: projectRoot,
  },
};

export default nextConfig;
