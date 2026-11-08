import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://pxart.thirdbearsolutions.com",
  trailingSlash: "always",
  build: { format: "directory" },
  // the content is read from the repository above this folder at build time
  vite: { server: { fs: { allow: [".."] } } },
});
