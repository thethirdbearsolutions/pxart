# 02 · Animation

[`hero.px`](hero.px) holds two animations: frames named `idle/down/0..3` and
`walk/down/0..7`. Each `@anim` line gives its group a default `ms` and a `pivot` (the
pixel under the hero's feet), and `@frame idle/down/0 ms=360` holds one frame longer.
`anim` writes a GIF (each frame at scale, with 1x and 2x copies beside it) and a strip
whose second row shows what changed from the frame before, once the whole-body bob is
taken out; without `-o` it prints only those numbers. `onion` lays one frame over another
as a red silhouette, and `--feet 6` reads only the bottom rows.

```
pxart sheet hero.px --rows group --align pivot --scale 4 -o sheet.png
pxart anim hero.px:walk/down -o walk.gif --scale 6
pxart anim hero.px:idle/down -o idle.gif --scale 6
pxart anim hero.px:walk/down            # readout only: anim-walk.txt
pxart onion hero.px:walk/down/0 hero.px:walk/down/1 -o onion.png
pxart onion hero.px:walk/down/0 hero.px:walk/down/3 --feet 6 -o onion-feet.png
```

![walk GIF](walk.gif) ![idle GIF](idle.gif)

![sheet: every frame, lined up by pivot](sheet.png)

The walk strip ([`anim-walk.txt`](anim-walk.txt) has the same numbers):

![walk strip](walk.strip.png)

```
  walk/down/0                110ms  vs walk/down/7: shift -1,+1 then 72px (20%) (no shift: 260px)
  walk/down/1                110ms  vs walk/down/0: shift +0,+1 then 26px (7%) (no shift: 205px)
  ...
```

| `onion` 0 vs 1: the head rose 1px | `onion --feet 6` 0 vs 3: a foot lifted |
|---|---|
| ![onion](onion.png) | ![onion feet](onion-feet.png) |
| `B vs A: left +0, right +0, top +1, bottom +0; best shift +0,+1 then 26px changed (no shift: 205px)` | `B vs A (rows 26-31): left +0, right +0, top +0, bottom -1; best shift +0,-1 then 9px changed (no shift: 11px)` |

Also: [`idle.strip.png`](idle.strip.png), [`anim-idle.txt`](anim-idle.txt),
[`onion.txt`](onion.txt), [`onion-feet.txt`](onion-feet.txt).
