// The load bench's static server: HTTP/2 over TLS, serving the way a CDN serves a deployed game.
// Text (.json, .px, .js, .html) is precompressed with brotli (quality 11), else gzip (level 9);
// images go as they are; nothing is cached between runs (cache-control: no-store). An
// out-<option>.gzip/ directory is served gzip-only (the ".px, gzip" option).
//   node bench/load/web/server.mjs WORK_DIR PORT CERT_DIR
// PORT 0 takes a free port; the first line printed is "listening https://localhost:<port>".
// /sc/<scenario>/... is WORK_DIR/<scenario>/...; /px.js is pxart's js/px.ts with its types
// stripped; /pxc/... is bench/cast/web/ (the PXC1 decoder); anything else is a file in this
// directory (/ is game.html).
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { createSecureServer } from 'node:http2';
import { stripTypeScriptTypes } from 'node:module';
import { join, extname, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { brotliCompressSync, gzipSync, constants } from 'node:zlib';

const [work, port, certs] = process.argv.slice(2);
const web = fileURLToPath(new URL('./', import.meta.url));
const pxTs = fileURLToPath(new URL('../../../js/px.ts', import.meta.url));
const pxcWeb = fileURLToPath(new URL('../../cast/web/', import.meta.url));
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.px': 'text/plain; charset=utf-8', '.png': 'image/png', '.webp': 'image/webp', '.pxc': 'application/octet-stream' };
// .pxc is binary but compresses like text; served brotli as a CDN serves precompressed assets
const TEXT = ['.html', '.js', '.json', '.px', '.pxc'];
const cache = new Map();

function raw(path) {
  if (path === pxTs) return Buffer.from(stripTypeScriptTypes(readFileSync(pxTs, 'utf8'), { mode: 'strip' }));
  return readFileSync(path);
}

function body(path, enc) {
  const key = `${enc}:${path}`;
  if (!cache.has(key)) {
    const data = raw(path);
    cache.set(key, enc === 'br' ? brotliCompressSync(data, { params: { [constants.BROTLI_PARAM_QUALITY]: 11, [constants.BROTLI_PARAM_SIZE_HINT]: data.length } })
      : enc === 'gzip' ? gzipSync(data, { level: 9 }) : data);
  }
  return cache.get(key);
}

// compress every text file before the first request, as a CDN serves them precompressed
for (const rel of readdirSync(work, { recursive: true })) {
  const p = join(work, rel);
  if (TEXT.includes(extname(p)) && statSync(p).isFile()) for (const enc of ['br', 'gzip']) body(p, enc);
}
for (const p of [pxTs, ...readdirSync(web).map((r) => join(web, r)), ...readdirSync(pxcWeb).map((r) => join(pxcWeb, r))]) if (TEXT.includes(extname(p)) || p === pxTs) for (const enc of ['br', 'gzip']) body(p, enc);

const server = createSecureServer({ key: readFileSync(join(certs, 'key.pem')), cert: readFileSync(join(certs, 'cert.pem')), allowHTTP1: true }, (req, res) => {
  const url = decodeURIComponent(new URL(req.url, 'https://x').pathname);
  const path = url === '/px.js' ? pxTs
    : url.startsWith('/sc/') ? join(work, normalize(url.slice(4)))
    : url.startsWith('/pxc/') ? join(pxcWeb, normalize(url.slice(5)))
    : join(web, normalize(url.replace(/^\/+/, '') || 'game.html'));
  if (![work, web, pxcWeb].some((d) => path.startsWith(d)) && path !== pxTs) { res.writeHead(403); res.end(); return; }
  if (!existsSync(path) || !statSync(path).isFile()) { res.writeHead(404); res.end(); return; }
  const type = path === pxTs ? TYPES['.js'] : TYPES[extname(path)] ?? 'application/octet-stream';
  const accept = String(req.headers['accept-encoding'] ?? '');
  const gzipOnly = /\/out-[^/]+\.gzip\//.test(url);
  const enc = type.startsWith('image/') ? '' : gzipOnly ? (accept.includes('gzip') ? 'gzip' : '')
    : accept.includes('br') ? 'br' : accept.includes('gzip') ? 'gzip' : '';
  const headers = { 'content-type': type, 'cache-control': 'no-store' };
  if (enc) headers['content-encoding'] = enc;
  res.writeHead(200, headers);
  res.end(body(path, enc));
});
server.on('error', (e) => { console.error(String(e)); process.exit(1); });
server.listen(Number(port), () => console.log(`listening https://localhost:${server.address().port}`));
