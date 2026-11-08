import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import fs from "node:fs";

// whether the blog has a post this build will publish (drafts only with PXART_DRAFTS=1)
function hasPosts() {
  const dir = new URL("./src/content/blog/", import.meta.url);
  if (!fs.existsSync(dir)) return false;
  return fs.readdirSync(dir).some((f) => f.endsWith(".md") && !f.startsWith("_") && (process.env.PXART_DRAFTS === "1" || !/^draft:\s*true\s*$/m.test(fs.readFileSync(new URL(f, dir), "utf8"))));
}

export default defineConfig({
  site: "https://pxart.thirdbearsolutions.com",
  trailingSlash: "always",
  build: { format: "directory" },
  // a complete sitemap: docs, tutorials, reference and the blog (drafts are never built)
  // (an empty /blog/ is noindexed and left out until there's a post)
  integrations: [sitemap({ filter: (page) => !page.endsWith("/404/") && !(page.endsWith("/blog/") && !hasPosts()) })],
  // the content is read from the repository above this folder at build time
  vite: { server: { fs: { allow: [".."] } } },
});
