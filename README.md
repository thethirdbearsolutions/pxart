# pxart

Pixel art as text. A sprite is a small plain-text file (a palette, then a grid of
characters) that renders to PNG. Language models can write it, git can diff it, and
you can read it.

```
# a small face
k #3f2631
g #43e1b3
y #fee761

....kkkk....
...kggggk...
..kgyggygk..
...kggggk...
....kkkk....
```

The tool is built for an author–render–look loop: write rows, render a preview with a
pixel grid and coordinate rulers, look at it, fix, and repeat. Animation strips show
what actually moved between frames once the whole-body bob is removed, so a walk cycle
that's secretly a bob shows up as a number. When the feet stay put and only the body
above them moves (an idle breathing), the strip shows that instead of lighting up the legs.

## Install

```
pip install git+https://github.com/thethirdbearsolutions/pxart
pxart -h
```

It's also a single file: `python3 pxart.py -h`, with [Pillow](https://pypi.org/project/pillow/)
as the only dependency.

## Format

- **Palette:** one line per key: a single character, then `#rrggbb`, `#rrggbbaa`, or
  `transparent`. `.` is always transparent and needs no line. Keys can be any printable
  ASCII except `# @ . " \`.
- **Grid:** rows of palette keys, all the same width. The sprite's size is the grid's
  size; nothing is declared or counted.
- **Comments:** lines starting with `#`.
- **Version line (optional):** a first line of `pxart 1`.

### Frames and animation

Several grids can live in one file. Name each with `@frame`. A frame id is a path, and
frames that share a parent path form an animation:

```
pxart 1
@palette dungeon.px
@anim walk/down direction=pingpong ms=125

@frame walk/down/0
..kk..
.kggk.
@frame walk/down/1 ms=250
..kk..
.kgrk.
```

- **`@anim`:** sets a group's `direction` (`forward`, `reverse`, `pingpong`,
  `pingpong_reverse`, the same words Aseprite uses), `repeat` and default `ms`.
- **`@frame … ms=`:** overrides the duration for that frame.
- **`anim-set`** writes both: `anim-set hero.px:walk/down ms=125 direction=pingpong`
  updates (or adds) the `@anim` line, and `anim-set hero.px:walk/down/1 ms=250` sets one
  frame's `ms`. Only that line changes; `ms=` with no value clears it.
- **`@palette file.px`:** imports keys from a palette-only file, so a whole sprite set
  shares one palette. Keys defined locally win.
- **`@variant night`:** followed by key lines, defines a recolor, rendered with
  `--variant night`.
- **`@still ui/life`:** a frame group that isn't an animation; `@still *` marks every
  frame, top-level ids included (a parts file).

Any command that takes a file also takes `file.px:walk/down` (a whole group) or
`file.px:walk/down/0` (one frame). In zsh write `"${F}:walk/down"`: `"$F:walk/down"` applies a
modifier, and a missing input like `hero.pxalk/down` is reported as that mistake.

### Errors

Every problem in a file is reported at once with a stable code and a location:

```
hero.px:14: E_UNKNOWN_KEY (frame walk/down/1, row 2, x=[3]): keys 'q' aren't in the palette
```

Unknown `@sections` are kept as-is, or rejected with `check --strict`.

## Commands

`pxart -h` has the full reference.

- **Looking:** `render`, `sheet`, `anim` (GIF with 1x and 2x copies, plus a motion strip),
  `onion`, `scene` (.px/.png items at x,y, negative allowed, mirrored with a `+h`/`+v`
  suffix as in `hero.px:walk/0+h@3,4`; `--variant V` recolors the whole room;
  `--tint '#10183080'` lays a translucent color over the finished scene for night), and
  `tint`, which does the same to a PNG.
- **Maps** (`scene --map`): a legend line is `<char> <path>`, and the rest of the line
  is the path, so a pack folder with spaces works as is (quotes optional). A legend
  entry that can't load is an error at its legend line. A `#` line before the rows is a
  comment unless it is exactly `# FILE.px[:frame][%variant]` or `# FILE.png` (or a
  quoted path), which makes `#` a map char (a wall row `####`); `check` and `scene` note
  it. A line `---` after the rows starts another layer of rows over the same legend (a
  tile and a sprite in one cell); later layers draw on top, and `.` is empty. Each item
  draws from its cell's top-left, so a prop bigger than a tile hangs right and down; a
  legend entry ending in `+b` (`+hb` with a flip) stands it on its cell instead,
  bottom-aligned and centered (`L props/lamp.px+b`). `pxart -h` has a worked map.
- **Checking:** `check` (format errors, size, off-palette colors, color budget, unused
  keys; `.map` tilemaps too; notes Cyrillic/Greek/fullwidth letters posing as ASCII;
  exits 1), `stats`, `frames` (`--rm`/`--move` print only what they did; with a selector,
  `frames hero.px:walk/left` lists those frames, `--rm` removes them and `--after ID` moves them).
- **Editing:** `new` (a blank or filled frame, in a new or existing file), `put`
  (`put hero.px:walk/1 < rows.txt` replaces one frame's grid with rows from stdin, with
  optional palette lines merged like `compose`'s; checked like a file, errors at stdin's
  lines, nothing written on an error, and only that frame's lines change), `fill` (a
  region or the whole frame with one key), `flip`, `shift` (the pixels it leaves behind become `.`, or `--fill KEY`), `set`, `crop`, `recolor`
  (optionally within a region; `'a<>b'` swaps two keys, quoted for the shell; the key
  moves of one call apply together, so none feeds another), `mask` (erase outside `--keep x,y,w,h` or
  `--keep-circle cx,cy,r`, with a `--dither N` edge; `--invert` erases the inside
  instead; works on a rendered PNG too), `paste`, `compose` (stack layers into a frame;
  a new frame lands after its animation), `dup` (copy a frame), `anim-set` (timing), `palette --add`. Edits
  rewrite only the lines that changed, keeping the file's blank lines and comments, and
  an edit that changes nothing says `no change` and leaves the file alone. `-o OUT`
  always writes the whole file: `flip hero.px:walk/0 -o out.px` is a copy of hero.px
  with that frame flipped. `extract hero.px:walk -o walk.px` writes only the selected
  frames, with the same palette and imports; `--inline-palette` copies the imported keys
  they use (and the variants' colors for them) into the file and drops `@palette`, so the
  hand-off renders the same with nothing beside it.
- **Converting:**
  - `export --frames DIR` writes one PNG per frame.
  - `export --aseprite x.json` writes a sprite sheet and JSON with frameTags.
  - `export --tiled x.tsj` writes a tileset with tile animations.
  - `export harbor.px:cobble harbor.px:water --tiled t.tsj` exports only those frames
    (selectors of one file add up), so a tileset can leave out the big props.
  - Frame and tile ids count over the exported frames with each animation group
    contiguous, groups in order of first appearance, and all top-level frames together as
    one group. A file that already keeps each group together gets ids in file order;
    otherwise a frame moves up to its group (`a/0 b/0 a/1` gives `a/0 a/1 b/0`).
  - `palette --export x.gpl|x.hex` writes the palette.
  - `from-png` converts a PNG to a sprite.

## Prior art

pxart's grid-plus-keyed-palette format is close to XPM2 without its header. It sits in
the same family as the sprite formats of
[PuzzleScript](https://www.puzzlescript.net/Documentation/objects.html),
[MakeCode Arcade](https://arcade.makecode.com/developer/images) and Bitsy.
[PixTXT](https://github.com/Fantety/PixTXT) (MIT) is the nearest standalone format.
pxart's optional version line, built-in transparent `.`, located error codes, palette
variants and lenient handling of unknown sections all come from it.

## License

MIT
