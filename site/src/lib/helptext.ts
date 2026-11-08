// pxart's help text, as printed, made into HTML: escaped, with command and topic names
// linked to their reference pages and the option lines picked out.
import { escapeHtml } from "./px";
import reference from "../data/reference.json";

const COMMANDS = new Set(reference.commands.map((c) => c.name));
const TOPICS = new Map(reference.topics.map((t) => [t.id, t.id]));

export function commandUrl(name: string) {
  return `/reference/${name}/`;
}
export function topicUrl(id: string) {
  return `/reference/topics/${id.toLowerCase()}/`;
}

export function helpHtml(text: string, self?: string): string {
  return text
    .replace(/\n$/, "")
    .split("\n")
    .map((raw) => {
      let line = escapeHtml(raw);
      // an option line: '  -o O, --out O    what it does'
      const opt = /^(\s{2,4})(-{1,2}[\w-]+(?:[ ,=][^\s].*?)?)(\s{2,}|$)(.*)$/.exec(line);
      if (opt && raw.trimStart().startsWith("-")) line = `${opt[1]}<span class="h-opt">${opt[2]}</span>${opt[3]}${link(opt[4], self)}`;
      else if (/^[A-Z][A-Z &()'\-,.:]{3,}$/.test(raw.trim()) && !raw.startsWith("    ")) line = `<span class="h-head">${line}</span>`;
      else if (/^(usage:|positional arguments:|options:)/.test(raw)) line = `<span class="h-sect">${line}</span>`;
      else if (/^\s+\$ /.test(raw)) line = line.replace(/^(\s+)\$ (.*)$/, (_, s, cmd) => `${s}<span class="h-prompt">$</span> <span class="h-cmd">${link(cmd, self)}</span>`);
      else line = link(line, self);
      return line;
    })
    .join("\n");
}

function link(html: string, self?: string): string {
  return html.replace(/\bpxart (help )?([A-Za-z][\w-]*)/g, (m, help: string | undefined, word: string) => {
    const id = word.toLowerCase();
    if (help && id === "all") return `<a href="/reference/all/">${m}</a>`;
    if (help && word !== id && TOPICS.has(id)) return `<a href="${topicUrl(id)}">${m}</a>`;
    if (help && ["recipes", "worlds", "slots"].includes(word)) return `<a href="${topicUrl(id)}">${m}</a>`;
    if (COMMANDS.has(word) && word !== self) return `<a href="${commandUrl(word)}">${m}</a>`;
    return m;
  });
}
