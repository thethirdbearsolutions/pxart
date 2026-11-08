// Copy the examples' images into public/examples/ so the tutorials can show them.
// The images live in examples/ (the tests rebuild them byte for byte); this copy is
// a build product, ignored by git.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const src = path.join(site, "..", "examples");
const dest = path.join(site, "public", "examples");

fs.rmSync(dest, { recursive: true, force: true });
let n = 0;
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const from = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(from);
    else if (/\.(png|gif)$/i.test(entry.name)) {
      const to = path.join(dest, path.relative(src, from));
      fs.mkdirSync(path.dirname(to), { recursive: true });
      fs.copyFileSync(from, to);
      n++;
    }
  }
}
walk(src);
console.log(`sync-assets: copied ${n} images from examples/ to public/examples/`);
