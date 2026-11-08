// The try-me editor's markup: one sample or several (a menu), its files as tabs. The behavior is
// src/scripts/playground.ts, which every page that shows one loads.
import data from "../data/playground.json";
import { escapeHtml } from "./px";

export type Sample = (typeof data.samples)[keyof typeof data.samples];
export const SAMPLES = data.samples as Record<string, Sample>;
export const HOME = data.home;

export function playgroundHtml(names: string[], opts: { compact?: boolean; hint?: string } = {}): string {
  const samples = names.map((n) => {
    const s = SAMPLES[n];
    if (!s) throw new Error(`no playground sample "${n}" (site/scripts/gen_reference.py SAMPLES)`);
    return { name: n, ...s };
  });
  const first = samples[0];
  const menu =
    samples.length > 1
      ? `<label class="visually-hidden" for="pg-${first.name}">Sample</label><select id="pg-${first.name}" class="pg-sample">${samples
          .map((s) => `<option value="${s.name}">${escapeHtml(s.files ? Object.keys(s.files)[0] : s.name)}</option>`)
          .join("")}</select>`
      : `<span class="pg-title">${escapeHtml(first.label)}</span>`;
  return `<div class="pg${opts.compact ? " compact" : ""}" data-samples="${escapeHtml(JSON.stringify(samples))}">
  <div class="pg-bar"><span class="pg-dots" aria-hidden="true"><i></i><i></i><i></i></span>${menu}<span class="pg-hint">${escapeHtml(opts.hint ?? "edit me")}</span></div>
  <div class="pg-tabs" role="tablist" aria-label="Files" hidden></div>
  <div class="pg-body">
    <div class="pg-editor">
      <pre class="pg-paint" aria-hidden="true"><code></code></pre>
      <textarea class="pg-text" spellcheck="false" autocapitalize="off" autocomplete="off" aria-label="The file's text; edit it and the picture redraws">${escapeHtml(first.files[first.main])}</textarea>
    </div>
    <div class="pg-view">
      <div class="pg-stage checker"><canvas class="pg-canvas" width="96" height="40" role="img" aria-label="the picture, drawn from the text"></canvas></div>
      <div class="pg-selector" hidden><label>selector <input type="text" spellcheck="false" autocapitalize="off" /></label></div>
      <div class="pg-meta"><span class="pg-frame">…</span><span class="pg-variants"></span></div>
      <p class="pg-status" role="status"></p>
    </div>
  </div>
</div>`;
}
