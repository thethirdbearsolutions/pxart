# 03 · Palette variants

[`palette.px`](palette.px) has a `@variant night`: key lines that override the base
colors, with the lamp's `l` and `g` relisted unchanged so they stay lit.
[`coast.px`](coast.px) imports it, so `coast.px:lighthouse%night` renders the night.
`palette --variant dusk --derive-from base` builds a whole dusk from the base colors
(darkened, then tinted, as `scene --tint` would) with `--keep-lit` holding the lamp; it
writes into a copy under [`derived/`](derived/palette.px). `palette FILE` alone lists
the keys and what each variant recolors.

```
pxart palette derived/palette.px --variant dusk --derive-from base \
  --darken 0.2 --tint '#ff6a3a38' --keep-lit l,g
pxart palette derived/palette.px                  # the listing: palette.txt

# one panel per variant: every item with %base, %dusk or %night
pxart scene --size 48x64 --scale 1 --bg '#e0936a' -o dusk.png \
  derived/coast.px:sand%dusk@0,48 derived/coast.px:sand%dusk@16,48 derived/coast.px:sand%dusk@32,48 \
  derived/coast.px:lighthouse%dusk@2,6 derived/coast.px:keeper%dusk@16,26
pxart scene --size 152x64 --scale 4 -o panels.x4.png base.png@0,0 dusk.png@52,0 night.png@104,0
```

Base, derived dusk, hand-made night:

![base, dusk, night](panels.x4.png)

From [`derive.txt`](derive.txt) and [`palette.txt`](palette.txt):

```
new @variant dusk; derived from base (darkened 20%, tinted #ff6a3a38): recolors 15 key(s);
l g kept lit (in their base colors); k N O held no brighter than their base colors ...

variants: dusk, night
  dusk: recolors (darker) k w s S y Y n N b c a A o O r; relists unchanged: l g; inherits: nothing
  night: recolors (darker) k w s S y Y n N b c a A o O r; relists unchanged: l g; inherits: nothing
    # night: cool moonlight; lamp colors (l, g) stay lit
```

1x: [`panels.png`](panels.png), [`base.png`](base.png), [`dusk.png`](dusk.png), [`night.png`](night.png).
