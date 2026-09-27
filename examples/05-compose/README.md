# 05 · Compose across packs

Three packs, each with its own palette file and its own darkness: the harbor market's
`dusk`, the lighthouse keeper's `night`, and wick's `dark`. `compose` stacks their frames
into one [`dock.px`](dock.px). They reuse the same letters for different colors (`k` is
three different near-blacks), so the first try is an `E_KEY_CONFLICT` that names every
clash and the fix. `--rekey` gives those keys free ones in `dock.px` (the packs' files
are untouched), and `--variant-map dusk=night,dark` builds one dusk from each layer's
dusk, night or dark, so the whole scene dims together.

```
H=harbor-market/harbor.px
layers=(
  $H:water/0@0,0 $H:water/0@16,0 $H:water/0@32,0 $H:water/0@48,0 $H:water/0@64,0
  $H:cobble/a@0,16 $H:cobble/b@16,16 $H:cobble/c@32,16 $H:cobble/a@48,16 $H:cobble/b@64,16
  $H:cobble/c@0,32 $H:cobble/a@16,32 $H:cobble/b@32,32 $H:cobble/c@48,32 $H:cobble/a@64,32
  $H:stall@2,6 $H:lamp@36,8
  lighthouse-keeper/keeper.px:idle/down/0@42,14 wick/player.px:idle/0@62,28
)
pxart compose -o dock.px --size 80x48 "${layers[@]}"          # E_KEY_CONFLICT: conflict.txt
pxart compose -o dock.px --size 80x48 --rekey --variant-map dusk=night,dark "${layers[@]}"
pxart scene --size 80x48 --scale 4 -o dock.x4.png dock.px@0,0
pxart scene --size 80x48 --scale 4 -o dock-dusk.x4.png dock.px%dusk@0,0
```

| base | `%dusk` |
|---|---|
| ![dock](dock.x4.png) | ![dock at dusk](dock-dusk.x4.png) |

The conflict ([`conflict.txt`](conflict.txt), one line per source file; shortened):

```
compose: layer 18 (lighthouse-keeper/keeper.px:idle/down/0): E_KEY_CONFLICT: 4 keys of this
layer are other colors in the new dock.px: 'c' #8ccfd6 (#a6dce4 there, from layer 1
(harbor-market/harbor.px:water/0)), 'k' #2a1f33 (#2b1e2f there, from layer 16
(harbor-market/harbor.px:stall)), ...; to keep both colors (no pixel changes color), add
--rekey: compose then gives this layer's keys free ones in the new dock.px ('c>e' 'k>j'
'w>q' 'y>v' 'r>F' 'l>H' 'g>I'; ...) and leaves lighthouse-keeper/keeper.px as it is. Or give
them those keys in a copy and compose from that: pxart recolor lighthouse-keeper/keeper.px
'c>e' 'k>j' 'w>q' 'y>v' 'r>F' 'l>H' 'g>I' -o rekeyed/keeper.px
compose: layer 19 (wick/player.px:idle/0): E_KEY_CONFLICT: 5 keys of this layer ...
```

With `--rekey` ([`compose.txt`](compose.txt)) it reports what moved and why:

```
note: --rekey gives lighthouse-keeper/keeper.px's keys free ones in dock.px: 'c>e' 'k>j'
'w>q' 'y>v' 'r>F' 'l>H' 'g>I' (lighthouse-keeper/keeper.px is unchanged): c k w y are other
colors there; r has dock.px's base color but other variant colors; ...
note: --rekey gives wick/player.px's keys free ones in dock.px: 'b>x' 'c>z' 'f>C' 'k>D' 'w>E'
(wick/player.px is unchanged)
wrote dock.px
```

1x: [`dock.png`](dock.png), [`dock-dusk.png`](dock-dusk.png).
