# 08 · Export

`export` turns `.px` files into what engines and editors read.
`--aseprite` writes a sheet PNG and Aseprite-style JSON: frames with durations, a
`frameTags` entry per animation (with `repeat` for the one-shot attack), and the pivots as
Aseprite's own `meta.slices`. `--tiled` writes a Tiled tileset whose water tile animates.
`--frames` writes one PNG per frame, plus `pivots.json`.

```sh
pxart export alchemist.px --aseprite alchemist.json
pxart export harbor.px --tiled harbor.tsj
pxart export alchemist.px --frames frames
pxart sheet harbor.px --cols 6 --scale 6 -o harbor-tiles.png    # the tiles, labelled
```

## Aseprite

[`alchemist.png`](alchemist.png) + [`alchemist.json`](alchemist.json), from
[`alchemist.px`](alchemist.px) (shown at 4x): six walk frames, then five attack frames.

![the alchemist's exported sheet: walk/right, then attack/right](alchemist.x4.png)

```json
"frameTags": [
  {"name": "walk/right", "from": 0, "to": 5, "direction": "forward", "color": "#000000ff"},
  {"name": "attack/right", "from": 6, "to": 10, "direction": "forward", "color": "#000000ff", "repeat": "1"}
],
"slices": [{"name": "pivot", "color": "#0000ffff", "keys": [
  {"frame": 0, "bounds": {"x": 0, "y": 0, "w": 24, "h": 32}, "pivot": {"x": 12, "y": 31}}, ...
```

## Tiled

[`harbor.png`](harbor.png) + [`harbor.tsj`](harbor.tsj), from [`harbor.px`](harbor.px).
Tile ids follow the frames in file order, as `sheet` labels them here: 0-2 are
`cobble/a`-`cobble/c`, 3 is `planks`, 4-5 are the two `water` frames.

![the harbor tiles in id order, labelled](harbor-tiles.png)

The exported `harbor.png` itself, at 8x (three tiles to a row):

![the exported harbor tileset image](harbor.x8.png)

Tile 4 carries the water animation:

```json
{"id": 4, "animation": [{"tileid": 4, "duration": 450}, {"tileid": 5, "duration": 450}],
 "properties": [{"name": "pxart_anim", "type": "string", "value": "water"}]}
```

## One PNG per frame

[`frames/`](frames): `walk/right/0.png` ... `attack/right/4.png`
(![walk frame 0](frames/walk/right/0.png) ![attack frame 3](frames/attack/right/3.png)) and
[`frames/pivots.json`](frames/pivots.json): `{"walk/right/0": {"x": 12, "y": 31}, ...}`.
From [`export-frames.txt`](export-frames.txt):

```text
created frames/
wrote 11 PNGs under frames (frames/walk/right/0.png ... frames/attack/right/4.png) frames/pivots.json
```
