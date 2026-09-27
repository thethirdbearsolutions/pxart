# 03 · Palette variants

[`palette.px`](palette.px) has a comment on every key (which one is the sea, which the
lamp) and a `@variant night`: key lines that override the base colors, with the lamp's `l`
and `g` relisted unchanged so they stay lit. [`coast.px`](coast.px) imports it, so
`coast.px:lighthouse%night` renders the night. `palette --variant dusk --derive-from base`
builds a whole dusk from the base colors (darkened, then tinted, as `scene --tint` would)
with `--keep-lit` holding the lamp, and `palette --variant dusk --add` then sets one key by
hand. Both write into copies under `derived/` ([`derived/palette.px`](derived/palette.px)).
`palette FILE` alone lists the keys and what each variant recolors.

Base, derived dusk, hand-made night:

![the coast in base, dusk and night](panels.x4.png)

The whole sequence, runnable from this folder (the sky behind each panel is its `--bg`,
not part of the palette):

```sh
mkdir derived
cp palette.px coast.px derived/
pxart palette derived/palette.px --variant dusk --derive-from base \
  --darken 0.2 --tint '#ff6a3a38' --keep-lit l,g
pxart palette derived/palette.px --variant dusk --add 'w=#f2c6a8'   # whitewash catches the sunset
pxart palette derived/palette.px                                    # the listing: palette.txt

F=derived/coast.px
pxart scene --size 48x64 --scale 1 --bg '#8ccfd6' -o base.png \
  "${F}:sand@0,48" "${F}:sand@16,48" "${F}:sand@32,48" "${F}:lighthouse@2,6" "${F}:keeper@16,26"
pxart scene --size 48x64 --scale 1 --bg '#e0936a' -o dusk.png \
  "${F}:sand%dusk@0,48" "${F}:sand%dusk@16,48" "${F}:sand%dusk@32,48" \
  "${F}:lighthouse%dusk@2,6" "${F}:keeper%dusk@16,26"
pxart scene --size 48x64 --scale 1 --bg '#5a86b0' -o night.png \
  "${F}:sand%night@0,48" "${F}:sand%night@16,48" "${F}:sand%night@32,48" \
  "${F}:lighthouse%night@2,6" "${F}:keeper%night@16,26"
pxart scene --size 152x64 --scale 1 -o panels.png base.png@0,0 dusk.png@52,0 night.png@104,0
pxart scene --size 152x64 --scale 4 -o panels.x4.png base.png@0,0 dusk.png@52,0 night.png@104,0
```

The comments were written with `palette --comment`, which takes several keys per call; for example:

```sh
pxart palette palette.px --comment b 'sea' c 'sea foam; the shaded side of whitewash' \
  l 'lamp light (stays lit at night)' g 'lamp glow (stays lit at night)'
```

From [`derive.txt`](derive.txt), [`add.txt`](add.txt) and [`palette.txt`](palette.txt):

```text
new @variant dusk; derived from base (darkened 20%, tinted #ff6a3a38): recolors 15 key(s); l g kept lit (in their base colors); k N O held no brighter than their base colors by Rec. 709 luma (darker than a quarter: an outline stays dark; --lift-darks lets the derive brighten them); wrote derived/palette.px
@variant dusk; sets w #f2c6a8; wrote derived/palette.px
b #3a7ca5     local  # sea
c #8ccfd6     local  # sea foam; the shaded side of whitewash
l #fff4b0     local  # lamp light (stays lit at night)
variants: dusk, night
  dusk: recolors (darker) k w s S y Y n N b c a A o O r; relists unchanged: l g; inherits: nothing
  night: recolors (darker) k w s S y Y n N b c a A o O r; relists unchanged: l g; inherits: nothing
    # night: cool moonlight; lamp colors (l, g) stay lit
```

1x: [`panels.png`](panels.png), [`base.png`](base.png), [`dusk.png`](dusk.png), [`night.png`](night.png).
