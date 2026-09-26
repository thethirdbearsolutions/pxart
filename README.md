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
- **`@palette file.px`:** imports keys from a palette-only file, so a whole sprite set
  shares one palette. Keys defined locally win.
- **`@variant night`:** followed by key lines, defines a recolor, rendered with
  `--variant night`.
- **`@still ui/life`:** a frame group that isn't an animation; `@still *` marks every
  frame, top-level ids included (a parts file).

Any command that takes a file also takes `file.px:walk/down` (a whole group) or
`file.px:walk/down/0` (one frame).

### Errors

Every problem in a file is reported at once with a stable code and a location:

```
hero.px:14: E_UNKNOWN_KEY (frame walk/down/1, row 2, x=[3]): keys 'q' aren't in the palette
```

Unknown `@sections` are kept as-is, or rejected with `check --strict`.

## Commands

`pxart -h` has the full reference.

- **Looking:** `render`, `sheet`, `anim` (GIF with 1x and 2x copies, plus a motion strip),
  `onion`, `scene` (.px/.png items at x,y, negative allowed; `--map` text tilemaps;
  `--variant V` recolors the whole room; `--tint '#10183080'` lays a translucent color over
  the finished scene for night, and `tint` does the same to a PNG). A map legend line is `<char> <path>`: the rest
  of the line is the path, so a pack folder with spaces works as is (quotes optional),
  and a legend entry that can't load is an error at its legend line. A `#` line before
  the rows is a comment unless it is exactly `# FILE.px[:frame][%variant]` or
  `# FILE.png` (or a quoted path), which makes `#` a map char (a wall row `####`);
  `check` and `scene` note it.
- **Checking:** `check` (format errors, size, off-palette colors, color budget, unused
  keys; `.map` tilemaps too; exits 1), `stats`, `frames` (`--rm`/`--move` print only what
  they did).
- **Editing:** `new` (a blank or filled frame, in a new or existing file), `fill` (a
  region or the whole frame with one key), `flip`, `shift`, `set`, `crop`, `recolor` (optionally within a region),
  `mask` (erase outside `--keep x,y,w,h` or `--keep-circle cx,cy,r`, with a `--dither N`
  edge; `--invert` erases the inside instead; works on a rendered PNG too), `paste`, `compose` (stack layers into a frame; a
  new frame lands after its animation), `dup` (copy a frame), `palette --add`. Edits
  rewrite only the lines that changed, keeping the file's blank lines and comments, and
  an edit that changes nothing says `no change` and leaves the file alone. `-o OUT`
  always writes the whole file: `flip hero.px:walk/0 -o out.px` is a copy of hero.px with
  that frame flipped. `extract hero.px:walk -o walk.px` writes only the selected frames,
  with the same palette and imports.
- **Converting:**
  - `export --frames DIR` writes one PNG per frame.
  - `export --aseprite x.json` writes a sprite sheet and JSON with frameTags.
  - `export --tiled x.tsj` writes a tileset with tile animations.
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
