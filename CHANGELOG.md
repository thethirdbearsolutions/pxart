# Changelog

What changed in pxart, newest first. pxart is still `0.1.0`: until a first tagged
release, entries are grouped by the day they landed on `main`. The file format is
`pxart 1` throughout, and every `.px` file written for an earlier day still reads the same.

## 2026-11-25

### Fixed

- **`check` fails a `@variant base` (PX-57).** `base` is the base palette's name: `%base` and `--variant base` draw
  the base colors whatever the file says, so a `@variant base` parsed and its colors never drew, and `check` only
  noted it. Now the file fails, in one line with the line number and no `ok` line beside it: `FAIL pal.px:19:
  E_BAD_ID: '@variant base': 'base' is the base palette's name (%base and --variant base draw the base colors), so
  this variant's colors never draw; give it another name (edit the line: @variant NAME)`. A sprite that gets one
  through `@palette` fails naming the palette file's line (`comes from pal.px:19`, through nested imports too).
  Files still parse and render as before.

## 2026-11-24

### Fixed

- **Four small traps (PX-24).** An empty `.px` (a failed `from-png X.png > X.px` leaves one) passed `check` as `ok
  X.px: palette file, 0 key(s)`; now a warning line says `empty: nothing in it` (run the command again, or remove the
  file), and `--strict` fails it. `dup
  walker.px:walker idle/0` on a file of one unnamed grid said `dup needs FILE:frame-id ...; frames: walker`, listing the
  frame it refused, and `frames --rename walker ...` was `E_MIXED_FRAMES`; both now turn the grid into `@frame walker`
  first (with a note naming the id; a file name that can't be an id is an error), and a rename of another name says what the grid goes by. `outline
  --key k` on art with its own dark line now notes `12 of the shape's 12 edge px are already as dark as k (d): the art
  has a line of its own, and an outline outside it makes a 2px dark rim; --inside draws on that edge instead`. The note
  counts the key's own pixels, needs a dark, mostly opaque key, and names only the frames that have the line. Its
  advice to restore the file from git and re-outline with `--pad` now adds: if you added the key with `palette --add`
  since your last commit, add it again.

- **`-o FILE.px:FRAME` no longer makes a file named `FILE.px:FRAME` (PX-23).** `outline w.px --key k -o w.px:walk/9`
  made a folder `w.px:walk` holding a file `9`, and left w.px alone; `from-png x.png -o into.px:new` wrote a file
  literally named `into.px:new`. An edit that writes a whole file (`outline`, `shade`, `fill` and the rest that go
  through the shared edit path) now says `-o w.px:walk/9 names a frame (walk/9), but this edit writes a whole file,
  so -o takes a file`, and for a frame or group of the same file, the route: `copy it first: pxart dup w.px:walk/0
  walk/9, then edit w.px:walk/9` (`--replace` when that frame exists; a note when the copy would join an
  animation; when the id is the one being edited, `leave -o off`; when it is a group for a frame or a frame for a
  group, `give a new id`). `from-png x.png -o into.px:walk/9` adds the PNG to into.px as frame walk/9 (several
  PNGs or `--grid`: `walk/9` is their prefix, as `--id`; with `--id`, `--names`, `--labels` or `--prefix-dir` too, an
  error). No `.px` write makes a file named with a `:FRAME`: any other command handed one (put, anim-set, extract)
  says `-o takes a file`. compose and crop still take `OUT:FRAME` as a frame, flip, rotate and transpose
  `OUT:NEWGROUP`; a folder whose name has a `:` still works as a folder, and a `%variant` on `-o` is an error, not
  dropped.

- **Two argument errors say what to do (PX-21).** `pxart from-png in.png face.px` read face.px as a second PNG and
  failed with `E_FILE: No such file or directory`; now `face.px is a .px, and from-png reads PNGs: the output goes
  after -o: pxart from-png in.png -o face.px`: the command as typed with the .px moved after `-o`, so `--grid` and
  the rest stay (several .px name the first, beside an `-o` it offers `--palette`, and a PNG after an option is read
  as an input, as it reads). `palette f.px --remove h j` failed with argparse's bare `unrecognized arguments: j`; now
  `(--remove takes its keys as one word: pxart palette f.px --remove hj or pxart palette f.px --remove h,j)`, the
  keys of every `--remove` (and `--remove=h`, `--rem`) and the stray words in one, `--to` and the rest kept, a `,`
  key only in the comma form (`,,x`) and a `-` key after `=` (`--remove=-h`). A comma list `--remove h,j` was already
  read as h and j and leaves a real `,` key alone; `--remove ,` removes that one.

- **`repeat=N` on a pingpong means what it means in Aseprite: N one-way passes (PX-56).** pxart counted whole round
  trips, so `repeat=1` played 0 1 2 3 2 1 and stopped on frame 1. Aseprite's own playback (its `playback.cpp`, and
  tests like `SimplePingPong3Repeats`, where a 0..2 pingpong with repeat 3 plays 0 1 2 1 0 1 2) counts each one-way
  pass, turning at an end frame it doesn't play twice; `@anim` uses Aseprite's words and `export --aseprite` writes
  the tag's repeat for Aseprite to read, so pxart now means the same. `anim` writes a pingpong with a repeat out pass
  by pass and plays it through once (`repeat=1`: 0 1 2 3; `repeat=2`: 0 1 2 3 2 1 0; `pingpong_reverse` starts from
  the last frame), the way back marked `back` and a pass forward again `again`, up to 64 passes; 0 or none still
  loops one cycle, 0 1 2 3 2 1. `check`'s hold advice for identical frames at a pingpong's end doubles the neighbours only
  at an end where a pass turns: the far end from 2 passes, the starting end from 3, both when it loops (`repeat=2`
  with frames 0 and 1 alike holds 600 ms, not 900). FORMAT and the README say so.

- **`anim`'s GIF plays as often as `repeat` says (PX-50).** An `@anim idle ... repeat=1` group read `plays once
  (repeat=1); no wrap-around`, but `anim -o idle.gif` wrote `loop=0`, forever, and `--dry-run` said `300 ms a loop`.
  Now the GIF has no loop extension for `repeat=1` (it plays once), `loop=N-1` for `repeat=N`, and loops forever
  for 0 or none, as before (a GIF can say at most 65536 plays; a bigger repeat is written as that, with a note); the
  repeat is a whole group's: a part of a group, or frames of several groups, loop, as they play as selected; the dry run says `300 ms, played once (repeat=1)` or `300 ms a pass, 3 passes
  (repeat=3)`. A selection across groups or files loops, as before. Render and sheet labels on a 16x24 frame read
  `16x249c`: the font's space is narrow (2 px), so the size and color count are now drawn apart (`16x24  9c`), and a
  frame up to 30 px tall (was 22) gets its 1x copy beside the label, in the pad under it. The example images with
  labels are rebuilt.

- **`anim` reads a pair of frames the same both ways (PX-55).** Its shifted comparison counted only the pixels left
  on the canvas, so a shift that pushed a sprite's bottom row (its feet, a shadow) past the edge didn't count them:
  a slime's `breathe/3 vs breathe/2` read `shift +0,-1 then 12px` and the way back `shift +0,+1 then 0px`, a "just a
  bob" on one leg of a pingpong and 12px on the other. Now a pixel pushed past the edge counts as changed, on a
  canvas padded by the shift, both when the best shift is chosen and in the number; `anim`, the strip and `onion`'s
  whole-canvas readout give a pair the same count in both directions (a tie between two shifts of the same count,
  a mirror-image pair, can name the same shift both ways). Counts grow where a bob pushes the feet off the canvas (the
  example walk's `shift +0,+1 then 26px` is 30px), and a shift that only pushed pixels off no longer beats no shift.
  `onion --rows`/`--feet` bands still count only their own rows. No pixel of the strip can show a pixel that went
  past the edge, so the number says how many it counts: `then 30px (8%; 4 past the edge)`, in a `rows N+ still`
  reading and in `onion` too. `paste --align shift` follows the same best shift, so a sprite whose feet stay on the
  canvas floor while its head drops no longer reads as a whole-body bob. The comparison runs in Pillow, not Python:
  `anim` on a 256x256 animation takes about half the time it did.

- **The cast encoder says which key breaks the one-palette rule (PX-46).** `bench/cast/pxc.py` needs one palette
  for a whole cast, which neither its README nor its docstring said, and it failed with a raw `KeyError` when the
  first file (by name) didn't list a key another drew, or with `characters differ` naming nothing. Now a file
  needn't list keys it doesn't draw (so `pxart check`'s `palette --remove` advice is safe to follow), and a key
  colored two ways is `PXC1 needs one palette for the whole cast: key 'k' in the base differs between files
  (fox.px #1b1420, owl.px #2b1d32)`; a variant one file lacks names that file. A file of one unnamed grid goes by
  its file's name instead of an `AttributeError`. The README and docstring say how `CAST_DIR` is laid out (a flat
  folder of `.px` files, one per character, named after it; palette-only files skipped) and that `cast.bytes` is
  the decoded size, not the bytes on the wire. An empty or missing cast folder, or one whose files sit in a subfolder,
  is an error instead of a 9-byte cast, and a file that doesn't parse gives its pxart error instead of a traceback.
  Casts that encoded before encode to the same bytes.

- **`scene --variant` says the default backdrop stays a day color (PX-48).** `scene --map island.map --size
  320x240 --anchor center --variant night` drew the room at night on the day `#472d3c` border, and nothing said
  `--bg` isn't recolored. Now, with `--variant` and no `--bg`, a note counts the backdrop pixels that show (a pixel
  drawn less than fully opaque lets it through): `note: --variant night doesn't recolor the backdrop: 3 px show the
  default --bg #472d3c, a day color; give --bg a night color (or --bg transparent)`; a scene the room covers, or an
  opaque `--tint`, says nothing. With `--anchor`, the crop counts are left out, since the window is the point and
  the `--anchor` note says what it shows (`40854 px of the map ... were cropped` varied by corner); an item wholly
  outside the window is named instead (`item 2 (lamp.px) is wholly outside the window`). The map's crop count
  counts each scene pixel once, so overlapping layers and tiles bigger than their cell no longer count a pixel
  twice. The help says `@still` takes one group a line and that top-level frames need none, and `@still
  grass,path`'s `E_BAD_ID` adds `(a @still line per group)`.

- **Negative coordinates after a flag work as typed (PX-52).** `mask lamp.px --keep-circle -10,-8,34` failed with
  argparse's `expected one argument` and no hint, because a word starting with `-` that isn't a plain number
  (`-10,-8,34`, `-8,4`) was read as an option; a chained command then went on with an uncut copy. Every command now
  reads a word of `-` and a digit as a value, a number, coordinates, a size or a rect, exponents too (`--keep`,
  `--keep-circle`, `--anchor`, `--at`, `--region`, `set`'s points, ...; `rect`, `line`, `poly`, `ellipse`, `arc`,
  `flood` and `crop` already took negative points): no option of pxart's starts with `-` and a digit. Another value
  starting with `-` (the key `-` in `--keep-lit -,k`) still needs `=`, and the error now says so: `argument
  --keep-lit: expected one argument (a value starting with '-' goes after '=': --keep-lit=-,k)`; for `--add`,
  `one value to each`. With negatives now easy to type, the coordinate flags were audited: `shift --region
  -2,0,3,2` read a negative x or y as a Python index from the far edge (a zero shift erased columns 2-3, a hero
  lost its legs) and now clips to the frame as `fill` and `recolor` do; a `--size` of `0x5`, or a negative one, was
  a traceback in `scene` and taken by `check` and `compose`, and is now `--size wants WxH`; `crop F 0,0,-3,4` wrote
  an empty frame and `mask --keep-circle 5,5,-3` erased everything, and a negative w, h or r is now `E_BAD_ARG`.

- **`compose` and `crop` into an existing file say what the `--rekey` they offer changes (PX-49).** PX-35 put a
  note after paste's and `frames --copy-to`'s variant WARNINGs; `compose -o tiles.px:c quarter.px@0,0` and `crop
  quarter.px 0,0,2,1 -o tiles.px:d` printed the same WARNINGs, `... compose --rekey E gives it a key of its own`,
  with no note, so their advice would still rename stand-in keys a game reads by letter. Now the same note follows
  them: `note: compose --rekey D,E,F,L would give those pixels new letters in tiles.px; left off, the keys stay (a
  key-for-key copy) and take tiles.px's variant colors`; after a partial `--rekey D,F` it says `adding E,L to
  --rekey ...`, and more than six keys, or a list a shell can't take as written, gives a bare `--rekey`; each key
  is listed once, however many source files warn about it.

## 2026-11-23

### Fixed

- **A failed `export` writes nothing (PX-44).** `export a.px b.px --indexed o/k.json --frames o/f --aseprite o/s.json`,
  where the two files give a key different colors, exited 1 with `E_KEY_CONFLICT` but had already written the sheet,
  its JSON and the frame PNGs, stale files that looked like a success, against the rule that a command that fails
  wrote nothing. `--indexed`'s palette and variant merge, and `--tiled`'s one frame size (`E_TILE_SIZE`), now run
  before any output is written, so `o/` isn't even made; so does every file the export would write (each frame's PNG, `pivots.json`, the
  sheets and JSONs): one under a file, or one that is a directory, is `E_FILE` before any is written, and two outputs
  onto one file (`--aseprite s.json --indexed s.json`) are `E_BAD_ARG` instead of the last one silently winning
  (`--aseprite X.json --tiled X.tsj` still share X.png, as documented). The
  `E_KEY_CONFLICT` hint's command is quoted once (`pxart recolor b.px 'w>K'`, K a free key; its quotes nested
  before), and a variant conflict names both files.

- **`check --outline K` says when K draws nothing in a render (PX-43).** It compared keys, not colors, so a sprite
  outlined in a `k` that is `transparent` in the base and visible only in `@variant night` passed, though the base
  render shows no outline; and the reverse (opaque by day, alpha 0 at night) passed too. Now a note names the
  renders where K draws nothing, each read with its own palette (a variant's own slot list too): `o.px: outline 'k'
  draws nothing in base (transparent there), so that render shows no outline`; with `--min-alpha A`, those where K is
  fainter than A. With several keys (`--outline kL`), a render where only some are gone `loses the outline's 'L'
  pixels`, and one where all are gone shows no outline. A K that draws in no render isn't part of the shape, so the
  gaps aren't checked, and a line says so instead of pointing gaps inside it. A K whose see-through color comes from
  an imported palette names that file (`outline 'k' (from pal.px)`), and a slot color that does draw K is named.

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

- **A second `palette --add` adds to the first (PX-54, PX-25).** `palette p.px --add f=#a07040 --add g=#a07041` set
  only g: `--add` took a run of values, and a second `--add` replaced the first's, with no error or note. Now every
  `--add` adds its values (`action="extend"`), with or without `--variant`, so a `# derived by` line with several
  `--add=V` values (PX-53 writes them so for a value starting with `-`) makes the same file again. One key given twice
  is said once, or, in two colors, refused (`--add gives 'p' two colors, p=#9a5ad0 and p=#6a3a9a: give it one`; it
  was `E_KEY_CONFLICT` naming the key as already in the file, or the last color silently). The note after an `--add`
  on a derived variant names the keys its `# derived by` line doesn't make so, and says nothing when there are none;
  and an edited copy (`-o copy.px`) gets its `# derived by` lines re-pointed at itself, as a derive's `-o` does.

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

- **A derived variant says how it was made (PX-53).** After `palette --variant night --derive-from base --darken
  0.55 --tint '#18204880' --keep-lit y --lamplit f@0.6`, the file kept only the colors, so changing one strength
  meant remembering the whole command. The derive now writes that command, as a comment, right above `@variant
  night`: `# derived by (from this file's folder): pxart palette pal.px --variant night --derive-from base --darken
  0.55 --tint '#18204880' --keep-lit y --lamplit f@0.6`, with `--match` (its path from the file's folder),
  `--lift-darks`, and an `--add` or `--keep` of the same call; `--darken` is written exactly, and a value starting
  with `-` as `--keep-lit=-,k`. FILE is named as the file the line lives in (`-o OUT`'s name, for an edited copy), so
  run from that folder the line gives the same file again. A re-derive replaces it, and `--comment @variant night`
  keeps it under the new comment. A later `--add` or `--keep` on that variant prints a note that the line doesn't
  include it. The `palette` listing names the keys the line kept lit or lamplit by role, as the derive's summary
  does, instead of under "recolors (darker)" and "relists unchanged": `night: recolors (darker) k b g; kept lit: y;
  lamplit: f (0.6); inherits: nothing`, but only while a key's color is still what the line makes. It runs the line
  on a copy to check, and lists any other key apart (set since by `--add` or by hand, or a base color changed since):
  `not what its '# derived by' line makes now: f`; a key the line's own `--add` sets has no role, and a line that
  can't run there (one `--extract-to` copied from another file) names no roles and says so. Only the last comment
  line above `@variant`, in exactly that form, is the line: an author's `# derived by: ...` comment stays a comment. An imported key's `# lamplit` mark is no longer repeated as its comment in the listing. The file
  format is unchanged: the line is an ordinary comment.

- **`check --headroom N`, and how far an animation rises (PX-13).** A fox's jump rose 6 rows, then 3, on a canvas its
  standing frame already filled; reviewers named the fault in only 7 of 20 jumps, and it was set when the standing
  frame was drawn. `check fox.px --headroom 8` notes, a line per group (or top-level frame), the frames standing on
  the group's ground whose topmost drawn pixel (a key drawn in any variant counts) is fewer than 8 rows from the
  canvas top, and gives the `crop` that grows the canvas (and, for a frame with a pivot, the `anim-set` that keeps its
  feet put). The ground is where `anim` lines the frames up: each frame's lowest solid pixel (alpha 128 and up)
  against its pivot, or its bottom row, judged over the whole group whatever was selected, so a faint shadow, frames
  of other sizes and a pivoted jump read as they play. `.px` frames only: a PNG has no note. `note: fox.px:stand/0: 2 rows of headroom (want 8); to grow
  the canvas 6 rows up: pxart crop fox.px:stand/0 0,-6,16,22 -o fox.px:stand/0`. A jump's airborne frames (their
  bottom edge above the group's lowest) are meant to be high and aren't noted. It's a note, not a failure. `anim`
  adds a line for a group whose bottom edge moves, from the frames as it places them (by pivot, or as drawn on one
  canvas), counting only solid pixels (alpha 128 and up), so a faint ground shadow doesn't pin it: `vertical travel:
  3 rows (the bottom edge from row 23 up to 20); 1 row of headroom at its highest (jump/2)`, so a 3-row jump is a
  number. It reads what `anim` draws (the base, or `--variant`), so a key drawn only at night counts for `check`'s
  headroom and not for a base `anim`. A walk or an idle whose feet stay gets no such line; a walk that lifts the whole body a row does.

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
