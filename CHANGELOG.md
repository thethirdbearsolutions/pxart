# Changelog

What changed in pxart, newest first. pxart is still `0.1.0`: until a first tagged
release, entries are grouped by the day they landed on `main`. The file format is
`pxart 1` throughout, and every `.px` file written for an earlier day still reads the same.

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
