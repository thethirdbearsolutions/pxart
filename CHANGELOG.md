# Changelog

What changed in pxart, newest first. pxart is still `0.1.0`: until a first tagged
release, entries are grouped by the day they landed on `main`. The file format is
`pxart 1` throughout, and every `.px` file written for an earlier day still reads the same.

## 2026-11-22

### Added

- **`review-pack`: a blind reviewer hand-off, with copies to measure the reviewer (PX-5).** Two
  lessons about judging art were hand-run procedure: a folder name can tell a model reviewer the
  answer, and one reviewer can change its verdict on frames that are identical. `review-pack
  renders/ -o pack` puts each PNG (a directory: every `.png` under it) in `pack/<id>/image.png`
  under a random 12-digit id, its pixels re-saved with no metadata, and writes the map of ids to
  renders beside the folder as `pack.manifest.json` (or `--manifest M.json`; never inside it). The
  pack goes in a new or empty directory, written in id order with one time on every file, so a
  listing by time doesn't give the sources' order away. `--copies 2` puts each render in twice under
  different ids, and the copies differ in bytes, size and image data (another compression, a chunk of
  random padding), so a reviewer can't pair them by a hash; their pixels are the same, so one that
  decodes them can. A label drawn into a render isn't hidden: pack `render --plain` PNGs.
  `review-pack --score pack verdicts.json` reads `{"<id>": verdict}` (keys may be `<id>/image.png`,
  or a list of `{"id", "verdict"}`; an object verdict compares by its `"verdict"` field, so a free-text
  reason beside it doesn't count; text compares without case or surrounding spaces, numbers as numbers;
  UTF-16 with a BOM reads too), prints each
  render's verdicts, the copies that DISAGREE, `agreement: 5 of 6 render(s) judged in 2+ copies
  (83%)`, each source folder's tally when there are several (an A/B review), and notes for items with
  no verdict and keys that name no item; verdicts that match no item at all are an error.
  `--seed` makes the ids repeatable.

### Fixed

- **The cast decoder gunzips by the bytes, not the URL (PX-29).** `bench/cast/web/pxc.js`'s
  `fetchCast` gunzipped only a URL ending `.gz`, so `cast.pxc.gz?r=2` (a cache-busting query)
  reached the decoder still gzipped, and a `.gz` a server had already decoded (sent with
  `Content-Encoding: gzip`) was gunzipped twice. It now gunzips what still starts with the gzip
  magic `1f 8b`, whatever the URL. `bench/cast/web/pxc.test.mjs` (run by `tests/test_pxc_js.py`)
  covers both.

## 2026-11-21

### Added

- **`check --outline K` finds the gaps in an outline (PX-11).** A sprite with holes in its outline
  passed `check`, and only looking caught them. With `--outline k` (`--outline kL` for an outline
  in several keys, a selective one's lit key too), each frame's shape is walked and every edge
  pixel (a drawn pixel with an empty side) not drawn in K is a note, with its coordinates:
  `hero.px:idle/0: outline 'k' has 3 gaps at (4,2) (11,7) (11,8)`. It agrees with `outline`: a
  frame `outline --key K` just drew, outside or inside, with `--corners` or `--lit`, has no gaps.
  Where the shape meets the frame's border isn't a gap (`outline` can't draw there without
  `--pad`; `outline` itself notes that the outline is open there). A file that never draws in K
  says nothing, but one that draws K anywhere is checked, so on a folder name a key your sprites
  keep for outlines. A K that no checked file has at all (a typo) is a note of its own; `.` or an
  empty K is an error. `--min-alpha A` reads the shape as `outline --min-alpha A` did. `-v` lists
  every gap's coordinates, not the first eight.

- **`check` notes an animation's repeated neighbour frames (PX-10).** Two frames in a row that draw the
  same in the base and every variant read as a stutter, and only looking caught it (a slime idle in the
  cave run). `check` now says `idle/1 and idle/2 are identical (0 px differ, in every variant too)`,
  one note for a run of copies, including the wrap from the last frames back to the first when the
  group loops (forward or reverse, repeat other than 1), and gives the hold that does it on purpose as
  two commands: remove the copies, and give the frame kept their time on screen as its `ms=` (at a
  pingpong's turn, the end frame's plus twice the others'). A group with no `@anim` line may be icons,
  so the note offers `anim-set FILE:GROUP --still` first. A group whose frames are all alike is called
  one picture rather than a hold. The same pixels on another pivot are a move, not a copy.
  `@still` groups and top-level frames are exempt, and `check FILE:SEL` speaks only of the frames it
  selects. `--strict` fails it as `E_SAME_FRAMES`, at the line of the first copy to remove.

### Fixed

- **The test suite passes again, on any machine (PX-27).** The example check compared PNGs and
  GIFs byte for byte, and the bytes depend on the machine for the same picture (zlib deflates
  PNGs differently, Pillow versions order a GIF's palette differently): which images failed
  depended on where you ran it, though none drew differently. Images now compare by mode, size,
  metadata and each frame's pixels, timing and disposal; text stays byte for byte. The glade's
  Tiled parity test counted every `.map` under `examples/` and broke when the map-variants
  tutorial added six; it reads the scene tutorial's own, and each map-variants room now has a
  Tiled parity test of its own. The slot round trip failed everywhere since the px.ts fixtures
  added a slot list on purpose; those four files are now named as having slots. The
  read-only-output test failed under root, which can write to a read-only directory.

## 2026-11-19

### Added

- **px.ts keeps slots and blends palettes, for games that recolor at runtime.** `doc.slots` holds
  each slot's colors (a local line replaces an imported slot whole; a plain one hides its
  alternatives, as pxart.py resolves them), and `slotsOf(doc, variant)` gives them as a variant draws
  them. `paletteFor(doc, variant, picks)` picks slot colors by index, as `render --slots k=i` does, and
  CI now checks every slot color picked alone byte for byte against pxart.py too. `mixPalettes(a, b,
  t)` blends two palettes key by key, for a dusk that deepens by the minute.

## 2026-11-17

### Added

- **`js/px.ts`, a reader for `.px` in the browser.** It draws frames, variants and maps from the
  `.px` text, so a web game can ship its sprites' sources instead of PNGs. CI checks that it draws
  every frame and variant of `examples/` byte for byte as pxart.py does. It was
  the pxart website's playground reader; it doesn't validate, so pxart.py stays the reference.
- **`bench/load/`, the load bench, and every result it has recorded.** It times how long a web
  game takes to load and draw a cast shipped as PNG or WebP frames, as sheets, or as `.px` drawn by
  px.ts, in Chromium on desktop broadband, 4G and an emulated phone. One command reruns it on a
  synthetic cast that it draws itself: `uv run bench/load/run.py --out DIR`.
- **`bench/cast/`, a whole-cast format spike.** PXC1 ships a cast as one file of palette
  indices, with palettes and damage and expression overlays as data, and decodes it in a Web
  Worker. Its README has the results.

## 2026-11-14

### Changed

- **Rendering a file with palette variants is no longer slower the more frames it has.** Every frame
  rendered in a variant re-read every row of every frame to look for colors the variant leaves at base.
  A 640-frame cast with two variants took 8.2 s to build and now takes 2.0 s, with byte-identical
  output and the same warnings.

## 2026-11-12

### Changed

- **`put --rows` repairs a frame whose rows are the wrong width.** A file with one ragged row used to
  refuse every command, `put` included, so the only fix was retyping the file. `put` now loads it with
  the rows as typed, writes only if the frame it edits ends up even (replacing every row may change the
  width), and notes any other frame still ragged. `--at` still refuses a ragged frame. The first
  E_ROW_WIDTH in a file's frame names the repair.
- **`put --text ROW`**, once per row, gives the rows on the command line instead of stdin.

- **The argv shapes people guess first now work.** `dup FILE:a FILE:b` reads `b` as the new id when
  both name the same file (another file's selector says to use `compose -o`); `shift FILE DX DY` is
  `--dx DX --dy DY` (and so is `DX,DY`); `set FILE x,y ... KEY`, the key last, is read as
  `set FILE KEY x,y ...` with a note (so are separate numbers, `set FILE 3 4 k`), and a point where
  the key goes says the order instead of "not in palette". `dup SRC -o FILE:NEWID` names the new
  frame through `-o`.
- **A row one pixel off says where.** When most of a frame's rows agree on a width, `E_ROW_WIDTH`
  for a row one too wide or short names the pixel to delete or add that lines it up with the rows
  around it, or says it's a `.` (an edge or a gap: the rows can't tell which).

## 2026-11-10

### Added

- **Edits for drawing in layered passes.** `put FILE[:frame] --at X,Y` puts a few typed rows
  (a patch) onto a frame with its top-left at X,Y: `.` keeps the pixel under it, and a patch
  that runs past the frame is an error, so a miscounted column shows. `put --rows Y0-Y1`
  replaces a range of rows with full-width typed rows. Both print how many pixels changed.
- **An erase key.** `compose --erase KEY` makes a layer's KEY pixels clear what the layers
  below drew to `.`, so a cleanup layer can remove pixels, not only add them; KEY is never
  copied into OUT. `put --at … --erase KEY` does the same for a patch.

### Fixed

- `compose --erase KEY` no longer copies KEY's palette line into a new OUT when a layer
  defines it.
- `render -h` said `--plain` ignores `--bg`; `render --plain --bg COLOR` fills the
  transparent pixels, and the help now says so.

## 2026-09-29

### Added

- **Palette slots.** A key line can list alternatives, `f #e0ac69 | #f5cfa0 | #c68642`,
  for a game that recolors sprites at runtime. The first color is the key's base color.
  `render --slots` and `sheet --slots` draw combinations of them, and `export --indexed
  keys.json` writes the frames as key grids with the palette and its slots. A `@variant`
  can give a slot one color or a list. `pxart help slots` has the rules and the JSON shape.
- `from-png --colors N` reduces a PNG with many colors to fit the free palette keys, and
  reuses OUT's palette when OUT already exists.
- `from-png --hard-edges`, `outline --min-alpha A` and `outline --pad`.

### Changed

- Alpha is visible: `check` and `from-png` count the see-through pixels, and say when a
  key is faint or a shape touches the frame's edge.
- `from-png` with no `-o` prints its notes on stderr, so `from-png a.png > a.px` gives a
  clean `.px`.
- Erase errors name a command that runs as printed.

## 2026-09-28

### Added

- **Tiled worlds.** `export --tiled` compiles a `world.src.json` and its `.map` rooms into
  a `.world` and `.tmj` files, with stable object ids. `pxart help worlds` has the details.
- `pxart world` draws a compiled world, its rooms where they sit, to one PNG.
- `check` reads `.world` and `.tmj` files, using the same rules as the export.

## 2026-09-27

The first public version: the format, about forty commands, and the
[nine tutorials](examples/README.md), whose outputs are rebuilt and compared byte for
byte by the tests.

### Added

- `compose --dry-run` prints what compose would say and the diff it would write.
- `paste --align shift|pivot|bottom|bbox` and `FILE:a,b,c` frame lists, so one paste can
  follow a bobbing animation.
- `ellipse --ring N` and `ellipse --box x,y,w,h`.
- `onion --variant V`, `stats --variant V`, and `render`/`sheet` cells labeled with their variant.
- `dup FILE:GROUP NEWGROUP`; `flip FILE:G -o FILE:NEWG`; `--replace` for `flip`, `rotate`,
  `transpose` and `dup`.
- `--dry-run` on every in-place edit, `new` and `palette` included.

### Changed

- `render` and `sheet` draw a grey checkerboard behind each frame by default.
- Every edit says what it did: `painted N px`, `erased N px`, `changed 41 px: 29->C, 12->X`,
  and the keys `palette --add` added.
- A missing selector says "no frame or group" and lists the groups. An unknown variant
  gets "did you mean".
- `anim` over several groups animates each on its own, and its percentages never go over 100.
