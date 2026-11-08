# Getting started

pxart is pixel art as text. A sprite is a small plain-text file: a palette, then a grid
of characters. It renders to PNG. Language models can write it, git can diff it, and
you can read it.

This page installs pxart, has you write a sprite, look at it, break it, and animate it.
That takes five minutes. The [tutorials](/tutorials/) then go further, one feature at a time.

## How it fits together

There are two layers. At the bottom is **the format**: `.px` sprites, palette files and `.map`
maps, all plain text that lives in git. Above it is **the tool**, `pxart`, whose commands read
those files, write them back, or turn them into pictures and other tools' files. pxart groups its
commands the way the diagram does, and so do `pxart -h` and the [reference](/reference/).

```layers
```

## Install

pxart needs Python 3.9 or newer. Its only dependency is [Pillow](https://pypi.org/project/pillow/).

```sh
pip install git+https://github.com/thethirdbearsolutions/pxart
pxart -h
```

It's also a single file. If you'd rather not install anything, download
[`pxart.py`](https://github.com/thethirdbearsolutions/pxart/blob/main/pxart.py) and run
`python3 pxart.py -h`.

## Write a sprite

Make a file called `face.px` and type this into it:

```px
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

- Each palette line is a **key**, one character, followed by a color: `#rrggbb`,
  `#rrggbbaa`, or `transparent`.
- The **grid** uses those keys, one character per pixel. `.` is always transparent and
  is never listed.
- Every row has to be the same width. The sprite's size is the grid's size, so there's
  nothing to declare or count.
- Lines starting with `#` are comments.

## Look at it

```sh
pxart render face.px -o face.preview.png --png
```

```text
wrote face.png (--png: face.px at 1x)
wrote face.preview.png
```

`render` draws a preview for looking at while you edit. Every pixel is drawn as a block,
with a grid, coordinate rulers, and a grey checkerboard where the pixels are transparent.
`--png` also writes the sprite at 1x, which is the file a game would use.

pxart is built around a loop: write some rows, render them, look, fix, and render again.
Every step is plain text in and a picture out, so you can take that loop yourself, give
it to a language model, or do both.

## Break it on purpose

Change one `g` to a `q`, a key the palette doesn't have, and check the file:

```sh
pxart check face.px
```

```text
FAIL face.px: 1 error(s)
     face.px:8: E_UNKNOWN_KEY (row 2, x=[8]): keys 'q' aren't in the palette
```

Every problem in a file is reported at once, each with a stable code, a line number and
the pixel it's at. [Errors](/docs/errors/) lists every code.

## Animate it

One file can hold several grids. Name each with `@frame`. Frames whose ids share a
parent path form an animation, and `@anim` sets its timing:

```px
# a small face that blinks
pxart 1
k #3f2631
g #43e1b3
y #fee761

@anim face/blink ms=400

@frame face/blink/0
....kkkk....
...kggggk...
..kgyggygk..
...kggggk...
....kkkk....

@frame face/blink/1 ms=120
....kkkk....
...kggggk...
..kgkggkgk..
...kggggk...
....kkkk....
```

Without `-o`, `anim` prints what changed between each pair of frames and writes nothing.
After it removes any whole-body movement, it counts the pixels that are left:

```sh
pxart anim blink.px
```

```text
  face/blink/0               400ms  vs face/blink/1: shift +0,+0 then 2px (7%)
  face/blink/1               120ms  vs face/blink/0: shift +0,+0 then 2px (7%)
```

Here only the two eyes changed. In a walk cycle, the same numbers show whether the legs
really move, or whether the sprite just bobs up and down. Add `-o blink.gif` to write
the GIF and a strip of the frames.

## Where next

- **[Concepts](/docs/concepts/)**: sprites, palettes, variants, frames, selectors, packs and
  maps, each with an editor to try it in, and a glossary.
- **[The tutorials](/tutorials/)**: nine short walkthroughs, from the format to palette
  variants, drawing tools, tilemaps, and exporting to Aseprite and Tiled. Each one ends
  with a picture you made.
- **[The .px format](/docs/format/)**: the whole format, including frames, pivots,
  shared palettes, `@variant` recolors and palette slots.
- **[Commands at a glance](/docs/commands/)**: every command in a paragraph, grouped by
  what it's for.
- **[Reference](/reference/)**: `pxart help` for each command, as the tool prints it.
