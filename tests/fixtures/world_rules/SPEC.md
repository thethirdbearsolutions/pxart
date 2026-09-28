# The world rules

One spec for the rules a multi-screen world must pass (GAMES-286, decision 2: "the world rules are one spec, checked
in two places"; RGG ADR 0008, rule 4). Two implementations run it:

- **pxart**, at compile time: `pxart export --tiled world.src.json` and `pxart check world.src.json` run the rules on
  the Tiled files they are about to write (`world_rules` in `pxart.py`), and map each issue back to the source's
  `file:line:col`.
- **The harness**, at load time: `Sprites.world()` (GAMES-286 W3) runs them on Tiled-authored worlds, in-memory
  rooms, and anything else the compile never saw.

Both test suites run **every fixture in this folder**. A rule added to one side without the other fails a test.

## Where this lives, and why here

The design names no location. The fixtures are in pxart, under `tests/fixtures/world_rules/`, because pxart is the
repo both sides already share: RGG vendors `pxart.py` (`apps/games/manifest_generation/vendor/`), and W3 vendors or
reads this folder the same way. Nothing here is Python- or JS-specific: it's JSON and PNGs.

## The files

- `rules.json`: every rule's code, level (`error` or `warning`) and one-line meaning. A runner checks that the codes
  its implementation can emit are exactly these, and that each has a fixture.
- `<name>.json`: one fixture world. `valid-*` fixtures expect nothing.
- `tiles.tsj` (+ `tiles.png`) and `props.tsj` (+ `log.png`): the tilesets the fixtures share.

A fixture is an in-memory world, the shape `Sprites.world` accepts as data (decision 9):

```jsonc
{
  "about": "what it shows",
  "world": "world.world",            // the .world, a key of "files"
  "files": {                         // POSIX path -> parsed JSON: the .world and each .tmj
    "world.world": {"type": "world", "maps": [...]},
    "rooms/a.tmj": {"type": "map", ...}
  },
  "expect": [                        // exactly these issues, in any order
    {"level": "error", "code": "door-arrival", "room": "b", "name": "E", "cell": [2, 1]}
  ]
}
```

- Paths resolve as Tiled resolves them: a `.world`'s `fileName`, a door's `target` and a map's tileset `source`, each
  from the directory of the file that holds it. A path that isn't a key of `files` is read from disk, relative to
  this folder (the shared tilesets: `rooms/a.tmj`'s `"source": "../tiles.tsj"` is `tiles.tsj` here).
- An issue is compared on exactly `level`, `code`, `room`, `name` and `cell` (`null` where the rule has none). Messages
  are free text and not compared.

## Terms

- **Room:** a Tiled map. Its **id** is its file name without `.tmj` (`rooms/point.tmj` is `point`).
- **Placed rooms** are the `.world`'s `maps`, at their `x`, `y` in pixels. **Interiors** are rooms no `.world` entry
  names, found by following door targets from the placed rooms, transitively. The world is both.
- **Cell** `[x, y]`: a map cell, `x` in `0 .. width-1`, `y` in `0 .. height-1`, `tilewidth` x `tileheight` pixels.
- **An object's class:** its own `type` (or `class`, as Tiled 1.9 saved it); a tile object with none has its tile's
  class, as Tiled shows it.
- **Door:** an object whose class is `door`. Its **name** is its `name`; its properties: `target` (a file, the room it
  leads to), `entry` (the name of the door there), `trigger` (`touch`, the default, or `use`). A door's **rectangle**
  is `x, y, width, height`, except for a door that is a tile object (it has a `gid`): Tiled's `y` is then its bottom
  edge, so its rectangle is `x, y - height, width, height`. Its **cells** are those the rectangle overlaps with
  positive area (a door with zero width or height: the cell containing its top-left).
- **Start:** an object whose class is `start`. Its **cell** is the one under its feet: for a point, the cell
  containing `(x, y)`, where a point on a cell's bottom edge belongs to that cell: `[floor(x / tw), ceil(y / th) - 1]`
  (the compiler puts it at a cell's bottom centre). A tile-object start's feet are `(x + width / 2, y)` (y is its
  bottom); a rectangle's, `(x + width / 2, y + height)`; each placed in a cell the same way.
- **Door and start objects are never solid**, even when they are tile objects whose tile has collision shapes.
- **GID:** a tile layer's or tile object's global tile id. The top four bits are flip flags (`0x80000000`
  horizontal, `0x40000000` vertical, `0x20000000` diagonal, `0x10000000` hex rotation), masked off before looking the
  tile up: the tileset with the largest `firstgid` not above it, tile id `gid - firstgid`. A tileset that can't be
  loaded keeps its range: a GID that falls in it is unresolved (it blocks nothing), never the tileset before it's.
- **Collision shapes:** a tile's `objectgroup` objects, each counted as its bounding box (a polygon's by its points).
  Points and zero-area shapes block nothing. They are placed where the tile is drawn:
  - a tile-layer tile: its art's bottom-left on the cell's bottom-left (Tiled's alignment for tiles of any size);
  - a tile object: its art's bottom-left at the object's `x`, `y`, scaled by the object's `width` and `height` over
    the art's size;
  - flipped as the GID says: diagonal first (swap x with y and width with height), then horizontal
    (`x = artwidth - x - w`), then vertical (`y = artheight - y - h`).
- **Markers:** a tile object whose tile's class is `character_frame` is a marker (the `@` start, the gulls' `g`). The
  harness doesn't draw it and it **blocks nothing**, whatever its tile's shapes say. (A `character_frame` tile in a
  tile layer blocks nothing either.)
- **Solid cell:** a cell some collision shape overlaps with positive area, from any tile layer (group layers
  included) or any tile object that isn't a marker, a door or a start. A partial shape, like a crate's bottom strip,
  makes its whole cell solid. **Invisible layers count**: visibility is drawing, and a hidden collision layer is a
  common Tiled idiom.
- **Walkable cell:** a cell inside its room that isn't solid.
- **Beside a door** (the **arrival cells**): the walkable cells 4-adjacent to one of the door's cells, not themselves
  door cells, inside the room. Arrival lands on one of them, never on the door. **Which one is W4's:** the runtime
  must pick the arrival cell facing into the room (away from the door's wall). The rules don't pin that choice, so
  they over-approximate: reachability counts every arrival cell, and `door-arrival-split` warns when a door's
  arrival cells lie in separate regions (where the pick would matter).
- **Region:** cells joined by steps between 4-adjacent walkable cells of one room.
- **Touching a door:** standing in one of its walkable cells or one of its arrival cells.
- **Placed rooms never overlap:** two `.world` rectangles (`x, y`, and the map's `width * tilewidth` by
  `height * tileheight`) may share a side, never area (`room-overlap`).
- **Shared edge:** a placed room's side, a cell at a time: from a border cell, the point at the centre of the cell just
  outside the side, in world pixels (`room.x + (cx + 0.5) * tw`, ...). If a placed room other than this one contains
  that point (`x <= px < x + width * tw`, the same for y), that point's cell there is across the edge. Interiors have
  no edges.
- **Reachable:** from the start's cell, the cells a flood fill reaches, stepping:
  - to a 4-adjacent walkable cell in the same room;
  - across a shared edge, onto the cell across it, if walkable (the runtime's nudge out of a solid is not assumed);
  - through a door whose pair is valid (no `door-target`, `door-entry` or `door-pair` issue): from a cell touching it
    to any arrival cell of its partner.

## The rules

Each issue names the room (its id), a name (a door's name, the start object's name, an edge's side) and a cell, where
the rule has them.

| code | level | when | room, name, cell |
|---|---|---|---|
| `room-missing` | error | a `.world` entry's file can't be loaded | the file's id, -, - |
| `room-id-dup` | error | two rooms of the world have one id | the id, -, - |
| `tileset-missing` | error | a room's external tileset can't be loaded: that tileset's tiles block nothing (its GIDs are unresolved; the room's other tilesets still count) | the room, -, - |
| `tiled-unsupported` | error | the room uses a Tiled feature the rules don't read, rather than guess: a layer `offsetx`/`offsety` (`layer offset`), a nonzero `rotation` on a tile object, door or start (`rotation`), a tileset `tileoffset` (`tileoffset`), or a tileset `objectalignment` other than `unspecified`/`bottomleft` (`objectalignment`). One issue per room and feature. The compiler never writes any of them | the room, the feature, - |
| `room-overlap` | error | two placed rooms overlap with positive area | the later one in the `.world`, the earlier one's id, - |
| `start-count` | error | no start in the world: one issue. Two or more: one issue per start | -, -, - / its room, name, cell |
| `start-solid` | error | the one start's cell is solid, or outside its room | its room, name, cell |
| `door-name-dup` | error | a second door in a room has a name an earlier door (in file order) has; the later door is then skipped by every other rule | the room, the name, the later door's first cell |
| `door-trigger` | error | `trigger` is present and isn't `touch` or `use` | room, door, its first cell |
| `door-arrival` | error | the door has no arrival cells | room, door, first cell |
| `door-arrival-split` | warning | the door's arrival cells are in more than one region of its room | room, door, first cell |
| `door-target` | error | no `target`, or the target room can't be loaded | room, door, first cell |
| `door-entry` | error | no `entry`, or the target room has no door named `entry` | room, door, first cell |
| `door-pair` | error | the partner (the target's door named `entry`) doesn't have `target` resolving to this room's file and `entry` equal to this door's name. Doors pair up; one-way doors are a later form | room, door, first cell |
| `door-unreachable` | error | no cell touching the door is reachable. Checked only when there is exactly one start and its cell is walkable, and not for a door with a `door-arrival` issue | room, door, first cell |
| `edge-one-side` | warning | walking off a walkable border cell of a placed room lands on a solid cell across a shared edge. Reported from the walkable side, one issue per run of consecutive such cells along a side with the same room across | the walkable room, the side (`north`, `south`, `east`, `west`), the run's first cell |
| `room-unreachable` | warning | no cell of the room is reachable (same condition as `door-unreachable`) | the room, -, - |

A door's "first cell" is the first of its cells in row-major order (top-left).

The order issues come out in isn't part of the spec; fixtures compare them as a set.

## Not rules (and where they live)

- **Source errors** (a `.map`'s ragged rows or unknown chars, a `world.src.json` door naming a char its map doesn't
  draw, and so on) are the compiler's own: a source has no Tiled form yet. See `pxart export -h`.
- **Unsupported formats** are the loader's to reject (design, 02 · Formats), before these rules run, in the harness
  and in pxart's reader of compiled worlds (`pxart check W.world`, `pxart world`) alike: infinite maps, compressed
  or base64 layer data, non-orthogonal maps, a `.world` that places its maps by `patterns` (list them in `maps`),
  and Tiled's XML files (a `.tmx` map, a `.tsx` tileset: save or export them as JSON, `.tmj` and `.tsj`). The
  features within a supported map that the rules can't place are `tiled-unsupported`, above; everything else in a
  map (parallax, tints, image layers, text objects) doesn't bear on the rules and is ignored.

## Reserved (ADR 0010)

Nothing is reserved here beyond what the design names: one-way doors (a later `"->"` form in `world.src.json`) would
change `door-pair`; runtime doors and terraforming (GAMES-315) and generated rooms (GAMES-317) are checked by these
same rules, run on their Tiled-shaped data.
