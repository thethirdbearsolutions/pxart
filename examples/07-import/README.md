# 07 · Import from PNG

`from-png --grid 16x16` slices a sprite sheet into frames, one group per row of cells,
named by `--names`. `--palette beetle_pal.px` makes the new file import that palette and
reuse its keys, so the imported grids read like the originals. `diff` then proves the
round trip lossless: it compares two renders pixel by pixel and exits 1 when anything
differs. The sheet here is laid out from [`beetle.px`](beetle.px) with `scene`, so the
whole round trip can be rebuilt.

```
# the sheet: walk/right on row 0, walk_cave/right on row 1
pxart scene --size 64x32 --scale 1 --bg transparent -o sheet.png \
  beetle.px:walk/right/0@0,0 beetle.px:walk_cave/right/0@0,16 \
  beetle.px:walk/right/1@16,0 beetle.px:walk_cave/right/1@16,16 ...

pxart from-png sheet.png --grid 16x16 --names walk/right,walk_cave/right \
  --palette beetle_pal.px -o imported.px
pxart diff beetle.px:walk/right imported.px:walk/right
pxart diff beetle.px:walk_cave/right imported.px:walk_cave/right
```

The input, [`sheet.png`](sheet.png), at 8x:

![sheet](sheet.x8.png)

What came back, [`imported.px`](imported.px):

![imported frames](imported.png)

```
$ pxart from-png sheet.png --grid 16x16 --names walk/right,walk_cave/right --palette beetle_pal.px -o imported.px
wrote imported.px (8 frame(s): walk/right 4, walk_cave/right 4)
$ pxart diff beetle.px:walk/right imported.px:walk/right
4 frame(s): 4 same
$ pxart diff beetle.px:walk_cave/right imported.px:walk_cave/right
4 frame(s): 4 same
```

And the check bites when frames do differ ([`diff-mismatch.txt`](diff-mismatch.txt)):

```
$ pxart diff beetle.px:walk/right imported.px:walk_cave/right
walk/right/0 vs walk_cave/right/0: 57 px differ in 1,3,12,7 (x,y,w,h)
...
4 frame(s): 0 same, 4 differ
(exit 1)
```

A PNG carries no timing, so `imported.px` has no `@anim` lines; `anim-set
imported.px:walk/right ms=110` puts them back.
