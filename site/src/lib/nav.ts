import { docs, tutorials, ref, TOPIC_ORDER } from "./content";
import type { NavGroup } from "../layouts/Docs.astro";

export async function docsNav(): Promise<NavGroup[]> {
  const pages = await docs();
  const href = (slug: string) => (slug ? `/docs/${slug}/` : "/docs/");
  const of = (group: string) => pages.filter((p) => p.group === group).map((p) => ({ href: href(p.slug), label: p.nav }));
  return [
    { title: "The format", items: of("The format") },
    {
      title: "The tool",
      items: [
        ...of("The tool"),
        // pxart's own taxonomy, as pxart -h and the reference group the commands
        ...TOPIC_ORDER.filter((t) => t !== "HELP").map((t) => ({ href: `/reference/topics/${t.toLowerCase()}/`, label: t.charAt(0) + t.slice(1).toLowerCase() })),
        { href: "/reference/", label: "Command reference" },
      ],
    },
    {
      title: "Integrations",
      items: [
        ...of("Integrations"),
        { href: "/tutorials/08-export/", label: "Aseprite, Tiled and PNGs" },
        { href: "/tutorials/07-import/", label: "Importing PNG packs" },
      ],
    },
    { title: "Go further", items: [{ href: "/tutorials/", label: "Tutorials" }, { href: "/changelog/", label: "Changelog" }] },
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
