// The try-me editor: edit a little folder of .px (and .map) files and see what they draw. A
// sketchpad over the site's reader (lib/px.ts, which tests/test_site.py checks against pxart's own
// renders); pxart itself checks far more.
import {
  parsePx, parseColor, parseMap, resolvePx, DEFAULT_MS, paletteFor, frameRgba, renderMap, select, sheetRgba, drawRgba, escapeHtml,
  type Rgba, type PxDoc, type PxFrame, type Rgba32,
} from "../lib/px";

interface Sample {
  name: string;
  label: string;
  mode: "frames" | "sheet" | "map";
  main: string;
  selector: string | null;
  files: Record<string, string>;
}

const onColor = ([r, g, b]: Rgba) => (0.2126 * r + 0.7152 * g + 0.0722 * b > 140 ? "#2b1e2f" : "#efe6d2");
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

function paintText(src: string, pal: Map<string, Rgba>, isMap: boolean): string {
  let inGrid = false;
  return (
    src
      .split("\n")
      .map((line) => {
        const t = line.trim();
        if (t.startsWith("#")) return `<span class="pxc-comment">${escapeHtml(line)}</span>`;
        if (isMap) {
          const m = /^(\s*)(\S)(\s+)(.+)$/.exec(line);
          return m && !inGrid ? `${m[1]}<span class="pxc-directive">${escapeHtml(m[2])}</span>${m[3]}${escapeHtml(m[4])}` : ((inGrid = inGrid || (!!t && !m)), escapeHtml(line));
        }
        if (t.startsWith("@") || /^pxart\s+\d+$/.test(t)) {
          inGrid = false;
          const [w, ...rest] = line.split(" ");
          return `<span class="pxc-directive">${escapeHtml(w)}</span>${rest.length ? " " + escapeHtml(rest.join(" ")) : ""}`;
        }
        const key = /^(\s*)(\S)(\s+)(#[0-9a-fA-F]{6,8}|transparent)(.*)$/.exec(line);
        if (key && !inGrid) {
          const rgba = parseColor(key[4]);
          const style = rgba && rgba[3] > 0 ? `--c:${key[4]};--on:${onColor(rgba)}` : "--c:transparent;--on:var(--ink)";
          return `${key[1]}<span class="pxc-px" style="${style}">${escapeHtml(key[2])}</span>${key[3]}${escapeHtml(key[4])}${escapeHtml(key[5])}`;
        }
        if (/^\S+$/.test(t)) {
          inGrid = true;
          return [...line]
            .map((ch) => {
              if (ch === "." || ch === " ") return `<span class="pxc-dot">${ch}</span>`;
              const c = pal.get(ch);
              if (!c) return `<span class="pxc-bad">${escapeHtml(ch)}</span>`;
              if (c[3] === 0) return `<span class="pxc-dot">${escapeHtml(ch)}</span>`;
              return `<span class="pxc-px" style="--c:rgb(${c[0]} ${c[1]} ${c[2]} / ${(c[3] / 255).toFixed(2)});--on:${onColor(c)}">${escapeHtml(ch)}</span>`;
            })
            .join("");
        }
        if (!t) inGrid = false;
        return escapeHtml(line);
      })
      .join("\n") + "\n"
  );
}

function rowProblems(doc: PxDoc): string[] {
  const out: string[] = [];
  if (doc.unknown.size) out.push(`keys ${[...doc.unknown].map((k) => `'${k}'`).join(", ")} aren't in the palette`);
  for (const f of doc.frames) {
    const w = f.rows[0].length;
    const bad = f.rows.findIndex((r) => r.length !== w);
    if (bad >= 0) {
      out.push(`${f.id ? `frame ${f.id}, ` : ""}row ${bad} is ${f.rows[bad].length} wide; row 0 is ${w}`);
      break;
    }
  }
  return out;
}

function setup(root: HTMLElement) {
  const samples: Sample[] = JSON.parse(root.dataset.samples!);
  const $ = <T extends HTMLElement>(s: string) => root.querySelector<T>(s)!;
  const text = $<HTMLTextAreaElement>(".pg-text");
  const paint = $(".pg-paint code");
  const paintPre = $(".pg-paint");
  const canvas = $<HTMLCanvasElement>(".pg-canvas");
  const stage = $(".pg-stage");
  const frameLabel = $(".pg-frame");
  const variantsEl = $(".pg-variants");
  const status = $(".pg-status");
  const tabs = $(".pg-tabs");
  const selBox = $(".pg-selector");
  const selInput = $<HTMLInputElement>(".pg-selector input");
  const menu = root.querySelector<HTMLSelectElement>(".pg-sample");

  let sample = samples[0];
  let files: Record<string, string> = {};
  let current = "";
  let variant = "";
  let frameIndex = 0;
  let timer = 0;
  let frames: PxFrame[] = [];
  let pal = new Map<string, Rgba>();
  let still: Rgba32 | null = null;
  let anims = new Map<string, { ms?: number }>();

  const read = (p: string) => (p in files ? files[p] : null);

  function load(s: Sample) {
    sample = s;
    mapStart = performance.now();
    files = { ...s.files };
    current = s.main;
    variant = "";
    frameIndex = 0;
    const names = Object.keys(files);
    tabs.hidden = names.length < 2;
    tabs.innerHTML = names.map((n) => `<button type="button" role="tab" data-file="${escapeHtml(n)}">${escapeHtml(n)}</button>`).join("");
    selBox.hidden = !s.selector;
    if (s.selector) selInput.value = s.selector;
    showFile(current);
  }

  function showFile(name: string) {
    current = name;
    for (const b of tabs.querySelectorAll("button")) b.setAttribute("aria-selected", String(b.dataset.file === name));
    text.value = files[name];
    text.scrollTop = 0;
    update();
  }

  function fitScale(w: number, h: number): number {
    const box = stage.getBoundingClientRect();
    const availW = Math.max(64, box.width - 32);
    const availH = Math.max(96, box.height - 32);
    return Math.max(1, Math.min(16, Math.floor(Math.min(availW / Math.max(1, w), availH / Math.max(1, h)))));
  }

  function draw() {
    if (still) {
      drawRgba(canvas, still, fitScale(still.width, still.height));
      return;
    }
    const f = frames[frameIndex % Math.max(1, frames.length)];
    if (!f) {
      drawRgba(canvas, { width: 0, height: 0, data: new Uint8ClampedArray(0) }, 1);
      return;
    }
    const w = Math.max(...frames.map((fr) => Math.max(...fr.rows.map((r) => r.length))));
    const h = Math.max(...frames.map((fr) => fr.rows.length));
    drawRgba(canvas, frameRgba(f, pal), fitScale(w, h));
    frameLabel.textContent = `${f.id || sample.main.replace(/\.px$/, "")} · ${Math.max(...f.rows.map((r) => r.length))}x${f.rows.length}${variant ? ` %${variant}` : ""}`;
  }

  function msOf(f: PxFrame): number {
    return f.ms ?? anims.get(f.id.split("/").slice(0, -1).join("/"))?.ms ?? DEFAULT_MS;
  }

  // a map's animated tiles play as they would in Tiled, all in step, timed from when the map
  // first showed; editing the text redraws without starting them over
  let mapStart = performance.now();
  let mapTimer = 0;
  function mapTick(delay: number) {
    clearTimeout(mapTimer);
    if (reduceMotion || !Number.isFinite(delay)) return;
    mapTimer = window.setTimeout(() => {
      if (sample.mode !== "map") return;
      try {
        const img = renderMap(sample.main, read, { variant: variant || undefined, time: performance.now() - mapStart });
        still = img;
        draw();
        mapTick(Math.max(16, img.nextChange));
      } catch {
        /* the next edit says what's wrong */
      }
    }, Math.max(16, delay));
  }

  function play() {
    clearTimeout(timer);
    draw();
    if (still || frames.length < 2 || reduceMotion) return;
    timer = window.setTimeout(() => {
      frameIndex = (frameIndex + 1) % frames.length;
      play();
    }, msOf(frames[frameIndex % frames.length]));
  }

  function showVariants(names: string[]) {
    if (variant && !names.includes(variant)) variant = "";
    variantsEl.innerHTML = names.length
      ? ["", ...names].map((n) => `<button type="button" data-v="${escapeHtml(n)}" aria-pressed="${n === variant}">${n ? "%" + escapeHtml(n) : "base"}</button>`).join("")
      : "";
  }

  function update() {
    files[current] = text.value;
    const isMap = current.endsWith(".map");
    const problems: string[] = [];
    let notes = "";
    // paint the open file in its own colors
    let ownPal = new Map<string, Rgba>();
    if (!isMap) {
      try {
        const d = resolvePx(current, read);
        ownPal = paletteFor(d, variant || undefined);
        problems.push(...rowProblems(d).map((p) => `${current}: ${p}`));
      } catch (e) {
        problems.push(String((e as Error).message));
        ownPal = parsePx(text.value).palette;
      }
    }
    paint.innerHTML = paintText(text.value, ownPal, isMap);

    still = null;
    frames = [];
    try {
      if (sample.mode === "frames") {
        const doc = resolvePx(sample.main, read);
        anims = doc.anims;
        let sel = { frames: doc.frames, variant: variant || undefined } as ReturnType<typeof select>;
        if (sample.selector) {
          sel = select(doc, selInput.value);
          if (sel.error) problems.push(sel.error);
          variantsEl.innerHTML = "";
        } else showVariants([...doc.variants.keys()]);
        const v = sample.selector ? sel.variant : variant || undefined;
        frames = sel.frames;
        pal = paletteFor(doc, v);
        if (sample.selector) variant = v ?? "";
        const n = frames.length;
        notes = `${n} frame${n === 1 ? "" : "s"}${doc.variants.size ? `; variants: ${[...doc.variants.keys()].join(", ")}` : ""}`;
      } else if (sample.mode === "sheet") {
        const docs = Object.keys(files)
          .filter((f) => f.endsWith(".px"))
          .map((f) => {
            try {
              return [f, resolvePx(f, read)] as const;
            } catch (e) {
              problems.push(String((e as Error).message));
              return null;
            }
          })
          .filter(Boolean) as (readonly [string, PxDoc])[];
        const names = [...new Set(docs.flatMap(([, d]) => [...d.variants.keys()]))];
        showVariants(names);
        const imgs = docs.flatMap(([, d]) => d.frames.map((f) => frameRgba(f, paletteFor(d, d.variants.has(variant) ? variant : undefined))));
        still = sheetRgba(imgs, 4, 160);
        const drawn = docs.filter(([, d]) => d.frames.length);
        frameLabel.textContent = `${drawn.length} sprite${drawn.length === 1 ? "" : "s"}, ${imgs.length} frames${variant ? ` %${variant}` : ""}`;
        const paletteOnly = docs.filter(([, d]) => !d.frames.length).map(([f]) => f);
        notes = paletteOnly.length ? `${paletteOnly.join(", ")}: colors only, imported by the others` : "";
      } else {
        const docs = Object.keys(files).filter((f) => f.endsWith(".px")).map((f) => { try { return resolvePx(f, read); } catch { return null; } });
        showVariants([...new Set(docs.flatMap((d) => (d ? [...d.variants.keys()] : [])))]);
        const img = renderMap(sample.main, read, { variant: variant || undefined, time: performance.now() - mapStart });
        mapTick(img.animated ? img.nextChange : Infinity);
        problems.push(...img.notes);
        still = img;
        const m = parseMap(files[sample.main] ?? "");
        const cols = Math.max(0, ...m.layers.flatMap((l) => l.map((r) => r.length)));
        const rows = Math.max(0, ...m.layers.map((l) => l.length));
        notes = `${cols}x${rows} cells of 16x16, ${m.layers.length} layer${m.layers.length === 1 ? "" : "s"}, ${m.legend.size} legend characters`;
        if (img.animated)
          notes += reduceMotion
            ? "; animated tiles held still (reduced motion)"
            : "; animated tiles play as in Tiled (pxart scene draws their first frame)";
        frameLabel.textContent = `${sample.main} · ${img.width}x${img.height}${variant ? ` %${variant}` : ""}`;
      }
    } catch (e) {
      problems.push(String((e as Error).message));
    }
    status.classList.toggle("bad", problems.length > 0);
    status.textContent = problems.length ? problems.join("; ") : notes || " ";
    if (frameIndex >= frames.length) frameIndex = 0;
    play();
  }

  text.addEventListener("input", update);
  text.addEventListener("scroll", () => {
    paintPre.scrollTop = text.scrollTop;
    paintPre.scrollLeft = text.scrollLeft;
  });
  selInput.addEventListener("input", () => {
    frameIndex = 0;
    update();
  });
  tabs.addEventListener("click", (e) => {
    const b = (e.target as HTMLElement).closest<HTMLButtonElement>("button");
    if (b?.dataset.file) showFile(b.dataset.file);
  });
  variantsEl.addEventListener("click", (e) => {
    const b = (e.target as HTMLElement).closest<HTMLButtonElement>("button");
    if (!b) return;
    variant = b.dataset.v ?? "";
    update();
  });
  menu?.addEventListener("change", () => {
    const s = samples.find((x) => x.name === menu.value);
    if (s) load(s);
  });
  new ResizeObserver(() => draw()).observe(stage);
  load(sample);
}

for (const root of document.querySelectorAll<HTMLElement>(".pg[data-samples]")) setup(root);
