// The blog's RSS feed: every published post, newest first.
import type { APIRoute } from "astro";
import { posts } from "../../lib/blog";
import { escapeHtml } from "../../lib/px";

export const GET: APIRoute = async ({ site }) => {
  const base = site!.href.replace(/\/$/, "");
  const items = (await posts())
    .map(
      (p) => `<item><title>${escapeHtml(p.title)}</title><link>${base}/blog/${p.slug}/</link><guid>${base}/blog/${p.slug}/</guid><pubDate>${new Date(p.date + "T12:00:00Z").toUTCString()}</pubDate><description>${escapeHtml(p.description)}</description></item>`,
    )
    .join("");
  const xml = `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>pxart blog</title><link>${base}/blog/</link><description>How pxart works, how to use it, and what we've learned drawing pixel art as text.</description><language>en</language>${items}</channel></rss>`;
  return new Response(xml, { headers: { "Content-Type": "application/rss+xml; charset=utf-8" } });
};
