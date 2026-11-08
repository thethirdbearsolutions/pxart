// Markdown from the repository (README, examples/*/README.md, CHANGELOG.md) to HTML for the
// site: links rewritten to the site's own pages or to GitHub, ```px blocks painted in their
// own palette with a render beside them, everything else highlighted by shiki.
import fs from "node:fs";
import path from "node:path";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import rehypeRaw from "rehype-raw";
import rehypeSlug from "rehype-slug";
import rehypeStringify from "rehype-stringify";
import { visit } from "unist-util-visit";
import { toString } from "hast-util-to-string";
import { createHighlighter, createCssVariablesTheme, type Highlighter } from "shiki";
import { REPO_ROOT, GITHUB_BLOB, GITHUB_TREE } from "./paths";
import { parsePx, frameSvg, escapeHtml, type Rgba, paletteFor } from "./px";
import { playgroundHtml } from "./playground";

const cssTheme = createCssVariablesTheme({ name: "pxart", variablePrefix: "--shiki-", fontStyle: true });
let highlighter: Promise<Highlighter> | null = null;
function getHighlighter() {
  highlighter ??= createHighlighter({ themes: [cssTheme], langs: ["sh", "json", "python", "toml"] });
  return highlighter;
}

export interface Heading {
  depth: number;
  id: string;
  text: string;
}

export interface Rendered {
  html: string;
  title: string;
  headings: Heading[];
  lead: string;
}

/** Where a repository path is served on the site; null for "link to GitHub". */
export function siteUrlFor(repoPath: string, hash = ""): string | null {
  const p = repoPath.replace(/\/+$/, "");
  if (p === "README.md" || p === "") {
    if (hash === "#commands") return "/reference/";
    if (hash === "#format") return "/docs/format/";
    return "/docs/";
  }
  if (p === "CHANGELOG.md") return "/changelog/";
  if (p === "examples" || p === "examples/README.md") return "/tutorials/" + hash;
  let m = /^examples\/(\d\d-[\w-]+)(?:\/README\.md)?$/.exec(p);
  if (m) return `/tutorials/${m[1]}/${hash}`;
  m = /^examples\/.+\.(png|gif)$/i.exec(p);
  if (m) return "/" + p;
  return null;
}

function rewrite(url: string, fromDir: string, isImage: boolean): string {
  if (/^([a-z]+:|#|\/)/i.test(url)) return url; // external, in-page, or already a site path
  const [pathPart, hashPart] = url.split("#");
  const hash = hashPart ? "#" + hashPart : "";
  const repoPath = path.posix.normalize(path.posix.join(fromDir, pathPart || "."));
  const site = siteUrlFor(repoPath === "." ? "" : repoPath, hash);
  if (site) return site;
  const abs = path.join(REPO_ROOT, repoPath);
  const isDir = fs.existsSync(abs) && fs.statSync(abs).isDirectory();
  if (isImage) return "/" + repoPath;
  return (isDir ? GITHUB_TREE : GITHUB_BLOB) + repoPath + hash;
}

// ---- ```px blocks ------------------------------------------------------------------

const paletteCache = new Map<string, Map<string, Rgba>>();
function paletteOf(file: string): Map<string, Rgba> {
  if (!paletteCache.has(file)) {
    let pal = new Map<string, Rgba>();
    try {
      const text = fs.readFileSync(file, "utf8");
      const doc = parsePx(text);
      const imported = doc.imports.map((p) => paletteOf(path.join(path.dirname(file), p)));
      pal = new Map([...imported.flatMap((m) => [...m]), ...doc.palette]);
    } catch {
      /* a missing file paints nothing */
    }
    paletteCache.set(file, pal);
  }
  return paletteCache.get(file)!;
}

/** Keys from the .px files beside the doc, for a snippet that leaves out lines it doesn't need. */
function folderPalette(dir: string): Map<string, Rgba> {
  const out = new Map<string, Rgba>();
  if (!fs.existsSync(dir)) return out;
  const files = fs.readdirSync(dir).filter((f) => f.endsWith(".px")).sort((a, b) => (a === "palette.px" ? -1 : b === "palette.px" ? 1 : a.localeCompare(b)));
  for (const f of files.reverse()) for (const [k, v] of paletteOf(path.join(dir, f))) out.set(k, v);
  return out;
}

function ink([r, g, b]: Rgba): string {
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum > 140 ? "#2b1e2f" : "#efe6d2";
}

export function paintPx(code: string, absDir: string | null, opts: { render?: boolean } = {}): string {
  let doc = parsePx(code);
  const imports = absDir ? doc.imports.map((p) => paletteOf(path.join(absDir, p))) : [];
  doc = parsePx(code, imports);
  let pal = paletteFor(doc);
  if (doc.unknown.size && absDir) {
    const extra = folderPalette(absDir);
    pal = new Map([...[...extra].filter(([k]) => doc.unknown.has(k)), ...pal]);
  }
  const lines = code.replace(/\n$/, "").split("\n");
  let inGrid = false;
  const html = lines
    .map((line) => {
      if (line.startsWith("#")) return `<span class="pxc-comment">${escapeHtml(line)}</span>`;
      if (line.startsWith("@") || /^pxart\s+\d+$/.test(line)) {
        inGrid = false;
        const [w, ...rest] = line.split(" ");
        return `<span class="pxc-directive">${escapeHtml(w)}</span>${rest.length ? " " + `<span class="pxc-arg">${escapeHtml(rest.join(" "))}</span>` : ""}`;
      }
      const key = /^(\S)(\s+)(#[0-9a-fA-F]{6,8}|transparent)(.*)$/.exec(line);
      if (key && !inGrid) {
        const c = key[3] === "transparent" ? "transparent" : key[3];
        const rest = key[4].replace(/(#[0-9a-fA-F]{6,8})/g, (h) => `<span class="pxc-swatch" style="--c:${h}"></span>${h}`);
        return `<span class="pxc-key" style="--c:${c};--on:${c === "transparent" ? "inherit" : ink(hexToRgba(c))}">${escapeHtml(key[1])}</span>${key[2]}<span class="pxc-swatch" style="--c:${c}"></span><span class="pxc-hex">${escapeHtml(key[3])}</span>${rest}`;
      }
      if (/^\S+$/.test(line)) {
        inGrid = true;
        return [...line]
          .map((ch) => {
            const c = pal.get(ch);
            if (ch === "." || !c || c[3] === 0) return `<span class="pxc-dot">${escapeHtml(ch)}</span>`;
            const h = `rgb(${c[0]} ${c[1]} ${c[2]} / ${(c[3] / 255).toFixed(2)})`;
            return `<span class="pxc-px" style="--c:${h};--on:${ink(c)}">${escapeHtml(ch)}</span>`;
          })
          .join("");
      }
      if (!line.trim()) inGrid = false;
      return escapeHtml(line);
    })
    .join("\n");

  const drawable = doc.frames.filter((f) => f.rows.length >= 3 && [...f.rows.join("")].every((ch) => ch === "." || pal.has(ch)));
  const renders = opts.render === false ? "" : drawable
    .slice(0, 6)
    .map((f) => `<div class="px-render-cell">${frameSvg(f, pal, { title: f.id || "render", fit: 128 })}${f.id ? `<span>${escapeHtml(f.id)}</span>` : ""}</div>`)
    .join("");
  return (
    `<figure class="px-block${renders ? " has-render" : ""}"><pre class="px-code"><code>${html}</code></pre>` +
    (renders ? `<div class="px-render" aria-label="rendered">${renders}</div>` : "") +
    `</figure>`
  );
}

function hexToRgba(h: string): Rgba {
  const n = parseInt(h.slice(1, 7), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 255];
}

// ---- the pipeline -------------------------------------------------------------------

export interface RenderOptions {
  /** the doc's path in the repository, for resolving its relative links */
  repoPath?: string;
  /** drop the first h1 (the page shows its own title) */
  stripTitle?: boolean;
}

export async function renderMarkdown(source: string, opts: RenderOptions = {}): Promise<Rendered> {
  const hl = await getHighlighter();
  const fromDir = opts.repoPath ? path.posix.dirname(opts.repoPath) : "";
  const absDir = opts.repoPath ? path.join(REPO_ROOT, fromDir) : null;
  let title = "";
  let lead = "";
  const headings: Heading[] = [];

  const file = await unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkRehype, { allowDangerousHtml: true })
    .use(rehypeRaw)
    .use(rehypeSlug)
    .use(() => (tree: any) => {
      visit(tree, "element", (node: any, index: any, parent: any) => {
        if (node.tagName === "a" && node.properties?.href) {
          node.properties.href = rewrite(String(node.properties.href), fromDir, false);
          if (/^https?:/.test(node.properties.href)) node.properties.rel = ["noopener"];
        }
        if (node.tagName === "img" && node.properties?.src) {
          node.properties.src = rewrite(String(node.properties.src), fromDir, true);
          node.properties.loading = "lazy";
          node.properties.decoding = "async";
        }
        if (/^h[1-6]$/.test(node.tagName)) {
          const depth = Number(node.tagName[1]);
          const text = toString(node);
          if (depth === 1 && !title) {
            title = text;
            if (opts.stripTitle && parent && typeof index === "number") {
              parent.children.splice(index, 1);
              return index;
            }
          } else if (depth <= 3) headings.push({ depth, id: String(node.properties.id), text });
        }
        if (node.tagName === "p" && !lead && parent?.type === "root") {
          const t = toString(node).trim();
          if (t && !node.children.some((c: any) => c.tagName === "img")) lead = t;
        }
        if (node.tagName === "pre" && node.children?.[0]?.tagName === "code") {
          const code = node.children[0];
          const cls: string[] = code.properties?.className ?? [];
          const lang = (cls.find((c) => c.startsWith("language-")) ?? "").replace("language-", "");
          const text = toString(code);
          let html: string;
          const looksPx = !lang && /^(pxart \d+|@(frame|palette|anim|variant|still) .*|\S\s+#[0-9a-fA-F]{6}.*)$/m.test(text) && /^[^\s#@]+$/m.test(text);
          if (lang === "tryme") html = playgroundHtml(text.trim().split(/\s+/), { compact: true, hint: "try me: edit it" });
          else if (lang === "px" || looksPx) html = paintPx(text, absDir);
          else if (["sh", "bash", "json", "python", "toml"].includes(lang)) {
            html = hl.codeToHtml(text.replace(/\n$/, ""), { lang: lang === "bash" ? "sh" : lang, theme: "pxart" });
            html = `<div class="code-block" data-lang="${lang}">${html}</div>`;
          } else {
            const kind = lang === "text" ? "output" : lang || "plain";
            html = `<div class="code-block" data-lang="${kind}"><pre class="plain"><code>${escapeHtml(text.replace(/\n$/, ""))}</code></pre></div>`;
          }
          parent.children[index] = { type: "raw", value: html };
        }
      });
    })
    .use(rehypeStringify, { allowDangerousHtml: true })
    .process(source);

  return { html: String(file), title, headings, lead };
}

export function readRepo(rel: string): string {
  return fs.readFileSync(path.join(REPO_ROOT, rel), "utf8");
}
