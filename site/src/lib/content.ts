import fs from "node:fs";
import path from "node:path";
import { REPO_ROOT } from "./paths";
import { renderMarkdown, readRepo, type Rendered } from "./markdown";
import reference from "../data/reference.json";

export interface Page extends Rendered {
  slug: string;
  nav: string;
  source: string; // repository path, for "edit on GitHub"
}

// ---- docs: a hand-written start, then the README's own sections -------------------

function readmeSection(start: string, end: string | null): string {
  const text = readRepo("README.md");
  const from = text.indexOf("\n" + start + "\n");
  if (from < 0) throw new Error(`README.md has no "${start}"`);
  const to = end ? text.indexOf("\n" + end + "\n", from + 1) : -1;
  const body = text.slice(from + 1, to < 0 ? undefined : to + 1);
  // one heading level up: the section's heading becomes the page's title
  return body.replace(/^(#{2,6}) /gm, (_, h: string) => h.slice(1) + " ");
}

const DOCS: { slug: string; nav: string; load: () => { md: string; source: string } }[] = [
  {
    slug: "",
    nav: "Getting started",
    load: () => ({ md: fs.readFileSync(path.join(REPO_ROOT, "site/src/content/getting-started.md"), "utf8"), source: "site/src/content/getting-started.md" }),
  },
  {
    slug: "concepts",
    nav: "Concepts",
    load: () => ({ md: fs.readFileSync(path.join(REPO_ROOT, "site/src/content/concepts.md"), "utf8"), source: "site/src/content/concepts.md" }),
  },
  { slug: "format", nav: "The .px format", load: () => ({ md: readmeSection("## Format", "### Errors"), source: "README.md" }) },
  { slug: "errors", nav: "Errors", load: () => ({ md: readmeSection("### Errors", "## Commands"), source: "README.md" }) },
  { slug: "commands", nav: "Commands at a glance", load: () => ({ md: readmeSection("## Commands", "## Prior art"), source: "README.md" }) },
  { slug: "prior-art", nav: "Prior art & license", load: () => ({ md: readmeSection("## Prior art", null), source: "README.md" }) },
];

let docsCache: Promise<Page[]> | null = null;
export function docs(): Promise<Page[]> {
  docsCache ??= Promise.all(
    DOCS.map(async (d) => {
      const { md, source } = d.load();
      const r = await renderMarkdown(md, { repoPath: source === "README.md" ? "README.md" : undefined, stripTitle: true });
      return { ...r, slug: d.slug, nav: d.nav, source };
    }),
  );
  return docsCache;
}

// ---- tutorials: examples/NN-name/README.md ----------------------------------------

export interface Tutorial extends Page {
  number: string;
  short: string;
  thumb: string | null;
  uses: string;
}

function tutorialTable(): Map<string, { thumb: string; uses: string }> {
  const out = new Map();
  for (const line of readRepo("examples/README.md").split("\n")) {
    const m = /^\| <img src="([^"]+)"[^|]*\| \[[^\]]+\]\(([^)]+)\) \| (.+) \|$/.exec(line);
    if (m) out.set(m[2], { thumb: "/examples/" + m[1], uses: m[3] });
  }
  return out;
}

let tutorialsCache: Promise<Tutorial[]> | null = null;
export function tutorials(): Promise<Tutorial[]> {
  tutorialsCache ??= (async () => {
    const table = tutorialTable();
    const dirs = fs
      .readdirSync(path.join(REPO_ROOT, "examples"))
      .filter((d) => /^\d\d-/.test(d) && fs.existsSync(path.join(REPO_ROOT, "examples", d, "README.md")))
      .sort();
    return Promise.all(
      dirs.map(async (d) => {
        const source = `examples/${d}/README.md`;
        const r = await renderMarkdown(readRepo(source), { repoPath: source, stripTitle: true });
        const [, number, short] = /^(\d\d)\s*·\s*(.+)$/.exec(r.title) ?? [null, d.slice(0, 2), r.title];
        const row = table.get(d);
        return { ...r, slug: d, nav: short, source, number, short, thumb: row?.thumb ?? null, uses: row?.uses ?? "" };
      }),
    );
  })();
  return tutorialsCache;
}

export async function tutorialsIndex(): Promise<Rendered> {
  const md = readRepo("examples/README.md")
    // the table becomes the cards on the page; the setup and upkeep sections stay
    .replace(/\n## Start here[\s\S]*?(?=\n## Setting up)/, "\n")
    .replace(/\n## What's in each[\s\S]*?(?=\n## How these stay correct)/, "\n");
  return renderMarkdown(md, { repoPath: "examples/README.md", stripTitle: true });
}

// ---- the changelog --------------------------------------------------------------

export function changelog(): Promise<Rendered> {
  return renderMarkdown(readRepo("CHANGELOG.md"), { repoPath: "CHANGELOG.md", stripTitle: true });
}

// ---- the reference: pxart's own help ----------------------------------------------

export type Command = (typeof reference.commands)[number];
export type Topic = (typeof reference.topics)[number];
export const ref = reference;
export const TOPIC_ORDER = ["LOOKING", "CHECKING", "EDITING", "DRAWING", "CONVERTING", "HELP"];
export const TOPIC_BLURB: Record<string, string> = {
  LOOKING: "Render previews, sheets, GIFs and scenes to look at while you work.",
  CHECKING: "Find format errors, read sizes and colors, prove two renders match.",
  EDITING: "Change frames, palettes and files, rewriting only the lines that change.",
  DRAWING: "Lines, shapes, fills, shading and outlines in palette keys.",
  CONVERTING: "Get art in from PNGs and out to Aseprite, Tiled or plain PNGs.",
  HELP: "The reference itself, by topic or command.",
};
