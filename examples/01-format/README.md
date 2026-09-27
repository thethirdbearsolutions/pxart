# 01 · Format basics

A sprite is a text file: palette lines (a key character, then a color), then a grid of
those keys. `.` is always transparent. [`barrel.px`](barrel.px) carries its own five keys;
[`lamp.px`](lamp.px) has none and imports them with `@palette palette.px`, the way a whole
pack shares one palette ([`palette.px`](palette.px)).

| `barrel.px` | `lamp.px` (imports `palette.px`) |
|---|---|
| ![barrel preview](barrel.preview.png) | ![lamp preview](lamp.preview.png) |

```sh
pxart render barrel.px -o barrel.preview.png --png
pxart render lamp.px -o lamp.preview.png --png
```

`render` draws a preview with a pixel grid and rulers; `--png` also writes the 1x sprite
beside the `.px` and prints its path: [`barrel.png`](barrel.png) and [`lamp.png`](lamp.png), each 16px wide.

```px
# A barrel from the harbor-market pack: a palette, then the grid.
pxart 1
k #2b1e2f
G #5d5869
b #9b6440
B #5e3a2a
h #6e4230

....kkkkkkkk....
...kBbbbbbbbk...
..kBbbbbbbbbbk..
..kGGGGGGGGGGk..
.kBbbhbbbbhbbbk.
...
```
