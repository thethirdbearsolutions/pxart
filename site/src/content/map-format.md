# The .map format

A `.map` file is a text tilemap: a **legend** saying what each character stands for, then
**rows** of those characters, one per cell, in one or more **layers**. Like a `.px` file, it is
plain text that git can diff, and nothing in it is procedural: it names sprites and says where
each one goes. pxart turns it into a picture, a `.px` frame or a Tiled world.

```map
# A quay: cobbles, planks and water, then a lamp and a barrel on top.
c tiles.px:cobble/a
C tiles.px:cobble/b
p tiles.px:planks
w tiles.px:water/0
L lamp.px+b
b barrel.px%base

cCcCcC
CcCcCc
pppppp
wwwwww
---
......
.L..b.
```

```tryme
map
```

## The legend

Each legend line is a character, whitespace, then an item:

```text
<char> FILE[:frame][%variant][+h|+v|+hv|+b|+hb|+vb|+hvb]
```

- **FILE** is a `.px` file, or a `.png`, with its path relative to the map file. The rest of the line is
  the path, so a pack folder with spaces in its name works as it is (`b ../png/trees and bushes/bush.png`).
  Quotes are optional.
- **`:frame`** picks a frame or group of a `.px` file, as a selector does anywhere else
  (`tiles.px:water/0`). A misspelled one is an error at its legend line, with suggestions:

  ```text
  bad.map:6: E_SELECT: legend 'p': 'tiles.px:plank': no frame or group 'plank'; groups: cobble, water; frames: cobble/a, cobble/b, cobble/c, planks, water/0, water/1; did you mean 'planks'?
  ```
- **`%variant`** draws that item in a variant whatever the scene's variant is, and `%base` keeps
  its base colors (a lamp that stays lit in a night room).
- **`+h`**, **`+v`** and **`+hv`** mirror the item left-right, top-bottom or both.
- **`+b`** stands the item on its cell (see [Placement](#placement)); with a mirror it's one suffix, `+hb`.

A legend entry that can't load is an error at its line, so `pxart check room.map` finds a broken path
before anything is drawn.

## Variant tiles

A legend line can list two or more tiles instead of one. That's a **variant list**, and each
cell with its character draws one of them:

```map
g ../tiles/field.px:grass_a ../tiles/field.px:grass_b ../tiles/field.px:grass_c
```

The pick isn't random. It's a hash of the room's name (the map's file name without `.map`) and
the cell's column and row, so a map draws the same way every time, and `scene`, `compose --map`
and `export --tiled` all pick the same tile for each cell. Two maps with the same rows but
different names pick differently, so renaming a room changes its picks.

- **Every item is equally likely.** List a tile twice to make it twice as common, or list the
  others more often to make one rare.
- **Every item names a tile:** a `.px` file (with a `:frame` when it has several) or a `.png`,
  each with its own `%variant` and flips if it wants them (`flowers.px+h`). A single path with
  spaces in it stays one path.

```tryme
map-variants
```

The flowers are listed twice among eight, so they grow in about one cell of four. List
`flowers` a third time, give one of them `+h`, or turn some `g` cells into `w`. To see the picks
themselves, swap the variants for tiles that look nothing alike; this is tutorial 10's
`picks/meadow.map`:

```tryme
map-picks
```

[Tutorial 10](/tutorials/10-map-variants/) walks through variant lists step by step.

## Animated tiles

A map cell draws one frame, so a legend entry that names a whole animation is an error that
asks you to pick one:

```text
E_SELECT: legend 'w': 'tiles.px:water': legend 'w' 'tiles.px:water' is 2 frames; pick one with FILE:frame-id
```

Name the first frame (`w tiles.px:water/0`). `scene` and `compose --map` draw that frame, a
still picture. In Tiled the tile moves: `export tiles.px --tiled tiles.tsj` gives each
animation's first tile Tiled's own frame animation, with each frame's `ms`. A room compiled with
`export ROOM.map --tiled` then draws its water cells with that tile. Every copy of a tile
animates in step, because the animation belongs to the tile, not the cell.

The editors on this site play animated tiles the way Tiled will: the group's frames in file order,
each for its `ms`, every cell in step. That's a preview ahead of pxart itself, whose `scene` draws
the first frame. The site's tests pin each frame to pxart's render of that frame. Tiled plays a
group forward whatever its `@anim direction`, and so do the editors.

## Rows and layers

After the legend, a blank line, then the rows: one character per cell, with `.` for an empty cell.
A line `---` starts another layer of rows over the same legend. Layers draw in order, later ones
over earlier ones, and `.` is empty in each, so a ground layer and a props layer share cells. The map
is as wide as its widest row and as tall as its tallest layer.

`#` lines are comments only before the first row. After that, every non-blank line is a row, so `#`
can be a map character (a wall row `####`). Before the rows, a line that is exactly `# FILE.px` (one
token after the `#`, or a quoted path) is the legend line for `#`, not a comment; `check` and `scene`
print a note when they read one that way.

## Placement

A cell is one tile, 16x16 unless `--tile WxH` says otherwise. An item draws with its top-left
corner at its cell's top-left (column × tile width, row × tile height), so a 32x32 stall on 16x16
tiles hangs right and down over the next cells.

With `+b`, an item stands on its cell instead: bottom-aligned, and centered across it with the odd
pixel to the left. Its x is the cell's x plus (tile width − its width) ÷ 2, rounded down, and its y
is the cell's y plus the tile's height, minus its own. A 16x32 lamp then stands on its cell and rises
into the row above (cut off at the top edge on row 0).

## Variants

`--variant dusk` draws every item in its dusk colors, except items with their own `%variant`. A `.px`
item without that variant is an error, because the room would come out half at dusk:

```text
scene: --map (bad.map): bad.map:9: E_SELECT: legend 'b': 'barrel.px': unknown variant 'dusk' (have: none)
```

Give the item `%base` to keep its base colors in such a scene, as the quay does for its barrel, or
give the sprite a dusk of its own (`palette barrel.px --variant dusk --derive-from base ...`).

## What a map becomes

```sh
pxart check quay.map
```

```text
ok   quay.map: map 6x4 tiles, 6 legend char(s), 2 layers
```

- **A picture:** `pxart scene --map quay.map -o quay.png` draws it (4x by default; `--scale 1`
  for 1:1), and `--variant dusk` draws it at dusk. Items placed at `x,y` can be drawn on top
  (`pxart scene --map quay.map -o q.png hero.px:walk/0@40,20`).
- **A `.px` frame:** `pxart compose --map quay.map -o room.px` builds the room as one frame, with a
  palette merged from its tiles' palettes and their variants merged by name. It renders pixel for pixel as
  `scene --map` does, in every variant, and its header records the command that made it.
- **A Tiled world:** a `world.src.json` that lists `.map` rooms compiles to Tiled's `.world` and `.tmj`
  files with `export --tiled` ([`pxart help worlds`](/reference/topics/worlds/)), and
  `pxart world` draws the compiled world as one picture.

[Tutorial 06](/tutorials/06-scene/) builds a level in four layers, from a 256-pixel sky to the props.
