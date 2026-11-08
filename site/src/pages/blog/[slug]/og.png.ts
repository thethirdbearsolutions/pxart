// A post's preview card (1200x630), drawn from its heroSprite at the largest integer scale that fits.
import type { APIRoute } from "astro";
import { posts, heroImage } from "../../../lib/blog";
import { card, encodePng } from "../../../lib/png";

export async function getStaticPaths() {
  return (await posts()).filter((p) => p.heroSprite).map((p) => ({ params: { slug: p.slug }, props: { p } }));
}

export const GET: APIRoute = ({ props }) => {
  const p = (props as { p: Awaited<ReturnType<typeof posts>>[number] }).p;
  const png = encodePng(card(heroImage(p.heroSprite!, p.source)));
  return new Response(png, { headers: { "Content-Type": "image/png" } });
};
