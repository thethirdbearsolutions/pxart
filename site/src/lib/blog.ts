// The blog: markdown posts, <slug>.md with YAML frontmatter, in the folder PXART_BLOG_DIR names.
// The posts aren't part of this repository: pxart is free software, and its promotion (drafts
// most of all) isn't. Without PXART_BLOG_DIR the site builds with no blog.
// Drafts (draft: true) are built only with PXART_DRAFTS=1, so they never reach production.
// The plan these follow is the BLOG doc "pxart blog: four tracks ..." (v3) in Chaotic.
import fs from "node:fs";
import path from "node:path";
import { parse as parseYaml } from "yaml";
import { REPO_ROOT } from "./paths";
import { renderMarkdown, type Heading } from "./markdown";
import { resolvePx, select, paletteFor, frameRgba, type Rgba32 } from "./px";

/** Where a post's relative links resolve from, as if it sat in the repository here. */
export const BLOG_DIR = "site/src/content/blog";

/** The hubs: structure for readers, not a calendar. A post names one. */
export const HUBS: Record<string, { title: string; blurb: string }> = {
  git: { title: "Pixel art in git", blurb: "Workflow for game developers: sprites as text files you diff, review, check and export." },
  format: { title: "The format", blurb: "How .px and .map work, and why they're designed the way they are." },
  "field-notes": { title: "Field notes: drawing with models", blurb: "Real data and real failures from models drawing and reviewing pixel art." },
  builds: { title: "Builds", blurb: "Case studies and origin stories." },
  craft: { title: "Craft", blurb: "For pixel artists: palettes, readability, and pxart alongside the tools you already use." },
};

export const DEFAULT_BYLINE = "Written by Claude for pxart";
export const DEFAULT_FOOTER = "Written and fact-checked by Claude sessions working on pxart, under Ethan Jucovy's direction.";

export interface Post {
  slug: string;
  source: string; // repository path
  title: string;
  description: string;
  date: string; // YYYY-MM-DD
  updated?: string;
  hub: string;
  tags: string[];
  related: string[]; // slugs, hand-picked, at most 3
  heroSprite?: string; // FILE.px[:frame][%variant], a repository path
  credits?: string; // who drew what
  byline: string;
  footer: string;
  track?: "A" | "B";
  draft: boolean;
  html: string;
  headings: Heading[];
  words: number;
}

const showDrafts = process.env.PXART_DRAFTS === "1";

function fail(file: string, msg: string): never {
  throw new Error(`${file}: ${msg}`);
}

function splitFrontmatter(text: string, file: string): [Record<string, unknown>, string] {
  const m = /^---\n([\s\S]*?)\n---\n?([\s\S]*)$/.exec(text);
  if (!m) fail(file, "needs YAML frontmatter between --- lines");
  const data = parseYaml(m[1]) ?? {};
  if (typeof data !== "object" || Array.isArray(data)) fail(file, "frontmatter must be a mapping");
  return [data as Record<string, unknown>, m[2]];
}

const asDate = (v: unknown) => (v instanceof Date ? v.toISOString().slice(0, 10) : typeof v === "string" ? v : "");

let cache: Promise<Post[]> | null = null;
/** Every post (drafts only with PXART_DRAFTS=1), newest first, frontmatter checked. */
export function posts(): Promise<Post[]> {
  cache ??= (async () => {
    const dir = process.env.PXART_BLOG_DIR ? path.resolve(process.env.PXART_BLOG_DIR) : "";
    if (!dir || !fs.existsSync(dir)) return [];
    const files = fs.readdirSync(dir).filter((f) => f.endsWith(".md") && !f.startsWith("_")).sort();
    const out: Post[] = [];
    for (const f of files) {
      const source = `${BLOG_DIR}/${f}`;
      const [fm, body] = splitFrontmatter(fs.readFileSync(path.join(dir, f), "utf8"), source);
      const draft = fm.draft === true;
      if (draft && !showDrafts) continue;
      const slug = f.replace(/\.md$/, "");
      if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(slug)) fail(source, "a slug is lowercase words joined by hyphens");
      const title = String(fm.title ?? "");
      const description = String(fm.description ?? "");
      const date = asDate(fm.date);
      const hub = String(fm.hub ?? "");
      if (!title) fail(source, "title is required");
      if (title.length > 60) fail(source, `title is ${title.length} characters; keep it to 60`);
      if (!description) fail(source, "description is required");
      if (description.length > 155) fail(source, `description is ${description.length} characters; keep it to 155`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) fail(source, "date must be YYYY-MM-DD");
      if (!HUBS[hub]) fail(source, `hub must be one of ${Object.keys(HUBS).join(", ")}`);
      const related = Array.isArray(fm.related) ? fm.related.map(String) : [];
      if (related.length > 3) fail(source, "related lists at most 3 posts");
      const r = await renderMarkdown(body, { repoPath: source, stripTitle: true });
      out.push({
        slug,
        source,
        title,
        description,
        date,
        updated: fm.updated ? asDate(fm.updated) : undefined,
        hub,
        tags: Array.isArray(fm.tags) ? fm.tags.map(String) : [],
        related,
        heroSprite: fm.heroSprite ? String(fm.heroSprite) : undefined,
        credits: fm.credits ? String(fm.credits) : undefined,
        byline: fm.byline ? String(fm.byline) : DEFAULT_BYLINE,
        footer: fm.footer ? String(fm.footer) : DEFAULT_FOOTER,
        track: fm.track === "A" || fm.track === "B" ? fm.track : undefined,
        draft,
        html: r.html,
        headings: r.headings,
        words: body.split(/\s+/).filter(Boolean).length,
      });
    }
    // A related post must exist; one that's still a draft is left out until it's published.
    const files_ = new Set(files.map((f) => f.replace(/\.md$/, "")));
    const built = new Set(out.map((p) => p.slug));
    for (const p of out) {
      for (const s of p.related) if (!files_.has(s)) fail(p.source, `related post '${s}' doesn't exist`);
      p.related = p.related.filter((s) => built.has(s));
    }
    return out.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : a.slug.localeCompare(b.slug)));
  })();
  return cache;
}

/** The hero sprite as RGBA: FILE.px[:frame][%variant], the first frame when none is named. */
export function heroImage(spec: string, source: string): Rgba32 {
  const [, file, sel = ""] = /^([^:%]+\.px)(.*)$/.exec(spec) ?? fail(source, `heroSprite '${spec}' isn't FILE.px[:frame][%variant]`);
  const read = (p: string) => {
    const abs = path.join(REPO_ROOT, p);
    return fs.existsSync(abs) ? fs.readFileSync(abs, "utf8") : null;
  };
  const doc = resolvePx(file, read);
  const s = select(doc, sel.replace(/^:/, ""));
  if (s.error || !s.frames.length) fail(source, `heroSprite '${spec}': ${s.error ?? "no frames"}`);
  return frameRgba(s.frames[0], paletteFor(doc, s.variant));
}

export const readingMinutes = (words: number) => Math.max(1, Math.round(words / 220));
