# Concepts

pxart rests on a few ideas: a sprite file, the palette its characters stand for, the frames and
variants inside it, the folder of sprites it belongs to, and the tilemap that lays them out. Each
one gets a short explanation here and an editor to try it in. A glossary at the end covers every
term the docs use.

Every editor below works on real files from the [tutorials](/tutorials/). Edit any of them and the
picture redraws as you type. The editor is a sketchpad: `pxart check` checks far more than it does.

| File | What it holds | Made into |
|---|---|---|
| `hero.px` | a **sprite**: a palette, then one or more grids of its keys | PNGs, GIFs, sheets, Aseprite and Tiled exports |
| `palette.px` | a **palette file**: colors only, imported by sprites with `@palette` | the colors of every sprite that imports it |
| `room.map` | a **map**: a legend of tiles, then rows of legend characters ([format](/docs/map-format/)) | a scene PNG, a `.px` frame, a Tiled world |
| `harbor/` | a **pack**: a folder of sprites that share a palette file | one sheet, one check, one export |

## Sprites

A sprite is a plain-text `.px` file: a palette (one line per key, a character and a color), then
a grid that uses those characters, one per pixel. The sprite's size is the grid's size, so
nothing is declared or counted. Lines starting with `#` are comments, and `pxart 1`, the version
line, is optional.

```tryme
gem
```

Things to try: change `p #d8718c` to another color; add a `w` in the second row for more shine;
or make one row a character shorter, and see what the editor says.

A `.px` file is data, not a program: it says which color each pixel is, and nothing else
happens when it's read. pxart's drawing commands (`rect`, `ellipse`, `shade`, `outline`...) work
on a file the way you would, writing ordinary rows of keys into it. Nothing remembers which
command made which pixels, so a sprite drawn by commands and one typed by hand are the same
kind of file.

`pxart render gem.px -o gem.png` draws it with a pixel grid and rulers, and `pxart check gem.px` reports any
mistakes, with a code and a line number. See [the .px format](/docs/format/) and
[tutorial 01](/tutorials/01-format/).

## Keys and palettes

A **key** is one printable ASCII character, any except `# @ . " \`. Its **color** is
`#rrggbb`, `#rrggbbaa` (with alpha) or `transparent`. `.` is always transparent and is never listed.

A **palette file** is a `.px` file with key lines and no grid. A sprite imports it with
`@palette palette.px`, the path relative to the sprite's own file. Keys the sprite defines itself
win over imported ones. Change a color in the palette file and every sprite that imports it
changes.

```tryme
palette
```

`lamp.px` has no colors of its own. Open the `palette.px` tab and change `y`, the lamp's light,
or `G`, its post. Then switch back to `lamp.px`: its characters are painted in the palette file's
colors.

`palette lamp.px` lists a file's keys and what each variant does to them, and
`palette gem.px --import palette.px` moves a sprite onto a shared palette.
[Tutorial 01](/tutorials/01-format/) does this step by step.

## Variants

A **variant** is a named recolor: `@variant night`, then key lines giving some keys new colors,
up to the next blank line. Keys the variant doesn't name keep their base colors. Select a
variant with `%night` after a file name, or `--variant night`. A variant defined in a palette
file reaches every sprite that imports it.

```tryme
variants
```

Press `%night` to see the coast at night. Then open `palette.px` and change a color under
`@variant night`: `w` is the whitewash, `b` the sea. The lamp's `l` and `g` aren't in the night
variant at all, so the lamp stays lit.

`palette pal.px --variant dusk --derive-from base --darken 0.35 --keep-lit y` builds a whole
variant from the base colors, with the lights still lit. [Tutorial 03](/tutorials/03-variants/) covers
variants. **Slots** are a related idea for games that recolor at runtime: a key line can list
alternatives, `f #e0ac69 | #f5cfa0`, of which the first is the color everything draws
([`pxart help slots`](/reference/topics/slots/)).

## Frames and animations

One file can hold many grids. `@frame walk/down/0` names the grid below it, and a frame **id**
is a path. Frames that share a parent path form a **group**, and a group is an animation.
`@anim walk/down ms=110 direction=pingpong` sets the group's timing; `ms=` on a `@frame` line
overrides it for that frame. `pivot=x,y` marks the frame's anchor pixel, such as the feet.
`@still ui/icons` marks a group that isn't an animation. A file with one unnamed grid calls its
frame by the file's name.

```tryme
face
```

The face blinks because frame 1 holds its eyes shut for 120 ms. Try `ms=1000` on the
`@anim` line, or close only one eye in frame 1.

`pxart anim blink.px` prints what changed between each pair of frames, once whole-body movement
is taken out, so a walk that only bobs shows up as a number. [Tutorial 02](/tutorials/02-animation/)
covers frames and animations.

## Selectors

Any command that takes a file takes part of one: `hero.px:walk/down` is a group,
`hero.px:walk/down/0` is one frame, and `'hero.px:*'` (quoted for the shell) is every frame.
`%dusk` at the end picks a variant, and in a scene or a map `+h` or `+v` mirrors the item.

```tryme
selectors
```

Try `walk/down/3`, `idle/right`, `idle/right%dusk`, `*`, or `walk%night` to see the error
it gives.

pxart prints the frames with `pxart frames hero.px`. An edit at pixel coordinates (`set`, `line`,
`rect`...) needs a selector that names one frame, so it's clear which frame it changes.

## Packs

A **pack** is a folder of sprites that belong together, usually sharing one palette file, such as
the harbor market's 20 colors. Most commands take a folder as well as a file: `sheet harbor/`
draws every sprite in it on one PNG, `check harbor/` checks them all, and
`export harbor/ --frames out/` exports every frame. Packs of PNGs, the kind sold or shared online,
come in with `from-png`, which names each frame from the `labels.csv` a pack ships with. Then
`diff` proves the conversion is lossless.

```tryme
pack
```

Here, `palette.px` is the pack's colors, and `lamp.px` and `gem-shared.px` import it. Change
`k`, the outline, and both of them change. The barrel doesn't: it lists its own colors instead of
importing the palette. Press `%dusk` and the lamp and the gem turn to dusk while the barrel stays as
it is, since it has no dusk of its own. `pxart palette barrel.px --import palette.px` would move it
onto the shared palette.

Combining packs whose colors clash is [compose](/reference/compose/)'s job: `--rekey` gives
clashing keys free characters without touching the source files ([tutorial 05](/tutorials/05-compose/)).

## Maps

A **map** is a text tilemap, saved as `.map`. Its **legend** lines say what each character
stands for: a file, optionally with a frame, a variant and flags (`w tiles.px:water/0`,
`L lamp.px+b`). After a blank line come the rows, one character per cell, with `.` for an empty
cell. A `---` line starts another **layer** over the same cells, so props can stand on tiles.
Each cell is a 16x16 tile by default (`--tile`). An item draws from its cell's top-left
corner; `+b` stands it on its cell instead, bottom-aligned and centered.

```tryme
map
```

The `c` line lists three cobbles: a **variant list**. Each `c` cell draws one of them, picked
by a hash of the room's name and the cell, so the quay is never the same tile over and over,
and it draws the same way every time (see [variant tiles](/docs/map-format/#variant-tiles)).

Try: change a row of `p` to `w` to flood the planks; put another `L` in the second layer; or
point `c` at `tiles.px:cobble/c`. The tile and prop files are in the other tabs. Press `%dusk`
for the whole quay at dusk. The barrel has no dusk of its own, so its legend line says
`barrel.px%base`; take the `%base` off and the editor says what pxart would.

`pxart scene --map quay.map -o quay.png` draws a map as a PNG. `compose --map` builds the
same room as a `.px` frame, and `export --tiled` compiles a world of `.map` rooms for
[Tiled](https://www.mapeditor.org/) ([`pxart help worlds`](/reference/topics/worlds/)).
[The .map format](/docs/map-format/) has the whole syntax, and [tutorial 06](/tutorials/06-scene/)
builds a level in layers.

## Glossary

- **`.`**: the transparent key, in every palette, never listed.
- **`@anim`**: a line that sets a group's `ms`, `direction` (`forward`, `reverse`, `pingpong`,
  `pingpong_reverse`), `repeat` and `pivot`.
- **base**: a palette's own colors, before any variant. `%base` selects it explicitly.
- **cell**: one tile-sized square of a map, at column × tile width, row × tile height.
- **comment**: a line starting with `#`. The comment right above a line belongs to that line, and
  the comments at the top of a file are its **header**. Edits keep comments with their lines.
- **error code**: the stable name of a problem, like `E_UNKNOWN_KEY` or `E_ROW_WIDTH`, printed
  with the file, the line and the pixel. See [Errors](/docs/errors/).
- **frame**: one grid, named by `@frame ID`.
- **frame id**: a frame's name. It's a path, such as `walk/down/0`.
- **group**: the frames that share a parent path (`walk/down/0`, `walk/down/1`, ...). A group is an
  animation unless it's marked `@still`.
- **key**: one character that stands for one color in a sprite's grid.
- **key line**: a palette line, a key and then its color: `k #2b1e2f`.
- **labels.csv**: the file a pack of PNGs ships with, naming each image. `from-png --labels`
  uses it to name frames.
- **layer**: one grid of rows in a map. A `---` line starts the next one, and later layers draw on
  top.
- **legend**: a map's lines saying what each character stands for.
- **variant list**: a legend line listing several tiles; each cell picks one by a hash of the
  room's name and the cell.
- **map**: a `.map` text tilemap: a legend, then rows.
- **ms**: a frame's duration in milliseconds, from its `@frame` line or its group's `@anim`.
- **pack**: a folder of sprites that belong together, usually sharing a palette file.
- **palette**: a sprite's keys and their colors, its own and any imported.
- **palette file**: a `.px` file with only key lines (and variants), imported with `@palette`.
- **pivot**: a frame's anchor pixel, `pivot=x,y` from its top-left, used to line up frames and
  exported to Aseprite and Tiled.
- **preview**: what `render` draws: the sprite scaled up, with a pixel grid, rulers and a
  checkerboard behind transparent pixels. `render --plain` draws just the pixels.
- **scene**: a PNG of sprites placed at x,y, or of a map, from `pxart scene`.
- **selector**: the part after a file name that picks frames and a variant: `FILE:walk/down/0%dusk`.
- **slot**: one of a key's alternative colors, `f #e0ac69 | #f5cfa0`, for a game that recolors at
  runtime. The first is the key's color.
- **sprite**: a `.px` file with at least one grid.
- **still**: a group marked `@still`: frames that belong together but don't animate, like icons.
- **tile**: the size of a map's cells, 16x16 unless `--tile` says otherwise.
- **variant**: a named recolor of a palette, `@variant night`, selected with `%night` or
  `--variant night`.
- **version line**: `pxart 1`, optional, saying which version of the format a file uses.
