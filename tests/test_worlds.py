"""GAMES-327 (W2 of GAMES-286): worlds. export --tiled compiles world.src.json and .map rooms to Tiled .world and
.tmj; check runs the same compile; the world rules are one spec (tests/fixtures/world_rules/SPEC.md) with shared
fixtures, run here and by the harness.

Redundant on purpose: each rule and each row of the design's "what a .map compiles to" table is pinned from more
than one side."""
import json
import math
import pathlib
import re
import shutil
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
RULES = FIXTURES / "world_rules"
LIGHTHOUSE = FIXTURES / "lighthouse"
EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"
KEYS = ("level", "code", "room", "name", "cell")


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def run_err(*argv):
    with pytest.raises(SystemExit) as e:
        pxart.main([str(a) for a in argv])
    assert not isinstance(e.value.code, int) or e.value.code != 0
    return str(e.value.code)


def load(p):
    return json.loads(pathlib.Path(p).read_text())


# ================================================================ the world rules: spec, fixtures, runner

def fixture_files():
    return sorted(p for p in RULES.glob("*.json") if p.name != "rules.json")


FIXTURE_NAMES = [p.stem for p in fixture_files()]


def as_dicts(issues):
    return [dict(zip(KEYS, i.key())) for i in issues]


def canon(ds):
    return sorted(json.dumps(d, sort_keys=True) for d in ds)


def fixture_issues(f):
    return pxart.world_rules_files(f["files"], f["world"], str(RULES))


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_world_rules_fixture(name):
    f = load(RULES / f"{name}.json")
    assert canon(as_dicts(fixture_issues(f))) == canon(f["expect"]), name


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_world_rules_fixture_shape(name):
    f = load(RULES / f"{name}.json")
    assert set(f) == {"about", "world", "files", "expect"}, name
    assert f["about"].strip() and f["world"] in f["files"], name
    assert f["files"][f["world"]]["type"] == "world", name
    for e in f["expect"]:
        assert set(e) == set(KEYS), (name, e)
    if name.startswith("valid-"):
        assert f["expect"] == [], name
    else:
        assert f["expect"], name


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_world_rules_fixture_levels_match_rules_json(name):
    rules = load(RULES / "rules.json")["rules"]
    for e in load(RULES / f"{name}.json")["expect"]:
        assert rules[e["code"]]["level"] == e["level"], (name, e)


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_world_rules_fixture_same_from_files_on_disk(name, tmp_path):
    # decision 4: an in-memory world loads exactly like the same world from files
    f = load(RULES / f"{name}.json")
    root = tmp_path / "w"
    for rel, data in f["files"].items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))
    for shared in ("tiles.tsj", "tiles.png", "props.tsj", "log.png"):
        shutil.copy(RULES / shared, root / shared)
    got = pxart.world_rules(str(root / f["world"]), pxart.read_json)
    assert canon(as_dicts(got)) == canon(f["expect"]), name


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_world_rules_fixture_order_is_stable(name):
    f = load(RULES / f"{name}.json")
    assert [i.key() for i in fixture_issues(f)] == [i.key() for i in fixture_issues(f)]


def test_rules_json_matches_the_implementation():
    # ADR 0008: a rule added on one side without the other fails a test
    rules = load(RULES / "rules.json")
    assert rules["spec"] == "SPEC.md" and (RULES / "SPEC.md").is_file()
    assert {k: v["level"] for k, v in rules["rules"].items()} == pxart.WORLD_RULES
    for v in rules["rules"].values():
        assert v["meaning"].strip() and v["level"] in ("error", "warning")


def test_every_rule_has_a_fixture():
    seen = {e["code"] for p in fixture_files() for e in load(p)["expect"]}
    assert seen == set(pxart.WORLD_RULES)


def test_every_rule_is_in_the_spec_table():
    spec = (RULES / "SPEC.md").read_text()
    for code, level in pxart.WORLD_RULES.items():
        assert re.search(rf"^\| `{re.escape(code)}` \| {level} \|", spec, re.M), code


def test_spec_names_where_it_lives_and_both_runners():
    spec = " ".join((RULES / "SPEC.md").read_text().split())
    assert "tests/fixtures/world_rules/" in spec and "Sprites.world()" in spec and "world_rules" in spec
    assert "rules.json" in spec and "The design names no location" in spec


def test_there_are_valid_fixtures_and_broken_ones():
    assert sum(n.startswith("valid-") for n in FIXTURE_NAMES) >= 5
    assert sum(not n.startswith("valid-") for n in FIXTURE_NAMES) >= 15


def test_shared_tilesets_are_plain_tiled():
    t = load(RULES / "tiles.tsj")
    assert t["type"] == "tileset" and t["image"] == "tiles.png" and Image.open(RULES / "tiles.png").size == (80, 16)
    p = load(RULES / "props.tsj")
    assert p["columns"] == 0 and Image.open(RULES / "log.png").size == (32, 16)


def test_rule_issue_levels_come_from_the_table():
    for code, level in pxart.WORLD_RULES.items():
        assert pxart.RuleIssue(code, "a", None, None, "m").level == level


def test_world_rules_missing_world_file_is_just_no_start():
    got = as_dicts(pxart.world_rules_files({}, "nope.world"))
    assert got == [{"level": "error", "code": "start-count", "room": None, "name": None, "cell": None}]


def fixture(name):
    return load(RULES / f"{name}.json")


def mutated(name, fn):
    f = json.loads(json.dumps(fixture(name)))
    fn(f["files"])
    return as_dicts(pxart.world_rules_files(f["files"], f["world"], str(RULES)))


def objects(files, room):
    return next(l for l in files[room]["layers"] if l["type"] == "objectgroup")["objects"]


def test_rules_a_door_moved_into_the_wall_row_still_arrives_beside():
    def move(files):
        d = next(o for o in objects(files, "rooms/a.tmj") if o["name"] == "D")
        d["y"] = 48  # row 3 of FLOORS rooms is floor too; still fine
    assert mutated("valid-two-rooms-and-a-door", move) == []


def test_rules_trigger_touch_is_fine_too():
    def touch(files):
        for room in ("rooms/a.tmj", "rooms/b.tmj"):
            for o in objects(files, room):
                for p in o.get("properties", []):
                    if p["name"] == "trigger":
                        p["value"] = "touch"
    assert mutated("valid-use-trigger-and-tiled-1-9-class", touch) == []


def test_rules_empty_trigger_is_an_error():
    def empty(files):
        for o in objects(files, "rooms/a.tmj"):
            for p in o.get("properties", []):
                if p["name"] == "trigger":
                    p["value"] = ""
    assert [d["code"] for d in mutated("valid-use-trigger-and-tiled-1-9-class", empty)] == ["door-trigger"]


def test_rules_vertical_flip_matters_for_a_tile_layer_half():
    # the half tile's solid left half, flipped left-right, is still over its own cell: still solid
    def flip(files):
        layer = files["rooms/a.tmj"]["layers"][0]
        layer["data"] = [g | pxart.GID_H if g == 5 else g for g in layer["data"]]
    got = mutated("start-on-a-half-tile", flip)
    assert [d["code"] for d in got] == ["start-solid"]


def test_rules_diagonal_flip_swaps_the_log_shape():
    # the log's left half (x 0..16 of 32) transposed is y 0..16 of 16 tall, x 0..16: still the left cell
    def diag(files):
        o = next(o for o in objects(files, "rooms/a.tmj") if o["name"] == "log")
        o["gid"] = o["gid"] & ~pxart.GID_FLAGS | pxart.GID_D
    got = mutated("valid-log-flipped-away", diag)
    assert [d["code"] for d in got] == ["start-solid"]


def test_rules_a_scaled_tile_object_scales_its_shape():
    # the log drawn at 64x16 (twice as wide): its solid half is 32 px, cells 1 and 2
    def wide(files):
        o = next(o for o in objects(files, "rooms/a.tmj") if o["name"] == "log")
        o["gid"] = o["gid"] & ~pxart.GID_FLAGS
        o["width"] = 64
        o["x"] = 0
    got = mutated("valid-log-flipped-away", wide)
    assert [d["code"] for d in got] == ["start-solid"]


def test_rules_group_layers_count():
    def group(files):
        room = files["rooms/a.tmj"]
        room["layers"] = [{"id": 9, "name": "g", "type": "group", "layers": room["layers"]}]
    assert mutated("valid-two-rooms-and-a-door", group) == []
    assert [d["code"] for d in mutated("start-in-a-wall", group)] == ["start-solid"]


def test_rules_embedded_tileset_works_like_an_external_one():
    def embed(files):
        for room in files.values():
            if room.get("type") == "map":
                room["tilesets"] = [dict(load(RULES / "tiles.tsj"), firstgid=1)]
    assert mutated("valid-two-rooms-and-a-door", embed) == []
    assert [d["code"] for d in mutated("start-in-a-wall", embed)] == ["start-solid"]


def test_rules_door_zero_size_uses_its_cell():
    def point(files):
        d = next(o for o in objects(files, "rooms/a.tmj") if o["name"] == "D")
        d["width"] = d["height"] = 0
    assert mutated("valid-two-rooms-and-a-door", point) == []


def test_rules_door_target_resolves_from_the_room_dir():
    def elsewhere(files):
        files["other/b.tmj"] = files.pop("rooms/b.tmj")
        files["world.world"]["maps"][1]["fileName"] = "other/b.tmj"
        for o in objects(files, "rooms/a.tmj"):
            for p in o.get("properties", []):
                if p["name"] == "target":
                    p["value"] = "../other/b.tmj"
        for o in objects(files, "other/b.tmj"):
            for p in o.get("properties", []):
                if p["name"] == "target":
                    p["value"] = "../rooms/a.tmj"
    assert mutated("valid-two-rooms-and-a-door", elsewhere) == []


def test_rules_interior_found_through_a_chain_of_doors():
    f = json.loads(json.dumps(fixture("valid-interior")))
    files = f["files"]
    inner = json.loads(json.dumps(files["rooms/in.tmj"]))
    objects(files, "rooms/in.tmj").append({"id": 9, "name": "U", "type": "door", "x": 32, "y": 16, "width": 16,
                                           "height": 16, "properties": [
                                               {"name": "entry", "type": "string", "value": "u"},
                                               {"name": "target", "type": "file", "value": "deep.tmj"}]})
    objects({"x": inner}, "x")[:] = [{"id": 1, "name": "u", "type": "door", "x": 32, "y": 32, "width": 16,
                                      "height": 16, "properties": [
                                          {"name": "entry", "type": "string", "value": "U"},
                                          {"name": "target", "type": "file", "value": "in.tmj"}]}]
    files["rooms/deep.tmj"] = inner
    assert as_dicts(pxart.world_rules_files(files, "world.world", str(RULES))) == []
    objects(files, "rooms/deep.tmj")[0]["properties"][1]["value"] = "out.tmj"  # u now leads out, where no 'U' is
    got = as_dicts(pxart.world_rules_files(files, "world.world", str(RULES)))
    assert [(d["code"], d["room"], d["name"]) for d in got if d["level"] == "error"] == [
        ("door-pair", "in", "U"), ("door-entry", "deep", "u"), ("door-unreachable", "deep", "u")]
    assert [(d["code"], d["room"]) for d in got if d["level"] == "warning"] == [("room-unreachable", "deep")]


def test_rules_edge_warning_both_rooms_walled_is_quiet():
    def wall(files):
        layer = files["rooms/b.tmj"]["layers"][0]
        layer["data"] = [2 if i % 5 == 0 else g for i, g in enumerate(layer["data"])]
        la = files["rooms/a.tmj"]["layers"][0]
        la["data"] = [2 if i % 5 == 4 else g for i, g in enumerate(la["data"])]
    assert [d["code"] for d in mutated("edge-walkable-one-side", wall)] == ["room-unreachable"]  # and no edge


def test_rules_edge_warning_is_one_per_stretch():
    def split(files):
        files["rooms/b.tmj"]["layers"][0]["data"] = [
            2, 1, 1, 1, 1,
            1, 1, 1, 1, 1,
            2, 1, 1, 1, 1,
            2, 1, 1, 1, 1]
    got = mutated("edge-walkable-one-side", split)
    assert [(d["code"], d["name"], d["cell"]) for d in got] == [("edge-one-side", "east", [4, 0]),
                                                                ("edge-one-side", "east", [4, 2])]


def test_rules_edge_warning_other_sides():
    def south(files):
        files["world.world"]["maps"][1].update(x=0, y=64)
        files["rooms/b.tmj"]["layers"][0]["data"] = [2, 2, 1, 1, 1] + [1] * 15
    got = mutated("edge-walkable-one-side", south)
    assert [(d["room"], d["name"], d["cell"]) for d in got] == [("a", "south", [0, 3])]


def test_rules_start_count_three():
    def third(files):
        objects(files, "rooms/b.tmj").append({"id": 7, "name": "start", "type": "start", "point": True,
                                              "x": 8, "y": 16, "width": 0, "height": 0})
    got = mutated("start-two", third)
    assert [d["code"] for d in got] == ["start-count"] * 3


def test_rules_door_unreachable_not_reported_when_the_start_is_bad():
    def bad_start(files):
        s = next(o for o in objects(files, "rooms/a.tmj") if o["type"] == "start")
        s["x"], s["y"] = 8, 16  # cell 0,0: a wall
    got = mutated("door-unreachable", bad_start)
    assert [d["code"] for d in got] == ["start-solid"]


# ================================================================ cell_hash and legend variant lists

def test_cell_hash_pinned_values():
    # pinned: the compiler, scene and any other port must pick the same tile
    assert pxart.cell_hash("point", 0, 0) == pxart.cell_hash("point", 0, 0)
    got = [pxart.cell_hash("point", x, y) for x, y in ((0, 0), (1, 0), (0, 1), (15, 11))]
    assert got == PINNED_POINT
    assert pxart.cell_hash("", 0, 0) == PINNED_EMPTY


PINNED_POINT = [1573464345, 3772951790, 2975222525, 2704959150]
PINNED_EMPTY = 4261097152


def fnv(room):
    h = 2166136261
    for b in room.encode():
        h = ((h ^ b) * 16777619) % 2 ** 32
    return h


def js_imul(a, b):
    return (a * b) % 2 ** 32


def reference_hash(room, x, y):
    """cell_hash, written out again the long way (as sprites.js's groundTilePath mixes, with the room folded in)."""
    h = fnv(room) ^ js_imul(x, 73856093) ^ js_imul(y, 19349663)
    h = js_imul(h ^ (h >> 13), 0x5BD1E995)
    return (h ^ (h >> 15)) % 2 ** 32


@pytest.mark.parametrize("room", ["point", "shore", "tower", "", "café", "a-b_c"])
def test_cell_hash_matches_its_reference(room):
    for x in range(0, 40, 3):
        for y in range(0, 30, 4):
            assert pxart.cell_hash(room, x, y) == reference_hash(room, x, y)


def test_cell_hash_is_32_bit_and_depends_on_every_part():
    vals = {pxart.cell_hash(r, x, y) for r in ("a", "b") for x in range(8) for y in range(8)}
    assert all(0 <= v < 2 ** 32 for v in vals) and len(vals) == 128


def test_cell_hash_matches_the_kit_mix_for_the_room_part():
    # sprites.js groundTilePath with the room's FNV in: for x=y=0 the mix sees the FNV alone
    h = fnv("point")
    h = js_imul(h ^ (h >> 13), 0x5BD1E995)
    assert pxart.cell_hash("point", 0, 0) == (h ^ (h >> 15)) % 2 ** 32


def test_pick_variant_single_is_itself():
    assert pxart.pick_variant("a.png", "r", 3, 4) == "a.png"


def test_pick_variant_uses_the_hash_mod_len():
    opts = ("a.png", "b.png", "c.png")
    for x in range(6):
        for y in range(6):
            assert pxart.pick_variant(opts, "r", x, y) == opts[pxart.cell_hash("r", x, y) % 3]


def test_map_room_is_the_stem():
    assert pxart.map_room("rooms/point.map") == "point" and pxart.map_room("x/y/tower.map") == "tower"


@pytest.mark.parametrize("rest,want", [
    ("a.png b.png", ["a.png", "b.png"]),
    ("a.png  b.png\tc.png", ["a.png", "b.png", "c.png"]),
    ("t.px:grass_a t.px:grass_b", ["t.px:grass_a", "t.px:grass_b"]),
    ("t.px:grass_a%night t.px:grass_b+h", ["t.px:grass_a%night", "t.px:grass_b+h"]),
    ('"my tiles/a.png" b.png', ["my tiles/a.png", "b.png"]),
    ("../x/a.png ../x/b.png+hb", ["../x/a.png", "../x/b.png+hb"]),
])
def test_variant_list_parses(rest, want):
    assert pxart.variant_list(rest) == want


@pytest.mark.parametrize("rest", ["a.png", "../png/trees and bushes/bush.png", "a.png and", "a.gif b.gif",
                                  '"a.png', "a.png b", "x y"])
def test_variant_list_not_a_list(rest):
    assert pxart.variant_list(rest) is None


def mk_tiles(tmp_path):
    for name, c in (("a", (255, 0, 0)), ("b", (0, 255, 0)), ("c", (0, 0, 255)), ("d", (9, 9, 9))):
        Image.new("RGBA", (2, 2), c + (255,)).save(tmp_path / f"{name}.png")


def test_parse_map_variant_list_legend(tmp_path):
    mk_tiles(tmp_path)
    m = tmp_path / "room.map"
    m.write_text("v a.png b.png c.png\nd d.png\n\nvvd\n")
    legend, layers, notes, where = pxart.parse_map(m)
    assert legend["v"] == tuple(str(tmp_path / n) for n in ("a.png", "b.png", "c.png"))
    assert legend["d"] == str(tmp_path / "d.png")
    assert where["v"] == (1, ["a.png", "b.png", "c.png"]) and where["d"] == (2, "d.png")


def test_legend_entries_flatten_lists(tmp_path):
    mk_tiles(tmp_path)
    m = tmp_path / "room.map"
    m.write_text("v a.png b.png\nd d.png\n\nvd\n")
    legend, _, _, where = pxart.parse_map(m)
    assert [(ch, pathlib.Path(a).name, w) for ch, a, w in pxart.legend_entries(legend, where)] == [
        ("v", "a.png", "a.png"), ("v", "b.png", "b.png"), ("d", "d.png", "d.png")]


def test_read_map_picks_by_cell_hash(tmp_path):
    mk_tiles(tmp_path)
    m = tmp_path / "field.map"
    m.write_text("v a.png b.png c.png\n\n" + "v" * 12 + "\n" + "v" * 12 + "\n")
    placed, size = pxart.read_map(m, (2, 2))
    assert size == (24, 4)
    for arg, x, y in placed:
        cx, cy = x // 2, y // 2
        want = ("a.png", "b.png", "c.png")[pxart.cell_hash("field", cx, cy) % 3]
        assert pathlib.Path(arg).name == want
    assert len({pathlib.Path(a).name for a, _, _ in placed}) > 1  # 24 cells: it does vary


def test_scene_map_variant_list_draws_the_picks(tmp_path):
    mk_tiles(tmp_path)
    m = tmp_path / "field.map"
    m.write_text("v a.png b.png c.png\n\n" + "v" * 10 + "\n" + "v" * 10 + "\n")
    assert run("scene", "--map", m, "--tile", "2", "--scale", "1", "-o", tmp_path / "s.png") == 0
    img = Image.open(tmp_path / "s.png").convert("RGBA")
    colors = {"a.png": (255, 0, 0), "b.png": (0, 255, 0), "c.png": (0, 0, 255)}
    for cy in range(2):
        for cx in range(10):
            want = ("a.png", "b.png", "c.png")[pxart.cell_hash("field", cx, cy) % 3]
            assert img.getpixel((cx * 2, cy * 2))[:3] == colors[want]


def test_scene_map_variant_pick_depends_on_the_room_name(tmp_path):
    mk_tiles(tmp_path)
    body = "v a.png b.png c.png\n\n" + "v" * 16 + "\n"
    (tmp_path / "one.map").write_text(body)
    (tmp_path / "two.map").write_text(body)
    for n in ("one", "two"):
        assert run("scene", "--map", tmp_path / f"{n}.map", "--tile", "2", "--scale", "1", "-o", tmp_path / f"{n}.png") == 0
    a, b = (Image.open(tmp_path / f"{n}.png").convert("RGBA").tobytes() for n in ("one", "two"))
    assert a != b


def test_compose_map_variant_list_matches_scene(tmp_path):
    for name, c in (("a", "#ff0000"), ("b", "#00ff00"), ("c", "#0000ff")):
        (tmp_path / f"{name}.px").write_text(f"{name} {c}\n\n{name}{name}\n{name}{name}\n")
    m = tmp_path / "room.map"
    m.write_text("v a.px b.px c.px\n\nvvvvvv\nvvvvvv\n")
    assert run("scene", "--map", m, "--tile", "2", "--bg", "transparent", "--scale", "1", "-o", tmp_path / "s.png") == 0
    assert run("compose", "--map", m, "--tile", "2", "-o", tmp_path / "room.px") == 0
    assert run("render", tmp_path / "room.px", "--plain", "-o", tmp_path / "c.png") == 0
    assert Image.open(tmp_path / "s.png").convert("RGBA").tobytes() == \
        Image.open(tmp_path / "c.png").convert("RGBA").tobytes()


def test_check_map_with_variant_list_is_ok(tmp_path, capsys):
    mk_tiles(tmp_path)
    m = tmp_path / "room.map"
    m.write_text("v a.png b.png c.png\n\nvv\n")
    assert run("check", m) == 0
    assert "ok   " in capsys.readouterr().out


def test_check_map_variant_list_missing_file_names_it(tmp_path, capsys):
    mk_tiles(tmp_path)
    m = tmp_path / "room.map"
    m.write_text("v a.png gone.png\n\nvv\n")
    assert run("check", m) == 1
    out = capsys.readouterr().out
    assert "gone.png" in out and ":1" in out


def test_variant_list_with_flips_and_bottom_anchor(tmp_path):
    Image.new("RGBA", (2, 4), (255, 0, 0, 255)).save(tmp_path / "tall.png")
    Image.new("RGBA", (2, 4), (0, 255, 0, 255)).save(tmp_path / "tall2.png")
    m = tmp_path / "room.map"
    m.write_text("T tall.png+b tall2.png+hb\n\n....\n.TT.\n")
    placed, _ = pxart.read_map(m, (2, 2))
    assert all(pxart.split_flip(a)[1] in ("b", "hb") for a, _, _ in placed)
    assert run("scene", "--map", m, "--tile", "2", "--scale", "1", "-o", tmp_path / "s.png") == 0


def test_help_documents_variant_lists():
    doc = " ".join(pxart.__doc__.split())
    assert "'1 sand.png sand2.png sand3.png'" in doc and "hash of (room, x, y)" in doc
    assert "scene, compose --map and export --tiled all pick the same one" in doc


# ================================================================ a small pack, W1-shaped, to compile against

GROUND = {  # pack path: (color, collision rect or None)
    "world/floor.png": ((236, 212, 158), None),
    "world/floor2.png": ((226, 200, 140), None),
    "world/floor3.png": ((216, 190, 130), None),
    "world/wall.png": ((90, 83, 83), [0, 0, 16, 16]),
    "world/water.png": ((58, 124, 165), [0, 0, 16, 16]),
}
PROPS = {  # pack path: (size, color, class, collision)
    "props/crate.png": ((16, 16), (160, 110, 60), "object", [0, 12, 16, 4]),
    "props/tree.png": ((16, 32), (40, 140, 60), "object", [4, 24, 8, 8]),
    "props/rug.png": ((32, 16), (170, 60, 60), "decor", None),
    "props/hero.png": ((16, 16), (60, 60, 200), "character_frame", None),
    "props/pebble.png": ((8, 8), (120, 120, 120), "decor", None),
    "props/lamp.png": ((16, 16), (250, 230, 90), "decor", None),
}


def art(size, color):
    """Solid art with an asymmetric mark (a dark top-left pixel, a light bottom-right one), so flips show."""
    img = Image.new("RGBA", size, color + (255,))
    img.putpixel((0, 0), (0, 0, 0, 255))
    img.putpixel((size[0] - 1, size[1] - 1), (255, 255, 255, 255))
    if size[0] > 2:
        img.putpixel((1, 0), (0, 0, 0, 255))
    return img


def collision(rect):
    x, y, w, h = rect
    return {"draworder": "index", "id": 2, "name": "", "opacity": 1, "type": "objectgroup", "visible": True, "x": 0,
            "y": 0, "objects": [{"id": 1, "name": "", "type": "", "x": x, "y": y, "width": w, "height": h,
                                 "rotation": 0, "visible": True}]}


def make_pack(root, slug="mini", ground_order=None):
    pack = root / slug
    (pack / "tiled").mkdir(parents=True, exist_ok=True)
    order = ground_order or list(GROUND)
    for p, (c, _) in GROUND.items():
        (pack / p).parent.mkdir(parents=True, exist_ok=True)
        art((16, 16), c).save(pack / p)
    cols = math.ceil(math.sqrt(len(order)))
    rows = math.ceil(len(order) / cols)
    sheet = Image.new("RGBA", (cols * 16, rows * 16))
    tiles = []
    for i, p in enumerate(order):
        sheet.paste(Image.open(pack / p), ((i % cols) * 16, (i // cols) * 16))
        t = {"id": i, "type": "tile_fill", "properties": [{"name": "png", "type": "string", "value": p}]}
        if GROUND[p][1]:
            t["objectgroup"] = collision(GROUND[p][1])
        tiles.append(t)
    sheet.save(pack / "tiled" / f"{slug}-ground.png")
    (pack / "tiled" / f"{slug}-ground.tsj").write_text(json.dumps({
        "type": "tileset", "version": "1.10", "name": f"{slug}-ground",
        "properties": [{"name": "nextid", "type": "int", "value": len(order)}], "tilewidth": 16, "tileheight": 16,
        "tilecount": cols * rows, "columns": cols, "margin": 0, "spacing": 0, "image": f"{slug}-ground.png",
        "imagewidth": cols * 16, "imageheight": rows * 16, "tiles": tiles}, indent=1))
    ptiles = []
    for i, (p, (size, c, cls, rect)) in enumerate(PROPS.items()):
        (pack / p).parent.mkdir(parents=True, exist_ok=True)
        art(size, c).save(pack / p)
        t = {"id": i, "type": cls, "image": f"../{p}", "imagewidth": size[0], "imageheight": size[1],
             "properties": [{"name": "png", "type": "string", "value": p}]}
        if rect:
            t["objectgroup"] = collision(rect)
        ptiles.append(t)
    (pack / "tiled" / f"{slug}-props.tsj").write_text(json.dumps({
        "type": "tileset", "version": "1.10", "name": f"{slug}-props",
        "properties": [{"name": "nextid", "type": "int", "value": len(PROPS)}], "tilewidth": 32, "tileheight": 32,
        "tilecount": len(PROPS), "columns": 0, "margin": 0, "spacing": 0,
        "grid": {"orientation": "orthogonal", "width": 1, "height": 1}, "tiles": ptiles}, indent=1))
    return pack


P = "../../assets/mini"
LEGEND = f"""1 {P}/world/floor.png
V {P}/world/floor.png {P}/world/floor2.png {P}/world/floor3.png
W {P}/world/wall.png
~ {P}/world/water.png
c {P}/props/crate.png+b
T {P}/props/tree.png+b
t {P}/props/tree.png+hb
R {P}/props/rug.png+b
@ {P}/props/hero.png+b
p {P}/props/pebble.png
l {P}/props/lamp.png
L {P}/props/lamp.png+h
D {P}/world/floor.png
d {P}/world/wall.png
"""


def room_text(ground, props=None, legend=LEGEND, comment="# a room"):
    body = f"{comment}\n{legend}\n" + "\n".join(ground) + "\n"
    if props:
        body += "---\n" + "\n".join(props) + "\n"
    return body


def game(tmp_path, rooms, src=None, pack=True):
    """tmp/assets/mini (the pack) and tmp/game/{world.src.json, rooms/*.map}: the world source's path."""
    if pack:
        make_pack(tmp_path / "assets")
    g = tmp_path / "game"
    (g / "rooms").mkdir(parents=True, exist_ok=True)
    for name, text in rooms.items():
        (g / "rooms" / f"{name}.map").write_text(text)
    if src is not None:
        (g / "world.src.json").write_text(src if isinstance(src, str) else json.dumps(src, indent=1))
    return g / "world.src.json"


BOX = ["WWWWWW", "W1111W", "W1111W", "W1111W", "WWWWWW"]
OPEN5 = ["111111", "111111", "111111", "111111", "111111"]


def two_rooms(tmp_path, a_props=None, b_props=None, src=None, a=None, b=None, pack=True):
    a_props = a_props or ["......", "......", ".@....", "......", "......"]
    b_props = b_props or ["......"] * 5
    a = a or ["111111", "111111", "1111D1", "111111", "111111"]
    b = b or ["WWWWWW", "W1111W", "W1111W", "W1111W", "WWdWWW"]
    src = src or {"layout": ["a"], "start": {"room": "a", "at": "@"}, "doors": [["a D", "b d"]]}
    return game(tmp_path, {"a": room_text(a, a_props), "b": room_text(b, b_props)}, src, pack=pack)


def compile_ok(src, *extra, capsys=None):
    code = run("export", src, "--tiled", *extra)
    assert code == 0
    return src.parent


def tmj(src_dir, name):
    return load(src_dir / "rooms" / f"{name}.tmj")


def objs(t, layer=None):
    return [o for l in t["layers"] if l["type"] == "objectgroup" and (layer is None or l["name"] == layer)
            for o in l["objects"]]


def gid_png(room_path, gid):
    """The pack path a GID in a .tmj resolves to (via its tilesets' png properties), with its flip flags."""
    t = load(room_path)
    g = gid & ~pxart.GID_FLAGS
    first, source = max(((ts["firstgid"], ts["source"]) for ts in t["tilesets"] if ts["firstgid"] <= g))
    tsj = load(room_path.parent / source)
    tile = next(x for x in tsj["tiles"] if x["id"] == g - first)
    return next(p["value"] for p in tile["properties"] if p["name"] == "png"), gid & pxart.GID_FLAGS


# ================================================================ the compiler: what a .map compiles to

def test_compile_writes_tmj_per_room_and_the_world(tmp_path, capsys):
    src = two_rooms(tmp_path)
    assert run("export", src, "--tiled") == 0
    out = capsys.readouterr().out
    g = src.parent
    assert (g / "rooms" / "a.tmj").is_file() and (g / "rooms" / "b.tmj").is_file() and (g / "world.world").is_file()
    assert f"wrote {g / 'rooms' / 'a.tmj'}: 6x5, " in out and "interior" in out
    assert f"wrote {g / 'world.world'}: 1 room placed, interior b, start in a" in out


def test_compile_output_says_kept_and_new_ids(tmp_path, capsys):
    src = two_rooms(tmp_path)
    run("export", src, "--tiled")
    first = capsys.readouterr().out
    assert "(0 kept ids, 3 new)" in first  # a: '@', the door, the start
    run("export", src, "--tiled")
    again = capsys.readouterr().out
    assert "(3 kept ids, 0 new)" in again


def test_compile_tiled_before_the_source_works(tmp_path):
    src = two_rooms(tmp_path)
    assert run("export", "--tiled", src) == 0
    assert (src.parent / "world.world").is_file()


def test_compile_map_header(tmp_path):
    src = two_rooms(tmp_path)
    t = tmj(compile_ok(src), "a")
    assert t["type"] == "map" and t["version"] == "1.10" and t["orientation"] == "orthogonal"
    assert t["renderorder"] == "right-down" and t["infinite"] is False
    assert (t["width"], t["height"], t["tilewidth"], t["tileheight"]) == (6, 5, 16, 16)
    assert t["properties"] == [{"name": "source", "type": "file", "value": "a.map"}]
    assert t["nextlayerid"] == max(l["id"] for l in t["layers"]) + 1


def test_compile_tilesets_point_at_the_pack(tmp_path):
    src = two_rooms(tmp_path)
    t = tmj(compile_ok(src), "a")
    sources = [ts["source"] for ts in t["tilesets"]]
    assert sources == ["../../assets/mini/tiled/mini-ground.tsj", "../../assets/mini/tiled/mini-props.tsj"]
    assert t["tilesets"][0]["firstgid"] == 1
    ground = load(tmp_path / "assets/mini/tiled/mini-ground.tsj")
    assert t["tilesets"][1]["firstgid"] == 1 + ground["tilecount"]


def test_compile_one_tile_cells_are_a_tile_layer(tmp_path):
    src = two_rooms(tmp_path)
    t = tmj(compile_ok(src), "b")
    layer = next(l for l in t["layers"] if l["type"] == "tilelayer")
    assert layer["name"] == "layer 1" and (layer["width"], layer["height"]) == (6, 5)
    room = src.parent / "rooms" / "b.tmj"
    pngs = [gid_png(room, g)[0] for g in layer["data"]]
    assert pngs[:6] == ["world/wall.png"] * 6 and pngs[7] == "world/floor.png"
    assert pngs[6 * 4 + 2] == "world/wall.png"  # the door 'd' is a wall tile


def test_compile_gids_are_firstgid_plus_the_stable_tile_id(tmp_path):
    src = two_rooms(tmp_path)
    t = tmj(compile_ok(src), "b")
    ground = load(tmp_path / "assets/mini/tiled/mini-ground.tsj")
    wall_id = next(x["id"] for x in ground["tiles"] if x["properties"][0]["value"] == "world/wall.png")
    assert next(l for l in t["layers"] if l["type"] == "tilelayer")["data"][0] == 1 + wall_id


def test_compile_gids_follow_the_tile_ids_not_the_order(tmp_path):
    # a tileset whose ids are in another order: the GID follows the id, never a position
    make_pack(tmp_path / "assets", ground_order=["world/water.png", "world/wall.png", "world/floor3.png",
                                                  "world/floor2.png", "world/floor.png"])
    src = two_rooms(tmp_path, pack=False)
    t = tmj(compile_ok(src), "b")
    data = next(l for l in t["layers"] if l["type"] == "tilelayer")["data"]
    assert data[0] == 2 and data[7] == 5


def test_gids_follow_a_regenerated_tileset(tmp_path):
    # compile, then the pack's tileset is regenerated with other ids: a recompile follows the ids
    src = two_rooms(tmp_path)
    before = next(l for l in tmj(compile_ok(src), "b")["layers"] if l["type"] == "tilelayer")["data"]
    make_pack(tmp_path / "assets", ground_order=["world/water.png", "world/wall.png", "world/floor3.png",
                                                  "world/floor2.png", "world/floor.png"])
    after = next(l for l in tmj(compile_ok(src), "b")["layers"] if l["type"] == "tilelayer")["data"]
    assert before[0] == 4 and after[0] == 2 and before[7] == 1 and after[7] == 5


def test_compile_bottom_anchored_props_are_tile_objects(tmp_path):
    src = two_rooms(tmp_path, a_props=["......", ".T....", ".@....", "....c.", "......"])
    t = tmj(compile_ok(src), "a")
    props = objs(t, "layer 2 objects")
    assert [o["name"] for o in props] == ["T", "@", "c"]
    tree = props[0]
    # cell 1,1: art 16x32 feet on the cell: top-left 16,-16 -> Tiled's bottom-left is 16,32
    assert (tree["x"], tree["y"], tree["width"], tree["height"]) == (16, 32, 16, 32)
    assert tree["type"] == "" and tree["rotation"] == 0 and tree["visible"] is True
    crate = props[2]
    assert (crate["x"], crate["y"], crate["width"], crate["height"]) == (64, 64, 16, 16)
    room = src.parent / "rooms" / "a.tmj"
    assert gid_png(room, tree["gid"]) == ("props/tree.png", 0)
    assert gid_png(room, crate["gid"]) == ("props/crate.png", 0)


def test_compile_prop_layer_is_index_ordered_in_draw_order(tmp_path):
    src = two_rooms(tmp_path, a_props=["....c.", ".T....", ".@....", "c.....", "......"])
    t = tmj(compile_ok(src), "a")
    layer = next(l for l in t["layers"] if l["name"] == "layer 2 objects")
    assert layer["draworder"] == "index"
    assert [(o["name"], o["x"]) for o in layer["objects"]] == [("c", 64), ("T", 16), ("@", 16), ("c", 0)]


def test_compile_wide_bottom_anchor_centres_on_the_cell(tmp_path):
    # +b: x = cell x + (tile w - w) // 2, y (Tiled's bottom) = the cell's bottom
    src = two_rooms(tmp_path, a_props=["......", "..R...", ".@....", "......", "......"])
    t = tmj(compile_ok(src), "a")
    rug = next(o for o in objs(t) if o["name"] == "R")
    assert (rug["x"], rug["y"], rug["width"], rug["height"]) == (32 + (16 - 32) // 2, 32, 32, 16)


def test_compile_odd_width_bottom_anchor_odd_pixel_left(tmp_path):
    make_pack(tmp_path / "assets")
    art((13, 20), (5, 6, 7)).save(tmp_path / "assets" / "mini" / "props" / "odd.png")
    ts = load(tmp_path / "assets/mini/tiled/mini-props.tsj")
    ts["tiles"].append({"id": 99, "type": "object", "image": "../props/odd.png", "imagewidth": 13, "imageheight": 20,
                        "properties": [{"name": "png", "type": "string", "value": "props/odd.png"}]})
    (tmp_path / "assets/mini/tiled/mini-props.tsj").write_text(json.dumps(ts))
    legend = LEGEND + f"o {P}/props/odd.png+b\n"
    src = game(tmp_path, {"a": room_text(OPEN5, ["......", "..o...", ".@....", "......", "......"], legend=legend)},
               {"layout": ["a"], "start": {"room": "a", "at": "@"}}, pack=False)
    odd = next(o for o in objs(tmj(compile_ok(src), "a")) if o["name"] == "o")
    assert (odd["x"], odd["y"]) == (32 + (16 - 13) // 2, 32) == (33, 32)


def test_compile_flip_suffixes_are_gid_flags(tmp_path):
    src = two_rooms(tmp_path, a_props=["......", ".T.t..", ".@....", "..l.L.", "......"])
    t = tmj(compile_ok(src), "a")
    room = src.parent / "rooms" / "a.tmj"
    by = {o["name"]: o for o in objs(t)}
    assert gid_png(room, by["T"]["gid"]) == ("props/tree.png", 0)
    assert gid_png(room, by["t"]["gid"]) == ("props/tree.png", pxart.GID_H)
    layer2 = next(l for l in t["layers"] if l["name"] == "layer 2")
    lamps = [gid_png(room, g) for g in layer2["data"] if g]
    assert lamps == [("props/lamp.png", 0), ("props/lamp.png", pxart.GID_H)]


def test_compile_vertical_flip(tmp_path):
    legend = LEGEND + f"v {P}/props/lamp.png+v\nx {P}/props/lamp.png+hv\n"
    src = game(tmp_path, {"a": room_text(OPEN5, ["......", ".vx...", ".@....", "......", "......"], legend=legend)},
               {"layout": ["a"], "start": {"room": "a", "at": "@"}})
    t = tmj(compile_ok(src), "a")
    data = next(l for l in t["layers"] if l["name"] == "layer 2")["data"]
    flags = [g & pxart.GID_FLAGS for g in data if g]
    assert flags == [pxart.GID_V, pxart.GID_H | pxart.GID_V]


def test_compile_tile_sized_prop_without_b_is_a_tile(tmp_path):
    src = two_rooms(tmp_path, a_props=["......", ".l....", ".@....", "......", "......"])
    t = tmj(compile_ok(src), "a")
    names = [l["name"] for l in t["layers"]]
    assert names == ["layer 1", "layer 2", "layer 2 objects", "world"]
    layer2 = next(l for l in t["layers"] if l["name"] == "layer 2")
    assert layer2["data"][6 + 1] != 0 and sum(1 for g in layer2["data"] if g) == 1


def test_compile_small_art_without_b_is_a_top_left_object(tmp_path):
    src = two_rooms(tmp_path, a_props=["......", "..p...", ".@....", "......", "......"])
    t = tmj(compile_ok(src), "a")
    pebble = next(o for o in objs(t) if o["name"] == "p")
    assert (pebble["x"], pebble["y"], pebble["width"], pebble["height"]) == (32, 16 + 8, 8, 8)


def test_compile_big_art_without_b_warns_and_is_top_left(tmp_path, capsys):
    legend = LEGEND + f"S {P}/props/tree.png\n"
    src = game(tmp_path, {"a": room_text(OPEN5, ["......", ".S....", "......", "...@..", "......"], legend=legend)},
               {"layout": ["a"], "start": {"room": "a", "at": "@"}})
    assert run("export", src, "--tiled") == 0
    out = capsys.readouterr().out
    assert "WARNING:" in out and "legend 'S' is 16x32, bigger than a 16x16 cell, with no +b" in out
    tree = next(o for o in objs(tmj(src.parent, "a")) if o["name"] == "S")
    assert (tree["x"], tree["y"]) == (16, 16 + 32)


def test_compile_art_past_the_edge_warns(tmp_path, capsys):
    src = two_rooms(tmp_path, a_props=[".T....", "......", ".@....", "......", "......"])
    assert run("export", src, "--tiled") == 0
    out = capsys.readouterr().out
    assert "'T''s art at cell 1,0 reaches past the room's edge" in out


def test_compile_a_tile_under_an_earlier_objects_overhang_becomes_an_object(tmp_path):
    # T at cell 1,2 (feet) rises into cell 1,1; the lamp tile at 1,1 comes AFTER T? No: row 1 is before row 2.
    # So put the overhang the other way: a tall tree whose art covers the next row's cell? +b rises up, so use the
    # top-left pebble... the case is an object drawn before a tile it overlaps: a top-left 16x32 'S' on row 1 hangs
    # into row 2, where a lamp tile sits: scene draws the lamp over S; Tiled must too.
    legend = LEGEND + f"S {P}/props/tree.png\n"
    src = game(tmp_path, {"a": room_text(OPEN5, ["......", ".S....", ".l.l..", "......", ".@...."], legend=legend)},
               {"layout": ["a"], "start": {"room": "a", "at": "@"}})
    t = tmj(compile_ok(src), "a")
    layer_objs = next(l for l in t["layers"] if l["name"] == "layer 2 objects")["objects"]
    assert [o["name"] for o in layer_objs] == ["S", "l", "@"]  # the overhung lamp, in draw order
    lamp = layer_objs[1]
    assert (lamp["x"], lamp["y"], lamp["width"], lamp["height"]) == (16, 48, 16, 16)
    tiles = next(l for l in t["layers"] if l["name"] == "layer 2")["data"]
    assert tiles[2 * 6 + 3] != 0 and tiles[2 * 6 + 1] == 0  # the lamp nothing overhangs stays a tile


def test_compile_variant_list_cells_pick_by_hash(tmp_path):
    ground = ["VVVVVV"] * 5
    src = game(tmp_path, {"field": room_text(ground, ["......", "......", "..@...", "......", "......"])},
               {"layout": ["field"], "start": {"room": "field", "at": "@"}})
    t = tmj(compile_ok(src), "field")
    room = src.parent / "rooms" / "field.tmj"
    data = next(l for l in t["layers"] if l["type"] == "tilelayer")["data"]
    opts = ["world/floor.png", "world/floor2.png", "world/floor3.png"]
    for i, g in enumerate(data):
        x, y = i % 6, i // 6
        assert gid_png(room, g)[0] == opts[pxart.cell_hash("field", x, y) % 3]
    assert len(set(data)) > 1


def test_compile_variant_pick_is_stable_across_recompiles(tmp_path):
    src = game(tmp_path, {"field": room_text(["VVVVVV"] * 5, ["......", "......", "..@...", "......", "......"])},
               {"layout": ["field"], "start": {"room": "field", "at": "@"}})
    compile_ok(src)
    first = (src.parent / "rooms" / "field.tmj").read_bytes()
    compile_ok(src)
    assert (src.parent / "rooms" / "field.tmj").read_bytes() == first


def test_compile_markers_are_tile_objects_of_character_class(tmp_path):
    src = two_rooms(tmp_path)
    t = tmj(compile_ok(src), "a")
    hero = next(o for o in objs(t) if o["name"] == "@")
    pack = load(tmp_path / "assets/mini/tiled/mini-props.tsj")
    room = src.parent / "rooms" / "a.tmj"
    png = gid_png(room, hero["gid"])[0]
    assert next(x["type"] for x in pack["tiles"] if x["properties"][0]["value"] == png) == "character_frame"


def test_compile_start_is_a_point_at_the_marker_feet(tmp_path):
    src = two_rooms(tmp_path)
    t = tmj(compile_ok(src), "a")
    start = next(o for o in objs(t, "world") if o["type"] == "start")
    assert start == {"id": start["id"], "name": "start", "type": "start", "point": True, "x": 1 * 16 + 8,
                     "y": 2 * 16 + 16, "width": 0, "height": 0, "rotation": 0, "visible": True}


def test_compile_door_objects_both_sides(tmp_path):
    src = two_rooms(tmp_path)
    g = compile_ok(src)
    da = next(o for o in objs(tmj(g, "a"), "world") if o["type"] == "door")
    db = next(o for o in objs(tmj(g, "b"), "world") if o["type"] == "door")
    assert (da["name"], da["x"], da["y"], da["width"], da["height"]) == ("D", 64, 32, 16, 16)
    assert (db["name"], db["x"], db["y"], db["width"], db["height"]) == ("d", 32, 64, 16, 16)
    assert da["properties"] == [{"name": "entry", "type": "string", "value": "d"},
                                {"name": "target", "type": "file", "value": "b.tmj"}]
    assert db["properties"] == [{"name": "entry", "type": "string", "value": "D"},
                                {"name": "target", "type": "file", "value": "a.tmj"}]


def test_compile_door_extra_properties_and_trigger(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"},
                                   "doors": [["a D", "b d", {"trigger": "use", "requires": "key", "locked": True,
                                                             "cost": 3, "volume": 0.5}]]})
    g = compile_ok(src)
    for room in ("a", "b"):
        d = next(o for o in objs(tmj(g, room), "world") if o["type"] == "door")
        props = {p["name"]: (p["type"], p["value"]) for p in d["properties"]}
        assert props["trigger"] == ("string", "use") and props["requires"] == ("string", "key")
        assert props["locked"] == ("bool", True) and props["cost"] == ("int", 3) and props["volume"] == ("float", 0.5)
        assert [p["name"] for p in d["properties"]] == sorted(props)


def test_compile_trigger_touch_is_written_when_given(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"},
                                   "doors": [["a D", "b d", {"trigger": "touch"}]]})
    d = next(o for o in objs(tmj(compile_ok(src), "a"), "world") if o["type"] == "door")
    assert {"name": "trigger", "type": "string", "value": "touch"} in d["properties"]


def test_compile_wide_door_is_one_rectangle(tmp_path):
    b = ["WWWWWW", "W1111W", "W1111W", "W1111W", "WddddW"]
    src = two_rooms(tmp_path, b=b)
    d = next(o for o in objs(tmj(compile_ok(src), "b"), "world") if o["type"] == "door")
    assert (d["x"], d["y"], d["width"], d["height"]) == (16, 64, 64, 16)


def test_compile_door_drawn_in_the_prop_layer_counts(tmp_path):
    a = ["111111"] * 5
    src = two_rooms(tmp_path, a=a, a_props=["......", "......", ".@..D.", "......", "......"])
    d = next(o for o in objs(tmj(compile_ok(src), "a"), "world") if o["type"] == "door")
    assert (d["x"], d["y"]) == (64, 32)


def test_compile_world_file(tmp_path):
    src = two_rooms(tmp_path)
    w = load(compile_ok(src) / "world.world")
    assert w == {"type": "world", "onlyShowAdjacentMaps": False,
                 "maps": [{"fileName": "rooms/a.tmj", "x": 0, "y": 0, "width": 96, "height": 80}]}


def test_compile_world_layout_sizes_columns_and_rows(tmp_path):
    small = ["1111"] * 3
    big = ["111111"] * 5
    src = game(tmp_path, {"a": room_text(small, ["....", ".@..", "...."]), "b": room_text(big),
                          "c": room_text(small), "d": room_text(big)},
               {"layout": ["a b", "c .", ". d"], "start": {"room": "a", "at": "@"}})
    assert run("export", src, "--tiled") == 0
    w = load(src.parent / "world.world")
    at = {m["fileName"]: (m["x"], m["y"], m["width"], m["height"]) for m in w["maps"]}
    assert at == {"rooms/a.tmj": (0, 0, 64, 48), "rooms/b.tmj": (64, 0, 96, 80), "rooms/c.tmj": (0, 80, 64, 48),
                  "rooms/d.tmj": (64, 128, 96, 80)}
    assert [m["fileName"] for m in w["maps"]] == ["rooms/a.tmj", "rooms/b.tmj", "rooms/c.tmj", "rooms/d.tmj"]


def test_compile_world_empty_column_is_the_largest_room(tmp_path):
    room = ["1111"] * 3
    src = game(tmp_path, {"a": room_text(room, ["....", ".@..", "...."]), "b": room_text(room)},
               {"layout": ["a . b"], "start": {"room": "a", "at": "@"}})
    assert run("export", src, "--tiled") == 0
    w = load(src.parent / "world.world")
    assert [(m["fileName"], m["x"]) for m in w["maps"]] == [("rooms/a.tmj", 0), ("rooms/b.tmj", 128)]


def test_compile_world_name_follows_the_source_name(tmp_path):
    src = two_rooms(tmp_path)
    other = src.parent / "island.src.json"
    other.write_text(src.read_text())
    assert run("export", other, "--tiled") == 0
    assert (src.parent / "island.world").is_file()


def test_compile_unused_rooms_get_a_note(tmp_path, capsys):
    src = two_rooms(tmp_path)
    (src.parent / "rooms" / "spare.map").write_text(room_text(OPEN5))
    assert run("export", src, "--tiled") == 0
    out = capsys.readouterr().out
    assert "note:" in out and "spare.map isn't in the world" in out
    assert not (src.parent / "rooms" / "spare.tmj").exists()


def test_compile_json_rows_on_a_line(tmp_path):
    src = two_rooms(tmp_path)
    text = (compile_ok(src) / "rooms" / "b.tmj").read_text()
    assert re.search(r'"data": \[\n +\d+, \d+, \d+, \d+, \d+, \d+,\n', text)
    assert text.endswith("\n")


def test_tiled_json_round_trips():
    data = {"layers": [{"type": "tilelayer", "width": 2, "data": [1, 2, 3, 4]}, {"type": "objectgroup"}], "x": 1}
    assert json.loads(pxart.tiled_json(data)) == data


def test_compile_lone_map(tmp_path, capsys):
    make_pack(tmp_path / "assets")
    (tmp_path / "game" / "rooms").mkdir(parents=True)
    m = tmp_path / "game" / "rooms" / "solo.map"
    m.write_text(room_text(OPEN5, ["......", ".T....", ".@....", "......", "......"]))
    assert run("export", m, "--tiled") == 0
    out = capsys.readouterr().out
    t = load(m.with_suffix(".tmj"))
    assert f"wrote {m.with_suffix('.tmj')}: 6x5, 2 objects (0 kept ids, 2 new)" in out
    assert not objs(t, "world") and t["properties"][0]["value"] == "solo.map"


def test_compile_lone_maps_several(tmp_path):
    make_pack(tmp_path / "assets")
    (tmp_path / "game" / "rooms").mkdir(parents=True)
    ms = []
    for n in ("one", "two"):
        m = tmp_path / "game" / "rooms" / f"{n}.map"
        m.write_text(room_text(OPEN5))
        ms.append(m)
    assert run("export", *ms, "--tiled") == 0
    assert all(m.with_suffix(".tmj").is_file() for m in ms)


def test_compile_tile_size_option(tmp_path):
    # 16px art on an 8px grid: every cell's art is bigger than a cell, so everything is a (top-left) object
    src = two_rooms(tmp_path)
    assert run("export", src, "--tiled", "--tile", "8") == 0
    t = tmj(src.parent, "a")
    assert (t["tilewidth"], t["tileheight"]) == (8, 8)


def test_compile_explicit_tileset(tmp_path):
    # art outside any pack, found through --tileset
    loose = tmp_path / "loose"
    loose.mkdir()
    art((16, 16), (1, 2, 3)).save(loose / "stone.png")
    (loose / "stone.tsj").write_text(json.dumps({
        "type": "tileset", "name": "stone", "tilewidth": 16, "tileheight": 16, "tilecount": 1, "columns": 0,
        "tiles": [{"id": 0, "image": "stone.png", "imagewidth": 16, "imageheight": 16}]}))
    make_pack(tmp_path / "assets")
    (tmp_path / "game" / "rooms").mkdir(parents=True)
    m = tmp_path / "game" / "rooms" / "r.map"
    m.write_text("s ../../loose/stone.png\n\nss\n")
    msg = run_err("export", m, "--tiled")
    assert "E_TILESET" in msg and "no tileset has this art" in msg
    assert run("export", m, "--tiled", "--tileset", loose / "stone.tsj") == 0
    t = load(m.with_suffix(".tmj"))
    assert t["tilesets"] == [{"firstgid": 1, "source": "../../loose/stone.tsj"}]
    assert next(l for l in t["layers"] if l["type"] == "tilelayer")["data"] == [1, 1]


def test_compile_px_legend_found_by_pixels(tmp_path):
    # a .px frame is its pack's PNG when the pixels are the same (the pack's pxart/ sources)
    make_pack(tmp_path / "assets")
    pack = tmp_path / "assets" / "mini"
    (pack / "pxart").mkdir()
    img = Image.open(pack / "world" / "floor.png")
    assert run("from-png", pack / "world" / "floor.png", "-o", pack / "pxart" / "floor.px") == 0
    assert pxart.parse(pack / "pxart" / "floor.px").image(pxart.parse(pack / "pxart" / "floor.px").frames[0]).tobytes() \
        == img.convert("RGBA").tobytes()
    (tmp_path / "game" / "rooms").mkdir(parents=True)
    m = tmp_path / "game" / "rooms" / "r.map"
    m.write_text("f ../../assets/mini/pxart/floor.px\n\nff\n")
    assert run("export", m, "--tiled") == 0
    t = load(m.with_suffix(".tmj"))
    assert gid_png(m.with_suffix(".tmj"), next(l for l in t["layers"] if l["type"] == "tilelayer")["data"][0])[0] \
        == "world/floor.png"


def test_compile_png_not_in_a_tileset_but_pixel_identical_is_found(tmp_path):
    make_pack(tmp_path / "assets")
    pack = tmp_path / "assets" / "mini"
    shutil.copy(pack / "world" / "wall.png", pack / "world" / "wall-copy.png")
    (tmp_path / "game" / "rooms").mkdir(parents=True)
    m = tmp_path / "game" / "rooms" / "r.map"
    m.write_text("w ../../assets/mini/world/wall-copy.png\n\nww\n")
    assert run("export", m, "--tiled") == 0
    t = load(m.with_suffix(".tmj"))
    assert gid_png(m.with_suffix(".tmj"), next(l for l in t["layers"] if l["type"] == "tilelayer")["data"][0])[0] \
        == "world/wall.png"


def test_compile_pixel_twins_are_ambiguous(tmp_path):
    make_pack(tmp_path / "assets")
    pack = tmp_path / "assets" / "mini"
    shutil.copy(pack / "world" / "floor.png", pack / "world" / "floor2.png")  # now two tiles look alike
    shutil.copy(pack / "world" / "floor.png", pack / "world" / "copy.png")
    ts = load(pack / "tiled" / "mini-ground.tsj")
    sheet = Image.open(pack / "tiled" / "mini-ground.png")
    cols = ts["columns"]
    sheet.paste(Image.open(pack / "world" / "floor.png"), ((1 % cols) * 16, (1 // cols) * 16))
    sheet.save(pack / "tiled" / "mini-ground.png")
    (tmp_path / "game" / "rooms").mkdir(parents=True)
    m = tmp_path / "game" / "rooms" / "r.map"
    m.write_text("w ../../assets/mini/world/copy.png\n\nww\n")
    msg = run_err("export", m, "--tiled")
    assert "more than one tile has this art" in msg and "name the PNG itself" in msg


def test_compile_finds_the_pack_through_a_symlink(tmp_path):
    make_pack(tmp_path / "real")
    (tmp_path / "game" / "rooms").mkdir(parents=True)
    (tmp_path / "game" / "mini").symlink_to(tmp_path / "real" / "mini")
    m = tmp_path / "game" / "rooms" / "r.map"
    m.write_text("f ../mini/world/floor.png\n\nff\n")
    assert run("export", m, "--tiled") == 0
    t = load(m.with_suffix(".tmj"))
    assert t["tilesets"][0]["source"] == "../mini/tiled/mini-ground.tsj"  # through the link, as the game sees it


# ================================================================ stable object ids (ADR 0009)

def id_map(t):
    return {(o["type"], o["name"], pxart.object_cell(o, 16, 16)): o["id"] for o in objs(t)}


def test_ids_first_compile_in_draw_order(tmp_path):
    src = two_rooms(tmp_path, a_props=["....c.", ".T....", ".@....", "c.....", "......"])
    t = tmj(compile_ok(src), "a")
    assert [o["id"] for o in objs(t)] == list(range(1, 7))  # c, T, @, c, then the door and the start
    assert t["nextobjectid"] == 7


def test_ids_recompile_unchanged_is_byte_identical(tmp_path):
    src = two_rooms(tmp_path, a_props=["....c.", ".T....", ".@....", "c.....", "......"])
    g = compile_ok(src)
    before = {p.name: p.read_bytes() for p in (g / "rooms").glob("*.tmj")} | {"w": (g / "world.world").read_bytes()}
    compile_ok(src)
    after = {p.name: p.read_bytes() for p in (g / "rooms").glob("*.tmj")} | {"w": (g / "world.world").read_bytes()}
    assert before == after


def test_ids_insert_a_prop_keeps_the_others(tmp_path):
    # the rule-3 test: an unrelated edit, a rebuild, and untouched things keep their ids
    src = two_rooms(tmp_path, a_props=["....c.", ".T....", ".@....", "c.....", "......"])
    g = compile_ok(src)
    before = id_map(tmj(g, "a"))
    nxt = tmj(g, "a")["nextobjectid"]
    (g / "rooms" / "a.map").write_text(room_text(["111111", "111111", "1111D1", "111111", "111111"],
                                                 ["c...c.", ".T....", ".@....", "c.....", "......"]))
    compile_ok(src)
    t = tmj(g, "a")
    after = id_map(t)
    for k, v in before.items():
        assert after[k] == v, k
    new = [v for k, v in after.items() if k not in before]
    assert new == [nxt] and t["nextobjectid"] == nxt + 1
    assert objs(t, "layer 2 objects")[0]["id"] == nxt  # drawn first (row 0), numbered last


def test_ids_delete_a_prop_never_reuses_its_id(tmp_path):
    src = two_rooms(tmp_path, a_props=["....c.", ".T....", ".@....", "c.....", "......"])
    g = compile_ok(src)
    first = tmj(g, "a")
    gone = next(o["id"] for o in objs(first) if o["name"] == "T")
    (g / "rooms" / "a.map").write_text(room_text(["111111", "111111", "1111D1", "111111", "111111"],
                                                 ["....c.", "......", ".@....", "c.....", "......"]))
    compile_ok(src)
    second = tmj(g, "a")
    assert gone not in [o["id"] for o in objs(second)] and second["nextobjectid"] == first["nextobjectid"]
    (g / "rooms" / "a.map").write_text(room_text(["111111", "111111", "1111D1", "111111", "111111"],
                                                 ["....c.", "...R..", ".@....", "c.....", "......"]))
    compile_ok(src)
    third = tmj(g, "a")
    rug = next(o for o in objs(third) if o["name"] == "R")
    assert rug["id"] == first["nextobjectid"] and gone not in [o["id"] for o in objs(third)]


def test_ids_bring_it_back_and_it_is_new(tmp_path):
    # a deleted then restored prop is a new object: its old id is gone for good (never reused)
    src = two_rooms(tmp_path, a_props=["......", ".T....", ".@....", "......", "......"])
    g = compile_ok(src)
    old = next(o["id"] for o in objs(tmj(g, "a")) if o["name"] == "T")
    (g / "rooms" / "a.map").write_text(room_text(["111111", "111111", "1111D1", "111111", "111111"],
                                                 ["......", "......", ".@....", "......", "......"]))
    compile_ok(src)
    (g / "rooms" / "a.map").write_text(room_text(["111111", "111111", "1111D1", "111111", "111111"],
                                                 ["......", ".T....", ".@....", "......", "......"]))
    compile_ok(src)
    assert next(o["id"] for o in objs(tmj(g, "a")) if o["name"] == "T") != old


def test_ids_move_a_prop_is_a_new_object(tmp_path):
    src = two_rooms(tmp_path, a_props=["......", ".T....", ".@....", "....c.", "......"])
    g = compile_ok(src)
    before = {o["name"]: o["id"] for o in objs(tmj(g, "a"))}
    (g / "rooms" / "a.map").write_text(room_text(["111111", "111111", "1111D1", "111111", "111111"],
                                                 ["......", "..T...", ".@....", "....c.", "......"]))
    compile_ok(src)
    after = {o["name"]: o["id"] for o in objs(tmj(g, "a"))}
    assert after["c"] == before["c"] and after["@"] == before["@"] and after["T"] != before["T"]


def test_ids_rename_a_prop_is_a_new_object(tmp_path):
    src = two_rooms(tmp_path, a_props=["......", ".T....", ".@....", "....c.", "......"])
    g = compile_ok(src)
    before = {o["name"]: o["id"] for o in objs(tmj(g, "a"))}
    legend = LEGEND.replace("T ", "Y ").replace("t ", "T ")  # 'T' now the flipped tree; the plain one is 'Y'
    (g / "rooms" / "a.map").write_text(room_text(["111111", "111111", "1111D1", "111111", "111111"],
                                                 ["......", ".Y....", ".@....", "....c.", "......"], legend=legend))
    compile_ok(src)
    after = {o["name"]: o["id"] for o in objs(tmj(g, "a"))}
    assert after["Y"] not in before.values() and after["c"] == before["c"]


def test_ids_same_char_same_cell_twice_keeps_order(tmp_path):
    src = two_rooms(tmp_path, a_props=["......", ".c....", ".@....", "......", "......"])
    g = compile_ok(src)
    text = (g / "rooms" / "a.map").read_text() + "---\n......\n.c....\n......\n......\n......\n"
    (g / "rooms" / "a.map").write_text(text)
    compile_ok(src)
    first = [(o["id"], l["name"]) for l in tmj(g, "a")["layers"] if l["type"] == "objectgroup"
             for o in l["objects"] if o["name"] == "c"]
    compile_ok(src)
    again = [(o["id"], l["name"]) for l in tmj(g, "a")["layers"] if l["type"] == "objectgroup"
             for o in l["objects"] if o["name"] == "c"]
    assert first == again and len({i for i, _ in first}) == 2


def test_ids_doors_and_start_keep_theirs(tmp_path):
    src = two_rooms(tmp_path)
    g = compile_ok(src)
    before = {(o["type"], o["name"]): o["id"] for o in objs(tmj(g, "a"), "world")}
    (g / "rooms" / "a.map").write_text(room_text(["111111", "111111", "1111D1", "111111", "111111"],
                                                 ["c.....", "......", ".@....", "......", "...c.."]))
    compile_ok(src)
    after = {(o["type"], o["name"]): o["id"] for o in objs(tmj(g, "a"), "world")}
    assert before == after


def test_ids_moving_the_door_gives_it_a_new_id(tmp_path):
    src = two_rooms(tmp_path)
    g = compile_ok(src)
    old = next(o["id"] for o in objs(tmj(g, "a"), "world") if o["type"] == "door")
    (g / "rooms" / "a.map").write_text(room_text(["111111", "111111", "11111D", "111111", "111111"],
                                                 ["......", "......", ".@....", "......", "......"]))
    compile_ok(src)
    assert next(o["id"] for o in objs(tmj(g, "a"), "world") if o["type"] == "door") != old


def test_ids_a_door_and_a_prop_of_one_char_and_cell_are_two_objects(tmp_path):
    legend = LEGEND.replace(f"D {P}/world/floor.png", f"D {P}/props/crate.png+b")
    src = game(tmp_path, {"a": room_text(OPEN5, ["......", "......", ".@..D.", "......", "......"], legend=legend),
                          "b": room_text(["WWWWWW", "W1111W", "W1111W", "W1111W", "WWdWWW"])},
               {"layout": ["a"], "start": {"room": "a", "at": "@"}, "doors": [["a D", "b d"]]})
    g = compile_ok(src)
    ds = [(o["type"], o["id"]) for o in objs(tmj(g, "a")) if o["name"] == "D"]
    assert sorted(t for t, _ in ds) == ["", "door"]
    compile_ok(src)
    assert [(o["type"], o["id"]) for o in objs(tmj(g, "a")) if o["name"] == "D"] == ds


def test_ids_take_the_previous_nextobjectid_even_if_higher(tmp_path):
    src = two_rooms(tmp_path)
    g = compile_ok(src)
    p = g / "rooms" / "a.tmj"
    t = load(p)
    t["nextobjectid"] = 50  # say Tiled, or a later compile, issued up to 49
    p.write_text(json.dumps(t))
    (g / "rooms" / "a.map").write_text(room_text(["111111", "111111", "1111D1", "111111", "111111"],
                                                 ["c.....", "......", ".@....", "......", "......"]))
    compile_ok(src)
    t = tmj(g, "a")
    assert next(o["id"] for o in objs(t) if o["name"] == "c") == 50 and t["nextobjectid"] == 51


def test_ids_previous_ids_past_nextobjectid_are_not_reissued(tmp_path):
    src = two_rooms(tmp_path)
    g = compile_ok(src)
    p = g / "rooms" / "a.tmj"
    t = load(p)
    t["nextobjectid"] = 1  # a broken counter: ids go on after the highest one there
    p.write_text(json.dumps(t))
    top = max(o["id"] for o in objs(t))
    (g / "rooms" / "a.map").write_text(room_text(["111111", "111111", "1111D1", "111111", "111111"],
                                                 ["c.....", "......", ".@....", "......", "......"]))
    compile_ok(src)
    assert next(o["id"] for o in objs(tmj(g, "a")) if o["name"] == "c") == top + 1


def test_ids_all_rooms_independent(tmp_path):
    src = two_rooms(tmp_path, b_props=["......", ".c....", "......", "......", "......"])
    g = compile_ok(src)
    assert [o["id"] for o in objs(tmj(g, "b"))] == [1, 2]


def test_object_cell_rules():
    assert pxart.object_cell({"point": True, "x": 88, "y": 128}, 16, 16) == (5, 7)
    assert pxart.object_cell({"point": True, "x": 88, "y": 120}, 16, 16) == (5, 7)
    assert pxart.object_cell({"gid": 1, "x": 72, "y": 128, "width": 32, "height": 32}, 16, 16) == (5, 7)
    assert pxart.object_cell({"gid": 1, "x": 156, "y": 112, "width": 24, "height": 48}, 16, 16) == (10, 6)
    assert pxart.object_cell({"x": 160, "y": 112, "width": 16, "height": 16}, 16, 16) == (10, 7)


def test_firstgids_keep_previous_when_they_fit(tmp_path):
    src = two_rooms(tmp_path)
    g = compile_ok(src)
    p = g / "rooms" / "a.tmj"
    t = load(p)
    old = {ts["source"]: ts["firstgid"] for ts in t["tilesets"]}
    # pretend a previous compile put the props tileset high up
    for ts in t["tilesets"]:
        if "props" in ts["source"]:
            ts["firstgid"] = 100
    for l in t["layers"]:
        for o in l.get("objects", ()):
            o.pop("gid", None)
    p.write_text(json.dumps(t))
    compile_ok(src)
    got = {ts["source"]: ts["firstgid"] for ts in tmj(g, "a")["tilesets"]}
    assert got[next(s for s in old if "props" in s)] == 100 and got[next(s for s in old if "ground" in s)] == 1


def test_firstgids_repack_when_the_old_ones_overlap(tmp_path):
    src = two_rooms(tmp_path)
    g = compile_ok(src)
    p = g / "rooms" / "a.tmj"
    t = load(p)
    for ts in t["tilesets"]:
        ts["firstgid"] = 2 if "props" in ts["source"] else 1  # overlapping
    p.write_text(json.dumps(t))
    compile_ok(src)
    got = [ts["firstgid"] for ts in tmj(g, "a")["tilesets"]]
    assert got[0] == 1 and got[1] == 1 + load(tmp_path / "assets/mini/tiled/mini-ground.tsj")["tilecount"]


# ================================================================ generated files

def test_generated_tmj_without_source_is_never_overwritten(tmp_path):
    src = two_rooms(tmp_path)
    g = src.parent
    (g / "rooms" / "b.tmj").write_text(json.dumps({"type": "map", "width": 1, "height": 1, "layers": []}))
    msg = run_err("export", src, "--tiled")
    assert "E_GENERATED" in msg and "has no 'source' property" in msg
    assert load(g / "rooms" / "b.tmj") == {"type": "map", "width": 1, "height": 1, "layers": []}
    assert not (g / "rooms" / "a.tmj").exists() and not (g / "world.world").exists()


def test_generated_tmj_from_another_source_is_never_overwritten(tmp_path):
    src = two_rooms(tmp_path)
    g = compile_ok(src)
    t = tmj(g, "b")
    t["properties"] = [{"name": "source", "type": "file", "value": "other.map"}]
    (g / "rooms" / "b.tmj").write_text(json.dumps(t))
    msg = run_err("export", src, "--tiled")
    assert "E_GENERATED" in msg and "compiled from other.map, not b.map" in msg


def test_generated_tmj_unreadable_is_an_error(tmp_path):
    src = two_rooms(tmp_path)
    (src.parent / "rooms" / "b.tmj").write_text("{not json")
    msg = run_err("export", src, "--tiled")
    assert "E_GENERATED" in msg and "can't be read" in msg


# ================================================================ strictness: source errors, at file:line:col

def errors(msg):
    return [l for l in msg.splitlines() if l.strip()]


def test_strict_ragged_ground_row(tmp_path):
    src = two_rooms(tmp_path, a=["111111", "11111", "1111D1", "111111", "111111"])
    msg = run_err("export", src, "--tiled")
    # line 17: the comment, 14 legend lines, the blank, then row 2
    assert re.search(r"rooms/a\.map:18:6: E_ROW_WIDTH: row is 5 wide, the room is 6", msg), msg
    assert not (src.parent / "world.world").exists()


def test_strict_ragged_prop_row(tmp_path):
    src = two_rooms(tmp_path, a_props=["......", ".....", ".@....", "......", "......"])
    msg = run_err("export", src, "--tiled")
    assert "E_ROW_WIDTH" in msg and "row is 5 wide" in msg


def test_strict_row_wider_than_the_rest(tmp_path):
    src = two_rooms(tmp_path, a_props=["......", ".......", ".@....", "......", "......"])
    msg = run_err("export", src, "--tiled")
    assert msg.count("E_ROW_WIDTH") == 9 and "the room is 7" in msg  # every other row is now short


def test_strict_short_layer_is_a_warning(tmp_path, capsys):
    src = two_rooms(tmp_path, a_props=["......", "......", ".@...."])
    assert run("export", src, "--tiled") == 0
    out = capsys.readouterr().out
    assert "WARNING:" in out and "layer 2 has 3 rows, the room has 5" in out


def test_strict_unknown_chars_all_at_once(tmp_path):
    src = two_rooms(tmp_path, a=["111111", "11?111", "1111D1", "11111!", "111111"])
    msg = run_err("export", src, "--tiled")
    assert re.search(r"a\.map:18:3: E_UNKNOWN_KEY: map char '\?' has no legend line", msg), msg
    assert re.search(r"a\.map:20:6: E_UNKNOWN_KEY: map char '!' has no legend line", msg), msg


def test_strict_errors_across_rooms_at_once(tmp_path):
    src = two_rooms(tmp_path, a=["111111", "11?111", "1111D1", "111111", "111111"],
                    b=["WWWWWW", "W1111W", "W11111W", "W1111W", "WWdWWW"])
    msg = run_err("export", src, "--tiled")
    assert "a.map" in msg and "b.map" in msg and "E_UNKNOWN_KEY" in msg and "E_ROW_WIDTH" in msg


def test_strict_space_in_a_row(tmp_path):
    src = two_rooms(tmp_path, a=["111111", "11 111", "1111D1", "111111", "111111"])
    msg = run_err("export", src, "--tiled")
    assert "E_BAD_ROW" in msg and "a.map:18:3" in msg


def test_strict_empty_room(tmp_path):
    src = game(tmp_path, {"a": "# nothing\n" + LEGEND}, {"layout": ["a"]})
    msg = run_err("export", src, "--tiled")
    assert "E_MAP_SIZE" in msg and "no rows" in msg


def test_strict_art_no_tileset_has(tmp_path):
    loose = tmp_path / "loose"
    loose.mkdir()
    art((16, 16), (3, 3, 3)).save(loose / "odd.png")
    legend = LEGEND + "o ../../loose/odd.png\n"
    src = game(tmp_path, {"a": room_text(OPEN5, ["......", ".o....", ".@....", "......", "......"], legend=legend)},
               {"layout": ["a"], "start": {"room": "a", "at": "@"}})
    msg = run_err("export", src, "--tiled")
    assert re.search(r"a\.map:16: E_TILESET: legend 'o' \(\.\./\.\./loose/odd\.png\): no tileset has this art", msg), msg
    assert "<pack>/tiled/*.tsj" in msg and "--tileset" in msg


def test_strict_missing_legend_file(tmp_path):
    legend = LEGEND + f"z {P}/props/nope.png\n"
    src = game(tmp_path, {"a": room_text(OPEN5, ["......", ".z....", ".@....", "......", "......"], legend=legend)},
               {"layout": ["a"], "start": {"room": "a", "at": "@"}})
    msg = run_err("export", src, "--tiled")
    assert "E_FILE" in msg and "nope.png" in msg


def test_strict_tile_size_mismatch(tmp_path):
    make_pack(tmp_path / "assets")
    pack = tmp_path / "assets" / "mini"
    ts = load(pack / "tiled" / "mini-props.tsj")
    ts["tiles"][0]["imagewidth"] = 20  # the tileset says 20 wide; the crate is 16
    (pack / "tiled" / "mini-props.tsj").write_text(json.dumps(ts))
    src = game(tmp_path, {"a": room_text(OPEN5, ["......", ".c....", ".@....", "......", "......"])},
               {"layout": ["a"], "start": {"room": "a", "at": "@"}}, pack=False)
    msg = run_err("export", src, "--tiled")
    assert "E_TILESET" in msg and "its art is 16x16, but mini-props.tsj tile 0 is 20x16" in msg


def test_strict_broken_tileset_is_an_error(tmp_path):
    make_pack(tmp_path / "assets")
    (tmp_path / "assets" / "mini" / "tiled" / "mini-props.tsj").write_text("{nope")
    src = game(tmp_path, {"a": room_text(OPEN5, ["......", ".c....", ".@....", "......", "......"])},
               {"layout": ["a"], "start": {"room": "a", "at": "@"}}, pack=False)
    msg = run_err("export", src, "--tiled")
    assert "E_TILESET" in msg and "mini-props.tsj" in msg and "can't read the tileset" in msg


def test_strict_not_json(tmp_path):
    src = two_rooms(tmp_path, src='{"layout": ["a"],\n "start": {"room": "a" "at": "@"}}')
    msg = run_err("export", src, "--tiled")
    assert re.search(r"world\.src\.json:2:\d+: E_WORLD: not JSON", msg), msg


def test_strict_not_an_object(tmp_path):
    src = two_rooms(tmp_path, src="[1, 2]")
    assert "a world source is a JSON object" in run_err("export", src, "--tiled")


def test_strict_unknown_key_guesses(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"}, "door": [["a D", "b d"]]})
    msg = run_err("export", src, "--tiled")
    assert re.search(r"world\.src\.json:\d+:\d+: E_WORLD: unknown key 'door'.*did you mean 'doors'\?", msg), msg


def test_strict_no_layout(tmp_path):
    src = two_rooms(tmp_path, src={"start": {"room": "a", "at": "@"}})
    msg = run_err("export", src, "--tiled")
    assert 'no "layout"' in msg


def test_strict_layout_not_strings(tmp_path):
    src = two_rooms(tmp_path, src={"layout": [["a"]], "start": {"room": "a", "at": "@"}})
    assert '"layout" is a list of strings' in run_err("export", src, "--tiled")


def test_strict_layout_places_nothing(tmp_path):
    src = two_rooms(tmp_path, src={"layout": [". ."], "start": {"room": "a", "at": "@"}})
    assert '"layout" places no room' in run_err("export", src, "--tiled")


def test_strict_layout_room_twice(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a a"], "start": {"room": "a", "at": "@"}})
    assert "room 'a' is placed twice" in run_err("export", src, "--tiled")


def test_strict_layout_bad_name(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a b/c"], "start": {"room": "a", "at": "@"}})
    assert "'b/c' isn't a room name" in run_err("export", src, "--tiled")


def test_strict_layout_missing_room(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a bb"], "start": {"room": "a", "at": "@"}})
    msg = run_err("export", src, "--tiled")
    assert re.search(r"world\.src\.json:\d+:\d+: E_WORLD: room 'bb': no rooms/bb\.map", msg), msg
    assert "did you mean 'b'?" in msg


def test_strict_door_room_missing(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"}, "doors": [["a D", "c d"]]})
    assert "room 'c': no rooms/c.map" in run_err("export", src, "--tiled")


def test_strict_door_char_not_drawn(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"}, "doors": [["a D", "b x"]]})
    msg = run_err("export", src, "--tiled")
    assert re.search(r"world\.src\.json:\d+:\d+: E_DOOR: door 'b x': no 'x' drawn in rooms/b\.map", msg), msg


def test_strict_door_not_a_rectangle(tmp_path):
    a = ["111111", "1D1111", "1111D1", "111111", "111111"]
    src = two_rooms(tmp_path, a=a)
    msg = run_err("export", src, "--tiled")
    assert re.search(r"a\.map:18:2: E_DOOR: door 'a D': 'D' is drawn at 2 cells that aren't one rectangle", msg), msg


def test_strict_door_end_malformed(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"}, "doors": [["aD", "b d"]]})
    assert "door end 'aD': write 'ROOM CHAR'" in run_err("export", src, "--tiled")


def test_strict_door_pair_shape(tmp_path):
    for bad in (["a D"], ["a D", "b d", "x"], "a D", [["a D", "b d", {"x": 1}, 4]]):
        src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"},
                                       "doors": bad if isinstance(bad, list) and bad and isinstance(bad[0], list)
                                       else [bad]})
        assert "a door pair is" in run_err("export", src, "--tiled"), bad
        shutil.rmtree(tmp_path)
        tmp_path.mkdir()


def test_strict_doors_not_a_list(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"}, "doors": {"a D": "b d"}})
    assert '"doors" is a list of pairs' in run_err("export", src, "--tiled")


def test_strict_door_with_itself(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"}, "doors": [["a D", "a D"]]})
    assert "door 'a D' is paired with itself" in run_err("export", src, "--tiled")


def test_strict_door_in_two_pairs(tmp_path):
    a = ["111111", "111111", "1111D1", "111111", "1E1111"]
    src = two_rooms(tmp_path, a=a, src={"layout": ["a"], "start": {"room": "a", "at": "@"},
                                        "doors": [["a D", "b d"], ["a E", "b d"]]})
    msg = run_err("export", src, "--tiled")
    assert "door 'b d' is in two pairs" in msg


def test_strict_door_reserved_property(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"},
                                   "doors": [["a D", "b d", {"target": "x.tmj"}]]})
    assert "'target' is written by the compiler" in run_err("export", src, "--tiled")


def test_strict_door_bad_trigger(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"},
                                   "doors": [["a D", "b d", {"trigger": "step"}]]})
    msg = run_err("export", src, "--tiled")
    assert "E_DOOR" in msg and "trigger is 'touch' (the default) or 'use'" in msg


def test_strict_door_bad_property_value(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "@"},
                                   "doors": [["a D", "b d", {"sound": ["creak"]}]]})
    assert "property 'sound' is a string, number or true/false" in run_err("export", src, "--tiled")


def test_strict_start_shape(tmp_path):
    for bad in ("a", {"room": "a"}, {"room": "a", "at": "@@"}, {"at": "@"}):
        src = two_rooms(tmp_path, src={"layout": ["a"], "start": bad, "doors": [["a D", "b d"]]})
        assert '"start" is {"room": ROOM, "at": CHAR}' in run_err("export", src, "--tiled"), bad
        shutil.rmtree(tmp_path)
        tmp_path.mkdir()


def test_strict_start_room_not_in_the_world(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "c", "at": "@"}, "doors": [["a D", "b d"]]})
    msg = run_err("export", src, "--tiled")
    assert "E_START" in msg and "start: room 'c' isn't in the world" in msg


def test_strict_start_char_not_drawn(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "start": {"room": "a", "at": "&"}, "doors": [["a D", "b d"]]})
    msg = run_err("export", src, "--tiled")
    assert "E_START" in msg and "'&' is drawn at 0 cells" in msg


def test_strict_start_char_twice(tmp_path):
    src = two_rooms(tmp_path, a_props=["......", "....@.", ".@....", "......", "......"])
    msg = run_err("export", src, "--tiled")
    assert "'@' is drawn at 2 cells" in msg and "1,2" in msg and "4,1" in msg


def test_strict_start_in_an_interior_is_fine(tmp_path):
    src = two_rooms(tmp_path, a_props=["......"] * 5, b_props=["......", "..@...", "......", "......", "......"],
                    src={"layout": ["a"], "start": {"room": "b", "at": "@"}, "doors": [["a D", "b d"]]})
    assert run("export", src, "--tiled") == 0
    assert any(o["type"] == "start" for o in objs(tmj(src.parent, "b"), "world"))


def test_strict_nothing_written_on_any_error(tmp_path):
    src = two_rooms(tmp_path, a=["111111", "11?111", "1111D1", "111111", "111111"])
    run_err("export", src, "--tiled")
    assert list((src.parent / "rooms").glob("*.tmj")) == [] and not (src.parent / "world.world").exists()


def test_strict_source_errors_come_before_the_world_rules(tmp_path):
    # a start in a wall AND an unknown char: the source error is what's said (the rules would be noise)
    src = two_rooms(tmp_path, a=["111111", "11?111", "WWWWD1", "111111", "111111"])
    msg = run_err("export", src, "--tiled")
    assert "E_UNKNOWN_KEY" in msg and "E_WORLD" not in msg


# ================================================================ the world rules, from sources

def test_rules_from_source_start_in_a_solid(tmp_path):
    src = two_rooms(tmp_path, a=["111111", "111111", "WWWWD1", "111111", "111111"])
    msg = run_err("export", src, "--tiled")
    assert re.search(r"a\.map:19:2: E_WORLD: start-solid: the start in a is at cell 1,2, which is solid", msg), msg


def test_rules_from_source_start_on_a_crate(tmp_path):
    legend = LEGEND.replace(f"@ {P}/props/hero.png+b", f"@ {P}/props/crate.png+b")
    src = game(tmp_path, {"a": room_text(OPEN5, ["......", "......", ".@....", "......", "......"], legend=legend)},
               {"layout": ["a"], "start": {"room": "a", "at": "@"}})
    msg = run_err("export", src, "--tiled")
    assert "start-solid" in msg


def test_rules_from_source_marker_on_the_start_is_fine(tmp_path):
    src = two_rooms(tmp_path)
    assert run("export", src, "--tiled") == 0


def test_rules_from_source_door_walled_in(tmp_path):
    b = ["WWWWWW", "WWWWWW", "WWdWWW", "WWWWWW", "W1111W"]
    src = two_rooms(tmp_path, b=b)
    msg = run_err("export", src, "--tiled")
    assert re.search(r"b\.map:19:3: E_WORLD: door-arrival: door 'd' in b has no walkable cell beside it", msg), msg


def test_rules_from_source_door_unreachable(tmp_path):
    a = ["111W11", "111W11", "111WD1", "111W11", "111W11"]
    src = two_rooms(tmp_path, a=a)
    msg = run_err("export", src, "--tiled")
    assert "door-unreachable: door 'D' in a can't be reached from the start" in msg
    assert "door-unreachable: door 'd' in b" in msg


def test_rules_from_source_no_start(tmp_path):
    src = two_rooms(tmp_path, src={"layout": ["a"], "doors": [["a D", "b d"]]})
    msg = run_err("export", src, "--tiled")
    assert "E_WORLD: start-count: the world has no start" in msg and '"start": {"room": ROOM, "at": CHAR}' in msg
    assert "world.src.json" in msg


def test_rules_from_source_edge_warning_located_in_the_map(tmp_path, capsys):
    a = ["111111"] * 5
    b = ["W11111", "W11111", "111111", "111111", "111111"]
    src = game(tmp_path, {"a": room_text(a, ["......", "......", ".@....", "......", "......"]), "b": room_text(b)},
               {"layout": ["a b"], "start": {"room": "a", "at": "@"}})
    assert run("export", src, "--tiled") == 0
    out = capsys.readouterr().out
    assert re.search(r"WARNING: \S*rooms/a\.map:17:6: edge-one-side: a's east edge from cell 5,0 \(2 cells\)", out), out


def test_rules_from_source_room_unreachable_warning(tmp_path, capsys):
    a = ["11111W"] * 5
    b = ["W11111"] * 5
    src = game(tmp_path, {"a": room_text(a, ["......", "......", ".@....", "......", "......"]), "b": room_text(b)},
               {"layout": ["a b"], "start": {"room": "a", "at": "@"}})
    assert run("export", src, "--tiled") == 0
    assert "room-unreachable: no walkable cell of b can be reached from the start" in capsys.readouterr().out


def test_rules_from_source_across_an_edge_is_reachable(tmp_path):
    a = ["111111"] * 5
    b = ["111111", "111111", "1111D1", "111111", "111111"]
    i = ["WWWWWW", "W1111W", "W1111W", "W1111W", "WWdWWW"]
    src = game(tmp_path, {"a": room_text(a, ["......", "......", ".@....", "......", "......"]), "b": room_text(b),
                          "i": room_text(i)},
               {"layout": ["a b"], "start": {"room": "a", "at": "@"}, "doors": [["b D", "i d"]]})
    assert run("export", src, "--tiled") == 0


# ================================================================ check on world sources

def test_check_world_ok(tmp_path, capsys):
    src = two_rooms(tmp_path)
    assert run("check", src) == 0
    out = capsys.readouterr().out
    assert f"ok   {src}: 1 room placed, interior b, 1 door pair, start in a" in out
    assert not (src.parent / "world.world").exists() and not list((src.parent / "rooms").glob("*.tmj"))


def test_check_world_fail_lists_every_error(tmp_path, capsys):
    src = two_rooms(tmp_path, a=["111111", "11?111", "1111D1", "11111!", "111111"])
    assert run("check", src) == 1
    out = capsys.readouterr().out
    assert f"FAIL {src}: 2 error(s)" in out and out.count("E_UNKNOWN_KEY") == 2


def test_check_world_rule_error(tmp_path, capsys):
    src = two_rooms(tmp_path, a=["111111", "111111", "WWWWD1", "111111", "111111"])
    assert run("check", src) == 1
    assert "start-solid" in capsys.readouterr().out


def test_check_world_warnings_counted(tmp_path, capsys):
    a = ["111111"] * 5
    b = ["W11111", "W11111", "111111", "111111", "111111"]
    src = game(tmp_path, {"a": room_text(a, ["......", "......", ".@....", "......", "......"]), "b": room_text(b)},
               {"layout": ["a b"], "start": {"room": "a", "at": "@"}})
    assert run("check", src, src.parent / "rooms" / "a.map") == 0
    out = capsys.readouterr().out
    assert "WARNING: " in out and "edge-one-side" in out and re.search(r"2 files, 0 frames, [1-9]\d* warning", out)


def test_check_directory_finds_world_sources(tmp_path, capsys):
    src = two_rooms(tmp_path)
    assert run("check", src.parent) == 0
    out = capsys.readouterr().out
    assert f"ok   {src}:" in out and "a.map" in out and "b.map" in out


def test_check_world_agrees_with_export(tmp_path, capsys):
    src = two_rooms(tmp_path, a=["111111", "11?111", "1111D1", "111111", "111111"])
    run("check", src)
    checked = capsys.readouterr().out
    msg = run_err("export", src, "--tiled")
    for line in errors(msg):
        body = line.split("export: ", 1)[-1]
        assert body in checked, body


def test_check_world_tile_option(tmp_path, capsys):
    src = two_rooms(tmp_path)
    assert run("check", src, "--tile", "16x16") == 0


def test_check_world_tileset_option(tmp_path, capsys):
    loose = tmp_path / "loose"
    loose.mkdir()
    art((16, 16), (1, 2, 3)).save(loose / "stone.png")
    (loose / "stone.tsj").write_text(json.dumps({
        "type": "tileset", "name": "stone", "tilewidth": 16, "tileheight": 16, "tilecount": 1, "columns": 0,
        "tiles": [{"id": 0, "image": "stone.png", "imagewidth": 16, "imageheight": 16}]}))
    legend = LEGEND + "s ../../loose/stone.png\n"
    src = game(tmp_path, {"a": room_text(["ss1111"] + ["111111"] * 4, ["......", "......", ".@....", "......",
                                                                          "......"], legend=legend)},
               {"layout": ["a"], "start": {"room": "a", "at": "@"}})
    assert run("check", src) == 1
    capsys.readouterr()
    assert run("check", src, "--tileset", loose / "stone.tsj") == 0


def test_check_map_alone_is_unchanged(tmp_path, capsys):
    src = two_rooms(tmp_path)
    assert run("check", src.parent / "rooms" / "a.map") == 0
    assert "ok   " in capsys.readouterr().out


# ================================================================ export's arguments

def test_export_sources_and_px_do_not_mix(tmp_path):
    src = two_rooms(tmp_path)
    (tmp_path / "x.px").write_text("k #000000\n\nk\n")
    assert "go in separate exports" in run_err("export", src, tmp_path / "x.px", "--tiled")


def test_export_sources_take_no_tsj(tmp_path):
    src = two_rooms(tmp_path)
    assert "takes no X.tsj" in run_err("export", src, "--tiled", tmp_path / "t.tsj")


def test_export_sources_need_tiled(tmp_path):
    src = two_rooms(tmp_path)
    assert "takes no X.tsj" in run_err("export", src, "--frames", tmp_path / "f")


def test_export_frames_tiled_needs_a_name(tmp_path):
    (tmp_path / "x.px").write_text("k #000000\n\nk\n")
    assert "name the tileset to write" in run_err("export", tmp_path / "x.px", "--tiled")


def test_export_tile_and_tileset_are_for_sources(tmp_path):
    (tmp_path / "x.px").write_text("k #000000\n\nk\n")
    assert "for world sources" in run_err("export", tmp_path / "x.px", "--frames", tmp_path / "f", "--tile", "8")


def test_export_nothing(tmp_path):
    assert "give FILE|DIR" in run_err("export")


def test_export_px_tiled_still_works(tmp_path):
    (tmp_path / "x.px").write_text("k #000000\nw #ffffff\n@frame a\nkw\nwk\n@frame b\nww\nkk\n")
    assert run("export", tmp_path / "x.px", "--tiled", tmp_path / "t.tsj") == 0
    assert load(tmp_path / "t.tsj")["tilecount"] == 2


def test_help_documents_worlds():
    doc = " ".join(pxart.__doc__.split())
    for s in ("export world.src.json|ROOM.map... --tiled", "rooms/NAME.map -> rooms/NAME.tmj",
              "a room only doors name is an interior", "Object ids are stable", "never reused",
              "tests/fixtures/world_rules/", "E_GENERATED", "A world.src.json is checked as export --tiled compiles it",
              "a PNG by a tile's png property, a .px frame by its pixels"):
        assert s in doc, s
    codes = doc.split("ERROR CODES", 1)[1]
    for c in ("E_MAP_SIZE", "E_TILESET", "E_GENERATED", "E_WORLD", "E_DOOR", "E_START"):
        assert c in codes, c


def test_every_new_error_code_is_used():
    src = pathlib.Path(pxart.__file__).read_text()
    for c in ("E_MAP_SIZE", "E_TILESET", "E_GENERATED", "E_WORLD", "E_DOOR", "E_START"):
        assert src.count(f'"{c}"') >= 1, c


def test_issue_prints_line_and_col():
    assert str(pxart.Issue("E_X", "m", "a.map", 3, col=7)) == "a.map:3:7: E_X: m"
    assert str(pxart.Issue("E_X", "m", "a.map", 3)) == "a.map:3: E_X: m"
    assert str(pxart.Issue("E_X", "m", "a.map", None, col=7)) == "a.map: E_X: m"
