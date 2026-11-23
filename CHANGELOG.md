# Changelog

What changed in pxart, newest first. pxart is still `0.1.0`: until a first tagged
release, entries are grouped by the day they landed on `main`. The file format is
`pxart 1` throughout, and every `.px` file written for an earlier day still reads the same.

## 2026-11-23

### Fixed

- **`anim` plays a group in its `direction` (PX-42).** A `@anim walk direction=pingpong` group of 4 frames gave a GIF
  of 4 frames playing 0 1 2 3 0, and a readout that compared walk/0 with walk/3 as a wrap-around, which a pingpong
  never plays; so `anim` couldn't preview the turnaround that `check`'s E_SAME_FRAMES reasons about. Now the GIF and
  the numbers follow the direction, one cycle: `pingpong` 0 1 2 3 2 1, `reverse` 3 2 1 0, `pingpong_reverse` 3 2 1 0
  1 2, each compared with the frame played before it (the cycle's wrap is the 1 -> 0 that really plays), with a
  note that gives the cycle's frames and time and how often it plays (`repeat`): `note: walk plays pingpong: 0 1 2 3
  2 1 (6 frames, 780 ms), then again; the GIF and the numbers follow it, the way back marked 'back'`. The frames of the
  way back are labeled `walk/2 back` on the strip and in the numbers. `forward`, a 2-frame pingpong (it plays 0 1), a
  `@still` group, and a selection that isn't one whole group in file order (`walk/0,walk/3`, several groups or files)
  play as before, as selected. `repeat=N` counts whole cycles (a pingpong's 0 1 2 3 2 1 is one), as `check`'s
  E_SAME_FRAMES does. The GIF still loops forever whatever `repeat` says
  (PX-50).

### Added

- **`render` and `sheet --silhouette [COLOR]`: the shape alone (PX-31).** The first look at any sprite, and what a
  blind review of several candidates compares, is its silhouette; pxart had none, so each artist and reviewer made
  one in Pillow, each a little differently. `sheet a.px b.px --silhouette -o shapes.png` draws every pixel that
  draws in one flat color (`#2b1d32`, or `--silhouette '#ffffff'`), at the pixel's own alpha times the color's, so a
  solid sprite is a solid shape and a faint glow stays faint; a transparent pixel stays transparent, on the usual
  checkerboard or `--bg`. It works with `--variant` (a halo lit only at night shows in the night silhouette),
  `--scale`, `--plain` and the rest; each label says `idle/0 silhouette`. A bare `--silhouette` before the files
  (`sheet --silhouette a.px b.px`, or a directory) takes no file as its color; a color that draws nothing
  (`transparent`) is an error; `render --png` still writes the colors, and says so. A PNG input whose four corners
  are one opaque color (a sprite rendered on a flat backdrop) has that color taken as the backdrop, with a note. The
  default is always `#2b1d32`: the ticket's "the outline key's color" would need a file to say which key is its
  outline, and none does.

## 2026-11-22

### Added

- **`palette --lamplit`: lamplight on what stands near a lamp (PX-30).** `--keep-lit` keeps a lamp
  lit through a derived night, but lit nothing around it; a pack warmed the wood by a light by hand.
  `palette pal.px --variant night --derive-from base --darken 0.35 --tint '#10183060' --keep-lit y
  --lamplit f,g@0.42 --lamplit m,n@0.2` derives as before, then mixes each listed key's derived
  color by its strength (default 0.4) toward the key's base color under the lamp, `relit = base x
  lamp / 255` per channel (lamp `#ffc080` by default, or `KEYS@S:#rrggbb`): each channel `c + S x
  (relit - c)`, alpha kept. At strength 1 a key is its day color in lamplight. It lifts a key only
  where `lamp / 255` beats what the darken and tint left of it, so after a light darken (0.1) a dim
  lamp darkens keys, and the summary names any lamplit key that came out darker than its plain
  derive; and as it lights a key toward its own day color, it can't brighten a dark key (a
  lantern's iron) much. The first cut, merged earlier the same day, mixed toward the flat lamp
  color (`#ffaa50`) instead, which squeezed a lit wood ramp nearly flat (12 apart in red where the
  day ramp was 86); the default lamp is now `#ffc080`, since a day color times `#ffaa50` keeps only
  71% of its luma and turns tan wood red. It repeats, so a near and a far ring take their own
  strengths, and the output lists each group as `--keep-lit` is listed: `lamplit: f g (0.42);
  lamplit: m n (0.2)`. A key is in one group, and not also `--keep-lit`; the dark-key hold doesn't
  undo the warming: the summary names a dark lamplit key the derive brightened as held (or, with
  `--lift-darks`, brightened), and says `lamplit d came out brighter` only when the lamp itself lit
  it past its `--derive-from` color. When FILE imports a palette whose own file has a variant by
  that name, a `--lamplit` key from the import is that variant's color lamplit, and a `--keep-lit`
  one its `--derive-from` color, each on a line of FILE's own (both were skipped, and still listed
  as done), unless the import's variant already has that color. That line has a comment right
  above it, `# lamplit (palette --derive-from)` or `# kept lit (palette --derive-from)`, and a
  re-derive without the flag drops a line so marked and says so; it leaves an unmarked line (an
  `--add`'s) alone, as before. An `--add` over a marked line takes the mark off: the color is set by
  hand now.
  `pxart help palette` (and the night recipe) says the setup it needs: keys of their own for what
  the lamp lights, a hair off the plain wood's so they match by day, another `--lamplit` per ring, a
  dithered edge; and to change a strength, derive from base again. An `--add` in the same call that
  sets a lamplit key says so. The file format is unchanged: the variant's lines are plain colors,
  and the mark an ordinary comment line, so `js/px.ts` needs nothing new.

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

- **`pxart help topics` lists the topics.** The main help says `pxart help TOPIC`, but `help
  topics` was "no such topic or command". It now lists each topic with the commands it covers, and
  the unknown-topic error points at it. Every topic takes any case now (`help ALL` and `help
  Palette-Rules` were refused).

- **`scene --anchor`: a smaller `--size` can keep the middle of a scene (PX-36).** `scene --size WxH`
  smaller than the map (or than what the items fill) kept the top-left, and the help didn't say so;
  an agent expecting the centre got a corner. The help now says the top-left is kept (x,y as typed,
  so every existing command draws the same), and `--anchor center` (or `top`, `left`, `bottom-right`,
  and the other edges and corners) keeps that part instead, and `--anchor X,Y` centres the window on
  that point of the scene (a camera on the hero), with a note naming the pixels shown: `note:
  --anchor center: the 96x64 scene shows 40,20 to 135,83 of the 176x104 the map and items fill`. A
  bigger `--size` with `--anchor center` puts the scene in its middle.

- **`anim` on one frame says there's nothing to compare (PX-41).** A file or group of a single frame
  printed `mushroom 100ms vs mushroom: shift +0,+0 then 0px (0%)`, the frame against itself, which
  reads like a measurement. It now prints `note: mushroom: 1 frame (100ms), nothing to compare` (a
  group of one frame by its group's name, one frame picked from a bigger group by its own; `plays once`
  for `repeat=1`), and still writes the GIF and strip that `-o`
  asks for.

- **The cast decoder gunzips by the bytes, not the URL (PX-29).** `bench/cast/web/pxc.js`'s
  `fetchCast` gunzipped only a URL ending `.gz`, so `cast.pxc.gz?r=2` (a cache-busting query)
  reached the decoder still gzipped, and a `.gz` a server had already decoded (sent with
  `Content-Encoding: gzip`) was gunzipped twice. It now gunzips what still starts with the gzip
  magic `1f 8b`, whatever the URL. `bench/cast/web/pxc.test.mjs` (run by `tests/test_pxc_js.py`)
  covers both.

- **`export --indexed` writes no `ms` on a `@still` frame (PX-33).** Every frame said `"ms": 100`,
  tiles under `@still *` too, so a game reading the JSON could take tiles for animation frames.
  A `@still` frame (a tile, an icon) now has no `"ms"`; animated frames keep theirs, and so does a
  top-level frame not marked still.

- **`paste` and `frames --copy-to` say what the `--rekey` their WARNINGs offer would change (PX-35).**
  Pasting quarters of tiles key for key into a file with a night printed one WARNING per key, each
  ending `paste --rekey L gives it a key of its own`; following that would have renamed stand-in keys
  a game's fill code reads by letter. After those WARNINGs a note now says so: `note: paste --rekey
  D,E,F,L would give those pixels new letters in tiles.px; left off, the keys stay (a key-for-key copy)
  and take tiles.px's variant colors`. Keys a shell or `--rekey` can't take as a list (`,` `=` `*`),
  or more than six, give plain `--rekey`; after a partial `--rekey D,F` it says `adding E,L to --rekey`.
  A source that shares DST's palette gets no WARNING and no note.

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
