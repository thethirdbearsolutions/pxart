// The layer diagram: the format at the bottom (plain text, in git), pxart's commands above it by
// their own topics (each reading the files, or writing them back), and what comes out on top.
// Built from reference.json, so the commands are the ones pxart has.
import reference from "../data/reference.json";
import { escapeHtml } from "./px";

const TOPICS: { id: string; name: string; does: string; arrow: "reads" | "writes" | "both"; out: string }[] = [
  { id: "LOOKING", name: "Looking", does: "draw what's there", arrow: "reads", out: "previews, sheets, GIFs, scenes" },
  { id: "CHECKING", name: "Checking", does: "find mistakes, measure, compare", arrow: "reads", out: "error codes, numbers, exit 1" },
  { id: "EDITING", name: "Editing", does: "change frames, palettes, files", arrow: "both", out: "the same .px, a few lines changed" },
  { id: "DRAWING", name: "Drawing", does: "lines, shapes, fills, shading", arrow: "both", out: "the same .px, its rows of keys" },
  { id: "CONVERTING", name: "Converting", does: "in from PNGs, out to other tools", arrow: "both", out: "PNGs, Aseprite, Tiled; .px from PNG" },
];

const ARROW = { reads: "reads ↑", writes: "writes ↓", both: "reads ↑ writes ↓" };

export function layersHtml(): string {
  const cmds = (topic: string) =>
    reference.commands
      .filter((c) => c.topic === topic)
      .map((c) => `<a href="/reference/${c.name}/"><code>${escapeHtml(c.name)}</code></a>`)
      .join(" ");
  const cols = TOPICS.map(
    (t) => `<div class="ly-topic">
      <div class="ly-out">${escapeHtml(t.out)}</div>
      <div class="ly-box"><a class="ly-name" href="/reference/topics/${t.id.toLowerCase()}/">${t.name}</a><p>${escapeHtml(t.does)}</p><div class="ly-cmds">${cmds(t.id)}</div></div>
      <div class="ly-arrow ly-${t.arrow}">${ARROW[t.arrow]}</div>
    </div>`,
  ).join("");
  return `<figure class="layers" aria-label="How pxart fits together: plain-text files at the bottom, pxart's commands above them, and what they produce on top">
  <div class="ly-band ly-tool"><div class="ly-label">The tool: <code>pxart</code>, one Python file</div><div class="ly-topics">${cols}</div></div>
  <div class="ly-band ly-format">
    <div class="ly-label">The format: plain text, in git</div>
    <div class="ly-files">
      <a class="ly-file" href="/docs/format/"><code>hero.px</code><span>a sprite: a palette, then grids of its keys; frames, animations, variants</span></a>
      <a class="ly-file" href="/docs/concepts/#keys-and-palettes"><code>palette.px</code><span>a palette file: colors (and variants) that sprites import</span></a>
      <a class="ly-file" href="/docs/map-format/"><code>room.map</code><span>a map: a legend of sprites, then rows of cells, in layers</span></a>
    </div>
    <p class="ly-note">Nothing procedural lives in these files. Every command reads them, writes them, or turns them into something else; a drawing command leaves behind ordinary rows of keys.</p>
  </div>
</figure>`;
}
