// px.ts's runtime helpers, the ones pxart.py has no counterpart to draw against: slotsOf (what a game
// can pick from) and mixPalettes (a palette between two). Run by tests/test_px_ts.py: node --test.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { mixPalettes, paletteFor, parsePx, resolvePx, slotColor, slotsOf, type Rgba } from './px.ts';

const read = (p: string): string | null => (existsSync(p) ? readFileSync(p, 'utf8') : null);
const doc = resolvePx('tests/fixtures/px_ts/slots.px', read);

test('a file keeps its own slots and its imports', () => {
  assert.deepEqual([...doc.slots.keys()].sort(), ['f', 'h', 's']);
  assert.deepEqual(doc.slots.get('f'), [[0xe0, 0xac, 0x69, 255], [0xf5, 0xcf, 0xa0, 255], [0xc6, 0x86, 0x42, 255]]);
  assert.equal(doc.slots.get('s')!.length, 3); // from base.px
});

test('slotsOf a variant: its list, its one color for every slot, or the slot as it is', () => {
  const night = slotsOf(doc, 'night');
  assert.deepEqual(night.get('f')![2], [0x63, 0x43, 0x21, 255]);
  assert.deepEqual(night.get('h'), [[0x20, 0x10, 0x08, 255], [0x20, 0x10, 0x08, 255]]);
  assert.deepEqual(night.get('s'), doc.slots.get('s'));
});

test('picks choose slot colors and ignore what is no slot', () => {
  const pal = paletteFor(doc, undefined, { f: 1, k: 1, h: 9 });
  assert.deepEqual(pal.get('f'), [0xf5, 0xcf, 0xa0, 255]);
  assert.deepEqual(pal.get('k'), [0x1a, 0x1a, 0x1a, 255]);
  assert.deepEqual(pal.get('h'), doc.palette.get('h'));
  assert.equal(slotColor(doc, 'f', -1), null);
});

test('a plain local line hides an imported slot; a local slot replaces it whole', () => {
  const hide = resolvePx('tests/fixtures/px_ts/slots-hide.px', read);
  assert.equal(hide.slots.has('s'), false);
  assert.deepEqual(hide.slots.get('o')![1], [0x5a, 0x3f, 0x6e, 255]);
});

test('mixPalettes blends key by key and keeps a key only one side has', () => {
  const a = new Map<string, Rgba>([['x', [0, 0, 0, 255]], ['y', [10, 20, 30, 255]]]);
  const b = new Map<string, Rgba>([['x', [255, 101, 0, 0]], ['z', [1, 2, 3, 255]]]);
  const m = mixPalettes(a, b, 0.5);
  assert.deepEqual(m.get('x'), [128, 51, 0, 128]);
  assert.deepEqual(m.get('y'), [10, 20, 30, 255]);
  assert.deepEqual(m.get('z'), [1, 2, 3, 255]);
  assert.deepEqual(mixPalettes(a, b, 0).get('x'), [0, 0, 0, 255]);
  assert.deepEqual(mixPalettes(a, b, 7).get('x'), [255, 101, 0, 0]); // t is clamped
});

test('a file with no slot lines has none', () => {
  assert.equal(parsePx('k #000000\n@frame a\nk\n').slots.size, 0);
});
