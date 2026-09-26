import json
import pathlib
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402

LEGACY = """# old-style file: '. transparent' declared, blank line before grid
. transparent
k #3f2631
g #43e1b3

.kk.
kggk
.kk.
"""

MULTI = """pxart 1
k #3f2631
g #43e1b3
r #e43b44

@variant night
g #25956a

@anim walk/down direction=pingpong repeat=2 ms=120

@frame walk/down/0
.kk.
kggk
@frame walk/down/1 ms=200
.kk.
kgrk
@frame idle
kggk
kggk
"""


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def codes(excinfo):
    return [i.code for i in excinfo.value.issues]


def run(*argv):
    """Run the CLI; returns the exit code (0 when it doesn't exit)."""
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


# ---------------------------------------------------------------- parsing

def test_legacy_file_parses_as_one_unnamed_frame(tmp_path):
    doc = pxart.parse(write(tmp_path, "a.px", LEGACY))
    assert doc.implicit and len(doc.frames) == 1 and doc.frames[0].size == (4, 3)
    img = doc.image(doc.frames[0])
    assert img.getpixel((0, 0))[3] == 0 and img.getpixel((1, 0)) == (0x3F, 0x26, 0x31, 255)


def test_blank_line_between_palette_and_grid_is_optional(tmp_path):
    doc = pxart.parse(write(tmp_path, "a.px", "k #3f2631\n.k\nk.\n"))
    assert doc.frames[0].grid == [".k", "k."]


def test_dot_is_builtin_transparent_and_reserved(tmp_path):
    pxart.parse(write(tmp_path, "ok.px", "k #000000\n.k\n"))
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(write(tmp_path, "bad.px", ". #ffffff\nk #000000\n.k\n"))
    assert codes(e) == ["E_DOT_RESERVED"]


def test_version_line(tmp_path):
    assert pxart.parse(write(tmp_path, "a.px", "pxart 1\nk #000000\nk\n")).version == 1
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(write(tmp_path, "b.px", "pxart 2\nk #000000\nk\n"))
    assert codes(e) == ["E_VERSION"]


def test_all_errors_reported_together_with_locations(tmp_path):
    text = "k #000000\nz #12345\n\nkkk\nkk\nkqk\n"
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(write(tmp_path, "a.px", text))
    got = {i.code: i for i in e.value.issues}
    assert set(got) == {"E_BAD_COLOR", "E_ROW_WIDTH", "E_UNKNOWN_KEY"}
    assert got["E_ROW_WIDTH"].line == 5 and got["E_ROW_WIDTH"].row == 1
    assert got["E_UNKNOWN_KEY"].cols == [1] and got["E_UNKNOWN_KEY"].line == 6
    assert "a.px:6: E_UNKNOWN_KEY (row 2, x=[1])" in str(got["E_UNKNOWN_KEY"])


@pytest.mark.parametrize("text,code", [
    ("# k\n\" #000000\n\"\n", "E_BAD_KEY"),
    ("k #000000\nk #111111\nk\n", "E_DUP_KEY"),
    ("k #000000\nk\nj #111111\n", "E_PALETTE_AFTER_GRID"),
    ("k #000000\nk k k\n", "E_BAD_ROW"),
    ("k #000000\nk k\n", "E_BAD_COLOR"),  # two tokens read as a palette line
    ("k #000000\n", "E_NO_FRAMES"),
    ("k #000000\nk\n@frame a\nk\n", "E_MIXED_FRAMES"),
    ("k #000000\n@frame a\nk\n@frame a\nk\n", "E_DUP_FRAME"),
    ("k #000000\n@frame bad id\nk\n", "E_BAD_ID"),
    ("k #000000\n@variant v\nq #111111\n\nk\n", "E_VARIANT_KEY"),
    ("k #000000\n@anim w direction=sideways\n@frame w/0\nk\n", "E_BAD_ARG"),
    ("k #000000\n@frame w/0 ms=0\nk\n", "E_BAD_ARG"),
    ("@palette nope.px\nk\n", "E_PALETTE_FILE"),
])
def test_error_codes(tmp_path, text, code):
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(write(tmp_path, "a.px", text))
    assert code in codes(e)


def test_unknown_sections_kept_when_lenient_rejected_when_strict(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nk\n\n@future thing\nwhatever here\n")
    doc = pxart.parse(p)
    assert doc.extensions == ["@future thing", "whatever here"]
    assert "@future thing\nwhatever here" in doc.text()
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p, strict=True)
    assert codes(e) == ["E_UNKNOWN_SECTION"]


def test_multi_frame_groups_durations_and_selection(tmp_path):
    doc = pxart.parse(write(tmp_path, "m.px", MULTI))
    assert [f.id for f in doc.frames] == ["walk/down/0", "walk/down/1", "idle"]
    assert list(doc.groups()) == ["walk/down", ""]
    assert [doc.ms(f) for f in doc.frames] == [120, 200, pxart.DEFAULT_MS]
    assert [f.id for f in doc.select("walk/down")] == ["walk/down/0", "walk/down/1"]
    assert [f.id for f in doc.select("walk/down/1")] == ["walk/down/1"]
    with pytest.raises(pxart.PxError):
        doc.select("walk/up")


def test_variant_recolors(tmp_path):
    doc = pxart.parse(write(tmp_path, "m.px", MULTI))
    f = doc.get("idle")
    assert doc.image(f).getpixel((1, 0))[:3] == (0x43, 0xE1, 0xB3)
    assert doc.image(f, "night").getpixel((1, 0))[:3] == (0x25, 0x95, 0x6A)


def test_shared_palette(tmp_path):
    write(tmp_path, "base.px", "# shared\nk #3f2631\ng #43e1b3\n")
    doc = pxart.parse(write(tmp_path, "s.px", "@palette base.px\ng #ffffff\n\nkg\n"))
    assert doc.image(doc.frames[0]).getpixel((1, 0))[:3] == (255, 255, 255)  # local overrides shared
    assert "k" not in doc.palette and "@palette base.px" in doc.text()


def test_round_trip_keeps_order_and_content(tmp_path):
    doc = pxart.parse(write(tmp_path, "m.px", MULTI))
    again = pxart.parse(write(tmp_path, "m2.px", doc.text()))
    assert again.text() == doc.text()
    assert list(again.palette) == ["k", "g", "r"]
    assert again.anims["walk/down"] == {"direction": "pingpong", "repeat": 2, "ms": 120}


def test_selector_parsing(tmp_path):
    assert pxart.split_sel("a/b.px:walk/down") == ("a/b.px", "walk/down")
    assert pxart.split_sel("a/b.px") == ("a/b.px", None)
    assert pxart.split_sel("x.png") == ("x.png", None)


# ---------------------------------------------------------------- editing

def test_flip_one_frame_leaves_others(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    assert run("flip", f"{p}:walk/down/1") == 0
    doc = pxart.parse(p)
    assert doc.get("walk/down/1").grid == [".kk.", "krgk"]
    assert doc.get("walk/down/0").grid == [".kk.", "kggk"]


def test_shift_region(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nk...\n....\n")
    assert run("shift", p, "--dx", "2", "--dy", "1", "--region", "0,0,1,1") == 0
    assert pxart.parse(p).frames[0].grid == ["....", "..k."]


def test_recolor_region_and_color(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\nkkkk\n")
    assert run("recolor", p, "k=j", "--region", "2,0,2,1") == 0
    assert pxart.parse(p).frames[0].grid == ["kkjj"]
    assert run("recolor", p, "k=#ff0000") == 0
    assert pxart.parse(p).palette["k"] == (255, 0, 0, 255)
    assert run("recolor", p, "k=#00ff00", "--region", "0,0,1,1") == 1


def test_palette_add(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    assert run("palette", p, "--add", "z=#123456") == 0
    assert pxart.parse(p).palette["z"] == (0x12, 0x34, 0x56, 255)
    assert run("palette", p, "--add", "k=#ffffff") == 1  # conflict


def test_paste_and_compose_and_dup(tmp_path):
    body = write(tmp_path, "body.px", "b #763b36\nbbb\nbbb\n")
    staff = write(tmp_path, "staff.px", "s #c0cbdc\ns\ns\ns\n")
    out = tmp_path / "hero.px"
    assert run("compose", "-o", f"{out}:walk/0", "--size", "4x3", f"{body}@0,0", f"{staff}@3,0") == 0
    assert run("compose", "-o", f"{out}:walk/1", "--size", "4x3", f"{body}@1,0", f"{staff}@0,0") == 0
    doc = pxart.parse(out)
    assert doc.get("walk/0").grid == ["bbbs", "bbbs", "...s"]
    assert doc.get("walk/1").grid == ["sbbb", "sbbb", "s..."]
    assert run("dup", f"{out}:walk/1", "walk/2") == 0
    assert run("paste", staff, "--into", f"{out}:walk/2", "--at", "3,0") == 0
    assert pxart.parse(out).get("walk/2").grid == ["sbbs", "sbbs", "s..s"]


def test_compose_key_conflict(tmp_path):
    a = write(tmp_path, "a.px", "k #000000\nk\n")
    b = write(tmp_path, "b.px", "k #ffffff\nk\n")
    assert run("compose", "-o", tmp_path / "o.px", "--size", "2x1", f"{a}@0,0", f"{b}@1,0") == 1


# ---------------------------------------------------------------- converting

def test_from_png_round_trip(tmp_path):
    img = Image.new("RGBA", (3, 2), (0, 0, 0, 0))
    img.putpixel((0, 0), (10, 20, 30, 255))
    img.putpixel((2, 1), (200, 100, 50, 128))
    img.save(tmp_path / "r.png")
    assert run("from-png", tmp_path / "r.png", "-o", tmp_path / "r.px") == 0
    doc = pxart.parse(tmp_path / "r.px")
    assert pxart.pixels(doc.image(doc.frames[0])) == pxart.pixels(img)


def test_export_frames_aseprite_tiled(tmp_path):
    p = write(tmp_path, "m.px", MULTI.replace("kggk\nkggk\n", ".kk.\nkggk\n"))
    assert run("export", p, "--frames", tmp_path / "f", "--aseprite", tmp_path / "s.json",
               "--tiled", tmp_path / "t.tsj") == 0
    assert (tmp_path / "f" / "walk" / "down" / "0.png").exists() and (tmp_path / "f" / "idle.png").exists()
    ase = json.loads((tmp_path / "s.json").read_text())
    assert [f["filename"] for f in ase["frames"]] == ["walk/down/0", "walk/down/1", "idle"]
    assert [f["duration"] for f in ase["frames"]] == [120, 200, 100]
    assert ase["meta"]["frameTags"] == [{"name": "walk/down", "from": 0, "to": 1, "direction": "pingpong",
                                         "color": "#000000ff", "repeat": "2"}]
    sheet = Image.open(tmp_path / "s.png")
    assert sheet.size == (ase["meta"]["size"]["w"], ase["meta"]["size"]["h"])
    tsj = json.loads((tmp_path / "t.tsj").read_text())
    assert tsj["type"] == "tileset" and tsj["tilecount"] == 3 and tsj["tilewidth"] == 4
    assert tsj["tiles"][0]["animation"] == [{"tileid": 0, "duration": 120}, {"tileid": 1, "duration": 200}]


def test_export_tiled_needs_uniform_size(tmp_path):
    p = write(tmp_path, "m.px", MULTI)  # idle is 4x2 too, so make one differ
    p.write_text(MULTI.replace("kggk\nkggk\n", "kggkk\nkggkk\n"))
    assert run("export", p, "--tiled", tmp_path / "t.tsj") == 1


def test_palette_export(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    assert run("palette", p, "--export", tmp_path / "p.gpl") == 0
    gpl = (tmp_path / "p.gpl").read_text()
    assert gpl.startswith("GIMP Palette") and " 63  38  49\tk" in gpl
    assert run("palette", p, "--export", tmp_path / "p.hex") == 0
    assert (tmp_path / "p.hex").read_text().split() == ["3f2631", "43e1b3", "e43b44"]


# ---------------------------------------------------------------- looking / checking

def test_anim_writes_gif_and_strip_with_file_durations(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    assert run("anim", f"{p}:walk/down", "-o", tmp_path / "w.gif") == 0
    gif = Image.open(tmp_path / "w.gif")
    durs = []
    for i in range(gif.n_frames):
        gif.seek(i)
        durs.append(gif.info["duration"])
    assert durs == [120, 200]
    assert (tmp_path / "w.strip.png").exists()


def test_check_exit_codes_and_palette(tmp_path):
    good = write(tmp_path, "g.px", "k #3f2631\nk\n")
    off = write(tmp_path, "o.px", "k #ff00ff\nk\n")
    broken = write(tmp_path, "b.px", "k #3f2631\nkq\n")
    pal = write(tmp_path, "p.hex", "3f2631\n")
    assert run("check", good, "--palette", pal, "--size", "1x1") == 0
    assert run("check", good, off, "--palette", pal) == 1
    assert run("check", good, broken) == 1


def test_render_sheet_onion_scene(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    single = write(tmp_path, "s.px", LEGACY)
    assert run("render", single, f"{p}:walk/down", "-o", tmp_path / "prev.png", "--png") == 0
    assert (tmp_path / "s.png").exists()
    assert run("sheet", p, "-o", tmp_path / "sh.png", "--scale", "1") == 0
    assert run("onion", f"{p}:walk/down/0", f"{p}:walk/down/1", "-o", tmp_path / "on.png") == 0
    assert run("scene", "-o", tmp_path / "sc.png", "--size", "8x8", f"{single}@1,1", f"{p}:idle@4,4") == 0
    assert run("scene", "-o", tmp_path / "sc.png", f"{p}@0,0") == 1  # 3 frames: ambiguous


# ---------------------------------------------------------------- loop-3 fixes

def test_mixed_sizes_allowed_and_noted(tmp_path, capsys):
    p = write(tmp_path, "m.px", "k #000000\n@frame w/0\nk\n@frame w/1\nkk\n")
    assert run("check", p) == 0
    assert "mixes frame sizes" in capsys.readouterr().out


def test_compose_sizes_from_animation_and_warns_on_crop(tmp_path, capsys):
    out = write(tmp_path, "h.px", "k #000000\n@frame w/0\nkkkk\nkkkk\n")
    big = write(tmp_path, "big.px", "k #000000\nkkkkk\n")
    assert run("compose", "-o", f"{out}:w/1", f"{big}@0,1") == 0
    assert pxart.parse(out).get("w/1").size == (4, 2)
    assert "1 px of big fall outside the 4x2 canvas" in capsys.readouterr().out


def test_compose_into_palette_only_file(tmp_path):
    out = write(tmp_path, "h.px", "@palette base.px\n")
    write(tmp_path, "base.px", "k #000000\n")
    layer = write(tmp_path, "l.px", "@palette base.px\nk.\n")
    assert run("compose", "-o", f"{out}:idle/0", f"{layer}@0,0") == 0
    doc = pxart.parse(out)
    assert doc.get("idle/0").grid == ["k."] and doc.palette_refs == ["base.px"] and "k" not in doc.palette


def test_dup_lands_at_end_of_its_animation(tmp_path):
    p = write(tmp_path, "m.px", "k #000000\n@frame idle/0\nk\n@frame shoot/0\nk\n@frame shoot/1\nk\n")
    assert run("dup", f"{p}:idle/0", "shoot/2") == 0
    assert [f.id for f in pxart.parse(p).frames] == ["idle/0", "shoot/0", "shoot/1", "shoot/2"]


def test_frames_rm_and_move(tmp_path):
    p = write(tmp_path, "m.px", "k #000000\n@frame a/0\nk\n@frame a/1\nk\n@frame a/2\nk\n")
    assert run("frames", p, "--move", "a/2", "--before", "a/0") == 0
    assert [f.id for f in pxart.parse(p).frames] == ["a/2", "a/0", "a/1"]
    assert run("frames", p, "--rm", "a/0") == 0
    assert [f.id for f in pxart.parse(p).frames] == ["a/2", "a/1"]


def test_variant_selector_suffix(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    (it,) = pxart.items(f"{p}:idle%night")
    assert it.img.getpixel((1, 0))[:3] == (0x25, 0x95, 0x6A)
    assert run("scene", "-o", tmp_path / "s.png", "--size", "8x8", f"{p}:idle%night@0,0") == 0


def test_missing_file_is_a_coded_error(tmp_path, capsys):
    assert run("render", tmp_path / "nope.px", "-o", tmp_path / "x.png") == 1


def test_palette_export_used_only(tmp_path):
    p = write(tmp_path, "m.px", "k #000000\nj #ffffff\nk\n")
    assert run("palette", p, "--export", tmp_path / "p.hex", "--used") == 0
    assert (tmp_path / "p.hex").read_text().split() == ["000000"]


def test_aseprite_and_tiled_share_identical_sheet(tmp_path):
    p = write(tmp_path, "m.px", "k #000000\nj #ffffff\n@frame b/0\nk\n@frame a/0\nj\n@frame b/1\nj\n")
    assert run("export", p, "--aseprite", tmp_path / "x.json") == 0
    first = pxart.pixels(Image.open(tmp_path / "x.png").convert("RGBA"))
    assert run("export", p, "--tiled", tmp_path / "x.tsj") == 0
    assert pxart.pixels(Image.open(tmp_path / "x.png").convert("RGBA")) == first


def test_from_png_multi_frame_shares_keys_across_runs(tmp_path):
    a = Image.new("RGBA", (2, 1)); a.putpixel((0, 0), (1, 1, 1, 255)); a.putpixel((1, 0), (2, 2, 2, 255))
    b = Image.new("RGBA", (2, 1)); b.putpixel((0, 0), (2, 2, 2, 255)); b.putpixel((1, 0), (3, 3, 3, 255))
    a.save(tmp_path / "000.png"); b.save(tmp_path / "001.png")
    out = tmp_path / "w.px"
    assert run("from-png", tmp_path / "000.png", "-o", out, "--id", "walk/down") == 0
    assert run("from-png", tmp_path / "001.png", "-o", out, "--id", "walk/down") == 0
    doc = pxart.parse(out)
    assert [f.id for f in doc.frames] == ["walk/down/000", "walk/down/001"]
    assert pxart.pixels(doc.image(doc.get("walk/down/000"))) == pxart.pixels(a)
    assert pxart.pixels(doc.image(doc.get("walk/down/001"))) == pxart.pixels(b)
    assert len(doc.palette) == 3  # the shared color reused its key
    assert run("from-png", tmp_path / "000.png", tmp_path / "001.png", "-o", tmp_path / "x.px") == 0
    assert [f.id for f in pxart.parse(tmp_path / "x.px").frames] == ["000", "001"]


def test_from_png_into_palette_file_reuses_its_keys(tmp_path):
    write(tmp_path, "pal.px", "o #010101\n")
    img = Image.new("RGBA", (1, 1), (1, 1, 1, 255)); img.save(tmp_path / "i.png")
    out = write(tmp_path, "o.px", "@palette pal.px\n")
    assert run("from-png", tmp_path / "i.png", "-o", out, "--id", "idle") == 0
    doc = pxart.parse(out)
    assert doc.get("idle/i").grid == ["o"] and doc.palette == {}


def test_anim_strip_diffs_frames_of_different_sizes(tmp_path, capsys):
    p = write(tmp_path, "m.px", "k #000000\n@frame w/0\nkk\nkk\n@frame w/1\nk.k\n")
    assert run("anim", f"{p}:w", "-o", tmp_path / "w.gif") == 0
    strip = Image.open(tmp_path / "w.strip.png").convert("RGBA")
    magenta = sum(1 for px in pxart.pixels(strip) if px[:3] == (255, 40, 200))
    assert magenta > 0  # both diff cells drawn, not skipped for the size mismatch
