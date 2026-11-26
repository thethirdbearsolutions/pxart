<!-- How to write an entry:
- Open with one plain sentence, from the user's side: what they can now do, or what no longer goes wrong. Name the command. Leave out the ticket history and why the old behaviour happened.
- At most one short example: a command and up to two lines of its output, in a code block, and only when it shows the change better than words.
- Under 60 words per entry, example included. The PX id goes last, in parentheses.
- Quote no full error or note text. Name the message instead ("`check` now names the line").
- Fold together fixes that only reword a warning or note: one entry per day, e.g. "Clearer messages from `crop`'s night-colour warnings and `render --png`'s skip note (PX-58, PX-59)."
- Keep the Added / Changed / Fixed headings under each day, newest first.
-->

# Changelog

What changed in pxart, newest first, grouped by the day it landed on `main` until a first tagged release.
The file format is `pxart 1` throughout, and every `.px` file written for an earlier day still reads the same.

## 2026-11-25

### Fixed

- **`check` fails a file with a `@variant base`, and names the line.** A variant called `base` can never draw,
  since `base` always means the base colors. A sprite that gets one through `@palette` fails too, naming the
  palette file's line (PX-57).

- **`export --tiled` plays `pingpong` and `reverse` groups in Tiled as `anim` plays them,** instead of always
  forward. A group with a `repeat` gets a note, because a Tiled animation always loops (PX-62).

- **Clearer messages from `crop`'s night-colour warnings and `render --png`'s skip note.** The warnings name only
  the keys the crop actually copies, and the skip note's `export` command runs as printed (PX-58, PX-59).

## 2026-11-24

### Fixed

- **`anim` gives a pair of frames the same count both ways.** Pixels a shift pushes off the canvas, such as feet,
  now count as changed, and the readout says how many went past the edge. Some counts grow, and `paste --align
  shift` follows the new numbers. `anim` is also about twice as fast on big frames (PX-55).

- **`repeat=N` on a `pingpong` group means N one-way passes, as in Aseprite.** `repeat=1` plays 0 1 2 3 and stops,
  where it used to go there and back. `anim` previews it pass by pass, and `check`'s hold advice follows (PX-56).

- **`anim -o x.gif` plays as often as the group's `repeat` says,** instead of looping forever, and `--dry-run` says
  so too. Frame labels on `render` and `sheet` no longer run the size into the color count (PX-50).

- **Negative coordinates after a flag work as typed,** such as `mask --keep-circle -10,-8,34`. Negative widths,
  heights, radii and sizes are now errors, and `shift --region` clips a negative x or y to the frame instead of
  counting from the far edge (PX-52).

- **`-o FILE.px:FRAME` no longer makes a file or folder with that literal name.** An edit that writes a whole file
  says so and gives the `dup` to run first. `from-png x.png -o into.px:walk/9` adds the PNG to into.px as frame
  `walk/9` (PX-23).

- **Four small traps.** `check` warns about an empty `.px` file. `dup` and `frames --rename` work on a file of one
  unnamed grid. `outline --key` notes when the art already has a dark line, which an outline would double
  (PX-24).

- **`scene --variant` notes when the default backdrop shows through,** since `--bg` stays a day color: give `--bg`
  a night color. With `--anchor`, it names items wholly outside the window instead of counting cropped pixels
  (PX-48).

- **`bench/cast/pxc.py` names the key and the files when a cast breaks its one-palette rule,** instead of a raw
  traceback. A file no longer has to list keys it doesn't draw, and an empty cast folder is an error (PX-46).

- **Clearer messages from `from-png` and `palette --remove` when the arguments are in the wrong place,** each now
  printing the command to type, and from `compose`'s and `crop`'s `--rekey` advice, which says what renaming the
  keys would change (PX-21, PX-49).

## 2026-11-23

### Added

- **`check --headroom N` notes standing frames with fewer than N empty rows above the sprite,** so a jump has room
  to rise, and gives the `crop` that grows the canvas. `anim` now reports how many rows a group rises, and the
  headroom left at its highest (PX-13).

- **`render --silhouette` and `sheet --silhouette` draw each sprite's shape in one flat color,** for comparing
  silhouettes or for a blind review. Faint pixels stay faint, and it works with `--variant`, `--scale` and
  `--plain`. Give a color, as in `--silhouette '#ffffff'` (PX-31).

- **A derived night variant records the command that made it,** as a `# derived by` comment above `@variant`, so
  you can change one strength and run it again. The `palette` listing names which keys were kept lit or lamplit
  (PX-53).

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

- **`palette --lamplit KEYS@S` warms the keys near a lamp in a derived night,** mixing each toward its day color
  under lamplight by strength S. Repeat it for a near and a far ring. `pxart help palette` shows the setup
  (PX-30).

- **`review-pack` packs renders for a blind review,** each under a random id with its metadata stripped, and can add
  copies of each render to test whether the reviewer agrees with itself. `review-pack --score` tallies the
  verdicts and lists the copies that disagree (PX-5).

### Fixed

- **`pxart help topics` lists the help topics,** and topic names take any case.

- **`scene --anchor center` (or an edge, a corner, or `X,Y`) picks which part of the scene a smaller `--size`
  keeps.** Without it, the top-left is kept, as before (PX-36).

- **`export --indexed` writes no `ms` for a `@still` frame,** so a game can tell tiles and icons from animation
  frames (PX-33).

- **`bench/cast/web/pxc.js` loads a gzipped cast whatever its URL,** including one with a query string, or one the
  server already unzipped (PX-29).

- **Clearer output from `anim` on a single frame,** which says there is nothing to compare, and from `paste`'s and
  `frames --copy-to`'s `--rekey` advice, which says what renaming the keys would change (PX-41, PX-35).

## 2026-11-21

### Added

- **`check --outline K` lists the gaps in a sprite's outline,** with their coordinates, so holes no longer pass
  unseen. A frame that `outline --key K` just drew has none (PX-11).

  ```
  $ pxart check hero.px --outline k
       note: hero.px:idle/0: outline 'k' has 2 gaps at (3,1) (4,2)
  ```

- **`check` notes two frames in a row of an animation that are identical,** which reads as a stutter, and gives
  the commands that make it a deliberate hold instead. `--strict` fails it (PX-10).

### Fixed

- **The test suite passes on any machine.** Images in the example checks now compare by their pixels, not their
  bytes, which differ between zlib and Pillow versions (PX-27).

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

- **`bench/cast/` is a spike of a whole-cast format** that ships a cast as one file and decodes it in a Web Worker.
  Its README has the results.

## 2026-11-14

### Changed

- **Rendering a file with palette variants no longer slows down as it gains frames.** A 640-frame cast with two
  variants builds in 2.0 s instead of 8.2 s, with the same output.

## 2026-11-12

### Changed

- **`put --rows` can repair a frame whose rows are different widths,** which used to make every command refuse
  the file. `put --text ROW`, once per row, gives the rows on the command line instead of stdin.

- **The argument orders people guess first now work,** such as `dup FILE:a FILE:b`, `shift FILE DX DY` and
  `set FILE x,y KEY` with the key last.

- **A row one pixel too wide or short says which pixel to delete or add** to line it up with the rows around it.

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

- **Palette slots:** a key line can list alternative colors, `f #e0ac69 | #f5cfa0 | #c68642`, for games that
  recolor at runtime. `render --slots` and `sheet --slots` draw them, and `export --indexed` writes them.
  `pxart help slots` has the rules.
- `from-png --colors N` reduces a PNG with many colors to fit the free palette keys.
- `from-png --hard-edges`, `outline --min-alpha A` and `outline --pad`.

### Changed

- `check` and `from-png` count see-through pixels, and say when a key is faint or a shape touches the frame's edge.
- `from-png` with no `-o` prints its notes on stderr, so `from-png a.png > a.px` gives a clean file.
- Erase errors name a command that runs as printed.

## 2026-09-28

### Added

- **Tiled worlds:** `export --tiled` compiles a `world.src.json` and its `.map` rooms into `.world` and `.tmj`
  files. `pxart help worlds` has the details.
- `pxart world` draws a compiled world to one PNG.
- `check` reads `.world` and `.tmj` files.

## 2026-09-27

The first public version: the format, about forty commands, and the
[nine tutorials](examples/README.md), whose outputs the tests rebuild and compare.

### Added

- `compose --dry-run` prints what compose would say and the diff it would write.
- `paste --align shift|pivot|bottom|bbox` and `FILE:a,b,c` frame lists, so one paste can follow a bobbing
  animation.
- `ellipse --ring N` and `ellipse --box x,y,w,h`.
- `onion --variant V`, `stats --variant V`, and `render` and `sheet` cells labeled with their variant.
- `dup FILE:GROUP NEWGROUP`; `flip FILE:G -o FILE:NEWG`; `--replace` for `flip`, `rotate`, `transpose` and `dup`.
- `--dry-run` on every in-place edit, `new` and `palette` included.

### Changed

- `render` and `sheet` draw a grey checkerboard behind each frame by default.
- Every edit says what it did, such as `painted N px`, and `palette --add` names the keys it added.
- A missing selector lists the groups, and an unknown variant gets "did you mean".
- `anim` over several groups animates each on its own, and its percentages never go over 100.
