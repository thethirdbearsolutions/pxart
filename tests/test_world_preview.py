"""GAMES-334 (W9 of GAMES-286, decision 13): pxart world draws a compiled world, and pxart check reads compiled
worlds (.world, or a lone .tmj). Both run world_rules on the Tiled files as they are, the one path the compile runs
(ADR 0008), so a Tiled-authored world is checked and drawn by the same rules as a compiled one.

Redundant on purpose: every shared fixture is run in memory, from disk through check, and drawn; the lighthouse
example is pinned as golden pictures and from the rules' side; the drawing is pinned pixel by pixel on synthetic
worlds."""
import json
import math
import pathlib
import re
import shutil
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pxart  # noqa: E402
from test_worlds import scene_render, same_pixels, tiled_render  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
RULES = FIXTURES / "world_rules"
LIGHTHOUSE = FIXTURES / "lighthouse"
GOLDEN = LIGHTHOUSE / "expected" / "world-preview.png"
GOLDEN_1X = LIGHTHOUSE / "expected" / "world-preview-1x.png"
KEYS = ("level", "code", "room", "name", "cell")
ROOMS = ("shore", "point", "cove", "tower")
M, G, L = pxart.WP_MARGIN, pxart.WP_GAP, pxart.WP_LABEL
FLOOR, WALL, HERO = (236, 212, 158, 255), (90, 83, 83, 255), (60, 120, 200, 255)


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


def canon(ds):
    return sorted(json.dumps(d, sort_keys=True) for d in ds)


def as_dicts(issues):
    return [dict(zip(KEYS, i.key())) for i in issues]


# ================================================================ writing worlds to disk

def fixture_files():
    return sorted(p for p in RULES.glob("*.json") if p.name != "rules.json")


FIXTURE_NAMES = [p.stem for p in fixture_files()]


def materialize(f, where):
    """A shared fixture on disk: each of its files at its path under where, and the shared tilesets beside them, as
    SPEC.md resolves them (a path not in files is read relative to the fixture folder)."""
    where.mkdir(parents=True, exist_ok=True)
    for name in ("tiles.tsj", "tiles.png", "props.tsj", "log.png"):
        shutil.copy(RULES / name, where / name)
    for p, data in f["files"].items():
        dst = where / p
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(data, indent=1))
    return where / f["world"]


def fixture(name):
    return load(RULES / f"{name}.json")


def room(rows, objects=(), tilesets=None, props=None, **extra):
    """A .tmj from rows of '.' (floor, gid 1), '#' (wall, gid 2), 'h' (half, gid 5), ' ' (empty), with a 'world'
    object layer."""
    gid = {".": 1, "#": 2, "h": 5, " ": 0}
    w, h = len(rows[0]), len(rows)
    t = {"type": "map", "version": "1.10", "orientation": "orthogonal", "renderorder": "right-down",
         "width": w, "height": h, "tilewidth": 16, "tileheight": 16, "infinite": False, "nextlayerid": 3,
         "nextobjectid": 20, "tilesets": tilesets or [{"firstgid": 1, "source": "../tiles.tsj"}],
         "layers": [{"id": 1, "name": "ground", "type": "tilelayer", "width": w, "height": h, "x": 0, "y": 0,
                     "opacity": 1, "visible": True, "data": [gid[c] for r in rows for c in r]},
                    {"id": 2, "name": "world", "type": "objectgroup", "draworder": "index", "x": 0, "y": 0,
                     "opacity": 1, "visible": True, "objects": list(objects)}]}
    if props:
        t["properties"] = props
    t.update(extra)
    return t


def door(oid, name, cx, cy, target, entry, w=1, h=1, **more):
    props = [{"name": "entry", "type": "string", "value": entry},
             {"name": "target", "type": "file", "value": target}]
    props += [{"name": k, "type": "string", "value": v} for k, v in more.items()]
    return {"id": oid, "name": name, "type": "door", "x": cx * 16, "y": cy * 16, "width": w * 16, "height": h * 16,
            "rotation": 0, "visible": True, "properties": props}


def start(oid, cx, cy):
    return {"id": oid, "name": "start", "type": "start", "point": True, "x": cx * 16 + 8, "y": (cy + 1) * 16,
            "width": 0, "height": 0, "rotation": 0, "visible": True}


def marker(oid, name, cx, cy):
    return {"id": oid, "name": name, "gid": 4, "x": cx * 16, "y": (cy + 1) * 16, "width": 16, "height": 16,
            "rotation": 0, "visible": True}


def world(maps):
    return {"type": "world", "onlyShowAdjacentMaps": False,
            "maps": [{"fileName": f"rooms/{n}.tmj", "x": x, "y": y, "width": w, "height": h} for n, x, y, w, h in maps]}


def write_world(where, maps, rooms, name="world.world"):
    """rooms: {id: .tmj dict}; maps: [(id, x, y)] placed (their size from the room). Tilesets are the shared
    fixtures'."""
    where.mkdir(parents=True, exist_ok=True)
    for n in ("tiles.tsj", "tiles.png", "props.tsj", "log.png"):
        shutil.copy(RULES / n, where / n)
    (where / "rooms").mkdir(exist_ok=True)
    for rid, t in rooms.items():
        (where / "rooms" / f"{rid}.tmj").write_text(json.dumps(t, indent=1))
    sized = [(n, x, y, rooms[n]["width"] * 16 if n in rooms else 64, rooms[n]["height"] * 16 if n in rooms else 64)
             for n, x, y in maps]
    (where / name).write_text(json.dumps(world(sized), indent=1))
    return where / name


A_ROWS = [".....",
          ".....",
          ".....",
          "....#"]
B_ROWS = [".....",
          ".....",
          "#....",
          "#...."]


def two_room_world(tmp_path, a_objs=None, b_objs=None, a_rows=A_ROWS, b_rows=B_ROWS, bx=80, by=0):
    """a at 0,0 and b beside it (80,0 by default): a's door D at cell 3,1 and b's E at 1,1 pair up; the start in a.
    Across the shared edge: rows 0 and 1 are walkable on both sides, row 2 only in a (edge-one-side), row 3 on
    neither (a wall)."""
    a_objs = [start(1, 1, 1), door(2, "D", 3, 1, "b.tmj", "E")] if a_objs is None else a_objs
    b_objs = [door(1, "E", 1, 1, "a.tmj", "D")] if b_objs is None else b_objs
    return write_world(tmp_path / "w", [("a", 0, 0), ("b", bx, by)],
                       {"a": room(a_rows, a_objs), "b": room(b_rows, b_objs)})


def preview(path, scale=2):
    issues, model, shown = pxart.load_tiled(str(path))
    img, missing = pxart.world_preview(model, issues, shown, scale)
    return img, model, issues


def boxes(model, scale):
    return {pathlib.PurePath(p).stem: b for p, b in pxart.world_layout(model, scale)[0].items()}


def px(img, x, y):
    return img.getpixel((int(x), int(y)))


def pixels(img):
    """An RGBA image's pixels as tuples, in order (getdata, without its deprecation)."""
    return list(zip(*[iter(img.convert("RGBA").tobytes())] * 4))


def colors(img):
    return set(pixels(img))


# ================================================================ check on compiled worlds: every shared fixture

@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_check_fixture_from_disk_gives_exactly_the_expected_issues(name, tmp_path, monkeypatch):
    f = fixture(name)
    wp = materialize(f, tmp_path / "f")
    monkeypatch.chdir(tmp_path / "f")
    issues, model, shown = pxart.load_tiled(f["world"])
    assert canon(as_dicts(issues)) == canon(f["expect"]), name


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_check_fixture_from_disk_by_absolute_path_too(name, tmp_path):
    f = fixture(name)
    wp = materialize(f, tmp_path / "f")
    issues, _, _ = pxart.load_tiled(str(wp))
    assert canon(as_dicts(issues)) == canon(f["expect"]), name


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_check_fixture_from_disk_matches_the_in_memory_runner(name, tmp_path, monkeypatch):
    # one path: the files on disk and the fixture's in-memory world give the same issues, in the same order
    f = fixture(name)
    materialize(f, tmp_path / "f")
    monkeypatch.chdir(tmp_path / "f")
    on_disk, _, _ = pxart.load_tiled(f["world"])
    in_memory = pxart.world_rules_files(f["files"], f["world"], str(RULES))
    assert [i.key() for i in on_disk] == [i.key() for i in in_memory], name
    assert [i.msg for i in on_disk] == [i.msg for i in in_memory], name


LINE_RE = re.compile(r"^     (WARNING: )?(\S+): (E_WORLD: )?([a-z-]+)(?: \[(.*?)\])?: (.*)$")


def parse_check(out):
    """check's issue lines as dicts (level, code, file, name, cell)."""
    got = []
    for line in out.splitlines():
        m = LINE_RE.match(line)
        if not m or line.startswith("     note:"):
            continue
        warn, path, err, code, tag, msg = m.groups()
        name, cell = None, None
        for part in (tag.split(", ", 1) if tag and not tag.startswith("cell ") else [tag] if tag else []):
            if part.startswith("cell "):
                cell = [int(v) for v in part[5:].split(",")]
            else:
                name = part
        if tag and ", cell " in tag:
            name, c = tag.split(", cell ")
            cell = [int(v) for v in c.split(",")]
        got.append({"level": "warning" if warn else "error", "code": code, "file": path, "name": name, "cell": cell})
    return got


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_check_cli_on_every_fixture_prints_exactly_the_expected_issues(name, tmp_path, capsys, monkeypatch):
    f = fixture(name)
    materialize(f, tmp_path / "f")
    monkeypatch.chdir(tmp_path / "f")
    code = run("check", f["world"])
    out = capsys.readouterr().out
    errors = [e for e in f["expect"] if e["level"] == "error"]
    assert code == (1 if errors else 0), (name, out)
    assert out.startswith(("FAIL " if errors else "ok   ") + f["world"] + ": "), out
    got = parse_check(out)
    want = [{"level": e["level"], "code": e["code"], "name": e["name"] or None, "cell": e["cell"]} for e in f["expect"]]
    assert canon([{k: g[k] for k in ("level", "code", "name", "cell")} for g in got]) == canon(want), (name, out)
    # each line names the file: the room's .tmj, or the .world for an issue with no loaded room
    live = {pathlib.PurePath(p).stem for p in f["files"] if p.endswith(".tmj")}
    for g in got:
        assert g["file"].endswith((".tmj", ".world")), g
    for e in f["expect"]:
        if e["room"] and e["room"] in live and e["code"] not in ("room-missing",):
            assert any(g["code"] == e["code"] and pathlib.PurePath(g["file"]).stem == e["room"] for g in got), (e, out)


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_check_cli_counts_lines_per_level(name, tmp_path, capsys, monkeypatch):
    f = fixture(name)
    materialize(f, tmp_path / "f")
    monkeypatch.chdir(tmp_path / "f")
    run("check", f["world"])
    out = capsys.readouterr().out
    n_err = sum(e["level"] == "error" for e in f["expect"])
    n_warn = sum(e["level"] == "warning" for e in f["expect"])
    assert out.count(": E_WORLD: ") == n_err, out
    assert out.count("     WARNING: ") == n_warn, out
    if n_err:
        assert f"FAIL {f['world']}: {n_err} error(s)" in out
    else:
        assert f"ok   {f['world']}: " in out


def test_there_are_fixtures_to_check():
    assert len(FIXTURE_NAMES) >= 30
    assert any(n.startswith("valid-") for n in FIXTURE_NAMES)


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_the_model_hook_changes_nothing(name):
    f = fixture(name)
    plain = pxart.world_rules_files(f["files"], f["world"], str(RULES))
    model = {}
    read = lambda p: f["files"].get(p) if p in f["files"] else pxart.read_json(str(RULES / p))  # noqa: E731
    hooked = pxart.world_rules(f["world"], read, model)
    assert [i.key() for i in plain] == [i.key() for i in hooked]
    assert set(model) == {"world_path", "world", "rooms", "placed", "live", "partner", "start", "reached"}


def test_one_path_check_world_and_compile_all_call_world_rules(tmp_path, monkeypatch, capsys):
    # ADR 0008: check on a source, check on the compiled world and the preview all run the one world_rules
    d = tmp_path / "lh"
    shutil.copytree(LIGHTHOUSE, d)
    monkeypatch.chdir(d)
    calls = []
    real = pxart.world_rules

    def spy(*a, **k):
        calls.append(a[0])
        return real(*a, **k)
    monkeypatch.setattr(pxart, "world_rules", spy)
    assert run("check", "world.src.json") == 0
    assert calls == ["world.world"]
    assert run("export", "world.src.json", "--tiled") == 0
    assert calls == ["world.world"] * 2
    assert run("check", "world.world") == 0
    assert calls == ["world.world"] * 3
    assert run("world", "world.world", "-o", "p.png") == 0
    assert calls == ["world.world"] * 4


# ================================================================ check on the lighthouse, compiled

@pytest.fixture
def lh(tmp_path, monkeypatch):
    d = tmp_path / "lighthouse"
    shutil.copytree(LIGHTHOUSE, d)
    monkeypatch.chdir(d)
    assert run("export", "world.src.json", "--tiled") == 0
    return d


LH_SUMMARY = "3 rooms placed, interior tower, 1 door pair, start in shore"
LH_EDGE = ("rooms/cove.tmj: edge-one-side [north, cell 1,0]: cove's north edge from cell 1,0 (1 cell) is walkable, "
           "and across it shore is solid: walking over puts the player in a solid")


def test_check_compiled_lighthouse_is_ok_with_its_edge_warning(lh, capsys):
    capsys.readouterr()
    assert run("check", "world.world") == 0
    assert capsys.readouterr().out == f"ok   world.world: {LH_SUMMARY}\n     WARNING: {LH_EDGE}\n"


def test_check_compiled_says_what_the_source_check_says(lh, capsys):
    capsys.readouterr()
    run("check", "world.src.json")
    src = capsys.readouterr().out
    run("check", "world.world")
    out = capsys.readouterr().out
    assert f"world.src.json: {LH_SUMMARY}" in src and f"world.world: {LH_SUMMARY}" in out
    # the same rule, found by the same code, located in the source there and in the compiled room here
    assert "rooms/cove.map:9:2: edge-one-side: cove's north edge from cell 1,0" in src
    assert "rooms/cove.tmj: edge-one-side [north, cell 1,0]: cove's north edge from cell 1,0" in out


def test_check_compiled_lighthouse_issues_equal_the_compile_rules(lh):
    issues, model, shown = pxart.load_tiled("world.world")
    assert as_dicts(issues) == [{"level": "warning", "code": "edge-one-side", "room": "cove", "name": "north",
                                 "cell": [1, 0]}]
    assert shown == "world.world"


def test_check_the_design_hand_compiled_world(capsys, monkeypatch):
    # the design's own example/ files (expected/): read as they are, the same verdict
    monkeypatch.chdir(LIGHTHOUSE / "expected")
    assert run("check", "world.world") == 0
    out = capsys.readouterr().out
    assert out.startswith(f"ok   world.world: {LH_SUMMARY}\n") and "edge-one-side [north, cell 1,0]" in out


def test_check_model_of_the_lighthouse(lh):
    _, model, _ = pxart.load_tiled("world.world")
    assert [r.id for r in model["placed"]] == ["shore", "point", "cove"]
    assert [r.id for r in model["live"]] == ["shore", "point", "cove", "tower"]
    assert model["start"][0].id == "shore" and model["start"][1] == (5, 7)
    assert len(model["partner"]) == 2
    assert model["reached"] and any(p.endswith("tower.tmj") for p, _ in model["reached"])


def test_check_a_placed_room_alone_is_refused_naming_its_world(lh, capsys):
    capsys.readouterr()
    assert run("check", "rooms/cove.tmj") == 1
    out = capsys.readouterr().out
    assert out.startswith("FAIL rooms/cove.tmj: 1 error(s)")
    assert "E_WORLD: rooms/cove.tmj is a room of world.world (placed)" in out and "give the world (world.world)" in out


def test_check_an_interior_alone_is_refused_naming_its_world(lh, capsys):
    capsys.readouterr()
    assert run("check", "rooms/tower.tmj") == 1
    assert "rooms/tower.tmj is a room of world.world (an interior)" in capsys.readouterr().out


def test_check_a_room_alone_is_refused_from_another_directory(lh, capsys, monkeypatch):
    monkeypatch.chdir(lh / "rooms")
    capsys.readouterr()
    assert run("check", "cove.tmj") == 1
    assert "cove.tmj is a room of ../world.world (placed)" in capsys.readouterr().out


def test_check_a_room_alone_is_refused_by_absolute_path(lh, capsys):
    capsys.readouterr()
    assert run("check", lh / "rooms" / "point.tmj") == 1
    assert "is a room of" in capsys.readouterr().out


def test_check_a_lone_room_is_a_world_of_one(tmp_path, capsys, monkeypatch):
    d = tmp_path / "lone"
    write_world(d, [], {"a": room(A_ROWS, [start(1, 1, 1)])})
    (d / "world.world").unlink()
    monkeypatch.chdir(d)
    assert run("check", "rooms/a.tmj") == 0
    assert capsys.readouterr().out == "ok   rooms/a.tmj: 1 room placed, 0 door pairs, start in a\n"


def test_check_a_lone_room_with_an_interior(tmp_path, capsys, monkeypatch):
    d = tmp_path / "lone"
    write_world(d, [], {"a": room(A_ROWS, [start(1, 1, 1), door(2, "D", 2, 0, "b.tmj", "E")]),
                        "b": room(B_ROWS, [door(1, "E", 2, 3, "a.tmj", "D")])})
    (d / "world.world").unlink()
    monkeypatch.chdir(d)
    assert run("check", "rooms/a.tmj") == 0
    assert capsys.readouterr().out == "ok   rooms/a.tmj: 1 room placed, interior b, 1 door pair, start in a\n"


def test_check_a_lone_room_without_a_start_fails(tmp_path, capsys, monkeypatch):
    d = tmp_path / "lone"
    write_world(d, [], {"a": room(A_ROWS)})
    (d / "world.world").unlink()
    monkeypatch.chdir(d)
    assert run("check", "rooms/a.tmj") == 1
    out = capsys.readouterr().out
    assert out.startswith("FAIL rooms/a.tmj: 1 error(s)")
    assert "rooms/a.tmj: E_WORLD: start-count: the world has no start" in out
    assert "a.tmj.world" not in out  # the one-room world's name is never said


def test_check_a_lone_tiled_room_made_in_tiled(tmp_path, capsys):
    # no source property: a Tiled-authored map, checked as it is
    d = tmp_path / "tiled"
    write_world(d, [], {"a": room(A_ROWS, [start(1, 1, 1)])})
    (d / "world.world").unlink()
    assert "properties" not in load(d / "rooms" / "a.tmj")
    assert run("check", d / "rooms" / "a.tmj") == 0


def test_check_world_and_source_together(lh, capsys):
    capsys.readouterr()
    assert run("check", "world.src.json", "world.world") == 0
    out = capsys.readouterr().out
    assert out.count(LH_SUMMARY) == 2 and "2 files, 0 frames, 3 warnings" in out  # the source's note counts


def test_check_world_and_a_sprite_together(lh, capsys, tmp_path):
    p = tmp_path / "s.px"
    p.write_text("k #000000\nkk\n")
    capsys.readouterr()
    assert run("check", "world.world", p) == 0
    out = capsys.readouterr().out
    assert f"ok   world.world: {LH_SUMMARY}" in out and "2 files, 1 frame, 1 warning" in out


def test_check_a_broken_world_among_others_fails_the_run(lh, capsys, tmp_path):
    f = fixture("door-not-paired")
    wp = materialize(f, tmp_path / "bad")
    capsys.readouterr()
    assert run("check", "world.world", wp) == 1
    out = capsys.readouterr().out
    assert f"ok   world.world" in out and "FAIL " in out and ", 1 failed" in out


def test_check_directory_still_means_world_sources(lh, capsys, monkeypatch):
    # a DIR stands for world sources (and .px, .map); a compiled .world under it isn't checked a second time
    monkeypatch.chdir(lh.parent)
    capsys.readouterr()
    assert run("check", "lighthouse", "--exclude", "lighthouse-keeper") == 0
    out = capsys.readouterr().out
    assert "world.src.json: " + LH_SUMMARY in out and "ok   lighthouse/world.world" not in out


# ---- check: files that aren't compiled worlds

def test_check_world_missing_file(tmp_path, capsys):
    assert run("check", tmp_path / "nope.world") == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "E_FILE" in out


def test_check_world_not_json(tmp_path, capsys):
    p = tmp_path / "w.world"
    p.write_text("{nope")
    assert run("check", p) == 1
    out = capsys.readouterr().out
    assert "E_WORLD: not JSON" in out and f"{p.as_posix()}:1:2" in out


def test_check_world_not_a_world(tmp_path, capsys):
    p = tmp_path / "w.world"
    p.write_text("[1, 2]")
    assert run("check", p) == 1
    assert 'a Tiled world is a JSON object with a "maps" list' in capsys.readouterr().out


def test_check_world_maps_not_a_list(tmp_path, capsys):
    p = tmp_path / "w.world"
    p.write_text('{"type": "world", "maps": {}}')
    assert run("check", p) == 1
    assert '"maps" list' in capsys.readouterr().out


def test_check_world_patterns_are_refused(tmp_path, capsys):
    p = tmp_path / "w.world"
    p.write_text('{"type": "world", "maps": [], "patterns": [{"regexp": "r(\\\\d+).tmj"}]}')
    assert run("check", p) == 1
    assert "places its maps by 'patterns'" in capsys.readouterr().out


def test_check_world_with_no_maps_says_no_start(tmp_path, capsys):
    p = tmp_path / "w.world"
    p.write_text('{"type": "world", "maps": []}')
    assert run("check", p) == 1
    out = capsys.readouterr().out
    assert f"{p.as_posix()}: E_WORLD: start-count: the world has no start" in out


def test_check_tmj_not_a_map(tmp_path, capsys):
    p = tmp_path / "a.tmj"
    p.write_text('{"type": "tileset"}')
    assert run("check", p) == 1
    assert 'a Tiled map is a JSON object with "type": "map"' in capsys.readouterr().out


@pytest.mark.parametrize("change, said", [
    ({"infinite": True}, "untick Infinite"),
    ({"orientation": "isometric"}, "orthogonal maps only"),
])
def test_check_unsupported_map_formats(tmp_path, capsys, change, said):
    d = tmp_path / "w"
    wp = two_room_world(tmp_path)
    t = load(d / "rooms" / "b.tmj")
    t.update(change)
    (d / "rooms" / "b.tmj").write_text(json.dumps(t))
    assert run("check", wp) == 1
    out = capsys.readouterr().out
    assert "E_WORLD" in out and said in out and "b.tmj" in out


def test_check_base64_tile_data_names_the_tiled_setting(tmp_path, capsys):
    wp = two_room_world(tmp_path)
    t = load(tmp_path / "w" / "rooms" / "a.tmj")
    t["layers"][0]["data"], t["layers"][0]["encoding"] = "AQAAAA==", "base64"
    (tmp_path / "w" / "rooms" / "a.tmj").write_text(json.dumps(t))
    assert run("check", wp) == 1
    assert "Tile Layer Format: CSV" in capsys.readouterr().out


def test_check_base64_in_a_lone_tmj(tmp_path, capsys):
    t = room(A_ROWS, [start(1, 1, 1)])
    t["layers"][0]["data"] = "AQAAAA=="
    p = tmp_path / "a.tmj"
    p.write_text(json.dumps(t))
    assert run("check", p) == 1
    assert "Tile Layer Format: CSV" in capsys.readouterr().out


def test_check_world_source_still_compiles_in_memory(lh, capsys):
    # check on a source is W2's (the compile, in memory); check on the compiled files is this: both, one rule path
    capsys.readouterr()
    before = (lh / "world.world").read_bytes()
    assert run("check", "world.src.json") == 0
    assert (lh / "world.world").read_bytes() == before


def test_check_warning_only_world_exits_0(tmp_path, capsys):
    wp = two_room_world(tmp_path)
    assert run("check", wp) == 0
    out = capsys.readouterr().out
    assert "ok   " in out and "WARNING: " in out and "edge-one-side" in out


def test_check_line_without_a_name_has_just_the_cell(tmp_path, capsys):
    wp = two_room_world(tmp_path, a_objs=[{**start(1, 4, 3), "name": ""}, door(2, "D", 3, 1, "b.tmj", "E")])
    assert run("check", wp) == 1
    assert "E_WORLD: start-solid [cell 4,3]: " in capsys.readouterr().out


def test_rule_line_formats():
    i = pxart.RuleIssue("door-pair", "a", "D", (3, 1), "m")
    assert pxart.rule_line(i, {}, "w.world") == "w.world: E_WORLD: door-pair [D, cell 3,1]: m"
    i = pxart.RuleIssue("edge-one-side", "a", "north", (1, 0), "m")
    assert pxart.rule_line(i, {}, "w.world") == "w.world: edge-one-side [north, cell 1,0]: m"
    i = pxart.RuleIssue("start-count", None, None, None, "m")
    assert pxart.rule_line(i, {}, "w.world") == "w.world: E_WORLD: start-count: m"
    i = pxart.RuleIssue("tiled-unsupported", "a", "rotation", None, "m")
    assert pxart.rule_line(i, {}, "w.world") == "w.world: E_WORLD: tiled-unsupported [rotation]: m"


# ================================================================ the preview: golden pictures of the lighthouse

def lighthouse_preview(lh, out, *extra):
    assert run("world", "world.world", "-o", out, *extra) == 0
    return Image.open(out).convert("RGBA")


def test_golden_lighthouse_preview(lh):
    got = lighthouse_preview(lh, "p.png")
    want = Image.open(GOLDEN).convert("RGBA")
    assert same_pixels(got, want), "regenerate with: cd a compiled lighthouse; pxart world world.world -o <GOLDEN>"


def test_golden_lighthouse_preview_scale_1(lh):
    got = lighthouse_preview(lh, "p.png", "--scale", "1")
    assert same_pixels(got, Image.open(GOLDEN_1X).convert("RGBA"))


def test_golden_is_the_default_scale(lh):
    a = lighthouse_preview(lh, "a.png")
    b = lighthouse_preview(lh, "b.png", "--scale", "2")
    assert same_pixels(a, b)


def test_golden_sizes(lh):
    img = Image.open(GOLDEN)
    one = Image.open(GOLDEN_1X)
    # three placed columns' worth: shore|point, the interior column; 2x rooms are 512x384
    assert img.width == M + 512 + G + 512 + 2 * G + 512 + M
    assert one.width == max(M + 256 + G + 256 + 2 * G + 256 + M, one.width)
    assert img.height > M + L + 384 + G + 384


def test_lighthouse_preview_output_lines(lh, capsys):
    capsys.readouterr()
    assert run("world", "world.world", "-o", "p.png") == 0
    assert capsys.readouterr().out == (f"[1] WARNING: {LH_EDGE}\n"
                                       f"wrote p.png: world.world, {LH_SUMMARY}; 1 warning, tagged [n] in the "
                                       "picture\n")


def test_lighthouse_preview_rooms_are_where_the_world_puts_them(lh):
    _, model, _ = pxart.load_tiled("world.world")
    b = boxes(model, 2)
    assert b["shore"] == (M, M + L, 512, 384)
    assert b["point"] == (M + 512 + G, M + L, 512, 384)
    assert b["cove"] == (M, M + L + 384 + G, 512, 384)
    assert b["tower"] == (M + 512 + G + 512 + 2 * G, M + L, 512, 384)  # the interior, to the right


@pytest.mark.parametrize("room", ROOMS)
def test_lighthouse_preview_draws_each_room_as_tiled_does(lh, room):
    # every pixel of a room that no overlay touches is the room's own render, scaled
    img, model, issues = preview("world.world")
    b = boxes(model, 2)[room]
    r = next(x for x in model["live"] if x.id == room)
    art = pxart.tiled_room_image(r).resize((b[2], b[3]), Image.NEAREST)
    bg = Image.new("RGBA", art.size, pxart.WP_ROOM)
    bg.alpha_composite(art)
    crop = img.crop((b[0], b[1], b[0] + b[2], b[1] + b[3]))
    same = sum(1 for p, q in zip(pixels(crop), pixels(bg)) if p == q)
    assert same / (b[2] * b[3]) > 0.97, (room, same)


@pytest.mark.parametrize("room", ROOMS)
def test_tiled_room_image_equals_the_parity_renderer_and_scene(lh, room, tmp_path):
    _, model, _ = pxart.load_tiled("world.world")
    r = next(x for x in model["live"] if x.id == room)
    mine = pxart.tiled_room_image(r)
    assert same_pixels(mine, tiled_render(lh / "rooms" / f"{room}.tmj", hide=()))
    assert same_pixels(mine, scene_render(lh / "rooms" / f"{room}.map", tmp_path / "s.png"))


def test_lighthouse_preview_start_is_outlined_green(lh):
    img, model, _ = preview("world.world")
    r, c = model["start"]
    x0, y0, x1, y1 = pxart.cell_box(boxes(model, 2)["shore"], r, c, 2)
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1), ((x0 + x1) // 2, y0)):
        assert px(img, x, y) == pxart.WP_START


def test_lighthouse_preview_door_link_crosses_to_the_tower(lh):
    img, model, _ = preview("world.world")
    b = boxes(model, 2)
    point = next(r for r in model["live"] if r.id == "point")
    tower = next(r for r in model["live"] if r.id == "tower")
    d0 = pxart.door_box(b["point"], point, point.doors[0], 2)
    d1 = pxart.door_box(b["tower"], tower, tower.doors[0], 2)
    for x, y in ((d0[0], d0[1]), (d0[2], d0[3]), (d1[0], d1[1]), (d1[2], d1[3])):
        assert px(img, x, y) == pxart.WP_DOOR
    (ax, ay), (bx, by) = pxart.centre(d0), pxart.centre(d1)
    for t in (0.25, 0.5, 0.75):  # along the link, over the gap and the rooms
        assert px(img, round(ax + (bx - ax) * t), round(ay + (by - ay) * t)) == pxart.WP_DOOR, t


def test_lighthouse_preview_arrival_dots(lh):
    img, model, _ = preview("world.world")
    b = boxes(model, 2)
    for r in model["live"]:
        for o in r.doors:
            for c in r.beside(o):
                x, y = pxart.centre(pxart.cell_box(b[r.id], r, c, 2))
                assert px(img, x, y) == pxart.WP_DOOR, (r.id, c)


def test_lighthouse_preview_markers_are_ringed(lh):
    img, model, _ = preview("world.world")
    cove = next(r for r in model["live"] if r.id == "cove")
    gulls = [o for l in cove.data["layers"] for o in l.get("objects", ()) if o.get("name") == "g"]
    assert len(gulls) == 2
    bx, by = boxes(model, 2)["cove"][:2]
    for o in gulls:
        cx, cy = bx + (o["x"] + o["width"] / 2) * 2, by + (o["y"] - o["height"] / 2) * 2
        rad = max(o["width"], o["height"]) * 2 / 2 + 2
        ring = [px(img, cx, cy - rad + d) for d in range(0, 2)] + [px(img, cx - rad + d, cy) for d in range(0, 2)]
        assert pxart.WP_MARKER in ring, o


def test_lighthouse_preview_edges_bands(lh):
    img, model, _ = preview("world.world")
    b = boxes(model, 2)
    # shore | point: rows 3..10 of shore's east side are sand on both sides (yellow); row 0 is sea on both (nothing)
    sx = b["shore"][0] + b["shore"][2] + G // 2
    assert px(img, sx, b["shore"][1] + 5 * 32 + 16) == pxart.WP_EDGE
    assert px(img, sx, b["shore"][1] + 16) == pxart.WP_BG
    # shore / cove: cove's cell 1,0 walks into shore's solid 1,11: magenta; 5,0 is sand both sides: yellow
    gy = b["shore"][1] + b["shore"][3] + 4
    assert px(img, b["cove"][0] + 1 * 32 + 16, gy) == pxart.WP_ISSUE
    assert px(img, b["cove"][0] + 5 * 32 + 16, gy) == pxart.WP_EDGE
    # the tagged issue: [1] at cove's cell 1,0
    x0, y0 = pxart.cell_box(b["cove"], next(r for r in model["live"] if r.id == "cove"), (1, 0), 2)[:2]
    assert px(img, x0 + 1, y0 + 1) == pxart.WP_ISSUE


def test_lighthouse_preview_labels_are_drawn(lh):
    img, model, _ = preview("world.world")
    b = boxes(model, 2)
    for rid in ROOMS:
        strip = img.crop((b[rid][0], b[rid][1] - L, b[rid][0] + 60, b[rid][1] - 1))
        assert pxart.WP_TEXT in colors(strip), rid


def test_lighthouse_preview_lists_the_issue_under_the_picture(lh):
    img, model, _ = preview("world.world")
    bottom = img.crop((0, img.height - 3 * L, img.width, img.height))
    assert pxart.WP_ISSUE in colors(bottom)


def test_lighthouse_preview_key_colors(lh):
    img, model, _ = preview("world.world")
    seen = colors(img)
    for c, _ in pxart.WP_KEY:
        assert c in seen


def test_lighthouse_preview_dry_run(lh, capsys):
    capsys.readouterr()
    assert run("world", "world.world", "-o", "p.png", "--dry-run") == 0
    out = capsys.readouterr().out
    assert not (lh / "p.png").exists()
    assert re.search(r"p\.png: \d+x\d+ px, " + re.escape(LH_SUMMARY) + ", at --scale 2", out)
    assert "would write p.png (dry run; nothing written)" in out


def test_lighthouse_preview_dry_run_without_o(lh, capsys):
    capsys.readouterr()
    assert run("world", "world.world", "--dry-run") == 0
    assert "(dry run; nothing written)" in capsys.readouterr().out


def test_lighthouse_preview_into_a_new_directory(lh, capsys):
    capsys.readouterr()
    assert run("world", "world.world", "-o", "out/p.png") == 0
    out = capsys.readouterr().out
    assert "created out/" in out and (lh / "out" / "p.png").exists()


def test_lighthouse_preview_big_scale_warns(lh, capsys):
    capsys.readouterr()
    assert run("world", "world.world", "-o", "p.png", "--scale", "6", "--dry-run") == 0
    assert "WARNING: p.png would be" in capsys.readouterr().out


def test_lighthouse_preview_from_another_directory(lh, capsys, monkeypatch):
    monkeypatch.chdir(lh.parent)
    capsys.readouterr()
    assert run("world", "lighthouse/world.world", "-o", "p.png") == 0
    out = capsys.readouterr().out
    assert "[1] WARNING: lighthouse/rooms/cove.tmj: edge-one-side" in out


def test_design_hand_compiled_world_previews_with_a_note(tmp_path, capsys, monkeypatch):
    # expected/ is the design's example as committed; its prop tileset names images from where the design kept
    # them, so those tiles can't be read here: a note, and the picture still draws
    monkeypatch.chdir(LIGHTHOUSE / "expected")
    assert run("world", "world.world", "-o", tmp_path / "p.png") == 0
    out = capsys.readouterr().out
    assert "note: " in out and "can't be read; its tiles are left out of the picture" in out
    assert (tmp_path / "p.png").exists()


# ================================================================ the preview: pixel-level, a synthetic world

@pytest.mark.parametrize("scale", [1, 2, 3, 4])
def test_two_rooms_layout(tmp_path, scale):
    wp = two_room_world(tmp_path)
    img, model, _ = preview(wp, scale)
    b = boxes(model, scale)
    assert b["a"] == (M, M + L, 80 * scale, 64 * scale)
    assert b["b"] == (M + 80 * scale + G, M + L, 80 * scale, 64 * scale)
    assert img.width == max(M + 160 * scale + G + M, 240 + M)


@pytest.mark.parametrize("scale", [1, 2, 3])
def test_two_rooms_floor_and_wall_pixels(tmp_path, scale):
    wp = two_room_world(tmp_path)
    img, model, _ = preview(wp, scale)
    b = boxes(model, scale)
    # a's cell 0,3: floor, clear of every overlay; a's cell 4,3: wall
    assert px(img, b["a"][0] + 8 * scale, b["a"][1] + 3 * 16 * scale + 8 * scale) == FLOOR
    assert px(img, b["a"][0] + 4 * 16 * scale + 8 * scale, b["a"][1] + 3 * 16 * scale + 8 * scale) == WALL
    assert px(img, b["b"][0] + 8 * scale, b["b"][1] + 3 * 16 * scale + 8 * scale) == WALL


@pytest.mark.parametrize("scale", [1, 2, 3])
def test_two_rooms_edge_bands_by_row(tmp_path, scale):
    wp = two_room_world(tmp_path)
    img, model, _ = preview(wp, scale)
    b = boxes(model, scale)
    gx = b["a"][0] + b["a"][2] + G // 2
    row = lambda y: b["a"][1] + y * 16 * scale + 8 * scale  # noqa: E731
    assert px(img, gx, row(0)) == pxart.WP_EDGE  # floor | floor
    assert px(img, gx, row(1)) in (pxart.WP_EDGE, pxart.WP_DOOR)  # the door link crosses here
    assert px(img, gx, row(2)) == pxart.WP_ISSUE  # a floor | b wall: edge-one-side
    assert px(img, gx, row(3)) == pxart.WP_BG  # wall | wall: a wall, nothing drawn


def test_two_rooms_edge_band_spans_the_gap(tmp_path):
    wp = two_room_world(tmp_path)
    img, model, _ = preview(wp, 2)
    b = boxes(model, 2)
    y = b["a"][1] + 16
    left, right = b["a"][0] + b["a"][2], b["b"][0]
    assert px(img, left + 2, y) == pxart.WP_EDGE and px(img, right - 3, y) == pxart.WP_EDGE
    assert px(img, left, y) != pxart.WP_EDGE  # the room's outline stays
    # a 1px break between cells: rows 0 and 1 are two bands, the break on row 0's last pixel line
    assert px(img, left + G // 2, b["a"][1] + 31) == pxart.WP_BG


def test_two_rooms_edge_one_side_cell_is_outlined(tmp_path):
    wp = two_room_world(tmp_path)
    img, model, issues = preview(wp, 2)
    a = next(r for r in model["live"] if r.id == "a")
    x0, y0, x1, y1 = pxart.cell_box(boxes(model, 2)["a"], a, (4, 2), 2)
    assert px(img, x1, y1) == pxart.WP_ISSUE and px(img, x1, (y0 + y1) // 2) == pxart.WP_ISSUE
    assert [i.code for i in issues] == ["edge-one-side"]


def test_two_rooms_door_outlines_and_link(tmp_path):
    wp = two_room_world(tmp_path)
    img, model, _ = preview(wp, 2)
    b = boxes(model, 2)
    a = next(r for r in model["live"] if r.id == "a")
    bb = next(r for r in model["live"] if r.id == "b")
    da = pxart.door_box(b["a"], a, a.doors[0], 2)
    db = pxart.door_box(b["b"], bb, bb.doors[0], 2)
    assert da == (M + 96, M + L + 32, M + 127, M + L + 63)
    assert db == (M + 160 + G + 32, M + L + 32, M + 160 + G + 63, M + L + 63)
    for box in (da, db):
        assert px(img, box[0], box[1]) == pxart.WP_DOOR and px(img, box[2], box[3]) == pxart.WP_DOOR
    # the link: the same row, so a horizontal line through both centres
    y = round(pxart.centre(da)[1])
    for x in range(round(pxart.centre(da)[0]), round(pxart.centre(db)[0]) + 1, 7):
        assert px(img, x, y) == pxart.WP_DOOR, x


def test_two_rooms_door_link_has_arrowheads_at_both_ends(tmp_path):
    wp = two_room_world(tmp_path)
    s = 4
    img, model, _ = preview(wp, s)
    b = boxes(model, s)
    a = next(r for r in model["live"] if r.id == "a")
    bb = next(r for r in model["live"] if r.id == "b")
    (ax, ay), (bx, by) = pxart.centre(pxart.door_box(b["a"], a, a.doors[0], s)), \
        pxart.centre(pxart.door_box(b["b"], bb, bb.doors[0], s))
    assert ay == by
    off = 4  # beside the line (width 4: +-2) but inside a head (4 + 2 * 4 = 12 long, +-~4.4 wide 8 back)
    assert px(img, bx - 7, by + off) == pxart.WP_DOOR and px(img, bx - 7, by - off) == pxart.WP_DOOR
    assert px(img, ax + 7, ay + off) == pxart.WP_DOOR and px(img, ax + 7, ay - off) == pxart.WP_DOOR
    mid = round((ax + bx) / 2)
    assert px(img, mid, ay + off + 1) != pxart.WP_DOOR and px(img, mid, ay - off - 1) != pxart.WP_DOOR


def test_two_rooms_arrival_dots(tmp_path):
    wp = two_room_world(tmp_path)
    img, model, _ = preview(wp, 2)
    b = boxes(model, 2)
    a = next(r for r in model["live"] if r.id == "a")
    got = []
    for c in [(x, y) for y in range(4) for x in range(5)]:
        x, y = pxart.centre(pxart.cell_box(b["a"], a, c, 2))
        if px(img, x, y) == pxart.WP_DOOR:
            got.append(c)
    # beside D (3,1): 2,1 4,1 3,0 3,2; the link line crosses row 1 too, so 4,1 and 2,1 show door either way
    assert {(3, 0), (3, 2), (2, 1), (4, 1)} <= set(got)
    assert (0, 0) not in got and (0, 3) not in got


def test_two_rooms_start_outline(tmp_path):
    wp = two_room_world(tmp_path)
    img, model, _ = preview(wp, 2)
    a = next(r for r in model["live"] if r.id == "a")
    x0, y0, x1, y1 = pxart.cell_box(boxes(model, 2)["a"], a, (1, 1), 2)
    assert (x0, y0) == (M + 32, M + L + 32)
    assert px(img, x0, y0) == pxart.WP_START and px(img, x1, y1) == pxart.WP_START
    assert px(img, x0 + 1, y0 + 1) == pxart.WP_START  # 2px wide at scale 2
    assert px(img, x0 + 8, y0 + 8) == FLOOR  # the cell itself still shows


def test_two_rooms_nothing_outside_the_rooms_but_links_bands_and_text(tmp_path):
    wp = two_room_world(tmp_path)
    img, model, _ = preview(wp, 2)
    allowed = {pxart.WP_BG, pxart.WP_EDGE, pxart.WP_DOOR, pxart.WP_ISSUE, pxart.WP_TEXT, pxart.WP_LINE,
               pxart.WP_START, pxart.WP_MARKER}
    b = boxes(model, 2)
    for x in range(0, img.width, 3):
        for y in range(0, img.height, 3):
            inside = any(bx <= x < bx + w and by <= y < by + h for bx, by, w, h in b.values())
            if not inside:
                assert px(img, x, y) in allowed, (x, y, px(img, x, y))


def test_one_way_door_is_magenta_with_one_head(tmp_path):
    # D -> E is fine, but E leads back to X, which a lacks: D gets door-pair, E door-entry
    wp = two_room_world(tmp_path, b_objs=[door(1, "E", 1, 1, "a.tmj", "X")])
    s = 4
    img, model, issues = preview(wp, s)
    assert sorted((i.code, i.room, i.name) for i in issues if i.level == "error") == [
        ("door-entry", "b", "E"), ("door-pair", "a", "D")]
    b = boxes(model, s)
    a = next(r for r in model["live"] if r.id == "a")
    bb = next(r for r in model["live"] if r.id == "b")
    da, db = pxart.door_box(b["a"], a, a.doors[0], s), pxart.door_box(b["b"], bb, bb.doors[0], s)
    assert px(img, da[2], da[3]) == pxart.WP_ISSUE and px(img, db[2], db[3]) == pxart.WP_ISSUE
    (ax, ay), (bx, by) = pxart.centre(da), pxart.centre(db)
    assert px(img, round((ax + bx) / 2), ay) == pxart.WP_ISSUE
    assert px(img, bx - 7, by + 4) == pxart.WP_ISSUE  # the head, at the door it points to
    assert px(img, ax + 7, ay + 4) != pxart.WP_ISSUE  # none where it starts


def test_door_to_a_missing_room_is_outlined_with_no_link(tmp_path):
    wp = two_room_world(tmp_path, a_objs=[start(1, 1, 1), door(2, "D", 3, 1, "nowhere.tmj", "E")],
                        b_objs=[])
    img, model, issues = preview(wp, 2)
    assert [(i.code, i.name) for i in issues if i.level == "error"] == [("door-target", "D")]
    a = next(r for r in model["live"] if r.id == "a")
    da = pxart.door_box(boxes(model, 2)["a"], a, a.doors[0], 2)
    assert px(img, da[0], da[1]) == pxart.WP_ISSUE or px(img, da[0] + 1, da[1] + 1) == pxart.WP_ISSUE
    gx = boxes(model, 2)["a"][0] + 160 + G // 2
    assert px(img, gx, round(pxart.centre(da)[1])) != pxart.WP_ISSUE


def test_stacked_rooms_south_edge_band(tmp_path):
    wp = write_world(tmp_path / "w", [("a", 0, 0), ("b", 0, 64)],
                     {"a": room(A_ROWS, [start(1, 1, 1)]), "b": room(["#....", ".....", ".....", "....."])})
    img, model, issues = preview(wp, 2)
    b = boxes(model, 2)
    assert b["b"] == (M, M + L + 128 + G, 160, 128)
    gy = b["a"][1] + b["a"][3] + 4  # the band is in the top of the gap, clear of b's label
    assert px(img, b["a"][0] + 2 * 32 + 16, gy) == pxart.WP_EDGE
    assert px(img, b["a"][0] + 16, gy) == pxart.WP_ISSUE  # a's 0,3 floor over b's 0,0 wall
    assert px(img, b["a"][0] + 4 * 32 + 16, gy) == pxart.WP_ISSUE  # a's 4,3 wall under... b's 4,0 floor
    assert {(i.code, i.room, i.name) for i in issues} == {("edge-one-side", "a", "south"),
                                                           ("edge-one-side", "b", "north")}


def test_offset_rooms_band_joins_the_shifted_cells(tmp_path):
    # b sits 32 px (two cells) lower: a's row 2 meets b's row 0
    wp = write_world(tmp_path / "w", [("a", 0, 0), ("b", 80, 32)],
                     {"a": room(["....."] * 4, [start(1, 1, 1)]), "b": room(["....."] * 4)})
    img, model, issues = preview(wp, 2)
    b = boxes(model, 2)
    assert b["b"] == (M + 160 + G, M + L + 64 + G, 160, 128)
    assert issues == [] or all(i.code != "edge-one-side" for i in issues)
    left, right = b["a"][0] + b["a"][2] + 2, b["b"][0] - 3
    ya, yb = b["a"][1] + 2 * 32 + 16, b["b"][1] + 16  # a's row 2 and b's row 0: one band, slanting
    assert px(img, left, ya) == pxart.WP_EDGE and px(img, right, yb) == pxart.WP_EDGE
    assert px(img, left, b["a"][1] + 16) == pxart.WP_BG  # a's row 0 has nothing across


def test_interior_goes_right_of_the_placed_rooms(tmp_path):
    wp = write_world(tmp_path / "w", [("a", 0, 0)],
                     {"a": room(A_ROWS, [start(1, 1, 1), door(2, "D", 2, 0, "in.tmj", "E")]),
                      "in": room(["###", "#.#", "#.#"], [door(1, "E", 1, 2, "a.tmj", "D")])})
    img, model, issues = preview(wp, 2)
    b = boxes(model, 2)
    assert b["in"] == (M + 160 + 2 * G, M + L, 96, 96)
    assert [r.id for r in model["placed"]] == ["a"]


def test_two_interiors_stack(tmp_path):
    wp = write_world(tmp_path / "w", [("a", 0, 0)],
                     {"a": room(A_ROWS, [start(1, 1, 1), door(2, "D", 1, 0, "i1.tmj", "E"),
                                         door(3, "F", 3, 0, "i2.tmj", "E")]),
                      "i1": room(["...", "..."], [door(1, "E", 1, 1, "a.tmj", "D")]),
                      "i2": room(["...", "..."], [door(1, "E", 1, 1, "a.tmj", "F")])})
    _, model, _ = preview(wp, 2)
    b = boxes(model, 2)
    assert b["i1"] == (M + 160 + 2 * G, M + L, 96, 64)
    assert b["i2"] == (M + 160 + 2 * G, M + L + 64 + G, 96, 64)


def test_unreachable_room_is_hatched(tmp_path):
    # b is walled off: nothing of it can be reached (room-unreachable, a warning)
    wp = write_world(tmp_path / "w", [("a", 0, 0), ("b", 0, 128)],
                     {"a": room(A_ROWS, [start(1, 1, 1)]), "b": room(["....."] * 3)})
    img, model, issues = preview(wp, 2)
    assert ("room-unreachable", "b") in {(i.code, i.room) for i in issues}
    x, y, w, h = boxes(model, 2)["b"]
    hatch = sum(1 for xx in range(x, x + w) for yy in range(y + 20, y + 40) if px(img, xx, yy) == pxart.WP_ISSUE)
    assert hatch > 20
    x, y, w, h = boxes(model, 2)["a"]
    assert sum(1 for xx in range(x, x + w) for yy in range(y + 70, y + 90) if px(img, xx, yy) == pxart.WP_ISSUE) == 0


def test_missing_room_is_crossed_out(tmp_path):
    wp = write_world(tmp_path / "w", [("a", 0, 0), ("gone", 80, 0)], {"a": room(A_ROWS, [start(1, 1, 1)])})
    img, model, issues = preview(wp, 2)
    assert [(i.code, i.room) for i in issues] == [("room-missing", "gone")]
    missing = pxart.world_layout(model, 2)[1]
    assert [fn for fn, _ in missing] == [str(pathlib.PurePath(wp).parent.as_posix()) + "/rooms/gone.tmj"]
    x, y, w, h = missing[0][1]
    assert (x, y, w, h) == (M + 160 + G, M + L, 128, 128)
    assert px(img, x, y) == pxart.WP_ISSUE and px(img, x + w - 1, y + h - 1) == pxart.WP_ISSUE
    assert px(img, x + w // 2, y + h // 2) == pxart.WP_ISSUE  # the cross


def test_issue_tags_are_numbered_at_their_cells(tmp_path):
    wp = two_room_world(tmp_path, a_objs=[start(1, 4, 3), door(2, "D", 3, 1, "b.tmj", "E")])
    img, model, issues = preview(wp, 2)
    codes = [i.code for i in issues]
    assert "start-solid" in codes
    i = issues[codes.index("start-solid")]
    a = next(r for r in model["live"] if r.id == "a")
    x0, y0 = pxart.cell_box(boxes(model, 2)["a"], a, tuple(i.cell), 2)[:2]
    assert px(img, x0 + 1, y0 + 1) == pxart.WP_ISSUE


def test_bad_start_is_magenta(tmp_path):
    wp = two_room_world(tmp_path, a_objs=[start(1, 4, 3), door(2, "D", 3, 1, "b.tmj", "E")])
    img, model, _ = preview(wp, 2)
    a = next(r for r in model["live"] if r.id == "a")
    x0, y0, x1, y1 = pxart.cell_box(boxes(model, 2)["a"], a, (4, 3), 2)
    assert px(img, x1, y1) == pxart.WP_ISSUE
    assert pxart.WP_START not in colors(img.crop((x0, y0, x1 + 1, y1 + 1)))


def test_two_starts_both_magenta(tmp_path):
    wp = two_room_world(tmp_path, b_objs=[door(1, "E", 1, 1, "a.tmj", "D"), start(2, 3, 0)])
    img, model, issues = preview(wp, 2)
    assert [i.code for i in issues if i.level == "error"] == ["start-count", "start-count"]
    b = boxes(model, 2)
    for rid, c in (("a", (1, 1)), ("b", (3, 0))):
        r = next(x for x in model["live"] if x.id == rid)
        x0, y0, x1, y1 = pxart.cell_box(b[rid], r, c, 2)
        assert px(img, x1, y1) == pxart.WP_ISSUE, rid


def test_markers_ringed_in_a_synthetic_room(tmp_path):
    wp = two_room_world(tmp_path, a_objs=[start(1, 1, 1), door(2, "D", 3, 1, "b.tmj", "E"), marker(3, "g", 1, 3)])
    img, model, issues = preview(wp, 2)
    x, y = boxes(model, 2)["a"][:2]
    cx, cy = x + (16 + 8) * 2, y + (64 - 8) * 2
    rad = 16 * 2 / 2 + 2
    assert pxart.WP_MARKER in {px(img, cx, cy - rad), px(img, cx, cy - rad + 1)}
    assert px(img, cx, cy) == HERO  # the marker's art draws (as in Tiled)


def test_marker_art_draws_but_blocks_nothing(tmp_path):
    wp = two_room_world(tmp_path, a_objs=[start(1, 1, 1), door(2, "D", 3, 1, "b.tmj", "E"), marker(3, "g", 1, 3)])
    _, model, issues = preview(wp, 2)
    a = next(r for r in model["live"] if r.id == "a")
    assert a.walkable((1, 3))


def test_every_fixture_draws(tmp_path):
    for name in FIXTURE_NAMES:
        f = fixture(name)
        wp = materialize(f, tmp_path / name)
        img, model, issues = preview(wp, 1)
        assert img.width > 0 and len(issues) == len(f["expect"]), name


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_every_fixture_cli_prints_each_issue_numbered(name, tmp_path, capsys, monkeypatch):
    f = fixture(name)
    materialize(f, tmp_path / "f")
    monkeypatch.chdir(tmp_path / "f")
    capsys.readouterr()
    assert run("world", f["world"], "-o", "p.png") == 0  # a broken world still draws: check is the verdict
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if re.match(r"^\[\d+\] ", l)]
    assert [int(re.match(r"^\[(\d+)\]", l).group(1)) for l in lines] == list(range(1, len(f["expect"]) + 1))
    n_err = sum(e["level"] == "error" for e in f["expect"])
    assert sum(": E_WORLD: " in l for l in lines) == n_err
    assert sum(l.split("] ", 1)[1].startswith("WARNING: ") for l in lines) == len(f["expect"]) - n_err
    last = out.splitlines()[-1]
    assert last.startswith("wrote p.png: world.world, ")
    assert ("tagged [n] in the picture" in last) == bool(f["expect"])


@pytest.mark.parametrize("name", [n for n in FIXTURE_NAMES if n.startswith("valid-")])
def test_valid_fixtures_draw_no_issue_color_in_the_rooms(name, tmp_path):
    f = fixture(name)
    wp = materialize(f, tmp_path / "f")
    img, model, issues = preview(wp, 2)
    assert issues == []
    for x, y, w, h in pxart.world_layout(model, 2)[0].values():
        assert pxart.WP_ISSUE not in colors(img.crop((x, y, x + w, y + h))), name


@pytest.mark.parametrize("name", [n for n in FIXTURE_NAMES if not n.startswith("valid-")])
def test_broken_fixtures_draw_the_issue_color(name, tmp_path):
    f = fixture(name)
    wp = materialize(f, tmp_path / "f")
    img, _, issues = preview(wp, 2)
    assert issues and pxart.WP_ISSUE in colors(img), name


# ================================================================ the renderer: Tiled's way of drawing a map

def render_one(tmp_path, t):
    wp = write_world(tmp_path / "r", [("a", 0, 0)], {"a": t})
    _, model, _ = pxart.load_tiled(str(wp))
    return pxart.tiled_room_image(model["live"][0])


def test_render_tile_layer_colors(tmp_path):
    img = render_one(tmp_path, room([".#", "h "]))
    assert img.size == (32, 32)
    assert img.getpixel((8, 8)) == FLOOR and img.getpixel((24, 8)) == WALL
    assert img.getpixel((24, 24))[3] == 0  # gid 0: empty


def test_render_hidden_layer_is_not_drawn(tmp_path):
    t = room([".."])
    t["layers"][0]["visible"] = False
    assert render_one(tmp_path, t).getpixel((8, 8))[3] == 0


def test_render_layer_opacity(tmp_path):
    t = room([".."])
    t["layers"][0]["opacity"] = 0.5
    assert render_one(tmp_path, t).getpixel((8, 8))[3] in (127, 128)


def test_render_group_layer_and_its_visibility(tmp_path):
    t = room([".."])
    ground = t["layers"].pop(0)
    t["layers"].insert(0, {"id": 9, "name": "g", "type": "group", "visible": True, "opacity": 1, "layers": [ground]})
    assert render_one(tmp_path, t).getpixel((8, 8)) == FLOOR
    t["layers"][0]["visible"] = False
    assert render_one(tmp_path / "2", t).getpixel((8, 8))[3] == 0


def test_render_tile_object_bottom_left_and_scaled(tmp_path):
    t = room(["  ", "  "], [{"id": 1, "name": "", "gid": 2, "x": 0, "y": 32, "width": 32, "height": 16}])
    img = render_one(tmp_path, t)
    assert img.getpixel((30, 20)) == WALL and img.getpixel((8, 8))[3] == 0


def test_render_flips(tmp_path):
    # the fixture's log (props.tsj, 32x16): its left half and right half differ; H flips them
    ts = [{"firstgid": 1, "source": "../tiles.tsj"}, {"firstgid": 101, "source": "../props.tsj"}]
    plain = render_one(tmp_path / "a", room(["  "], [{"id": 1, "name": "", "gid": 101, "x": 0, "y": 16,
                                                         "width": 32, "height": 16}], tilesets=ts))
    flipped = render_one(tmp_path / "b", room(["  "], [{"id": 1, "name": "", "gid": 101 | pxart.GID_H, "x": 0,
                                                           "y": 16, "width": 32, "height": 16}], tilesets=ts))
    assert flipped.tobytes() == plain.transpose(Image.FLIP_LEFT_RIGHT).tobytes()


def test_render_topdown_sorts_by_y(tmp_path):
    objs = [{"id": 1, "name": "", "gid": 1, "x": 0, "y": 32, "width": 16, "height": 16},
            {"id": 2, "name": "", "gid": 2, "x": 0, "y": 24, "width": 16, "height": 16}]
    t = room(["  ", "  "], objs)
    t["layers"][1]["draworder"] = "topdown"
    img = render_one(tmp_path / "t", t)
    assert img.getpixel((8, 20)) == FLOOR  # the lower one (y 32) draws last
    t["layers"][1]["draworder"] = "index"
    img = render_one(tmp_path / "i", t)
    assert img.getpixel((8, 20)) == WALL  # file order: the wall last


def test_render_hidden_object_not_drawn(tmp_path):
    t = room(["  "], [{"id": 1, "name": "", "gid": 2, "x": 0, "y": 16, "width": 16, "height": 16,
                       "visible": False}])
    assert render_one(tmp_path, t).getpixel((8, 8))[3] == 0


def test_render_embedded_tileset(tmp_path):
    ts = load(RULES / "tiles.tsj")
    ts["firstgid"] = 1
    ts["image"] = "../tiles.png"  # an embedded tileset's image is from the map's directory
    img = render_one(tmp_path, room([".#"], tilesets=[ts]))
    assert img.getpixel((8, 8)) == FLOOR and img.getpixel((24, 8)) == WALL


def test_render_missing_image_is_left_out_and_named(tmp_path):
    wp = write_world(tmp_path / "r", [("a", 0, 0)], {"a": room([".#"], [start(1, 0, 0)])})
    (tmp_path / "r" / "tiles.png").unlink()
    _, model, _ = pxart.load_tiled(str(wp))
    missing = {}
    img = pxart.tiled_room_image(model["live"][0], missing=missing)
    assert img.getpixel((8, 8))[3] == 0 and any(k.endswith("tiles.png") for k in missing)


def test_world_cli_notes_missing_art(tmp_path, capsys):
    wp = write_world(tmp_path / "r", [("a", 0, 0)], {"a": room([".#"], [start(1, 0, 0)])})
    (tmp_path / "r" / "tiles.png").unlink()
    capsys.readouterr()
    assert run("world", wp, "-o", tmp_path / "p.png") == 0
    assert "tiles.png can't be read; its tiles are left out of the picture" in capsys.readouterr().out


# ================================================================ the CLI: a lone room, and errors

def test_world_of_a_lone_room(tmp_path, capsys, monkeypatch):
    d = tmp_path / "lone"
    write_world(d, [], {"a": room(A_ROWS, [start(1, 1, 1)])})
    (d / "world.world").unlink()
    monkeypatch.chdir(d)
    capsys.readouterr()
    assert run("world", "rooms/a.tmj", "-o", "p.png") == 0
    assert capsys.readouterr().out == "wrote p.png: rooms/a.tmj, 1 room placed, 0 door pairs, start in a\n"
    img = Image.open(d / "p.png").convert("RGBA")
    assert img.getpixel((M + 8, M + L + 3 * 32 + 8)) == FLOOR


def test_world_of_a_world_room_is_refused(lh):
    msg = run_err("world", "rooms/point.tmj", "-o", "p.png")
    assert msg.startswith("world: rooms/point.tmj: E_WORLD: rooms/point.tmj is a room of world.world (placed)")
    assert not (lh / "p.png").exists()


def test_world_of_a_source_says_compile_it(lh):
    msg = run_err("world", "world.src.json", "-o", "p.png")
    assert "E_BAD_ARG" in msg and "is a world source" in msg and "'pxart export world.src.json --tiled'" in msg
    assert "'pxart check world.src.json'" in msg


def test_world_of_a_map_says_compile_it(lh):
    msg = run_err("world", "rooms/cove.map", "-o", "p.png")
    assert "E_BAD_ARG" in msg and "is a world source" in msg


def test_world_of_something_else(tmp_path):
    p = tmp_path / "a.px"
    p.write_text("k #000000\nk\n")
    assert "give a Tiled world (.world) or map (.tmj)" in run_err("world", p, "-o", tmp_path / "p.png")


def test_world_missing_file(tmp_path):
    msg = run_err("world", tmp_path / "nope.world", "-o", tmp_path / "p.png")
    assert msg.startswith("world: ") and "E_FILE" in msg


def test_world_not_json(tmp_path):
    p = tmp_path / "w.world"
    p.write_text("nope")
    assert "E_WORLD: not JSON" in run_err("world", p, "-o", tmp_path / "p.png")


def test_world_needs_o(lh):
    assert "-o is required: -o world.png" in run_err("world", "world.world")


def test_world_bad_o_extension_before_anything(lh, capsys):
    capsys.readouterr()
    msg = run_err("world", "world.world", "-o", "p.txt")
    assert "E_BAD_ARG" in msg and "name it .png" in msg
    assert "[1]" not in capsys.readouterr().out


def test_world_bad_scale(lh):
    assert "--scale 0: a whole number, 1 or more" in run_err("world", "world.world", "-o", "p.png", "--scale", "0")
    assert "--scale -1" in run_err("world", "world.world", "-o", "p.png", "--scale", "-1")


def test_world_scale_not_a_number(lh):
    with pytest.raises(SystemExit) as e:
        pxart.main(["world", "world.world", "-o", "p.png", "--scale", "x"])
    assert e.value.code == 2


def test_world_infinite_room_is_refused(tmp_path):
    wp = two_room_world(tmp_path)
    t = load(tmp_path / "w" / "rooms" / "a.tmj")
    t["infinite"] = True
    (tmp_path / "w" / "rooms" / "a.tmj").write_text(json.dumps(t))
    assert "untick Infinite" in run_err("world", wp, "-o", tmp_path / "p.png")


def test_world_exit_0_on_a_broken_world(tmp_path):
    wp = two_room_world(tmp_path, b_objs=[door(1, "E", 1, 1, "a.tmj", "X")])
    assert run("world", wp, "-o", tmp_path / "p.png") == 0
    assert run("check", wp) == 1


# ================================================================ help

def test_help_worlds_documents_the_preview_and_compiled_check():
    doc = " ".join(pxart.WORLDS.split())
    for s in ("check world.src.json|W.world|ROOM.tmj|DIR...", "world W.world|ROOM.tmj -o world.png [--scale 2]",
              "A lone ROOM.tmj is a world of that one room", "a band per cell", "exactly as the compile runs them",
              "A broken world still draws (exit 0): check is the verdict", "'export world.src.json --tiled' first",
              "rooms/point.tmj: E_WORLD: door-pair [D, cell 10,7]", "interiors in a column to the right",
              "markers cyan rings", "A DIR checks world sources only", "CSV (JSON array) tile data"):
        assert s in doc, s


def test_help_all_has_the_world_usage_line_and_stays_small(capsys):
    assert "  world W.world|ROOM.tmj -o world.png [--scale 2] [--dry-run]" in pxart.__doc__.splitlines()
    assert run("help", "all") == 0
    assert len(capsys.readouterr().out.encode()) <= 67277
    assert "a .world or .tmj: help worlds" in " ".join(pxart.__doc__.split())


def test_world_dash_h(capsys):
    with pytest.raises(SystemExit) as e:
        pxart.main(["world", "-h"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: pxart world ") and "Draw a compiled world" in out and "--scale" in out


def test_world_is_a_looking_command():
    assert "world" in pxart.commands_by_topic()["LOOKING"]


def test_help_worlds_lines_fit():
    assert all(len(l) <= 92 for l in pxart.WORLDS.splitlines())


def test_world_of_an_empty_world_still_draws(tmp_path, capsys):
    p = tmp_path / "e.world"
    p.write_text('{"type": "world", "maps": []}')
    capsys.readouterr()
    assert run("world", p, "-o", tmp_path / "e.png") == 0
    out = capsys.readouterr().out
    assert "E_WORLD: start-count" in out and "0 rooms placed, 0 door pairs, no start; 1 error, tagged" in out
    assert pxart.WP_ISSUE in colors(Image.open(tmp_path / "e.png"))


def test_world_whose_only_room_is_missing_draws_it_crossed_out(tmp_path, capsys):
    p = tmp_path / "m.world"
    p.write_text('{"type": "world", "maps": [{"fileName": "x.tmj", "x": 0, "y": 0, "width": 64, "height": 64}]}')
    capsys.readouterr()
    assert run("world", p, "-o", tmp_path / "m.png", "--scale", "1") == 0
    out = capsys.readouterr().out
    assert "[1] " in out and "room-missing" in out and "[2] " in out and "start-count" in out
    img = Image.open(tmp_path / "m.png").convert("RGBA")
    assert px(img, M, M + L) == pxart.WP_ISSUE and px(img, M + 32, M + L + 32) == pxart.WP_ISSUE
