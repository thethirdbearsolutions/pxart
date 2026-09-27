# 02 · Animation

[`hero.px`](hero.px) holds two animations: frames named `idle/right/0..3` (a side view,
48x48) and `walk/down/0..7` (toward the camera, 24x32). Each `@anim` line gives its group
a default `ms` and a `pivot`, the pixel under the hero's feet, and `@frame idle/right/0
ms=400` holds one frame longer. `anim` writes a GIF (each frame at scale, with 1x and 2x
copies beside it) and a strip whose second row shows what changed from the frame before,
once the whole-body bob is taken out; without `-o` it prints only those numbers. `onion`
lays one frame over another as a red silhouette, and `--feet 6` reads only the bottom rows.

![walk GIF](walk.gif) ![idle GIF](idle.gif)

```sh
pxart sheet hero.px --fit --rows group --align pivot --scale 4 -o sheet.png
pxart anim hero.px:walk/down -o walk.gif --scale 6
pxart anim hero.px:idle/right -o idle.gif --scale 4
pxart anim hero.px:walk/down            # the readout only: anim-walk.txt
pxart anim hero.px:idle/right           # anim-idle.txt
pxart onion hero.px:walk/down/0 hero.px:walk/down/1 -o onion.png
pxart onion hero.px:walk/down/0 hero.px:walk/down/3 --feet 6 -o onion-feet.png
```

Every frame, lined up by pivot:

![sheet: every frame, lined up by pivot](sheet.png)

## The walk: shift, then what's left

In a walk the whole body bobs, so `anim` finds the shift that best explains each frame
and counts only what changed after it: the legs and arms. `shift -1,+1 then 72px` means
the frame moved 1px left and 1px down, and then 72 pixels still differ. From
[`anim-walk.txt`](anim-walk.txt):

```text
  walk/down/0                110ms  vs walk/down/7: shift -1,+1 then 72px (20%) (no shift: 260px)
  walk/down/1                110ms  vs walk/down/0: shift +0,+1 then 26px (7%) (no shift: 205px)
```

![walk strip](walk.strip.png)

## The idle: rows still

In this idle the legs never move and the body above them breathes. Shifting the whole
sprite would light up the legs, so frames 1 and 3 read `no shift` and name the first row
that stays pixel-identical: `rows 34+ still`. The shift is still printed after it, for
comparison. From [`anim-idle.txt`](anim-idle.txt):

```text
  idle/right/1               240ms  vs idle/right/0: no shift then 237px (41%) (rows 34+ still; shift +0,+1: 48px)
  idle/right/3               240ms  vs idle/right/2: no shift then 247px (42%) (rows 34+ still; shift +0,-1: 62px)
```

![idle strip](idle.strip.png)

## Onion skins

`onion A B` prints how B's edges moved from A's. y grows down, so `+1` is lower:
`top +1` means B's top row of pixels is 1px below A's.

| `onion` 0 vs 1: the head dropped 1px | `onion --feet 6` 0 vs 3: a foot lifted 1px |
|---|---|
| ![onion of walk frames 0 and 1](onion.png) | ![onion of the feet in walk frames 0 and 3](onion-feet.png) |

From [`onion.txt`](onion.txt) and [`onion-feet.txt`](onion-feet.txt):

```text
B vs A: left +0, right +0, top +1, bottom +0; best shift +0,+1 then 26px changed (no shift: 205px)
B vs A (rows 26-31): left +0, right +0, top +0, bottom -1; best shift +0,-1 then 9px changed (no shift: 11px)
```
