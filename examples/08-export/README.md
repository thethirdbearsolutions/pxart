# 08 · Export

`export` turns `.px` files into what engines and editors read.
`--aseprite` writes a sheet PNG and Aseprite-style JSON: frames with durations, a
`frameTags` entry per animation (with `repeat` for the one-shot attack), and the pivots as
Aseprite's own `meta.slices`. `--tiled` writes a Tiled tileset whose water tile animates.
`--frames` writes one PNG per frame, plus `pivots.json`.

```
pxart export alchemist.px --aseprite alchemist.json
pxart export harbor.px --tiled harbor.tsj
pxart export alchemist.px --frames frames
```

[`alchemist.png`](alchemist.png) + [`alchemist.json`](alchemist.json), from
[`alchemist.px`](alchemist.px) (shown at 4x):

![alchemist sheet](alchemist.x4.png)

```json
"frameTags": [
  {"name": "walk/right", "from": 0, "to": 5, "direction": "forward", "color": "#000000ff"},
  {"name": "attack/right", "from": 6, "to": 10, "direction": "forward", "color": "#000000ff", "repeat": "1"}
],
"slices": [{"name": "pivot", "color": "#0000ffff", "keys": [
  {"frame": 0, "bounds": {"x": 0, "y": 0, "w": 24, "h": 32}, "pivot": {"x": 12, "y": 31}}, ...
```

[`harbor.png`](harbor.png) + [`harbor.tsj`](harbor.tsj), from [`harbor.px`](harbor.px)
(at 8x; tiles 0-2 are the cobbles, 3 the planks, 4-5 the water):

![harbor tileset](harbor.x8.png)

```json
{"id": 4, "animation": [{"tileid": 4, "duration": 450}, {"tileid": 5, "duration": 450}],
 "properties": [{"name": "pxart_anim", "type": "string", "value": "water"}]}
```

[`frames/`](frames): `walk/right/0.png` ... `attack/right/4.png`
(![](frames/walk/right/0.png) ![](frames/attack/right/3.png)) and
[`frames/pivots.json`](frames/pivots.json): `{"walk/right/0": {"x": 12, "y": 31}, ...}`.
