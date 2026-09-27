# Examples

Each folder holds the `.px` sources, the exact commands, and what they produce, all
committed. [`build.sh`](build.sh) regenerates every output from the sources, and
`tests/test_examples.py` rebuilds them and checks each is byte-identical, so these can't
drift from the tool.

| | Feature | Shows |
|---|---|---|
| <img src="01-format/barrel.preview.png" width="96"> | [01 · Format basics](01-format) | palette keys, a grid, `@palette` import; `render` |
| <img src="02-animation/walk.gif" width="160"> | [02 · Animation](02-animation) | `@anim`/`@frame`, ms, pivots; `anim` GIF, strip and readout; `onion --feet` |
| <img src="03-variants/panels.x4.png" width="200"> | [03 · Palette variants](03-variants) | `@variant`, `%VARIANT`, `palette --derive-from --keep-lit`, the palette listing |
| <img src="04-drawing/chest.preview.png" width="96"> | [04 · Drawing tools](04-drawing) | `rect` `poly` `shade` `line` `flood` `ellipse` `outline`, one step at a time |
| <img src="05-compose/dock-dusk.x4.png" width="200"> | [05 · Compose across packs](05-compose) | `compose --rekey --variant-map`, and the `E_KEY_CONFLICT` it starts from |
| <img src="06-scene/glade-dusk.x2.png" width="200"> | [06 · Scenes and maps](06-scene) | a layered `.map`, `scene --map`, base and `--variant dusk` |
| <img src="07-import/imported.png" width="200"> | [07 · Import](07-import) | `from-png --grid`, then `diff` proving it lossless |
| <img src="08-export/alchemist.x4.png" width="160"> | [08 · Export](08-export) | `export --aseprite`, `--tiled`, `--frames` (PNG + JSON) |
| <img src="09-check/fixed.png" width="200"> | [09 · Checking](09-check) | `check` on a broken file and its fix; `stats` |

Rebuild after changing a source (or pxart itself), then commit what changed:

```
examples/build.sh                 # in place
examples/build.sh /tmp/ex         # or into another directory
PYTHON=.venv/bin/python examples/build.sh
```

The art is from our own packs (the lighthouse keeper, the harbor market, wick) and our
own sprites (the SNES-scale hero and glade, the alchemist and her beetle), released with
this repo.
