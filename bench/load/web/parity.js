// Drawn parity in the browser: every manifest entry, drawn from the per-frame PNG pxart.py
// rendered and from each other option, onto a canvas and read back. What a game puts on screen,
// premultiplied alpha and all, must be the same pixels whichever option it loaded.
//   parity.html?sc=s650v2&opts=atlas,atlas+,render,...
import { load, source } from './runtime.js';

const q = new URLSearchParams(location.search);
const sc = q.get('sc');
const opts = q.get('opts').split(',');

function pixels(img, [x, y, w, h]) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(img, x, y, w, h, 0, 0, w, h);
  return ctx.getImageData(0, 0, w, h).data;
}

async function main() {
  const ref = await load(`/sc/${sc}/out-frames/manifest.json`, `/sc/${sc}/out-frames/`, 'frames');
  const packs = [];
  for (const opt of opts) packs.push([opt, await load(`/sc/${sc}/out-${opt}/manifest.json`, `/sc/${sc}/out-${opt}/`, opt)]);
  const res = { sc, entries: ref.manifest.sprites.length, identical: {}, differ: {}, maxChannelDelta: {}, translucentOnly: {} };
  for (const [opt] of packs) { res.identical[opt] = 0; res.differ[opt] = []; res.maxChannelDelta[opt] = 0; res.translucentOnly[opt] = true; }
  ref.manifest.sprites.forEach((s, i) => {
    const want = pixels(...source(ref, s));
    for (const [opt, pack] of packs) {
      const e = pack.manifest.sprites[i];
      const got = pixels(...source(pack, e));
      let n = 0;
      if (got.length !== want.length) n = Math.max(want.length, got.length) / 4;  // a rect of another size
      else for (let j = 0; j < want.length; j += 4) {
        let d = 0;
        for (let c = 0; c < 4; c++) d = Math.max(d, Math.abs(want[j + c] - got[j + c]));
        if (!d) continue;
        n++;
        res.maxChannelDelta[opt] = Math.max(res.maxChannelDelta[opt], d);
        if (want[j + 3] === 255 || want[j + 3] === 0) res.translucentOnly[opt] = false;
      }
      if (n || e.frame !== s.frame || e.variant !== s.variant) res.differ[opt].push(`${s.path}: ${n} px`);
      else res.identical[opt]++;
    }
  });
  for (const opt of opts) res.differ[opt] = { count: res.differ[opt].length, first: res.differ[opt].slice(0, 5) };
  window.__results = res;
}

main().catch((e) => { window.__results = { sc, error: String((e && e.stack) || e) }; });
