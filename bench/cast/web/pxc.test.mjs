// fetchCast gunzips by content, not by URL ending (PX-29). Run: node --test bench/cast/web/pxc.test.mjs
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { gzipSync } from 'node:zlib';
import { fetchCast, gunzipped } from './pxc.js';

const cast = new TextEncoder().encode('PXC1 a cast, as bytes');
const gz = gzipSync(cast);
const bytes = (buf) => Buffer.from(new Uint8Array(buf));

function serve(body) {  // fetch, answering every URL with these bytes, as a server would send them
  const seen = [];
  globalThis.fetch = async (url) => { seen.push(String(url)); return new Response(body); };
  return seen;
}

test('a .gz URL with a cache-busting query still gunzips', async () => {
  const seen = serve(gz);
  assert.deepEqual(bytes(await fetchCast('cast.pxc.gz?r=2')), Buffer.from(cast));
  assert.deepEqual(seen, ['cast.pxc.gz?r=2']);
});

test('a .gz the server already decoded (Content-Encoding: gzip) is not gunzipped again', async () => {
  serve(cast);  // what fetch hands over once the browser has undone Content-Encoding
  assert.deepEqual(bytes(await fetchCast('cast.pxc.gz')), Buffer.from(cast));
});

test('gzip bytes behind a plain .pxc URL gunzip too, and plain bytes pass through', async () => {
  serve(gz);
  assert.deepEqual(bytes(await fetchCast('cast.pxc')), Buffer.from(cast));
  serve(cast);
  assert.deepEqual(bytes(await fetchCast('cast.pxc')), Buffer.from(cast));
});

test('short and empty bodies pass through', async () => {
  assert.equal((await gunzipped(new Uint8Array([0x1f]).buffer)).byteLength, 1);
  assert.equal((await gunzipped(new ArrayBuffer(0))).byteLength, 0);
});

test('an HTTP error still says so', async () => {
  globalThis.fetch = async () => new Response('nope', { status: 404 });
  await assert.rejects(fetchCast('cast.pxc.gz'), /cast\.pxc\.gz: HTTP 404/);
});
