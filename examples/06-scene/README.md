# 06 · Scenes and maps

[`rooms/glade.map`](rooms/glade.map) is a text tilemap: legend lines (`a
../tiles/field.px:grass_a`), then rows of legend characters, with `---` starting another
layer over the same legend. Its four layers are a 256-wide sky, a tree line, the field
tiles, and the trees (`T ../tiles/tree.px:tree+b`: `+b` stands the 32x64 tree on its cell,
and `+hb` mirrors it too). `scene --map` draws it; items after it (the hero and his shadow)
go on top. `--variant dusk` renders every tile and item in its palette's dusk.

```sh
pxart check rooms/glade.map
pxart scene --map rooms/glade.map --scale 2 -o glade.x2.png \
  tiles/field.px:shadow_s@150,154 sprites/hero.px:walk/left/0@147,127
pxart scene --map rooms/glade.map --scale 2 --variant dusk -o glade-dusk.x2.png \
  tiles/field.px:shadow_s@150,154 sprites/hero.px:walk/left/0@147,127
```

| base | `--variant dusk` |
|---|---|
| ![glade](glade.x2.png) | ![glade at dusk](glade-dusk.x2.png) |

The bottom seven rows of the field layer and of the tree layer:

```map
abfab1NNNNNN2baf        ................
bacaaWppppppEcab        ................
afbabWppppppEaba        .P............T.
bcaab3SS78SS4bfa        ................
abafbcabWEbasbab        T..............t
fbabacbaWEabcafb        ................
abcabfabWEbabacb        ................
```

From [`check.txt`](check.txt) and [`scene.txt`](scene.txt) (the trees on the edge
columns hang past the map, and scene says how much it cropped):

```text
ok   rooms/glade.map: map 16x14 tiles, 22 legend char(s), 4 layers
note: 308 px of the map fall outside the 256x224 scene (size from --map) and were cropped
```

1x:
[`glade.png`](glade.png), [`glade-dusk.png`](glade-dusk.png).
