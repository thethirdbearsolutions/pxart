<!-- How to write an entry:
- Open with one plain sentence, from the user's side: what they can now do, or what no longer goes wrong. Name the command. Leave out the ticket history and why the old behaviour happened.
- At most one short example: a command and up to two lines of its output, in a code block, and only when it shows the change better than words.
- Under 60 words per entry, example included. The PX id goes last, in parentheses.
- Quote no full error or note text. Name the message instead ("`check` now names the line").
- Fold together fixes that only reword a warning or note: one entry per day, e.g. "Clearer messages from `crop`'s variant warnings and `render --png`'s skip note (PX-58, PX-59)."
- Keep the Added / Changed / Fixed headings under each day, newest first.
-->

# Changelog

What changed in pxart (still `0.1.0`), newest first, grouped by the day it landed on `main` until a first tagged
release. The file format is `pxart 1` throughout, and every `.px` file written for an earlier day still reads the same.

## 2026-11-28

### Fixed

- **When a sprite's own colors stay day-bright in a `night` from an imported palette, the `palette`
  command `check` suggests to fix them now runs.** It named a missing file when the sprite imports
  several palettes, and failed when the night was too small to copy; now it names the right file, or prints
  `palette --add` for your colors (PX-74).

- **`crop hero.px:walk/0 x,y,w,h -o other.px:walk/0` keeps the frame's pivot instead of dropping it,** moved
  with the crop, so `anim` and `export` still find the feet where they were. When the frame has no pivot and the
  file it lands in gives its animation one, the frame uses that one, and a note says so (PX-72).

## 2026-11-27

### Added

- **`onion A B -o out.png` now marks in pink the pixels that changed from frame A to frame B,** in a second
  panel beside the overlay, so a foot that lifted is easy to spot. With `--feet N` (only the bottom N rows), it
  marks just the pixels that band's printed count covers (PX-70).

- **`crop hero.px:walk x,y,w,h -o hero.px:walk` crops every frame of the `walk` animation to the same box,**
  keeping each frame's anchor point (pivot) on the same spot of the art. A negative y adds empty rows on top:
  `0,-6,16,30` makes 16x24 frames 16x30. `check --headroom`, which warns when a sprite has no room above it to
  jump, now prints this command (PX-69).

### Fixed

- **`check` now warns when some of a sprite's colors stay daytime-bright at night.** This happened when the
  sprite's own night colors (`@variant night`) covered only a few keys and the shared palette file it imports had
  none for the rest: those rendered in day colors, and `check` said nothing. The command it prints fixes the
  sprite's file and leaves the shared palette alone (PX-71).

## 2026-11-26

### Added

- **`export --tiled` writes a group's `repeat` and `direction` as tile properties,** `pxart_repeat` and
  `pxart_direction`, next to `pxart_anim`, so a game can stop an animation that Tiled would loop forever (PX-66).

### Fixed

- **Running the commands `render --png DIR` suggests for the multi-frame files it skips no longer overwrites
  anything.** For each such file it suggests an `export` and a `render`; when several files would write into DIR,
  each now gets a subfolder, such as `out/knight`. Both commands keep a `FILE%variant`'s colors (PX-67).

- **`crop`, `compose` and `paste` into an existing file add only the keys of the pixels they copy,** so `check`
  finds no unused keys. A key outside the copied area or hidden by `--under` isn't added, warned about or renamed,
  and can't cause a conflict. `crop` and `compose` also copy each added key's comment; `paste` doesn't (PX-64,
  PX-65).

- **`outline --key K` checks every variant before warning that the art already has a dark line,** which an outline
  would double into a 2px rim, and names the variants where that happens, for example a line that is only dark at
  night. When every variant agrees, it is one note as before (PX-63).

- **`onion A B --feet N` gives the same changed-pixel count as `onion B A --feet N`,** and so does `--rows Y0-Y1`. Pixels
  moving into or out of those rows now count, so some counts go up. Swapping A and B flips the best shift's sign,
  except in a tie, where both orders may name the same shift (PX-61).

## 2026-11-25

### Fixed

- **`check` fails a file with a `@variant base`, and names the line.** A variant called `base` can never draw,
  since `base` always means the base colors. A sprite that gets one through `@palette` fails too, naming the
  palette file's line. Such files still render as before (PX-57).

- **`export --tiled` plays `pingpong` and `reverse` groups in Tiled as `anim` plays them,** instead of always
  forward. A group with a `repeat` gets a note, because a Tiled animation always loops (PX-62).

- **Clearer messages from `crop`, `compose` and `render --png`.** Cropping or composing into a file with a
  `@variant` warns only about keys the copied pixels use, and the `--rekey` it offers lists only those. When
  `render --png` skips a multi-frame file, the `export` command its note suggests runs as printed (PX-58, PX-59).

## 2026-11-24

### Fixed

- **`anim` counts the same changed pixels from frame A to B as from B to A.** `anim` lines each pair up
  by its best shift; pixels that shift pushes off the canvas, such as feet, now count as changed, so some counts
  grow. `paste --align shift` uses the same shift. `anim` is also faster on big frames (PX-55).

- **`repeat=N` on a `pingpong` group means N one-way passes, as in Aseprite.** `repeat=1` plays 0 1 2 3 and stops,
  where it used to play 0 1 2 3 2 1. `anim` previews it pass by pass, and `check`'s hold advice follows (PX-56).

- **`anim -o x.gif` on a whole group plays as often as its `repeat` says,** instead of looping forever, and
  `--dry-run` says so too. Frame labels on `render` and `sheet` no longer run the size into the color count (PX-50).

- **Negative coordinates after a flag work as typed,** such as `mask --keep-circle -10,-8,34`. Negative widths,
  heights, radii and sizes are now errors, and `shift --region` clips a negative x or y to the frame instead of
  counting from the far edge (PX-52).

- **`-o FILE.px:FRAME` no longer makes a file or folder with that literal name.** Whole-file edits such as
  `outline` and `shade` refuse it; when it names a frame of the same file, they give the `dup` to copy it first.
  `from-png x.png -o into.px:walk/9` adds the PNG to into.px as frame `walk/9` (PX-23).

- **`check` warns about an empty `.px` file.** `dup` and `frames --rename` work on a file that
  is a single grid with no `@frame` name. `outline --key` notes when the art already has a dark line, which an
  outline would double (PX-24).

- **`scene --variant` notes when the default backdrop shows through,** since `--bg` stays a day color: give `--bg`
  a night color. With `--anchor`, it names items wholly outside the window instead of counting cropped pixels
  (PX-48).

- **The experimental cast encoder, `bench/cast/pxc.py`, explains its errors.** It packs a folder of character
  `.px` files into one file and needs them to share one palette; it now names the key and the files that differ,
  instead of a traceback. A file no longer has to list keys it doesn't draw (PX-46).

- **Clearer messages from `from-png` and `palette --remove` when the arguments are in the wrong place,** each now
  printing the command to type. When `compose` or `crop` into a file with a night palette suggest `--rekey`
  (giving the copied pixels new letters), they now say that this renames keys a game may read (PX-21, PX-49).

## 2026-11-23

### Added

- **`check --headroom N` notes frames with fewer than N empty rows above the sprite,** so a jump has room to
  rise, and gives the `crop` that grows the canvas. Frames already in the air are left out. `anim` now reports how
  many rows a group rises, and the headroom left at its highest (PX-13).

- **`render --silhouette` and `sheet --silhouette` draw each sprite's shape in one flat color,** for comparing
  silhouettes or for a blind review. Faint pixels stay faint, and it works with `--variant`, `--scale` and
  `--plain`. The color is `#2b1d32` unless you give one, as in `--silhouette '#ffffff'` (PX-31).

- **A variant made with `palette --variant night --derive-from base` records the command that made it,** as a
  `# derived by` comment above `@variant`, so you can change one setting, such as `--darken`, and run it again.
  The `palette` listing names the keys it kept lit (PX-53).

### Fixed

- **`export` that fails writes nothing,** instead of leaving a sheet and frame PNGs that look like a success. Two
  outputs pointed at one file are now an error (PX-44).

- **`check --outline K` notes a render where K draws nothing,** such as a key that is transparent by day and only
  shows at night, so that render has no outline (PX-43).

- **`anim` plays a group in its `direction`:** `pingpong`, `reverse` and `pingpong_reverse` now preview as they
  play, in the GIF and the numbers, with the frames of the way back marked (PX-42).

- **Several `--add` options in one `palette` call all add their keys.** Only the last one used to count. A key
  given two colors is an error (PX-54, PX-25).

## 2026-11-22

### Added

- **`palette --lamplit KEYS@S` warms chosen keys in a night variant made with `--derive-from`,** mixing each
  toward its day color under lamplight by strength S (0 to 1). Give the pixels near a lamp keys of their own,
  then list them; repeat the option for a brighter near ring and a dimmer far one (PX-30).

- **`review-pack` copies a folder of renders under random ids, for a blind review,** so the reviewer, a person or a
  model, can't tell from the file names which is which. `--copies 2` adds each render twice, and `review-pack
  --score` reads a JSON of verdicts by id and lists copies judged differently (PX-5).

### Fixed

- **`pxart help topics` lists the help topics,** and topic names take any case.

- **`scene --anchor center` (or an edge, a corner, or `X,Y`) picks which part of the scene a smaller `--size`
  keeps.** Without it, the top-left is kept, as before (PX-36).

- **`export --indexed` writes no `ms` (frame duration) for a frame marked `@still`,** such as a tile or an icon,
  so a game can tell it from an animation frame (PX-33).

- **The experimental cast decoder, `bench/cast/web/pxc.js`, loads a gzipped cast whatever its URL,** including one
  with a query string, or one the server already unzipped (PX-29).

- **Clearer output from `anim` on a single frame,** which says there is nothing to compare. When `paste` or
  `frames --copy-to` into a file with a night palette suggest `--rekey` (new letters for the copied pixels), they
  say that this renames keys a game may read (PX-41, PX-35).

## 2026-11-21

### Added

- **`check --outline K` lists the gaps in a sprite's outline,** with their coordinates, so holes no longer pass
  unseen. A frame that `outline --key K` just drew has none (PX-11).

  ```
  $ pxart check hero.px --outline k
  ok   hero.px:idle/0: 6x4 2c
       note: hero.px:idle/0: outline 'k' has 2 gaps at (3,1) (4,2)
  ```

- **`check` notes two frames in a row of an animation that are identical,** which reads as a stutter, and gives
  the commands that make it a deliberate hold instead. `--strict` fails it (PX-10).

### Fixed

- **`pytest` passes on any machine.** The example checks compare images by their pixels instead of their bytes
  (PX-27).

## 2026-11-19

### Added

- **`js/px.ts` reads palette slots and blends palettes,** for games that recolor at runtime: `paletteFor` picks
  slot colors as `render --slots` does, and `mixPalettes` blends two palettes, for a dusk that deepens by the
  minute.

## 2026-11-17

### Added

- **`js/px.ts` draws `.px` frames, variants and maps in the browser,** so a web game can ship sprite sources
  instead of PNGs. CI checks it draws every example exactly as pxart.py does. It doesn't validate, so pxart.py
  stays the reference.

- **`bench/load/` times how fast a web game loads a cast** shipped as PNG or WebP frames, as sheets, or as `.px`,
  on desktop, 4G and an emulated phone, with every result recorded so far. `uv run bench/load/run.py --out DIR`
  reruns it.

- **`bench/cast/` is an experiment, not a supported format:** it packs a game's whole cast of characters into one
  file and draws it in a Web Worker. Its README has the measurements.

## 2026-11-14

### Changed

- **`render`, `sheet` and `export` of a file with palette variants no longer slow down as it gains frames.** A 640-frame cast with two
  variants builds in 2.0 s instead of 8.2 s, with the same output.

## 2026-11-12

### Changed

- **`put --rows` can repair a frame whose rows are different widths,** so a file with one ragged row can be fixed
  without retyping it. `put --text ROW`, once per row, gives the rows on the command line instead of stdin.

- **The argument orders people guess first now work,** such as `dup FILE:a FILE:b`, `shift FILE DX DY` and
  `set FILE x,y KEY` with the key last.

- **`check` and every command that reads a file name the pixel to delete or add** when a row is one pixel too wide
  or short.

## 2026-11-10

### Added

- **`put FILE --at X,Y` stamps a few typed rows onto a frame,** and `put --rows Y0-Y1` replaces whole rows. Both
  say how many pixels changed.

- **`compose --erase KEY` and `put --erase KEY` let a layer clear pixels,** not only add them.

### Fixed

- `compose --erase KEY` no longer adds KEY to a new output's palette.
- `render -h` now says `--plain --bg COLOR` fills the transparent pixels.

## 2026-09-29

### Added

- **A palette key can list alternative colors (slots), `f #e0ac69 | #f5cfa0 | #c68642`, for games that
  recolor at runtime.** `render --slots` and `sheet --slots` draw them, and `export --indexed` writes them.
  `pxart help slots` has the rules.
- `from-png --colors N` reduces a PNG with many colors to fit the free palette keys, and reuses OUT's palette
  when OUT exists.
- `from-png --hard-edges` makes every see-through pixel opaque, or clear if faint; `outline --min-alpha A` ignores
  pixels fainter than A; `outline --pad` grows the frame so an outline fits at its border.

### Changed

- `check` and `from-png` count see-through pixels, and say when a key is faint or a shape touches the frame's edge.
- `from-png` with no `-o` prints its notes on stderr, so `from-png a.png > a.px` gives a clean file.
- When `recolor` refuses a move to `.` (`'k>.'`), the error gives the `recolor` command that does erase those
  pixels, ready to paste.

## 2026-09-28

### Added

- **`export --tiled` compiles a `world.src.json` and its `.map` rooms into Tiled `.world` and `.tmj` files,** with
  stable object ids. `pxart help worlds` has the details.
- `pxart world` draws a compiled world to one PNG.
- `check` reads `.world` and `.tmj` files, by the same rules as the export.

## 2026-09-27

The first public version: the format, about forty commands, and the
[nine tutorials](examples/README.md), whose outputs the tests rebuild and compare.

### Added

- `compose --dry-run` prints what compose would say and the diff it would write.
- `paste --align shift|pivot|bottom|bbox` and `FILE:a,b,c` frame lists, so one paste can follow a bobbing
  animation.
- `ellipse --ring N` draws a ring N pixels thick; `ellipse --box x,y,w,h` fits the ellipse in a box.
- `onion --variant V`, `stats --variant V`, and `render` and `sheet` cells labeled with their variant.
- `dup FILE:GROUP NEWGROUP` copies a whole animation group, and `flip FILE:G -o FILE:NEWG` writes a flipped copy
  as a new group. `--replace` lets `flip`, `rotate`, `transpose` and `dup` overwrite a group that exists.
- `--dry-run` on every in-place edit, `new` and `palette` included.

### Changed

- `render` and `sheet` draw a grey checkerboard behind each frame by default.
- Every edit says what it did, such as `painted N px`, and `palette --add` names the keys it added.
- A missing selector lists the groups, and an unknown variant gets "did you mean".
- `anim` over several groups animates each on its own, and its percentages never go over 100.
