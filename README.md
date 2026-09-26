# pxart

Pixel art as text. A sprite is a small plain-text file (a palette, then a grid of
characters) that renders to PNG. Language models can write it, git can diff it, and
you can read it.

```
# a small face
. transparent
o #3f2631
g #43e1b3
y #fee761

....oooo....
...oggggo...
..ogyggyog..
...oggggo...
....oooo....
```

The tool is built for an author–render–look loop: write rows, render a preview with a
pixel grid and coordinate rulers, look at it, fix, and repeat. The animation strips show
what actually moved between frames once the whole-body bob is removed, so a walk cycle
that's secretly a bob shows up as a number.

## Status

Early. `px.py` is a single-file Python 3 CLI and needs only [Pillow](https://pypi.org/project/pillow/).
The format will grow (shared palettes, several frames per file, exports to Aseprite
JSON, Tiled and `.gpl`/`.hex` palettes) while staying compatible with the files shown here.

## Format

- **Palette:** one line per key: a single character, then `#rrggbb`, `#rrggbbaa`, or
  `transparent`.
- **A blank line** ends the palette.
- **Grid:** rows of palette keys, all the same width. The sprite's size is the grid's
  size; nothing is declared or counted.
- **Comments:** lines starting with `#`.

## Commands

```
python3 px.py -h
```

**Looking**
- `render`: 1x PNG next to each sprite, plus a preview sheet with grid and rulers.
- `sheet`: labeled comparison of any mix of `.px` and `.png`.
- `anim`: GIF, plus a strip PNG: the frames, and what changed from the previous frame
  after removing the whole-sprite shift.
- `onion`: one frame over a faded other.
- `scene`: sprites composited onto tiles, to judge them in context.

**Checking**
- `check`: row widths, palette keys, size, colors outside a reference palette, color
  budget, unused keys. Exits 1 on failure.
- `stats`

**Editing** (writes `.px`)
- `flip`
- `shift`: whole sprite or one rectangle.
- `recolor`
- `paste`: stamp a sprite or region onto another.
- `from-png`: any PNG to `.px`.

## Prior art

pxart's grid-plus-keyed-palette format is close to XPM2 without its header. It sits in
the same family as the sprite formats of
[PuzzleScript](https://www.puzzlescript.net/Documentation/objects.html),
[MakeCode Arcade](https://arcade.makecode.com/developer/images) and Bitsy.
[PixTXT](https://github.com/Fantety/PixTXT) (MIT) is the nearest standalone format; its
optional version line, built-in transparent `.`, located error codes and palette
overlays are shaping pxart's next revision.

## License

MIT
