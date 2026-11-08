import { docs, tutorials, ref, TOPIC_ORDER } from "./content";
import type { NavGroup } from "../layouts/Docs.astro";

export async function docsNav(): Promise<NavGroup[]> {
  const pages = await docs();
  return [
    { title: "Docs", items: pages.map((p) => ({ href: p.slug ? `/docs/${p.slug}/` : "/docs/", label: p.nav })) },
    { title: "Go further", items: [
      { href: "/tutorials/", label: "Tutorials" },
      { href: "/reference/", label: "Command reference" },
      { href: "/changelog/", label: "Changelog" },
    ] },
  ];
}

export async function tutorialsNav(): Promise<NavGroup[]> {
  const ts = await tutorials();
  return [
    { title: "Tutorials", items: [{ href: "/tutorials/", label: "Overview" }, ...ts.map((t) => ({ href: `/tutorials/${t.slug}/`, label: t.short, num: t.number }))] },
  ];
}

export function referenceNav(): NavGroup[] {
  return [
    { title: "Reference", items: [
      { href: "/reference/", label: "All commands" },
      { href: "/reference/topics/recipes/", label: "Recipes" },
      { href: "/reference/all/", label: "pxart help all" },
    ] },
    { title: "Topics", items: ref.topics.filter((t) => !["recipes"].includes(t.id)).map((t) => ({ href: `/reference/topics/${t.id}/`, label: t.title })) },
    ...TOPIC_ORDER.map((topic) => ({
      title: topic.charAt(0) + topic.slice(1).toLowerCase(),
      items: ref.commands.filter((c) => c.topic === topic).map((c) => ({ href: `/reference/${c.name}/`, label: c.name, code: true })),
    })),
  ];
}
