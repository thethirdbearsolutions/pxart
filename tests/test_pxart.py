import io
import json
import math
import pathlib
import re
import shlex
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


def run_err(*argv):
    """Run the CLI expecting an error exit; returns the message it exits with."""
    with pytest.raises(SystemExit) as e:
        pxart.main([str(a) for a in argv])
    assert not isinstance(e.value.code, int) or e.value.code != 0
    return str(e.value.code)


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


# ---------------------------------------------------------------- loops A/B/C fixes

def test_variants_inherited_from_palette_file(tmp_path):
    write(tmp_path, "pal.px", "k #000000\ng #00ff00\n\n@variant night\ng #003300\n")
    p = write(tmp_path, "s.px", "@palette pal.px\nkg\n")
    doc = pxart.parse(p)
    assert doc.image(doc.frames[0], "night").getpixel((1, 0))[:3] == (0, 0x33, 0)
    assert "@variant" not in doc.text()  # inherited, not copied in
    local = write(tmp_path, "l.px", "@palette pal.px\n\n@variant night\nk #111111\n\nkg\n")
    img = pxart.parse(local).image(pxart.parse(local).frames[0], "night")
    assert img.getpixel((0, 0))[:3] == (0x11, 0x11, 0x11) and img.getpixel((1, 0))[:3] == (0, 0x33, 0)


def test_check_accepts_palette_files_and_notes_overrides(tmp_path, capsys):
    pal = write(tmp_path, "pal.px", "k #000000\n")
    s = write(tmp_path, "s.px", "@palette pal.px\nk #ffffff\nk\n")
    assert run("check", pal, s, pal) == 0
    out = capsys.readouterr().out
    assert "palette file, 1 key(s)" in out and out.count("pal.px: palette file") == 1
    assert "local keys override @palette colors: k" in out


def test_outputs_create_their_directories(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    assert run("render", p, "-o", tmp_path / "a" / "b" / "prev.png") == 0
    assert run("anim", f"{p}:walk/down", "-o", tmp_path / "c" / "w.gif") == 0
    assert run("palette", p, "--export", tmp_path / "d" / "p.gpl") == 0


def test_anim_prints_numbers(tmp_path, capsys):
    p = write(tmp_path, "m.px", MULTI)
    assert run("anim", f"{p}:walk/down", "-o", tmp_path / "w.gif") == 0
    out = capsys.readouterr().out
    assert "walk/down/1" in out and "then" in out and "px" in out


def test_row_width_message_says_majority(tmp_path):
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(write(tmp_path, "a.px", "k #000000\nkkkkk\nkkkkkk\nkkkkkk\n"))
    assert "2 of 3 rows are 6 wide" in str(e.value)


def test_dup_into_new_animation_goes_after_source_group_and_copies_timing(tmp_path):
    p = write(tmp_path, "m.px", "k #000000\n@anim crawl/right ms=150\n@frame crawl/right/0\nk\n"
              "@frame crawl/right/1\nk\n@frame other\nk\n")
    assert run("dup", f"{p}:crawl/right/0", "crawl/left/0") == 0
    assert run("dup", f"{p}:crawl/right/1", "crawl/left/1") == 0
    doc = pxart.parse(p)
    assert [f.id for f in doc.frames] == ["crawl/right/0", "crawl/right/1", "crawl/left/0", "crawl/left/1", "other"]
    assert doc.anims["crawl/left"]["ms"] == 150


def test_shift_wrap(tmp_path):
    p = write(tmp_path, "t.px", "k #000000\nk..\n...\n")
    assert run("shift", p, "--dx", "-1", "--wrap") == 0
    assert pxart.parse(p).frames[0].grid == ["..k", "..."]


def test_still_groups_skip_animation_exports(tmp_path, capsys):
    p = write(tmp_path, "ui.px", "k #000000\n@still life\n@frame life/full\nk\n@frame life/empty\nkk\n")
    doc = pxart.parse(p)
    assert doc.stills == ["life"] and "@still life" in doc.text()
    assert run("check", p) == 0
    assert "mixes frame sizes" not in capsys.readouterr().out
    assert run("export", p, "--aseprite", tmp_path / "u.json") == 0
    assert json.loads((tmp_path / "u.json").read_text())["meta"]["frameTags"] == []


def test_scene_map(tmp_path):
    write(tmp_path, "tiles.px", "k #000000\nw #ffffff\n@frame floor\nkk\nkk\n@frame wall\nww\nww\n")
    m = write(tmp_path, "room.map", "# a room\nf tiles.px:floor\nW tiles.px:wall\n\nWWW\nf.f\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    img = Image.open(tmp_path / "s.png").convert("RGBA")
    assert img.size == (6, 4)
    assert img.getpixel((0, 0))[:3] == (255, 255, 255) and img.getpixel((0, 2))[:3] == (0, 0, 0)
    assert img.getpixel((2, 2))[:3] == pxart.hex2rgba("#472d3c")[:3]  # '.' left empty
    bad = write(tmp_path, "bad.map", "f tiles.px:floor\n\nfq\n")
    assert run("scene", "-o", tmp_path / "x.png", "--map", bad, "--tile", "2x2") == 1


def test_set_and_crop(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\n@frame f\nkkk\nkkk\nkkk\n")
    assert run("set", f"{p}:f", "j", "1,1", "2,0") == 0
    assert pxart.parse(p).get("f").grid == ["kkj", "kjk", "kkk"]
    assert run("set", f"{p}:f", "j", "5,5") == 1
    assert run("crop", f"{p}:f", "1,0,2,2", "-o", f"{p}:g") == 0
    assert pxart.parse(p).get("g").grid == ["kj", "jk"]


def test_from_png_palette_option(tmp_path):
    write(tmp_path, "pal.px", "o #010101\n")
    Image.new("RGBA", (1, 1), (1, 1, 1, 255)).save(tmp_path / "i.png")
    out = tmp_path / "sub" / "o.px"
    out.parent.mkdir()
    assert run("from-png", tmp_path / "i.png", "-o", out, "--id", "x", "--palette", tmp_path / "pal.px") == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == ["../pal.px"] and doc.get("x/i").grid == ["o"] and doc.palette == {}


def test_sheet_of_big_pngs_does_not_overflow(tmp_path):
    Image.new("RGBA", (200, 120), (255, 0, 0, 255)).save(tmp_path / "big.png")
    assert run("sheet", tmp_path / "big.png", tmp_path / "big.png", "-o", tmp_path / "s.png", "--scale", "1",
               "--cols", "1") == 0
    img = Image.open(tmp_path / "s.png").convert("RGBA")
    red_rows = [y for y in range(img.height) if img.getpixel((img.width - 5, y))[:3] == (255, 0, 0)]
    assert len(red_rows) <= 2 * 120  # nothing extra below each cell


# ---------------------------------------------------------------- loop D fixes: map '#' rows

TILES = "k #000000\nw #ffffff\n@frame floor\nkk\nkk\n@frame wall\nww\nww\n"


def scene_px(path):
    return Image.open(path).convert("RGBA")


def test_map_hash_row_is_a_row_not_a_comment(tmp_path):
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "room.map", "# a room\nf tiles.px:floor\n# tiles.px:wall\n\n###\nf.f\n###\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.size == (6, 6)  # three rows, not two
    assert img.getpixel((0, 0))[:3] == (255, 255, 255) and img.getpixel((0, 5))[:3] == (255, 255, 255)
    assert img.getpixel((0, 2))[:3] == (0, 0, 0)


def test_map_hash_legend_line_defines_hash(tmp_path):
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "room.map", "# tiles.px:wall\n\n#\n")
    placed, size = pxart.read_map(m, (2, 2))
    assert size == (2, 2) and placed == [(str(tmp_path / "tiles.px:wall"), 0, 0)]


def test_map_hash_legend_line_with_variant(tmp_path):
    write(tmp_path, "tiles.px", TILES + "\n")
    m = write(tmp_path, "room.map", "# tiles.px:wall%dark\n\n##\n")
    placed, _ = pxart.read_map(m, (2, 2))
    assert [p[0] for p in placed] == [str(tmp_path / "tiles.px:wall%dark")] * 2


def test_map_comments_before_rows_still_skipped(tmp_path):
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "room.map", "# header comment\n# another one here\nf tiles.px:floor\n# note\n\nff\n")
    placed, size = pxart.read_map(m, (2, 2))
    assert size == (4, 2) and len(placed) == 2


def test_map_comment_after_blank_is_a_row(tmp_path):
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "room.map", "f tiles.px:floor\n\n# oops\nff\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.read_map(m, (2, 2))
    assert codes(e) == ["E_UNKNOWN_KEY"] and "'#'" in str(e.value) and "legend line '# FILE'" in str(e.value)


def test_map_undefined_hash_errors_clearly(tmp_path, capsys):
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "room.map", "f tiles.px:floor\n\n####\nffff\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2") == 1


def test_map_hash_comment_with_two_words_is_comment(tmp_path):
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "room.map", "# walls\nf tiles.px:floor\n\nf\n")
    placed, size = pxart.read_map(m, (2, 2))
    assert size == (2, 2) and "#" not in [p[0] for p in placed]


def test_map_row_count_matches_rows_with_hash_anywhere(tmp_path):
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "room.map", "# tiles.px:wall\nf tiles.px:floor\n\n####\n#ff#\n#ff#\n####\n")
    placed, size = pxart.read_map(m, (2, 2))
    assert size == (8, 8) and len(placed) == 16


def test_help_documents_map_hash_rows():
    assert "'####'" in pxart.__doc__ and "comments only before the first row" in pxart.__doc__


# ---------------------------------------------------------------- %variant after @

def test_split_at_variant_after_at_says_where_it_goes():
    with pytest.raises(pxart.PxError) as e:
        pxart.split_at("player.px:walk/0@26,70%dark")
    assert codes(e) == ["E_BAD_ARG"]
    msg = str(e.value)
    assert "%variant goes before @" in msg and "FILE:frame%variant@x,y" in msg
    assert "player.px:walk/0%dark@26,70" in msg


def test_split_at_variant_after_at_negative_coords():
    with pytest.raises(pxart.PxError) as e:
        pxart.split_at("a.px@-3,-4%night")
    assert "a.px%night@-3,-4" in str(e.value)


def test_split_at_variant_before_at_is_fine():
    assert pxart.split_at("player.px:walk/0%dark@26,70") == ("player.px:walk/0%dark", 26, 70)


def test_split_at_plain_bad_arg_still_generic():
    with pytest.raises(pxart.PxError) as e:
        pxart.split_at("player.px")
    assert "expected FILE[:frame][%variant]@x,y" in str(e.value)
    with pytest.raises(pxart.PxError):
        pxart.split_at("player.px@1")


def test_scene_and_compose_report_variant_after_at(tmp_path, capsys):
    p = write(tmp_path, "m.px", MULTI)
    assert run("scene", "-o", tmp_path / "s.png", f"{p}:idle@0,0%night") == 1
    assert run("compose", "-o", tmp_path / "o.px", f"{p}:idle@0,0%night") == 1


# ---------------------------------------------------------------- scene --variant

VTILES = ("k #000000\nw #ffffff\n\n@variant dark\nk #010101\nw #222222\n\n@variant red\nw #ff0000\n\n"
          "@frame floor\nkk\nkk\n@frame wall\nww\nww\n")
VHERO = "h #00ff00\n\n@variant dark\nh #003300\n\n@variant red\nh #ff0000\n\nh\n"


def test_scene_variant_applies_to_map_tiles(tmp_path):
    write(tmp_path, "tiles.px", VTILES)
    m = write(tmp_path, "room.map", "f tiles.px:floor\nW tiles.px:wall\n\nWf\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1",
               "--variant", "dark") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((0, 0))[:3] == (0x22, 0x22, 0x22) and img.getpixel((2, 0))[:3] == (1, 1, 1)


def test_scene_variant_applies_to_items(tmp_path):
    hero = write(tmp_path, "hero.px", VHERO)
    assert run("scene", "-o", tmp_path / "s.png", "--size", "2x1", "--scale", "1", "--variant", "dark",
               f"{hero}@0,0") == 0
    assert scene_px(tmp_path / "s.png").getpixel((0, 0))[:3] == (0, 0x33, 0)


def test_scene_item_own_variant_wins(tmp_path):
    hero = write(tmp_path, "hero.px", VHERO)
    assert run("scene", "-o", tmp_path / "s.png", "--size", "2x1", "--scale", "1", "--variant", "dark",
               f"{hero}@0,0", f"{hero}%red@1,0") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((0, 0))[:3] == (0, 0x33, 0) and img.getpixel((1, 0))[:3] == (255, 0, 0)


def test_scene_map_legend_own_variant_wins(tmp_path):
    write(tmp_path, "tiles.px", VTILES)
    m = write(tmp_path, "room.map", "f tiles.px:floor\nW tiles.px:wall%red\n\nWf\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1",
               "--variant", "dark") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((0, 0))[:3] == (255, 0, 0) and img.getpixel((2, 0))[:3] == (1, 1, 1)


def test_scene_without_variant_uses_base(tmp_path):
    write(tmp_path, "tiles.px", VTILES)
    hero = write(tmp_path, "hero.px", VHERO)
    m = write(tmp_path, "room.map", "W tiles.px:wall\n\nW\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1",
               f"{hero}@0,0") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((0, 0))[:3] == (0, 255, 0) and img.getpixel((1, 1))[:3] == (255, 255, 255)


def test_scene_variant_missing_in_a_file_is_an_error(tmp_path):
    hero = write(tmp_path, "hero.px", "h #00ff00\nh\n")
    assert run("scene", "-o", tmp_path / "s.png", "--size", "2x1", "--variant", "dark", f"{hero}@0,0") == 1


def test_scene_variant_leaves_png_items_alone(tmp_path):
    Image.new("RGBA", (1, 1), (9, 8, 7, 255)).save(tmp_path / "p.png")
    assert run("scene", "-o", tmp_path / "s.png", "--size", "1x1", "--scale", "1", "--variant", "dark",
               f"{tmp_path / 'p.png'}@0,0") == 0
    assert scene_px(tmp_path / "s.png").getpixel((0, 0))[:3] == (9, 8, 7)


def test_one_frame_takes_a_variant(tmp_path):
    hero = write(tmp_path, "hero.px", VHERO)
    assert pxart.one_frame(str(hero), variant="dark").img.getpixel((0, 0))[:3] == (0, 0x33, 0)
    assert pxart.one_frame(f"{hero}%red", variant="dark").img.getpixel((0, 0))[:3] == (255, 0, 0)


# ---------------------------------------------------------------- zsh-mangled output notes

def test_compose_notes_non_px_output(tmp_path, capsys):
    layer = write(tmp_path, "l.px", "k #000000\nk\n")
    out = tmp_path / "herok"  # what zsh makes of "$OUT:k..."
    assert run("compose", "-o", out, f"{layer}@0,0") == 0
    got = capsys.readouterr().out
    assert "doesn't end in .px" in got and '"${VAR}:sel"' in got and '"$VAR:sel"' in got
    assert out.exists()  # it's only a note; the write still happens


def test_compose_px_output_has_no_note(tmp_path, capsys):
    layer = write(tmp_path, "l.px", "k #000000\nk\n")
    assert run("compose", "-o", f"{tmp_path / 'h.px'}:idle/0", f"{layer}@0,0") == 0
    assert "doesn't end in .px" not in capsys.readouterr().out


def test_compose_mangled_frame_selector_notes(tmp_path, capsys):
    layer = write(tmp_path, "l.px", "k #000000\nk\n")
    out = f"{tmp_path / 'hero.pxalk'}/0"  # "$OUT:walk/0" after zsh's :w modifier
    assert run("compose", "-o", out, f"{layer}@0,0") == 0
    assert "doesn't end in .px" in capsys.readouterr().out


def test_dup_notes_non_px_output(tmp_path, capsys):
    p = write(tmp_path, "m.px", MULTI)
    assert run("dup", f"{p}:idle", "idle2", "-o", tmp_path / "copy") == 0
    assert "doesn't end in .px" in capsys.readouterr().out
    assert pxart.parse(tmp_path / "copy").get("idle2")


def test_dup_px_output_has_no_note(tmp_path, capsys):
    p = write(tmp_path, "m.px", MULTI)
    assert run("dup", f"{p}:idle", "idle2") == 0
    assert run("dup", f"{p}:idle", "idle3", "-o", tmp_path / "c.px") == 0
    assert "doesn't end in .px" not in capsys.readouterr().out


def test_note_suffix_helper(capsys):
    pxart.note_suffix("a.px")
    assert capsys.readouterr().out == ""
    pxart.note_suffix("a.pxalk/0")
    assert capsys.readouterr().out.startswith("note: output 'a.pxalk/0'")


# ---------------------------------------------------------------- failed @palette: no key-error flood

def test_missing_palette_file_suppresses_unknown_key_errors(tmp_path):
    p = write(tmp_path, "s.px", "@palette nope.px\n@frame a\nkgk\nggg\n@frame b\nkkk\nzzz\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p)
    assert codes(e) == ["E_PALETTE_FILE"]
    assert "unknown-key checks were skipped" in str(e.value)


def test_broken_palette_file_suppresses_unknown_key_errors(tmp_path):
    write(tmp_path, "pal.px", "k #12345\n")
    p = write(tmp_path, "s.px", "@palette pal.px\nkk\nkk\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p)
    assert codes(e) == ["E_PALETTE_FILE"] and "has errors" in str(e.value)
    assert str(e.value).count("unknown-key checks were skipped") == 1


def test_failed_palette_still_reports_other_errors(tmp_path):
    p = write(tmp_path, "s.px", "@palette nope.px\nkk\nk\nkk\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p)
    assert sorted(codes(e)) == ["E_PALETTE_FILE", "E_ROW_WIDTH"]


def test_failed_palette_suppresses_variant_key_errors(tmp_path):
    p = write(tmp_path, "s.px", "@palette nope.px\n\n@variant dark\nk #000000\n\nk\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p)
    assert codes(e) == ["E_PALETTE_FILE"]


def test_one_good_one_failed_palette_still_skips(tmp_path):
    write(tmp_path, "good.px", "k #000000\n")
    p = write(tmp_path, "s.px", "@palette nope.px\n@palette good.px\nkq\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p)
    assert codes(e) == ["E_PALETTE_FILE"]
    p = write(tmp_path, "t.px", "@palette good.px\n@palette nope.px\nkq\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p)
    assert codes(e) == ["E_PALETTE_FILE"]


def test_good_palette_still_checks_unknown_keys(tmp_path):
    write(tmp_path, "good.px", "k #000000\n")
    p = write(tmp_path, "s.px", "@palette good.px\nkq\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p)
    assert codes(e) == ["E_UNKNOWN_KEY"]


def test_check_prints_one_palette_error_not_a_flood(tmp_path, capsys):
    p = write(tmp_path, "s.px", "@palette nope.px\n" + "kgkgkg\n" * 20)
    assert run("check", p) == 1
    out = capsys.readouterr().out
    assert "1 error(s)" in out and "E_UNKNOWN_KEY" not in out and "checks were skipped" in out


def test_nested_failed_palette_has_one_skip_line(tmp_path):
    write(tmp_path, "mid.px", "@palette nope.px\n")
    p = write(tmp_path, "s.px", "@palette mid.px\nkk\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p)
    assert codes(e) == ["E_PALETTE_FILE"] and str(e.value).count("checks were skipped") == 1


# ---------------------------------------------------------------- layout-preserving text()

BLANK_FRAMES = """pxart 1
k #3f2631
g #43e1b3

@anim walk ms=120

@frame walk/0
.kk.
kggk

@frame walk/1
.kk.
kgkk

@frame idle
kkkk
"""

TIGHT_FRAMES = """pxart 1
k #3f2631
g #43e1b3
@frame walk/0
.kk.
kggk
@frame walk/1
.kk.
kgkk
@frame idle
kkkk
"""

TOP_COMMENTS = """# hero sprite
# drawn by an agent, loop D

# palette from dungeon.px
pxart 1
@palette base.px
k #3f2631

@frame a
kk
"""

MESSY = """# alignment and case survive untouched
pxart 1
k   #3F2631
g\t#43e1b3
Z #00000080
@variant  night
g #25956A

@anim walk   ms=120  direction=pingpong
@still ui


@frame walk/0   ms=90
  .kk.
kggk
# mid-grid comment
kggk
@frame walk/1
.kk.
.kk.
.kk.


"""

NO_FINAL_NEWLINE = "k #000000\nkk\nkk"

CRLF = "pxart 1\r\nk #000000\r\n\r\n@frame a\r\nk\r\n\r\n@frame b\r\nk\r\n"

EXTENSION = "k #000000\n\n@frame a\nk\n\n@future thing\nwhatever here\n\nmore\n"

SPARSE = "\n\npxart 1\n\n\nk #000000\n\n\n\n@frame a\nk\n\n\n\n@frame b\nk\n\n\n"


@pytest.mark.parametrize("text", [LEGACY, MULTI, BLANK_FRAMES, TIGHT_FRAMES, TOP_COMMENTS, MESSY,
                                  NO_FINAL_NEWLINE, CRLF, EXTENSION, SPARSE,
                                  "k #000000\nk\n", "k #000000\n\nk\n", "pxart 1\nk #000000\n\nk\n",
                                  ". transparent\nk #000000\n\n.k\n", "k #000000\n. transparent\n.k\n"],
                         ids=["legacy", "multi", "blank-frames", "tight-frames", "top-comments", "messy",
                              "no-final-newline", "crlf", "extension", "sparse", "min", "min-blank",
                              "version-blank", "dot-first", "dot-after"])
def test_round_trip_is_byte_identical(tmp_path, text):
    if "base.px" in text:
        write(tmp_path, "base.px", "q #ffffff\n")
    p = tmp_path / "a.px"
    p.write_bytes(text.encode())
    doc = pxart.parse(p)
    assert doc.text() == text
    doc.save()
    assert p.read_bytes() == text.encode()


def test_round_trip_palette_only_file(tmp_path):
    text = "# shared palette\n\nk #3f2631\ng #43e1b3\n\n@variant night\ng #25956a\n"
    p = write(tmp_path, "pal.px", text)
    assert pxart.parse(p, palette_only=True).text() == text


def test_editing_one_frame_changes_only_its_rows(tmp_path):
    for layout in (BLANK_FRAMES, TIGHT_FRAMES):
        p = write(tmp_path, "a.px", layout)
        assert run("set", f"{p}:walk/1", "g", "0,0") == 0
        before, after = layout.splitlines(), p.read_text().splitlines()
        assert len(before) == len(after)
        assert [i for i, (x, y) in enumerate(zip(before, after)) if x != y] == [before.index("kgkk") - 1]


def test_flip_keeps_comments_and_spacing(tmp_path):
    p = write(tmp_path, "a.px", MESSY)
    assert run("flip", f"{p}:walk/1") == 0
    got = p.read_text()
    assert "# mid-grid comment" in got and "k   #3F2631" in got and "@anim walk   ms=120  direction=pingpong" in got
    assert got.endswith(".kk.\n\n\n") and "@still ui\n\n\n@frame walk/0   ms=90\n  .kk.\n" in got


def test_changed_line_is_rewritten_canonically(tmp_path):
    p = write(tmp_path, "a.px", MESSY)
    assert run("recolor", p, "k=#000000") == 0
    got = p.read_text()
    assert "k #000000\n" in got and "#3F2631" not in got and "g\t#43e1b3" in got


def test_dup_follows_blank_frame_spacing(tmp_path):
    p = write(tmp_path, "a.px", BLANK_FRAMES)
    assert run("dup", f"{p}:walk/1", "walk/2") == 0
    assert p.read_text() == BLANK_FRAMES.replace("\n@frame idle", "\n@frame walk/2\n.kk.\nkgkk\n\n@frame idle")


def test_dup_follows_tight_frame_spacing(tmp_path):
    p = write(tmp_path, "a.px", TIGHT_FRAMES)
    assert run("dup", f"{p}:walk/1", "walk/2") == 0
    assert p.read_text() == TIGHT_FRAMES.replace("@frame idle", "@frame walk/2\n.kk.\nkgkk\n@frame idle")


def test_compose_new_frame_follows_tight_spacing(tmp_path):
    p = write(tmp_path, "a.px", TIGHT_FRAMES)
    layer = write(tmp_path, "l.px", "k #3f2631\nkk\n")
    assert run("compose", "-o", f"{p}:extra", "--size", "2x1", f"{layer}@0,0") == 0
    assert p.read_text() == TIGHT_FRAMES + "@frame extra\nkk\n"


def test_palette_add_inserts_one_line(tmp_path):
    p = write(tmp_path, "a.px", BLANK_FRAMES)
    assert run("palette", p, "--add", "z=#123456") == 0
    assert p.read_text() == BLANK_FRAMES.replace("g #43e1b3\n", "g #43e1b3\nz #123456\n")


def test_frames_rm_takes_its_comment_along(tmp_path):
    text = "k #000000\n\n# first\n@frame a\nk\n\n# second\n@frame b\nk\n"
    p = write(tmp_path, "a.px", text)
    assert run("frames", p, "--rm", "a") == 0
    assert p.read_text() == "k #000000\n\n# second\n@frame b\nk\n"


def test_frames_move_keeps_frame_comments(tmp_path):
    text = "k #000000\n\n# first\n@frame a\nk\n\n# second\n@frame b\nj\n"
    p = write(tmp_path, "a.px", text.replace("j", "k"))
    assert run("frames", p, "--move", "b", "--before", "a") == 0
    doc = pxart.parse(p)
    assert [f.id for f in doc.frames] == ["b", "a"]
    assert "# second\n@frame b" in p.read_text() and "# first\n@frame a" in p.read_text()


def test_mid_file_comments_are_kept(tmp_path):
    text = "pxart 1\n# keys\nk #000000\n# frames below\n\n@frame a\n# row comment\nk\n# trailing\n"
    p = write(tmp_path, "a.px", text)
    assert pxart.parse(p).text() == text
    assert run("flip", p) == 0
    assert p.read_text() == text


def test_cropped_rows_drop_their_comments_only(tmp_path):
    text = "k #000000\n@frame a\nkk\n# about row 2\nkk\n"
    p = write(tmp_path, "a.px", text)
    doc = pxart.parse(p)
    doc.frames[0].grid = ["k."]
    assert doc.text() == "k #000000\n@frame a\nk.\n"


def test_new_doc_text_unchanged_defaults():
    doc = pxart.Doc("x.px")
    doc.version = 1
    doc.palette["k"] = (0, 0, 0, 255)
    doc.anims["w"] = {"ms": 100}
    doc.frames = [pxart.Frame("w/0", ["k"]), pxart.Frame("w/1", ["k"])]
    assert doc.text() == "pxart 1\nk #000000\n\n@anim w ms=100\n\n@frame w/0\nk\n\n@frame w/1\nk\n"


def test_new_implicit_doc_text_defaults():
    doc = pxart.Doc("x.px")
    doc.palette["k"] = (0, 0, 0, 255)
    doc.implicit, doc.frames = True, [pxart.Frame(None, ["k."])]
    assert doc.text() == "k #000000\n\nk.\n"


def test_from_png_stdout_unchanged(tmp_path, capsys):
    Image.new("RGBA", (2, 1), (1, 2, 3, 255)).save(tmp_path / "i.png")
    assert run("from-png", tmp_path / "i.png") == 0
    assert capsys.readouterr().out == "pxart 1\na #010203\n\naa\n"


def test_text_reparses_to_same_doc_after_reorder(tmp_path):
    p = write(tmp_path, "a.px", MESSY)
    doc = pxart.parse(p)
    doc.frames.reverse()
    again = pxart.parse(p, text=doc.text())
    assert [(f.id, f.grid) for f in again.frames] == [(f.id, f.grid) for f in doc.frames]
    assert again.variants == doc.variants and again.palette == doc.palette


def test_help_documents_layout_limits():
    assert "sections are written in a fixed order" in pxart.__doc__


# ---------------------------------------------------------------- @still *

PARTS = "k #000000\n@still *\n@frame hat/big\nkk\n@frame hat/small\nk\n@frame body/a\nkkk\n@frame loose\nk\n"


def test_still_star_marks_every_group(tmp_path):
    doc = pxart.parse(write(tmp_path, "p.px", PARTS))
    assert doc.stills == ["*"]
    assert not doc.animated("hat") and not doc.animated("body") and not doc.animated("anything/else")


def test_still_star_round_trips(tmp_path):
    p = write(tmp_path, "p.px", PARTS)
    assert pxart.parse(p).text() == PARTS


def test_still_star_skips_mixed_size_note(tmp_path, capsys):
    p = write(tmp_path, "p.px", PARTS)
    assert run("check", p) == 0
    assert "mixes frame sizes" not in capsys.readouterr().out


def test_without_still_star_mixed_sizes_are_noted(tmp_path, capsys):
    p = write(tmp_path, "p.px", PARTS.replace("@still *\n", ""))
    assert run("check", p) == 0
    assert "mixes frame sizes" in capsys.readouterr().out


def test_still_star_no_aseprite_tags_or_tiled_anims(tmp_path):
    p = write(tmp_path, "p.px", "k #000000\n@still *\n@frame a/0\nk\n@frame a/1\nk\n@frame b/0\nk\n@frame b/1\nk\n")
    assert run("export", p, "--aseprite", tmp_path / "x.json", "--tiled", tmp_path / "x.tsj") == 0
    assert json.loads((tmp_path / "x.json").read_text())["meta"]["frameTags"] == []
    assert json.loads((tmp_path / "x.tsj").read_text())["tiles"] == []


def test_still_star_with_other_args_is_bad(tmp_path):
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(write(tmp_path, "p.px", "k #000000\n@still * x\n@frame a/0\nk\n"))
    assert codes(e) == ["E_BAD_ID"]
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(write(tmp_path, "q.px", "k #000000\n@still **\n@frame a/0\nk\n"))
    assert codes(e) == ["E_BAD_ID"]


def test_still_star_works_in_strict_mode(tmp_path):
    pxart.parse(write(tmp_path, "p.px", PARTS), strict=True)


# ---------------------------------------------------------------- mask

def square(tmp_path, n=8, name="sq.px", extra=""):
    return write(tmp_path, name, "k #000000\n" + extra + ("k" * n + "\n") * n)


def test_mask_keep_rect(tmp_path):
    p = square(tmp_path, 4)
    assert run("mask", p, "--keep", "1,1,2,2") == 0
    assert pxart.parse(p).frames[0].grid == ["....", ".kk.", ".kk.", "...."]


def test_mask_keep_rect_partly_outside(tmp_path):
    p = square(tmp_path, 3)
    assert run("mask", p, "--keep=-1,-1,3,3") == 0
    assert pxart.parse(p).frames[0].grid == ["kk.", "kk.", "..."]


def test_mask_keep_rect_whole_frame_changes_nothing(tmp_path):
    p = square(tmp_path, 3)
    before = p.read_text()
    assert run("mask", p, "--keep", "0,0,3,3") == 0
    assert p.read_text() == before


def test_mask_keep_circle_hard_edge(tmp_path):
    p = square(tmp_path, 7)
    assert run("mask", p, "--keep-circle", "3,3,2") == 0
    assert pxart.parse(p).frames[0].grid == [
        ".......",
        "...k...",
        "..kkk..",
        ".kkkkk.",
        "..kkk..",
        "...k...",
        ".......",
    ]


def test_mask_keep_circle_matches_distance_rule(tmp_path):
    p = square(tmp_path, 16)
    assert run("mask", p, "--keep-circle", "7.5,7.5,6") == 0
    g = pxart.parse(p).frames[0].grid
    for y in range(16):
        for x in range(16):
            assert (g[y][x] == "k") == ((x - 7.5) ** 2 + (y - 7.5) ** 2 <= 36)


def test_mask_dither_band(tmp_path):
    p = square(tmp_path, 24)
    assert run("mask", p, "--keep-circle", "12,12,10", "--dither", "4") == 0
    g = pxart.parse(p).frames[0].grid
    for y in range(24):
        for x in range(24):
            d = ((x - 12) ** 2 + (y - 12) ** 2) ** 0.5
            if d <= 6:
                assert g[y][x] == "k"  # solid core
            if d > 10:
                assert g[y][x] == "."  # nothing past the radius
    band = [(x, y) for y in range(24) for x in range(24) if 6 < ((x - 12) ** 2 + (y - 12) ** 2) ** 0.5 <= 10]
    kept = sum(g[y][x] == "k" for x, y in band)
    assert 0 < kept < len(band)  # partly kept: a dither, not a hard edge


def test_mask_dither_falls_off_outward(tmp_path):
    p = square(tmp_path, 40)
    assert run("mask", p, "--keep-circle", "20,20,18", "--dither", "8") == 0
    g = pxart.parse(p).frames[0].grid

    def density(lo, hi):
        ring = [(x, y) for y in range(40) for x in range(40) if lo < ((x - 20) ** 2 + (y - 20) ** 2) ** 0.5 <= hi]
        return sum(g[y][x] == "k" for x, y in ring) / len(ring)
    assert density(10, 12) > density(12, 14) > density(14, 16) > density(16, 18)


def test_mask_dither_is_bayer_ordered(tmp_path):
    # The dither is deterministic: the same input masks the same way twice.
    a, b = square(tmp_path, 16, "a.px"), square(tmp_path, 16, "b.px")
    assert run("mask", a, "--keep-circle", "8,8,7", "--dither", "3") == 0
    assert run("mask", b, "--keep-circle", "8,8,7", "--dither", "3") == 0
    assert pxart.parse(a).frames[0].grid == pxart.parse(b).frames[0].grid
    assert pxart.BAYER4 == ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def test_mask_one_frame_leaves_others(tmp_path):
    p = write(tmp_path, "m.px", "k #000000\n@frame a\nkk\nkk\n@frame b\nkk\nkk\n")
    assert run("mask", f"{p}:a", "--keep", "0,0,1,1") == 0
    doc = pxart.parse(p)
    assert doc.get("a").grid == ["k.", ".."] and doc.get("b").grid == ["kk", "kk"]


def test_mask_output_file(tmp_path):
    p = square(tmp_path, 2)
    before = p.read_text()
    assert run("mask", p, "--keep", "0,0,1,1", "-o", tmp_path / "out.px") == 0
    assert p.read_text() == before and pxart.parse(tmp_path / "out.px").frames[0].grid == ["k.", ".."]


def test_mask_reports_erased_count(tmp_path, capsys):
    p = square(tmp_path, 3)
    assert run("mask", p, "--keep", "0,0,1,1") == 0
    assert "erased 8 px" in capsys.readouterr().out


def test_mask_bad_args(tmp_path):
    p = square(tmp_path, 3)
    assert run("mask", p, "--keep", "1,2,3") == 1
    assert run("mask", p, "--keep-circle", "1,x,3") == 1
    assert run("mask", p, "--keep", "0,0,1,1", "--dither", "2") == 1  # dither is for circles
    assert run("mask", p, "--keep-circle", "1,1,1", "--dither", "0") == 1
    with pytest.raises(SystemExit):
        pxart.main(["mask", str(p)])  # one of --keep / --keep-circle is required
    assert run("mask", p, "--keep", "0,0,1,1", "--keep-circle", "1,1,1") == 0  # loop H: shapes mix, as a union


def test_mask_keeps_layout(tmp_path):
    text = "# lamp\npxart 1\nk #000000\n\n@frame a\nkkk\nkkk\n\n@frame b\nkkk\n"
    p = write(tmp_path, "m.px", text)
    assert run("mask", f"{p}:a", "--keep", "0,0,3,1") == 0
    assert p.read_text() == text.replace("kkk\nkkk\n\n", "kkk\n...\n\n")


# ---------------------------------------------------------------- PNG items, negative coordinates

def png(tmp_path, name, size, color):
    Image.new("RGBA", size, color).save(tmp_path / name)
    return tmp_path / name


def test_scene_png_item(tmp_path):
    p = png(tmp_path, "hero.png", (2, 2), (10, 20, 30, 255))
    assert run("scene", "-o", tmp_path / "s.png", "--size", "4x4", "--scale", "1", f"{p}@1,1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((1, 1))[:3] == (10, 20, 30) and img.getpixel((2, 2))[:3] == (10, 20, 30)
    assert img.getpixel((0, 0))[:3] == pxart.hex2rgba("#472d3c")[:3]


def test_scene_png_and_px_items_together(tmp_path):
    p = png(tmp_path, "hero.png", (1, 1), (10, 20, 30, 255))
    px = write(tmp_path, "k.px", "k #ffffff\nk\n")
    assert run("scene", "-o", tmp_path / "s.png", "--size", "2x1", "--scale", "1", f"{p}@0,0", f"{px}@1,0") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((0, 0))[:3] == (10, 20, 30) and img.getpixel((1, 0))[:3] == (255, 255, 255)


def test_scene_png_translucent_item_blends(tmp_path):
    p = png(tmp_path, "glow.png", (1, 1), (255, 255, 255, 128))
    assert run("scene", "-o", tmp_path / "s.png", "--size", "1x1", "--scale", "1", "--bg", "#000000",
               f"{p}@0,0") == 0
    assert 120 <= scene_px(tmp_path / "s.png").getpixel((0, 0))[0] <= 135


def test_scene_map_png_tile(tmp_path):
    png(tmp_path, "floor.png", (2, 2), (1, 2, 3, 255))
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "room.map", "f floor.png\nW tiles.px:wall\n\nfW\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((0, 0))[:3] == (1, 2, 3) and img.getpixel((2, 0))[:3] == (255, 255, 255)


def test_scene_map_png_hash_legend(tmp_path):
    png(tmp_path, "wall.png", (2, 2), (7, 7, 7, 255))
    m = write(tmp_path, "room.map", "# wall.png\n\n##\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.size == (4, 2) and img.getpixel((3, 1))[:3] == (7, 7, 7)


def test_scene_negative_coordinates(tmp_path):
    px = write(tmp_path, "b.px", "k #ffffff\nj #ff0000\nkj\njj\n")
    assert run("scene", "-o", tmp_path / "s.png", "--size", "2x2", "--scale", "1", f"{px}@-1,-1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((0, 0))[:3] == (255, 0, 0)  # the bottom-right pixel lands at 0,0
    assert img.getpixel((1, 1))[:3] == pxart.hex2rgba("#472d3c")[:3]


def test_scene_item_fully_offscreen_is_fine(tmp_path):
    px = write(tmp_path, "b.px", "k #ffffff\nk\n")
    assert run("scene", "-o", tmp_path / "s.png", "--size", "2x2", "--scale", "1", f"{px}@-5,0", f"{px}@0,-5") == 0


def test_scene_png_negative_coordinates(tmp_path):
    p = png(tmp_path, "hero.png", (3, 3), (10, 20, 30, 255))
    assert run("scene", "-o", tmp_path / "s.png", "--size", "3x3", "--scale", "1", f"{p}@-2,1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((0, 1))[:3] == (10, 20, 30) and img.getpixel((1, 1))[:3] != (10, 20, 30)


def test_draw_at_matches_alpha_composite_for_positive(tmp_path):
    a, b = Image.new("RGBA", (4, 4)), Image.new("RGBA", (4, 4))
    s = Image.new("RGBA", (2, 2), (1, 2, 3, 255))
    pxart.draw_at(a, s, 1, 2)
    b.alpha_composite(s, (1, 2))
    assert pxart.pixels(a) == pxart.pixels(b)


def test_compose_negative_coordinates(tmp_path):
    layer = write(tmp_path, "l.px", "k #000000\nj #ffffff\nkj\njk\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x2", f"{layer}@-1,0") == 0
    assert pxart.parse(out).frames[0].grid == ["j.", "k."]


def test_help_documents_negative_coords_and_png_items():
    assert "may be negative" in pxart.__doc__ and "hero.png@3,4" in pxart.__doc__


# ---------------------------------------------------------------- loop E: compose places new frames like dup

GROUPS = "k #000000\n@frame idle/0\nk\n@frame walk/0\nk\n@frame walk/1\nk\n@frame shoot/0\nk\n"


def ids(p):
    return [f.id for f in pxart.parse(p).frames]


def test_compose_new_frame_lands_after_its_animation(tmp_path):
    p = write(tmp_path, "h.px", GROUPS)
    layer = write(tmp_path, "l.px", "k #000000\nk\n")
    assert run("compose", "-o", f"{p}:walk/2", f"{layer}@0,0") == 0
    assert ids(p) == ["idle/0", "walk/0", "walk/1", "walk/2", "shoot/0"]


def test_compose_new_frame_first_group(tmp_path):
    p = write(tmp_path, "h.px", GROUPS)
    layer = write(tmp_path, "l.px", "k #000000\nk\n")
    assert run("compose", "-o", f"{p}:idle/1", f"{layer}@0,0") == 0
    assert ids(p) == ["idle/0", "idle/1", "walk/0", "walk/1", "shoot/0"]


def test_compose_new_group_goes_at_end(tmp_path):
    p = write(tmp_path, "h.px", GROUPS)
    layer = write(tmp_path, "l.px", "k #000000\nk\n")
    assert run("compose", "-o", f"{p}:jump/0", f"{layer}@0,0") == 0
    assert ids(p) == ["idle/0", "walk/0", "walk/1", "shoot/0", "jump/0"]


def test_compose_new_top_level_frame_goes_at_end(tmp_path):
    p = write(tmp_path, "h.px", GROUPS)
    layer = write(tmp_path, "l.px", "k #000000\nk\n")
    assert run("compose", "-o", f"{p}:icon", f"{layer}@0,0") == 0
    assert ids(p)[-1] == "icon"


def test_compose_replacing_frame_keeps_its_place(tmp_path):
    p = write(tmp_path, "h.px", GROUPS)
    layer = write(tmp_path, "l.px", "k #000000\nj #ffffff\nj\n")
    assert run("compose", "-o", f"{p}:walk/0", f"{layer}@0,0") == 0
    assert ids(p) == ["idle/0", "walk/0", "walk/1", "shoot/0"] and pxart.parse(p).get("walk/0").grid == ["j"]


def test_compose_group_split_in_file_uses_its_last_frame(tmp_path):
    p = write(tmp_path, "h.px", "k #000000\n@frame a/0\nk\n@frame b/0\nk\n@frame a/1\nk\n@frame c/0\nk\n")
    layer = write(tmp_path, "l.px", "k #000000\nk\n")
    assert run("compose", "-o", f"{p}:a/2", f"{layer}@0,0") == 0
    assert ids(p) == ["a/0", "b/0", "a/1", "a/2", "c/0"]


def test_compose_repeated_adds_stay_in_order(tmp_path):
    p = write(tmp_path, "h.px", GROUPS)
    layer = write(tmp_path, "l.px", "k #000000\nk\n")
    for n in (2, 3, 4):
        assert run("compose", "-o", f"{p}:walk/{n}", f"{layer}@0,0") == 0
    assert ids(p) == ["idle/0", "walk/0", "walk/1", "walk/2", "walk/3", "walk/4", "shoot/0"]


def test_compose_new_frame_in_group_follows_spacing(tmp_path):
    p = write(tmp_path, "a.px", TIGHT_FRAMES)
    layer = write(tmp_path, "l.px", "k #3f2631\nkk\n")
    assert run("compose", "-o", f"{p}:walk/2", "--size", "2x1", f"{layer}@0,0") == 0
    assert p.read_text() == TIGHT_FRAMES.replace("@frame idle", "@frame walk/2\nkk\n@frame idle")


def test_help_documents_compose_placement():
    assert "after the last frame of its\n      animation (like dup)" in pxart.__doc__


# ---------------------------------------------------------------- loop E: frames --rm/--move output, still groups

THREE = "k #000000\n@frame a/0\nk\n@frame a/1\nk\n@frame a/2\nk\n"


def test_frames_rm_prints_only_what_it_did(tmp_path, capsys):
    p = write(tmp_path, "m.px", THREE)
    assert run("frames", p, "--rm", "a/0") == 0
    out = capsys.readouterr().out
    assert out == f"removed a/0; wrote {p}\n"
    assert "frame(s)" not in out and "(line" not in out


def test_frames_rm_several(tmp_path, capsys):
    p = write(tmp_path, "m.px", THREE)
    assert run("frames", p, "--rm", "a/0", "a/2") == 0
    assert capsys.readouterr().out == f"removed a/0, a/2; wrote {p}\n"
    assert ids(p) == ["a/1"]


def test_frames_move_after_prints_only_what_it_did(tmp_path, capsys):
    p = write(tmp_path, "m.px", THREE)
    assert run("frames", p, "--move", "a/0", "--after", "a/2") == 0
    assert capsys.readouterr().out == f"moved a/0 after a/2; wrote {p}\n"
    assert ids(p) == ["a/1", "a/2", "a/0"]


def test_frames_move_before_prints_only_what_it_did(tmp_path, capsys):
    p = write(tmp_path, "m.px", THREE)
    assert run("frames", p, "--move", "a/2", "--before", "a/0") == 0
    assert capsys.readouterr().out == f"moved a/2 before a/0; wrote {p}\n"


def test_frames_rm_and_move_together(tmp_path, capsys):
    p = write(tmp_path, "m.px", THREE)
    assert run("frames", p, "--rm", "a/1", "--move", "a/2", "--before", "a/0") == 0
    assert capsys.readouterr().out == f"removed a/1; moved a/2 before a/0; wrote {p}\n"
    assert ids(p) == ["a/2", "a/0"]


def test_frames_listing_unchanged_without_edits(tmp_path, capsys):
    p = write(tmp_path, "m.px", MULTI)
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "walk/down: 2 frame(s) [direction=pingpong, repeat=2, ms=120]" in out
    assert "walk/down/1  4x2  200ms" in out and "  idle  4x2  (line" in out and "variants: night" in out


FRAMES_MS = ("pxart 1\nk #000000\n@anim w ms=120\n@still ui\n\n@frame w/0\nk\n@frame w/1 ms=200 pivot=0,0\nk\n"
             "@frame ui/a\nk\n@frame part ms=300\nk\n@frame badge pivot=0,0\nk\n@frame solo/0\nk\n")


def test_frames_ms_only_for_animation_frames(tmp_path, capsys):
    p = write(tmp_path, "f.px", FRAMES_MS)
    assert run("frames", p) == 0
    assert capsys.readouterr().out.splitlines() == [
        "w: 2 frame(s) [ms=120]",
        "  w/0  1x1  120ms  (line 6)",
        "  w/1  1x1  200ms  pivot 0,0  (line 8)",
        "ui: 1 frame(s) [still]",
        "  ui/a  1x1  still  (line 10)",
        "(no group): 2 frame(s)",
        "  part  1x1  (line 12)",
        "  badge  1x1  pivot 0,0  (line 14)",
        "solo: 1 frame(s)",
        "  solo/0  1x1  100ms  (line 16)",
    ]


def test_frames_ms_single_grid_file_has_none(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    assert run("frames", p) == 0
    assert capsys.readouterr().out.splitlines() == ["(no group): 1 frame(s)", "  a  1x1  (line 2)"]


def test_frames_ms_star_still_says_still(tmp_path, capsys):
    p = write(tmp_path, "f.px", FRAMES_MS.replace("@still ui\n", "@still *\n"))
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "  part  1x1  still  (line" in out and "  w/0  1x1  still  (line" in out and "ms  (" not in out


def test_frames_ms_selection_listing(tmp_path, capsys):
    p = write(tmp_path, "f.px", FRAMES_MS)
    assert run("frames", f"{p}:part") == 0
    assert capsys.readouterr().out.splitlines() == ["(no group): 1 frame(s) (of 2)", "  part  1x1  (line 12)"]


def test_frames_listing_has_no_trailing_or_double_spaces(tmp_path, capsys):
    p = write(tmp_path, "f.px", FRAMES_MS)
    assert run("frames", p) == 0
    for line in capsys.readouterr().out.splitlines():
        assert line == line.rstrip() and "   " not in line.strip()


def test_frames_still_group_shows_still_not_ms(tmp_path, capsys):
    p = write(tmp_path, "ui.px", "k #000000\n@still life\n@frame life/full\nk\n@frame life/empty\nk\n"
              "@frame walk/0\nk\n")
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "life: 2 frame(s) [still]" in out
    assert "life/full  1x1  still  (line" in out and "life/empty  1x1  still" in out
    assert "walk/0  1x1  100ms" in out and "walk: 1 frame(s)\n" in out


def test_frames_still_star_shows_still_everywhere(tmp_path, capsys):
    p = write(tmp_path, "p.px", PARTS)
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "ms" not in out
    assert "hat/big  2x1  still" in out and "body/a  3x1  still" in out
    assert "loose  1x1  still" in out  # '@still *' covers top-level frames too


def test_help_documents_frames_still_and_output():
    assert "'still' for @still groups" in pxart.__doc__ and "not the listing" in pxart.__doc__


# ---------------------------------------------------------------- loop E: crop's note names the crop rectangle

def test_crop_has_no_cropped_note(tmp_path, capsys):
    # Loop J: the pixels outside the rectangle are what crop cuts away; saying so was noise.
    p = write(tmp_path, "a.px", "k #000000\n@frame f\nkkk\nkkk\nkkk\n")
    assert run("crop", f"{p}:f", "1,1,2,2", "-o", f"{p}:g") == 0
    out = capsys.readouterr().out
    assert "note:" not in out and "fall outside" not in out and "were cropped" not in out
    assert pxart.parse(p).get("g").grid == ["kk", "kk"]


def test_crop_whole_frame_has_no_note(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\n@frame f\nkk\nkk\n")
    assert run("crop", f"{p}:f", "0,0,2,2", "-o", f"{p}:g") == 0
    assert "note:" not in capsys.readouterr().out


def test_compose_size_note_still_says_size(tmp_path, capsys):
    layer = write(tmp_path, "l.px", "k #000000\nkkk\n")
    assert run("compose", "-o", tmp_path / "o.px", "--size", "2x1", f"{layer}@0,0") == 0
    assert "(size from --size)" in capsys.readouterr().out


def test_compose_size_note_other_reasons(tmp_path, capsys):
    out = write(tmp_path, "h.px", "k #000000\n@frame w/0\nkk\n")
    big = write(tmp_path, "big.px", "k #000000\nkkk\n")
    assert run("compose", "-o", f"{out}:w/1", f"{big}@0,0") == 0
    assert "(size from the rest of 'w')" in capsys.readouterr().out
    assert run("compose", "-o", f"{out}:w/1", f"{big}@1,0") == 0
    assert "(size from the frame being replaced)" in capsys.readouterr().out


# ---------------------------------------------------------------- loop E: no-op edits say so and don't write

def untouched(p, before, mtime):
    return p.read_bytes() == before and p.stat().st_mtime_ns == mtime


def snap(p):
    import os
    os.utime(p, ns=(1_000_000_000, 1_000_000_000))  # a known mtime, so a rewrite would show
    return p.read_bytes(), p.stat().st_mtime_ns


def test_set_same_key_says_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\n@frame f\nkj\n")
    before, m = snap(p)
    assert run("set", f"{p}:f", "k", "0,0") == 0
    assert capsys.readouterr().out == f"no change: {p}\n" and untouched(p, before, m)


def test_set_several_points_all_same_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\n@frame f\nkj\nkj\n")
    before, m = snap(p)
    assert run("set", f"{p}:f", "j", "1,0", "1,1") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_set_that_changes_still_writes(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\n@frame f\nkj\n")
    assert run("set", f"{p}:f", "j", "0,0") == 0
    assert capsys.readouterr().out == f"wrote {p}\n" and pxart.parse(p).get("f").grid == ["jj"]


def test_set_one_same_one_different_writes(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\n@frame f\nkj\n")
    assert run("set", f"{p}:f", "j", "0,0", "1,0") == 0
    assert capsys.readouterr().out.startswith("wrote")


def test_set_erase_already_empty_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk.\n")
    before, m = snap(p)
    assert run("set", p, ".", "1,0") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_flip_symmetric_frame_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\nkjk\njkj\n")
    before, m = snap(p)
    assert run("flip", p) == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_flip_v_symmetric_frame_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\nkj\nkk\nkj\n")
    before, m = snap(p)
    assert run("flip", p, "--v") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_flip_asymmetric_writes(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk.\n")
    assert run("flip", p) == 0
    assert capsys.readouterr().out.startswith("wrote") and pxart.parse(p).frames[0].grid == [".k"]


def test_shift_zero_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk.\n")
    before, m = snap(p)
    assert run("shift", p, "--dx", "0", "--dy", "0") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_shift_of_empty_region_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk...\n")
    before, m = snap(p)
    assert run("shift", p, "--dx", "1", "--region", "2,0,2,1") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_shift_wrap_full_cycle_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk..\n")
    before, m = snap(p)
    assert run("shift", p, "--dx", "3", "--wrap") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_recolor_same_color_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\nkj\n")
    before, m = snap(p)
    assert run("recolor", p, "k=#000000") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_recolor_same_color_other_spelling_is_no_change(tmp_path, capsys):
    # Same color as '#FFFFFF': the line keeps its spelling, so the text is unchanged.
    p = write(tmp_path, "a.px", "k #000000\nj #FFFFFF\nkj\n")
    before, m = snap(p)
    assert run("recolor", p, "j=#ffffff") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_recolor_key_with_no_pixels_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\nq #ff0000\nkj\n")
    before, m = snap(p)
    assert run("recolor", p, "q=k") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_recolor_region_missing_key_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\nkj\n")
    before, m = snap(p)
    assert run("recolor", p, "k=j", "--region", "1,0,1,1") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_mask_nothing_erased_says_no_change(tmp_path, capsys):
    p = square(tmp_path, 3)
    before, m = snap(p)
    assert run("mask", p, "--keep", "0,0,3,3") == 0
    assert capsys.readouterr().out == f"erased 0 px; no change: {p}\n" and untouched(p, before, m)


def test_mask_that_erases_still_writes(tmp_path, capsys):
    p = square(tmp_path, 3)
    assert run("mask", p, "--keep", "0,0,1,1") == 0
    assert capsys.readouterr().out == f"erased 8 px; wrote {p}\n"


def test_paste_transparent_source_is_no_change(tmp_path, capsys):
    src = write(tmp_path, "s.px", "k #000000\n..\n")
    p = write(tmp_path, "d.px", "k #000000\nkk\n")
    before, m = snap(p)
    assert run("paste", src, "--into", p, "--at", "0,0") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_paste_same_pixels_is_no_change(tmp_path, capsys):
    src = write(tmp_path, "s.px", "k #000000\nk\n")
    p = write(tmp_path, "d.px", "k #000000\nkk\n")
    before, m = snap(p)
    assert run("paste", src, "--into", p, "--at", "1,0") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_compose_identical_replacement_is_no_change(tmp_path, capsys):
    layer = write(tmp_path, "l.px", "k #000000\nk\n")
    out = tmp_path / "h.px"
    assert run("compose", "-o", f"{out}:a/0", f"{layer}@0,0") == 0
    capsys.readouterr()
    before, m = snap(out)
    assert run("compose", "-o", f"{out}:a/0", f"{layer}@0,0") == 0
    assert capsys.readouterr().out == f"no change: {out} frame a/0\n" and untouched(out, before, m)


def test_palette_add_existing_same_color_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    before, m = snap(p)
    assert run("palette", p, "--add", "k=#000000") == 0
    assert capsys.readouterr().out == f"k is already #000000; unchanged; no change: {p}\n" and untouched(p, before, m)


def test_frames_move_to_same_place_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "m.px", THREE)
    before, m = snap(p)
    assert run("frames", p, "--move", "a/1", "--after", "a/0") == 0
    assert capsys.readouterr().out == f"already in place: a/1 after a/0; no change: {p}\n" and untouched(p, before, m)


def test_from_png_same_pixels_again_is_no_change(tmp_path, capsys):
    Image.new("RGBA", (1, 1), (1, 2, 3, 255)).save(tmp_path / "i.png")
    out = tmp_path / "o.px"
    assert run("from-png", tmp_path / "i.png", "-o", out, "--id", "x") == 0
    capsys.readouterr()
    before, m = snap(out)
    assert run("from-png", tmp_path / "i.png", "-o", out, "--id", "x") == 0
    assert capsys.readouterr().out.startswith(f"no change: {out}") and untouched(out, before, m)


def test_no_change_to_other_output_file_that_matches(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk.\n")
    o = write(tmp_path, "o.px", "k #000000\nk.\n")
    before, m = snap(o)
    assert run("set", p, "k", "0,0", "-o", o) == 0
    assert capsys.readouterr().out == f"no change: {o}\n" and untouched(o, before, m)


def test_no_op_to_new_output_file_still_writes_it(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk.\n")
    o = tmp_path / "new.px"
    assert run("set", p, "k", "0,0", "-o", o) == 0
    assert capsys.readouterr().out == f"wrote {o}\n" and o.read_text() == p.read_text()


def test_no_op_to_different_output_file_overwrites_it(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk.\n")
    o = write(tmp_path, "o.px", "k #000000\nkk\n")
    assert run("flip", p, "-o", o) == 0
    assert capsys.readouterr().out == f"wrote {o}\n" and o.read_text() == "k #000000\n.k\n"


def test_no_change_keeps_crlf_file_untouched(tmp_path, capsys):
    p = tmp_path / "a.px"
    p.write_bytes(CRLF.encode())
    before, m = snap(p)
    assert run("set", f"{p}:a", "k", "0,0") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_no_change_with_output_over_a_binary_file_writes(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    o = tmp_path / "o.bin"
    o.write_bytes(b"\xff\xfe\x00binary")
    assert run("set", p, "k", "0,0", "-o", o) == 0
    assert "wrote" in capsys.readouterr().out and o.read_text() == p.read_text()


def test_write_doc_helper(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    doc = pxart.parse(p)
    assert pxart.write_doc(doc) == f"no change: {p}"
    doc.frames[0].grid = ["."]
    assert pxart.write_doc(doc) == f"wrote {p}" and p.read_text() == "k #000000\n.\n"


def test_help_documents_no_change():
    assert '"no change: FILE"' in pxart.__doc__


# ---------------------------------------------------------------- loop E: mask a PNG directly

def solid_png(tmp_path, name="scene.png", size=(8, 8), color=(200, 100, 50, 255)):
    Image.new("RGBA", size, color).save(tmp_path / name)
    return tmp_path / name


def alpha_grid(path):
    img = Image.open(path).convert("RGBA")
    return ["".join("k" if img.getpixel((x, y))[3] else "." for x in range(img.width)) for y in range(img.height)]


def test_mask_png_keep_rect(tmp_path, capsys):
    p = solid_png(tmp_path, size=(4, 4))
    assert run("mask", p, "--keep", "1,1,2,2", "-o", tmp_path / "lit.png") == 0
    assert alpha_grid(tmp_path / "lit.png") == ["....", ".kk.", ".kk.", "...."]
    assert capsys.readouterr().out == f"erased 12 px; wrote {tmp_path / 'lit.png'}\n"
    assert alpha_grid(p) == ["kkkk"] * 4  # input untouched with -o


def test_mask_png_keeps_colors_of_kept_pixels(tmp_path):
    img = Image.new("RGBA", (3, 1))
    img.putpixel((0, 0), (1, 2, 3, 255)); img.putpixel((1, 0), (4, 5, 6, 128)); img.putpixel((2, 0), (7, 8, 9, 255))
    img.save(tmp_path / "s.png")
    assert run("mask", tmp_path / "s.png", "--keep", "0,0,2,1", "-o", tmp_path / "o.png") == 0
    out = Image.open(tmp_path / "o.png").convert("RGBA")
    assert [out.getpixel((x, 0)) for x in range(3)] == [(1, 2, 3, 255), (4, 5, 6, 128), (0, 0, 0, 0)]


def test_mask_png_circle_matches_px_mask(tmp_path):
    """Same shape and same dither as masking the .px: the PNG path is the render -> from-png round trip."""
    for args in (["--keep-circle", "7.5,7.5,6"], ["--keep-circle", "12,12,10", "--dither", "4"],
                 ["--keep-circle", "20,20,18", "--dither", "8"], ["--keep", "3,2,9,11"]):
        n = 40
        pxf = square(tmp_path, n, "sq.px")
        solid_png(tmp_path, "sq.png", (n, n), (0, 0, 0, 255))
        assert run("mask", pxf, *args) == 0
        assert run("mask", tmp_path / "sq.png", *args, "-o", tmp_path / "m.png") == 0
        assert alpha_grid(tmp_path / "m.png") == pxart.parse(pxf).frames[0].grid, args


def test_mask_png_in_place(tmp_path):
    p = solid_png(tmp_path, size=(3, 3))
    assert run("mask", p, "--keep", "0,0,1,1") == 0
    assert alpha_grid(p) == ["k..", "...", "..."]


def test_mask_png_count_ignores_already_transparent(tmp_path, capsys):
    img = Image.new("RGBA", (3, 1)); img.putpixel((0, 0), (1, 1, 1, 255)); img.putpixel((2, 0), (1, 1, 1, 255))
    img.save(tmp_path / "s.png")
    assert run("mask", tmp_path / "s.png", "--keep", "0,0,1,1", "-o", tmp_path / "o.png") == 0
    assert "erased 1 px" in capsys.readouterr().out


def test_mask_png_nothing_erased_in_place_is_no_change(tmp_path, capsys):
    p = solid_png(tmp_path, size=(2, 2))
    before, m = snap(p)
    assert run("mask", p, "--keep", "0,0,2,2") == 0
    assert capsys.readouterr().out == f"erased 0 px; no change: {p}\n" and untouched(p, before, m)


def test_mask_png_nothing_erased_to_new_file_writes(tmp_path):
    p = solid_png(tmp_path, size=(2, 2))
    assert run("mask", p, "--keep", "0,0,2,2", "-o", tmp_path / "o.png") == 0
    assert alpha_grid(tmp_path / "o.png") == ["kk", "kk"]


def test_mask_png_output_dir_created(tmp_path):
    p = solid_png(tmp_path, size=(2, 2))
    assert run("mask", p, "--keep", "0,0,1,1", "-o", tmp_path / "out" / "o.png") == 0
    assert (tmp_path / "out" / "o.png").exists()


def test_mask_png_to_px_output_is_bad_arg(tmp_path, capsys):
    p = solid_png(tmp_path, size=(2, 2))
    assert run("mask", p, "--keep", "0,0,1,1", "-o", tmp_path / "o.px") == 1
    assert not (tmp_path / "o.px").exists()


def test_mask_px_to_png_output_is_bad_arg(tmp_path):
    p = square(tmp_path, 2)
    assert run("mask", p, "--keep", "0,0,1,1", "-o", tmp_path / "o.png") == 1
    assert not (tmp_path / "o.png").exists()


def test_mask_png_with_frame_selector_is_select_error(tmp_path):
    p = solid_png(tmp_path, size=(2, 2))
    assert run("mask", f"{p}:idle", "--keep", "0,0,1,1", "-o", tmp_path / "o.png") == 1


def test_mask_png_bad_args_still_checked(tmp_path):
    p = solid_png(tmp_path, size=(2, 2))
    assert run("mask", p, "--keep", "0,0,1", "-o", tmp_path / "o.png") == 1
    assert run("mask", p, "--keep", "0,0,1,1", "--dither", "2", "-o", tmp_path / "o.png") == 1


def test_mask_png_lights_a_rendered_scene(tmp_path):
    """The loop E flow: render a scene at 1x, cut a dithered light radius out of it, stack it over the dark one."""
    hero = write(tmp_path, "floor.px", "k #806040\n" + ("k" * 16 + "\n") * 16)
    assert run("scene", "-o", tmp_path / "day.png", "--size", "16x16", "--scale", "1", f"{hero}@0,0") == 0
    assert run("mask", tmp_path / "day.png", "--keep-circle", "8,8,6", "--dither", "2",
               "-o", tmp_path / "light.png") == 0
    lit = Image.open(tmp_path / "light.png").convert("RGBA")
    assert lit.getpixel((8, 8)) == (0x80, 0x60, 0x40, 255) and lit.getpixel((0, 0))[3] == 0
    assert run("scene", "-o", tmp_path / "night.png", "--size", "16x16", "--scale", "1", "--bg", "#000000",
               f"{tmp_path / 'light.png'}@0,0") == 0
    night = Image.open(tmp_path / "night.png").convert("RGBA")
    assert night.getpixel((8, 8))[:3] == (0x80, 0x60, 0x40) and night.getpixel((0, 0))[:3] == (0, 0, 0)


def test_help_documents_mask_png():
    assert "FILE may be a PNG" in pxart.__doc__ and "--scale 1" in pxart.__doc__


# ---------------------------------------------------------------- loop E: the map '#' rule, stated and noted

def hash_map(tmp_path, head, rows="ff\n"):
    write(tmp_path, "tiles.px", TILES)
    png(tmp_path, "wall.png", (2, 2), (7, 7, 7, 255))
    return write(tmp_path, "room.map", head + "f tiles.px:floor\n\n" + rows)


@pytest.mark.parametrize("line", ["# tiles.px", "# tiles.px:wall", "# tiles.px:wall%dark", "# wall.png",
                                  "# wall.png%dark", "#   tiles.px:wall", "# sub/dir/t.px:a/b/0",
                                  "# ../up.px", "# t.v2.px:x.y"])
def test_map_hash_legend_forms(tmp_path, line):
    m = hash_map(tmp_path, line + "\n")
    legend, _, notes, _ = pxart.parse_map(m)
    assert "#" in legend and legend["#"] == str(tmp_path / line.split()[1])
    assert len(notes) == 1 and "legend line for '#'" in notes[0]


@pytest.mark.parametrize("line", ["# a room", "# see tiles.px", "# tiles.px is the tileset", "#tiles.px",
                                  "# tiles.pxx", "# tiles.px.bak", "# tiles", "# wall.PNG", "# wall.png:frame",
                                  "# tiles.px: wall", "# (tiles.px)", "# tiles.px:wall extra", "#", "##",
                                  "# tiles.px:bad id", "# tiles.gif"])
def test_map_hash_comment_forms(tmp_path, line):
    m = hash_map(tmp_path, line + "\n")
    legend, layers, notes, _ = pxart.parse_map(m)
    assert "#" not in legend and notes == [] and [[r for _, r in rows] for rows in layers] == [["ff"]]


def test_map_hash_comment_that_names_a_path_is_a_comment(tmp_path):
    m = hash_map(tmp_path, "# walls come from tiles.px:wall\n", "ff\n")
    placed, size = pxart.read_map(m, (2, 2))
    assert size == (4, 2) and len(placed) == 2


def test_map_hash_comment_with_path_then_hash_row_errors(tmp_path):
    m = hash_map(tmp_path, "# see tiles.px:wall\n", "##\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.read_map(m, (2, 2))
    assert codes(e) == ["E_UNKNOWN_KEY"]


def test_read_map_collects_hash_notes(tmp_path):
    m = hash_map(tmp_path, "# tiles.px:wall\n", "#f\n")
    notes = []
    placed, _ = pxart.read_map(m, (2, 2), notes)
    assert len(notes) == 1 and ":1:" in notes[0] and "'# tiles.px:wall'" in notes[0]
    assert "draws tiles.px:wall" in notes[0] and len(placed) == 2


def test_read_map_without_notes_list_still_works(tmp_path):
    m = hash_map(tmp_path, "# tiles.px:wall\n", "#f\n")
    assert len(pxart.read_map(m, (2, 2))[0]) == 2


def test_scene_prints_hash_legend_note(tmp_path, capsys):
    m = hash_map(tmp_path, "# tiles.px:wall\n", "#f\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    out = capsys.readouterr().out
    assert out.startswith("note: ") and "legend line for '#'" in out and "wrote" in out


def test_scene_no_note_without_hash_legend(tmp_path, capsys):
    m = hash_map(tmp_path, "# a room made of tiles.px\n", "ff\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    assert "note:" not in capsys.readouterr().out


def test_check_map_ok_with_note(tmp_path, capsys):
    m = hash_map(tmp_path, "# tiles.px:wall\n", "#f\n##\n")
    assert run("check", m) == 0
    out = capsys.readouterr().out
    assert f"ok   {m}: map 2x2 tiles, 2 legend char(s)" in out
    assert "note:" in out and "legend line for '#'" in out


def test_check_map_ok_without_note(tmp_path, capsys):
    m = hash_map(tmp_path, "# just a comment\n", "ff\n")
    assert run("check", m) == 0
    out = capsys.readouterr().out
    assert "ok" in out and "note:" not in out


def test_check_map_unknown_char_fails(tmp_path, capsys):
    m = hash_map(tmp_path, "# see tiles.px:wall\n", "#f\n")
    assert run("check", m) == 1
    out = capsys.readouterr().out
    assert f"FAIL {m}" in out and "E_UNKNOWN_KEY" in out


def test_check_map_bad_legend_entry_fails(tmp_path, capsys):
    m = hash_map(tmp_path, "q nope.px\nz tiles.px:missing\nw tiles.px\n", "ff\n")
    assert run("check", m) == 1
    out = capsys.readouterr().out
    assert "3 error(s)" in out and "E_FILE" in out and "E_SELECT" in out


def test_check_map_missing_png_legend_fails(tmp_path, capsys):
    m = hash_map(tmp_path, "q gone.png\n", "ff\n")
    assert run("check", m) == 1
    assert "E_FILE" in capsys.readouterr().out


def test_check_map_missing_file_fails(tmp_path, capsys):
    assert run("check", tmp_path / "nope.map") == 1
    assert "FAIL" in capsys.readouterr().out


def test_check_map_alongside_px(tmp_path, capsys):
    m = hash_map(tmp_path, "", "ff\n")
    assert run("check", m, tmp_path / "tiles.px", "-v") == 0
    out = capsys.readouterr().out
    assert "map 2x1 tiles" in out and "tiles.px:floor" in out
    assert run("check", m, tmp_path / "tiles.px") == 0
    out = capsys.readouterr().out
    assert "map 2x1 tiles" in out and f"ok   {tmp_path / 'tiles.px'}: " in out and "tiles.px:floor" not in out


def test_map_hash_rule_existing_behaviour_kept(tmp_path):
    # the loop D forms keep working
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "room.map", "# a room\nf tiles.px:floor\n# tiles.px:wall\n\n###\nf.f\n###\n")
    placed, size = pxart.read_map(m, (2, 2))
    assert size == (6, 6) and len(placed) == 8


def test_help_documents_map_hash_rule():
    doc = pxart.__doc__
    assert "'# FILE.px[:frame][%variant]' or '# FILE.png' (one token after '#', no spaces)" in doc
    assert "check and scene print a note" in doc and "('# see wall.px' too)" in doc
    assert "A .map (scene --map) is checked too" in doc


# ---------------------------------------------------------------- loop E: anim strip, breathing vs bob

BODY = [
    "...kkkk...",
    "..kyyyyk..",
    "..kysysk..",
    "..kssssk..",
    ".kkyyyykk.",
    "kyykyykyyk",
    "kyyyyyyyyk",
    "kyykyykyyk",
    ".kyyyyyyk.",
]
LEGS = ["..kbbbbk..", "..kbkkbk..", "..kbkkbk..", "..kkk.kkk."]
LEGS_WIDE = ["..kbbbbk..", ".kbk..kbk.", "kbk....kbk", "kk......kk"]
EMPTY = "." * 10
PAL = "k #1a1020\ny #f0c040\ns #f0c0a0\nb #3050a0\n"


def anim_file(tmp_path, *frames, name="a.px"):
    text = PAL + "@anim idle ms=200\n" + "".join(f"@frame idle/{i}\n" + "\n".join(g) + "\n" for i, g in enumerate(frames))
    return write(tmp_path, name, text)


BREATHE_0 = [EMPTY] + BODY + LEGS          # chest down
BREATHE_1 = BODY + [BODY[-1]] + LEGS       # chest up 1px, legs where they were
BOB_0 = BODY + LEGS + [EMPTY]
BOB_1 = [EMPTY] + BODY + LEGS              # everything down 1px
WALK_0 = [EMPTY] + BODY + LEGS
WALK_1 = BODY + LEGS_WIDE + [EMPTY]        # body up 1px and the legs change pose


def motion_of(tmp_path, a, b):
    doc = pxart.parse(anim_file(tmp_path, a, b, name="mo.px"))
    return pxart.motion(doc.image(doc.frames[0]), doc.image(doc.frames[1]))[:5]  # [5]: wrapped (loop H)


def pc(n, grid):
    """'24px (27%)': n and n as a percent of grid's opaque pixels, as the strip prints it (loop I)."""
    op = sum(c != "." for r in grid for c in r)
    return f"{n}px ({(200 * n + op) // (2 * op)}%)"


def anim_lines(tmp_path, capsys, *frames):
    p = anim_file(tmp_path, *frames)
    assert run("anim", f"{p}:idle", "-o", tmp_path / "a.gif") == 0
    return [l for l in capsys.readouterr().out.splitlines() if " vs " in l]


def magenta_rows(tmp_path, frame_i, h=14, w=10, S=8):
    """Which sprite rows of the strip's second-row cell for frame_i have magenta (changed) pixels."""
    strip = Image.open(tmp_path / "a.strip.png").convert("RGBA")
    pad, lab = 8, 14
    x0, y0 = pad + frame_i * (w * S + pad), pad * 2 + h * S + lab
    return {r for r in range(h) for c in range(w)
            if strip.getpixel((x0 + c * S + S // 2, y0 + r * S + S // 2))[:3] == (255, 40, 200)}


def test_breathing_idle_whole_shift_is_fewer_pixels(tmp_path):
    # The trap: moving the whole sprite really does leave fewer pixels changed, which is why a
    # "fewest pixels" rule alone would keep lighting up the legs.
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, BREATHE_0, BREATHE_1)
    assert (dx, dy) == (0, -1) and n_shift < n_none


def test_breathing_idle_reports_unshifted(tmp_path):
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, BREATHE_0, BREATHE_1)
    assert still == 9 and n_none > 0


def test_breathing_idle_stdout_shows_both_numbers(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, BREATHE_0, BREATHE_1)
    _, _, n_shift, n_none, _ = motion_of(tmp_path, BREATHE_0, BREATHE_1)
    assert lines[1].endswith(f"vs idle/0: no shift then {pc(n_none, BREATHE_1)} (rows 9+ still; shift +0,-1: {n_shift}px)")
    _, _, n_shift, n_none, still = motion_of(tmp_path, BREATHE_1, BREATHE_0)  # chest back down
    assert lines[0].endswith(f"vs idle/1: no shift then {pc(n_none, BREATHE_0)} (rows {still}+ still; "
                             f"shift +0,+1: {n_shift}px)")
    assert n_shift < n_none


def test_breathing_idle_strip_lights_the_chest_not_the_legs(tmp_path, capsys):
    anim_lines(tmp_path, capsys, BREATHE_0, BREATHE_1)
    for i in (0, 1):
        rows = magenta_rows(tmp_path, i)
        assert rows and max(rows) < 10, rows  # legs (rows 10-13) unlit
        assert rows & {0, 1, 2}               # the lifted head is what changed


def test_bob_reports_shift(tmp_path):
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, BOB_0, BOB_1)
    assert (dx, dy) == (0, 1) and n_shift == 0 and n_none > 0 and still is None


def test_bob_stdout_shows_both_numbers(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, BOB_0, BOB_1)
    n_none = motion_of(tmp_path, BOB_0, BOB_1)[3]
    assert lines[1].endswith(f"vs idle/0: shift +0,+1 then 0px (0%) (no shift: {n_none}px)")
    assert lines[0].endswith(f"vs idle/1: shift +0,-1 then 0px (0%) (no shift: {n_none}px)")


def test_bob_strip_shows_nothing_changed(tmp_path, capsys):
    anim_lines(tmp_path, capsys, BOB_0, BOB_1)
    assert magenta_rows(tmp_path, 1) == set() and magenta_rows(tmp_path, 0) == set()


def test_walk_with_bob_and_new_leg_pose_reports_shift(tmp_path, capsys):
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, WALK_0, WALK_1)
    assert (dx, dy) == (0, -1) and still is None and 0 < n_shift < n_none
    lines = anim_lines(tmp_path, capsys, WALK_0, WALK_1)
    assert f"shift +0,-1 then {pc(n_shift, WALK_1)} (no shift: {n_none}px)" in lines[1]


def test_walk_strip_lights_the_legs_not_the_body(tmp_path, capsys):
    anim_lines(tmp_path, capsys, WALK_0, WALK_1)
    rows = magenta_rows(tmp_path, 1)
    assert rows and min(rows) >= 8, rows  # only the leg rows changed once the bob is removed


def test_no_shift_line_has_no_alternative(tmp_path, capsys):
    same = [EMPTY] + BODY + LEGS
    lines = anim_lines(tmp_path, capsys, same, same)
    assert lines[1].endswith("vs idle/0: shift +0,+0 then 0px (0%)")


def test_motion_zero_shift_is_never_still(tmp_path):
    a = [EMPTY] + BODY + LEGS
    b = [EMPTY] + BODY[:-1] + ["kyyyyyyyyk"] + LEGS
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, a, b)
    assert (dx, dy) == (0, 0) and n_shift == n_none and still is None


def test_head_nod_is_not_a_whole_sprite_shift(tmp_path):
    # Only the head moves: rows below it stay put, so the report is unshifted either way.
    a = [EMPTY] + BODY + LEGS
    b = BODY[:4] + [BODY[3]] + BODY[4:] + LEGS
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, a, b)
    assert (dx, dy) == (0, 0) or still is not None


def test_big_upper_body_lift_is_unshifted(tmp_path):
    # Everything but the feet rises 1px: still reported as the feet staying put.
    a = [EMPTY] + BODY + LEGS
    b = BODY + LEGS[:3] + [LEGS[2], LEGS[3]]
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, a, b)
    # Rows 11+ are identical (LEGS[1] == LEGS[2]): the report names the first identical row.
    assert (dx, dy) == (0, -1) and still == 11


def test_strip_png_is_taller_for_the_second_label_line(tmp_path, capsys):
    anim_lines(tmp_path, capsys, BOB_0, BOB_1)
    strip = Image.open(tmp_path / "a.strip.png")
    assert strip.height == 8 + 2 * (14 * 8 + 8) + 14 + 26


def test_help_documents_breathing_strip():
    doc = pxart.__doc__
    assert '"shift dx,dy then N px (P%) (no shift: M px)"' in doc
    assert '"no shift then M px (P%) (rows Y+ still; shift dx,dy: N px)"' in doc and "Both counts are always shown" in doc


# ---------------------------------------------------------------- loop F: legend paths with spaces, located load errors

def spaced_pack(tmp_path):
    d = tmp_path / "refs" / "png" / "trees and bushes"
    d.mkdir(parents=True)
    Image.new("RGBA", (2, 2), (9, 99, 9, 255)).save(d / "bush.png")
    (tmp_path / "rooms").mkdir()
    return d


@pytest.mark.parametrize("line", ["b ../refs/png/trees and bushes/bush.png",
                                  'b "../refs/png/trees and bushes/bush.png"',
                                  "b    ../refs/png/trees and bushes/bush.png   ",
                                  "b\t../refs/png/trees and bushes/bush.png"])
def test_map_legend_path_with_spaces(tmp_path, line):
    spaced_pack(tmp_path)
    m = write(tmp_path / "rooms", "r.map", f"# a clearing\n{line}\n\nb.\n.b\n")
    legend, layers, notes, where = pxart.parse_map(m)
    assert legend["b"] == str(tmp_path / "rooms" / "../refs/png/trees and bushes/bush.png")
    assert where["b"] == (2, "../refs/png/trees and bushes/bush.png") and [r for _, r in layers[0]] == ["b.", ".b"]
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((0, 0))[:3] == (9, 99, 9) and img.getpixel((3, 3))[:3] == (9, 99, 9)
    assert img.getpixel((2, 0))[:3] == pxart.hex2rgba("#472d3c")[:3]


def test_map_legend_spaced_px_with_frame_and_variant(tmp_path):
    d = tmp_path / "my tiles"
    d.mkdir()
    write(d, "set one.px", VTILES)
    m = write(tmp_path, "r.map", "W my tiles/set one.px:wall%red\nf \"my tiles/set one.px:floor\"\n\nWf\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((0, 0))[:3] == (255, 0, 0) and img.getpixel((2, 0))[:3] == (0, 0, 0)


def test_map_legend_spaced_path_check_ok(tmp_path, capsys):
    spaced_pack(tmp_path)
    m = write(tmp_path / "rooms", "r.map", "b ../refs/png/trees and bushes/bush.png\n\nbb\n")
    assert run("check", m) == 0
    assert "map 2x1 tiles, 1 legend char(s)" in capsys.readouterr().out


def test_map_legend_quoted_path_without_spaces(tmp_path):
    png(tmp_path, "w.png", (2, 2), (1, 1, 1, 255))
    m = write(tmp_path, "r.map", 'w "w.png"\n\nw\n')
    placed, size = pxart.read_map(m, (2, 2))
    assert placed == [(str(tmp_path / "w.png"), 0, 0)] and size == (2, 2)


def test_map_legend_missing_file_errors_at_legend_line(tmp_path, capsys):
    spaced_pack(tmp_path)
    m = write(tmp_path / "rooms", "r.map", "# clearing\ng ../refs/png/trees and bushes/bush.png\n"
              "b ../refs/png/trees and shrubs/bush.png\n\ngb\n")
    err = run_err("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2")
    assert f"{m}:3: E_FILE" in err and "legend 'b'" in err
    assert "'../refs/png/trees and shrubs/bush.png'" in err and "relative to the map file" in err
    assert "has no legend line" not in err and not (tmp_path / "s.png").exists()


def test_map_legend_missing_file_check_names_line(tmp_path, capsys):
    m = write(tmp_path, "r.map", "a gone one.png\nb \"also gone.px:x\"\n\nab\n")
    assert run("check", m) == 1
    out = capsys.readouterr().out
    assert "2 error(s)" in out
    assert f"{m}:1: E_FILE" in out and "'gone one.png'" in out
    assert f"{m}:2: E_FILE" in out and "'also gone.px:x'" in out


def test_map_legend_bad_frame_errors_at_legend_line(tmp_path):
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "r.map", "f tiles.px:floor\nz tiles.px:missing\n\nfz\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.load_legend(m)
    assert codes(e) == ["E_SELECT"] and e.value.issues[0].line == 2
    assert "legend 'z': 'tiles.px:missing'" in str(e.value) and "no frame 'missing'" in str(e.value)


def test_map_legend_multi_frame_errors_at_legend_line(tmp_path):
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "r.map", "\n\nw tiles.px\n\nw\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.load_legend(m)
    assert e.value.issues[0].line == 3 and "is 2 frames" in str(e.value)


def test_map_legend_broken_px_errors_at_legend_line(tmp_path):
    write(tmp_path, "bad.px", "k #000000\nkq\n")
    m = write(tmp_path, "r.map", "b bad.px\n\nb\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.load_legend(m)
    i = e.value.issues[0]
    assert i.code == "E_UNKNOWN_KEY" and i.line == 1 and str(i.path) == str(m)
    assert "legend 'b': 'bad.px'" in i.msg and "bad.px:2" in i.msg


def test_map_unused_broken_legend_entry_still_errors(tmp_path):
    png(tmp_path, "ok.png", (2, 2), (1, 1, 1, 255))
    m = write(tmp_path, "r.map", "a ok.png\nz nope.png\n\naa\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2") == 1


def test_map_legend_quoted_missing_file_names_unquoted_path(tmp_path, capsys):
    m = write(tmp_path, "r.map", 'b "trees and bushes/bush.png"\n\nb\n')
    err = run_err("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2")
    assert "'trees and bushes/bush.png'" in err and '"trees' not in err


def test_map_hash_legend_quoted_path_with_spaces(tmp_path, capsys):
    d = tmp_path / "wall tiles"
    d.mkdir()
    png(d, "wall.png", (2, 2), (7, 7, 7, 255))
    m = write(tmp_path, "r.map", '# a room\n# "wall tiles/wall.png"\n\n##\n')
    legend, _, notes, _ = pxart.parse_map(m)
    assert legend["#"] == str(tmp_path / "wall tiles/wall.png") and len(notes) == 1
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    assert scene_px(tmp_path / "s.png").getpixel((3, 1))[:3] == (7, 7, 7)


@pytest.mark.parametrize("line", ["# wall tiles/wall.png", "# see wall tiles/wall.png", '# "a room"', '# wall.png"'])
def test_map_hash_unquoted_spaces_stay_comments(tmp_path, line):
    m = write(tmp_path, "r.map", f"{line}\nf x.png\n\nf\n")
    legend, _, notes, _ = pxart.parse_map(m)
    assert "#" not in legend and notes == []


def test_map_hash_hint_mentions_quoting(tmp_path):
    m = write(tmp_path, "r.map", "f x.png\n\n#f\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.read_map(m, (2, 2))
    assert "'# \"FILE\"' for a path with spaces" in str(e.value)


def test_map_row_with_spaces_is_bad_row(tmp_path):
    png(tmp_path, "a.png", (2, 2), (1, 1, 1, 255))
    m = write(tmp_path, "r.map", "a a.png\n\naa aa\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.read_map(m, (2, 2))
    assert codes(e) == ["E_BAD_ROW"] and "legend line is one char" in str(e.value)


def test_map_multichar_legend_like_line_is_a_bad_row(tmp_path):
    png(tmp_path, "a.png", (2, 2), (1, 1, 1, 255))
    m = write(tmp_path, "r.map", "a a.png\naa a.png\n\naa\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.read_map(m, (2, 2))
    assert codes(e) == ["E_BAD_ROW"] and e.value.issues[0].line == 2


def test_map_legend_later_line_wins_and_keeps_its_line(tmp_path):
    png(tmp_path, "a.png", (1, 1), (1, 1, 1, 255))
    m = write(tmp_path, "r.map", "a nope.png\na a.png\n\na\n")
    assert pxart.parse_map(m)[3]["a"] == (2, "a.png")
    assert pxart.load_legend(m)


def test_map_legend_old_forms_unchanged(tmp_path):
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "r.map", "# c\nf tiles.px:floor\nW tiles.px:wall\n# tiles.px:wall\n\n#W\nf.\n")
    legend, layers, notes, where = pxart.parse_map(m)
    (rows,) = layers
    assert legend == {"f": str(tmp_path / "tiles.px:floor"), "W": str(tmp_path / "tiles.px:wall"),
                      "#": str(tmp_path / "tiles.px:wall")}
    assert where == {"f": (2, "tiles.px:floor"), "W": (3, "tiles.px:wall"), "#": (4, "tiles.px:wall")}
    assert [r for _, r in rows] == ["#W", "f."]


def test_help_documents_legend_paths():
    doc = pxart.__doc__
    assert "the rest of the line is the path" in doc and "'# \"my tiles/wall.png\"'" in doc
    assert "error at its legend line" in doc


# ---------------------------------------------------------------- loop F: -o with a selector writes the whole file; extract

EDITS = "pxart 1\nk #000000\nj #ffffff\n@anim walk ms=90\n@frame walk/0\nkj.\n...\n@frame walk/1\n.jk\n...\n@frame idle\nkkk\nkkk\n"


@pytest.mark.parametrize("argv", [
    ["flip", "{p}:walk/0"],
    ["flip", "{p}:walk/0", "--v"],
    ["shift", "{p}:walk/0", "--dx", "1"],
    ["set", "{p}:walk/0", "j", "2,1"],
    ["mask", "{p}:walk/0", "--keep", "0,0,1,1"],
    ["recolor", "{p}:walk/0", "k=j"],
    ["paste", "{s}", "--into", "{p}:walk/0", "--at", "2,1"],
])
def test_edit_with_selector_and_output_writes_whole_file(tmp_path, capsys, argv):
    p = write(tmp_path, "h.px", EDITS)
    s = write(tmp_path, "s.px", "k #000000\nk\n")
    before = p.read_text()
    out = tmp_path / "out.px"
    args = [a.format(p=p, s=s) for a in argv]
    assert run(*args, "-o", out) == 0
    assert p.read_text() == before  # the input is untouched
    doc, src = pxart.parse(out), pxart.parse(p)
    assert [f.id for f in doc.frames] == ["walk/0", "walk/1", "idle"]  # every frame, not only the selection
    assert doc.get("walk/0").grid != src.get("walk/0").grid
    assert doc.get("walk/1").grid == src.get("walk/1").grid and doc.get("idle").grid == src.get("idle").grid
    assert doc.anims == src.anims and doc.palette == src.palette
    o = capsys.readouterr().out
    assert f"note: {out} gets all of {p} with walk/0 edited" in o and f"pxart extract {p}:walk/0 -o {out}" in o


@pytest.mark.parametrize("argv", [
    ["flip", "{p}"], ["shift", "{p}", "--dx", "1"], ["set", "{p}:walk/0", "j", "2,1"],
    ["recolor", "{p}", "k=j"], ["mask", "{p}", "--keep", "0,0,1,1"]])
def test_no_selector_note_without_output_or_selector(tmp_path, capsys, argv):
    p = write(tmp_path, "h.px", EDITS)
    assert run(*[a.format(p=p) for a in argv]) == 0
    assert "note:" not in capsys.readouterr().out


def test_selector_with_output_to_same_file_has_no_note(tmp_path, capsys):
    p = write(tmp_path, "h.px", EDITS)
    assert run("flip", f"{p}:walk/0", "-o", p) == 0
    assert "note:" not in capsys.readouterr().out


def test_output_without_selector_has_no_note(tmp_path, capsys):
    p = write(tmp_path, "h.px", EDITS)
    assert run("flip", p, "-o", tmp_path / "o.px") == 0
    assert "note:" not in capsys.readouterr().out
    assert len(pxart.parse(tmp_path / "o.px").frames) == 3


def test_flip_group_selector_output_flips_only_the_group(tmp_path):
    p = write(tmp_path, "h.px", EDITS)
    assert run("flip", f"{p}:walk", "-o", tmp_path / "o.px") == 0
    doc = pxart.parse(tmp_path / "o.px")
    assert doc.get("walk/0").grid == [".jk", "..."] and doc.get("walk/1").grid == ["kj.", "..."]
    assert doc.get("idle").grid == ["kkk", "kkk"]


def test_paste_goes_through_the_edit_path(tmp_path, capsys):
    p = write(tmp_path, "h.px", EDITS)
    s = write(tmp_path, "s.px", "k #000000\nk\n")
    assert run("paste", s, "--into", f"{p}:idle", "--at", "0,0") == 0
    assert "no change" in capsys.readouterr().out
    assert run("paste", s, "--into", p, "--at", "2,1") == 0
    doc = pxart.parse(p)
    assert all(f.grid[1][2] == "k" for f in doc.frames)


def test_extract_writes_only_selected_frames(tmp_path, capsys):
    p = write(tmp_path, "h.px", EDITS)
    out = tmp_path / "walk.px"
    assert run("extract", f"{p}:walk", "-o", out) == 0
    assert capsys.readouterr().out == f"wrote {out} (2 frame(s))\n"
    assert out.read_text() == ("pxart 1\nk #000000\nj #ffffff\n@anim walk ms=90\n@frame walk/0\nkj.\n...\n"
                               "@frame walk/1\n.jk\n...\n")


def test_extract_one_frame_drops_other_anims(tmp_path):
    p = write(tmp_path, "h.px", EDITS)
    assert run("extract", f"{p}:idle", "-o", tmp_path / "i.px") == 0
    doc = pxart.parse(tmp_path / "i.px")
    assert [f.id for f in doc.frames] == ["idle"] and doc.anims == {} and doc.palette == pxart.parse(p).palette


def test_extract_keeps_variants_and_stills(tmp_path):
    text = ("k #000000\n\n@variant night\nk #000011\n\n@still ui\n@still other\n@frame ui/a\nk\n@frame other/b\nk\n")
    p = write(tmp_path, "u.px", text)
    assert run("extract", f"{p}:ui", "-o", tmp_path / "o.px") == 0
    doc = pxart.parse(tmp_path / "o.px")
    assert doc.stills == ["ui"] and doc.variants == {"night": {"k": (0, 0, 0x11, 255)}}
    star = write(tmp_path, "s.px", PARTS)
    assert run("extract", f"{star}:hat", "-o", tmp_path / "hat.px") == 0
    assert pxart.parse(tmp_path / "hat.px").stills == ["*"]


def test_extract_repoints_palette_import(tmp_path):
    write(tmp_path, "pal.px", "k #000000\n")
    (tmp_path / "sprites").mkdir()
    p = write(tmp_path / "sprites", "h.px", "@palette ../pal.px\n@frame a\nk\n@frame b\nkk\n")
    assert run("extract", f"{p}:b", "-o", tmp_path / "out" / "deep" / "b.px") == 0
    doc = pxart.parse(tmp_path / "out" / "deep" / "b.px")
    assert doc.palette_refs == ["../../pal.px"] and doc.get("b").grid == ["kk"]
    assert run("extract", f"{p}:a", "-o", tmp_path / "sprites" / "a.px") == 0
    assert (tmp_path / "sprites" / "a.px").read_text() == "@palette ../pal.px\n@frame a\nk\n"
    assert run("extract", f"{p}:a", "-o", tmp_path / "a.px") == 0
    assert (tmp_path / "a.px").read_text() == "@palette pal.px\n@frame a\nk\n"


def test_extract_keeps_comments_of_kept_frames(tmp_path):
    p = write(tmp_path, "h.px", "k #000000\n\n# first\n@frame a\nk\n\n# second\n@frame b\nk\n")
    assert run("extract", f"{p}:b", "-o", tmp_path / "b.px") == 0
    assert (tmp_path / "b.px").read_text() == "k #000000\n\n# second\n@frame b\nk\n"


def test_extract_whole_file_is_a_byte_copy(tmp_path):
    p = write(tmp_path, "m.px", MESSY)
    assert run("extract", p, "-o", tmp_path / "c.px") == 0
    assert (tmp_path / "c.px").read_text() == MESSY


def test_extract_unknown_selection_is_select_error(tmp_path):
    p = write(tmp_path, "h.px", EDITS)
    assert "E_SELECT" in run_err("extract", f"{p}:nope", "-o", tmp_path / "o.px")
    assert not (tmp_path / "o.px").exists()


def test_extract_needs_output(tmp_path):
    p = write(tmp_path, "h.px", EDITS)
    with pytest.raises(SystemExit):
        pxart.main(["extract", f"{p}:idle"])


def test_extract_then_edit_gives_the_subset_flipped(tmp_path):
    p = write(tmp_path, "h.px", EDITS)
    out = tmp_path / "w0.px"
    assert run("extract", f"{p}:walk/0", "-o", out) == 0
    assert run("flip", out) == 0
    doc = pxart.parse(out)
    assert [f.id for f in doc.frames] == ["walk/0"] and doc.get("walk/0").grid == [".jk", "..."]


def test_help_documents_output_semantics_and_extract():
    doc = pxart.__doc__
    assert "-o OUT always gets the whole file" in doc and "extract FILE:SEL -o OUT" in doc


# ---------------------------------------------------------------- loop F: '@still *' covers top-level frames

TOPLEVEL = "k #000000\n@still *\n@frame icon\nk\n@frame badge\nkk\n@frame hat/big\nkk\n"


def test_still_star_top_level_frames_listed_still(tmp_path, capsys):
    p = write(tmp_path, "p.px", TOPLEVEL)
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "(no group): 2 frame(s) [still]" in out and "hat: 1 frame(s) [still]" in out
    assert "icon  1x1  still" in out and "badge  2x1  still" in out and "ms" not in out


def test_top_level_frames_without_still_star_show_no_ms(tmp_path, capsys):
    # GAMES-295: a top-level frame is never animated; it listed as 100ms.
    p = write(tmp_path, "p.px", TOPLEVEL.replace("@still *\n", ""))
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "  icon  1x1  (line" in out and "[still]" not in out and "icon  1x1  100ms" not in out


def test_named_still_group_does_not_cover_top_level(tmp_path, capsys):
    p = write(tmp_path, "p.px", TOPLEVEL.replace("@still *", "@still hat"))
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "  icon  1x1  (line" in out and "hat/big  2x1  still" in out
    assert "(no group): 2 frame(s)\n" in out


def test_doc_still_rule(tmp_path):
    star = pxart.parse(write(tmp_path, "a.px", TOPLEVEL))
    assert star.still("") and star.still("hat") and star.still("any/thing")
    named = pxart.parse(write(tmp_path, "b.px", TOPLEVEL.replace("@still *", "@still hat")))
    assert not named.still("") and named.still("hat") and not named.still("walk")
    plain = pxart.parse(write(tmp_path, "c.px", TOPLEVEL.replace("@still *\n", "")))
    assert not plain.still("") and not plain.still("hat")


def test_still_star_top_level_excluded_from_exports(tmp_path):
    p = write(tmp_path, "p.px", "k #000000\n@still *\n@frame a\nk\n@frame b\nk\n@frame g/0\nk\n@frame g/1\nk\n")
    assert run("export", p, "--aseprite", tmp_path / "x.json", "--tiled", tmp_path / "x.tsj") == 0
    assert json.loads((tmp_path / "x.json").read_text())["meta"]["frameTags"] == []
    assert json.loads((tmp_path / "x.tsj").read_text())["tiles"] == []


def test_still_star_top_level_mixed_sizes_no_note(tmp_path, capsys):
    p = write(tmp_path, "p.px", TOPLEVEL)
    assert run("check", p) == 0
    assert "mixes frame sizes" not in capsys.readouterr().out


def test_help_documents_still_star_top_level():
    assert "'@still *' marks every frame in the file, top-level" in pxart.__doc__


# ---------------------------------------------------------------- loop F: new, fill

def test_new_blank_file(tmp_path, capsys):
    out = tmp_path / "blank.px"
    assert run("new", out, "--size", "3x2") == 0
    assert out.read_text() == "pxart 1\n\n...\n...\n"
    assert capsys.readouterr().out == f"wrote {out}\n"
    doc = pxart.parse(out)
    assert doc.implicit and doc.frames[0].size == (3, 2)


def test_new_frame_in_new_file(tmp_path):
    out = tmp_path / "h.px"
    assert run("new", f"{out}:idle/0", "--size", "2x2") == 0
    assert out.read_text() == "pxart 1\n\n@frame idle/0\n..\n..\n"


def test_new_filled_with_palette_import(tmp_path):
    write(tmp_path, "pal.px", "g #00ff00\n")
    (tmp_path / "sub").mkdir()
    out = tmp_path / "sub" / "t.px"
    assert run("new", f"{out}:grass", "--size", "2x1", "--key", "g", "--palette", tmp_path / "pal.px") == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == ["../pal.px"] and doc.get("grass").grid == ["gg"] and doc.palette == {}
    assert doc.image(doc.get("grass")).getpixel((1, 0)) == (0, 255, 0, 255)


def test_new_frame_in_existing_file_lands_after_its_animation(tmp_path, capsys):
    p = write(tmp_path, "h.px", GROUPS)
    assert run("new", f"{p}:walk/2", "--size", "1x1", "--key", "k") == 0
    assert ids(p) == ["idle/0", "walk/0", "walk/1", "walk/2", "shoot/0"]
    assert pxart.parse(p).get("walk/2").grid == ["k"]
    assert capsys.readouterr().out == f"wrote {p} frame walk/2\n"


def test_new_frame_follows_file_spacing(tmp_path):
    p = write(tmp_path, "a.px", TIGHT_FRAMES)
    assert run("new", f"{p}:extra", "--size", "2x1") == 0
    assert p.read_text() == TIGHT_FRAMES + "@frame extra\n..\n"
    p = write(tmp_path, "b.px", BLANK_FRAMES)
    assert run("new", f"{p}:walk/2", "--size", "4x1", "--key", "g") == 0
    assert p.read_text() == BLANK_FRAMES.replace("\n@frame idle", "\n@frame walk/2\ngggg\n\n@frame idle")


def test_new_existing_frame_is_dup_error(tmp_path):
    p = write(tmp_path, "h.px", GROUPS)
    before = p.read_text()
    msg = run_err("new", f"{p}:walk/0", "--size", "1x1")
    assert "E_DUP_FRAME" in msg and "pxart fill" in msg and p.read_text() == before


def test_new_over_existing_single_grid_is_dup_error(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    assert "E_DUP_FRAME" in run_err("new", p, "--size", "1x1")
    assert p.read_text() == "k #000000\nk\n"


def test_new_into_palette_only_file(tmp_path):
    p = write(tmp_path, "pal.px", "k #000000\n")
    assert run("new", p, "--size", "2x1", "--key", "k") == 0
    assert p.read_text() == "k #000000\n\nkk\n"
    q = write(tmp_path, "pal2.px", "k #000000\n")
    assert run("new", f"{q}:a", "--size", "1x1", "--key", "k") == 0
    assert pxart.parse(q).get("a").grid == ["k"]


def test_new_without_frame_into_named_file_asks_for_one(tmp_path):
    p = write(tmp_path, "h.px", GROUPS)
    msg = run_err("new", p, "--size", "1x1")
    assert "E_SELECT" in msg and "new " in msg and ":<frame-id>" in msg


def test_new_frame_into_single_grid_file_names_the_grid_first(tmp_path):
    # Was E_MIXED_FRAMES; now the unnamed grid becomes '@frame a' (loop J) and x is added after it.
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    assert run("new", f"{p}:x", "--size", "1x1") == 0
    assert p.read_text() == "k #000000\n\n@frame a\nk\n\n@frame x\n.\n"


def test_new_unknown_key(tmp_path):
    assert "E_SELECT" in run_err("new", tmp_path / "a.px", "--size", "1x1", "--key", "k")
    assert not (tmp_path / "a.px").exists()


@pytest.mark.parametrize("size", ["0x4", "4x0", "4", "4x", "ax4", "4*4", "-1x2", ""])
def test_new_bad_size(tmp_path, size):
    assert "E_BAD_ARG" in run_err("new", tmp_path / "a.px", f"--size={size}")


def test_new_palette_on_existing_file_is_bad_arg(tmp_path):
    write(tmp_path, "pal.px", "k #000000\n")
    p = write(tmp_path, "h.px", GROUPS)
    assert "E_BAD_ARG" in run_err("new", f"{p}:x", "--size", "1x1", "--palette", tmp_path / "pal.px")


def test_new_missing_palette_file(tmp_path):
    assert "E_PALETTE_FILE" in run_err("new", tmp_path / "a.px", "--size", "1x1", "--palette", tmp_path / "no.px")


@pytest.mark.parametrize("sub", ["new", "a/b", "a/b/c"])
def test_new_palette_creates_missing_output_directories(tmp_path, sub, capsys):
    # GAMES-295: the output's directory didn't exist yet, and the @palette line was read from there: a misleading
    # E_PALETTE_FILE for a right path.
    write(tmp_path, "hero_pal.px", "k #102030\n@variant night\nk #000000\n")
    out = tmp_path / sub / "hero.px"
    assert run("new", out, "--size", "2x1", "--key", "k", "--palette", tmp_path / "hero_pal.px") == 0
    depth = len(pathlib.Path(sub).parts)
    ref = "../" * depth + "hero_pal.px"
    assert out.read_text() == f"pxart 1\n@palette {ref}\n\nkk\n"
    doc = pxart.parse(out)
    assert doc.image(doc.frames[0]).getpixel((0, 0)) == (0x10, 0x20, 0x30, 255)
    assert doc.image(doc.frames[0], "night").getpixel((1, 0)) == (0, 0, 0, 255)
    assert capsys.readouterr().out == f"wrote {out}\n"


def test_new_palette_frame_in_missing_directory(tmp_path):
    write(tmp_path, "pal.px", "g #00ff00\n")
    out = tmp_path / "x" / "y" / "t.px"
    assert run("new", f"{out}:walk/0", "--size", "1x2", "--key", "g", "--palette", tmp_path / "pal.px") == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == ["../../pal.px"] and doc.get("walk/0").grid == ["g", "g"]


def test_new_palette_relative_paths_from_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "pal.px", "g #00ff00\n")
    assert run("new", "art/sprites/t.px", "--size", "1x1", "--key", "g", "--palette", "pal.px") == 0
    assert pxart.parse(tmp_path / "art" / "sprites" / "t.px").palette_refs == ["../../pal.px"]
    (tmp_path / "pals").mkdir()
    write(tmp_path / "pals", "p2.px", "g #00ff00\n")
    assert run("new", "art/u.px", "--size", "1x1", "--key", "g", "--palette", "pals/p2.px") == 0
    assert pxart.parse(tmp_path / "art" / "u.px").palette_refs == ["../pals/p2.px"]


def test_new_missing_palette_names_the_palette_and_creates_nothing(tmp_path):
    msg = run_err("new", tmp_path / "d" / "e" / "a.px", "--size", "1x1", "--palette", tmp_path / "no.px")
    assert msg.startswith(f"new: --palette ({tmp_path / 'no.px'}): E_PALETTE_FILE: can't find palette file")
    assert not (tmp_path / "d").exists()


def test_new_palette_with_grid_rows_is_palette_file_error(tmp_path):
    write(tmp_path, "notpal.px", "k #000000\nk\n")
    msg = run_err("new", tmp_path / "n" / "a.px", "--size", "1x1", "--palette", tmp_path / "notpal.px")
    assert "E_PALETTE_FILE" in msg and "--palette" in msg
    assert not (tmp_path / "n").exists()


def test_from_png_palette_creates_missing_output_directories(tmp_path):
    write(tmp_path, "pal.px", "o #010101\n")
    Image.new("RGBA", (2, 1), (1, 1, 1, 255)).save(tmp_path / "i.png")
    out = tmp_path / "p" / "q" / "o.px"
    assert run("from-png", tmp_path / "i.png", "-o", out, "--palette", tmp_path / "pal.px") == 0
    assert out.read_text() == "pxart 1\n@palette ../../pal.px\n\noo\n"
    out2 = tmp_path / "r" / "o.px"
    assert run("from-png", tmp_path / "i.png", "-o", out2, "--id", "x", "--palette", tmp_path / "pal.px") == 0
    doc = pxart.parse(out2)
    assert doc.palette_refs == ["../pal.px"] and doc.get("x/i").grid == ["oo"] and doc.palette == {}


PAL_HERO = "pxart 1\n@palette pal.px\n@anim w ms=90\n\n@frame w/0\nkg\n@frame w/1\ngk\n"


@pytest.mark.parametrize("argv", [
    ["compose", "-o", "{o}/c.px", "{h}:w/0@0,0"],
    ["compose", "-o", "{o}/c.px:x/0", "{h}:w/0@0,0"],
    ["crop", "{h}:w/0", "0,0,1,1", "-o", "{o}/c.px"],
    ["dup", "{h}:w/0", "w/2", "-o", "{o}/c.px"],
    ["flip", "{h}", "-o", "{o}/c.px"],
    ["rotate", "{h}", "90", "-o", "{o}/c.px"],
    ["transpose", "{h}", "-o", "{o}/c.px"],
    ["shift", "{h}", "--dx", "1", "-o", "{o}/c.px"],
    ["extract", "{h}:w", "-o", "{o}/c.px"],
    ["anim-set", "{h}:w", "ms=50", "-o", "{o}/c.px"],
    ["recolor", "{h}", "k=g", "-o", "{o}/c.px"],
    ["set", "{h}:w/0", "g", "0,0", "-o", "{o}/c.px"],
    ["fill", "{h}", "g", "-o", "{o}/c.px"],
    ["mask", "{h}", "--keep", "0,0,1,1", "-o", "{o}/c.px"],
    ["line", "{h}", "g", "0,0", "1,0", "-o", "{o}/c.px"],
    ["outline", "{h}", "--key", "g", "--inside", "-o", "{o}/c.px"],
    ["paste", "{h}:w/0", "--into", "{h}:w/1", "--at", "1,0", "-o", "{o}/c.px"],
    ["shade", "{h}:w/0", "--ramp", "kg", "--keys", "kg", "-o", "{o}/c.px"],
])
def test_every_px_writer_creates_missing_directories_and_repoints(tmp_path, argv):
    # GAMES-295 audit: every -o/OUT .px writer into a directory that doesn't exist yet, from a file importing a
    # palette: the directories are made and @palette is re-pointed from there, so the output renders.
    write(tmp_path, "pal.px", "k #000000\ng #00ff00\n")
    h = write(tmp_path, "h.px", PAL_HERO)
    o = tmp_path / "out" / "deep"
    assert run(*[x.format(h=h, o=o) for x in argv]) == 0
    doc = pxart.parse(o / "c.px")
    assert doc.palette_refs == ["../../pal.px"]
    assert all(doc.image(f) for f in doc.frames)


def test_put_into_new_file_in_missing_directory(tmp_path, monkeypatch):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO("k #000000\nk.\n"))
    out = tmp_path / "a" / "b" / "p.px"
    assert run("put", f"{out}:x/0") == 0
    assert pxart.parse(out).get("x/0").grid == ["k."]


@pytest.mark.parametrize("argv, made", [
    (["anim", "{h}", "-o", "{o}/a.gif"], ["a.gif", "a.strip.png"]),
    (["onion", "{h}:w/0", "{h}:w/1", "-o", "{o}/o.png"], ["o.png"]),
    (["sheet", "{h}", "-o", "{o}/s.png"], ["s.png"]),
    (["render", "{h}", "-o", "{o}/r.png"], ["r.png"]),
    (["scene", "{h}:w/0@0,0", "-o", "{o}/s.png"], ["s.png"]),
    (["export", "{h}", "--aseprite", "{o}/s.json"], ["s.json", "s.png"]),
    (["export", "{h}", "--tiled", "{o}/t.tsj"], ["t.tsj", "t.png"]),
    (["export", "{h}", "--frames", "{o}"], ["w/0.png", "w/1.png"]),
    (["palette", "{h}", "--export", "{o}/p.gpl"], ["p.gpl"]),
    (["shade", "{h}:w/0", "--ramp", "kg", "--preview", "{o}/p.png"], ["p.png"]),
])
def test_every_image_writer_creates_missing_directories(tmp_path, argv, made):
    write(tmp_path, "pal.px", "k #000000\ng #00ff00\n")
    h = write(tmp_path, "h.px", PAL_HERO)
    o = tmp_path / "out" / "deep"
    assert run(*[x.format(h=h, o=o) for x in argv]) == 0
    for m in made:
        assert (o / m).exists(), m


def test_png_writers_create_missing_directories(tmp_path):
    Image.new("RGBA", (2, 2), (9, 9, 9, 255)).save(tmp_path / "s.png")
    assert run("tint", tmp_path / "s.png", "#00000080", "-o", tmp_path / "t" / "u" / "t.png") == 0
    assert run("mask", tmp_path / "s.png", "--keep", "0,0,1,1", "-o", tmp_path / "m" / "n" / "m.png") == 0
    assert (tmp_path / "t" / "u" / "t.png").exists() and (tmp_path / "m" / "n" / "m.png").exists()


def test_wrote_lines_have_no_trailing_space(tmp_path, capsys):
    # GAMES-295: 'wrote X ' (a trailing space where an empty frame suffix was printed).
    write(tmp_path, "pal.px", "k #000000\n")
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    Image.new("RGBA", (1, 1), (1, 1, 1, 255)).save(tmp_path / "i.png")
    runs = [
        ("new", tmp_path / "n.px", "--size", "1x1"),
        ("new", f"{tmp_path / 'n2.px'}:x", "--size", "1x1"),
        ("new", tmp_path / "n3.px", "--size", "1x1", "--palette", tmp_path / "pal.px"),
        ("compose", "-o", tmp_path / "c.px", f"{p}@0,0"),
        ("compose", "-o", f"{tmp_path / 'c2.px'}:x", f"{p}@0,0"),
        ("crop", p, "0,0,1,1", "-o", tmp_path / "cr.px"),
        ("crop", p, "0,0,1,1", "-o", f"{tmp_path / 'cr2.px'}:y"),
        ("from-png", tmp_path / "i.png", "-o", tmp_path / "f.px"),
        ("from-png", tmp_path / "i.png", "-o", tmp_path / "f2.px", "--id", "z"),
        ("flip", p), ("set", p, "k", "0,0"), ("fill", p, "k"),
    ]
    for argv in runs:
        assert run(*argv) == 0, argv
        out = capsys.readouterr().out
        assert out and out.endswith("\n"), argv
        for line in out.splitlines():
            assert line == line.rstrip(), (argv, line)


@pytest.mark.parametrize("argv, want", [
    (("new", "{d}/a.px", "--size", "1x1"), "wrote {d}/a.px\n"),
    (("new", "{d}/a.px:x/0", "--size", "1x1"), "wrote {d}/a.px frame x/0\n"),
    (("compose", "-o", "{d}/c.px", "{d}/src.px@0,0"), "wrote {d}/c.px\n"),
    (("compose", "-o", "{d}/c.px:q", "{d}/src.px@0,0"), "wrote {d}/c.px frame q\n"),
    (("crop", "{d}/src.px", "0,0,1,1", "-o", "{d}/c.px"), "wrote {d}/c.px\n"),
    (("from-png", "{d}/i.png", "-o", "{d}/f.px"), "wrote {d}/f.px\n"),
    (("from-png", "{d}/i.png", "-o", "{d}/f.px", "--id", "z"), "wrote {d}/f.px (1 frame(s))\n"),
])
def test_wrote_line_exact(tmp_path, capsys, argv, want):
    write(tmp_path, "src.px", "k #000000\nk\n")
    Image.new("RGBA", (1, 1), (1, 1, 1, 255)).save(tmp_path / "i.png")
    assert run(*[x.format(d=tmp_path) for x in argv]) == 0
    assert capsys.readouterr().out == want.format(d=tmp_path)


def test_new_bad_frame_id(tmp_path):
    assert "E_BAD_ID" in run_err("new", f"{tmp_path / 'a.px'}:bad id", "--size", "1x1")


def test_new_notes_mangled_output(tmp_path, capsys):
    assert run("new", tmp_path / "heroalk", "--size", "1x1") == 0
    assert "doesn't end in .px" in capsys.readouterr().out


def test_new_then_draw_round_trip(tmp_path):
    p = tmp_path / "s.px"
    assert run("new", f"{p}:a", "--size", "3x3") == 0
    assert run("palette", p, "--add", "k=#000000") == 0
    assert run("set", f"{p}:a", "k", "1,1") == 0
    assert pxart.parse(p).get("a").grid == ["...", ".k.", "..."]


def test_fill_whole_frame(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nj #ffffff\n@frame a\nkj\njk\n@frame b\nkk\n")
    assert run("fill", f"{p}:a", "j") == 0
    doc = pxart.parse(p)
    assert doc.get("a").grid == ["jj", "jj"] and doc.get("b").grid == ["kk"]


def test_fill_region(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\n" + "....\n" * 3)
    assert run("fill", p, "k", "--region", "1,1,2,2") == 0
    assert pxart.parse(p).frames[0].grid == ["....", ".kk.", ".kk."]


def test_fill_region_partly_outside_is_clipped(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\n...\n...\n")
    assert run("fill", p, "k", "--region=-1,1,3,5") == 0
    assert pxart.parse(p).frames[0].grid == ["...", "kk."]


def test_fill_erase_with_dot(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nkkk\n")
    assert run("fill", p, ".", "--region", "0,0,2,1") == 0
    assert pxart.parse(p).frames[0].grid == ["..k"]


def test_fill_every_selected_frame(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\n@frame w/0\n..\n@frame w/1\n...\n@frame x\n.\n")
    assert run("fill", f"{p}:w", "k") == 0
    doc = pxart.parse(p)
    assert doc.get("w/0").grid == ["kk"] and doc.get("w/1").grid == ["kkk"] and doc.get("x").grid == ["."]


def test_fill_unknown_key(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\n..\n")
    assert "E_SELECT" in run_err("fill", p, "q")


def test_fill_bad_region(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\n..\n")
    assert "E_BAD_ARG" in run_err("fill", p, "k", "--region", "1,2")


def test_fill_same_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nkk\n")
    before, m = snap(p)
    assert run("fill", p, "k") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_fill_output_is_whole_file(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\n@frame a\n.\n@frame b\n.\n")
    assert run("fill", f"{p}:a", "k", "-o", tmp_path / "o.px") == 0
    doc = pxart.parse(tmp_path / "o.px")
    assert doc.get("a").grid == ["k"] and doc.get("b").grid == ["."]
    assert "gets all of" in capsys.readouterr().out


def test_fill_keeps_layout(tmp_path):
    p = write(tmp_path, "a.px", MESSY)
    assert run("fill", f"{p}:walk/1", "Z") == 0
    assert p.read_text() == MESSY.replace(".kk.\n.kk.\n.kk.\n", "ZZZZ\nZZZZ\nZZZZ\n")


def test_compose_single_grid_replacement_unchanged(tmp_path):
    # compose OUT (no :frame) over an existing single grid still sizes from the first layer
    out = write(tmp_path, "o.px", "k #000000\nkkkk\n")
    layer = write(tmp_path, "l.px", "k #000000\nk\n")
    assert run("compose", "-o", out, f"{layer}@0,0") == 0
    assert pxart.parse(out).frames[0].grid == ["k"]


def test_help_documents_new_and_fill():
    doc = pxart.__doc__
    assert "new OUT[:frame] --size WxH [--key K] [--palette P.px]" in doc
    assert "fill FILE[:frame] KEY [--region x,y,w,h]" in doc


# ---------------------------------------------------------------- loop F: scene --tint, tint on a PNG

def near(a, b, tol=1):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def blend(c, t):
    a = t[3] / 255
    return tuple(round(x * (1 - a) + y * a) for x, y in zip(c[:3], t[:3]))


def test_scene_tint_darkens_everything(tmp_path):
    hero = write(tmp_path, "h.px", "h #c86432\nh\n")
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "r.map", "W tiles.px:wall\n\nW.\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1", "--bg", "#406080",
               "--tint", "#10183080", f"{hero}@1,1") == 0
    img = scene_px(tmp_path / "s.png")
    t = pxart.hex2rgba("#10183080")
    assert near(img.getpixel((0, 0))[:3], blend((255, 255, 255), t))  # map tile
    assert near(img.getpixel((1, 1))[:3], blend((0xc8, 0x64, 0x32), t))  # item
    assert near(img.getpixel((3, 0))[:3], blend((0x40, 0x60, 0x80), t))  # background
    assert all(img.getpixel((x, y))[3] == 255 for x in range(4) for y in range(2))


def test_scene_tint_applies_to_items_with_own_variant(tmp_path):
    hero = write(tmp_path, "hero.px", VHERO)
    assert run("scene", "-o", tmp_path / "s.png", "--size", "1x1", "--scale", "1", "--tint", "#000000ff",
               f"{hero}%red@0,0") == 0
    assert scene_px(tmp_path / "s.png").getpixel((0, 0))[:3] == (0, 0, 0)


def test_scene_tint_before_scale(tmp_path):
    hero = write(tmp_path, "h.px", "h #ffffff\nh\n")
    assert run("scene", "-o", tmp_path / "s.png", "--size", "1x1", "--scale", "3", "--tint", "#00000080",
               f"{hero}@0,0") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.size == (3, 3) and len(set(pxart.pixels(img))) == 1


def test_scene_tint_opaque_and_zero(tmp_path):
    hero = write(tmp_path, "h.px", "h #c86432\nh\n")
    assert run("scene", "-o", tmp_path / "a.png", "--size", "1x1", "--scale", "1", "--tint", "#ff0000",
               f"{hero}@0,0") == 0
    assert scene_px(tmp_path / "a.png").getpixel((0, 0)) == (255, 0, 0, 255)
    assert run("scene", "-o", tmp_path / "b.png", "--size", "1x1", "--scale", "1", "--tint", "#ff000000",
               f"{hero}@0,0") == 0
    assert scene_px(tmp_path / "b.png").getpixel((0, 0)) == (0xc8, 0x64, 0x32, 255)


def test_scene_tint_without_hash(tmp_path):
    hero = write(tmp_path, "h.px", "h #ffffff\nh\n")
    assert run("scene", "-o", tmp_path / "a.png", "--size", "1x1", "--scale", "1", "--tint", "000000ff",
               f"{hero}@0,0") == 0
    assert scene_px(tmp_path / "a.png").getpixel((0, 0))[:3] == (0, 0, 0)


@pytest.mark.parametrize("bad", ["#12345", "#1234567", "black", "#gggggggg", "#"])
def test_scene_tint_bad_color(tmp_path, bad):
    hero = write(tmp_path, "h.px", "h #ffffff\nh\n")
    msg = run_err("scene", "-o", tmp_path / "a.png", f"--tint={bad}", f"{hero}@0,0")
    assert "E_BAD_COLOR" in msg and "quote it" in msg and not (tmp_path / "a.png").exists()


def test_scene_without_tint_unchanged(tmp_path):
    hero = write(tmp_path, "h.px", "h #c86432\nh\n")
    assert run("scene", "-o", tmp_path / "a.png", "--size", "2x1", "--scale", "1", f"{hero}@0,0") == 0
    img = scene_px(tmp_path / "a.png")
    assert img.getpixel((0, 0)) == (0xc8, 0x64, 0x32, 255) and img.getpixel((1, 0))[:3] == (0x47, 0x2d, 0x3c)


def test_scene_tint_keeps_transparent_bg_transparent(tmp_path):
    hero = write(tmp_path, "h.px", "h #ffffff\nh\n")
    assert run("scene", "-o", tmp_path / "a.png", "--size", "2x1", "--scale", "1", "--bg", "#00000000",
               "--tint", "#00000080", f"{hero}@0,0") == 0
    img = scene_px(tmp_path / "a.png")
    assert img.getpixel((1, 0)) == (0, 0, 0, 0) and img.getpixel((0, 0))[3] == 255


def test_tint_png(tmp_path, capsys):
    p = solid_png(tmp_path, size=(2, 2), color=(200, 100, 50, 255))
    assert run("tint", p, "#00000080", "-o", tmp_path / "o.png") == 0
    assert capsys.readouterr().out == f"wrote {tmp_path / 'o.png'}\n"
    out = scene_px(tmp_path / "o.png")
    assert near(out.getpixel((1, 1))[:3], blend((200, 100, 50), pxart.hex2rgba("#00000080")))
    assert scene_px(p).getpixel((0, 0)) == (200, 100, 50, 255)  # input untouched


def test_tint_png_in_place(tmp_path):
    p = solid_png(tmp_path, size=(1, 1), color=(200, 100, 50, 255))
    assert run("tint", p, "#000000ff") == 0
    assert scene_px(p).getpixel((0, 0)) == (0, 0, 0, 255)


def test_tint_png_keeps_alpha(tmp_path):
    img = Image.new("RGBA", (3, 1))
    img.putpixel((0, 0), (200, 200, 200, 255)); img.putpixel((1, 0), (200, 200, 200, 100))
    img.save(tmp_path / "s.png")
    assert run("tint", tmp_path / "s.png", "#ff0000ff", "-o", tmp_path / "o.png") == 0
    out = scene_px(tmp_path / "o.png")
    assert out.getpixel((0, 0)) == (255, 0, 0, 255) and out.getpixel((1, 0)) == (255, 0, 0, 100)
    assert out.getpixel((2, 0)) == (0, 0, 0, 0)


def test_tint_png_matches_scene_tint(tmp_path):
    hero = write(tmp_path, "h.px", "h #c86432\ng #203040\nhg\ngh\n")
    base = ["scene", "--size", "3x3", "--scale", "1", f"{hero}@1,0"]
    assert run(*base, "-o", tmp_path / "day.png") == 0
    assert run(*base, "-o", tmp_path / "night.png", "--tint", "#10183099") == 0
    assert run("tint", tmp_path / "day.png", "#10183099", "-o", tmp_path / "t.png") == 0
    assert pxart.pixels(scene_px(tmp_path / "t.png")) == pxart.pixels(scene_px(tmp_path / "night.png"))


def test_tint_needs_pngs(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    assert "E_BAD_ARG" in run_err("tint", p, "#00000080")
    q = solid_png(tmp_path)
    assert "E_BAD_ARG" in run_err("tint", q, "#00000080", "-o", tmp_path / "o.px")


def test_tint_bad_color(tmp_path):
    q = solid_png(tmp_path)
    assert "E_BAD_COLOR" in run_err("tint", q, "#00000")


def test_tint_missing_png_is_file_error(tmp_path):
    assert "E_FILE" in run_err("tint", tmp_path / "nope.png", "#00000080")


def test_tint_night_with_a_lit_circle(tmp_path):
    """The loop F flow without a hand-made shade.px: tint, then the lit circle of the day render on top."""
    floor = write(tmp_path, "f.px", "k #806040\n" + ("k" * 16 + "\n") * 16)
    assert run("scene", "-o", tmp_path / "day.png", "--size", "16x16", "--scale", "1", f"{floor}@0,0") == 0
    assert run("scene", "-o", tmp_path / "dark.png", "--size", "16x16", "--scale", "1", "--tint", "#000000c0",
               f"{floor}@0,0") == 0
    assert run("mask", tmp_path / "day.png", "--keep-circle", "8,8,4", "-o", tmp_path / "lit.png") == 0
    assert run("scene", "-o", tmp_path / "night.png", "--size", "16x16", "--scale", "1",
               f"{tmp_path / 'dark.png'}@0,0", f"{tmp_path / 'lit.png'}@0,0") == 0
    img = scene_px(tmp_path / "night.png")
    assert img.getpixel((8, 8))[:3] == (0x80, 0x60, 0x40) and img.getpixel((0, 0))[0] < 0x30


def test_help_documents_tint():
    doc = pxart.__doc__
    assert "--tint '#10183080'" in doc and "those with their own %variant too" in doc
    assert "tint IN.png '#rrggbbaa' [-o OUT.png]" in doc and "Quote the color in scripts" in doc


# ---------------------------------------------------------------- loop F: mask --invert

def test_mask_invert_rect(tmp_path, capsys):
    p = square(tmp_path, 4)
    assert run("mask", p, "--keep", "1,1,2,2", "--invert") == 0
    assert pxart.parse(p).frames[0].grid == ["kkkk", "k..k", "k..k", "kkkk"]
    assert "erased 4 px" in capsys.readouterr().out


def test_mask_invert_circle_hard_edge(tmp_path):
    p = square(tmp_path, 7)
    assert run("mask", p, "--keep-circle", "3,3,2", "--invert") == 0
    assert pxart.parse(p).frames[0].grid == [
        "kkkkkkk",
        "kkk.kkk",
        "kk...kk",
        "k.....k",
        "kk...kk",
        "kkk.kkk",
        "kkkkkkk",
    ]


@pytest.mark.parametrize("args", [["--keep-circle", "7.5,7.5,6"], ["--keep-circle", "12,12,10", "--dither", "4"],
                                  ["--keep-circle", "20,20,18", "--dither", "8"], ["--keep", "3,2,9,11"],
                                  ["--keep=-3,-3,50,50"], ["--keep-circle", "0,0,5", "--dither", "5"]])
def test_mask_invert_is_the_exact_complement_px(tmp_path, args):
    a, b = square(tmp_path, 40, "a.px"), square(tmp_path, 40, "b.px")
    assert run("mask", a, *args) == 0
    assert run("mask", b, *args, "--invert") == 0
    ga, gb = pxart.parse(a).frames[0].grid, pxart.parse(b).frames[0].grid
    for y in range(40):
        for x in range(40):
            assert (ga[y][x] == "k") != (gb[y][x] == "k"), (x, y)


def test_mask_invert_dither_falls_off_inward(tmp_path):
    p = square(tmp_path, 40)
    assert run("mask", p, "--keep-circle", "20,20,18", "--dither", "8", "--invert") == 0
    g = pxart.parse(p).frames[0].grid

    def density(lo, hi):
        ring = [(x, y) for y in range(40) for x in range(40) if lo < ((x - 20) ** 2 + (y - 20) ** 2) ** 0.5 <= hi]
        return sum(g[y][x] == "k" for x, y in ring) / len(ring)
    assert density(0, 10) == 0 and density(18, 30) == 1
    assert density(10, 12) < density(12, 14) < density(14, 16) < density(16, 18)


@pytest.mark.parametrize("args", [["--keep-circle", "12,12,10", "--dither", "4"], ["--keep", "3,2,9,11"]])
def test_mask_invert_png_complements_and_matches_px(tmp_path, args):
    n = 24
    solid_png(tmp_path, "s.png", (n, n), (0, 0, 0, 255))
    pxf = square(tmp_path, n, "sq.px")
    assert run("mask", tmp_path / "s.png", *args, "--invert", "-o", tmp_path / "inv.png") == 0
    assert run("mask", tmp_path / "s.png", *args, "-o", tmp_path / "keep.png") == 0
    assert run("mask", pxf, *args, "--invert") == 0
    inv, keep = alpha_grid(tmp_path / "inv.png"), alpha_grid(tmp_path / "keep.png")
    assert inv == pxart.parse(pxf).frames[0].grid
    assert all((inv[y][x] == "k") != (keep[y][x] == "k") for y in range(n) for x in range(n))


def test_mask_invert_png_restacks_to_the_original(tmp_path):
    img = Image.new("RGBA", (10, 10))
    for y in range(10):
        for x in range(10):
            img.putpixel((x, y), (x * 20, y * 20, 99, 255))
    img.save(tmp_path / "s.png")
    for flag in ([], ["--invert"]):
        assert run("mask", tmp_path / "s.png", "--keep-circle", "5,5,4", "--dither", "2", *flag,
                   "-o", tmp_path / f"m{len(flag)}.png") == 0
    assert run("scene", "-o", tmp_path / "re.png", "--size", "10x10", "--scale", "1", "--bg", "#00000000",
               f"{tmp_path / 'm0.png'}@0,0", f"{tmp_path / 'm1.png'}@0,0") == 0
    assert pxart.pixels(scene_px(tmp_path / "re.png")) == pxart.pixels(img)


def test_mask_invert_nothing_inside_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk...\n....\n")
    before, m = snap(p)
    assert run("mask", p, "--keep", "2,0,2,2", "--invert") == 0
    assert capsys.readouterr().out == f"erased 0 px; no change: {p}\n" and untouched(p, before, m)


def test_mask_invert_one_frame_leaves_others(tmp_path):
    p = write(tmp_path, "m.px", "k #000000\n@frame a\nkk\nkk\n@frame b\nkk\nkk\n")
    assert run("mask", f"{p}:a", "--keep", "0,0,1,1", "--invert") == 0
    doc = pxart.parse(p)
    assert doc.get("a").grid == [".k", "kk"] and doc.get("b").grid == ["kk", "kk"]


def test_mask_invert_still_checks_args(tmp_path):
    p = square(tmp_path, 3)
    assert run("mask", p, "--keep", "0,0,1,1", "--dither", "2", "--invert") == 1
    with pytest.raises(SystemExit):
        pxart.main(["mask", str(p), "--invert"])


def test_help_documents_mask_invert():
    assert "--invert erases\n      the inside and keeps the outside" in pxart.__doc__


# ---------------------------------------------------------------- loop F: flipped scene items (+h / +v / +hv)

ARROW = "k #ff0000\nj #0000ff\nkj.\nk..\n"  # red left column, blue top middle


def test_split_flip():
    assert pxart.split_flip("hero.px:walk/0%night+h") == ("hero.px:walk/0%night", "h")
    assert pxart.split_flip("hero.px:walk/0+h%night") == ("hero.px:walk/0%night", "h")
    assert pxart.split_flip("hero.px+v") == ("hero.px", "v")
    assert pxart.split_flip("hero.png+hv") == ("hero.png", "hv")
    assert pxart.split_flip("hero.png+vh") == ("hero.png", "vh")
    assert pxart.split_flip("hero.px:walk/0") == ("hero.px:walk/0", "")
    assert pxart.split_flip("dir+h/x.png") == ("dir+h/x.png", "")
    assert pxart.split_flip("+h") == ("+h", "")
    assert pxart.split_flip("a.px+x") == ("a.px+x", "")


def scene_grid(path, w, h):
    img = scene_px(path)
    names = {(255, 0, 0): "k", (0, 0, 255): "j"}
    return ["".join(names.get(img.getpixel((x, y))[:3], ".") for x in range(w)) for y in range(h)]


@pytest.mark.parametrize("suffix,want", [("", ["kj.", "k.."]), ("+h", [".jk", "..k"]),
                                         ("+v", ["k..", "kj."]), ("+hv", ["..k", ".jk"]), ("+vh", ["..k", ".jk"])])
def test_scene_item_flip(tmp_path, suffix, want):
    a = write(tmp_path, "a.px", ARROW)
    assert run("scene", "-o", tmp_path / "s.png", "--size", "3x2", "--scale", "1", f"{a}{suffix}@0,0") == 0
    assert scene_grid(tmp_path / "s.png", 3, 2) == want


def test_scene_item_flip_with_frame_and_variant(tmp_path):
    a = write(tmp_path, "a.px", "k #ff0000\nj #0000ff\n\n@variant swap\nk #0000ff\nj #ff0000\n\n@frame f\nkj.\nk..\n"
              "@frame g\n...\n...\n")
    for spec in (f"{a}:f%swap+h@0,0", f"{a}:f+h%swap@0,0"):
        assert run("scene", "-o", tmp_path / "s.png", "--size", "3x2", "--scale", "1", spec) == 0
        assert scene_grid(tmp_path / "s.png", 3, 2) == [".kj", "..j"]


def test_scene_item_flip_png_and_negative_coords(tmp_path):
    img = Image.new("RGBA", (3, 1)); img.putpixel((0, 0), (255, 0, 0, 255)); img.save(tmp_path / "p.png")
    assert run("scene", "-o", tmp_path / "s.png", "--size", "2x1", "--scale", "1", f"{tmp_path / 'p.png'}+h@-1,0") == 0
    assert scene_grid(tmp_path / "s.png", 2, 1) == [".k"]


def test_scene_item_flip_uses_scene_variant(tmp_path):
    hero = write(tmp_path, "hero.px", VHERO.replace("h\n", "h.\n"))
    assert run("scene", "-o", tmp_path / "s.png", "--size", "2x1", "--scale", "1", "--variant", "red",
               f"{hero}+h@0,0") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((1, 0))[:3] == (255, 0, 0) and img.getpixel((0, 0))[:3] == (0x47, 0x2d, 0x3c)


def test_scene_flip_after_at_says_where_it_goes(tmp_path):
    a = write(tmp_path, "a.px", ARROW)
    msg = run_err("scene", "-o", tmp_path / "s.png", f"{a}@0,0+h")
    assert "E_BAD_ARG" in msg and "+h goes before @" in msg and f"{a}+h@0,0" in msg


def test_split_at_leaves_flip_on_the_item():
    assert pxart.split_at("a.px:w/0%n+hv@-2,3") == ("a.px:w/0%n+hv", -2, 3)


def test_map_legend_flip(tmp_path):
    write(tmp_path, "a.px", ARROW)
    m = write(tmp_path, "r.map", "a a.px\nb a.px+h\n\nab\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "3x2", "--scale", "1") == 0
    assert scene_grid(tmp_path / "s.png", 6, 2) == ["kj..jk", "k....k"]
    assert run("check", m) == 0


def test_map_legend_flip_with_spaces_and_quotes(tmp_path):
    d = tmp_path / "my set"
    d.mkdir()
    write(d, "a.px", ARROW)
    m = write(tmp_path, "r.map", 'b "my set/a.px+v"\nc my set/a.px+hv\n\nbc\n')
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "3x2", "--scale", "1") == 0
    assert scene_grid(tmp_path / "s.png", 6, 2) == ["k....k", "kj..jk"]


def test_compose_layer_flip(tmp_path):
    a = write(tmp_path, "a.px", ARROW)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "6x2", f"{a}@0,0", f"{a}+h@3,0") == 0
    assert pxart.parse(out).frames[0].grid == ["kj..jk", "k....k"]
    assert run("compose", "-o", out, "--size", "3x2", f"{a}+hv@0,0") == 0
    assert pxart.parse(out).frames[0].grid == ["..k", ".jk"]


def test_compose_flip_crop_note_counts_flipped_layer(tmp_path, capsys):
    a = write(tmp_path, "a.px", ARROW)
    assert run("compose", "-o", tmp_path / "o.px", "--size", "1x2", f"{a}+h@0,0") == 0
    assert "3 px of a fall outside" in capsys.readouterr().out
    assert pxart.parse(tmp_path / "o.px").frames[0].grid == [".", "."]


def test_flip_suffix_does_not_touch_the_source(tmp_path):
    a = write(tmp_path, "a.px", ARROW)
    assert run("scene", "-o", tmp_path / "s.png", "--size", "3x2", f"{a}+h@0,0") == 0
    assert a.read_text() == ARROW


def test_flip_suffix_through_real_shells(tmp_path):
    import shutil, subprocess
    a = write(tmp_path, "a.px", ARROW)
    script = pathlib.Path(pxart.__file__)
    ran = 0
    for shell in (["zsh", "-f", "-c"], ["zsh", "-f", "-o", "extendedglob", "-c"], ["bash", "-c"]):
        if not shutil.which(shell[0]):
            continue
        h, v = tmp_path / f"h{ran}.png", tmp_path / f"v{ran}.png"
        run_ = f'"{sys.executable}" "{script}" scene --size 3x2 --scale 1'
        cmd = f'P={a}; {run_} -o {h} "${{P}}+h@0,0" && {run_} -o {v} $P+v@0,0'
        r = subprocess.run(shell + [cmd], capture_output=True, text=True)
        assert r.returncode == 0, (shell, r.stderr)
        assert scene_grid(h, 3, 2) == [".jk", "..k"] and scene_grid(v, 3, 2) == ["k..", "kj."]
        ran += 1
    if not ran:
        pytest.skip("no zsh or bash")


def test_help_documents_flip_suffix():
    doc = pxart.__doc__
    assert "FILE[:frame][%variant][+h|+v|+hv]" in doc and "hero.px:walk/0+h@3,4" in doc
    assert "history expansion" in doc


# ---------------------------------------------------------------- loop F: map layers ('---')

LAYER_TILES = "g #00ff00\nd #806040\nr #ff0000\n@frame grass\ngg\ngg\n@frame dirt\ndd\ndd\n@frame rock\n..\n.r\n"


def layer_map(tmp_path, body, head=""):
    write(tmp_path, "t.px", LAYER_TILES)
    return write(tmp_path, "r.map", head + "g t.px:grass\nd t.px:dirt\nr t.px:rock\n\n" + body)


def test_map_layers_draw_in_order(tmp_path):
    m = layer_map(tmp_path, "gd\ngg\n---\nr.\n.r\n")
    placed, size = pxart.read_map(m, (2, 2))
    assert size == (4, 4)
    assert [(pathlib.Path(a).name, x, y) for a, x, y in placed] == [
        ("t.px:grass", 0, 0), ("t.px:dirt", 2, 0), ("t.px:grass", 0, 2), ("t.px:grass", 2, 2),
        ("t.px:rock", 0, 0), ("t.px:rock", 2, 2)]
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((1, 1))[:3] == (255, 0, 0)       # rock over grass
    assert img.getpixel((0, 0))[:3] == (0, 255, 0)       # the rock tile's '.' shows the grass
    assert img.getpixel((2, 0))[:3] == (0x80, 0x60, 0x40) and img.getpixel((3, 1))[:3] == (0x80, 0x60, 0x40)
    assert img.getpixel((3, 3))[:3] == (255, 0, 0)


def test_map_layers_later_wins(tmp_path):
    m = layer_map(tmp_path, "g\n---\nd\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    assert scene_px(tmp_path / "s.png").getpixel((0, 0))[:3] == (0x80, 0x60, 0x40)


def test_map_three_layers_and_blank_lines(tmp_path):
    m = layer_map(tmp_path, "gg\n\n---\n\n.d\n---\n..\n.r\n\n")
    legend, layers, notes, _ = pxart.parse_map(m)
    assert [[r for _, r in rows] for rows in layers] == [["gg"], [".d"], ["..", ".r"]]
    placed, size = pxart.read_map(m, (2, 2))
    assert size == (4, 4) and len(placed) == 4


def test_map_layer_size_is_widest_and_tallest(tmp_path):
    m = layer_map(tmp_path, "g\n---\n...d\n...d\n...d\n")
    placed, size = pxart.read_map(m, (2, 2))
    assert size == (8, 6)
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2", "--scale", "1") == 0
    assert scene_px(tmp_path / "s.png").size == (8, 6)


def test_map_empty_layers_ignored(tmp_path):
    m = layer_map(tmp_path, "---\ngg\n---\n---\ndd\n---\n")
    _, layers, _, _ = pxart.parse_map(m)
    assert [[r for _, r in rows] for rows in layers] == [["gg"], ["dd"]]


def test_map_single_layer_unchanged(tmp_path):
    m = layer_map(tmp_path, "gd\ndg\n")
    _, layers, notes, _ = pxart.parse_map(m)
    assert len(layers) == 1 and notes == []
    placed, size = pxart.read_map(m, (2, 2))
    assert size == (4, 4) and len(placed) == 4


def test_map_layer_hash_rows(tmp_path):
    write(tmp_path, "tiles.px", TILES)
    m = write(tmp_path, "r.map", "# tiles.px:wall\nf tiles.px:floor\n\nff\n---\n#.\n")
    placed, size = pxart.read_map(m, (2, 2))
    assert [pathlib.Path(a).name for a, _, _ in placed] == ["tiles.px:floor", "tiles.px:floor", "tiles.px:wall"]


def test_map_layer_unknown_char_names_its_line(tmp_path):
    m = layer_map(tmp_path, "gg\n---\nq.\n")
    with pytest.raises(pxart.PxError) as e:
        pxart.read_map(m, (2, 2))
    assert codes(e) == ["E_UNKNOWN_KEY"] and e.value.issues[0].line == 7


def test_map_layer_separator_with_dash_legend_notes(tmp_path, capsys):
    write(tmp_path, "t.px", LAYER_TILES)
    m = write(tmp_path, "r.map", "- t.px:dirt\ng t.px:grass\n\ng-\n---\n-.\n")
    _, layers, notes, _ = pxart.parse_map(m)
    assert len(layers) == 2 and any("'---' lines separate layers" in n for n in notes)
    assert run("check", m) == 0
    out = capsys.readouterr().out
    assert "2 layers" in out and "separate layers" in out


def test_map_dash_legend_without_separator_no_note(tmp_path):
    write(tmp_path, "t.px", LAYER_TILES)
    m = write(tmp_path, "r.map", "- t.px:dirt\n\n--\n")
    _, layers, notes, _ = pxart.parse_map(m)
    assert notes == [] and [r for _, r in layers[0]] == ["--"]


def test_check_map_reports_layers(tmp_path, capsys):
    m = layer_map(tmp_path, "gg\ngg\n---\nr.\n")
    assert run("check", m) == 0
    assert f"ok   {m}: map 2x2 tiles, 3 legend char(s), 2 layers" in capsys.readouterr().out


def test_check_map_single_layer_line_unchanged(tmp_path, capsys):
    m = layer_map(tmp_path, "gg\n")
    assert run("check", m) == 0
    assert capsys.readouterr().out.strip() == f"ok   {m}: map 2x1 tiles, 3 legend char(s)"


def test_map_layers_with_variant_and_flip(tmp_path):
    write(tmp_path, "tiles.px", VTILES)
    write(tmp_path, "a.px", ARROW)
    m = write(tmp_path, "r.map", "f tiles.px:floor%dark\na a.px+h\n\nf\n---\na\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "3x2", "--scale", "1", "--bg", "#ffffff") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.getpixel((2, 0))[:3] == (255, 0, 0) and img.getpixel((1, 0))[:3] == (0, 0, 255)
    assert img.getpixel((0, 1))[:3] == (1, 1, 1)  # dark floor under the arrow's '.'
    assert img.getpixel((2, 1))[:3] == (255, 0, 0)
    assert "E_SELECT" in run_err("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "3x2", "--variant", "dark")


def test_help_documents_map_layers():
    assert "a line '---' after the rows starts another" in pxart.__doc__


# ---------------------------------------------------------------- loop F: zsh-eaten ':' on inputs, -o under a file

@pytest.mark.parametrize("name", ["hero.pxalk/0", "hero.pxidle", "hero.pxidle:walk", "sub/hero.pxt",
                                  "scene.pngalk", "scene.pngx/y"])
def test_missing_mangled_input_mentions_zsh(tmp_path, name):
    msg = run_err("render", tmp_path / name, "-o", tmp_path / "x.png")
    assert "E_FILE" in msg and "zsh ate a ':'" in msg and '"${F}:walk/0"' in msg


@pytest.mark.parametrize("name", ["nope.px", "nope.png", "dir/nope.px", "nope.px:walk/0", "a.px.bak", "pngs/x.px"])
def test_missing_plain_input_has_no_zsh_hint(tmp_path, name):
    msg = run_err("render", tmp_path / name, "-o", tmp_path / "x.png")
    assert "E_FILE" in msg and "zsh" not in msg


@pytest.mark.parametrize("cmd", [["flip", "{f}"], ["check", "{f}"], ["stats", "{f}"], ["frames", "{f}"],
                                 ["set", "{f}", "k", "0,0"], ["mask", "{f}", "--keep", "0,0,1,1"],
                                 ["fill", "{f}", "k"], ["extract", "{f}", "-o", "{o}"],
                                 ["scene", "-o", "{o}", "{f}@0,0"], ["anim", "{f}", "-o", "{o}"]])
def test_mangled_input_hint_on_every_command(tmp_path, cmd):
    f, o = tmp_path / "hero.pxalk" / "0", tmp_path / "o.png"
    msg = run_err(*[a.format(f=f, o=o) for a in cmd])
    assert "zsh ate a ':'" in msg


def test_existing_file_with_glued_letters_is_fine(tmp_path):
    p = write(tmp_path, "tiles.pxbak", "k #000000\nk\n")  # exists: no hint, it just loads
    assert run("render", p, "-o", tmp_path / "x.png") == 0


def test_real_zsh_mangling_gets_the_hint(tmp_path):
    import shutil, subprocess
    if not shutil.which("zsh"):
        pytest.skip("no zsh")
    p = write(tmp_path, "hero.px", "k #000000\n@frame walk/0\nk.\n")
    script = pathlib.Path(pxart.__file__)
    for arg in ('"$P:walk/0"', '$P:twalk/0', '"$P:tidle"', '"$P:aidle"'):
        r = subprocess.run(["zsh", "-f", "-c", f'P={p}; "{sys.executable}" "{script}" flip {arg}'],
                           capture_output=True, text=True)
        assert r.returncode == 1 and "zsh ate a ':'" in r.stderr, (arg, r.stderr)
    # ':i' isn't a modifier: zsh leaves it, and the real problem (no such frame) is what's reported
    r = subprocess.run(["zsh", "-f", "-c", f'P={p}; "{sys.executable}" "{script}" flip "$P:idle"'],
                       capture_output=True, text=True)
    assert "E_SELECT" in r.stderr and "zsh ate" not in r.stderr
    r = subprocess.run(["zsh", "-f", "-c", f'P={p}; "{sys.executable}" "{script}" flip "${{P}}:walk/0"'],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "wrote" in r.stdout


@pytest.mark.parametrize("cmd", [
    ["flip", "{p}", "-o", "{p}/walk.px"],
    ["render", "{p}", "-o", "{p}/r.png"],
    ["scene", "-o", "{p}/s.png", "{p}@0,0"],
    ["sheet", "{p}", "-o", "{p}/deep/s.png"],
    ["anim", "{p}", "-o", "{p}/a.gif"],
    ["mask", "{png}", "--keep", "0,0,1,1", "-o", "{p}/m.png"],
    ["tint", "{png}", "#00000080", "-o", "{p}/t.png"],
    ["extract", "{p}", "-o", "{p}/e.px"],
    ["export", "{p}", "--frames", "{p}/frames"],
    ["palette", "{p}", "--export", "{p}/p.gpl"],
    ["new", "{p}/n.px", "--size", "1x1"],
])
def test_output_under_a_file_is_a_clear_error(tmp_path, cmd):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    png_ = solid_png(tmp_path, "s.png", (2, 2))
    msg = run_err(*[a.format(p=p, png=png_) for a in cmd])
    assert "E_FILE" in msg and f"{p} is a file, not a directory" in msg
    assert p.read_text() == "k #000000\nk\n"


def test_output_under_a_px_file_suggests_a_frame(tmp_path):
    p = write(tmp_path, "hero.px", "k #000000\n@frame a\nk\n")
    src = write(tmp_path, "l.px", "k #000000\nk\n")
    msg = run_err("flip", src, "-o", tmp_path / "hero.px" / "walk" / "0")
    assert f"a frame goes after ':', as in {p}:walk/0" in msg


def test_output_under_a_png_file_has_no_frame_hint(tmp_path):
    q = solid_png(tmp_path, "s.png", (2, 2))
    msg = run_err("tint", q, "#000000", "-o", tmp_path / "s.png" / "x.png")
    assert "is a file, not a directory" in msg and "a frame goes" not in msg


def test_outpath_still_creates_directories(tmp_path):
    assert pxart.outpath(tmp_path / "a" / "b" / "c.png") == tmp_path / "a" / "b" / "c.png"
    assert (tmp_path / "a" / "b").is_dir()


def test_help_documents_mangled_inputs_and_file_parents():
    doc = pxart.__doc__
    assert "hero.pxalk/0" in doc and "-o hero.px/walk/0" in doc


# ---------------------------------------------------------------- loop F: check notes non-ASCII lookalikes

@pytest.mark.parametrize("ch,asc,name", [("а", "a", "CYRILLIC SMALL LETTER A"), ("е", "e", "CYRILLIC SMALL LETTER IE"),
                                         ("о", "o", "CYRILLIC SMALL LETTER O"), ("р", "p", "CYRILLIC SMALL LETTER ER"),
                                         ("с", "c", "CYRILLIC SMALL LETTER ES"), ("х", "x", "CYRILLIC SMALL LETTER HA"),
                                         ("у", "y", "CYRILLIC SMALL LETTER U"), ("Н", "H", "CYRILLIC CAPITAL LETTER EN"),
                                         ("ο", "o", "GREEK SMALL LETTER OMICRON"), ("Α", "A", "GREEK CAPITAL LETTER ALPHA"),
                                         ("ｋ", "k", "FULLWIDTH LATIN SMALL LETTER K"), ("＃", "#", "FULLWIDTH NUMBER SIGN"),
                                         ("０", "0", "FULLWIDTH DIGIT ZERO"), ("．", ".", "FULLWIDTH FULL STOP")])
def test_lookalike_table(ch, asc, name):
    assert pxart.lookalike(ch) == asc
    import unicodedata
    assert unicodedata.name(ch) == name


@pytest.mark.parametrize("ch", ["a", "k", ".", " ", "é", "ß", "中", "→", "λ", "ж", "　"])
def test_not_lookalikes(ch):
    assert pxart.lookalike(ch) is None


def test_check_notes_lookalike_in_grid_row(tmp_path, capsys):
    p = write(tmp_path, "h.px", "k #000000\no #ffffff\n@frame walk/0\nkok\nkоk\n")
    assert run("check", p) == 1
    out = capsys.readouterr().out
    fail_at, note_at = out.index("FAIL"), out.index("note:")
    assert fail_at < note_at  # the note follows the file's own lines
    assert (f"     note: {p}:5 (frame walk/0, row 1, x=1): 'о' is U+043E CYRILLIC SMALL LETTER O, not ASCII 'o'"
            in out)


def test_check_notes_lookalike_palette_key(tmp_path, capsys):
    p = write(tmp_path, "h.px", "k #000000\nа #ffffff\nk\n")
    assert run("check", p) == 1
    out = capsys.readouterr().out
    assert f"{p}:2 (col 1 (the key)): 'а' is U+0430 CYRILLIC SMALL LETTER A, not ASCII 'a'" in out
    assert "E_BAD_KEY" in out


def test_check_notes_fullwidth_in_implicit_grid(tmp_path, capsys):
    p = write(tmp_path, "h.px", "k #000000\n\nkk\nkｋ\n")
    assert run("check", p) == 1
    assert f"{p}:4 (row 1, x=1): 'ｋ' is U+FF4B FULLWIDTH LATIN SMALL LETTER K, not ASCII 'k'" in capsys.readouterr().out


def test_check_notes_every_lookalike_on_a_line(tmp_path, capsys):
    p = write(tmp_path, "h.px", "o #000000\n@frame a\nоoо\n")
    assert run("check", p) == 1
    out = capsys.readouterr().out
    assert "(frame a, row 0, x=0)" in out and "(frame a, row 0, x=2)" in out and "x=1)" not in out


def test_check_notes_indented_lines_count_columns(tmp_path, capsys):
    p = write(tmp_path, "h.px", "k #000000\n  kkа\n")
    assert run("check", p) == 1
    assert "(row 0, x=2)" in capsys.readouterr().out


def test_check_lookalike_rows_count_per_frame(tmp_path, capsys):
    p = write(tmp_path, "h.px", "k #000000\n@frame a\nkk\nkk\n@frame b\nkk\nkх\n")
    assert run("check", p) == 1
    assert "(frame b, row 1, x=1): 'х'" in capsys.readouterr().out


def test_check_lookalike_in_comment_is_ignored(tmp_path, capsys):
    p = write(tmp_path, "h.px", "# сolor notes: о\nk #000000\nk\n")
    assert run("check", p) == 0
    assert "note:" not in capsys.readouterr().out


def test_check_lookalike_in_unknown_section_is_ignored(tmp_path, capsys):
    p = write(tmp_path, "h.px", "k #000000\nk\n\n@future thing\nаbc\n")
    assert run("check", p) == 0
    assert "note:" not in capsys.readouterr().out


def test_check_clean_file_has_no_lookalike_note(tmp_path, capsys):
    p = write(tmp_path, "m.px", MULTI)
    assert run("check", p) == 0
    assert "U+" not in capsys.readouterr().out


def test_check_lookalike_note_is_not_a_failure(tmp_path, capsys):
    q = write(tmp_path, "m.map", "а x.png\n\nа\n")
    png(tmp_path, "x.png", (1, 1), (1, 1, 1, 255))
    assert run("check", q) == 0  # a Cyrillic legend char used consistently still works
    assert "U+0430" in capsys.readouterr().out


def test_check_map_notes_lookalike_mismatch(tmp_path, capsys):
    png(tmp_path, "x.png", (1, 1), (1, 1, 1, 255))
    m = write(tmp_path, "m.map", "a x.png\n\naа\n")
    assert run("check", m) == 1
    out = capsys.readouterr().out
    assert "E_UNKNOWN_KEY" in out and f"{m}:3 (col 2): 'а' is U+0430 CYRILLIC SMALL LETTER A, not ASCII 'a'" in out


def test_check_palette_file_lookalike(tmp_path, capsys):
    p = write(tmp_path, "pal.px", "k #000000\nе #ffffff\n")
    assert run("check", p) == 1
    assert "'е' is U+0435 CYRILLIC SMALL LETTER IE, not ASCII 'e'" in capsys.readouterr().out


def test_check_missing_file_still_errors_without_notes(tmp_path):
    assert "E_FILE" in run_err("check", tmp_path / "nope.px")


def test_help_documents_lookalikes():
    assert "look like ASCII (Cyrillic/Greek" in pxart.__doc__


# ---------------------------------------------------------------- loop G: frames FILE:SEL

SELS = ("k #000000\n@anim walk ms=90\n@frame idle/0\nk\n@frame walk/0\nk\n@frame walk/1\nk\n@frame walk/2\nk\n"
        "@frame icon\nk\n")


def test_frames_sel_lists_only_the_selection(tmp_path, capsys):
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", f"{p}:walk") == 0
    out = capsys.readouterr().out
    assert out.startswith("walk: 3 frame(s) [ms=90]\n")
    assert "walk/0  1x1  90ms" in out and "walk/2  1x1  90ms" in out
    assert "idle" not in out and "icon" not in out


def test_frames_sel_one_frame_says_of_how_many(tmp_path, capsys):
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", f"{p}:walk/1") == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "walk: 1 frame(s) (of 3) [ms=90]" and "walk/1  1x1  90ms" in out
    assert "walk/0" not in out


def test_frames_sel_top_level_frame(tmp_path, capsys):
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", f"{p}:icon") == 0
    assert capsys.readouterr().out.startswith("(no group): 1 frame(s)\n")


def test_frames_without_sel_listing_unchanged(tmp_path, capsys):
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "(of" not in out and "walk: 3 frame(s) [ms=90]" in out and "idle: 1 frame(s)" in out


def test_frames_sel_unknown_is_select_not_file_error(tmp_path):
    p = write(tmp_path, "h.px", SELS)
    msg = run_err("frames", f"{p}:run")
    assert "E_SELECT" in msg and "E_FILE" not in msg


def test_frames_sel_rm_removes_the_selection(tmp_path, capsys):
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", f"{p}:walk", "--rm") == 0
    assert capsys.readouterr().out == f"removed walk/0, walk/1, walk/2; removed @anim walk (no frames left); wrote {p}\n"
    assert ids(p) == ["idle/0", "icon"] and "@anim" not in p.read_text()


def test_frames_sel_rm_one_frame(tmp_path, capsys):
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", f"{p}:walk/1", "--rm") == 0
    assert capsys.readouterr().out == f"removed walk/1; wrote {p}\n"
    assert ids(p) == ["idle/0", "walk/0", "walk/2", "icon"]


def test_frames_sel_rm_ids_inside_the_selection(tmp_path, capsys):
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", f"{p}:walk", "--rm", "walk/2", "walk/0") == 0
    assert capsys.readouterr().out == f"removed walk/0, walk/2; wrote {p}\n"
    assert ids(p) == ["idle/0", "walk/1", "icon"]


def test_frames_sel_rm_id_outside_the_selection_is_select_error(tmp_path):
    p = write(tmp_path, "h.px", SELS)
    before = p.read_text()
    msg = run_err("frames", f"{p}:walk", "--rm", "idle/0")
    assert "E_SELECT" in msg and "--rm idle/0: not in 'walk'" in msg and "drop the :SEL" in msg
    assert p.read_text() == before


def test_frames_sel_rm_is_the_error_from_loop_g(tmp_path):
    """The loop G call: 'frames FILE:SEL --rm ...' used to be E_FILE: No such file or directory."""
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", f"{p}:walk/0", "--rm", "walk/0") == 0
    assert ids(p) == ["idle/0", "walk/1", "walk/2", "icon"]


def test_frames_sel_rm_keeps_layout(tmp_path):
    p = write(tmp_path, "a.px", BLANK_FRAMES)
    assert run("frames", f"{p}:walk/1", "--rm") == 0
    assert p.read_text() == BLANK_FRAMES.replace("@frame walk/1\n.kk.\nkgkk\n\n", "")


def test_frames_sel_move_block_after(tmp_path, capsys):
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", f"{p}:walk", "--after", "icon") == 0
    assert capsys.readouterr().out == f"moved walk (3 frame(s)) after icon; wrote {p}\n"
    assert ids(p) == ["idle/0", "icon", "walk/0", "walk/1", "walk/2"]


def test_frames_sel_move_block_before(tmp_path, capsys):
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", f"{p}:walk", "--before", "idle/0") == 0
    assert ids(p) == ["walk/0", "walk/1", "walk/2", "idle/0", "icon"]


def test_frames_sel_move_one_frame(tmp_path):
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", f"{p}:walk/2", "--before", "walk/0") == 0
    assert ids(p) == ["idle/0", "walk/2", "walk/0", "walk/1", "icon"]


def test_frames_sel_move_to_same_place_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "h.px", SELS)
    before, m = snap(p)
    assert run("frames", f"{p}:walk", "--after", "idle/0") == 0
    assert capsys.readouterr().out.endswith(f"no change: {p}\n") and untouched(p, before, m)


def test_frames_sel_move_anchor_inside_selection(tmp_path):
    p = write(tmp_path, "h.px", SELS)
    msg = run_err("frames", f"{p}:walk", "--after", "walk/1")
    assert "E_SELECT" in msg and "inside the selection 'walk'" in msg


def test_frames_sel_move_missing_anchor(tmp_path):
    p = write(tmp_path, "h.px", SELS)
    assert "E_SELECT" in run_err("frames", f"{p}:walk", "--after", "nope")


def test_frames_sel_with_move_is_bad_arg_saying_why(tmp_path):
    p = write(tmp_path, "h.px", SELS)
    msg = run_err("frames", f"{p}:walk", "--move", "walk/0", "--after", "icon")
    assert "E_BAD_ARG" in msg and "--move takes one frame id and FILE without :SEL" in msg
    assert f"frames {p}:walk --after ID" in msg


def test_frames_sel_rm_and_move_together_is_bad_arg(tmp_path):
    p = write(tmp_path, "h.px", SELS)
    msg = run_err("frames", f"{p}:walk", "--rm", "--after", "icon")
    assert "E_BAD_ARG" in msg and "not both" in msg


def test_frames_after_and_before_together_is_bad_arg(tmp_path):
    p = write(tmp_path, "h.px", SELS)
    assert "E_BAD_ARG" in run_err("frames", p, "--move", "icon", "--after", "walk/0", "--before", "walk/1")


def test_frames_bare_rm_without_sel_is_bad_arg(tmp_path):
    p = write(tmp_path, "h.px", SELS)
    msg = run_err("frames", p, "--rm")
    assert "E_BAD_ARG" in msg and "FILE:SEL" in msg


def test_frames_after_without_move_or_sel_is_bad_arg(tmp_path):
    p = write(tmp_path, "h.px", SELS)
    before = p.read_text()
    msg = run_err("frames", p, "--after", "icon")
    assert "E_BAD_ARG" in msg and "--move ID" in msg and p.read_text() == before


def test_frames_sel_on_implicit_file(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    assert "E_SELECT" in run_err("frames", f"{p}:x")


def test_frames_missing_file_with_sel_is_file_error_on_the_file(tmp_path):
    msg = run_err("frames", f"{tmp_path / 'nope.px'}:walk", "--rm")
    assert "E_FILE" in msg and "nope.px" in msg and "nope.px:walk" not in msg


def test_help_documents_frames_sel():
    doc = pxart.__doc__
    assert "frames FILE[:SEL] [--rm [ID...]]" in doc and "moves them there as a block" in doc


# ---------------------------------------------------------------- loop G: map placement, +b bottom anchor

def rect(x, y, w, h):
    return {(xx, yy) for yy in range(y, y + h) for xx in range(x, x + w)}


def where(img, rgb):
    return {(x, y) for y in range(img.height) for x in range(img.width) if img.getpixel((x, y))[:3] == rgb}


def solid(w, h, key):
    return "\n".join([key * w] * h) + "\n"


MARKET_TILES = ("c #808080\nw #0000ff\nr #ff0000\no #ff8000\n@frame cobble\n" + solid(16, 16, "c")
                + "@frame water/0\n" + solid(16, 16, "w")
                + "@frame crate\n" + "\n".join(["r" + "o" * 15] * 16) + "\n")
STALL = "s #00ff00\n" + solid(32, 32, "s")
LAMP = "y #ffff00\nl #ff00ff\n" + "\n".join(["y" + "l" * 15] * 32) + "\n"


def doc_example_map():
    """The worked market.map in -h, as written there."""
    lines = pxart.__doc__.splitlines()
    i = next(n for n, l in enumerate(lines) if "A worked map, market.map" in l)
    body = []
    for l in lines[i + 2:]:
        if l.startswith("      'pxart scene"):
            break
        body.append(l[10:])
    return "\n".join(body) + "\n"


def market(tmp_path, text=None):
    write(tmp_path, "tiles.px", MARKET_TILES)
    write(tmp_path, "stall.px", STALL)
    write(tmp_path, "lamp.px", LAMP)
    return write(tmp_path, "market.map", text or doc_example_map())


def test_help_worked_map_example_renders_as_documented(tmp_path):
    m = market(tmp_path)
    assert "S stall.px+b" in m.read_text() and "---" in m.read_text() and "l lamp.px+hb" in m.read_text()
    assert run("check", m) == 0
    assert run("scene", "--map", m, "-o", tmp_path / "market.png", "--scale", "1") == 0
    img = scene_px(tmp_path / "market.png")
    assert img.size == (96, 48)
    assert where(img, (0, 255, 0)) == rect(8, 0, 32, 32)                          # stall at 8,0
    assert where(img, (255, 255, 0)) == rect(48, 0, 1, 32) | rect(95, 0, 1, 32)   # lamp edges: 48,0 and 80,0 mirrored
    assert where(img, (255, 0, 255)) == rect(49, 0, 15, 32) | rect(80, 0, 15, 32)
    assert where(img, (255, 0, 0)) == rect(15, 32, 1, 16)                        # crate mirrored at 0,32
    assert where(img, (255, 128, 0)) == rect(0, 32, 15, 16)
    assert where(img, (0, 0, 255)) == rect(16, 32, 80, 16)
    assert where(img, (128, 128, 128)) == rect(0, 0, 96, 32) - rect(8, 0, 32, 32) - rect(48, 0, 16, 32) \
        - rect(80, 0, 16, 32)


def test_map_default_placement_is_cell_top_left(tmp_path):
    m = market(tmp_path, "S stall.px\nL lamp.px\n\n....\n.S.L\n....\n")
    assert run("scene", "--map", m, "-o", tmp_path / "s.png", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.size == (64, 48)
    assert where(img, (0, 255, 0)) == rect(16, 16, 32, 32)  # hangs right and down from its cell
    assert where(img, (255, 255, 0)) == rect(48, 16, 1, 32)


@pytest.mark.parametrize("size,tile,cell,want", [
    ((32, 32), (16, 16), (16, 16), (8, 0)),
    ((16, 32), (16, 16), (48, 16), (48, 0)),
    ((16, 16), (16, 16), (32, 16), (32, 16)),     # a tile-sized item: same as top-left
    ((16, 8), (16, 16), (0, 0), (0, 8)),          # shorter: sits on the cell's bottom
    ((8, 8), (16, 16), (0, 0), (4, 8)),           # narrower: centered
    ((15, 16), (16, 16), (0, 0), (0, 0)),         # odd spare pixel: the item goes left
    ((13, 16), (16, 16), (16, 0), (17, 0)),
    ((33, 20), (16, 16), (16, 16), (7, 12)),      # wider by an odd amount: floor, one more to the left
    ((48, 48), (16, 16), (0, 0), (-16, -32)),     # off the top-left edge
    ((3, 5), (2, 2), (4, 6), (3, 3)),
])
def test_cell_spot_bottom_anchor_math(size, tile, cell, want):
    img = Image.new("RGBA", size)
    assert pxart.cell_spot("a.px+b", img, *cell, tile) == want
    x, y = cell
    assert want == (x + (tile[0] - size[0]) // 2, y + tile[1] - size[1])


@pytest.mark.parametrize("arg", ["a.px", "a.px+h", "a.px+v", "a.px+hv", "a.px:x%dusk+h", "dir+b/a.px"])
def test_cell_spot_without_b_is_the_cell(arg):
    assert pxart.cell_spot(arg, Image.new("RGBA", (32, 32)), 16, 16, (16, 16)) == (16, 16)


@pytest.mark.parametrize("arg", ["a.px+b", "a.px+hb", "a.px+bh", "a.px+vb", "a.px+hvb", "a.px+bvh", "a.px:x%dusk+b",
                                 "a.px:x+b%dusk"])
def test_cell_spot_with_b_anywhere_in_the_suffix(arg):
    assert pxart.cell_spot(arg, Image.new("RGBA", (32, 32)), 16, 16, (16, 16)) == (8, 0)


def test_split_flip_with_b():
    assert pxart.split_flip("lamp.px+b") == ("lamp.px", "b")
    assert pxart.split_flip("lamp.px+hb") == ("lamp.px", "hb")
    assert pxart.split_flip("lamp.px:on%dusk+hvb") == ("lamp.px:on%dusk", "hvb")
    assert pxart.split_flip("lamp.px:on+bh%dusk") == ("lamp.px:on%dusk", "bh")
    assert pxart.split_flip("lamp.px+bb") == ("lamp.px+bb", "")
    assert pxart.split_flip("lamp.px+hh") == ("lamp.px+hh", "")
    assert pxart.split_flip("lamp.px+hvbx") == ("lamp.px+hvbx", "")
    assert pxart.split_flip("+b") == ("+b", "")


@pytest.mark.parametrize("suffix,col", [("+b", 0), ("+hb", 15), ("+bh", 15)])
def test_map_bottom_anchor_with_flip(tmp_path, suffix, col):
    m = market(tmp_path, f"L lamp.px{suffix}\n\n.\nL\n")
    assert run("scene", "--map", m, "-o", tmp_path / "s.png", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert where(img, (255, 255, 0)) == rect(col, 0, 1, 32)


def test_map_bottom_anchor_with_v_flip(tmp_path):
    lamp = "y #ffff00\nl #ff00ff\n" + "y" * 16 + "\n" + ("l" * 16 + "\n") * 31  # yellow top row
    write(tmp_path, "lamp.px", lamp)
    m = write(tmp_path, "r.map", "L lamp.px+vb\nM lamp.px+b\n\n..\nLM\n")
    assert run("scene", "--map", m, "-o", tmp_path / "s.png", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert where(img, (255, 255, 0)) == rect(0, 31, 16, 1) | rect(16, 0, 16, 1)


def test_map_bottom_anchor_on_first_row_is_cut_at_the_top(tmp_path):
    m = market(tmp_path, "L lamp.px+b\n\nL\n")
    assert run("scene", "--map", m, "-o", tmp_path / "s.png", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.size == (16, 16) and where(img, (255, 255, 0)) == rect(0, 0, 1, 16)


def test_map_bottom_anchor_wide_prop_off_the_left_edge(tmp_path):
    m = market(tmp_path, "S stall.px+b\n\nS.\n")
    assert run("scene", "--map", m, "-o", tmp_path / "s.png", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert where(img, (0, 255, 0)) == rect(0, 0, 24, 16)  # drawn at -8,-16, clipped


def test_map_bottom_anchor_with_other_tile_size(tmp_path):
    m = market(tmp_path, "L lamp.px+b\n\n..\n.L\n")
    assert run("scene", "--map", m, "--tile", "8x8", "-o", tmp_path / "s.png", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert img.size == (16, 16)
    assert where(img, (255, 255, 0)) == rect(4, 0, 1, 16)  # 8 + (8-16)//2 = 4; 8 + 8 - 32 = -16


def test_map_bottom_anchor_with_variants(tmp_path):
    write(tmp_path, "lamp.px", "y #ffff00\n\n@variant dusk\ny #0000ff\n\n" + solid(4, 8, "y"))
    m = write(tmp_path, "r.map", "a lamp.px%dusk+b\nb lamp.px+b%dusk\nc lamp.px+b\n\n...\nabc\n")
    assert run("scene", "--map", m, "--tile", "4x4", "-o", tmp_path / "s.png", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert where(img, (0, 0, 255)) == rect(0, 0, 8, 8) and where(img, (255, 255, 0)) == rect(8, 0, 4, 8)
    assert run("scene", "--map", m, "--tile", "4x4", "-o", tmp_path / "t.png", "--scale", "1", "--variant", "dusk") == 0
    assert where(scene_px(tmp_path / "t.png"), (0, 0, 255)) == rect(0, 0, 12, 8)


def test_map_bottom_anchor_path_with_spaces(tmp_path):
    d = tmp_path / "tiles and props"
    d.mkdir()
    write(d, "lamp.px", LAMP)
    for line in ("L tiles and props/lamp.px+b", 'L "tiles and props/lamp.px+b"'):
        m = write(tmp_path, "r.map", f"{line}\n\n.\nL\n")
        assert run("check", m) == 0
        assert run("scene", "--map", m, "-o", tmp_path / "s.png", "--scale", "1") == 0
        assert where(scene_px(tmp_path / "s.png"), (255, 255, 0)) == rect(0, 0, 1, 32)


def test_map_bottom_anchor_png_legend(tmp_path):
    png(tmp_path, "tall.png", (2, 4), (9, 9, 9, 255))
    m = write(tmp_path, "r.map", "t tall.png+b\n\n..\n.t\n")
    assert run("scene", "--map", m, "--tile", "2x2", "-o", tmp_path / "s.png", "--scale", "1") == 0
    assert where(scene_px(tmp_path / "s.png"), (9, 9, 9)) == rect(2, 0, 2, 4)


def test_map_bottom_anchor_in_a_later_layer_draws_over_the_row_above(tmp_path):
    m = market(tmp_path, "c tiles.px:cobble\nL lamp.px+b\n\ncc\ncc\n---\n..\n.L\n")
    assert run("scene", "--map", m, "-o", tmp_path / "s.png", "--scale", "1") == 0
    img = scene_px(tmp_path / "s.png")
    assert where(img, (255, 255, 0)) == rect(16, 0, 1, 32)
    assert where(img, (128, 128, 128)) == rect(0, 0, 32, 32) - rect(16, 0, 16, 32)


def test_read_map_still_returns_cells(tmp_path):
    m = market(tmp_path, "L lamp.px+b\n\n.L\n")
    placed, size = pxart.read_map(m, (16, 16))
    assert placed == [(str(tmp_path / "lamp.px+b"), 16, 0)] and size == (32, 16)


def test_scene_item_with_b_is_bad_arg(tmp_path):
    write(tmp_path, "lamp.px", LAMP)
    msg = run_err("scene", "-o", tmp_path / "s.png", f"{tmp_path / 'lamp.px'}+hb@0,0")
    assert "E_BAD_ARG" in msg and "+b anchors a map legend entry" in msg and f"{tmp_path / 'lamp.px'}+h" in msg
    assert not (tmp_path / "s.png").exists()


def test_compose_layer_with_b_is_bad_arg(tmp_path):
    write(tmp_path, "lamp.px", LAMP)
    msg = run_err("compose", "-o", tmp_path / "o.px", f"{tmp_path / 'lamp.px'}+b@0,0")
    assert "E_BAD_ARG" in msg and "+b anchors" in msg


def test_scene_b_after_at_says_where_it_goes(tmp_path):
    write(tmp_path, "lamp.px", LAMP)
    msg = run_err("scene", "-o", tmp_path / "s.png", f"{tmp_path / 'lamp.px'}@0,0+hb")
    assert "+hb goes before @" in msg


def test_help_documents_map_placement():
    doc = pxart.__doc__
    assert "draws with its top-left at its cell's top-left" in doc
    assert "A legend entry ending in +b (with flips: +hb, +vb, +hvb)" in doc
    assert "x = cell x + (tile w - w) // 2" in doc and "y = cell y + tile h - h" in doc


# ---------------------------------------------------------------- loop G: recolor 'a<>b', moves apply together

SWAP = "k #000000\nj #ffffff\nr #ff0000\ng #00ff00\n@frame a\nkjrg\njkgr\n@frame b\nkkjj\n"


def grids(p):
    return {f.id: f.grid for f in pxart.parse(p).frames}


def test_recolor_swap(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", p, "k<>j") == 0
    assert grids(p) == {"a": ["jkrg", "kjgr"], "b": ["jjkk"]}


def test_recolor_swap_twice_is_the_original(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", p, "k<>j") == 0
    assert run("recolor", p, "j<>k") == 0
    assert p.read_text() == SWAP


def test_recolor_swap_selection_only(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", f"{p}:b", "k<>j") == 0
    assert grids(p) == {"a": ["kjrg", "jkgr"], "b": ["jjkk"]}


def test_recolor_swap_region_only(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", f"{p}:a", "k<>j", "--region", "0,0,2,1") == 0
    assert grids(p)["a"] == ["jkrg", "jkgr"]


def test_recolor_swap_region_and_selection(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", p, "r<>g", "--region", "2,1,2,1") == 0
    assert grids(p) == {"a": ["kjrg", "jkrg"], "b": ["kkjj"]}


def test_recolor_swap_does_not_interfere_with_a_move(tmp_path):
    # c=a moves c's own pixels to a; the swap doesn't then carry them on to b.
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", p, "k<>j", "r=k") == 0
    assert grids(p) == {"a": ["jkkg", "kjgk"], "b": ["jjkk"]}


def test_recolor_move_before_swap_same_result(tmp_path):
    p, q = write(tmp_path, "s.px", SWAP), write(tmp_path, "t.px", SWAP)
    assert run("recolor", p, "k<>j", "r=k") == 0
    assert run("recolor", q, "r=k", "k<>j") == 0
    assert grids(p) == grids(q)


def test_recolor_two_swaps_in_one_call(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", p, "k<>j", "r<>g") == 0
    assert grids(p) == {"a": ["jkgr", "kjrg"], "b": ["jjkk"]}


def test_recolor_rotation_with_moves(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", p, "k=j", "j=r", "r=k") == 0
    assert grids(p) == {"a": ["jrkg", "rjgk"], "b": ["jjrr"]}


def test_recolor_moves_apply_together_not_in_a_chain(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", p, "k=j", "j=r") == 0
    assert grids(p)["b"] == ["jjrr"]  # k went to j and stopped there


def test_recolor_equals_pair_is_a_swap(tmp_path):
    p, q = write(tmp_path, "s.px", SWAP), write(tmp_path, "t.px", SWAP)
    assert run("recolor", p, "k=j", "j=k") == 0
    assert run("recolor", q, "k<>j") == 0
    assert p.read_text() == q.read_text()


def test_recolor_swap_with_a_color_change(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", p, "k<>j", "r=#123456") == 0
    doc = pxart.parse(p)
    assert doc.get("b").grid == ["jjkk"] and doc.palette["r"] == (0x12, 0x34, 0x56, 255)
    assert doc.get("a").grid == ["jkrg", "kjgr"]


def test_recolor_swap_and_color_of_a_swapped_key(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", p, "k<>j", "k=#111111") == 0
    doc = pxart.parse(p)
    assert doc.get("b").grid == ["jjkk"] and doc.palette["k"] == (0x11, 0x11, 0x11, 255)


def test_recolor_swap_with_transparent(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n@frame a\nk..k\n")
    assert run("recolor", p, ".<>k") == 0
    assert grids(p)["a"] == [".kk."]


def test_recolor_swap_with_itself_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWAP)
    before, m = snap(p)
    assert run("recolor", p, "k<>k") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_recolor_swap_of_keys_with_no_pixels_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWAP)
    before, m = snap(p)
    assert run("recolor", f"{p}:b", "r<>g") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_recolor_swap_keeps_layout(tmp_path):
    p = write(tmp_path, "a.px", MESSY)
    assert run("recolor", f"{p}:walk/0", "k<>g") == 0
    assert p.read_text() == MESSY.replace("  .kk.\nkggk\n# mid-grid comment\nkggk\n",
                                          ".gg.\ngkkg\n# mid-grid comment\ngkkg\n")


def test_recolor_key_moved_twice_is_bad_arg(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    before = p.read_text()
    for maps in (["k<>j", "k=r"], ["k=r", "k<>j"], ["k<>j", "j<>r"], ["k=j", "k=r"]):
        msg = run_err("recolor", p, *maps)
        assert "E_BAD_ARG" in msg and "moved twice" in msg, maps
    assert p.read_text() == before


def test_recolor_two_colors_for_one_key_is_bad_arg(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    assert "two colors" in run_err("recolor", p, "k=#111111", "k=#222222")


def test_recolor_swap_unknown_key(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    assert "E_SELECT" in run_err("recolor", p, "k<>q")
    assert "E_SELECT" in run_err("recolor", p, "q<>k")


def test_recolor_swap_with_color_is_bad_arg(tmp_path):
    p = write(tmp_path, "s.px", SWAP)
    msg = run_err("recolor", p, "k<>#ffffff")
    assert "E_BAD_ARG" in msg and "k=#ffffff" in msg


def test_recolor_unquoted_swap_gets_a_hint(tmp_path):
    # 'recolor s.px k<>j' unquoted: the shell passes only 'k' (and redirects stdin from j)
    p = write(tmp_path, "s.px", SWAP)
    msg = run_err("recolor", p, "k")
    assert "E_BAD_ARG" in msg and "quote a swap" in msg and "shell redirections" in msg


def test_recolor_swap_through_a_real_shell(tmp_path):
    import shutil, subprocess
    p = write(tmp_path, "s.px", SWAP)
    script = pathlib.Path(pxart.__file__)
    ran = 0
    for shell in (["zsh", "-f", "-c"], ["bash", "-c"]):
        if not shutil.which(shell[0]):
            continue
        p.write_text(SWAP)
        r = subprocess.run(shell + [f'"{sys.executable}" "{script}" recolor "{p}" \'k<>j\''], capture_output=True,
                           text=True, cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert grids(p)["b"] == ["jjkk"] and not (tmp_path / "j").exists()
        ran += 1
    if not ran:
        pytest.skip("no zsh or bash")


def test_recolor_swap_with_output(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWAP)
    assert run("recolor", f"{p}:a", "k<>j", "-o", tmp_path / "o.px") == 0
    assert p.read_text() == SWAP and grids(tmp_path / "o.px") == {"a": ["jkrg", "kjgr"], "b": ["kkjj"]}


def test_help_documents_recolor_swap_and_order():
    doc = pxart.__doc__
    assert "'a<>b' swaps" in doc and "quote it, since unquoted < and > are shell" in doc
    assert "the key moves of one call apply together" in doc and "A key moved twice is E_BAD_ARG" in doc


# ---------------------------------------------------------------- GAMES-295: palette --extract-to

XBASE = "w #ffffff\nq #0000ff\n\n@variant night\nw #101010\n"
XSRC = ("pxart 1\n# my palette\n@palette base.px\n. transparent\n# black\nk #000000\nq #00ff00\n\n@variant night\n"
        "k #000011\n@variant day\nk #222222\n\n@anim w ms=5\n\n@frame w/0\nkwq.\n@frame w/1\nqwk.\n")


def xsetup(tmp_path):
    write(tmp_path, "base.px", XBASE)
    return write(tmp_path, "src.px", XSRC)


def test_palette_extract_to_writes_the_whole_palette(tmp_path, capsys):
    p = xsetup(tmp_path)
    out = tmp_path / "p.px"
    assert run("palette", p, "--extract-to", out) == 0
    assert out.read_text() == ("pxart 1\nw #ffffff\nq #00ff00\n# black\nk #000000\n\n@variant night\nw #101010\n"
                               "k #000011\n\n@variant day\nk #222222\n")
    assert p.read_text() == XSRC
    assert capsys.readouterr().out == f"wrote {out} (3 key(s), variants night, day)\n"


def test_palette_extract_to_is_a_palette_file(tmp_path, capsys):
    p = xsetup(tmp_path)
    out = tmp_path / "p.px"
    assert run("palette", p, "--extract-to", out) == 0
    capsys.readouterr()
    assert run("check", out) == 0
    assert "palette file, 3 key(s), variants night, day" in capsys.readouterr().out


def test_palette_extract_to_repoint_renders_the_same(tmp_path, capsys):
    p = xsetup(tmp_path)
    before = renders(p)
    out = tmp_path / "p.px"
    assert run("palette", p, "--extract-to", out, "--repoint") == 0
    assert p.read_text() == "pxart 1\n# my palette\n@palette p.px\n\n@anim w ms=5\n\n@frame w/0\nkwq.\n@frame w/1\nqwk.\n"
    assert renders(p) == before
    assert capsys.readouterr().out == f"wrote {out} (3 key(s), variants night, day); wrote {p} (@palette p.px)\n"


def test_palette_extract_to_other_directory_repoints_relative(tmp_path):
    p = xsetup(tmp_path)
    before = renders(p)
    out = tmp_path / "pals" / "deep" / "p.px"
    assert run("palette", p, "--extract-to", out, "--repoint") == 0
    assert pxart.parse(p).palette_refs == ["pals/deep/p.px"] and renders(p) == before


def test_palette_extract_to_from_a_subdirectory_file(tmp_path):
    (tmp_path / "art").mkdir()
    write(tmp_path / "art", "base.px", XBASE)
    p = write(tmp_path / "art", "src.px", XSRC)
    before = renders(p)
    out = tmp_path / "shared" / "p.px"
    assert run("palette", p, "--extract-to", out, "--repoint") == 0
    assert pxart.parse(p).palette_refs == ["../shared/p.px"] and renders(p) == before


def test_palette_extract_to_then_another_sprite_imports_it(tmp_path):
    p = xsetup(tmp_path)
    out = tmp_path / "p.px"
    assert run("palette", p, "--extract-to", out) == 0
    assert run("new", tmp_path / "b.px", "--size", "2x1", "--key", "k", "--palette", out) == 0
    doc = pxart.parse(tmp_path / "b.px")
    assert doc.image(doc.frames[0], "day").getpixel((0, 0)) == pxart.hex2rgba("#222222")


def test_palette_extract_to_without_repoint_leaves_file(tmp_path):
    p = xsetup(tmp_path)
    assert run("palette", p, "--extract-to", tmp_path / "p.px") == 0
    assert p.read_text() == XSRC


def test_palette_extract_to_self_contained_source(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nt transparent\ng #00ff00aa\n\nktg\n")
    before = renders(p)
    assert run("palette", p, "--extract-to", tmp_path / "p.px", "--repoint") == 0
    assert (tmp_path / "p.px").read_text() == "pxart 1\nk #000000\nt transparent\ng #00ff00aa\n"
    assert p.read_text() == "@palette p.px\n\nktg\n" and renders(p) == before


def test_palette_extract_to_from_a_palette_file(tmp_path):
    p = write(tmp_path, "pal.px", "k #000000\n\n@variant x\nk #ffffff\n")
    assert run("palette", p, "--extract-to", tmp_path / "copy.px") == 0
    doc = pxart.parse(tmp_path / "copy.px", palette_only=True)
    assert doc.palette == {"k": (0, 0, 0, 255)} and doc.variants == {"x": {"k": (255, 255, 255, 255)}}


def test_palette_extract_to_overwrites_out(tmp_path):
    p = xsetup(tmp_path)
    out = write(tmp_path, "p.px", "z #123456\n")
    assert run("palette", p, "--extract-to", out) == 0
    assert "z " not in out.read_text()


def test_palette_extract_to_itself_is_bad_arg(tmp_path):
    p = xsetup(tmp_path)
    assert "E_BAD_ARG" in run_err("palette", p, "--extract-to", p) and p.read_text() == XSRC


def test_palette_repoint_needs_extract_to(tmp_path):
    p = xsetup(tmp_path)
    msg = run_err("palette", p, "--repoint")
    assert "E_BAD_ARG" in msg and "--extract-to" in msg and p.read_text() == XSRC


def test_palette_extract_to_notes_a_non_px_name(tmp_path, capsys):
    p = xsetup(tmp_path)
    assert run("palette", p, "--extract-to", tmp_path / "p.pal") == 0
    assert "doesn't end in .px" in capsys.readouterr().out


def test_palette_add_then_extract(tmp_path):
    p = xsetup(tmp_path)
    assert run("palette", p, "--add", "z=#abcdef", "--extract-to", tmp_path / "p.px") == 0
    assert pxart.parse(tmp_path / "p.px", palette_only=True).palette["z"] == pxart.hex2rgba("#abcdef")


def test_help_documents_palette_extract_to():
    doc = pxart.__doc__
    assert "[--extract-to P.px [--repoint]]" in doc and "--repoint" in doc


# ---------------------------------------------------------------- GAMES-295: anim-set --still, new --still

STILLS = ("pxart 1\nk #000000\n@anim w ms=100\n\n@frame w/0\nk\n@frame w/1\nk\n@frame ui/a\nk\n@frame ui/b\nk\n"
          "@frame top\nk\n")


def test_anim_set_still_adds_the_line(tmp_path, capsys):
    p = write(tmp_path, "s.px", STILLS)
    assert run("anim-set", f"{p}:ui", "--still") == 0
    assert p.read_text() == STILLS.replace("@anim w ms=100\n", "@anim w ms=100\n@still ui\n")
    assert capsys.readouterr().out == f"@still ui; wrote {p}\n"
    doc = pxart.parse(p)
    assert doc.still("ui") and not doc.animated("ui") and doc.animated("w")


def test_anim_set_still_is_what_export_and_frames_see(tmp_path, capsys):
    p = write(tmp_path, "s.px", STILLS)
    assert run("anim-set", f"{p}:ui", "--still") == 0
    assert run("export", p, "--aseprite", tmp_path / "s.json") == 0
    tags = json.loads((tmp_path / "s.json").read_text())["meta"]["frameTags"]
    assert [t["name"] for t in tags] == ["w"]
    capsys.readouterr()
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "ui: 2 frame(s) [still]" in out and "  ui/a  1x1  still" in out


def test_anim_set_still_twice_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "s.px", STILLS)
    assert run("anim-set", f"{p}:ui", "--still") == 0
    text = p.read_text()
    capsys.readouterr()
    assert run("anim-set", f"{p}:ui", "--still") == 0
    assert p.read_text() == text and capsys.readouterr().out == f"already @still ui; no change: {p}\n"


def test_anim_set_no_still_removes_the_line(tmp_path, capsys):
    p = write(tmp_path, "s.px", STILLS.replace("@anim w ms=100\n", "@anim w ms=100\n@still ui\n"))
    assert run("anim-set", f"{p}:ui", "--no-still") == 0
    assert p.read_text() == STILLS and capsys.readouterr().out == f"removed @still ui; wrote {p}\n"


def test_anim_set_no_still_of_an_animation_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "s.px", STILLS)
    assert run("anim-set", f"{p}:w", "--no-still") == 0
    assert p.read_text() == STILLS and capsys.readouterr().out == f"not still: w; no change: {p}\n"


def test_anim_set_still_keeps_the_anim_line_with_a_note(tmp_path, capsys):
    p = write(tmp_path, "s.px", STILLS)
    assert run("anim-set", f"{p}:w", "--still") == 0
    assert "@anim w ms=100\n@still w\n" in p.read_text()
    out = capsys.readouterr().out
    assert out == f"note: @anim w stays; its timing is unused while the group is still\n@still w; wrote {p}\n"
    assert run("anim-set", f"{p}:w", "--no-still") == 0
    assert p.read_text() == STILLS


@pytest.mark.parametrize("order", ["flag-first", "flag-last"])
def test_anim_set_still_with_settings(tmp_path, capsys, order):
    p = write(tmp_path, "s.px", STILLS)
    argv = ["--still", "ms=50"] if order == "flag-first" else ["ms=50", "--still"]
    assert run("anim-set", f"{p}:w", *argv) == 0
    assert "@anim w ms=50\n@still w\n" in p.read_text()
    assert capsys.readouterr().out.splitlines()[-1] == f"@anim w ms=50; @still w; wrote {p}"


def test_anim_set_settings_after_dash_o(tmp_path):
    # argparse spends a '*' positional before an option; settings after -o OUT still count.
    p = write(tmp_path, "s.px", STILLS)
    assert run("anim-set", f"{p}:w", "-o", tmp_path / "o.px", "ms=70") == 0
    assert pxart.parse(tmp_path / "o.px").anims["w"]["ms"] == 70 and p.read_text() == STILLS


def test_anim_set_unknown_option_is_still_an_error(tmp_path):
    p = write(tmp_path, "s.px", STILLS)
    assert run("anim-set", f"{p}:w", "--bogus") == 2 and p.read_text() == STILLS


@pytest.mark.parametrize("target", ["{p}", "{p}:*"])
def test_anim_set_still_whole_file(tmp_path, capsys, target):
    p = write(tmp_path, "s.px", STILLS)
    assert run("anim-set", target.format(p=p), "--still") == 0
    assert "@anim w ms=100\n@still *\n" in p.read_text()
    doc = pxart.parse(p)
    assert all(doc.still(f.group) for f in doc.frames)
    assert run("anim-set", target.format(p=p), "--no-still") == 0
    assert p.read_text() == STILLS


def test_anim_set_still_group_under_star_is_already_still(tmp_path, capsys):
    p = write(tmp_path, "s.px", STILLS.replace("@anim w ms=100\n", "@anim w ms=100\n@still *\n"))
    text = p.read_text()
    assert run("anim-set", f"{p}:ui", "--still") == 0
    assert p.read_text() == text and "already still: '@still *' marks every frame" in capsys.readouterr().out


def test_anim_set_no_still_group_under_star_is_bad_arg(tmp_path):
    p = write(tmp_path, "s.px", STILLS.replace("@anim w ms=100\n", "@anim w ms=100\n@still *\n"))
    msg = run_err("anim-set", f"{p}:ui", "--no-still")
    assert "E_BAD_ARG" in msg and f"anim-set {p} --no-still" in msg


@pytest.mark.parametrize("sel, bit", [
    ("ui/a", "'ui/a' is one frame; @still marks its group: anim-set {p}:ui --still"),
    ("top", "'top' is a top-level frame, which is never animated"),
    ("nope", "'nope' is no group; groups: w, ui"),
])
def test_anim_set_still_needs_a_group(tmp_path, sel, bit):
    p = write(tmp_path, "s.px", STILLS)
    msg = run_err("anim-set", f"{p}:{sel}", "--still")
    assert "E_SELECT" in msg and bit.format(p=p) in msg and p.read_text() == STILLS


def test_anim_set_star_without_still_is_select_error(tmp_path):
    p = write(tmp_path, "s.px", STILLS)
    assert "E_SELECT" in run_err("anim-set", f"{p}:*", "ms=5")


def test_anim_set_still_and_no_still_together_is_usage_error(tmp_path):
    p = write(tmp_path, "s.px", STILLS)
    assert run("anim-set", f"{p}:ui", "--still", "--no-still") == 2


def test_anim_set_still_with_output(tmp_path):
    p = write(tmp_path, "s.px", STILLS)
    assert run("anim-set", f"{p}:ui", "--still", "-o", tmp_path / "o.px") == 0
    assert p.read_text() == STILLS and pxart.parse(tmp_path / "o.px").stills == ["ui"]


def test_anim_set_still_after_existing_stills(tmp_path):
    p = write(tmp_path, "s.px", STILLS.replace("@anim w ms=100\n", "@anim w ms=100\n@still ui\n"))
    assert run("anim-set", f"{p}:w", "--still") == 0
    assert "@still ui\n@still w\n" in p.read_text()


def test_new_still_marks_a_new_group(tmp_path, capsys):
    p = write(tmp_path, "s.px", STILLS)
    assert run("new", f"{p}:icons/life", "--size", "1x1", "--still") == 0
    assert capsys.readouterr().out == f"wrote {p} frame icons/life; @still icons\n"
    doc = pxart.parse(p)
    assert doc.stills == ["icons"] and doc.get("icons/life").grid == ["."]


def test_new_still_in_new_file(tmp_path):
    out = tmp_path / "ui.px"
    assert run("new", f"{out}:icons/life", "--size", "2x1", "--still") == 0
    assert out.read_text() == "pxart 1\n\n@still icons\n\n@frame icons/life\n..\n"


def test_new_still_group_already_still_adds_nothing(tmp_path, capsys):
    p = write(tmp_path, "s.px", STILLS.replace("@anim w ms=100\n", "@anim w ms=100\n@still ui\n"))
    assert run("new", f"{p}:ui/c", "--size", "1x1", "--still") == 0
    assert pxart.parse(p).stills == ["ui"] and capsys.readouterr().out == f"wrote {p} frame ui/c\n"


def test_new_still_under_star_adds_nothing(tmp_path):
    p = write(tmp_path, "s.px", STILLS.replace("@anim w ms=100\n", "@anim w ms=100\n@still *\n"))
    assert run("new", f"{p}:x/c", "--size", "1x1", "--still") == 0
    assert pxart.parse(p).stills == ["*"]


def test_new_still_top_level_frame_notes(tmp_path, capsys):
    p = write(tmp_path, "s.px", STILLS)
    assert run("new", f"{p}:badge", "--size", "1x1", "--still") == 0
    out = capsys.readouterr().out
    assert "note: badge is a top-level frame, never animated: no @still line needed" in out
    assert pxart.parse(p).stills == []


def test_new_still_into_an_animation_marks_it(tmp_path):
    p = write(tmp_path, "s.px", STILLS)
    assert run("new", f"{p}:w/2", "--size", "1x1", "--still") == 0
    doc = pxart.parse(p)
    assert doc.stills == ["w"] and not doc.animated("w")


def test_help_documents_still_flags():
    doc = pxart.__doc__
    assert "anim-set FILE:GROUP [ms=N] [direction=D] [repeat=N] [pivot=X,Y] [--still | --no-still]" in doc
    assert "new OUT[:frame] --size WxH [--key K] [--palette P.px] [--still]" in doc


# ---------------------------------------------------------------- GAMES-295: pxart CMD -h

COMMANDS = sorted(pxart.parser()[1].choices)


def cmd_help(capsys, cmd, flag="-h"):
    with pytest.raises(SystemExit) as e:
        pxart.main([cmd, flag])
    assert e.value.code == 0
    return capsys.readouterr().out


def test_every_subparser_has_a_section_in_the_top_level_help():
    # A new command without a section in pxart -h fails here.
    missing = [c for c in COMMANDS if not pxart.reference(c)]
    assert not missing, f"no section in pxart -h for: {missing}"
    assert len(COMMANDS) >= 36


@pytest.mark.parametrize("cmd", COMMANDS)
def test_every_command_help_has_its_section(capsys, cmd):
    out = cmd_help(capsys, cmd)
    ref = pxart.reference(cmd)
    assert out.startswith(f"usage: pxart {cmd} ")
    assert ref in out and ref.startswith(f"  {cmd}")
    assert out.index(ref) < out.index("options:")
    assert "pxart help all has the whole reference, pxart help TOPIC one part of it." in out


@pytest.mark.parametrize("cmd", COMMANDS)
def test_every_command_help_long_flag_too(capsys, cmd):
    assert pxart.reference(cmd) in cmd_help(capsys, cmd, "--help")


def see_also(text):
    """The see-also paragraph of a command's -h, as one line, or None."""
    for part in text.split("\n\n"):
        if part.startswith("See also, in pxart help all: "):
            return " ".join(l.strip() for l in part.splitlines())
    return None


@pytest.mark.parametrize("cmd", COMMANDS)
def test_every_command_help_is_sliced_from_the_top_level_text(cmd):
    # One source of truth: every line of the per-command text (but the labels and the see-also line) is a line of
    # pxart -h.
    doc = pxart.__doc__.splitlines()
    for part in pxart.command_help(cmd).split("\n\n"):
        if part.startswith("See also, in pxart help all: "):
            continue
        for line in part.splitlines():
            if not line or line.endswith("(from pxart help all):") or line == "pxart help all has the whole reference, pxart help TOPIC one part of it.":
                continue
            assert line in doc, (cmd, line)


@pytest.mark.parametrize("cmd", COMMANDS)
def test_every_command_help_names_what_it_refers_to(capsys, cmd):
    out = cmd_help(capsys, cmd)
    refs = pxart.SEE.get(cmd, [])
    also = see_also(out)
    assert (also is None) == (not refs), cmd
    for ref in refs:
        assert f"{ref} ({pxart.GIST[ref]})" in also, (cmd, ref)
    if also:  # in SEE's order
        assert [also.index(f"{r} (") for r in refs] == sorted(also.index(f"{r} (") for r in refs)


@pytest.mark.parametrize("cmd", COMMANDS)
def test_every_command_help_points_at_shared_blocks_rather_than_pasting_them(capsys, cmd):
    out = cmd_help(capsys, cmd)
    for ref in pxart.SEE.get(cmd, []):
        text = pxart.note(ref) if ref in pxart.NOTES else pxart.reference(ref)
        assert text not in out, (cmd, ref)
        assert f"{ref} (from pxart help all):" not in out


@pytest.mark.parametrize("cmd", COMMANDS)
def test_every_command_help_is_short(capsys, cmd):
    # The section, one see-also paragraph and argparse's flags; scene's worked map is the longest.
    out = cmd_help(capsys, cmd)
    body = out.split("options:")[0]
    assert len(body.splitlines()) <= len((pxart.reference(cmd) or "").splitlines()) + 25 \
        + sum(len(pxart.reference(r).splitlines()) + 2 for r in pxart.PASTE.get(cmd, [])), cmd


def test_see_also_lines_are_wrapped(capsys):
    for cmd in COMMANDS:
        for part in pxart.command_help(cmd).split("\n\n"):
            if part.startswith("See also"):
                lines = part.splitlines()
                assert all(len(l) <= 92 for l in lines) and all(l.startswith("  ") for l in lines[1:]), (cmd, part)


def test_see_names_real_commands_and_notes():
    for cmd, refs in pxart.SEE.items():
        assert cmd in COMMANDS, cmd
        for ref in refs:
            assert ref in pxart.NOTES or ref in COMMANDS, (cmd, ref)
            assert pxart.GIST.get(ref), (cmd, ref)
    assert set(pxart.SEE) == set(COMMANDS)  # every command says what it refers to (maybe nothing)
    for cmd, refs in pxart.PASTE.items():
        assert cmd in COMMANDS and all(r in COMMANDS and pxart.reference(r) for r in refs)


def test_every_gist_is_used():
    used = {r for refs in pxart.SEE.values() for r in refs}
    assert set(pxart.GIST) == used


@pytest.mark.parametrize("name", sorted(pxart.NOTES))
def test_every_note_slice_is_found(name):
    text = pxart.note(name)
    assert text and len(text.splitlines()) >= 2, name
    assert text.splitlines()[0].startswith(pxart.NOTES[name][0])


def test_anim_set_help_points_at_the_pivot_notes(capsys):
    out = cmd_help(capsys, "anim-set")
    also = see_also(out)
    assert "FORMAT: pivots and timing (pivot=x,y, direction, repeat, ms)" in also
    assert "FORMAT: still groups (@still GROUP, @still *)" in also and "--still adds '@still GROUP'" in out
    assert "pivot=x,y (optional) on '@frame ID'" not in out


def test_poly_help_explains_its_arguments(capsys):
    out = cmd_help(capsys, "poly")
    assert "A closed polygon through the points in order" in out and "nonzero winding" in out
    assert "DRAWING (FILE[:SEL], KEY, clipping, 'painted N px')" in see_also(out)


def test_rotate_help_has_the_shared_turn_paragraph(capsys):
    out = cmd_help(capsys, "rotate")
    assert "For deriving path edges and corners from one tile." in out


def test_reference_sections_end_at_the_next_command():
    assert "flood FILE" not in pxart.reference("arc") and "rect FILE" not in pxart.reference("line")
    assert pxart.reference("stats").splitlines() == [
        "  stats FILE|DIR...                 size, bbox, color count, colors per frame (a directory and",
        "                                    palette files as for sheet)"]
    assert "ERROR CODES" not in pxart.reference("from-png")
    assert "Centering:" not in pxart.reference("tint")


def test_reference_skips_prose_that_starts_with_a_command_name():
    # '  flood print "painted N px".' (DRAWING's intro) and '  transpose move ...' (FORMAT) aren't sections.
    assert pxart.reference("flood").startswith("  flood FILE[:frame] KEY x,y")
    assert pxart.reference("transpose").startswith("  transpose FILE[:SEL]")
    assert pxart.reference("frames").startswith("  frames FILE[:SEL]")
    assert pxart.reference("nope") is None


def test_scene_help_keeps_the_worked_map_with_its_blank_line(capsys):
    out = cmd_help(capsys, "scene")
    assert "          l lamp.px+hb\n\n          cccccc" in out


def test_plain_runs_do_not_build_the_command_help(monkeypatch, tmp_path):
    # Only -h pays for the slicing.
    calls = []
    monkeypatch.setattr(pxart, "command_help", lambda c: calls.append(c) or "")
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    assert run("stats", p) == 0 and not calls


def test_readme_mentions_command_help():
    readme = (pathlib.Path(pxart.__file__).parent / "README.md").read_text()
    assert "pxart CMD -h" in readme


# ---------------------------------------------------------------- GAMES-295: frames --copy-to

CSRC = ("pxart 1\nk #000000\nw #ffffff\n\n@variant night\nw #888888\n\n@anim walk direction=pingpong ms=120 "
        "pivot=0,1\n@still ui\n\n@frame walk/0\nkw\nk.\n@frame walk/1 ms=200\nwk\n.k\n@frame ui/a\nw\n@frame idle\nkk\n")
CDST = "pxart 1\nk #000000\n\n@variant night\nk #000011\n\n@frame idle\nk\n@frame tail/0\nk\n"


def ids(path):
    return [f.id for f in pxart.parse(path).frames]


def plays(path, fid):
    """How a frame plays: its image (base palette), its duration and pivot. (DST's own variant colors win for keys
    it had, so a variant render may differ: see test_frames_copy_adds_keys_and_their_variant_colors.)"""
    doc = pxart.parse(path)
    f = doc.get(fid)
    return ({None: list(pxart.pixels(doc.image(f)))}, doc.ms(f), doc.pivot(f))


def test_frames_copy_group_new_to_dst(tmp_path, capsys):
    s, d = write(tmp_path, "s.px", CSRC), write(tmp_path, "d.px", CDST)
    assert run("frames", f"{s}:walk", "--copy-to", d) == 0
    # k is black in both, but d's night recolors it and s's night doesn't: a WARNING, and d's night colors those pixels.
    assert capsys.readouterr().out == (
        f"WARNING: FILE ({s}:walk) draws 'k' #000000 in {d}'s variant colors, not s.px's: night #000011 (s.px: "
        "#000000); frames --copy-to --rekey k gives it a key of its own\n"
        f"copied walk/0, walk/1 to {d}; added @anim walk; wrote {d}\n")
    assert ids(d) == ["idle", "tail/0", "walk/0", "walk/1"]
    doc = pxart.parse(d)
    assert doc.anims["walk"] == {"direction": "pingpong", "repeat": None, "ms": 120, "pivot": (0, 1)}
    assert doc.get("walk/0").ms is None and doc.get("walk/1").ms == 200  # the @anim came along: nothing to spell out
    for fid in ("walk/0", "walk/1"):
        assert plays(d, fid) == plays(s, fid)
    assert s.read_text() == CSRC


def test_frames_copy_keeps_timing_against_dst_anim(tmp_path, capsys):
    # DST has its own @anim walk ms=90: copied frames spell out SRC's ms and pivot so they play as they did.
    s = write(tmp_path, "s.px", CSRC)
    d = write(tmp_path, "d.px", CDST.replace("\n@frame idle", "@anim walk ms=90\n\n@frame idle"))
    assert run("frames", f"{s}:walk", "--copy-to", d) == 0
    doc = pxart.parse(d)
    assert doc.anims["walk"] == {"repeat": None, "ms": 90}
    assert (doc.get("walk/0").ms, doc.get("walk/0").pivot) == (120, (0, 1))
    assert (doc.get("walk/1").ms, doc.get("walk/1").pivot) == (200, (0, 1))
    for fid in ("walk/0", "walk/1"):
        assert plays(d, fid) == plays(s, fid)
    assert "note: " + f"{d}'s @anim walk stays (direction and repeat are the group's)" in capsys.readouterr().out


def test_frames_copy_lands_after_its_group_in_dst(tmp_path):
    s = write(tmp_path, "s.px", CSRC)
    d = write(tmp_path, "d.px", CDST.replace("@frame tail/0", "@frame walk/9\nk\n@frame tail/0"))
    assert run("frames", f"{s}:walk", "--copy-to", d) == 0
    assert ids(d) == ["idle", "walk/9", "walk/0", "walk/1", "tail/0"]


@pytest.mark.parametrize("flag, want", [
    ("--after", ["idle", "walk/0", "walk/1", "tail/0"]),
    ("--before", ["walk/0", "walk/1", "idle", "tail/0"]),
])
def test_frames_copy_after_before_a_dst_frame(tmp_path, capsys, flag, want):
    s, d = write(tmp_path, "s.px", CSRC), write(tmp_path, "d.px", CDST)
    assert run("frames", f"{s}:walk", "--copy-to", d, flag, "idle") == 0
    assert ids(d) == want
    assert f"to {d} ({flag[2:]} idle)" in capsys.readouterr().out


def test_frames_copy_by_ids_in_src_order(tmp_path):
    s, d = write(tmp_path, "s.px", CSRC), write(tmp_path, "d.px", CDST.replace("idle", "rest"))
    assert run("frames", s, "--copy-to", d, "idle", "walk/1") == 0
    assert ids(d) == ["rest", "tail/0", "walk/1", "idle"]  # walk/1 first: the order they have in SRC
    assert plays(d, "walk/1") == plays(s, "walk/1") and plays(d, "idle")[0] == plays(s, "idle")[0]


def test_frames_copy_ids_within_selection(tmp_path):
    s, d = write(tmp_path, "s.px", CSRC), write(tmp_path, "d.px", CDST)
    assert run("frames", f"{s}:walk", "--copy-to", d, "walk/1") == 0
    assert ids(d) == ["idle", "tail/0", "walk/1"]
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "ui/a")
    assert "E_SELECT" in msg and "ui/a" in msg and "in 'walk'" in msg


def test_frames_copy_whole_file(tmp_path):
    s = write(tmp_path, "s.px", CSRC)
    d = write(tmp_path, "d.px", "pxart 1\nk #000000\n\n@frame x\nk\n")
    assert run("frames", s, "--copy-to", d) == 0
    assert ids(d) == ["x", "walk/0", "walk/1", "ui/a", "idle"]
    assert pxart.parse(d).stills == ["ui"]


def test_frames_copy_still_group(tmp_path, capsys):
    s, d = write(tmp_path, "s.px", CSRC), write(tmp_path, "d.px", CDST)
    assert run("frames", f"{s}:ui", "--copy-to", d) == 0
    assert pxart.parse(d).stills == ["ui"] and "added @still ui" in capsys.readouterr().out


def test_frames_copy_adds_keys_and_their_variant_colors(tmp_path):
    s, d = write(tmp_path, "s.px", CSRC), write(tmp_path, "d.px", CDST)
    assert run("frames", f"{s}:walk/0", "--copy-to", d) == 0
    doc = pxart.parse(d)
    assert doc.palette["w"] == (255, 255, 255, 255) and doc.variants["night"]["w"] == pxart.hex2rgba("#888888")
    assert doc.variants["night"]["k"] == pxart.hex2rgba("#000011")  # DST's own variant color for k stays


def test_frames_copy_key_conflict_names_all_with_fix(tmp_path):
    import shlex
    s = write(tmp_path, "s.px", CSRC)
    d = write(tmp_path, "d.px", CDST.replace("k #000000\n", "k #000000\nw #eeeeee\n"))
    before = d.read_text()
    msg = run_err("frames", f"{s}:walk", "--copy-to", d)
    assert msg.startswith(f"frames: FILE ({s}:walk): E_KEY_CONFLICT: 1 key of FILE is another color in {d}: 'w' #ffffff "
                          "(#eeeeee there)")
    assert d.read_text() == before
    fix = fix_of(msg)
    assert fix == ["recolor", str(s), "w>a", "-o", str(tmp_path / "rekeyed" / "s.px")]
    src = s.read_text()
    assert run(*fix) == 0 and s.read_text() == src
    assert run("frames", f"{fix[-1]}:walk", "--copy-to", d) == 0
    assert plays(d, "walk/0")[0][None] == plays(s, "walk/0")[0][None]


def test_frames_copy_transparent_key_conflicts_too(tmp_path):
    s = write(tmp_path, "s.px", "k #000000\nz transparent\n@frame a\nkz\n")
    d = write(tmp_path, "d.px", "k #000000\nz #ff0000\n@frame b\nk\n")
    assert "E_KEY_CONFLICT" in run_err("frames", s, "--copy-to", d)


def test_frames_copy_dup_ids(tmp_path):
    s, d = write(tmp_path, "s.px", CSRC), write(tmp_path, "d.px", CDST)
    before = d.read_text()
    msg = run_err("frames", s, "--copy-to", d)
    assert "E_DUP_FRAME" in msg and f"already has idle" in msg and f"frames {d} --rm idle" in msg
    assert d.read_text() == before


def test_frames_copy_missing_dst_suggests_extract(tmp_path):
    s = write(tmp_path, "s.px", CSRC)
    msg = run_err("frames", f"{s}:walk", "--copy-to", tmp_path / "no.px")
    assert "E_FILE" in msg and f"pxart extract {s}:walk -o {tmp_path / 'no.px'}" in msg
    assert not (tmp_path / "no.px").exists()


@pytest.mark.parametrize("extra, bit", [
    (["--rm", "idle"], "give one"),
    (["--move", "idle"], "give one"),
    (["--after", "idle", "--before", "idle"], "not both"),
])
def test_frames_copy_bad_combinations(tmp_path, extra, bit):
    s, d = write(tmp_path, "s.px", CSRC), write(tmp_path, "d.px", CDST)
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, *extra)
    assert "E_BAD_ARG" in msg and bit in msg and d.read_text() == CDST and s.read_text() == CSRC


def test_frames_copy_anchor_not_in_dst(tmp_path):
    s, d = write(tmp_path, "s.px", CSRC), write(tmp_path, "d.px", CDST)
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--after", "walk/0")
    assert "E_SELECT" in msg and f"no such frame in {d}" in msg


def test_frames_copy_dst_selector_is_bad_arg(tmp_path):
    s, d = write(tmp_path, "s.px", CSRC), write(tmp_path, "d.px", CDST)
    assert "E_BAD_ARG" in run_err("frames", f"{s}:walk", "--copy-to", f"{d}:x")


def test_frames_copy_from_unnamed_grid_is_mixed_frames(tmp_path):
    s = write(tmp_path, "s.px", "k #000000\nk\n")
    d = write(tmp_path, "d.px", CDST)
    assert "E_MIXED_FRAMES" in run_err("frames", s, "--copy-to", d)


def test_frames_copy_into_unnamed_grid_names_it(tmp_path, capsys):
    s = write(tmp_path, "s.px", CSRC)
    d = write(tmp_path, "d.px", "k #000000\nk\n")
    assert run("frames", f"{s}:walk", "--copy-to", d) == 0
    assert ids(d) == ["d", "walk/0", "walk/1"] and "is now '@frame d'" in capsys.readouterr().out


def test_frames_copy_into_palette_file(tmp_path):
    s = write(tmp_path, "s.px", CSRC)
    d = write(tmp_path, "d.px", "k #000000\n")
    assert run("frames", f"{s}:idle", "--copy-to", d) == 0
    assert ids(d) == ["idle"] and plays(d, "idle")[0][None] == plays(s, "idle")[0][None]


def test_frames_copy_dst_anim_pivot_note_when_src_has_none(tmp_path, capsys):
    s = write(tmp_path, "s.px", "k #000000\n@frame walk/0\nk\n")
    d = write(tmp_path, "d.px", "k #000000\n@anim walk pivot=0,0\n@frame walk/9\nk\n")
    assert run("frames", s, "--copy-to", d) == 0
    assert "note: walk/0 has no pivot in" in capsys.readouterr().out


def test_frames_copy_puts_back_a_removed_frame_in_place(tmp_path):
    # A frame removed by mistake: copy it back from a copy of the file, after its neighbor, timing and all.
    s = write(tmp_path, "s.px", CSRC)
    backup = write(tmp_path, "backup.px", CSRC)
    assert run("frames", s, "--rm", "walk/1") == 0
    assert run("frames", f"{backup}:walk/1", "--copy-to", s, "--after", "walk/0") == 0
    assert s.read_text() == CSRC


def test_frames_copy_into_the_same_file_is_dup(tmp_path):
    s = write(tmp_path, "s.px", CSRC)
    assert "E_DUP_FRAME" in run_err("frames", f"{s}:walk", "--copy-to", s)


def test_frames_copy_dst_in_other_directory_keeps_its_palette_import(tmp_path):
    (tmp_path / "d").mkdir()
    write(tmp_path / "d", "pal.px", "k #000000\n")
    d = write(tmp_path / "d", "d.px", "@palette pal.px\n@frame x\nk\n")
    s = write(tmp_path, "s.px", CSRC)
    assert run("frames", f"{s}:idle", "--copy-to", d) == 0
    doc = pxart.parse(d)
    assert doc.palette_refs == ["pal.px"] and ids(d) == ["x", "idle"]


def test_help_documents_frames_copy_to():
    doc = pxart.__doc__
    assert "[--copy-to DST [ID...] [--rekey [KEYS]] [--variant-map NAME=V1,V2]\n          [--prefix P | " \
        "--rename GROUP NEWGROUP]]" in doc and "'frames hero.px:walk --copy-to beast.px --after idle/3'" in doc


# ---------------------------------------------------------------- GAMES-295: mask --keep-keys / --drop-keys

MASKK = "W #ffffff\nT #00ff00\nt #008800\nk #000000\n@frame a\nWTtk\nkWTt\n@frame b\nkkkk\nWWWW\n"


@pytest.mark.parametrize("keys", ["W,T,t", "WTt"])
def test_mask_keep_keys(tmp_path, capsys, keys):
    p = write(tmp_path, "m.px", MASKK)
    assert run("mask", p, "--keep-keys", keys) == 0
    assert grids(p) == {"a": ["WTt.", ".WTt"], "b": ["....", "WWWW"]}
    assert capsys.readouterr().out == f"erased 6 px; wrote {p}\n"


def test_mask_drop_keys(tmp_path, capsys):
    p = write(tmp_path, "m.px", MASKK)
    assert run("mask", p, "--drop-keys", "W,k") == 0
    assert grids(p) == {"a": [".Tt.", "..Tt"], "b": ["....", "...."]}
    assert capsys.readouterr().out == f"erased 12 px; wrote {p}\n"


def test_mask_keep_and_drop_split_every_pixel(tmp_path):
    # --keep-keys S and --drop-keys S erase complementary pixels: together they erase each opaque pixel once.
    p, q = write(tmp_path, "p.px", MASKK), write(tmp_path, "q.px", MASKK)
    assert run("mask", p, "--keep-keys", "Tt") == 0 and run("mask", q, "--drop-keys", "Tt") == 0
    for f in pxart.parse(p).frames:
        g = pxart.parse(q).get(f.id).grid
        src = pxart.parse(write(tmp_path, "s.px", MASKK)).get(f.id).grid
        for r1, r2, r0 in zip(f.grid, g, src):
            for c1, c2, c0 in zip(r1, r2, r0):
                assert (c1 == ".") != (c2 == ".") and c0 in (c1, c2)


def test_mask_keep_keys_one_frame(tmp_path):
    p = write(tmp_path, "m.px", MASKK)
    assert run("mask", f"{p}:a", "--keep-keys", "k") == 0
    assert grids(p) == {"a": ["...k", "k..."], "b": ["kkkk", "WWWW"]}


def test_mask_keep_keys_with_shape_is_both(tmp_path):
    # A pixel stays only inside the rectangle AND with a kept key.
    p = write(tmp_path, "m.px", MASKK)
    assert run("mask", f"{p}:a", "--keep", "0,0,2,2", "--keep-keys", "W,k") == 0
    assert grids(p)["a"] == ["W...", "kW.."]


def test_mask_drop_keys_with_inverted_shape(tmp_path):
    p = write(tmp_path, "m.px", MASKK)
    assert run("mask", f"{p}:a", "--keep", "0,0,2,2", "--invert", "--drop-keys", "t") == 0
    assert grids(p)["a"] == ["...k", "..T."]  # the left 2 columns go (inverted shape), then every t


def test_mask_keys_output_elsewhere(tmp_path):
    p = write(tmp_path, "m.px", MASKK)
    assert run("mask", p, "--keep-keys", "W", "-o", tmp_path / "o.px") == 0
    assert p.read_text() == MASKK and grids(tmp_path / "o.px")["b"] == ["....", "WWWW"]


def test_mask_keys_no_change(tmp_path, capsys):
    p = write(tmp_path, "m.px", MASKK)
    assert run("mask", p, "--keep-keys", "WTtk") == 0
    assert capsys.readouterr().out == f"erased 0 px; no change: {p}\n" and p.read_text() == MASKK


def test_mask_keys_transparent_key_counts_as_a_pixel(tmp_path):
    # A key whose color is transparent is still a key: --drop-keys erases it to '.'.
    p = write(tmp_path, "m.px", "k #000000\nz transparent\n\nkz\n")
    assert run("mask", p, "--drop-keys", "z") == 0
    assert pxart.parse(p).frames[0].grid == ["k."]


@pytest.mark.parametrize("argv, code, bit", [
    (["--keep-keys", "q"], "E_SELECT", "keys 'q' aren't in the palette"),
    (["--drop-keys", "qz"], "E_SELECT", "keys 'qz' aren't in the palette"),
    (["--keep-keys", "W,W"], "E_BAD_ARG", "names a key twice"),
    (["--keep-keys", "W,,T"], "E_BAD_ARG", "wants keys like a,b,c"),
    (["--invert", "--keep-keys", "W"], "E_BAD_ARG", "use --drop-keys"),
    (["--dither", "2", "--keep-keys", "W"], "E_BAD_ARG", "--dither N wants N >= 1 and --keep-circle"),
])
def test_mask_keys_errors(tmp_path, argv, code, bit):
    p = write(tmp_path, "m.px", MASKK)
    msg = run_err("mask", p, *argv)
    assert code in msg and bit in msg and p.read_text() == MASKK


def test_mask_keep_and_drop_keys_together_is_usage_error(tmp_path):
    p = write(tmp_path, "m.px", MASKK)
    assert run("mask", p, "--keep-keys", "W", "--drop-keys", "T") == 2 and p.read_text() == MASKK


def test_mask_keys_on_png_is_bad_arg(tmp_path):
    Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(tmp_path / "s.png")
    msg = run_err("mask", tmp_path / "s.png", "--keep-keys", "W")
    assert "E_BAD_ARG" in msg and "a PNG has none" in msg


def test_mask_needs_shape_or_keys_message(tmp_path):
    p = write(tmp_path, "m.px", MASKK)
    msg = run_err("mask", p)
    assert "E_BAD_ARG" in msg and "--keep-keys" in msg


def test_help_documents_mask_keys():
    doc = pxart.__doc__
    assert "[--keep-keys K,K | --drop-keys K,K]" in doc and "--keep-keys W,T,t (or WTt) erases every pixel" in doc


# ---------------------------------------------------------------- GAMES-295: recolor says how many frames

@pytest.mark.parametrize("target, maps, want", [
    ("{p}", ["k=j"], "applied to 3 frames; wrote {p}"),                  # no selector: every frame
    ("{p}:a", ["k=j"], "wrote {p}"),                                     # one frame: no count
    ("{p}", ["k<>j"], "applied to 3 frames; wrote {p}"),
    ("{p}", ["k=#123456"], "wrote {p}"),                                 # a color change moves no pixels
    ("{p}", ["k=#123456", "j=r"], "applied to 3 frames; wrote {p}"),
    ("{p}", ["q=r"], "applied to 3 frames; no change: {p}"),            # q is in no frame: nothing changes
])
def test_recolor_says_applied_to_n_frames(tmp_path, capsys, target, maps, want):
    p = write(tmp_path, "s.px", "k #000000\nj #111111\nr #ff0000\nq #00ff00\n@frame a\nkj\n@frame b\nkr\n"
              "@frame c\njj\n")
    assert run("recolor", target.format(p=p), *maps) == 0
    assert capsys.readouterr().out.splitlines()[-1] == want.format(p=p)


def test_recolor_group_selector_counts_its_frames(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\nj #111111\n@frame w/0\nk\n@frame w/1\nk\n@frame x\nk\n")
    assert run("recolor", f"{p}:w", "k=j") == 0
    assert capsys.readouterr().out == f"applied to 2 frames; wrote {p}\n"
    assert grids(p) == {"w/0": ["j"], "w/1": ["j"], "x": ["k"]}


def test_recolor_single_grid_file_no_count(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\nj #111111\n\nkj\n")
    assert run("recolor", p, "k=j") == 0
    assert capsys.readouterr().out == f"wrote {p}\n"


# ---------------------------------------------------------------- GAMES-295: E_KEY_CONFLICT names every key

def conflict_layers(tmp_path):
    a = write(tmp_path, "a.px", "h #111111\nn #222222\nw #eee0b8\n\nhnw\n")
    b = write(tmp_path, "b.px", "h #aaaaaa\nn #bbbbbb\nw #f6ecd2\nq #123456\n\nhnwq\n")
    c = write(tmp_path, "c.px", "q #654321\n\nq\n")
    return a, b, c


def fix_of(msg):
    """The recolor an E_KEY_CONFLICT line suggests, as argv: the words after its last ': pxart '."""
    import shlex
    return shlex.split(msg.rsplit(": pxart ", 1)[1])


def from_copies(argv, fixes):
    """argv with every input a fix copied (recolor SRC ... -o COPY) read from its copy instead."""
    swap = {f[1]: f[-1] for f in fixes if "-o" in f}
    out = []
    for x in map(str, argv):
        for src, copy in swap.items():
            if x == src or x.startswith(src + ":") or x.startswith(src + "@") or x.startswith(src + "+"):
                x = copy + x[len(src):]
        out.append(x)
    return out


def rekeyed(tmp_path, name):
    return tmp_path / "rekeyed" / name


def test_compose_conflict_new_out_lists_every_key_both_colors_and_origin(tmp_path):
    a, b, c = conflict_layers(tmp_path)
    out = tmp_path / "o.px"
    msg = run_err("compose", "-o", out, "--size", "4x3", f"{a}@0,0", f"{b}@0,1")
    assert msg == (f"compose: layer 2 ({b}): E_KEY_CONFLICT: 3 keys of this layer are other colors in the new {out}: "
                   f"'h' #aaaaaa (#111111 there, from layer 1 ({a})), 'n' #bbbbbb (#222222 there, from layer 1 ({a})), "
                   f"'w' #f6ecd2 (#eee0b8 there, from layer 1 ({a})); to keep both colors (no pixel changes color), "
                   f"add --rekey: compose then gives this layer's keys free ones in the new {out} ('h>a' 'n>b' 'w>c') "
                   f"and leaves {b} as it is. Or give them those keys in a copy and compose from that: pxart recolor {b} "
                   f"'h>a' 'n>b' 'w>c' -o {tmp_path / 'rekeyed' / 'b.px'}")
    assert not out.exists()
    assert " here" not in msg and "recolor one side" not in msg


def test_compose_conflict_every_layer_at_once(tmp_path):
    a, b, c = conflict_layers(tmp_path)
    out = tmp_path / "o.px"
    lines = run_err("compose", "-o", out, "--size", "4x3", f"{a}@0,0", f"{b}@0,1", f"{c}@1,1").splitlines()
    assert len(lines) == 2
    assert lines[0].startswith(f"compose: layer 2 ({b}): E_KEY_CONFLICT: 3 keys")
    assert lines[1] == (f"compose: layer 3 ({c}): E_KEY_CONFLICT: 1 key of this layer is another color in the new "
                        f"{out}: 'q' #654321 (#123456 there, from layer 2 ({b})); to keep both colors (no pixel changes "
                        f"color), add --rekey: compose then gives this layer's keys free ones in the new {out} ('q>d') "
                        f"and leaves {c} as it is. Or give them those keys in a copy and compose from that: pxart "
                        f"recolor {c} 'q>d' -o {tmp_path / 'rekeyed' / 'c.px'}")


def test_compose_conflict_recipe_works(tmp_path, capsys):
    # The fix the message gives, run as it says, lets the compose through, and every layer's colors survive.
    import shlex
    a, b, c = conflict_layers(tmp_path)
    out = tmp_path / "o.px"
    argv = ["compose", "-o", out, "--size", "4x3", f"{a}@0,0", f"{b}@0,1", f"{c}@1,1"]
    fixes = [fix_of(line) for line in run_err(*argv).splitlines()]
    for fix in fixes:
        assert run(*fix) == 0
    assert run(*from_copies(argv, fixes)) == 0
    img = pxart.parse(out).image(pxart.parse(out).frames[0])
    want = {(0, 0): "#111111", (1, 0): "#222222", (2, 0): "#eee0b8", (0, 1): "#aaaaaa", (1, 1): "#654321",
            (2, 1): "#f6ecd2", (3, 1): "#123456"}
    for xy, col in want.items():
        assert img.getpixel(xy) == pxart.hex2rgba(col), xy


def test_compose_conflict_existing_out(tmp_path):
    a, b, c = conflict_layers(tmp_path)
    out = write(tmp_path, "o.px", "w #eee0b8\nh #111111\n@frame x\nwh\n")
    before = out.read_text()
    msg = run_err("compose", "-o", f"{out}:y", f"{b}@0,0")
    assert msg == (f"compose: layer 1 ({b}): E_KEY_CONFLICT: 2 keys of this layer are other colors in {out}: "
                   "'h' #aaaaaa (#111111 there), 'w' #f6ecd2 (#eee0b8 there); to keep both colors (no pixel changes "
                   f"color), add --rekey: compose then gives this layer's keys free ones in {out} ('h>a' 'w>b') and "
                   f"leaves {b} as it is. Or give them those keys in a copy and compose from that: pxart recolor {b} "
                   f"'h>a' 'w>b' -o {tmp_path / 'rekeyed' / 'b.px'}")
    assert out.read_text() == before


def test_compose_conflict_with_key_an_earlier_layer_added_to_existing_out(tmp_path):
    a, b, c = conflict_layers(tmp_path)
    out = write(tmp_path, "o.px", "k #000000\n@frame x\nk\n")
    msg = run_err("compose", "-o", f"{out}:y", "--size", "4x2", f"{b}@0,0", f"{c}@0,1")
    assert f"'q' #654321 (#123456 there, from layer 1 ({b}))" in msg and f"in {out}:" in msg


def test_compose_conflict_free_keys_avoid_every_layer_and_out(tmp_path):
    # 'a' is taken by the OUT, 'b' by layer 1's palette (unused), 'c' by layer 2: the fix picks 'd'.
    a = write(tmp_path, "a.px", "k #000000\nb #0000ff\n\nk\n")
    b = write(tmp_path, "b.px", "k #ffffff\nc #00ff00\n\nk\n")
    out = write(tmp_path, "o.px", "a #ff0000\n@frame x\na\n")
    msg = run_err("compose", "-o", f"{out}:y", "--size", "2x1", f"{a}@0,0", f"{b}@1,0")
    assert fix_of(msg)[:3] == ["recolor", str(b), "k>d"]


def test_compose_conflict_quotes_paths_and_keys_for_the_shell(tmp_path):
    import shlex
    d = tmp_path / "my parts"
    d.mkdir()
    a = write(d, "a.px", "' #000000\n\n'\n")
    b = write(d, "b.px", "' #ffffff\n\n'\n")
    msg = run_err("compose", "-o", tmp_path / "o.px", "--size", "2x1", f"{a}@0,0", f"{b}@1,0")
    fix = fix_of(msg)
    assert fix == ["recolor", str(b), "'>a", "-o", str(tmp_path / "rekeyed" / "b.px")]
    assert run(*fix) == 0 and pxart.parse(fix[-1]).frames[0].grid == ["a"]


def test_compose_conflict_transparent_keys_never_conflict(tmp_path):
    a = write(tmp_path, "a.px", "k #000000\nt transparent\n\nkt\n")
    b = write(tmp_path, "b.px", "t #ffffff\nj #00ff00\n\nj\n")
    assert run("compose", "-o", tmp_path / "o.px", "--size", "3x1", f"{b}@0,0", f"{a}@1,0") == 0


def test_compose_conflict_out_of_free_keys(tmp_path):
    keys = pxart.KEYS
    a = write(tmp_path, "a.px", "".join(f"{k} #000000\n" for k in keys) + "\n" + keys[0] + "\n")
    b = write(tmp_path, "b.px", f"{keys[0]} #ffffff\n\n{keys[0]}\n")
    msg = run_err("compose", "-o", tmp_path / "o.px", "--size", "2x1", f"{a}@0,0", f"{b}@1,0")
    assert "E_KEY_CONFLICT" in msg and "aren't enough free keys" in msg


def test_paste_conflict_lists_every_key_with_fix(tmp_path):
    a, b, c = conflict_layers(tmp_path)
    before = a.read_text()
    msg = run_err("paste", b, "--into", a, "--at", "0,0")
    assert msg == (f"paste: SRC ({b}): E_KEY_CONFLICT: 3 keys of SRC are other colors in {a}: 'h' #aaaaaa (#111111 "
                   "there), 'n' #bbbbbb (#222222 there), 'w' #f6ecd2 (#eee0b8 there); to keep both colors (no pixel "
                   f"changes color), add --rekey: paste then gives SRC's keys free ones in {a} ('h>a' 'n>b' 'w>c') and "
                   f"leaves {b} as it is. Or give them those keys in a copy and paste from that: pxart recolor {b} "
                   f"'h>a' 'n>b' 'w>c' -o {tmp_path / 'rekeyed' / 'b.px'}")
    assert a.read_text() == before


def test_paste_conflict_recipe_works(tmp_path):
    import shlex
    a, b, c = conflict_layers(tmp_path)
    fix = fix_of(run_err("paste", b, "--into", a, "--at", "0,0"))
    assert run(*fix) == 0
    assert run("paste", fix[-1], "--into", a, "--at", "0,0") == 0
    doc = pxart.parse(a)
    assert doc.image(doc.frames[0]).getpixel((2, 0)) == pxart.hex2rgba("#f6ecd2")


def test_palette_add_conflict_says_how_to_change_the_color(tmp_path):
    p = write(tmp_path, "p.px", "w #eee0b8\n\nw\n")
    msg = run_err("palette", p, "--add", "w=#f6ecd2")
    assert "E_KEY_CONFLICT" in msg and f"key 'w' is already #eee0b8 in {p}, not #f6ecd2" in msg
    assert f"'recolor {p} w=#f6ecd2'" in msg and " here" not in msg


def test_put_conflict_lists_every_key(tmp_path, monkeypatch):
    import io
    p = write(tmp_path, "p.px", "a #000000\nb #111111\n@frame x\nab\n")
    monkeypatch.setattr(sys, "stdin", io.StringIO("a #ffffff\nb #eeeeee\nc #00ff00\nabc\n"))
    lines = run_err("put", f"{p}:x").splitlines()
    assert [l.split(": E_")[0] for l in lines] == ["put: stdin:1", "put: stdin:2"]
    assert "'a' #ffffff" in lines[0] and "#000000" in lines[0] and "'b' #eeeeee" in lines[1]


# ---------------------------------------------------------------- GAMES-295: recolor 'a>b' (a new key)

RENAME = ("pxart 1\n# keys\nk #000000\n# the white\nw #ffffff\n\n@variant night\nw #888888\nk #000011\n\n"
          "@frame a\nkw\n@frame b\nww\n")


def renders(path):
    doc = pxart.parse(path)
    names = [None] + sorted(set(doc.variants) | set(doc.shared_variants))
    return {(f.id, n): list(pxart.pixels(doc.image(f, n))) for f in doc.frames for n in names}


def test_recolor_rename_whole_file_renames_the_lines_in_place(tmp_path, capsys):
    p = write(tmp_path, "r.px", RENAME)
    before = renders(p)
    assert run("recolor", p, "w>Z") == 0
    assert p.read_text() == RENAME.replace("w #", "Z #").replace("kw\n", "kZ\n").replace("ww\n", "ZZ\n")
    assert renders(p) == before
    assert capsys.readouterr().out == f"applied to 2 frames; wrote {p}\n"


def test_recolor_rename_part_keeps_the_old_key(tmp_path, capsys):
    p = write(tmp_path, "r.px", RENAME)
    before = renders(p)
    assert run("recolor", f"{p}:a", "w>Z") == 0
    doc = pxart.parse(p)
    assert grids(p) == {"a": ["kZ"], "b": ["ww"]}
    assert doc.palette == {"k": (0, 0, 0, 255), "w": (255, 255, 255, 255), "Z": (255, 255, 255, 255)}
    assert doc.variants["night"]["Z"] == doc.variants["night"]["w"] == pxart.hex2rgba("#888888")
    assert renders(p) == before
    out = capsys.readouterr().out
    assert "note: 'w' stays in the palette: pixels outside the recolor still use it" in out


def test_recolor_rename_in_a_region(tmp_path):
    p = write(tmp_path, "r.px", "k #000000\nw #ffffff\n\nwwww\nwwww\n")
    before = renders(p)
    assert run("recolor", p, "w>Z", "--region", "1,0,2,2") == 0
    assert pxart.parse(p).frames[0].grid == ["wZZw", "wZZw"]
    assert set(pxart.parse(p).palette) == {"k", "w", "Z"}
    assert renders(p) == before


def test_recolor_rename_imported_key_adds_a_local_one(tmp_path):
    write(tmp_path, "pal.px", "w #ffffff\nk #000000\n\n@variant night\nw #101010\n")
    p = write(tmp_path, "r.px", "@palette pal.px\n\nkw\nww\n")
    before = renders(p)
    assert run("recolor", p, "w>Z") == 0
    doc = pxart.parse(p)
    assert doc.palette == {"Z": (255, 255, 255, 255)} and doc.variants == {"night": {"Z": (16, 16, 16, 255)}}
    assert doc.frames[0].grid == ["kZ", "ZZ"]
    assert renders(p) == before


def test_recolor_rename_local_key_with_shared_variant(tmp_path):
    # A local key that an imported variant recolors: the new key gets that variant color as a local variant line.
    write(tmp_path, "pal.px", "q #000000\n\n@variant night\nw #101010\n")
    p = write(tmp_path, "r.px", "@palette pal.px\nw #ffffff\n\nqw\n")
    before = renders(p)
    assert run("recolor", p, "w>Z") == 0
    doc = pxart.parse(p)
    assert doc.palette == {"Z": (255, 255, 255, 255)} and doc.variants == {"night": {"Z": (16, 16, 16, 255)}}
    assert renders(p) == before


def test_recolor_rename_keeps_order_and_comments(tmp_path):
    p = write(tmp_path, "r.px", "# top\na #010101\n# b's line\nb #020202\nc #030303\n\nabc\n")
    assert run("recolor", p, "b>Q") == 0
    assert p.read_text() == "# top\na #010101\n# b's line\nQ #020202\nc #030303\n\naQc\n"


def test_recolor_rename_several_at_once(tmp_path):
    p = write(tmp_path, "r.px", RENAME)
    before = renders(p)
    assert run("recolor", p, "w>Z", "k>Y") == 0
    doc = pxart.parse(p)
    assert list(doc.palette) == ["Y", "Z"] and grids(p) == {"a": ["YZ"], "b": ["ZZ"]}
    assert list(doc.variants["night"]) == ["Z", "Y"]
    assert renders(p) == before


def test_recolor_rename_with_a_move_applies_together(tmp_path):
    # 'w>Z' and k=w: w's pixels become Z, k's become w (not Z): moves apply together. w is still used: it stays.
    p = write(tmp_path, "r.px", "k #000000\nw #ffffff\n\nkw\n")
    assert run("recolor", p, "w>Z", "k=w") == 0
    doc = pxart.parse(p)
    assert doc.frames[0].grid == ["wZ"] and doc.palette["Z"] == (255, 255, 255, 255) and "w" in doc.palette


def test_recolor_rename_with_output_leaves_source(tmp_path):
    p = write(tmp_path, "r.px", RENAME)
    assert run("recolor", p, "w>Z", "-o", tmp_path / "o.px") == 0
    assert p.read_text() == RENAME and grids(tmp_path / "o.px") == {"a": ["kZ"], "b": ["ZZ"]}


@pytest.mark.parametrize("arg, code, bit", [
    ("w>k", "E_BAD_ARG", "'k' is already one (#000000): name a free key ('w>a'; free: a b c), or free 'k' in the "
     "same call: 'k>a' 'w>k'"),
    ("w>w", "E_BAD_ARG", "gives w's pixels the key they have"),
    ("q>Z", "E_SELECT", "key 'q' not in palette"),
    (".>Z", "E_SELECT", "'.' is transparent"),
    ("w>.", "E_BAD_ARG", "'.' is already one"),
    ("w>#", "E_BAD_KEY", "can't be a palette key"),
    ("w>@", "E_BAD_KEY", "can't be a palette key"),
])
def test_recolor_rename_errors(tmp_path, arg, code, bit):
    p = write(tmp_path, "r.px", RENAME)
    msg = run_err("recolor", p, arg)
    assert code in msg and bit in msg and p.read_text() == RENAME


def test_recolor_rename_to_the_same_new_key_twice(tmp_path):
    p = write(tmp_path, "r.px", RENAME)
    msg = run_err("recolor", p, "w>Z", "k>Z")
    assert "E_BAD_ARG" in msg and "'k>Z' and 'w>Z' both give pixels the new key 'Z'" in msg and p.read_text() == RENAME


def test_recolor_rename_and_move_of_one_key(tmp_path):
    p = write(tmp_path, "r.px", RENAME)
    msg = run_err("recolor", p, "w=k", "w>Z")
    assert "E_BAD_ARG" in msg and "moved twice" in msg and p.read_text() == RENAME


def test_recolor_rename_punctuation_keys(tmp_path):
    # '>' and '=' are keys too: '=>Q' renames '=', and 'a=>' still moves a to '>'.
    p = write(tmp_path, "r.px", "= #111111\n> #222222\na #333333\n\n=>a\n")
    assert run("recolor", p, "=>Q") == 0
    assert pxart.parse(p).frames[0].grid == ["Q>a"]
    assert run("recolor", p, "a=>") == 0
    assert pxart.parse(p).frames[0].grid == ["Q>>"]


def test_recolor_rename_through_a_real_shell(tmp_path):
    import shutil, subprocess
    script = pathlib.Path(pxart.__file__)
    ran = 0
    for shell in (["zsh", "-f", "-c"], ["bash", "-c"]):
        if not shutil.which(shell[0]):
            continue
        p = write(tmp_path, "r.px", RENAME)
        r = subprocess.run(shell + [f'"{sys.executable}" "{script}" recolor "{p}" \'w>Z\''], capture_output=True,
                           text=True, cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert grids(p) == {"a": ["kZ"], "b": ["ZZ"]} and not (tmp_path / "Z").exists()
        ran += 1
    if not ran:
        pytest.skip("no zsh or bash")


def test_help_documents_recolor_rename():
    doc = pxart.__doc__
    assert "recolor FILE a=b ['a<>b'] ['a>b'] [c=#rrggbb]" in doc
    assert "'a>b' gives a's pixels a new key b, in a's color" in doc


# ---------------------------------------------------------------- loop G: anim-set (timing)

TIMED = ("pxart 1\nk #000000\n\n@anim walk ms=120\n@anim idle   direction=pingpong  ms=300\n\n@frame walk/0\nk\n"
         "@frame walk/1 ms=200\nk\n@frame idle/0\nk\n@frame idle/1\nk\n@frame run/0\nk\n@frame run/1\nk\n@frame icon\nk\n")


def changed_lines(before, after):
    """(indices changed in place, lines inserted, lines removed) between two texts."""
    import difflib
    a, b = before.splitlines(), after.splitlines()
    ops = [op for op in difflib.SequenceMatcher(None, a, b).get_opcodes() if op[0] != "equal"]
    return ops


def test_anim_set_updates_one_line(tmp_path, capsys):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:walk", "ms=90") == 0
    assert capsys.readouterr().out.endswith(f"\n@anim walk ms=90; wrote {p}\n")
    assert p.read_text() == TIMED.replace("@anim walk ms=120", "@anim walk ms=90")
    assert changed_lines(TIMED, p.read_text()) == [("replace", 3, 4, 3, 4)]


def test_anim_set_adds_a_setting_keeps_the_others(tmp_path):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:walk", "direction=reverse", "repeat=3") == 0
    assert pxart.parse(p).anims["walk"] == {"direction": "reverse", "repeat": 3, "ms": 120}
    assert p.read_text() == TIMED.replace("@anim walk ms=120", "@anim walk direction=reverse repeat=3 ms=120")


def test_anim_set_rewrites_only_the_changed_line_canonically(tmp_path):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:idle", "repeat=2") == 0
    got = p.read_text()
    assert got == TIMED.replace("@anim idle   direction=pingpong  ms=300", "@anim idle direction=pingpong repeat=2 ms=300")
    assert changed_lines(TIMED, got) == [("replace", 4, 5, 4, 5)]


def test_anim_set_new_group_adds_one_line_after_the_others(tmp_path, capsys):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:run", "ms=80", "direction=pingpong") == 0
    assert capsys.readouterr().out == f"@anim run direction=pingpong ms=80; wrote {p}\n"
    got = p.read_text()
    assert got == TIMED.replace("ms=300\n", "ms=300\n@anim run direction=pingpong ms=80\n", 1)
    assert changed_lines(TIMED, got) == [("insert", 5, 5, 5, 6)]


def test_anim_set_first_anim_in_a_file(tmp_path):
    text = "k #000000\n\n@frame a/0\nk\n@frame a/1\nk\n"
    p = write(tmp_path, "a.px", text)
    assert run("anim-set", f"{p}:a", "ms=150") == 0
    assert p.read_text() == "k #000000\n\n@anim a ms=150\n\n@frame a/0\nk\n@frame a/1\nk\n"
    assert pxart.parse(p).anims["a"]["ms"] == 150


def test_anim_set_frame_ms_one_line(tmp_path, capsys):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:walk/0", "ms=250") == 0
    assert capsys.readouterr().out == f"@frame walk/0 ms=250; wrote {p}\n"
    assert p.read_text() == TIMED.replace("@frame walk/0\n", "@frame walk/0 ms=250\n")
    assert changed_lines(TIMED, p.read_text()) == [("replace", 6, 7, 6, 7)]
    doc = pxart.parse(p)
    assert doc.ms(doc.get("walk/0")) == 250 and doc.ms(doc.get("walk/1")) == 200


def test_anim_set_frame_ms_replaces_its_own(tmp_path):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:walk/1", "ms=60") == 0
    assert p.read_text() == TIMED.replace("@frame walk/1 ms=200", "@frame walk/1 ms=60")


def test_anim_set_frame_ms_clear(tmp_path):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:walk/1", "ms=") == 0
    assert p.read_text() == TIMED.replace("@frame walk/1 ms=200", "@frame walk/1")
    doc = pxart.parse(p)
    assert doc.ms(doc.get("walk/1")) == 120  # back to the group's


def test_anim_set_clear_a_group_setting(tmp_path):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:idle", "direction=") == 0
    assert "@anim idle ms=300\n" in p.read_text() and pxart.parse(p).anims["idle"].get("direction") is None
    assert run("anim-set", f"{p}:idle", "ms=") == 0
    assert "@anim idle\n" in p.read_text()
    doc = pxart.parse(p)
    assert doc.ms(doc.get("idle/0")) == pxart.DEFAULT_MS


def test_anim_set_top_level_frame(tmp_path):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:icon", "ms=500") == 0
    assert "@frame icon ms=500\n" in p.read_text()


def test_anim_set_same_values_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "h.px", TIMED)
    before, m = snap(p)
    assert run("anim-set", f"{p}:idle", "ms=300", "direction=pingpong") == 0
    assert capsys.readouterr().out == f"@anim idle direction=pingpong ms=300; no change: {p}\n"
    assert untouched(p, before, m)
    assert run("anim-set", f"{p}:walk/1", "ms=200") == 0
    assert "no change" in capsys.readouterr().out and untouched(p, before, m)


def test_anim_set_group_ms_notes_frames_with_their_own(tmp_path, capsys):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:walk", "ms=100") == 0
    out = capsys.readouterr().out
    assert f"note: walk/1 keeps its own ms=200 (anim-set {p}:walk/1 ms= clears it)" in out
    assert "walk/0 keeps" not in out


def test_anim_set_used_by_anim_and_exports(tmp_path):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:run", "ms=70", "direction=pingpong", "repeat=2") == 0
    assert run("anim-set", f"{p}:run/1", "ms=140") == 0
    assert run("export", f"{p}", "--aseprite", tmp_path / "x.json") == 0
    ase = json.loads((tmp_path / "x.json").read_text())
    by = {f["filename"]: f["duration"] for f in ase["frames"]}
    assert by["run/0"] == 70 and by["run/1"] == 140
    assert {"name": "run", "from": 4, "to": 5, "direction": "pingpong", "color": "#000000ff",
            "repeat": "2"} in ase["meta"]["frameTags"]


@pytest.mark.parametrize("arg", ["ms=0", "ms=-5", "ms=x", "repeat=-1", "repeat=1.5", "direction=sideways", "speed=3",
                                 "ms", "=5"])
def test_anim_set_bad_settings(tmp_path, arg):
    p = write(tmp_path, "h.px", TIMED)
    msg = run_err("anim-set", f"{p}:walk", arg)
    assert "E_BAD_ARG" in msg and p.read_text() == TIMED


def test_anim_set_needs_a_setting(tmp_path):
    p = write(tmp_path, "h.px", TIMED)
    assert "E_BAD_ARG" in run_err("anim-set", f"{p}:walk")


def test_anim_set_needs_a_selector(tmp_path):
    p = write(tmp_path, "h.px", TIMED)
    msg = run_err("anim-set", p, "ms=100")
    assert "E_SELECT" in msg and "FILE:GROUP" in msg and "walk, idle, run" in msg


def test_anim_set_unknown_group(tmp_path):
    p = write(tmp_path, "h.px", TIMED)
    msg = run_err("anim-set", f"{p}:jump", "ms=100")
    assert "E_SELECT" in msg and "neither an animation nor a frame" in msg and p.read_text() == TIMED


def test_anim_set_grandparent_path_is_not_a_group(tmp_path):
    p = write(tmp_path, "h.px", "k #000000\n@frame walk/down/0\nk\n@frame walk/left/0\nk\n")
    msg = run_err("anim-set", f"{p}:walk", "ms=100")
    assert "E_SELECT" in msg and "walk/down, walk/left" in msg


def test_anim_set_frame_rejects_direction_and_repeat(tmp_path):
    p = write(tmp_path, "h.px", TIMED)
    for arg in ("direction=reverse", "repeat=2"):
        msg = run_err("anim-set", f"{p}:walk/0", "ms=90", arg)
        assert "E_BAD_ARG" in msg and "takes only ms=" in msg and f"anim-set {p}:walk" in msg
    assert p.read_text() == TIMED


def test_anim_set_group_and_frame_with_the_same_path_means_the_group(tmp_path):
    p = write(tmp_path, "h.px", "k #000000\n@frame walk\nk\n@frame walk/0\nk\n@frame walk/1\nk\n")
    assert run("anim-set", f"{p}:walk", "ms=90") == 0
    doc = pxart.parse(p)
    assert doc.anims["walk"]["ms"] == 90 and doc.get("walk").ms is None


def test_anim_set_output_file(tmp_path, capsys):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:walk", "ms=90", "-o", tmp_path / "o.px") == 0
    assert p.read_text() == TIMED and (tmp_path / "o.px").read_text() == TIMED.replace("ms=120", "ms=90")


def test_anim_set_keeps_messy_layout(tmp_path):
    p = write(tmp_path, "m.px", MESSY)
    assert run("anim-set", f"{p}:walk/1", "ms=40") == 0
    assert p.read_text() == MESSY.replace("@frame walk/1\n", "@frame walk/1 ms=40\n")


def test_anim_set_crlf_file(tmp_path):
    p = tmp_path / "c.px"
    p.write_bytes(CRLF.encode())
    assert run("anim-set", f"{p}:b", "ms=40") == 0
    assert p.read_bytes() == CRLF.replace("@frame b\r\n", "@frame b ms=40\r\n").encode()


def test_anim_set_missing_file_is_file_error(tmp_path):
    assert "E_FILE" in run_err("anim-set", f"{tmp_path / 'nope.px'}:walk", "ms=90")


def test_anim_set_frames_listing_shows_it(tmp_path, capsys):
    p = write(tmp_path, "h.px", TIMED)
    assert run("anim-set", f"{p}:run", "ms=80") == 0
    capsys.readouterr()
    assert run("frames", f"{p}:run") == 0
    assert "run: 2 frame(s) [ms=80]" in capsys.readouterr().out


def test_help_documents_anim_set():
    doc = pxart.__doc__
    assert "anim-set FILE:GROUP [ms=N] [direction=D] [repeat=N] [pivot=X,Y] [--still | --no-still] [-o OUT]" in doc
    assert "FILE:GROUP/ID (one frame) takes only ms=N" in doc and "Only that one line changes" in doc


# ---------------------------------------------------------------- loop G: extract --inline-palette

BASE_PAL = "# base colors\nk #101010\ng #20a020\nb #2020c0\nu #999999\n\n@variant dusk\nk #000000\ng #104010\nu #555555\n"
MID_PAL = "@palette base.px\nr #c02020\n\n@variant dusk\nr #601010\n\n@variant frost\nb #a0c0ff\n"
HANDOFF = ("pxart 1\n# imports\n@palette pals/mid.px\ng #30ff30\nq #ff00ff\n\n@variant dusk\nq #800080\n\n"
           "@variant rain\nk #333344\n\n@anim cat ms=90\n\n@frame cat/0\nkgr.\nk..b\n@frame cat/1\n.gk.\nq..r\n"
           "@frame dog/0\nuuuu\n")


def handoff(tmp_path):
    (tmp_path / "pals").mkdir(exist_ok=True)
    write(tmp_path / "pals", "base.px", BASE_PAL)
    write(tmp_path / "pals", "mid.px", MID_PAL)
    return write(tmp_path, "folk.px", HANDOFF)


def same_renders(src, out, sel=None):
    """Every selected frame of src renders the same from out, base palette and every variant src knows."""
    names = [None] + sorted(set(src.variants) | set(src.shared_variants))
    n = 0
    for f in src.select(sel):
        for v in names:
            assert pxart.pixels(src.image(f, v)) == pxart.pixels(out.image(out.get(f.id), v)), (f.id, v)
            n += 1
    return n


def test_extract_inline_palette_renders_identically(tmp_path):
    p = handoff(tmp_path)
    out = tmp_path / "hand" / "cat.px"
    assert run("extract", f"{p}:cat", "-o", out, "--inline-palette") == 0
    src, o = pxart.parse(p), pxart.parse(out)
    assert same_renders(src, o, "cat") == 2 * 4  # two frames x (base, dusk, frost, rain)


def test_extract_inline_palette_is_self_contained(tmp_path):
    p = handoff(tmp_path)
    out = tmp_path / "cat.px"
    assert run("extract", f"{p}:cat", "-o", out, "--inline-palette") == 0
    text = out.read_text()
    assert "@palette" not in text
    alone = tmp_path / "elsewhere"
    alone.mkdir()
    (alone / "cat.px").write_text(text)  # no palette files beside it
    o = pxart.parse(alone / "cat.px")
    assert o.palette_refs == [] and same_renders(pxart.parse(p), o, "cat") == 8


def test_extract_inline_palette_exact_text(tmp_path):
    p = handoff(tmp_path)
    out = tmp_path / "cat.px"
    assert run("extract", f"{p}:cat", "-o", out, "--inline-palette") == 0
    assert out.read_text() == (
        "pxart 1\n# imports\n"
        "k #101010\nb #2020c0\nr #c02020\n"      # imported keys the frames use, in import order (base.px first)
        "g #30ff30\nq #ff00ff\n"                  # local keys as they were (g overrides the import)
        "\n@variant dusk\nq #800080\nk #000000\ng #104010\nr #601010\n"
        "\n@variant rain\nk #333344\n"
        "\n@variant frost\nb #a0c0ff\n"
        "\n@anim cat ms=90\n\n@frame cat/0\nkgr.\nk..b\n@frame cat/1\n.gk.\nq..r\n")


def test_extract_inline_palette_only_used_imported_keys(tmp_path):
    p = handoff(tmp_path)
    out = tmp_path / "dog.px"
    assert run("extract", f"{p}:dog", "-o", out, "--inline-palette") == 0
    o = pxart.parse(out)
    assert list(o.palette) == ["k", "u", "g", "q"]  # u used; k set by local @variant rain; g, q local
    assert "b" not in o.palette and "r" not in o.palette
    assert o.variants["dusk"] == {"q": (0x80, 0, 0x80, 255), "k": (0, 0, 0, 255), "g": (0x10, 0x40, 0x10, 255),
                                  "u": (0x55, 0x55, 0x55, 255)}
    assert o.variants["frost"] == {} and "@variant frost\n" in out.read_text()
    assert same_renders(pxart.parse(p), o, "dog") == 4


def test_extract_inline_palette_local_override_wins_over_imported_variant_rule(tmp_path):
    # An imported variant color applies to a locally overridden key too; inlining keeps that.
    p = handoff(tmp_path)
    out = tmp_path / "cat.px"
    assert run("extract", f"{p}:cat/0", "-o", out, "--inline-palette") == 0
    src, o = pxart.parse(p), pxart.parse(out)
    assert src.image(src.get("cat/0"), "dusk").getpixel((1, 0))[:3] == (0x10, 0x40, 0x10)
    assert o.image(o.get("cat/0"), "dusk").getpixel((1, 0))[:3] == (0x10, 0x40, 0x10)
    assert o.image(o.get("cat/0")).getpixel((1, 0))[:3] == (0x30, 0xff, 0x30)


def test_extract_inline_palette_without_variants(tmp_path):
    write(tmp_path, "pal.px", "k #000000\nj #ffffff\nz #123456\n")
    p = write(tmp_path, "s.px", "@palette pal.px\n@frame a\nkj\n@frame b\njj\n")
    out = tmp_path / "o.px"
    assert run("extract", f"{p}:a", "-o", out, "--inline-palette") == 0
    assert out.read_text() == "k #000000\nj #ffffff\n@frame a\nkj\n"
    assert same_renders(pxart.parse(p), pxart.parse(out), "a") == 1


def test_extract_inline_palette_keeps_comments_above_the_import(tmp_path):
    write(tmp_path, "pal.px", "k #000000\n")
    p = write(tmp_path, "s.px", "pxart 1\n\n# shared colors\n@palette pal.px\nj #ffffff\n\n@frame a\nkj\n")
    assert run("extract", p, "-o", tmp_path / "o.px", "--inline-palette") == 0
    assert (tmp_path / "o.px").read_text() == "pxart 1\n\n# shared colors\nk #000000\nj #ffffff\n\n@frame a\nkj\n"


def test_extract_inline_palette_with_dot_line(tmp_path):
    write(tmp_path, "pal.px", "k #000000\n")
    p = write(tmp_path, "s.px", "@palette pal.px\n. transparent\nj #ffffff\n\n.kj\n")
    assert run("extract", p, "-o", tmp_path / "o.px", "--inline-palette") == 0
    assert (tmp_path / "o.px").read_text() == "k #000000\n. transparent\nj #ffffff\n\n.kj\n"


def test_extract_inline_palette_all_keys_imported(tmp_path):
    write(tmp_path, "pal.px", "k #000000\nj #ffffff\n\n@variant night\nk #000022\n")
    p = write(tmp_path, "s.px", "@palette pal.px\n\nkj\n")
    out = tmp_path / "sub" / "o.px"
    assert run("extract", p, "-o", out, "--inline-palette") == 0
    assert out.read_text() == "k #000000\nj #ffffff\n\n@variant night\nk #000022\n\nkj\n"
    assert same_renders(pxart.parse(p), pxart.parse(out)) == 2


def test_extract_inline_palette_no_import_is_plain_extract(tmp_path):
    p = write(tmp_path, "h.px", EDITS)
    assert run("extract", f"{p}:walk", "-o", tmp_path / "a.px") == 0
    assert run("extract", f"{p}:walk", "-o", tmp_path / "b.px", "--inline-palette") == 0
    assert (tmp_path / "a.px").read_text() == (tmp_path / "b.px").read_text()


def test_extract_inline_palette_two_imports(tmp_path):
    write(tmp_path, "a.px", "k #000000\n\n@variant v\nk #010101\n")
    write(tmp_path, "b.px", "j #ffffff\nk #0000ff\n")  # the later import wins for k
    p = write(tmp_path, "s.px", "@palette a.px\n@palette b.px\n\nkj\n")
    assert run("extract", p, "-o", tmp_path / "o.px", "--inline-palette") == 0
    o = pxart.parse(tmp_path / "o.px")
    assert o.palette == {"k": (0, 0, 255, 255), "j": (255, 255, 255, 255)}
    assert same_renders(pxart.parse(p), o) == 2


def test_extract_inline_palette_then_check_strict(tmp_path, capsys):
    p = handoff(tmp_path)
    assert run("extract", f"{p}:cat", "-o", tmp_path / "cat.px", "--inline-palette") == 0
    assert run("check", "--strict", tmp_path / "cat.px") == 0


def test_extract_without_inline_still_repoints(tmp_path):
    p = handoff(tmp_path)
    assert run("extract", f"{p}:cat", "-o", tmp_path / "x" / "cat.px") == 0
    assert pxart.parse(tmp_path / "x" / "cat.px").palette_refs == ["../pals/mid.px"]


def test_help_documents_inline_palette():
    doc = pxart.__doc__
    assert "extract FILE:SEL -o OUT [--inline-palette]" in doc and "makes OUT self-contained" in doc


# ---------------------------------------------------------------- loop G: export FILE:SEL, id order

HARBOR = ("k #000000\nw #0000ff\ns #00ff00\n@anim water ms=450\n@still cobble\n"
          "@frame cobble/a\nkk\nkk\n@frame cobble/b\nkk\nk.\n@frame planks\nk.\n.k\n"
          "@frame water/0\nww\nww\n@frame water/1\nw.\nww\n@frame crate\n.k\nk.\n@frame stall\nssss\nssss\nssss\nssss\n")


def tsj(path):
    return json.loads(pathlib.Path(path).read_text())


def test_export_whole_file_needs_uniform_tiles_and_says_how(tmp_path):
    p = write(tmp_path, "h.px", HARBOR)
    msg = run_err("export", p, "--tiled", tmp_path / "t.tsj")
    assert "E_TILE_SIZE" in msg and "stall 4x4" in msg and f"export {p}:GROUP ... --tiled" in msg


def test_export_tiled_selection(tmp_path):
    p = write(tmp_path, "h.px", HARBOR)
    assert run("export", f"{p}:water", "--tiled", tmp_path / "t.tsj") == 0
    t = tsj(tmp_path / "t.tsj")
    assert t["tilecount"] == 2 and t["tilewidth"] == 2
    assert t["tiles"] == [{"id": 0, "animation": [{"tileid": 0, "duration": 450}, {"tileid": 1, "duration": 450}],
                           "properties": [{"name": "pxart_anim", "type": "string", "value": "water"}]}]


def test_export_several_selectors_add_up_in_file_order(tmp_path):
    p = write(tmp_path, "h.px", HARBOR)
    assert run("export", f"{p}:water", f"{p}:cobble", f"{p}:planks", f"{p}:crate", "--tiled", tmp_path / "t.tsj",
               "--aseprite", tmp_path / "t.json") == 0
    t = tsj(tmp_path / "t.tsj")
    assert t["tilecount"] == 6
    ase = tsj(tmp_path / "t.json")
    # file order is cobble/a cobble/b planks water/0 water/1 crate; top-level planks and crate are one group
    assert [f["filename"] for f in ase["frames"]] == ["cobble/a", "cobble/b", "planks", "crate", "water/0", "water/1"]
    assert t["tiles"][0]["id"] == 4 and [a["tileid"] for a in t["tiles"][0]["animation"]] == [4, 5]
    assert ase["meta"]["frameTags"] == [{"name": "water", "from": 4, "to": 5, "direction": "forward",
                                         "color": "#000000ff"}]


def test_export_selection_sheet_holds_only_the_selection(tmp_path):
    p = write(tmp_path, "h.px", HARBOR)
    assert run("export", f"{p}:cobble", "--aseprite", tmp_path / "c.json") == 0
    sheet = Image.open(tmp_path / "c.png").convert("RGBA")
    assert sheet.size == (4, 2)  # two 2x2 frames, not the 4x4 stall's cells
    assert [f["filename"] for f in tsj(tmp_path / "c.json")["frames"]] == ["cobble/a", "cobble/b"]


def test_export_selection_frames_dir(tmp_path):
    p = write(tmp_path, "h.px", HARBOR)
    assert run("export", f"{p}:water/1", f"{p}:stall", "--frames", tmp_path / "f") == 0
    got = sorted(str(q.relative_to(tmp_path / "f")) for q in (tmp_path / "f").rglob("*.png"))
    assert got == ["stall.png", "water/1.png"]


def test_export_partial_group_tag_covers_the_selected_frames(tmp_path):
    p = write(tmp_path, "m.px", "k #000000\n@frame w/0\nk\n@frame w/1\nk\n@frame w/2\nk\n")
    assert run("export", f"{p}:w/1", f"{p}:w/2", "--aseprite", tmp_path / "x.json", "--tiled", tmp_path / "x.tsj") == 0
    assert tsj(tmp_path / "x.json")["meta"]["frameTags"][0]["from"] == 0
    assert tsj(tmp_path / "x.json")["meta"]["frameTags"][0]["to"] == 1
    assert [a["tileid"] for a in tsj(tmp_path / "x.tsj")["tiles"][0]["animation"]] == [0, 1]


def test_export_single_frame_of_a_group_has_no_tiled_animation(tmp_path):
    p = write(tmp_path, "h.px", HARBOR)
    assert run("export", f"{p}:water/0", "--tiled", tmp_path / "t.tsj") == 0
    assert tsj(tmp_path / "t.tsj")["tiles"] == [] and tsj(tmp_path / "t.tsj")["tilecount"] == 1


def test_export_overlapping_selectors_count_once(tmp_path):
    p = write(tmp_path, "h.px", HARBOR)
    assert run("export", f"{p}:water", f"{p}:water/1", "--tiled", tmp_path / "t.tsj") == 0
    assert tsj(tmp_path / "t.tsj")["tilecount"] == 2


def test_export_plain_file_among_selectors_means_everything(tmp_path):
    p = write(tmp_path, "h.px", HARBOR)
    assert run("export", p, f"{p}:water", "--aseprite", tmp_path / "x.json") == 0
    assert len(tsj(tmp_path / "x.json")["frames"]) == 7


def test_export_two_files_is_bad_arg(tmp_path):
    p = write(tmp_path, "h.px", HARBOR)
    q = write(tmp_path, "m.px", MULTI)
    msg = run_err("export", p, q, "--frames", tmp_path / "f")
    assert "E_BAD_ARG" in msg and "export reads one file" in msg


def test_export_unknown_selection_is_select_error(tmp_path):
    p = write(tmp_path, "h.px", HARBOR)
    assert "E_SELECT" in run_err("export", f"{p}:nope", "--frames", tmp_path / "f")
    assert not (tmp_path / "f").exists()


def test_export_selector_variant_suffix(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    assert run("export", f"{p}:idle%night", "--frames", tmp_path / "f") == 0
    assert Image.open(tmp_path / "f" / "idle.png").convert("RGBA").getpixel((1, 0))[:3] == (0x25, 0x95, 0x6A)
    assert "E_BAD_ARG" in run_err("export", f"{p}:idle%night", f"{p}:walk%day", "--frames", tmp_path / "g")


def test_export_without_selector_unchanged(tmp_path):
    p = write(tmp_path, "m.px", MULTI.replace("kggk\nkggk\n", ".kk.\nkggk\n"))
    assert run("export", p, "--aseprite", tmp_path / "a.json", "--tiled", tmp_path / "a.tsj") == 0
    assert run("export", f"{p}:walk", f"{p}:idle", "--aseprite", tmp_path / "b.json", "--tiled", tmp_path / "b.tsj") == 0
    a, b = tsj(tmp_path / "a.json"), tsj(tmp_path / "b.json")
    a["meta"]["image"] = b["meta"]["image"] = "x"
    assert a == b
    a, b = tsj(tmp_path / "a.tsj"), tsj(tmp_path / "b.tsj")
    a["image"] = b["image"] = a["name"] = b["name"] = "x"
    assert a == b


@pytest.mark.parametrize("order,want", [
    (["a/0", "a/1", "b/0", "b/1"], ["a/0", "a/1", "b/0", "b/1"]),                  # contiguous: file order
    (["b/0", "b/1", "a/0", "a/1"], ["b/0", "b/1", "a/0", "a/1"]),
    (["a/0", "b/0", "a/1"], ["a/0", "a/1", "b/0"]),                                # a/1 moves up to its group
    (["icon", "walk/0", "walk/1", "badge"], ["icon", "badge", "walk/0", "walk/1"]),  # top-level frames: one group
    (["walk/0", "icon", "walk/1"], ["walk/0", "walk/1", "icon"]),
    (["icon", "badge", "walk/0", "walk/1"], ["icon", "badge", "walk/0", "walk/1"]),
    (["x/a/0", "x/b/0", "x/a/1"], ["x/a/0", "x/a/1", "x/b/0"]),                    # the group is the parent path
])
def test_export_id_order(tmp_path, order, want):
    p = write(tmp_path, "o.px", "k #000000\n" + "".join(f"@frame {i}\nk\n" for i in order))
    assert run("export", p, "--aseprite", tmp_path / "x.json", "--tiled", tmp_path / "x.tsj") == 0
    assert [f["filename"] for f in tsj(tmp_path / "x.json")["frames"]] == want
    sheet, cols = Image.open(tmp_path / "x.png"), tsj(tmp_path / "x.tsj")["columns"]
    for n, f in enumerate(tsj(tmp_path / "x.json")["frames"]):  # Tiled id n sits where Aseprite frame n does
        assert (f["frame"]["x"], f["frame"]["y"]) == ((n % cols), (n // cols))
    assert sheet.size == (cols, -(-len(order) // cols))


def test_help_documents_export_selection_and_id_order():
    doc = pxart.__doc__
    assert "export FILE[:SEL]... [--frames DIR]" in doc and "several selectors of one file add up" in doc
    assert "each animation group contiguous" in doc and "a/0 b/0 a/1 -> a/0=0 a/1=1 b/0=2" in doc
    assert "gets ids in file order" in doc


# ---------------------------------------------------------------- loop H: put (a frame's grid from stdin)

import io  # noqa: E402

PUT = BLANK_FRAMES  # walk/0, walk/1, idle, with blank lines between frames


def put(monkeypatch, text, *argv):
    """Run 'pxart put ...' with `text` on stdin; returns the exit code."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    return run("put", *argv)


def put_err(monkeypatch, text, *argv):
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    return run_err("put", *argv)


def diff_lines(before, after):
    import difflib
    return [l for l in difflib.unified_diff(before.splitlines(), after.splitlines(), n=0, lineterm="")
            if l[:1] in "+-" and not l.startswith(("+++", "---"))]


def touched_lines(before, after):
    """Indexes of `before`'s lines that a diff to `after` replaces, deletes or inserts at."""
    import difflib
    sm = difflib.SequenceMatcher(None, before.splitlines(), after.splitlines(), autojunk=False)
    return {i for op, i1, i2, _, _ in sm.get_opcodes() if op != "equal" for i in range(i1, max(i2, i1 + 1))}


def test_put_replaces_one_frame(tmp_path, monkeypatch, capsys):
    p = write(tmp_path, "a.px", PUT)
    assert put(monkeypatch, "kggk\n.kk.\n", f"{p}:walk/1") == 0
    assert capsys.readouterr().out == f"wrote {p} frame walk/1\n"
    doc = pxart.parse(p)
    assert doc.get("walk/1").grid == ["kggk", ".kk."]
    assert doc.get("walk/0").grid == [".kk.", "kggk"] and doc.get("idle").grid == ["kkkk"]


def test_put_diff_is_only_that_frames_lines(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    assert put(monkeypatch, "kggk\n.kk.\n", f"{p}:walk/1") == 0
    assert diff_lines(PUT, p.read_text()) == ["+kggk", "-kgkk"]  # .kk. stays, now the second row
    before = PUT.splitlines()
    rows = {i for i, l in enumerate(before) if i > before.index("@frame walk/1")} - \
        {i for i, l in enumerate(before) if i >= before.index("@frame idle") - 1}
    assert touched_lines(PUT, p.read_text()) <= rows
    assert p.read_text() == PUT.replace("@frame walk/1\n.kk.\nkgkk\n", "@frame walk/1\nkggk\n.kk.\n")


def test_put_one_changed_row_is_one_changed_line(tmp_path, monkeypatch):
    for layout in (BLANK_FRAMES, TIGHT_FRAMES, MESSY):
        p = write(tmp_path, "a.px", layout)
        doc = pxart.parse(p)
        grid = list(doc.get("walk/1").grid)
        grid[-1] = grid[-1].replace(".", "k", 1) if "." in grid[-1] else grid[-1].replace("k", ".", 1)
        assert put(monkeypatch, "\n".join(grid) + "\n", f"{p}:walk/1") == 0
        before, after = layout.splitlines(), p.read_text().splitlines()
        assert len(before) == len(after)
        assert len([i for i, (x, y) in enumerate(zip(before, after)) if x != y]) == 1


def test_put_keeps_comments_spacing_and_odd_spelling(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", MESSY)
    assert put(monkeypatch, ".kk.\nkggk\nkggk\n", f"{p}:walk/0") == 0
    got = p.read_text()
    assert got == MESSY  # same grid as the file's: indented '  .kk.' and the mid-grid comment kept


def test_put_same_grid_is_no_change(tmp_path, monkeypatch, capsys):
    p = write(tmp_path, "a.px", PUT)
    before, m = snap(p)
    assert put(monkeypatch, ".kk.\nkgkk\n", f"{p}:walk/1") == 0
    assert capsys.readouterr().out == f"no change: {p} frame walk/1\n" and untouched(p, before, m)


def test_put_crlf_file_keeps_crlf(tmp_path, monkeypatch):
    p = tmp_path / "a.px"
    p.write_bytes(CRLF.encode())
    assert put(monkeypatch, "k\n", f"{p}:b") == 0
    assert p.read_bytes() == CRLF.encode()
    assert put(monkeypatch, ".\n", f"{p}:b") == 0
    assert p.read_bytes() == CRLF.replace("@frame b\r\nk\r\n", "@frame b\r\n.\r\n").encode()


def test_put_rows_may_change_size_with_a_note(tmp_path, monkeypatch, capsys):
    p = write(tmp_path, "a.px", PUT)
    assert put(monkeypatch, "kgk\nkgk\nkgk\n", f"{p}:idle") == 0
    out = capsys.readouterr().out
    assert "note: idle is now 3x3 (was 4x1)" in out
    assert pxart.parse(p).get("idle").grid == ["kgk"] * 3


def test_put_same_size_has_no_note(tmp_path, monkeypatch, capsys):
    p = write(tmp_path, "a.px", PUT)
    assert put(monkeypatch, "gggg\n", f"{p}:idle") == 0
    assert "note:" not in capsys.readouterr().out


def test_put_new_frame_lands_after_its_animation(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    assert put(monkeypatch, "kkkk\n", f"{p}:walk/2") == 0
    assert ids(p) == ["walk/0", "walk/1", "walk/2", "idle"]
    assert p.read_text() == PUT.replace("\n@frame idle", "\n@frame walk/2\nkkkk\n\n@frame idle")


def test_put_new_frame_in_new_group_goes_at_the_end(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", TIGHT_FRAMES)
    assert put(monkeypatch, "kk\n", f"{p}:run/0") == 0
    assert ids(p) == ["walk/0", "walk/1", "idle", "run/0"]
    assert p.read_text() == TIGHT_FRAMES + "@frame run/0\nkk\n"


def test_put_new_frame_matches_new_and_compose_placement(tmp_path, monkeypatch):
    for target in ("walk/2", "idle/1", "shoot/1", "zzz", "run/0", "walk/down/0"):
        a, b = write(tmp_path, "a.px", GROUPS), write(tmp_path, "b.px", GROUPS)
        assert put(monkeypatch, "k\n", f"{a}:{target}") == 0
        assert run("new", f"{b}:{target}", "--size", "1x1", "--key", "k") == 0
        assert ids(a) == ids(b)


def test_put_creates_a_new_file(tmp_path, monkeypatch):
    p = tmp_path / "n.px"
    assert put(monkeypatch, "k #102030\n.k\nk.\n", f"{p}:idle/0") == 0
    doc = pxart.parse(p)
    assert [f.id for f in doc.frames] == ["idle/0"] and doc.get("idle/0").grid == [".k", "k."]
    assert doc.palette == {"k": (0x10, 0x20, 0x30, 255)}


def test_put_plain_file_replaces_its_one_grid(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", LEGACY)
    assert put(monkeypatch, "gggg\nkkkk\ngggg\n", p) == 0
    assert p.read_text() == LEGACY.replace(".kk.\nkggk\n.kk.\n", "gggg\nkkkk\ngggg\n")


def test_put_plain_file_with_named_frames_needs_a_frame(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    before = p.read_text()
    msg = put_err(monkeypatch, "kk\n", p)
    assert "E_SELECT" in msg and "say which one" in msg and p.read_text() == before


def test_put_new_plain_file(tmp_path, monkeypatch):
    p = tmp_path / "n.px"
    assert put(monkeypatch, "k #000000\nkk\n", p) == 0
    assert p.read_text() == "pxart 1\nk #000000\n\nkk\n"


def test_put_group_selector_is_select_error(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    before = p.read_text()
    msg = put_err(monkeypatch, "kkkk\n", f"{p}:walk")
    assert "E_SELECT" in msg and "'walk' is a group (walk/0, walk/1)" in msg and f"put {p}:walk/0" in msg
    assert p.read_text() == before


def test_put_stdin_palette_adds_used_keys(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    assert put(monkeypatch, "r #ff0000\nz #00ff00\nkrrk\n", f"{p}:idle") == 0
    doc = pxart.parse(p)
    assert doc.palette["r"] == (255, 0, 0, 255) and "z" not in doc.palette  # z is unused, like compose
    assert doc.get("idle").grid == ["krrk"]
    assert p.read_text() == PUT.replace("g #43e1b3\n", "g #43e1b3\nr #ff0000\n").replace("kkkk\n", "krrk\n")


def test_put_stdin_palette_same_color_is_fine(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    assert put(monkeypatch, "k #3f2631\ng #43e1b3\n\ngkgk\n", f"{p}:idle") == 0
    assert diff_lines(PUT, p.read_text()) == ["-kkkk", "+gkgk"]


def test_put_stdin_palette_other_color_is_key_conflict(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    before, m = snap(p)
    msg = put_err(monkeypatch, "# mine\nk #ffffff\nkkkk\n", f"{p}:idle")
    assert "stdin:2: E_KEY_CONFLICT" in msg and "#ffffff" in msg and "#3f2631" in msg
    assert untouched(p, before, m)


def test_put_stdin_key_conflict_with_shared_palette(tmp_path, monkeypatch):
    write(tmp_path, "base.px", "k #000000\n")
    p = write(tmp_path, "a.px", "@palette base.px\n@frame a\nk\n")
    before = p.read_text()
    assert "E_KEY_CONFLICT" in put_err(monkeypatch, "k #111111\nk\n", f"{p}:a")
    assert p.read_text() == before
    assert put(monkeypatch, "k #000000\nkk\n", f"{p}:a") == 0  # the imported color: nothing added
    assert p.read_text() == "@palette base.px\n@frame a\nkk\n"


def test_put_uses_shared_palette_keys(tmp_path, monkeypatch):
    write(tmp_path, "base.px", "k #000000\n")
    p = write(tmp_path, "a.px", "@palette base.px\n@frame a\nk\n")
    assert put(monkeypatch, "k.k\n", f"{p}:a") == 0
    assert pxart.parse(p).get("a").grid == ["k.k"]


def test_put_unknown_key_is_located_at_stdin(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    before, m = snap(p)
    msg = put_err(monkeypatch, "kkkk\nkqkk\n", f"{p}:idle")
    assert "stdin:2: E_UNKNOWN_KEY (row 1, x=[1]): keys 'q'" in msg and untouched(p, before, m)


def test_put_row_width_is_located_at_stdin(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    before, m = snap(p)
    msg = put_err(monkeypatch, "kkkk\nkkkk\nkkk\n", f"{p}:idle")
    assert "stdin:3: E_ROW_WIDTH (row 2)" in msg and untouched(p, before, m)


def test_put_reports_every_stdin_error_at_once(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    msg = put_err(monkeypatch, "z #12345\nkkkk\nkk\nkqkk\n", f"{p}:idle")
    assert "stdin:1: E_BAD_COLOR" in msg and "stdin:3: E_ROW_WIDTH" in msg and "stdin:4: E_UNKNOWN_KEY" in msg


@pytest.mark.parametrize("text,code", [
    ("kk k\n", "E_BAD_ROW"),
    ("kk\nk #000000\n", "E_PALETTE_AFTER_GRID"),
    ("", "E_NO_FRAMES"),
    ("# only a comment\n", "E_NO_FRAMES"),
    (". #ffffff\nk\n", "E_DOT_RESERVED"),
    ("k #000000\nk #000000\nk\n", "E_DUP_KEY"),
    ("@frame x\nkk\n", "E_BAD_ARG"),
    ("@anim walk ms=90\nkk\n", "E_BAD_ARG"),
    ("@variant night\nk #000000\n\nkk\n", "E_BAD_ARG"),
    ("@future\nkk\n", "E_BAD_ARG"),
])
def test_put_stdin_errors_write_nothing(tmp_path, monkeypatch, text, code):
    p = write(tmp_path, "a.px", PUT)
    before, m = snap(p)
    assert code in put_err(monkeypatch, text, f"{p}:idle")
    assert untouched(p, before, m)


def test_put_stdin_errors_on_a_new_file_create_nothing(tmp_path, monkeypatch):
    p = tmp_path / "n.px"
    assert "E_UNKNOWN_KEY" in put_err(monkeypatch, "kq\n", f"{p}:a")
    assert not p.exists()


def test_put_from_a_terminal_is_bad_arg(tmp_path, monkeypatch):
    class Tty(io.StringIO):
        def isatty(self):
            return True
    p = write(tmp_path, "a.px", PUT)
    monkeypatch.setattr(sys, "stdin", Tty("kk\n"))
    msg = run_err("put", f"{p}:idle")
    assert "E_BAD_ARG" in msg and "put reads the grid from stdin" in msg and f"< grid.txt" in msg


def test_put_output_file_gets_the_whole_file(tmp_path, monkeypatch, capsys):
    p = write(tmp_path, "a.px", PUT)
    out = tmp_path / "o.px"
    assert put(monkeypatch, "gggg\n", f"{p}:idle", "-o", out) == 0
    assert p.read_text() == PUT
    assert out.read_text() == PUT.replace("kkkk\n", "gggg\n")
    assert f"note: {out} gets all of {p} with idle replaced" in capsys.readouterr().out


def test_put_transparent_stdin_key(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    assert put(monkeypatch, "t transparent\nktkk\n", f"{p}:idle") == 0
    doc = pxart.parse(p)
    assert doc.palette["t"] == pxart.CLEAR and doc.get("idle").grid == ["ktkk"]


def test_put_dot_transparent_line_is_accepted(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    assert put(monkeypatch, ". transparent\nk..k\n", f"{p}:idle") == 0
    assert diff_lines(PUT, p.read_text()) == ["-kkkk", "+k..k"]


def test_put_variant_still_renders(tmp_path, monkeypatch):
    p = write(tmp_path, "m.px", MULTI)
    assert put(monkeypatch, "gggg\ngggg\n", f"{p}:idle") == 0
    doc = pxart.parse(p)
    assert doc.image(doc.get("idle"), "night").getpixel((0, 0))[:3] == (0x25, 0x95, 0x6A)


def test_put_with_blank_lines_and_comments_on_stdin(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    assert put(monkeypatch, "# new idle\n\nr #ff0000\n\nrrrr\n", f"{p}:idle") == 0
    assert pxart.parse(p).get("idle").grid == ["rrrr"] and "# new idle" not in p.read_text()


def test_put_indented_stdin_rows(tmp_path, monkeypatch):
    p = write(tmp_path, "a.px", PUT)
    assert put(monkeypatch, "  gggg\n  gggg\n", f"{p}:idle") == 0
    assert pxart.parse(p).get("idle").grid == ["gggg", "gggg"]


def test_put_notes_non_px_output(tmp_path, monkeypatch, capsys):
    p = tmp_path / "herok"
    assert put(monkeypatch, "k #000000\nk\n", p) == 0
    assert "doesn't end in .px" in capsys.readouterr().out


def test_help_documents_put():
    doc = pxart.__doc__
    assert "put FILE[:frame] [-o OUT] < grid.txt" in doc and "nothing is written on an error" in doc
    assert "Only that frame's lines change" in doc


# ---------------------------------------------------------------- loop H: shift leaves '.', or --fill KEY

FLOOR = "k #000000\nf #806040\nffff\nfkkf\nfkkf\nffff\n"


def test_shift_vacated_pixels_become_dot(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nkk..\nkk..\n")
    assert run("shift", p, "--dx", "2") == 0
    assert pxart.parse(p).frames[0].grid == ["..kk", "..kk"]


def test_shift_region_vacated_pixels_become_dot(tmp_path):
    p = write(tmp_path, "a.px", FLOOR)
    assert run("shift", p, "--dx", "1", "--region", "1,1,2,2") == 0
    assert pxart.parse(p).frames[0].grid == ["ffff", "f.kk", "f.kk", "ffff"]


def test_shift_fill_paints_vacated_region_pixels(tmp_path):
    p = write(tmp_path, "a.px", FLOOR)
    assert run("shift", p, "--dx", "1", "--region", "1,1,2,2", "--fill", "f") == 0
    assert pxart.parse(p).frames[0].grid == ["ffff", "ffkk", "ffkk", "ffff"]


def test_shift_fill_whole_frame(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nf #806040\nkk..\nkk..\n")
    assert run("shift", p, "--dx", "1", "--dy", "1", "--fill", "f") == 0
    assert pxart.parse(p).frames[0].grid == ["ffff", "fkk."]


def test_shift_fill_leaves_transparent_moved_pixels_transparent(tmp_path):
    # Pixels under the moved block aren't vacated: a '.' moved there stays '.', it isn't filled.
    p = write(tmp_path, "a.px", "k #000000\nf #806040\nk.k.\n")
    assert run("shift", p, "--dx", "1", "--fill", "f") == 0
    assert pxart.parse(p).frames[0].grid == ["fk.k"]


def test_shift_fill_dot_is_the_default(tmp_path):
    a, b = write(tmp_path, "a.px", FLOOR), write(tmp_path, "b.px", FLOOR)
    assert run("shift", a, "--dx", "-1", "--dy", "1", "--region", "1,1,2,2") == 0
    assert run("shift", b, "--dx", "-1", "--dy", "1", "--region", "1,1,2,2", "--fill", ".") == 0
    assert a.read_text() == b.read_text()


@pytest.mark.parametrize("dx,dy", [(1, 0), (-1, 0), (0, 1), (0, -1), (2, 2), (-3, 1), (5, 0), (0, 0)])
def test_shift_fill_only_touches_vacated_pixels(tmp_path, dx, dy):
    n = 6
    text = "k #000000\nf #806040\n" + "".join("".join("k" if (x + y) % 2 else "." for x in range(n)) + "\n"
                                              for y in range(n))
    plain, filled = write(tmp_path, "p.px", text), write(tmp_path, "q.px", text)
    args = ["--dx", str(dx), "--dy", str(dy), "--region", "1,1,4,4"]
    assert run("shift", plain, *args) == 0
    assert run("shift", filled, *args, "--fill", "f") == 0
    gp, gf = pxart.parse(plain).frames[0].grid, pxart.parse(filled).frames[0].grid
    for y in range(n):
        for x in range(n):
            vacated = 1 <= x < 5 and 1 <= y < 5 and not (1 + dx <= x < 5 + dx and 1 + dy <= y < 5 + dy)
            assert gf[y][x] == ("f" if vacated else gp[y][x]), (x, y)


def test_shift_fill_unknown_key_is_select_error(tmp_path):
    p = write(tmp_path, "a.px", FLOOR)
    before = p.read_text()
    msg = run_err("shift", p, "--dx", "1", "--fill", "q")
    assert "E_SELECT" in msg and "--fill key 'q'" in msg and p.read_text() == before


def test_shift_fill_with_wrap_is_bad_arg(tmp_path):
    p = write(tmp_path, "a.px", FLOOR)
    before = p.read_text()
    msg = run_err("shift", p, "--dx", "1", "--wrap", "--fill", "f")
    assert "E_BAD_ARG" in msg and "--wrap leaves none" in msg and p.read_text() == before


def test_shift_fill_one_frame_leaves_others(tmp_path):
    p = write(tmp_path, "m.px", "k #000000\nf #806040\n@frame a\nk.\n@frame b\nk.\n")
    assert run("shift", f"{p}:a", "--dx", "1", "--fill", "f") == 0
    doc = pxart.parse(p)
    assert doc.get("a").grid == ["fk"] and doc.get("b").grid == ["k."]


def test_help_documents_shift_vacated_and_fill():
    doc = pxart.__doc__
    assert "[--wrap] [--fill KEY]" in doc and "(vacated) become '.', or KEY" in doc


# ---------------------------------------------------------------- loop H: mask takes several shapes (union)

def mask_grid(tmp_path, n, *args, name="u.px"):
    p = square(tmp_path, n, name)
    assert run("mask", p, *args) == 0
    return pxart.parse(p).frames[0].grid


def kept(grid):
    return {(x, y) for y, row in enumerate(grid) for x, ch in enumerate(row) if ch == "k"}


def test_mask_two_rects_union(tmp_path):
    g = mask_grid(tmp_path, 6, "--keep", "0,0,2,2", "--keep", "4,4,2,2")
    assert g == ["kk....", "kk....", "......", "......", "....kk", "....kk"]


def test_mask_two_circles_hard_edge_union(tmp_path):
    g = mask_grid(tmp_path, 11, "--keep-circle", "2,5,2", "--keep-circle", "8,5,2")
    assert kept(g) == kept(mask_grid(tmp_path, 11, "--keep-circle", "2,5,2", name="a.px")) | \
        kept(mask_grid(tmp_path, 11, "--keep-circle", "8,5,2", name="b.px"))
    assert g[5] == "kkkkk.kkkkk"


@pytest.mark.parametrize("shapes", [
    [["--keep-circle", "12,20,10"], ["--keep-circle", "28,20,10"]],                 # overlapping lamps
    [["--keep-circle", "10,10,8"], ["--keep-circle", "30,30,8"]],                   # apart
    [["--keep-circle", "20,20,12"], ["--keep-circle", "20,20,6"]],                  # nested
    [["--keep-circle", "15,15,9"], ["--keep", "20,5,15,10"]],                       # a circle and a rect
    [["--keep", "0,0,10,10"], ["--keep", "5,5,10,10"], ["--keep-circle", "30,30,7"]],
    [["--keep-circle", "12,20,10"], ["--keep-circle", "20,20,10"], ["--keep-circle", "28,20,10"]],
])
@pytest.mark.parametrize("dither", [[], ["--dither", "3"], ["--dither", "6"]])
def test_mask_union_is_the_or_of_single_masks(tmp_path, shapes, dither):
    if dither and not any(s[0] == "--keep-circle" for s in shapes):
        pytest.skip("dither needs a circle")
    n = 40
    union = kept(mask_grid(tmp_path, n, *[a for s in shapes for a in s], *dither))
    each = set()
    for i, s in enumerate(shapes):
        d = dither if s[0] == "--keep-circle" else []
        each |= kept(mask_grid(tmp_path, n, *s, *d, name=f"s{i}.px"))
    assert union == each


@pytest.mark.parametrize("dither", [[], ["--dither", "4"], ["--dither", "8"]])
def test_mask_union_invert_is_the_exact_complement(tmp_path, dither):
    shapes = ["--keep-circle", "14,20,11", "--keep-circle", "26,20,11", "--keep", "0,34,40,3"]
    n = 40
    plain = kept(mask_grid(tmp_path, n, *shapes, *dither, name="p.px"))
    inv = kept(mask_grid(tmp_path, n, *shapes, *dither, "--invert", name="i.px"))
    assert plain & inv == set() and plain | inv == {(x, y) for x in range(n) for y in range(n)}


def test_mask_overlapping_dither_bands_keep_what_either_keeps(tmp_path):
    # Two lamps whose dither bands overlap: in the overlap a pixel is kept if either lamp keeps it.
    n = 40
    both = kept(mask_grid(tmp_path, n, "--keep-circle", "15,20,10", "--keep-circle", "25,20,10", "--dither", "5"))
    a = kept(mask_grid(tmp_path, n, "--keep-circle", "15,20,10", "--dither", "5", name="a.px"))
    b = kept(mask_grid(tmp_path, n, "--keep-circle", "25,20,10", "--dither", "5", name="b.px"))
    band = lambda cx, x, y: 5 < ((x - cx) ** 2 + (y - 20) ** 2) ** 0.5 <= 10  # noqa: E731
    overlap = {(x, y) for x in range(n) for y in range(n) if band(15, x, y) and band(25, x, y)}
    assert overlap and both == a | b
    assert any(p in a and p not in b for p in overlap) and any(p in b and p not in a for p in overlap)
    assert all(p in both for p in overlap if p in a or p in b)


def test_mask_union_on_a_png(tmp_path):
    solid_png(tmp_path, "s.png", (30, 20), (0, 0, 0, 255))
    args = ["--keep-circle", "8,10,6", "--keep-circle", "22,10,6", "--dither", "3"]
    assert run("mask", tmp_path / "s.png", *args, "-o", tmp_path / "m.png") == 0
    p = write(tmp_path, "r.px", "k #000000\n" + ("k" * 30 + "\n") * 20)
    assert run("mask", p, *args) == 0
    assert alpha_grid(tmp_path / "m.png") == pxart.parse(p).frames[0].grid


def test_mask_union_erased_count(tmp_path, capsys):
    p = square(tmp_path, 4)
    assert run("mask", p, "--keep", "0,0,1,1", "--keep", "3,3,1,1", "--keep", "0,0,1,1") == 0
    assert "erased 14 px" in capsys.readouterr().out


def test_mask_one_shape_unchanged(tmp_path):
    assert mask_grid(tmp_path, 7, "--keep-circle", "3,3,2") == [
        ".......", "...k...", "..kkk..", ".kkkkk.", "..kkk..", "...k...", "......."]


def test_mask_union_bad_value_names_the_flag(tmp_path):
    p = square(tmp_path, 4)
    before = p.read_text()
    msg = run_err("mask", p, "--keep-circle", "1,1,1", "--keep-circle", "1,1")
    assert "E_BAD_ARG" in msg and "--keep-circle wants cx,cy,r, got '1,1'" in msg
    msg = run_err("mask", p, "--keep", "0,0,1,1", "--keep", "a,0,1,1")
    assert "--keep wants x,y,w,h, got 'a,0,1,1'" in msg and p.read_text() == before


def test_mask_union_dither_needs_a_circle(tmp_path):
    p = square(tmp_path, 4)
    assert "E_BAD_ARG" in run_err("mask", p, "--keep", "0,0,1,1", "--keep", "1,1,1,1", "--dither", "2")
    assert run("mask", p, "--keep", "0,0,1,1", "--keep-circle", "3,3,1", "--dither", "1") == 0


def test_mask_without_a_shape_is_bad_arg(tmp_path):
    p = square(tmp_path, 4)
    msg = run_err("mask", p, "--invert")
    assert "E_BAD_ARG" in msg and "mask needs a shape" in msg


def test_help_documents_mask_union():
    doc = pxart.__doc__
    assert "--keep and --keep-circle repeat" in doc and "the kept area is their union" in doc
    assert "--dither and --invert\n      work over the union" in doc


# ---------------------------------------------------------------- loop H: anim without -o prints only the numbers

def test_anim_without_output_prints_numbers_and_writes_nothing(tmp_path, capsys, monkeypatch):
    p = write(tmp_path, "m.px", MULTI)
    monkeypatch.chdir(tmp_path)
    before = sorted(x.name for x in tmp_path.iterdir())
    assert run("anim", f"{p}:walk/down") == 0
    out = capsys.readouterr().out
    assert sorted(x.name for x in tmp_path.iterdir()) == before
    assert "wrote" not in out and len(out.splitlines()) == 2 and all(" vs " in l for l in out.splitlines())


@pytest.mark.parametrize("frames", [(BOB_0, BOB_1), (BREATHE_0, BREATHE_1), (WALK_0, WALK_1), (WALK_0, WALK_0)])
def test_anim_without_output_prints_the_same_lines(tmp_path, capsys, frames):
    p = anim_file(tmp_path, *frames)
    assert run("anim", f"{p}:idle", "-o", tmp_path / "a.gif") == 0
    with_o = capsys.readouterr().out.splitlines()
    assert with_o[-1].startswith("wrote ")
    assert run("anim", f"{p}:idle") == 0
    assert capsys.readouterr().out.splitlines() == with_o[:-1]


def test_anim_without_output_fps_and_variant(tmp_path, capsys):
    p = write(tmp_path, "m.px", MULTI)
    assert run("anim", f"{p}:walk/down", "--fps", "5", "--variant", "night") == 0
    out = capsys.readouterr().out
    assert out.count("  200ms") == 2 and not list(tmp_path.glob("*.gif"))


def test_anim_without_output_still_reports_errors(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    assert "E_SELECT" in run_err("anim", f"{p}:nope")


def test_anim_with_output_still_writes_gif_and_strip(tmp_path, capsys):
    p = write(tmp_path, "m.px", MULTI)
    assert run("anim", f"{p}:walk/down", "-o", tmp_path / "w.gif") == 0
    assert (tmp_path / "w.gif").exists() and (tmp_path / "w.strip.png").exists()
    assert capsys.readouterr().out.splitlines()[-1] == f"wrote {tmp_path / 'w.gif'} and {tmp_path / 'w.strip.png'}"


def test_help_documents_anim_without_output():
    doc = pxart.__doc__
    assert "anim FILE... [-o walk.gif]" in doc and "without -o, anim prints only those lines" in doc


# ---------------------------------------------------------------- loop H: frames move already in place

@pytest.mark.parametrize("sel,where,anchor", [
    ("walk", "--after", "idle/0"), ("walk", "--before", "icon"), ("walk/0", "--after", "idle/0"),
    ("walk/2", "--before", "icon"), ("idle", "--before", "walk/0"), ("icon", "--after", "walk/2"),
    ("walk/1", "--after", "walk/0"), ("walk/1", "--before", "walk/2"),
])
def test_frames_sel_move_already_in_place(tmp_path, capsys, sel, where, anchor):
    p = write(tmp_path, "h.px", SELS)
    before, m = snap(p)
    assert run("frames", f"{p}:{sel}", where, anchor) == 0
    out = capsys.readouterr().out
    n = len(pxart.parse(p).select(sel))
    assert out == f"already in place: {sel} ({n} frame(s)) {where[2:]} {anchor}; no change: {p}\n"
    assert out.count("already in place") == 1 and "moved" not in out and untouched(p, before, m)


@pytest.mark.parametrize("move,where,anchor", [
    ("a/1", "--after", "a/0"), ("a/0", "--before", "a/1"), ("a/2", "--after", "a/1"), ("a/1", "--before", "a/2")])
def test_frames_move_already_in_place(tmp_path, capsys, move, where, anchor):
    p = write(tmp_path, "m.px", "k #000000\n@frame a/0\nk\n@frame a/1\nk\n@frame a/2\nk\n")
    before, m = snap(p)
    assert run("frames", p, "--move", move, where, anchor) == 0
    out = capsys.readouterr().out
    assert out == f"already in place: {move} {where[2:]} {anchor}; no change: {p}\n"
    assert "moved" not in out and untouched(p, before, m)


def test_frames_move_that_moves_still_says_moved(tmp_path, capsys):
    p = write(tmp_path, "m.px", "k #000000\n@frame a/0\nk\n@frame a/1\nk\n@frame a/2\nk\n")
    assert run("frames", p, "--move", "a/0", "--after", "a/1") == 0
    out = capsys.readouterr().out
    assert out == f"moved a/0 after a/1; wrote {p}\n" and "already" not in out
    assert ids(p) == ["a/1", "a/0", "a/2"]


def test_frames_sel_move_that_moves_still_says_moved(tmp_path, capsys):
    p = write(tmp_path, "h.px", SELS)
    assert run("frames", f"{p}:walk", "--after", "icon") == 0
    out = capsys.readouterr().out
    assert out == f"moved walk (3 frame(s)) after icon; wrote {p}\n" and "already" not in out


def test_frames_rm_with_move_already_in_place_writes_the_removal(tmp_path, capsys):
    p = write(tmp_path, "m.px", "k #000000\n@frame a/0\nk\n@frame a/1\nk\n@frame a/2\nk\n")
    assert run("frames", p, "--rm", "a/0", "--move", "a/2", "--after", "a/1") == 0
    assert capsys.readouterr().out == f"removed a/0; already in place: a/2 after a/1; wrote {p}\n"
    assert ids(p) == ["a/1", "a/2"]


def test_frames_already_in_place_keeps_layout(tmp_path, capsys):
    p = write(tmp_path, "a.px", MESSY)
    assert run("frames", f"{p}:walk/1", "--after", "walk/0") == 0
    assert p.read_text() == MESSY and "already in place" in capsys.readouterr().out


def test_help_documents_already_in_place():
    assert 'prints "already in place" and writes nothing' in " ".join(pxart.__doc__.split())


# ---------------------------------------------------------------- loop H: extract writes @anim in frame-group order

ANIMS_OUT_OF_ORDER = ("k #000000\n\n@anim villager/walk ms=150\n@anim dog/walk ms=90\n@anim dog/idle ms=300\n\n"
                      "@frame dog/idle/0\nk\n@frame dog/walk/0\nk\n@frame dog/walk/1\nk\n"
                      "@frame villager/walk/0\nk\n@frame villager/walk/1\nk\n")


def anim_order(p):
    return [l.split()[1] for l in p.read_text().splitlines() if l.startswith("@anim")]


def test_extract_anims_follow_the_frames_groups(tmp_path):
    p = write(tmp_path, "f.px", ANIMS_OUT_OF_ORDER)
    assert run("extract", f"{p}:dog", "-o", tmp_path / "dog.px") == 0
    assert anim_order(tmp_path / "dog.px") == ["dog/idle", "dog/walk"]
    assert (tmp_path / "dog.px").read_text() == (
        "k #000000\n\n@anim dog/idle ms=300\n@anim dog/walk ms=90\n\n"
        "@frame dog/idle/0\nk\n@frame dog/walk/0\nk\n@frame dog/walk/1\nk\n")


def test_extract_whole_file_orders_anims_by_frames(tmp_path):
    p = write(tmp_path, "f.px", ANIMS_OUT_OF_ORDER)
    assert run("extract", p, "-o", tmp_path / "all.px") == 0
    assert anim_order(tmp_path / "all.px") == ["dog/idle", "dog/walk", "villager/walk"]
    doc = pxart.parse(tmp_path / "all.px")
    assert doc.anims == pxart.parse(p).anims and [f.id for f in doc.frames] == ids(p)


def test_extract_anims_already_in_order_are_a_byte_copy(tmp_path):
    text = ("k #000000\n\n# timing\n@anim a ms=90\n\n@anim b ms=80\n\n@frame a/0\nk\n@frame b/0\nk\n")
    p = write(tmp_path, "f.px", text)
    assert run("extract", p, "-o", tmp_path / "c.px") == 0
    assert (tmp_path / "c.px").read_text() == text


def test_extract_anim_comments_move_with_their_line(tmp_path):
    text = "k #000000\n\n# for b\n@anim b ms=80\n# for a\n@anim a ms=90\n@frame a/0\nk\n@frame b/0\nk\n"
    p = write(tmp_path, "f.px", text)
    assert run("extract", p, "-o", tmp_path / "c.px") == 0
    assert (tmp_path / "c.px").read_text() == ("k #000000\n# for a\n@anim a ms=90\n\n# for b\n@anim b ms=80\n"
                                               "@frame a/0\nk\n@frame b/0\nk\n")


def test_extract_anim_without_frames_goes_last(tmp_path):
    text = "k #000000\n@anim ghost ms=10\n@anim b ms=80\n@anim a ms=90\n@frame a/0\nk\n@frame b/0\nk\n"
    p = write(tmp_path, "f.px", text)
    assert run("extract", p, "-o", tmp_path / "c.px") == 0
    assert anim_order(tmp_path / "c.px") == ["a", "b", "ghost"]


def test_extract_anims_after_frames_move(tmp_path):
    # The loop H sequence: move the dog after the villager, then extract everything: @anim follows.
    p = write(tmp_path, "f.px", ANIMS_OUT_OF_ORDER)
    assert run("frames", f"{p}:dog", "--after", "villager/walk/1") == 0
    assert run("extract", p, "-o", tmp_path / "c.px") == 0
    assert anim_order(tmp_path / "c.px") == ["villager/walk", "dog/idle", "dog/walk"]


def test_extract_inline_palette_orders_anims_too(tmp_path):
    write(tmp_path, "pal.px", "k #000000\n")
    p = write(tmp_path, "f.px", "@palette pal.px\n@anim b ms=80\n@anim a ms=90\n@frame a/0\nk\n@frame b/0\nk\n")
    assert run("extract", p, "-o", tmp_path / "c.px", "--inline-palette") == 0
    assert anim_order(tmp_path / "c.px") == ["a", "b"]


def test_help_documents_extract_anim_order():
    assert "@anim lines in the order of the frames' groups" in pxart.__doc__


# ---------------------------------------------------------------- loop H: errors name the command and the input

BROKEN = "k #000000\n@frame hat\nkk\nk\n@frame body\nkq\n"  # line 4: E_ROW_WIDTH, line 6: E_UNKNOWN_KEY


def broken_lines(msg):
    return [l for l in msg.splitlines() if "E_ROW_WIDTH" in l or "E_UNKNOWN_KEY" in l]


def test_compose_error_names_the_layer(tmp_path):
    ok, bad = write(tmp_path, "ok.px", "k #000000\nkk\n"), write(tmp_path, "parts.px", BROKEN)
    msg = run_err("compose", "-o", tmp_path / "o.px", f"{ok}@0,0", f"{bad}:hat@0,0")
    lines = broken_lines(msg)
    assert len(lines) == 2 and all(l.startswith(f"compose: layer 2 ({bad}:hat): {bad}:") for l in lines)
    assert f"compose: layer 2 ({bad}:hat): {bad}:4: E_ROW_WIDTH (frame hat, row 1)" in msg
    assert f"compose: layer 2 ({bad}:hat): {bad}:6: E_UNKNOWN_KEY (frame body, row 0, x=[1])" in msg
    assert not (tmp_path / "o.px").exists()


def test_compose_error_names_the_first_layer_too(tmp_path):
    ok, bad = write(tmp_path, "ok.px", "k #000000\nkk\n"), write(tmp_path, "parts.px", BROKEN)
    assert run_err("compose", "-o", tmp_path / "o.px", f"{bad}:hat@1,1", f"{ok}@0,0").startswith(
        f"compose: layer 1 ({bad}:hat): ")


def test_compose_select_error_names_the_layer(tmp_path):
    ok = write(tmp_path, "ok.px", "k #000000\n@frame a\nkk\n")
    msg = run_err("compose", "-o", tmp_path / "o.px", f"{ok}:a@0,0", f"{ok}:zz@0,0")
    assert msg.startswith(f"compose: layer 2 ({ok}:zz): {ok}: E_SELECT: no frame 'zz'")


def test_compose_key_conflict_names_the_layer(tmp_path):
    a, b = write(tmp_path, "a.px", "k #000000\nk\n"), write(tmp_path, "b.px", "k #ffffff\nk\n")
    msg = run_err("compose", "-o", tmp_path / "o.px", "--size", "2x1", f"{a}@0,0", f"{b}@1,0")
    assert msg.startswith(f"compose: layer 2 ({b}): ") and "E_KEY_CONFLICT" in msg


def test_compose_bad_layer_arg_names_the_layer(tmp_path):
    a = write(tmp_path, "a.px", "k #000000\nk\n")
    msg = run_err("compose", "-o", tmp_path / "o.px", f"{a}@0,0", f"{a}")
    assert msg.startswith(f"compose: layer 2 ({a}): E_BAD_ARG: expected FILE[:frame][%variant]@x,y")


def test_compose_png_layer_names_the_layer(tmp_path):
    Image.new("RGBA", (1, 1), (1, 2, 3, 255)).save(tmp_path / "p.png")
    msg = run_err("compose", "-o", tmp_path / "o.px", f"{tmp_path / 'p.png'}@0,0")
    assert msg.startswith(f"compose: layer 1 ({tmp_path / 'p.png'}): E_BAD_ARG: compose layers must be .px frames")


def test_compose_broken_output_file_is_named(tmp_path):
    ok = write(tmp_path, "ok.px", "k #000000\nk\n")
    out = write(tmp_path, "out.px", BROKEN)
    msg = run_err("compose", "-o", f"{out}:hat", f"{ok}@0,0")
    assert all(l.startswith(f"compose: -o ({out}:hat): {out}:") for l in broken_lines(msg))


def test_crop_error_names_its_input(tmp_path):
    bad = write(tmp_path, "parts.px", BROKEN)
    msg = run_err("crop", f"{bad}:hat", "0,0,1,1", "-o", tmp_path / "o.px")
    assert all(l.startswith(f"crop: FILE ({bad}:hat): ") for l in broken_lines(msg)) and broken_lines(msg)


def test_scene_error_names_the_item(tmp_path):
    ok, bad = write(tmp_path, "ok.px", "k #000000\nkk\n"), write(tmp_path, "parts.px", BROKEN)
    msg = run_err("scene", "-o", tmp_path / "s.png", f"{ok}@0,0", f"{bad}:body@1,1")
    assert len(broken_lines(msg)) == 2
    assert all(l.startswith(f"scene: item 2 ({bad}:body): {bad}:") for l in broken_lines(msg))
    assert not (tmp_path / "s.png").exists()


def test_scene_variant_error_names_the_item(tmp_path):
    ok = write(tmp_path, "ok.px", "k #000000\nkk\n")
    msg = run_err("scene", "-o", tmp_path / "s.png", "--variant", "night", f"{ok}@0,0")
    assert msg.startswith(f"scene: item 1 ({ok}): {ok}: E_SELECT: no @variant 'night'")


def test_scene_map_error_names_the_map(tmp_path):
    write(tmp_path, "parts.px", BROKEN)
    m = write(tmp_path, "room.map", "h parts.px:hat\n\nh\n")
    msg = run_err("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "2x2")
    assert msg.startswith(f"scene: --map ({m}): {m}:1: E_ROW_WIDTH: legend 'h'")
    bad = write(tmp_path, "bad.map", "h parts.px:hat\n\nhq\n")
    assert run_err("scene", "-o", tmp_path / "s.png", "--map", bad).startswith(
        f"scene: --map ({bad}): {bad}:3: E_UNKNOWN_KEY")


def test_paste_errors_name_src_or_into(tmp_path):
    ok, bad = write(tmp_path, "ok.px", "k #000000\nkk\n"), write(tmp_path, "parts.px", BROKEN)
    msg = run_err("paste", f"{bad}:hat", "--into", ok, "--at", "0,0")
    assert broken_lines(msg) and all(l.startswith(f"paste: SRC ({bad}:hat): ") for l in broken_lines(msg))
    msg = run_err("paste", ok, "--into", f"{bad}:hat", "--at", "0,0")
    assert broken_lines(msg) and all(l.startswith(f"paste: --into ({bad}:hat): ") for l in broken_lines(msg))


def test_paste_key_conflict_names_src(tmp_path):
    a, b = write(tmp_path, "a.px", "k #000000\nkk\n"), write(tmp_path, "b.px", "k #ffffff\nk\n")
    msg = run_err("paste", b, "--into", a, "--at", "0,0")
    assert msg.startswith(f"paste: SRC ({b}): ") and "E_KEY_CONFLICT" in msg


@pytest.mark.parametrize("argv", [
    ["flip", "{b}:hat"], ["shift", "{b}", "--dx", "1"], ["set", "{b}:hat", "k", "0,0"], ["fill", "{b}", "k"],
    ["mask", "{b}", "--keep", "0,0,1,1"], ["recolor", "{b}", "k=k"], ["extract", "{b}:hat", "-o", "{t}/o.px"],
    ["frames", "{b}"], ["dup", "{b}:hat", "hat2"], ["anim-set", "{b}:hat", "ms=90"], ["palette", "{b}"],
    ["export", "{b}", "--frames", "{t}/f"], ["new", "{b}:x", "--size", "1x1"],
])
def test_one_input_commands_name_command_and_input(tmp_path, argv):
    bad = write(tmp_path, "parts.px", BROKEN)
    args = [a.format(b=bad, t=tmp_path) for a in argv]
    before = bad.read_text()
    msg = run_err(*args)
    lines = broken_lines(msg)
    label = "OUT" if argv[0] == "new" else "FILE"
    assert len(lines) == 2 and all(l.startswith(f"{argv[0]}: {label} ({args[1]}): {bad}:") for l in lines), msg
    assert bad.read_text() == before


@pytest.mark.parametrize("cmd", ["render", "sheet", "anim", "stats"])
def test_several_file_commands_name_which_file(tmp_path, cmd):
    ok, bad = write(tmp_path, "ok.px", "k #000000\nkk\n"), write(tmp_path, "parts.px", BROKEN)
    out = ["-o", tmp_path / "x.png"] if cmd != "stats" else []
    msg = run_err(cmd, ok, bad, *out)
    assert len(broken_lines(msg)) == 2 and all(l.startswith(f"{cmd}: file 2 ({bad}): ") for l in broken_lines(msg))


def test_onion_names_a_or_b(tmp_path):
    ok, bad = write(tmp_path, "ok.px", "k #000000\nkk\n"), write(tmp_path, "parts.px", BROKEN)
    assert run_err("onion", ok, f"{bad}:hat", "-o", tmp_path / "o.png").startswith(f"onion: B ({bad}:hat): ")
    assert run_err("onion", f"{bad}:hat", ok, "-o", tmp_path / "o.png").startswith(f"onion: A ({bad}:hat): ")


def test_export_select_error_names_the_selector(tmp_path):
    ok = write(tmp_path, "ok.px", "k #000000\n@frame a\nk\n")
    msg = run_err("export", f"{ok}:a", f"{ok}:zz", "--frames", tmp_path / "f")
    assert msg.startswith(f"export: FILE ({ok}:zz): {ok}: E_SELECT")


def test_put_errors_name_the_command(tmp_path, monkeypatch):
    bad = write(tmp_path, "parts.px", BROKEN)
    msg = put_err(monkeypatch, "k\n", f"{bad}:hat")
    assert broken_lines(msg) and all(l.startswith(f"put: FILE ({bad}:hat): ") for l in broken_lines(msg))
    ok = write(tmp_path, "ok.px", "k #000000\nkk\n")
    assert put_err(monkeypatch, "kk\nk\n", ok).startswith("put: stdin:2: E_ROW_WIDTH")  # stdin isn't said twice
    assert put_err(monkeypatch, "@frame x\nk\n", ok).startswith("put: stdin: E_BAD_ARG")


def test_check_palette_error_names_the_flag(tmp_path):
    ok, bad = write(tmp_path, "ok.px", "k #000000\nkk\n"), write(tmp_path, "parts.px", BROKEN)
    msg = run_err("check", ok, "--palette", bad)
    assert msg.startswith(f"check: --palette ({bad}): ")


def test_from_png_broken_output_is_named(tmp_path):
    Image.new("RGBA", (1, 1), (1, 2, 3, 255)).save(tmp_path / "i.png")
    bad = write(tmp_path, "parts.px", BROKEN)
    msg = run_err("from-png", tmp_path / "i.png", "-o", bad)
    assert broken_lines(msg) and all(l.startswith(f"from-png: -o ({bad}): ") for l in broken_lines(msg))


def test_check_output_is_unchanged_by_error_prefixes(tmp_path, capsys):
    bad = write(tmp_path, "parts.px", BROKEN)
    assert run("check", bad) == 1
    out = capsys.readouterr().out
    assert out.splitlines()[1] == f"     {bad}:4: E_ROW_WIDTH (frame hat, row 1): row is 1 wide, but 1 of 2 rows are 2 wide: 'k'"
    assert "check:" not in out and "FILE (" not in out


def test_argument_errors_have_no_input_prefix(tmp_path):
    ok = write(tmp_path, "ok.px", "k #000000\nkk\n")
    msg = run_err("set", ok, "k", "9,9")
    assert msg.startswith("set: E_BAD_ARG: ")  # loop J: the command, never a bare ': E_BAD_ARG'
    assert "FILE (" not in msg


def test_parse_errors_outside_a_command_are_unchanged(tmp_path):
    bad = write(tmp_path, "parts.px", BROKEN)
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(bad)
    assert str(e.value).startswith(f"{bad}:4: E_ROW_WIDTH") and all(i.ctx is None for i in e.value.issues)


def test_reading_innermost_label_wins():
    with pytest.raises(pxart.PxError) as e:
        with pxart.reading("outer"):
            with pxart.reading("inner"):
                pxart.fail("E_BAD_ARG", "x", path="a.px")
    assert str(e.value) == "inner: a.px: E_BAD_ARG: x"


def test_reading_without_path_has_no_empty_where():
    with pytest.raises(pxart.PxError) as e:
        with pxart.reading("layer 1 (a.px)"):
            pxart.fail("E_SELECT", "nope")
    assert str(e.value) == "layer 1 (a.px): E_SELECT: nope"


def test_missing_input_file_is_still_plain_e_file(tmp_path):
    ok = write(tmp_path, "ok.px", "k #000000\nk\n")
    msg = run_err("compose", "-o", tmp_path / "o.px", f"{ok}@0,0", f"{tmp_path / 'nope.px'}@0,0")
    assert msg.startswith(f"compose: {tmp_path / 'nope.px'}: E_FILE")


def test_help_documents_error_prefixes():
    assert "compose: layer 2 (parts.px:hat): parts.px:4: E_ROW_WIDTH" in pxart.__doc__


# ---------------------------------------------------------------- loop H: the strip's shift detector wraps tiles

SNOW_PAL = "s #f4f8ff\nw #c8d8f0\n"
SNOW_0 = ["............s...", "..w.............", "................", ".........w......", "....s...........",
          "................", "..............w.", "................", ".....w..........", "................",
          "........s.......", "...........w....", "...............s", ".w..............", ".......w........",
          "................"]


def roll_grid(grid, dx, dy):
    """grid scrolled by dx, dy with wrap-around, as 'shift --wrap' does."""
    h, w = len(grid), len(grid[0])
    return ["".join(grid[(y - dy) % h][(x - dx) % w] for x in range(w)) for y in range(h)]


def tile_file(tmp_path, pal, *grids, name="t.px", group="fall"):
    text = pal + f"@anim {group} ms=180\n" + "".join(f"@frame {group}/{i}\n" + "\n".join(g) + "\n"
                                                    for i, g in enumerate(grids))
    return write(tmp_path, name, text)


def strip_lines(tmp_path, capsys, p, sel="fall"):
    assert run("anim", f"{p}:{sel}") == 0
    return [l.split(": ", 1)[1] for l in capsys.readouterr().out.splitlines() if " vs " in l]


def test_roll_grid_matches_shift_wrap(tmp_path):
    p = write(tmp_path, "s.px", SNOW_PAL + "\n".join(SNOW_0) + "\n")
    assert run("shift", p, "--dx", "-1", "--dy", "4", "--wrap") == 0
    assert pxart.parse(p).frames[0].grid == roll_grid(SNOW_0, -1, 4)


def test_snowfall_wrap_is_found(tmp_path, capsys):
    # The loop H case: a sparse snow overlay scrolled -1,+4 with wrap read as 'shift -1,-2 then 17px'.
    p = tile_file(tmp_path, SNOW_PAL, SNOW_0, roll_grid(SNOW_0, -1, 4))
    lines = strip_lines(tmp_path, capsys, p)
    assert lines[1].startswith("shift -1,+4 (wrap) then 0px (0%) (no shift: ")
    assert lines[0].startswith("shift +1,-4 (wrap) then 0px (0%) (no shift: ")


def test_loop_h_snowfall_frames(tmp_path, capsys):
    f1 = roll_grid(SNOW_0, -1, 4)
    f2 = roll_grid(f1, 1, 4)
    f3 = roll_grid(f2, -1, 4)
    p = tile_file(tmp_path, SNOW_PAL, SNOW_0, f1, f2, f3)
    lines = strip_lines(tmp_path, capsys, p)
    assert [l.split(" then")[0] for l in lines] == ["shift +1,+4 (wrap)", "shift -1,+4 (wrap)",
                                                    "shift +1,+4 (wrap)", "shift -1,+4 (wrap)"]
    assert all(" then 0px " in l for l in lines)


def test_snowfall_strip_shows_nothing_changed(tmp_path, capsys):
    p = tile_file(tmp_path, SNOW_PAL, SNOW_0, roll_grid(SNOW_0, -1, 4))
    assert run("anim", f"{p}:fall", "-o", tmp_path / "a.gif") == 0
    capsys.readouterr()
    for i in (0, 1):
        assert magenta_rows(tmp_path, i, h=16, w=16) == set()


@pytest.mark.parametrize("dx,dy", [(1, 0), (-1, 0), (0, 1), (0, -1), (3, 5), (-7, 2), (8, 8), (-5, -6), (0, 7)])
def test_wrap_scroll_of_a_sparse_overlay_any_offset(tmp_path, capsys, dx, dy):
    p = tile_file(tmp_path, SNOW_PAL, SNOW_0, roll_grid(SNOW_0, dx, dy))
    line = strip_lines(tmp_path, capsys, p)[1]
    assert line.startswith(f"shift {dx:+d},{dy:+d} ") and " then 0px " in line
    # A scroll within the plain reach (2px) that no flake wraps in is already exact as a plain shift: no '(wrap)'.
    doc = pxart.parse(p)
    a, b = (doc.image(f) for f in doc.frames)
    plain_exact = max(abs(dx), abs(dy)) <= 2 and pxart.n_changed(pxart.shifted(a, dx, dy), b) == 0
    assert ("(wrap)" in line) != plain_exact


WATER_PAL = "a #2050a0\nb #3070c0\nc #80b0e0\n"
WATER_0 = ["aaaabbbaaaaacaaa", "aabbbaaaaccaaaaa", "abbaaaaacaaaaabb", "bbaaaaaaaaaaabba",
           "aaaacaaaaabbbbaa", "aaacccaaabbaaaaa", "aaaaaaabbaaaaaac", "bbaaaabbaaaaaccc"]


@pytest.mark.parametrize("dx,dy", [(1, 0), (-2, 0), (0, 1), (3, -2)])
def test_wrap_scroll_of_a_ground_tile(tmp_path, capsys, dx, dy):
    p = tile_file(tmp_path, WATER_PAL, WATER_0, roll_grid(WATER_0, dx, dy), group="water")
    lines = strip_lines(tmp_path, capsys, p, "water")
    assert lines[1].startswith(f"shift {dx:+d},{dy:+d} (wrap) then 0px (0%) (no shift: ")


def test_ground_tile_still_frame_is_no_shift(tmp_path, capsys):
    p = tile_file(tmp_path, WATER_PAL, WATER_0, WATER_0, group="water")
    assert strip_lines(tmp_path, capsys, p, "water") == ["shift +0,+0 then 0px (0%)"] * 2


def test_ground_tile_with_a_changed_pixel_and_no_scroll(tmp_path, capsys):
    other = list(WATER_0)
    other[3] = "c" + other[3][1:]
    p = tile_file(tmp_path, WATER_PAL, WATER_0, other, group="water")
    assert strip_lines(tmp_path, capsys, p, "water")[1] == "shift +0,+0 then 1px (1%)"  # 1 of 128


def test_wrap_needs_strictly_fewer_pixels(tmp_path, capsys):
    # One flake moved 1,1 in the middle: the plain shift already explains it all, so no '(wrap)'.
    a = ["." * 8] * 3 + ["...s...."] + ["." * 8] * 4
    b = ["." * 8] * 4 + ["....s..."] + ["." * 8] * 3
    p = tile_file(tmp_path, SNOW_PAL, a, b)
    lines = strip_lines(tmp_path, capsys, p)
    assert lines[1] == "shift +1,+1 then 0px (0%) (no shift: 2px)" and "(wrap)" not in lines[0]


def test_character_sprite_never_wraps(tmp_path, capsys):
    # Half the pixels opaque (a sprite, not a tile or an overlay): even a scroll that a wrap would explain
    # exactly is reported as a plain shift, as before.
    a = ["kkyy....", "kkyy....", "..yykk..", "..yykk..", "kk....yy", "kk....yy", "yykk..kk", "yykk..kk"]
    b = roll_grid(a, 0, 1)
    p = anim_file(tmp_path, a, b, name="c.px")
    assert run("anim", f"{p}:idle") == 0
    out = capsys.readouterr().out
    assert "(wrap)" not in out and "shift +0,+1 then" in out


def test_mixed_size_frames_never_wrap(tmp_path, capsys):
    small = [r[:15] for r in SNOW_0]  # 15 wide: drawn on a 16-wide canvas, so it doesn't fill it
    p = tile_file(tmp_path, SNOW_PAL, small, roll_grid(SNOW_0, -1, 4))
    assert all("(wrap)" not in l for l in strip_lines(tmp_path, capsys, p))


def test_may_wrap_rules(tmp_path):
    def img(n_opaque, w=8, h=8):
        im = Image.new("RGBA", (w, h))
        for i in range(n_opaque):
            im.putpixel((i % w, i // w), (1, 2, 3, 255))
        return im
    assert pxart.may_wrap(img(64), img(64))          # a ground tile
    assert pxart.may_wrap(img(16), img(3))           # sparse: at most 1/4
    assert pxart.may_wrap(img(0), img(16))
    assert not pxart.may_wrap(img(17), img(3))       # just over 1/4
    assert not pxart.may_wrap(img(64), img(63))      # a tile with a hole isn't a ground tile
    assert not pxart.may_wrap(img(64), img(10))      # one tile, one overlay
    assert not pxart.may_wrap(img(30), img(30))      # a sprite
    assert not pxart.may_wrap(img(4, 8, 8), img(4, 8, 9))


def test_best_shift_without_wrap_is_unchanged(tmp_path):
    a, b = Image.new("RGBA", (4, 4)), Image.new("RGBA", (4, 4))
    a.putpixel((0, 0), (1, 1, 1, 255)); b.putpixel((3, 3), (1, 1, 1, 255))
    assert pxart.best_shift(a, b) == (0, -1, False)  # as before: out of reach, it pushes the pixel off the edge
    assert pxart.best_shift(a, b, wrap=True) == (-1, -1, True)  # 0,0 scrolled -1,-1 lands on 3,3


def test_motion_reports_wrapped(tmp_path):
    doc = pxart.parse(tile_file(tmp_path, SNOW_PAL, SNOW_0, roll_grid(SNOW_0, -1, 4)))
    a, b = (doc.image(f) for f in doc.frames)
    dx, dy, n_shift, n_none, still, wrapped = pxart.motion(a, b, wrap=True)
    assert (dx, dy, n_shift, still, wrapped) == (-1, 4, 0, None, True) and n_none > 0
    assert pxart.motion(a, b)[5] is False


def test_n_changed_counts_differing_pixels():
    a, b = Image.new("RGBA", (3, 2)), Image.new("RGBA", (3, 2))
    b.putpixel((0, 0), (0, 0, 0, 1)); b.putpixel((2, 1), (5, 0, 0, 0))
    assert pxart.n_changed(a, b) == 2 and pxart.n_changed(a, a) == 0
    assert pxart.n_changed(a, b) == sum(x != y for x, y in zip(pxart.pixels(a), pxart.pixels(b)))


def test_rolled_matches_shift_wrap(tmp_path):
    doc = pxart.parse(tile_file(tmp_path, SNOW_PAL, SNOW_0, roll_grid(SNOW_0, 3, -5)))
    a, b = (doc.image(f) for f in doc.frames)
    assert pxart.pixels(pxart.rolled(a, 3, -5)) == pxart.pixels(b)


def test_help_documents_wrap_in_the_strip():
    doc = pxart.__doc__
    assert '"shift dx,dy (wrap) then N px (P%) (no shift: M px)"' in doc and "A character sprite never wraps" in doc
    assert "strictly fewer pixels changed" in doc


# ---------------------------------------------------------------- loop I: 'transparent' wherever a color is typed

def test_scene_bg_transparent(tmp_path):
    p = write(tmp_path, "a.px", "k #102030\nk.\n")
    assert run("scene", "-o", tmp_path / "s.png", "--size", "3x2", "--scale", "1", "--bg", "transparent",
               f"{p}@0,0") == 0
    img = Image.open(tmp_path / "s.png").convert("RGBA")
    assert img.getpixel((0, 0)) == (0x10, 0x20, 0x30, 255)
    assert img.getpixel((1, 0)) == (0, 0, 0, 0) and img.getpixel((2, 1)) == (0, 0, 0, 0)


def test_scene_bg_transparent_with_map_and_tint(tmp_path):
    write(tmp_path, "t.px", "k #000000\n@frame a\nk\n")
    m = write(tmp_path, "r.map", "a t.px:a\n\na.\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "1x1", "--scale", "1", "--bg", "transparent",
               "--tint", "#ff000080") == 0
    img = Image.open(tmp_path / "s.png").convert("RGBA")
    assert img.getpixel((1, 0)) == (0, 0, 0, 0) and img.getpixel((0, 0))[3] == 255


@pytest.mark.parametrize("bg", ["#00000000", "transparent", "00000000"])
def test_scene_bg_spellings_of_clear_agree(tmp_path, bg):
    assert run("scene", "-o", tmp_path / "s.png", "--size", "2x2", "--scale", "1", "--bg", bg) == 0
    assert set(pxart.pixels(Image.open(tmp_path / "s.png").convert("RGBA"))) == {(0, 0, 0, 0)}


def test_scene_bg_without_hash(tmp_path):
    assert run("scene", "-o", tmp_path / "s.png", "--size", "1x1", "--scale", "1", "--bg", "ff0000") == 0
    assert Image.open(tmp_path / "s.png").convert("RGBA").getpixel((0, 0)) == (255, 0, 0, 255)


@pytest.mark.parametrize("cmd", ["scene", "render", "sheet"])
def test_bad_bg_is_a_coded_error_not_a_crash(tmp_path, cmd):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    msg = run_err(cmd, p if cmd != "scene" else f"{p}@0,0", "-o", tmp_path / "x.png", "--bg", "red")
    assert "E_BAD_COLOR" in msg and "--bg 'red'" in msg and "transparent" in msg
    assert not (tmp_path / "x.png").exists()


@pytest.mark.parametrize("cmd", ["render", "sheet"])
def test_render_and_sheet_bg_transparent(tmp_path, cmd):
    p = write(tmp_path, "a.px", "k #000000\nk.\n")
    assert run(cmd, p, "-o", tmp_path / "x.png", "--bg", "transparent", "--scale", "1") == 0
    img = Image.open(tmp_path / "x.png").convert("RGBA")
    assert (0, 0, 0, 0) in set(pxart.pixels(img))


def test_tint_transparent_changes_nothing(tmp_path):
    img = Image.new("RGBA", (2, 1), (10, 20, 30, 255))
    img.save(tmp_path / "a.png")
    assert run("tint", tmp_path / "a.png", "transparent", "-o", tmp_path / "b.png") == 0
    assert pxart.pixels(Image.open(tmp_path / "b.png").convert("RGBA")) == pxart.pixels(img)


def test_palette_add_transparent_key(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    assert run("palette", p, "--add", "t=transparent") == 0
    assert pxart.parse(p).palette["t"] == (0, 0, 0, 0) and "t transparent" in p.read_text()
    assert "E_BAD_COLOR" in run_err("palette", p, "--add", "z=clear")


def test_parse_color_spellings():
    assert pxart.parse_color("transparent") == (0, 0, 0, 0)
    assert pxart.parse_color("#010203") == (1, 2, 3, 255) == pxart.parse_color("010203")
    assert pxart.parse_color("#01020304") == (1, 2, 3, 4)
    with pytest.raises(pxart.PxError) as e:
        pxart.parse_color("#12345", "--bg")
    assert codes(e) == ["E_BAD_COLOR"]


# ---------------------------------------------------------------- loop I: removing a group's last frame drops its @anim/@still

ORPH = ("k #000000\n@anim walk ms=90\n@anim idle ms=200\n@still ui\n\n@frame walk/0\nk\n@frame walk/1\nk\n"
        "@frame idle/0\nk\n@frame ui/a\nk\n@frame ui/b\nk\n")


def test_rm_every_frame_of_a_group_by_id_drops_its_anim(tmp_path, capsys):
    p = write(tmp_path, "o.px", ORPH)
    assert run("frames", p, "--rm", "walk/0", "walk/1") == 0
    assert capsys.readouterr().out == f"removed walk/0, walk/1; removed @anim walk (no frames left); wrote {p}\n"
    doc = pxart.parse(p)
    assert list(doc.anims) == ["idle"] and "@anim walk" not in p.read_text()


def test_rm_selection_drops_its_still(tmp_path, capsys):
    p = write(tmp_path, "o.px", ORPH)
    assert run("frames", f"{p}:ui", "--rm") == 0
    assert "removed @still ui (no frames left)" in capsys.readouterr().out
    assert pxart.parse(p).stills == [] and "@still" not in p.read_text()


def test_rm_part_of_a_group_keeps_its_anim(tmp_path, capsys):
    p = write(tmp_path, "o.px", ORPH)
    assert run("frames", p, "--rm", "walk/0") == 0
    assert "no frames left" not in capsys.readouterr().out
    assert "@anim walk ms=90" in p.read_text()


def test_rm_keeps_an_unrelated_orphan(tmp_path):
    # Only the groups this --rm empties lose their lines; an @anim that was already orphaned is left for check.
    p = write(tmp_path, "o.px", "k #000000\n@anim gone ms=5\n" + ORPH.split("\n", 1)[1])
    assert run("frames", p, "--rm", "idle/0") == 0
    assert list(pxart.parse(p).anims) == ["gone", "walk"]


def test_rm_everything_leaves_a_palette_only_file_without_orphans(tmp_path):
    p = write(tmp_path, "o.px", ORPH)
    assert run("frames", p, "--rm", "walk/0", "walk/1", "idle/0", "ui/a", "ui/b") == 0
    assert p.read_text() == "k #000000\n"


def test_rm_star_still_is_kept(tmp_path):
    p = write(tmp_path, "o.px", "k #000000\n@still *\n@frame a\nk\n@frame b\nk\n")
    assert run("frames", p, "--rm", "a") == 0
    assert pxart.parse(p).stills == ["*"]


def test_rm_orphan_output_is_a_byte_exact_rewrite(tmp_path):
    p = write(tmp_path, "o.px", "k #000000\n# walk timing\n@anim walk ms=90\n@anim idle ms=200\n\n@frame walk/0\nk\n"
              "@frame idle/0\nk\n")
    assert run("frames", p, "--rm", "walk/0") == 0
    # The comment goes with its @anim line; the blank line went with walk/0's @frame, as any --rm does.
    assert p.read_text() == "k #000000\n@anim idle ms=200\n@frame idle/0\nk\n"


def test_check_notes_orphan_anim_and_still(tmp_path, capsys):
    p = write(tmp_path, "o.px", "k #000000\n@anim gone ms=5\n@still nothing\n@frame a/0\nk\n")
    assert run("check", p) == 0
    out = capsys.readouterr().out
    assert f"{p}: line 2: '@anim gone' names a group with no frames" in out
    assert f"{p}: line 3: '@still nothing' names a group with no frames" in out
    assert "check --strict fails on it" in out


def test_check_strict_fails_on_orphans(tmp_path, capsys):
    p = write(tmp_path, "o.px", "k #000000\n@anim gone ms=5\n@still nothing\n@frame a/0\nk\n")
    assert run("check", "--strict", p) == 1
    out = capsys.readouterr().out
    assert f"FAIL {p}:2: E_SELECT: '@anim gone' names a group with no frames" in out
    assert f"FAIL {p}:3: E_SELECT: '@still nothing' names a group with no frames" in out


def test_check_strict_passes_without_orphans(tmp_path, capsys):
    p = write(tmp_path, "o.px", ORPH)
    assert run("check", "--strict", p) == 0
    assert "no frames" not in capsys.readouterr().out


def test_check_star_still_is_never_an_orphan(tmp_path, capsys):
    p = write(tmp_path, "o.px", "k #000000\n@still *\nk\n")
    assert run("check", "--strict", p) == 0


def test_orphans_helper(tmp_path):
    doc = pxart.parse(write(tmp_path, "o.px", "k #000000\n@anim x\n@anim a\n@still y\n@frame a/0\nk\n"))
    assert pxart.orphans(doc) == [("@anim x", 2), ("@still y", 4)]


# ---------------------------------------------------------------- loop I: --move with a group name

def test_move_a_group_name_says_how_groups_move(tmp_path):
    p = write(tmp_path, "o.px", ORPH)
    msg = run_err("frames", p, "--move", "walk", "--after", "idle/0")
    assert "E_BAD_ARG" in msg and "'walk' is a group (walk/0, walk/1)" in msg
    assert "frames FILE:GROUP --before/--after ID" in msg and f"frames {p}:walk --after idle/0" in msg
    assert p.read_text() == ORPH


def test_move_a_group_name_with_before(tmp_path):
    p = write(tmp_path, "o.px", ORPH)
    assert f"frames {p}:ui --before walk/0" in run_err("frames", p, "--move", "ui", "--before", "walk/0")


def test_move_an_unknown_id_is_still_select(tmp_path):
    p = write(tmp_path, "o.px", ORPH)
    msg = run_err("frames", p, "--move", "nope", "--after", "idle/0")
    assert "E_SELECT" in msg and "is a group" not in msg


def test_move_a_frame_still_works(tmp_path):
    p = write(tmp_path, "o.px", ORPH)
    assert run("frames", p, "--move", "idle/0", "--before", "walk/0") == 0
    assert [f.id for f in pxart.parse(p).frames][:2] == ["idle/0", "walk/0"]


# ---------------------------------------------------------------- loop I: -h states default scales

def test_help_states_default_scales():
    doc = pxart.__doc__
    assert "Default --scale 4 (not render's 8)" in doc and "(default --scale 8;" in doc


# ---------------------------------------------------------------- loop I: %base keeps an item in the base palette

NIGHT = "k #102030\ny #f0c040\n@variant night\ny #203040\n\n@frame lamp\ny\n@frame wall\nk\n"


def px1(path, xy):
    return Image.open(path).convert("RGBA").getpixel(xy)


def test_scene_item_base_ignores_variant(tmp_path):
    p = write(tmp_path, "l.px", NIGHT)
    assert run("scene", "-o", tmp_path / "s.png", "--size", "2x1", "--scale", "1", "--variant", "night",
               f"{p}:lamp%base@0,0", f"{p}:lamp@1,0") == 0
    assert px1(tmp_path / "s.png", (0, 0))[:3] == (0xF0, 0xC0, 0x40)
    assert px1(tmp_path / "s.png", (1, 0))[:3] == (0x20, 0x30, 0x40)


def test_scene_legend_base_ignores_variant(tmp_path):
    write(tmp_path, "l.px", NIGHT)
    m = write(tmp_path, "r.map", "L l.px:lamp%base\nl l.px:lamp\n\nLl\n")
    assert run("scene", "-o", tmp_path / "s.png", "--map", m, "--tile", "1x1", "--scale", "1", "--variant", "night") == 0
    assert px1(tmp_path / "s.png", (0, 0))[:3] == (0xF0, 0xC0, 0x40)
    assert px1(tmp_path / "s.png", (1, 0))[:3] == (0x20, 0x30, 0x40)


def test_base_with_flip_suffix(tmp_path):
    p = write(tmp_path, "l.px", "y #f0c040\nk #000000\n@variant night\ny #203040\n\n@frame a\nyk\n")
    assert run("scene", "-o", tmp_path / "s.png", "--size", "2x1", "--scale", "1", "--variant", "night",
               f"{p}:a%base+h@0,0") == 0
    assert px1(tmp_path / "s.png", (1, 0))[:3] == (0xF0, 0xC0, 0x40)


def test_base_without_variant_is_base(tmp_path):
    p = write(tmp_path, "l.px", NIGHT)
    (it,) = pxart.items(f"{p}:lamp%base")
    assert it.img.getpixel((0, 0))[:3] == (0xF0, 0xC0, 0x40)


def test_base_works_for_a_file_with_no_variants(tmp_path):
    p = write(tmp_path, "l.px", "k #000000\nk\n")
    assert run("render", f"{p}%base", "-o", tmp_path / "r.png") == 0


def test_export_base(tmp_path):
    p = write(tmp_path, "l.px", NIGHT)
    assert run("export", f"{p}:lamp%base", "--frames", tmp_path / "f", "--variant", "night") == 0
    assert px1(tmp_path / "f" / "lamp.png", (0, 0))[:3] == (0xF0, 0xC0, 0x40)


def test_check_notes_variant_named_base(tmp_path, capsys):
    p = write(tmp_path, "l.px", "k #000000\n@variant base\nk #ffffff\n\nk\n")
    assert run("check", p) == 0
    assert "'@variant base' can't be picked" in capsys.readouterr().out


def test_help_documents_percent_base():
    assert "%base is the base palette" in pxart.__doc__


# ---------------------------------------------------------------- loop I: sheet doesn't count the --bg backdrop

def test_sheet_color_count_skips_bg_filled_png(tmp_path):
    img = Image.new("RGBA", (6, 6), (0x3A, 0x3A, 0x44, 255))
    img.putpixel((2, 2), (255, 0, 0, 255)); img.putpixel((3, 3), (0, 255, 0, 255))
    img.save(tmp_path / "scene.png")
    its = pxart.all_items([str(tmp_path / "scene.png")])
    assert pxart.n_colors(its[0], "#3a3a44") == 2
    assert pxart.n_colors(its[0], (0x3A, 0x3A, 0x44, 255)) == 2
    assert pxart.n_colors(its[0], "#000000") == 3  # another bg: the fill is a color of the art


def test_sheet_color_count_needs_all_four_corners(tmp_path):
    img = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
    img.putpixel((3, 3), (9, 9, 9, 255))
    img.save(tmp_path / "a.png")
    (it,) = pxart.all_items([str(tmp_path / "a.png")])
    assert pxart.n_colors(it, "#000000") == 2


def test_sheet_color_count_of_px_is_unchanged(tmp_path):
    p = write(tmp_path, "a.px", "k #3a3a44\nr #ff0000\nkk\nkr\n")
    (it,) = pxart.all_items([str(p)])
    assert pxart.n_colors(it, "#3a3a44") == 2  # a sprite's own color is never the backdrop


def test_sheet_label_uses_the_count(tmp_path):
    img = Image.new("RGBA", (6, 6), (0x47, 0x2D, 0x3C, 255)); img.putpixel((1, 1), (255, 0, 0, 255))
    img.save(tmp_path / "s.png")
    assert run("sheet", tmp_path / "s.png", "-o", tmp_path / "a.png", "--bg", "#472d3c") == 0
    assert run("sheet", tmp_path / "s.png", "-o", tmp_path / "b.png") == 0
    a, b = (pxart.pixels(Image.open(tmp_path / n).convert("RGBA")) for n in ("a.png", "b.png"))
    assert a != b


# ---------------------------------------------------------------- loop I: 'rows Y+ still' needs identical rows; percents

LEGS_NUDGED = ["..kbbbbk..", "..kbkkbk..", "..kbkkbk..", "..kkk.kkkk"]  # one foot pixel more than LEGS


def test_breathing_with_identical_legs_is_still(tmp_path):
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, BREATHE_0, BREATHE_1)
    assert still == 9 and (dx, dy) == (0, -1)


def test_one_changed_pixel_below_the_split_keeps_the_shift(tmp_path):
    # The loop I walk: the body bobbed and a leg moved 1px. Under the old near-still rule this read
    # 'rows 10+ still'; with the legs not identical, the shift is the honest reading.
    b = BODY + [BODY[-1]] + LEGS[:3] + [LEGS_NUDGED[3]]
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, BREATHE_0, b)
    assert (dx, dy) == (0, -1) and still is None and n_shift < n_none


def test_identical_tail_below_changed_rows_picks_the_first_identical_row(tmp_path):
    a = [EMPTY] + BODY + LEGS
    b = BODY + [BODY[-1]] + ["..kbbbbk..", "..kbkkbk..", "..kbkkbk..", "..kkk.kkk."]
    b[10] = "..kbbbbbk."  # a changed pixel in row 10: rows 11+ are the identical tail
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, a, b)
    assert still is None or still >= 11


def test_motion_still_rows_are_pixel_identical(tmp_path):
    doc = pxart.parse(anim_file(tmp_path, BREATHE_0, BREATHE_1, name="st.px"))
    a, b = (doc.image(f) for f in doc.frames)
    still = pxart.motion(a, b)[4]
    w = a.width
    assert pxart.pixels(a)[still * w:] == pxart.pixels(b)[still * w:]


def test_no_opaque_identical_tail_is_not_still(tmp_path):
    # Identical rows that are all transparent (empty space under the feet) don't make 'rows still'.
    a = BODY + LEGS + [EMPTY, EMPTY]
    b = [EMPTY] + BODY + LEGS + [EMPTY]
    assert motion_of(tmp_path, a, b)[4] is None


def test_walk_line_after_nudged_leg_prints_the_shift(tmp_path, capsys):
    b = BODY + [BODY[-1]] + LEGS[:3] + [LEGS_NUDGED[3]]
    lines = anim_lines(tmp_path, capsys, BREATHE_0, b)
    assert "vs idle/0: shift +0,-1 then " in lines[1] and "rows" not in lines[1]


def test_percent_is_of_the_frames_opaque_pixels(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, WALK_0, WALK_1)
    n_shift = motion_of(tmp_path, WALK_0, WALK_1)[2]
    op = sum(c != "." for r in WALK_1 for c in r)
    assert f"then {n_shift}px ({round(100 * n_shift / op)}%)" in lines[1]


def test_percent_rounds_half_up(tmp_path, capsys):
    # 1 changed of 8 opaque = 12.5% -> 13%
    a = ["kkkk", "kkkk"]
    b = ["kkkk", "kkky"]
    lines = anim_lines(tmp_path, capsys, a, b)
    assert lines[1].endswith("shift +0,+0 then 1px (13%)")


def test_percent_of_an_empty_frame_is_left_out(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, ["k."], [".."])
    assert "then 0px (no shift: 1px)" in lines[1] and "%" not in lines[1]  # pushing k off the edge empties it


def test_percent_on_the_strip_label(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, BOB_0, BOB_1)
    assert all("then 0px (0%)" in l for l in lines)


def test_percent_in_rows_still_line_is_the_unshifted_count(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, BREATHE_0, BREATHE_1)
    n_none = motion_of(tmp_path, BREATHE_0, BREATHE_1)[3]
    assert f"no shift then {pc(n_none, BREATHE_1)} (rows 9+ still;" in lines[1]


def test_help_documents_identical_rows():
    assert "rows Y down identical, 0 px changed" in pxart.__doc__ and "even 1px keeps the shift" in pxart.__doc__


# ---------------------------------------------------------------- loop I: drawing primitives (golden grids)

def canvas(tmp_path, w, h, name="d.px", extra=""):
    """A file with one blank frame 'a' of w x h and keys k (black) and w (white)."""
    return write(tmp_path, name, "k #000000\nw #ffffff\n" + extra + "@frame a\n" + ("." * w + "\n") * h)


def grid_of(p, fid="a"):
    return pxart.parse(p).get(fid).grid


def pts_grid(pts, w, h):
    return ["".join("k" if (x, y) in set(pts) else "." for x in range(w)) for y in range(h)]


LINE_OCTANTS = {
    (8, 3): ['kk.......', '..kkk....', '.....kk..', '.......kk'],
    (3, 8): ['k...', 'k...', '.k..', '.k..', '.k..', '..k.', '..k.', '...k', '...k'],
    (-3, 8): ['...k', '...k', '..k.', '..k.', '.k..', '.k..', '.k..', 'k...', 'k...'],
    (-8, 3): ['.......kk', '.....kk..', '..kkk....', 'kk.......'],
    (-8, -3): ['kk.......', '..kkk....', '.....kk..', '.......kk'],
    (-3, -8): ['k...', 'k...', '.k..', '.k..', '.k..', '..k.', '..k.', '...k', '...k'],
    (3, -8): ['...k', '...k', '..k.', '..k.', '.k..', '.k..', '.k..', 'k...', 'k...'],
    (8, -3): ['.......kk', '.....kk..', '..kkk....', 'kk.......'],
    (8, 0): ['kkkkkkkkk'],
    (0, 8): ['k'] * 9,
    (8, 8): ['k........', '.k.......', '..k......', '...k.....', '....k....', '.....k...', '......k..', '.......k.', '........k'],
    (-8, 8): ['........k', '.......k.', '......k..', '.....k...', '....k....', '...k.....', '..k......', '.k.......', 'k........'],
}


@pytest.mark.parametrize("end", list(LINE_OCTANTS))
def test_line_octants_golden(tmp_path, end):
    p = canvas(tmp_path, 17, 17)
    assert run("line", f"{p}:a", "k", "8,8", f"{8 + end[0]},{8 + end[1]}") == 0
    g = grid_of(p)
    ys = [y for y, r in enumerate(g) if "k" in r]
    xs = [x for r in g for x, c in enumerate(r) if c == "k"]
    assert [r[min(xs):max(xs) + 1] for r in g[min(ys):max(ys) + 1]] == LINE_OCTANTS[end]


@pytest.mark.parametrize("end", list(LINE_OCTANTS))
def test_line_is_the_same_drawn_backwards(end):
    assert set(pxart.line_points(0, 0, *end)) == set(pxart.line_points(*end, 0, 0))


@pytest.mark.parametrize("dx,dy", [(a, b) for a in range(-7, 8) for b in range(-7, 8)])
def test_line_is_8_connected_one_pixel_per_step(dx, dy):
    pts = pxart.line_points(0, 0, dx, dy)
    assert len(pts) == len(set(pts)) == max(abs(dx), abs(dy)) + 1
    assert pts[0] in {(0, 0), (dx, dy)} and pts[-1] in {(0, 0), (dx, dy)}
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        assert max(abs(x1 - x0), abs(y1 - y0)) == 1  # no gaps and no doubled (L) corners


@pytest.mark.parametrize("dx,dy", [(a, b) for a in range(-7, 8) for b in range(-7, 8)
                                   if not (max(abs(a), abs(b)) % 2 == 0 and min(abs(a), abs(b)) % 2 == 1)])
def test_line_is_symmetric_turned_180(dx, dy):
    # Except where the middle pixel is a true tie (even length, odd rise), the line looks the same upside down.
    pts = set(pxart.line_points(0, 0, dx, dy))
    assert {(dx - x, dy - y) for x, y in pts} == pts


def test_line_even_runs():
    assert pts_grid(pxart.line_points(0, 0, 8, 2), 9, 3) == ["kkk......", "...kkk...", "......kkk"]
    assert pts_grid(pxart.line_points(0, 0, 7, 3), 8, 4) == ["kk......", "..kk....", "....kk..", "......kk"]
    assert pts_grid(pxart.line_points(0, 0, 5, 2), 6, 3) == ["kk....", "..kk..", "....kk"]


def test_line_single_point(tmp_path):
    p = canvas(tmp_path, 3, 3)
    assert run("line", f"{p}:a", "k", "1,1", "1,1") == 0
    assert grid_of(p) == ["...", ".k.", "..."]


def test_line_width_2_goes_down(tmp_path):
    p = canvas(tmp_path, 7, 6)
    assert run("line", f"{p}:a", "k", "0,1", "6,3", "--width", "2") == 0
    assert grid_of(p) == [".......", "kk.....", "kkkkk..", "..kkkkk", ".....kk", "......."]


def test_line_width_3_steep_goes_across(tmp_path):
    p = canvas(tmp_path, 6, 7)
    assert run("line", f"{p}:a", "k", "1,0", "3,6", "--width", "3") == 0
    assert grid_of(p) == ["kkk...", "kkk...", ".kkk..", ".kkk..", ".kkk..", "..kkk.", "..kkk."]


def test_line_width_must_be_positive(tmp_path):
    p = canvas(tmp_path, 3, 3)
    assert "E_BAD_ARG" in run_err("line", f"{p}:a", "k", "0,0", "2,2", "--width", "0")


def test_line_negative_start_is_clipped_with_a_note(tmp_path, capsys):
    p = canvas(tmp_path, 4, 4)
    assert run("line", f"{p}:a", "k", "-2,0", "3,0") == 0
    out = capsys.readouterr().out
    assert "note: 2 px of the line fall outside a (4x4) and were clipped" in out and "painted 4 px" in out
    assert grid_of(p)[0] == "kkkk"


def test_line_bad_point_is_bad_arg(tmp_path):
    p = canvas(tmp_path, 3, 3)
    msg = run_err("line", f"{p}:a", "k", "0,0", "2")
    assert msg.startswith("line: E_BAD_ARG: the end wants x,y")


def test_line_unknown_key(tmp_path):
    p = canvas(tmp_path, 3, 3)
    before = p.read_text()
    msg = run_err("line", f"{p}:a", "q", "0,0", "2,2")
    assert "E_SELECT" in msg and "key 'q' not in palette" in msg and p.read_text() == before


def test_line_dot_erases(tmp_path):
    p = write(tmp_path, "d.px", "k #000000\n@frame a\nkkk\n")
    assert run("line", f"{p}:a", ".", "0,0", "1,0") == 0
    assert grid_of(p) == ["..k"]


def test_line_on_every_selected_frame(tmp_path):
    p = write(tmp_path, "d.px", "k #000000\n@frame w/0\n...\n@frame w/1\n...\n@frame other\n...\n")
    assert run("line", f"{p}:w", "k", "0,0", "2,0") == 0
    doc = pxart.parse(p)
    assert doc.get("w/0").grid == doc.get("w/1").grid == ["kkk"] and doc.get("other").grid == ["..."]


def test_line_rewrites_only_changed_rows(tmp_path):
    p = write(tmp_path, "d.px", "# hi\nk #000000\n\n@frame a\n...\n# keep\n...\n")
    assert run("line", f"{p}:a", "k", "0,1", "2,1") == 0
    assert p.read_text() == "# hi\nk #000000\n\n@frame a\n...\n# keep\nkkk\n"


def test_line_no_change(tmp_path, capsys):
    p = write(tmp_path, "d.px", "k #000000\n@frame a\nkkk\n")
    assert run("line", f"{p}:a", "k", "0,0", "2,0") == 0
    assert capsys.readouterr().out == f"painted 0 px; no change: {p}\n"


def test_line_dash_o_writes_a_copy(tmp_path):
    p = canvas(tmp_path, 3, 1)
    before = p.read_text()
    assert run("line", f"{p}:a", "k", "0,0", "2,0", "-o", tmp_path / "o.px") == 0
    assert p.read_text() == before and grid_of(tmp_path / "o.px") == ["kkk"]


def test_negative_coordinates_are_not_options(tmp_path):
    p = canvas(tmp_path, 3, 3)
    assert run("line", f"{p}:a", "k", "-1,-1", "1,1") == 0
    assert run("rect", f"{p}:a", "w", "-1,-1,2,2", "--fill") == 0
    assert run("ellipse", f"{p}:a", "k", "-1,-1,1,1") == 0
    assert run("arc", f"{p}:a", "k", "-1,1,2", "-90,90") == 0


# rect

def test_rect_outline_golden(tmp_path):
    p = canvas(tmp_path, 6, 5)
    assert run("rect", f"{p}:a", "k", "1,1,4,3") == 0
    assert grid_of(p) == ["......", ".kkkk.", ".k..k.", ".kkkk.", "......"]


def test_rect_fill_golden(tmp_path):
    p = canvas(tmp_path, 4, 3)
    assert run("rect", f"{p}:a", "k", "1,0,2,3", "--fill") == 0
    assert grid_of(p) == [".kk.", ".kk.", ".kk."]


def test_rect_one_pixel(tmp_path):
    p = canvas(tmp_path, 3, 3)
    assert run("rect", f"{p}:a", "k", "1,1,1,1") == 0
    assert grid_of(p) == ["...", ".k.", "..."]


def test_rect_clipped(tmp_path, capsys):
    p = canvas(tmp_path, 3, 3)
    assert run("rect", f"{p}:a", "k", "1,1,4,4") == 0
    assert grid_of(p) == ["...", ".kk", ".k."]
    assert "px of the rect fall outside" in capsys.readouterr().out


@pytest.mark.parametrize("spec", ["1,1,0,2", "1,1,2", "a,b,c,d", "1,1,-2,2"])
def test_rect_bad(tmp_path, spec):
    p = canvas(tmp_path, 3, 3)
    assert "E_BAD_ARG" in run_err("rect", f"{p}:a", "k", spec)


# ellipse

ELLIPSES = {
    (1, 1): ['k'],
    (2, 2): ['kk', 'kk'],
    (3, 3): ['.k.', 'k.k', '.k.'],
    (4, 4): ['.kk.', 'k..k', 'k..k', '.kk.'],
    (5, 5): ['.kkk.', 'k...k', 'k...k', 'k...k', '.kkk.'],
    (6, 6): ['..kk..', '.k..k.', 'k....k', 'k....k', '.k..k.', '..kk..'],
    (7, 7): ['..kkk..', '.k...k.', 'k.....k', 'k.....k', 'k.....k', '.k...k.', '..kkk..'],
    (8, 8): ['..kkkk..', '.k....k.', 'k......k', 'k......k', 'k......k', 'k......k', '.k....k.', '..kkkk..'],
    (8, 4): ['..kkkk..', 'kk....kk', 'kk....kk', '..kkkk..'],
    (4, 8): ['.kk.', '.kk.', 'k..k', 'k..k', 'k..k', 'k..k', '.kk.', '.kk.'],
    (7, 3): ['.kkkkk.', 'k.....k', '.kkkkk.'],
    (6, 5): ['.kkkk.', 'k....k', 'k....k', 'k....k', '.kkkk.'],
    (1, 4): ['k', 'k', 'k', 'k'],
    (2, 5): ['kk'] * 5,
    (5, 2): ['kkkkk'] * 2,
}


def ellipse_arg(w, h, x=0, y=0):
    """cx,cy,rx,ry for the w x h ellipse with its box at x,y."""
    f = lambda v: str(int(v)) if v == int(v) else str(v)
    rx, ry = (w - 1) / 2, (h - 1) / 2
    return ",".join(f(v) for v in (x + rx, y + ry, rx, ry))


@pytest.mark.parametrize("size", list(ELLIPSES))
def test_ellipse_golden(tmp_path, size):
    w, h = size
    p = canvas(tmp_path, w, h)
    assert run("ellipse", f"{p}:a", "k", ellipse_arg(w, h)) == 0
    assert grid_of(p) == ELLIPSES[size]


@pytest.mark.parametrize("size", list(ELLIPSES))
def test_ellipse_fill_golden_is_the_outline_filled_in(tmp_path, size):
    w, h = size
    p = canvas(tmp_path, w, h)
    assert run("ellipse", f"{p}:a", "k", ellipse_arg(w, h), "--fill") == 0
    want = [r[:r.find("k")] + "k" * (r.rfind("k") - r.find("k") + 1) + r[r.rfind("k") + 1:] for r in ELLIPSES[size]]
    assert grid_of(p) == want


@pytest.mark.parametrize("w", range(1, 25))
@pytest.mark.parametrize("h", range(1, 25))
def test_ellipse_properties(w, h):
    o = pxart.ellipse_points(0, 0, w - 1, h - 1)
    f = pxart.ellipse_points(0, 0, w - 1, h - 1, fill=True)
    assert o <= f and all(0 <= x < w and 0 <= y < h for x, y in f)          # inside its box
    assert {x for x, _ in o} == set(range(w)) and {y for _, y in o} == set(range(h))  # touches every side
    assert {(w - 1 - x, y) for x, y in o} == o and {(x, h - 1 - y) for x, y in o} == o  # mirror-symmetric
    if w > 2 and h > 2:
        for x, y in o:  # thin: no L-shaped doubled corner (a pixel with a side neighbor each way and no diagonal)
            for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                assert not ((x + dx, y) in o and (x, y + dy) in o and (x + dx, y + dy) not in o), (x, y)
    seen, todo = set(), [min(o)]
    while todo:  # 8-connected: no stray pixels
        q = todo.pop()
        if q in seen:
            continue
        seen.add(q)
        todo += [(q[0] + a, q[1] + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (q[0] + a, q[1] + b) in o]
    assert seen == o
    rows = {}
    for x, y in f:
        rows.setdefault(y, []).append(x)
    assert all(sorted(xs) == list(range(min(xs), max(xs) + 1)) for xs in rows.values())  # fill has no holes


def test_ellipse_even_size_with_halves(tmp_path):
    p = canvas(tmp_path, 8, 8)
    assert run("ellipse", f"{p}:a", "k", "3.5,4.5,3.5,2.5") == 0
    assert grid_of(p) == ["........", "........", "..kkkk..", ".k....k.", "k......k", "k......k", ".k....k.",
                          "..kkkk.."]


def test_ellipse_off_the_frame_is_clipped(tmp_path, capsys):
    p = canvas(tmp_path, 4, 4)
    assert run("ellipse", f"{p}:a", "k", "0,0,3,3", "--fill") == 0
    assert grid_of(p)[0] == "kkkk" and "fall outside a (4x4)" in capsys.readouterr().out


@pytest.mark.parametrize("spec", ["1.5,1,1,1", "1,1,1.5,1", "1,1,-1,1", "1,1,1", "1,1,1.25,1", "x,1,1,1"])
def test_ellipse_bad(tmp_path, spec):
    p = canvas(tmp_path, 3, 3)
    assert "E_BAD_ARG" in run_err("ellipse", f"{p}:a", "k", spec)


def test_ellipse_half_spec_message_explains(tmp_path):
    p = canvas(tmp_path, 3, 3)
    assert "both ending in .5" in run_err("ellipse", f"{p}:a", "k", "1.5,1,1,1")


# arc

ARCS = {
    (0, 90): ['....kk...', '......k..', '.......k.', '........k', '........k', '.........', '.........', '.........', '.........'],
    (90, 180): ['...kk....', '..k......', '.k.......', 'k........', 'k........', '.........', '.........', '.........', '.........'],
    (180, 270): ['.........', '.........', '.........', '.........', 'k........', 'k........', '.k.......', '..k......', '...kk....'],
    (270, 360): ['.........', '.........', '.........', '.........', '........k', '........k', '.......k.', '......k..', '....kk...'],
    (300, 60): ['.........', '......k..', '.......k.', '........k', '........k', '........k', '.......k.', '......k..', '.........'],
    (45, 135): ['...kkk...', '..k...k..', '.........', '.........', '.........', '.........', '.........', '.........', '.........'],
    (0, 360): ['...kkk...', '..k...k..', '.k.....k.', 'k.......k', 'k.......k', 'k.......k', '.k.....k.', '..k...k..', '...kkk...'],
}


@pytest.mark.parametrize("angles", list(ARCS))
def test_arc_quadrants_golden(tmp_path, angles):
    p = canvas(tmp_path, 9, 9)
    assert run("arc", f"{p}:a", "k", "4,4,4", f"{angles[0]},{angles[1]}") == 0
    assert grid_of(p) == ARCS[angles]


def test_arc_quadrants_make_the_circle():
    quads = [pxart.arc_points(4, 4, 4, a, a + 90) for a in (0, 90, 180, 270)]
    assert set().union(*quads) == pxart.ellipse_points(0, 0, 8, 8)


def test_arc_full_turn_is_the_ellipse():
    assert pxart.arc_points(6, 6, 6, 10, 370) == pxart.ellipse_points(0, 0, 12, 12)
    assert pxart.arc_points(6, 6, 6, 0, -360) == pxart.ellipse_points(0, 0, 12, 12)


def test_arc_negative_start_wraps():
    assert pxart.arc_points(4, 4, 4, -60, 60) == pxart.arc_points(4, 4, 4, 300, 60)


def test_arc_width_golden(tmp_path):
    p = canvas(tmp_path, 11, 11)
    assert run("arc", f"{p}:a", "k", "5,5,5", "0,180", "--width", "2") == 0
    assert grid_of(p)[:6] == ['...kkkkk...', '..kkkkkkk..', '.kkk...kkk.', 'kkk.....kkk', 'kk.......kk', 'kk.......kk']
    assert grid_of(p)[6:] == ["." * 11] * 5


def test_arc_width_ring_has_no_gaps():
    ring = pxart.arc_points(10, 10, 10, 0, 360, 3)
    for y in range(21):
        for x in range(21):
            d = math.hypot(x - 10, y - 10)
            if 8.6 <= d <= 9.4:
                assert (x, y) in ring, (x, y)


def test_arc_even_circle_with_halves(tmp_path):
    p = canvas(tmp_path, 8, 8)
    assert run("arc", f"{p}:a", "k", "3.5,3.5,3.5", "0,180") == 0
    assert grid_of(p)[:4] == ['..kkkk..', '.k....k.', 'k......k', 'k......k'] and grid_of(p)[4] == "........"


@pytest.mark.parametrize("args", [["4,4,4", "0"], ["4,4,4", "a,b"], ["4,4", "0,90"], ["4,4,1.5", "0,90"]])
def test_arc_bad(tmp_path, args):
    p = canvas(tmp_path, 9, 9)
    assert "E_BAD_ARG" in run_err("arc", f"{p}:a", "k", *args)


# flood

HOLEY = ["kkkkkk", "k....k", "k.kk.k", "k.k..k", "kkkkkk"]


def holey(tmp_path, rows=HOLEY):
    return write(tmp_path, "h.px", "k #000000\nw #ffffff\n@frame a\n" + "\n".join(rows) + "\n")


def test_flood_fills_around_a_hole(tmp_path):
    p = holey(tmp_path)
    assert run("flood", f"{p}:a", "w", "1,1") == 0
    assert grid_of(p) == ["kkkkkk", "kwwwwk", "kwkkwk", "kwkwwk", "kkkkkk"]


def test_flood_the_border_key(tmp_path):
    p = holey(tmp_path)
    assert run("flood", f"{p}:a", "w", "0,0") == 0
    assert grid_of(p) == ["wwwwww", "w....w", "w.ww.w", "w.w..w", "wwwwww"]  # the kk/k spur touches the bottom


def test_flood_island_diagonal(tmp_path):
    rows = ["k...", ".k..", "..k.", "...k"]
    p = holey(tmp_path, rows)
    assert run("flood", f"{p}:a", "w", "0,0") == 0
    assert grid_of(p) == ["w...", ".k..", "..k.", "...k"]
    p = holey(tmp_path, rows)
    assert run("flood", f"{p}:a", "w", "0,0", "--diagonal") == 0
    assert grid_of(p) == ["w...", ".w..", "..w.", "...w"]


def test_flood_diagonal_leaks_through_corners(tmp_path):
    rows = ["..k.", ".k..", "k...", "...."]
    p = holey(tmp_path, rows)
    assert run("flood", f"{p}:a", "w", "0,0") == 0
    assert grid_of(p) == ["wwk.", "wk..", "k...", "...."]
    p = holey(tmp_path, rows)
    assert run("flood", f"{p}:a", "w", "0,0", "--diagonal") == 0
    assert grid_of(p) == ["wwkw", "wkww", "kwww", "wwww"]


def test_flood_same_key_is_no_change(tmp_path, capsys):
    p = holey(tmp_path)
    assert run("flood", f"{p}:a", "k", "0,0") == 0
    assert capsys.readouterr().out == f"painted 0 px; no change: {p}\n"


def test_flood_with_dot_erases_a_region(tmp_path):
    p = holey(tmp_path, ["kkkk", "k..k", "k.wk", "kkkk"])
    assert run("flood", f"{p}:a", ".", "0,0") == 0
    assert grid_of(p) == ["....", "....", "..w.", "...."]


def test_flood_outside_is_bad_arg(tmp_path):
    p = holey(tmp_path)
    msg = run_err("flood", f"{p}:a", "w", "6,0")
    assert "E_BAD_ARG" in msg and "6,0 is outside a (6x5)" in msg


def test_flood_count(tmp_path, capsys):
    p = holey(tmp_path)
    assert run("flood", f"{p}:a", "w", "1,1") == 0
    assert capsys.readouterr().out.startswith("painted 9 px; wrote")


def test_help_documents_drawing():
    doc = pxart.__doc__
    for s in ("DRAWING", "line FILE[:frame] KEY x0,y0 x1,y1 [--width N]", "rect FILE[:frame] KEY x,y,w,h [--fill]",
              "ellipse FILE[:frame] KEY cx,cy,rx,ry [--fill]", "arc FILE[:frame] KEY cx,cy,r a0,a1 [--width N]",
              "flood FILE[:frame] KEY x,y [--diagonal]"):
        assert s in doc, s


# ---------------------------------------------------------------- loop I: pivot=x,y on @frame and @anim

PIV = ("k #000000\nj #ffffff\n@anim walk ms=90 pivot=1,2\n\n@frame walk/0\n.k.\n.k.\nkkk\n"
       "@frame walk/1 pivot=2,1\n.kk\n.kk\n")


def test_pivot_parses_on_frame_and_anim(tmp_path):
    doc = pxart.parse(write(tmp_path, "p.px", PIV))
    assert doc.anims["walk"] == {"repeat": None, "ms": 90, "pivot": (1, 2)}
    assert doc.get("walk/1").pivot == (2, 1) and doc.get("walk/0").pivot is None
    assert doc.pivot(doc.get("walk/0")) == (1, 2) and doc.pivot(doc.get("walk/1")) == (2, 1)


def test_pivot_default_is_none(tmp_path):
    doc = pxart.parse(write(tmp_path, "p.px", MULTI))
    assert all(doc.pivot(f) is None for f in doc.frames) and "pivot" not in doc.anims["walk/down"]


def test_pivot_round_trips_byte_identically(tmp_path):
    p = write(tmp_path, "p.px", PIV)
    assert pxart.parse(p).text() == PIV


@pytest.mark.parametrize("line", ["@frame a pivot=3,4 ms=20", "@frame a ms=20 pivot=3,4", "@frame a pivot=-1,-2",
                                  "@frame a  pivot=0,0"])
def test_pivot_spellings_round_trip(tmp_path, line):
    text = f"k #000000\n{line}\nk\n"
    assert pxart.parse(write(tmp_path, "p.px", text)).text() == text


def test_pivot_canonical_order_when_rewritten(tmp_path):
    p = write(tmp_path, "p.px", "k #000000\n@frame a pivot=0,0 ms=20\nk\n")
    assert run("anim-set", f"{p}:a", "ms=30") == 0
    assert "@frame a ms=30 pivot=0,0\n" in p.read_text()


def test_pivot_negative_and_outside_parse(tmp_path):
    doc = pxart.parse(write(tmp_path, "p.px", "k #000000\n@frame a pivot=-3,9\nk\n"))
    assert doc.get("a").pivot == (-3, 9)


@pytest.mark.parametrize("bad", ["pivot=1", "pivot=a,b", "pivot=1,2,3", "pivot=", "pivot=1.5,2", "pivot=1;2"])
def test_pivot_bad_is_bad_arg(tmp_path, bad):
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(write(tmp_path, "p.px", f"k #000000\n@frame a {bad}\nk\n"))
    assert codes(e) == ["E_BAD_ARG"] and "must be x,y" in str(e.value)
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(write(tmp_path, "q.px", f"k #000000\n@anim a {bad}\n@frame a/0\nk\n"))
    assert codes(e) == ["E_BAD_ARG"]


def test_check_notes_pivot_outside_the_frame(tmp_path, capsys):
    p = write(tmp_path, "p.px", "k #000000\n@anim w pivot=0,5\n@frame w/0\nkk\n@frame w/1 pivot=1,0\nkk\n")
    assert run("check", p) == 0
    out = capsys.readouterr().out
    assert "frame w/0: pivot 0,5 (@anim w's) is outside its 2x1 frame" in out
    assert "w/1" not in out.split("pivot 0,5")[1].split("\n")[0]
    assert "frame w/1: pivot" not in out


def test_check_strict_passes_outside_pivot(tmp_path):
    p = write(tmp_path, "p.px", "k #000000\n@frame a pivot=5,5\nk\n")
    assert run("check", "--strict", p) == 0


def test_frames_lists_pivots(tmp_path, capsys):
    p = write(tmp_path, "p.px", PIV)
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "walk: 2 frame(s) [ms=90, pivot=1,2]" in out
    assert "walk/0  3x3  90ms  pivot 1,2  (line 5)" in out and "walk/1  3x2  90ms  pivot 2,1  (line 9)" in out


def test_frames_listing_without_pivots_is_unchanged(tmp_path, capsys):
    p = write(tmp_path, "m.px", MULTI)
    assert run("frames", p) == 0
    assert "pivot" not in capsys.readouterr().out


def test_anim_set_group_pivot(tmp_path, capsys):
    p = write(tmp_path, "p.px", PIV)
    assert run("anim-set", f"{p}:walk", "pivot=0,0") == 0
    out = capsys.readouterr().out
    assert "@anim walk ms=90 pivot=0,0; wrote" in out
    assert f"note: walk/1 keeps its own pivot=2,1 (anim-set {p}:walk/1 pivot= clears it)" in out
    assert p.read_text() == PIV.replace("@anim walk ms=90 pivot=1,2", "@anim walk ms=90 pivot=0,0")


def test_anim_set_frame_pivot(tmp_path):
    p = write(tmp_path, "p.px", PIV)
    assert run("anim-set", f"{p}:walk/0", "pivot=1,1") == 0
    assert p.read_text() == PIV.replace("@frame walk/0\n", "@frame walk/0 pivot=1,1\n")


def test_anim_set_frame_pivot_and_ms_together(tmp_path):
    p = write(tmp_path, "p.px", PIV)
    assert run("anim-set", f"{p}:walk/0", "pivot=1,1", "ms=40") == 0
    assert "@frame walk/0 ms=40 pivot=1,1\n" in p.read_text()


def test_anim_set_pivot_clears(tmp_path):
    p = write(tmp_path, "p.px", PIV)
    assert run("anim-set", f"{p}:walk/1", "pivot=") == 0
    assert run("anim-set", f"{p}:walk", "pivot=") == 0
    assert "pivot" not in p.read_text()


def test_anim_set_pivot_on_a_new_anim_line(tmp_path):
    p = write(tmp_path, "p.px", "k #000000\n@frame a/0\nk\n")
    assert run("anim-set", f"{p}:a", "pivot=0,0") == 0
    assert p.read_text() == "k #000000\n\n@anim a pivot=0,0\n@frame a/0\nk\n" or "@anim a pivot=0,0" in p.read_text()
    assert pxart.parse(p).pivot(pxart.parse(p).get("a/0")) == (0, 0)


@pytest.mark.parametrize("v", ["1", "a,b", "1,2,3", "1.5,1"])
def test_anim_set_bad_pivot(tmp_path, v):
    p = write(tmp_path, "p.px", PIV)
    before = p.read_text()
    msg = run_err("anim-set", f"{p}:walk", f"pivot={v}")
    assert "E_BAD_ARG" in msg and "must be x,y" in msg and p.read_text() == before


def test_anim_set_frame_still_refuses_direction(tmp_path):
    p = write(tmp_path, "p.px", PIV)
    msg = run_err("anim-set", f"{p}:walk/0", "direction=reverse")
    assert "takes only ms= and pivot=" in msg


def test_dup_copies_the_frame_pivot(tmp_path):
    p = write(tmp_path, "p.px", PIV)
    assert run("dup", f"{p}:walk/1", "walk/2") == 0
    assert pxart.parse(p).get("walk/2").pivot == (2, 1)


def test_flip_mirrors_the_frame_pivot(tmp_path):
    p = write(tmp_path, "p.px", PIV)
    assert run("flip", f"{p}:walk/1") == 0
    assert pxart.parse(p).get("walk/1").pivot == (0, 1)
    assert run("flip", f"{p}:walk/1", "--v") == 0
    assert pxart.parse(p).get("walk/1").pivot == (0, 0)


def test_flip_turns_an_inherited_pivot_into_the_frames_own(tmp_path):
    p = write(tmp_path, "p.px", "k #000000\n@anim w pivot=0,1\n@frame w/0\nk.\nkk\n@frame w/1\nk.\nkk\n")
    assert run("flip", f"{p}:w/0") == 0
    doc = pxart.parse(p)
    assert doc.get("w/0").pivot == (1, 1) and doc.get("w/1").pivot is None and doc.anims["w"]["pivot"] == (0, 1)


def test_flip_keeps_a_symmetric_inherited_pivot_inherited(tmp_path):
    p = write(tmp_path, "p.px", "k #000000\n@anim w pivot=1,2\n@frame w/0\n.k.\nkkk\nk.k\n")
    assert run("flip", f"{p}:w/0") == 0
    assert "@frame w/0\n" in p.read_text()


# GAMES-295: a whole group flipped together moves its @anim pivot, not per-frame copies.

GPIV = "k #000000\n@anim w ms=90 pivot=0,1\n\n@frame w/0\nk.\nkk\n@frame w/1\nk.\nk.\n@frame x\nk.\n..\n"


def pivot_pixels(path):
    """Each frame's pivot pixel's key (the pivot stays on its pixel through a move)."""
    doc = pxart.parse(path)
    return {f.id: doc.pivot(f) and f.grid[doc.pivot(f)[1]][doc.pivot(f)[0]] for f in doc.frames}


@pytest.mark.parametrize("target", ["{p}:w", "{p}"])
def test_flip_whole_group_moves_the_anim_pivot(tmp_path, capsys, target):
    p = write(tmp_path, "g.px", GPIV)
    assert run("flip", target.format(p=p)) == 0
    doc = pxart.parse(p)
    assert doc.anims["w"]["pivot"] == (1, 1) and all(f.pivot is None for f in doc.frames)
    assert "@anim w ms=90 pivot=1,1\n" in p.read_text() and "@frame w/0\n" in p.read_text()


def test_flip_whole_group_only_the_anim_line_changes(tmp_path):
    p = write(tmp_path, "g.px", GPIV)
    assert run("flip", f"{p}:w") == 0
    assert p.read_text() == GPIV.replace("pivot=0,1", "pivot=1,1").replace("k.\nkk\n@frame w/1\nk.\nk.",
                                                                           ".k\nkk\n@frame w/1\n.k\n.k")


def test_flip_whole_group_vertical(tmp_path):
    p = write(tmp_path, "g.px", GPIV)
    assert run("flip", f"{p}:w", "--v") == 0
    doc = pxart.parse(p)
    assert doc.anims["w"]["pivot"] == (0, 0) and all(f.pivot is None for f in doc.frames)


def test_flip_whole_group_twice_is_the_original(tmp_path):
    p = write(tmp_path, "g.px", GPIV)
    assert run("flip", f"{p}:w") == 0 and run("flip", f"{p}:w") == 0
    assert p.read_text() == GPIV


def test_flip_one_frame_of_group_still_gets_its_own(tmp_path):
    p = write(tmp_path, "g.px", GPIV)
    assert run("flip", f"{p}:w/1") == 0
    doc = pxart.parse(p)
    assert doc.anims["w"]["pivot"] == (0, 1) and doc.get("w/1").pivot == (1, 1) and doc.get("w/0").pivot is None


def test_flip_whole_group_keeps_frames_own_pivots_their_own(tmp_path):
    # w/1 has its own pivot: it flips on its @frame line; the others share the @anim's, which moves.
    p = write(tmp_path, "g.px", GPIV.replace("@frame w/1\n", "@frame w/1 pivot=0,0\n"))
    assert run("flip", f"{p}:w") == 0
    doc = pxart.parse(p)
    assert doc.anims["w"]["pivot"] == (1, 1) and doc.get("w/1").pivot == (1, 0) and doc.get("w/0").pivot is None


def test_flip_whole_group_of_mixed_sizes_gets_per_frame_pivots(tmp_path):
    # 2 wide and 3 wide: the anim pivot 0,1 mirrors to 1,1 and 2,1; no one point, so each frame gets its own.
    p = write(tmp_path, "g.px", "k #000000\n@anim w pivot=0,1\n@frame w/0\nk.\nkk\n@frame w/1\nk..\nkkk\n")
    assert run("flip", f"{p}:w") == 0
    doc = pxart.parse(p)
    assert doc.anims["w"]["pivot"] == (0, 1) and doc.get("w/0").pivot == (1, 1) and doc.get("w/1").pivot == (2, 1)


def test_flip_whole_group_renders_and_pivots_like_per_frame(tmp_path):
    # Same pixels, same pivot per frame as flipping each frame on its own.
    a = write(tmp_path, "a.px", GPIV)
    b = write(tmp_path, "b.px", GPIV)
    assert run("flip", f"{a}:w") == 0
    for fid in ("w/0", "w/1"):
        assert run("flip", f"{b}:{fid}") == 0
    da, db = pxart.parse(a), pxart.parse(b)
    for f in da.frames:
        assert f.grid == db.get(f.id).grid and da.pivot(f) == db.pivot(db.get(f.id))
    assert pivot_pixels(a) == pivot_pixels(b)


@pytest.mark.parametrize("cmd", [["rotate", "90"], ["rotate", "180"], ["rotate", "270"], ["transpose"]])
def test_turn_whole_group_moves_the_anim_pivot(tmp_path, cmd):
    p = write(tmp_path, "g.px", "k #000000\nj #ffffff\n@anim w pivot=2,0\n@frame w/0\nkkj\nk..\n"
              "@frame w/1\nk.j\n.k.\n")
    before = pivot_pixels(p)
    assert run(cmd[0], f"{p}:w", *cmd[1:]) == 0
    doc = pxart.parse(p)
    assert all(f.pivot is None for f in doc.frames) and doc.anims["w"]["pivot"] != (2, 0)
    assert pivot_pixels(p) == before == {"w/0": "j", "w/1": "j"}


def test_turn_one_frame_of_group_gets_its_own(tmp_path):
    p = write(tmp_path, "g.px", "k #000000\nj #ffffff\n@anim w pivot=2,0\n@frame w/0\nkkj\nk..\n"
              "@frame w/1\nk.j\n.k.\n")
    assert run("rotate", f"{p}:w/0", "90") == 0
    doc = pxart.parse(p)
    assert doc.anims["w"]["pivot"] == (2, 0) and doc.get("w/0").pivot is not None and doc.get("w/1").pivot is None
    assert pivot_pixels(p) == {"w/0": "j", "w/1": "j"}


def test_flip_group_symmetric_anim_pivot_unchanged(tmp_path):
    p = write(tmp_path, "g.px", "k #000000\n@anim w pivot=1,0\n@frame w/0\nkkk\n@frame w/1\nk.k\n")
    assert run("flip", f"{p}:w") == 0
    doc = pxart.parse(p)
    assert doc.anims["w"]["pivot"] == (1, 0) and all(f.pivot is None for f in doc.frames)


def test_flip_without_pivots_is_unchanged(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    assert run("flip", f"{p}:walk/down/1") == 0
    assert "pivot" not in p.read_text()


# alignment

def pivot_anim_file(tmp_path, p0="pivot=1,3", p1="pivot=1,1"):
    # A 3x4 frame and a 3x2 frame: bottom-centered they share a bottom row; by pivot they line up another way.
    return write(tmp_path, "pa.px", f"k #000000\n@anim a ms=100\n@frame a/0 {p0}\nk..\nk..\nk..\nk..\n"
                                    f"@frame a/1 {p1}\n.k.\n.k.\n")


def test_pivot_layout_lines_up_pivots(tmp_path):
    doc = pxart.parse(pivot_anim_file(tmp_path))
    its = [pxart.Item(f.id, doc.image(f), 100, doc, f) for f in doc.frames]
    w, h, spots = pxart.pivot_layout(its)
    assert spots == [(0, 0), (0, 2)] and (w, h) == (3, 4)  # pivots 1,3 and 1,1 both land at 1,3


def test_pivot_layout_none_without_pivots(tmp_path):
    doc = pxart.parse(write(tmp_path, "m.px", MULTI))
    assert pxart.pivot_layout([pxart.Item(f.id, doc.image(f), 100, doc, f) for f in doc.frames]) is None


def test_pivot_layout_mixed_uses_bottom_centre_pixel(tmp_path):
    doc = pxart.parse(pivot_anim_file(tmp_path, p1=""))
    its = [pxart.Item(f.id, doc.image(f), 100, doc, f) for f in doc.frames]
    w, h, spots = pxart.pivot_layout(its)
    assert spots == [(0, 0), (0, 2)]  # a/1's bottom-centre pixel 1,1 meets a/0's pivot 1,3


def test_pivot_layout_grows_the_canvas(tmp_path):
    doc = pxart.parse(pivot_anim_file(tmp_path, p0="pivot=0,0", p1="pivot=2,1"))
    its = [pxart.Item(f.id, doc.image(f), 100, doc, f) for f in doc.frames]
    w, h, spots = pxart.pivot_layout(its)
    assert spots == [(2, 1), (0, 0)] and (w, h) == (5, 5)


def test_pivot_layout_png_items_use_bottom_centre(tmp_path):
    Image.new("RGBA", (3, 2), (1, 1, 1, 255)).save(tmp_path / "a.png")
    doc = pxart.parse(pivot_anim_file(tmp_path))
    its = [pxart.Item("png", Image.open(tmp_path / "a.png").convert("RGBA"), 100),
           pxart.Item("a/0", doc.image(doc.get("a/0")), 100, doc, doc.get("a/0"))]
    w, h, spots = pxart.pivot_layout(its)
    assert spots == [(0, 2), (0, 0)]


def same_frames(tmp_path, p0, p1):
    return write(tmp_path, "sf.px", f"k #000000\n@frame a/0 {p0}\nk..\nkk.\n@frame a/1 {p1}\nk..\nkk.\n")


def strip_of(tmp_path, capsys, p):
    assert run("anim", f"{p}:a") == 0
    return [l.split(": ", 1)[1] for l in capsys.readouterr().out.splitlines() if " vs " in l]


def test_anim_aligns_by_pivot(tmp_path, capsys):
    # The same pixels with pivots 1px apart: lined up by pivot, the second frame is drawn 1px to the left.
    assert strip_of(tmp_path, capsys, same_frames(tmp_path, "pivot=0,1", "pivot=1,1"))[1] == \
        "shift -1,+0 then 0px (0%) (no shift: 4px)"


def test_anim_same_pivots_are_still(tmp_path, capsys):
    assert strip_of(tmp_path, capsys, same_frames(tmp_path, "pivot=2,0", "pivot=2,0"))[1] == "shift +0,+0 then 0px (0%)"


def test_anim_bottom_centre_without_pivots(tmp_path, capsys):
    assert strip_of(tmp_path, capsys, same_frames(tmp_path, "", ""))[1] == "shift +0,+0 then 0px (0%)"


def test_anim_anim_level_pivot_applies_to_every_frame(tmp_path, capsys):
    p = write(tmp_path, "sf.px", "k #000000\n@anim a pivot=0,1\n@frame a/0\nk..\nkk.\n@frame a/1 pivot=1,1\nk..\nkk.\n")
    assert strip_of(tmp_path, capsys, p)[1].startswith("shift -1,+0 then 0px")


def test_anim_gif_with_pivots_is_the_pivot_canvas(tmp_path, capsys):
    p = pivot_anim_file(tmp_path, p0="pivot=0,0", p1="pivot=2,1")
    assert run("anim", f"{p}:a", "-o", tmp_path / "a.gif", "--scale", "1") == 0
    gif = Image.open(tmp_path / "a.gif")
    assert gif.size == (5 * 1 + 8 * 3 + 5 * 3, max(5 * 1, 5 * 3 + 8))  # w*S + 3 gaps + 1x and 2x copies


def test_anim_writes_exactly_the_gif_and_the_strip(tmp_path, capsys):
    # GAMES-295: -h promised 1x and 2x GIF copies "alongside"; they're inside the one GIF, beside the big frame.
    p = write(tmp_path, "w.px", "k #ff0000\ng #00ff00\n@frame w/0\nkg\ngk\n@frame w/1\ngk\nkg\n")
    out = tmp_path / "o"
    assert run("anim", f"{p}:w", "-o", out / "w.gif", "--scale", "4") == 0
    assert sorted(x.name for x in out.iterdir()) == ["w.gif", "w.strip.png"]
    assert capsys.readouterr().out.splitlines()[-1] == f"wrote {out / 'w.gif'} and {out / 'w.strip.png'}"


@pytest.mark.parametrize("n", [0, 1])
def test_anim_gif_frame_holds_the_1x_and_2x_copies(tmp_path, n):
    p = write(tmp_path, "w.px", "k #ff0000\ng #00ff00\n@frame w/0\nkg\ngk\n@frame w/1\ngk\nkg\n")
    S, gap, w = 4, 8, 2
    assert run("anim", f"{p}:w", "-o", tmp_path / "w.gif", "--scale", S) == 0
    gif = Image.open(tmp_path / "w.gif")
    assert gif.size == (w * S + gap * 3 + w * 3, max(w * S, w * 3 + gap))
    gif.seek(n)
    im = gif.convert("RGBA")
    doc = pxart.parse(p)
    src = doc.image(doc.frames[n])
    for y in range(w):
        for x in range(w):
            want = src.getpixel((x, y))
            assert im.getpixel((x * S, y * S)) == want                       # --scale
            assert im.getpixel((w * S + gap + x, y)) == want                 # 1x
            for dy in (0, 1):
                for dx in (0, 1):                                            # 2x
                    assert im.getpixel((w * S + gap * 2 + w + 2 * x + dx, 2 * y + dy)) == want


def test_anim_help_describes_one_gif_with_copies_inside():
    doc = pxart.__doc__
    assert "GIF (with 1x and 2x copies alongside)" not in doc
    assert "walk.gif (one file: each frame at --scale, its 1x and 2x copies beside it in the same" in doc
    readme = (pathlib.Path(pxart.__file__).parent / "README.md").read_text()
    assert "2x copies beside it in the same picture" in readme


def test_onion_aligns_by_pivot(tmp_path):
    p = pivot_anim_file(tmp_path, p0="pivot=0,0", p1="pivot=1,0")
    assert run("onion", f"{p}:a/0", f"{p}:a/1", "-o", tmp_path / "o.png", "--scale", "1") == 0
    img = Image.open(tmp_path / "o.png").convert("RGBA")
    assert img.size == (4, 4)  # a/1's pivot 1,0 meets a/0's 0,0: a/1 starts 1px left, so the canvas is 4 wide


def test_onion_without_pivots_is_unchanged(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    assert run("onion", f"{p}:walk/down/0", f"{p}:idle", "-o", tmp_path / "o.png", "--scale", "1") == 0
    assert Image.open(tmp_path / "o.png").size == (4, 2)


# GAMES-295: onion prints an alignment readout (a 1px jump is too faint to judge by eye).

BOB = "k #000000\n@frame w/0\n.k.\nkkk\n.k.\nk.k\n@frame w/1\n...\n.k.\nkkk\nk.k\n@frame w/2\n.k.\nkkk\n.k.\n.k.\n"


def onion_lines(tmp_path, capsys, a, b, *more):
    assert run("onion", a, b, "-o", tmp_path / "o.png", *more) == 0
    return capsys.readouterr().out.splitlines()


def test_onion_readout_head_drops_feet_stay(tmp_path, capsys):
    p = write(tmp_path, "b.px", BOB)
    assert onion_lines(tmp_path, capsys, f"{p}:w/0", f"{p}:w/1") == [
        "A w/0: opaque x 0..2, y 0..3 (on the 3x4 canvas, bottom-centered)",
        "B w/1: opaque x 0..2, y 1..3",
        "B vs A: left +0, right +0, top +1, bottom +0; best shift +0,+1 then 3px changed (no shift: 5px)",
        f"wrote {tmp_path / 'o.png'}",
    ]


def test_onion_readout_identical_frames(tmp_path, capsys):
    p = write(tmp_path, "b.px", BOB)
    lines = onion_lines(tmp_path, capsys, f"{p}:w/0", f"{p}:w/0")
    assert lines[2] == "B vs A: left +0, right +0, top +0, bottom +0; best shift +0,+0 then 0px changed (no shift: 0px)"


def test_onion_readout_one_pixel_jump(tmp_path, capsys):
    # The whole sprite 1px up: every edge -1 on y, and the shift explains it with nothing left changed.
    p = write(tmp_path, "j.px", "k #000000\n@frame a\n...\n.k.\nkkk\n@frame b\n.k.\nkkk\n...\n")
    lines = onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b")
    assert lines[2] == "B vs A: left +0, right +0, top -1, bottom -1; best shift +0,-1 then 0px changed (no shift: 6px)"


def test_onion_readout_changed_leg_only(tmp_path, capsys):
    p = write(tmp_path, "b.px", BOB)
    lines = onion_lines(tmp_path, capsys, f"{p}:w/0", f"{p}:w/2")
    assert lines[2] == "B vs A: left +0, right +0, top +0, bottom +0; best shift +0,+0 then 3px changed (no shift: 3px)"


def test_onion_readout_by_pivot(tmp_path, capsys):
    p = pivot_anim_file(tmp_path, p0="pivot=0,0", p1="pivot=1,0")
    lines = onion_lines(tmp_path, capsys, f"{p}:a/0", f"{p}:a/1")
    assert lines[0] == "A a/0: opaque x 1..1, y 0..3 (on the 4x4 canvas, lined up by pivot)"
    assert lines[1] == "B a/1: opaque x 1..1, y 0..1"
    assert lines[2].startswith("B vs A: left +0, right +0, top +0, bottom -2; ")


def test_onion_readout_frames_of_different_sizes_bottom_centered(tmp_path, capsys):
    p = write(tmp_path, "m.px", MULTI)
    lines = onion_lines(tmp_path, capsys, f"{p}:walk/down/0", f"{p}:idle")
    assert lines[0] == "A walk/down/0: opaque x 0..3, y 0..1 (on the 4x2 canvas, bottom-centered)"
    assert lines[1] == "B idle: opaque x 0..3, y 0..1"


def test_onion_readout_empty_frame(tmp_path, capsys):
    p = write(tmp_path, "e.px", "k #000000\n@frame a\nk.\n@frame b\n..\n")
    lines = onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b")
    assert lines[:2] == ["A a: opaque x 0..0, y 0..0 (on the 2x1 canvas, bottom-centered)", "B b: empty"]
    assert lines[2] == f"wrote {tmp_path / 'o.png'}"


def test_onion_readout_pngs(tmp_path, capsys):
    Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(tmp_path / "a.png")
    Image.new("RGBA", (2, 1), (1, 2, 3, 255)).save(tmp_path / "b.png")
    lines = onion_lines(tmp_path, capsys, tmp_path / "a.png", tmp_path / "b.png")
    assert lines[0] == "A a: opaque x 0..1, y 0..1 (on the 2x2 canvas, bottom-centered)"
    assert lines[2].startswith("B vs A: left +0, right +0, top +1, bottom +0; ")


def test_onion_readout_image_unchanged(tmp_path, capsys):
    # The readout is text only: the PNG is what it was.
    p = write(tmp_path, "b.px", BOB)
    assert run("onion", f"{p}:w/0", f"{p}:w/1", "-o", tmp_path / "o.png", "--scale", "2") == 0
    img = Image.open(tmp_path / "o.png").convert("RGBA")
    assert img.size == (3 * 2, 4 * 2)  # below --scale 4: no grid, no rulers
    assert img.getpixel((2, 0))[3] == 255 and img.getpixel((0, 0)) == (58, 58, 68, 255)


def test_help_documents_onion_readout():
    assert "B vs A: left +0, right +0, top -1, bottom +0; best shift +0,-1 then 4px changed" in pxart.__doc__


# export

def test_export_aseprite_slices_pivots(tmp_path):
    p = write(tmp_path, "p.px", PIV + "@frame icon\nj\n")
    assert run("export", p, "--aseprite", tmp_path / "s.json") == 0
    meta = json.loads((tmp_path / "s.json").read_text())["meta"]
    assert meta["slices"] == [{"name": "pivot", "color": "#0000ffff", "keys": [
        {"frame": 0, "bounds": {"x": 0, "y": 0, "w": 3, "h": 3}, "pivot": {"x": 1, "y": 2}},
        {"frame": 1, "bounds": {"x": 0, "y": 0, "w": 3, "h": 2}, "pivot": {"x": 2, "y": 1}},
        {"frame": 2, "bounds": {"x": 0, "y": 0, "w": 1, "h": 1}}]}]


def test_export_aseprite_slice_keys_follow_sheet_order(tmp_path):
    p = write(tmp_path, "p.px", "k #000000\n@frame b/0 pivot=0,0\nk\n@frame a/0\nk\n@frame b/1 pivot=0,1\nk\nk\n")
    assert run("export", p, "--aseprite", tmp_path / "s.json") == 0
    data = json.loads((tmp_path / "s.json").read_text())
    assert [f["filename"] for f in data["frames"]] == ["b/0", "b/1", "a/0"]
    keys = data["meta"]["slices"][0]["keys"]
    assert [k["frame"] for k in keys] == [0, 1, 2]
    assert [k.get("pivot") for k in keys] == [{"x": 0, "y": 0}, {"x": 0, "y": 1}, None]


def test_export_aseprite_without_pivots_has_no_slices(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    assert run("export", p, "--aseprite", tmp_path / "s.json") == 0
    assert json.loads((tmp_path / "s.json").read_text())["meta"]["slices"] == []


def test_export_aseprite_selection_with_pivots(tmp_path):
    p = write(tmp_path, "p.px", PIV + "@frame icon pivot=0,0\nj\n")
    assert run("export", f"{p}:icon", "--aseprite", tmp_path / "s.json") == 0
    keys = json.loads((tmp_path / "s.json").read_text())["meta"]["slices"][0]["keys"]
    assert keys == [{"frame": 0, "bounds": {"x": 0, "y": 0, "w": 1, "h": 1}, "pivot": {"x": 0, "y": 0}}]


def test_export_frames_writes_pivots_json(tmp_path, capsys):
    p = write(tmp_path, "p.px", PIV + "@frame icon\nj\n")
    assert run("export", p, "--frames", tmp_path / "f") == 0
    assert json.loads((tmp_path / "f" / "pivots.json").read_text()) == {"walk/0": {"x": 1, "y": 2},
                                                                         "walk/1": {"x": 2, "y": 1}}
    assert str(tmp_path / "f" / "pivots.json") in capsys.readouterr().out


def test_export_frames_without_pivots_writes_no_json(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    assert run("export", p, "--frames", tmp_path / "f") == 0
    assert not (tmp_path / "f" / "pivots.json").exists()


def test_extract_keeps_pivots(tmp_path):
    p = write(tmp_path, "p.px", PIV)
    assert run("extract", f"{p}:walk", "-o", tmp_path / "o.px") == 0
    assert "@anim walk ms=90 pivot=1,2" in (tmp_path / "o.px").read_text()
    assert "@frame walk/1 pivot=2,1" in (tmp_path / "o.px").read_text()


def test_help_documents_pivots():
    doc = pxart.__doc__
    assert "pivot=x,y (optional) on '@frame ID' or '@anim GROUP'" in doc
    assert "meta.slices = one slice \"pivot\"" in doc and "pivots.json" in doc
    assert "[pivot=X,Y]" in doc


# ---------------------------------------------------------------- loop I: rotate and transpose

ROT = "k #000000\nj #ffffff\n@frame a\nkkj\nk..\n"


@pytest.mark.parametrize("angle,want", [
    ("90", ["kk", ".k", ".j"]),
    ("180", ["..k", "jkk"]),
    ("270", ["j.", "k.", "kk"]),
])
def test_rotate_golden(tmp_path, angle, want):
    p = write(tmp_path, "r.px", ROT)
    assert run("rotate", f"{p}:a", angle) == 0
    assert grid_of(p) == want


def test_transpose_golden(tmp_path):
    p = write(tmp_path, "r.px", ROT)
    assert run("transpose", f"{p}:a") == 0
    assert grid_of(p) == ["kk", "k.", "j."]


def test_rotate_four_times_is_identity(tmp_path):
    p = write(tmp_path, "r.px", ROT)
    for _ in range(4):
        assert run("rotate", p, "90") == 0
    assert p.read_text() == ROT


@pytest.mark.parametrize("a,b", [("90", "270"), ("180", "180"), ("270", "90")])
def test_rotate_and_back(tmp_path, a, b):
    p = write(tmp_path, "r.px", ROT)
    assert run("rotate", p, a) == 0 and run("rotate", p, b) == 0
    assert p.read_text() == ROT


def test_transpose_twice_is_identity(tmp_path):
    p = write(tmp_path, "r.px", ROT)
    assert run("transpose", p) == 0 and run("transpose", p) == 0
    assert p.read_text() == ROT


def test_rotate_90_is_transpose_then_flip(tmp_path):
    p, q = write(tmp_path, "r.px", ROT), write(tmp_path, "q.px", ROT)
    assert run("rotate", p, "90") == 0
    assert run("transpose", q) == 0 and run("flip", q) == 0
    assert grid_of(p) == grid_of(q)


def test_rotate_notes_size_and_light(tmp_path, capsys):
    p = write(tmp_path, "r.px", ROT)
    assert run("rotate", f"{p}:a", "90") == 0
    out = capsys.readouterr().out
    assert "note: a is now 2x3 (was 3x2)" in out
    assert "a top-left light is now top-right (--light ne)" in out and "re-light with 'shade'" in out


@pytest.mark.parametrize("cmd,said", [(["rotate", "180"], "now bottom-right (--light se)"),
                                      (["rotate", "270"], "now bottom-left (--light sw)"),
                                      (["transpose"], "stays top-left, a top-right one is now bottom-left (--light sw)")])
def test_rotate_light_notes(tmp_path, capsys, cmd, said):
    p = write(tmp_path, "r.px", ROT)
    assert run(cmd[0], f"{p}:a", *cmd[1:]) == 0
    assert said in capsys.readouterr().out


def test_rotate_square_has_no_size_note(tmp_path, capsys):
    p = write(tmp_path, "r.px", "k #000000\nk.\n..\n")
    assert run("rotate", p, "90") == 0
    assert "(was " not in capsys.readouterr().out and grid_of(p, None) == [".k", ".."]


def test_rotate_symmetric_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "r.px", "k #000000\n.k.\nkkk\n.k.\n")
    assert run("rotate", p, "90") == 0
    out = capsys.readouterr().out
    assert out == f"no change: {p}\n"


def test_rotate_selection_only(tmp_path):
    p = write(tmp_path, "r.px", "k #000000\n@frame t/a\nk.\n..\n@frame t/b\nk.\n..\n@frame c\nk.\n..\n")
    assert run("rotate", f"{p}:t", "180") == 0
    doc = pxart.parse(p)
    assert doc.get("t/a").grid == doc.get("t/b").grid == ["..", ".k"] and doc.get("c").grid == ["k.", ".."]


def test_rotate_moves_pivots(tmp_path):
    p = write(tmp_path, "r.px", "k #000000\nj #ffffff\n@frame a pivot=0,1\nkkj\nk..\n")
    assert run("rotate", f"{p}:a", "90") == 0
    assert pxart.parse(p).get("a").pivot == (0, 0)  # the bottom-left pixel is now the top-left one
    assert run("rotate", f"{p}:a", "180") == 0
    assert pxart.parse(p).get("a").pivot == (1, 2)
    assert run("transpose", f"{p}:a") == 0
    assert pxart.parse(p).get("a").pivot == (2, 1)


def test_rotate_pixel_follows_pivot(tmp_path):
    # Wherever the pivot goes, it stays on the same pixel.
    p = write(tmp_path, "r.px", "k #000000\nj #ffffff\n@frame a pivot=2,0\nkkj\nk..\n")
    for cmd in (["rotate", "90"], ["rotate", "270"], ["transpose"], ["rotate", "180"]):
        assert run(cmd[0], f"{p}:a", *cmd[1:]) == 0
        doc = pxart.parse(p)
        x, y = doc.get("a").pivot
        assert doc.get("a").grid[y][x] == "j"


def test_rotate_bad_angle(tmp_path):
    p = write(tmp_path, "r.px", ROT)
    assert run("rotate", p, "45") == 2  # argparse: choices 90|180|270


def test_rotate_dash_o(tmp_path):
    p = write(tmp_path, "r.px", ROT)
    assert run("rotate", f"{p}:a", "90", "-o", tmp_path / "o.px") == 0
    assert p.read_text() == ROT and grid_of(tmp_path / "o.px") == ["kk", ".k", ".j"]


def test_help_documents_rotate():
    doc = pxart.__doc__
    assert "rotate FILE[:SEL] 90|180|270 [-o OUT]" in doc and "transpose FILE[:SEL] [-o OUT]" in doc
    assert "re-light with shade and outline --selective" in doc


# ---------------------------------------------------------------- loop I: outline (selective, pixel-perfect corners)

def shape_file(tmp_path, rows, name="s.px"):
    return write(tmp_path, name, "b #406080\no #101018\nl #203040\n@frame a\n" + "\n".join(rows) + "\n")


SQUARE = [".......", ".......", "..bbb..", "..bbb..", "..bbb..", ".......", "......."]


def test_outline_outside_square_cuts_corners(tmp_path):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o") == 0
    assert grid_of(p) == [".......", "..ooo..", ".obbbo.", ".obbbo.", ".obbbo.", "..ooo..", "......."]


def test_outline_outside_square_corners_kept(tmp_path):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o", "--corners") == 0
    assert grid_of(p) == [".......", ".ooooo.", ".obbbo.", ".obbbo.", ".obbbo.", ".ooooo.", "......."]


def test_outline_outside_is_the_default(tmp_path):
    p, q = shape_file(tmp_path, SQUARE), shape_file(tmp_path, SQUARE, "q.px")
    assert run("outline", f"{p}:a", "--key", "o") == 0 and run("outline", f"{q}:a", "--key", "o", "--outside") == 0
    assert grid_of(p) == grid_of(q)


def test_outline_inside_square(tmp_path):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o", "--inside") == 0
    assert grid_of(p) == [".......", ".......", "..ooo..", "..obo..", "..ooo..", ".......", "......."]


DIAG = ["......", ".b....", ".bb...", ".bbb..", "......", "......"]


def test_outline_diagonal_is_a_clean_staircase(tmp_path):
    p = shape_file(tmp_path, DIAG)
    assert run("outline", f"{p}:a", "--key", "o") == 0
    assert grid_of(p) == [".o....", "obo...", "obbo..", "obbbo.", ".ooo..", "......"]


def test_outline_diagonal_with_corners_doubles(tmp_path):
    p = shape_file(tmp_path, DIAG)
    assert run("outline", f"{p}:a", "--key", "o", "--corners") == 0
    assert grid_of(p) == ["ooo...", "oboo..", "obboo.", "obbbo.", "ooooo.", "......"]


def test_outline_inside_diagonal(tmp_path):
    p = shape_file(tmp_path, DIAG)
    assert run("outline", f"{p}:a", "--key", "o", "--inside") == 0
    assert grid_of(p) == ["......", ".o....", ".oo...", ".ooo..", "......", "......"]


def test_outline_inside_corners_on_a_thick_diagonal(tmp_path):
    rows = ["bbbb..", "bbbbb.", "bbbbbb", "bbbbbb"]
    p = shape_file(tmp_path, rows)
    assert run("outline", f"{p}:a", "--key", "o", "--inside") == 0
    assert grid_of(p) == ["oooo..", "obbbo.", "obbbbo", "oooooo"]
    p = shape_file(tmp_path, rows, "q.px")
    assert run("outline", f"{p}:a", "--key", "o", "--inside", "--corners") == 0
    assert grid_of(p) == ["oooo..", "obboo.", "obbboo", "oooooo"]


@pytest.mark.parametrize("w", range(3, 14))
def test_outline_outside_of_ellipses_has_no_doubled_corners(tmp_path, w):
    shape = pxart.ellipse_points(2, 2, w + 1, w // 2 + 3, fill=True)
    ring = pxart.outline_points(shape, w + 4, w // 2 + 6)
    for x, y in ring:
        assert (x, y) not in shape
        for dx, dy in pxart.CORNERS:  # an L: two ring side-neighbors that touch each other at a corner
            assert not ((x + dx, y) in ring and (x, y + dy) in ring and (x + dx, y + dy) not in shape), (x, y)


def test_outline_every_ring_pixel_touches_the_shape_on_a_side(tmp_path):
    shape = pxart.ellipse_points(1, 1, 10, 7, fill=True)
    for x, y in pxart.outline_points(shape, 12, 9):
        assert any((x + dx, y + dy) in shape for dx, dy in pxart.SIDES)


def test_outline_single_pixel(tmp_path):
    p = shape_file(tmp_path, [".....", ".....", "..b..", ".....", "....."])
    assert run("outline", f"{p}:a", "--key", "o") == 0
    assert grid_of(p) == [".....", "..o..", ".obo.", "..o..", "....."]


def test_outline_clips_at_the_frame(tmp_path):
    p = shape_file(tmp_path, ["bb.", "bb.", "..."])
    assert run("outline", f"{p}:a", "--key", "o") == 0
    assert grid_of(p) == ["bbo", "bbo", "oo."]


def test_outline_inside_frame_edge_counts_as_empty(tmp_path):
    p = shape_file(tmp_path, ["bbb", "bbb", "bbb"])
    assert run("outline", f"{p}:a", "--key", "o", "--inside") == 0
    assert grid_of(p) == ["ooo", "obo", "ooo"]


def test_outline_transparent_keys_are_empty(tmp_path):
    p = write(tmp_path, "s.px", "b #406080\no #101018\nt transparent\n@frame a\nttt\ntbt\nttt\n")
    assert run("outline", f"{p}:a", "--key", "o") == 0
    assert grid_of(p) == ["tot", "obo", "tot"]


# selective

def test_selective_square_nw(tmp_path):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "l", "--selective") == 0
    assert grid_of(p) == [".......", "..lll..", ".lbbbo.", ".lbbbo.", ".lbbbo.", "..ooo..", "......."]


@pytest.mark.parametrize("light,want", [
    # The normals at the ends of a side lean round the corner (the pull of the pixels within 2px), so under an
    # axis light the lit edge wraps one pixel down each side: a small shape reads round.
    ("n", [".......", "..lll..", ".lbbbl.", ".obbbo.", ".obbbo.", "..ooo..", "......."]),
    ("s", [".......", "..ooo..", ".obbbo.", ".lbbbl.", ".lbbbl.", "..lll..", "......."]),
    ("e", [".......", "..ool..", ".obbbl.", ".obbbl.", ".obbbl.", "..ool..", "......."]),
    ("w", [".......", "..loo..", ".lbbbo.", ".lbbbo.", ".lbbbo.", "..loo..", "......."]),
    ("se", [".......", "..ooo..", ".obbbl.", ".obbbl.", ".obbbl.", "..lll..", "......."]),
])
def test_selective_square_lights(tmp_path, light, want):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "l", "--light", light) == 0
    assert grid_of(p) == want


def test_lit_alone_means_selective(tmp_path):
    p, q = shape_file(tmp_path, SQUARE), shape_file(tmp_path, SQUARE, "q.px")
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "l") == 0
    assert run("outline", f"{q}:a", "--key", "o", "--lit", "l", "--selective") == 0
    assert grid_of(p) == grid_of(q)


def test_selective_circle_lit_side_faces_the_light(tmp_path):
    rows = pts_grid(pxart.ellipse_points(2, 2, 13, 13, fill=True), 16, 16)
    p = shape_file(tmp_path, [r.replace("k", "b") for r in rows])
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "l") == 0
    g = grid_of(p)
    lit = {(x, y) for y, r in enumerate(g) for x, c in enumerate(r) if c == "l"}
    dark = {(x, y) for y, r in enumerate(g) for x, c in enumerate(r) if c == "o"}
    assert lit and dark and all(x + y < 15 for x, y in lit) and all(x + y >= 15 for x, y in dark)
    assert {(y, x) for x, y in lit} == lit  # symmetric about the light's diagonal


def test_selective_inside(tmp_path):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "l", "--inside") == 0
    assert grid_of(p) == [".......", ".......", "..llo..", "..lbo..", "..ooo..", ".......", "......."]


def test_outline_counts(tmp_path, capsys):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "l") == 0
    assert capsys.readouterr().out == f"changed 12 px: 6->o, 6->l; wrote {p}\n"


def test_outline_count_plain(tmp_path, capsys):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o") == 0
    assert capsys.readouterr().out == f"changed 12 px: 12->o; wrote {p}\n"


def test_selective_needs_lit(tmp_path):
    p = shape_file(tmp_path, SQUARE)
    assert "--selective needs --lit KEY" in run_err("outline", f"{p}:a", "--key", "o", "--selective")


def test_outline_unknown_keys(tmp_path):
    p = shape_file(tmp_path, SQUARE)
    assert "key 'q' not in palette" in run_err("outline", f"{p}:a", "--key", "q")
    assert "key 'q' not in palette" in run_err("outline", f"{p}:a", "--key", "o", "--lit", "q")


def test_outline_inside_and_outside_exclusive(tmp_path):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o", "--inside", "--outside") == 2


def test_outline_every_selected_frame(tmp_path):
    p = write(tmp_path, "s.px", "b #406080\no #101018\n@frame w/0\n...\n.b.\n...\n@frame w/1\n...\n.b.\n...\n")
    assert run("outline", f"{p}:w", "--key", "o") == 0
    doc = pxart.parse(p)
    assert doc.get("w/0").grid == doc.get("w/1").grid == [".o.", "obo", ".o."]


def test_outline_twice_grows(tmp_path):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o") == 0 and run("outline", f"{p}:a", "--key", "o") == 0
    assert grid_of(p)[0] == "..ooo.."


def test_outline_no_change_inside_twice(tmp_path, capsys):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o", "--inside") == 0
    capsys.readouterr()
    assert run("outline", f"{p}:a", "--key", "o", "--inside") == 0
    assert "no change" in capsys.readouterr().out


def test_normal_points_out():
    shape = {(x, y) for x in range(5) for y in range(5)}
    assert pxart.normal((2, 0), shape) == pytest.approx((0, -1))
    assert pxart.normal((4, 2), shape) == pytest.approx((1, 0))
    assert pxart.normal((2, 2), shape) == (0.0, 0.0) or abs(pxart.normal((2, 2), shape)[0]) < 1e-9
    nx, ny = pxart.normal((0, 0), shape)
    assert nx == pytest.approx(ny) and nx < 0
    assert pxart.normal((2, -1), shape) == pytest.approx((0, -1))  # outside pixels too


def test_help_documents_outline():
    doc = pxart.__doc__
    assert "outline FILE[:frame] --key K [--outside | --inside] [--lit L [--selective]] [--light nw]" in doc
    assert "pixel-perfect" in doc and "--corners" in doc


# ---------------------------------------------------------------- loop I: shade (ramp by light direction)

SHADE_PAL = "A #201028\nB #403050\nC #6060a0\nD #90a0d0\nE #d0e0f0\no #000000\ng #00ff00\n"
RAMP = "A,B,C,D,E"


def material_file(tmp_path, rows, name="m.px"):
    return write(tmp_path, name, SHADE_PAL + "@frame a\n" + "\n".join(rows) + "\n")


def circle_rows(n, key="C", pad=1):
    pts = pxart.ellipse_points(pad, pad, pad + n - 1, pad + n - 1, fill=True)
    return ["".join(key if (x, y) in pts else "." for x in range(n + 2 * pad)) for y in range(n + 2 * pad)]


def square_rows(n, key="C", pad=1):
    return ["." * (n + 2 * pad)] * pad + ["." * pad + key * n + "." * pad] * n + ["." * (n + 2 * pad)] * pad


def tones(p):
    g = grid_of(p)
    return {(x, y): c for y, r in enumerate(g) for x, c in enumerate(r) if c in "ABCDE"}


def components(pts):
    pts, n = set(pts), 0
    while pts:
        n += 1
        todo = [pts.pop()]
        while todo:
            x, y = todo.pop()
            for q in [(x + a, y + b) for a in (-1, 0, 1) for b in (-1, 0, 1)]:
                if q in pts:
                    pts.remove(q)
                    todo.append(q)
    return n


def half_means(t, light):
    """Mean ramp index of the pixels on the light's side of the shape's center vs the far side."""
    lx, ly = pxart.LIGHTS[light]
    cx = sum(x for x, _ in t) / len(t)
    cy = sum(y for _, y in t) / len(t)
    near = [RAMP.index(k) / 2 for (x, y), k in t.items() if (x - cx) * lx + (y - cy) * ly > 0.5]
    far = [RAMP.index(k) / 2 for (x, y), k in t.items() if (x - cx) * lx + (y - cy) * ly < -0.5]
    return sum(near) / len(near), sum(far) / len(far)


@pytest.mark.parametrize("shape", ["circle", "square"])
@pytest.mark.parametrize("light", list(pxart.LIGHTS))
@pytest.mark.parametrize("size", [8, 12, 16, 24])
def test_shade_lit_side_is_lighter(tmp_path, shape, light, size):
    p = material_file(tmp_path, (circle_rows if shape == "circle" else square_rows)(size))
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--light", light) == 0
    near, far = half_means(tones(p), light)
    assert near > far


@pytest.mark.parametrize("shape", ["circle", "square"])
@pytest.mark.parametrize("light", list(pxart.LIGHTS))
@pytest.mark.parametrize("size", [8, 11, 16, 23, 32])
@pytest.mark.parametrize("strength", [2, 3, 4])
@pytest.mark.parametrize("ramp", ["A,B,C", "A,B,C,D", "A,B,C,D,E"])
def test_shade_bands_are_contiguous(tmp_path, shape, light, size, strength, ramp):
    rows = (circle_rows if shape == "circle" else square_rows)(size)
    shape_px = {(x, y) for y, r in enumerate(rows) for x, c in enumerate(r) if c == "C"}
    got = pxart.shade_tones(shape_px, ramp.split(","), len(ramp.split(",")) // 2, light, strength)
    for k in set(got.values()):
        assert components([q for q, v in got.items() if v == k]) == 1, k


@pytest.mark.parametrize("shape", ["circle", "square"])
@pytest.mark.parametrize("light", list(pxart.LIGHTS))
def test_shade_strength_1_is_a_1px_rim(shape, light):
    # --strength 1 shades only the edge pixels. With one step each way every band is one piece; with two dark
    # steps the rim runs d1 d2 d1 around the dark side (two d1 pieces flanking d2), as a hand-shaded rim does.
    rows = (circle_rows if shape == "circle" else square_rows)(16)
    shape_px = {(x, y) for y, r in enumerate(rows) for x, c in enumerate(r) if c == "C"}
    got = pxart.shade_tones(shape_px, list("ABC"), 1, light, 1)
    edge = {p for p, (d, _) in pxart.nearest_edge(shape_px).items() if d == 0}
    assert all(got[p] == "B" for p in shape_px - edge)
    for k in "ABC":
        assert components([q for q, v in got.items() if v == k]) == 1, k


def test_shade_bands_contiguous_through_the_cli(tmp_path):
    p = material_file(tmp_path, circle_rows(20))
    assert run("shade", f"{p}:a", "--ramp", RAMP) == 0
    t = tones(p)
    for k in "ABCDE":
        assert components([q for q, v in t.items() if v == k]) == 1, k


@pytest.mark.parametrize("shape", ["circle", "square"])
def test_shade_no_dither_means_no_stray_pixels(tmp_path, shape):
    p = material_file(tmp_path, (circle_rows if shape == "circle" else square_rows)(16))
    assert run("shade", f"{p}:a", "--ramp", RAMP) == 0
    t = tones(p)
    for (x, y), k in t.items():
        near = [t[q] for q in [(x + a, y + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b] if q in t]
        assert k in near, (x, y)


def test_shade_dither_mixes_band_boundaries(tmp_path):
    p, q = material_file(tmp_path, circle_rows(20)), material_file(tmp_path, circle_rows(20), "q.px")
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--strength", "6") == 0
    assert run("shade", f"{q}:a", "--ramp", RAMP, "--strength", "6", "--dither") == 0
    plain, dith = tones(p), tones(q)
    assert plain != dith
    differ = [xy for xy in plain if plain[xy] != dith[xy]]
    assert all(abs(RAMP.index(plain[xy]) - RAMP.index(dith[xy])) <= 2 for xy in differ)  # one ramp step apart
    stray = sum(1 for (x, y), k in dith.items()
                if k not in [dith.get((x + a, y + b)) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b])
    assert stray > 0  # a dither pattern is what makes lone pixels


def test_shade_dither_uses_the_bayer_pattern():
    # A lighting value exactly on a boundary (0.5 of a step) splits pixels by the 4x4 Bayer thresholds: half each.
    got = [pxart.ramp_key(0.25, list("ABCDE"), 2, x, y, dither=True) for y in range(4) for x in range(4)]
    assert got.count("C") == 8 and got.count("D") == 8
    assert pxart.ramp_key(0.25, list("ABCDE"), 2, 0, 0) == "C"  # a tie goes to the base without dither


def test_ramp_key_bands():
    ramp = list("ABCDE")
    assert [pxart.ramp_key(v, ramp, 2, 0, 0) for v in (-1, -0.8, -0.74, -0.3, -0.2, 0, 0.2, 0.3, 0.74, 0.8, 1)] == \
        ["A", "A", "B", "B", "C", "C", "C", "D", "D", "E", "E"]
    assert [pxart.ramp_key(v, list("ABCD"), 2, 0, 0) for v in (-1, -0.3, 0, 0.4, 0.6, 1)] == \
        ["A", "B", "C", "C", "D", "D"]
    assert [pxart.ramp_key(v, list("AB"), 1, 0, 0) for v in (-1, -0.6, -0.4, 0.9)] == ["A", "A", "B", "B"]


def test_shade_never_touches_other_keys(tmp_path):
    rows = circle_rows(12)
    rows = [r.replace(".", "g") for r in rows]
    rows[6] = rows[6][:6] + "oo" + rows[6][8:]
    p = material_file(tmp_path, rows)
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--keys", "C") == 0
    for r0, r1 in zip(rows, grid_of(p)):
        for c0, c1 in zip(r0, r1):
            assert c0 == c1 if c0 != "C" else c1 in "ABCDE"


def test_shade_keys_default_to_the_ramp(tmp_path):
    p = material_file(tmp_path, circle_rows(12))
    assert run("shade", f"{p}:a", "--ramp", RAMP) == 0
    first = grid_of(p)
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--light", "se") == 0  # re-shade the shaded material
    second = grid_of(p)
    p2 = material_file(tmp_path, circle_rows(12), "p2.px")
    assert run("shade", f"{p2}:a", "--ramp", RAMP, "--light", "se") == 0
    assert second == grid_of(p2) and first != second


def test_shade_is_deterministic(tmp_path):
    a, b = material_file(tmp_path, circle_rows(17)), material_file(tmp_path, circle_rows(17), "b.px")
    assert run("shade", f"{a}:a", "--ramp", RAMP, "--strength", "3") == 0
    assert run("shade", f"{b}:a", "--ramp", RAMP, "--strength", "3") == 0
    assert a.read_text() == b.read_text()


def test_shade_twice_is_no_change(tmp_path, capsys):
    p = material_file(tmp_path, circle_rows(12))
    assert run("shade", f"{p}:a", "--ramp", RAMP) == 0
    capsys.readouterr()
    assert run("shade", f"{p}:a", "--ramp", RAMP) == 0
    assert "no change" in capsys.readouterr().out


def test_shade_symmetric_under_its_light(tmp_path):
    p = material_file(tmp_path, circle_rows(15, pad=0))
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--light", "n") == 0
    g = grid_of(p)
    assert all(r == r[::-1] for r in g)  # a north light on a circle: mirror-symmetric left-right
    p = material_file(tmp_path, circle_rows(15, pad=0), "d.px")
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--light", "nw") == 0
    g = grid_of(p)
    assert all(g[y][x] == g[x][y] for y in range(15) for x in range(15))  # nw: symmetric across the diagonal


def test_shade_square_north_light_golden(tmp_path):
    p = material_file(tmp_path, square_rows(6, pad=0))
    assert run("shade", f"{p}:a", "--ramp", "A,B,C,D,E", "--light", "n") == 0
    # Lit top, dark bottom, base sides; the corners' normals lean round them (one step toward the base).
    assert grid_of(p) == ["DEEEED", "DDDDDD", "CCCCCC", "CCCCCC", "BBBBBB", "BAAAAB"]


def test_shade_rim_then_base(tmp_path):
    p = material_file(tmp_path, square_rows(12, pad=0))
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--strength", "2") == 0
    g = grid_of(p)
    assert all(c == "C" for r in g[3:9] for c in r[3:9])  # deeper than strength: the base tone


def test_shade_strength_reaches_deeper(tmp_path):
    p, q = material_file(tmp_path, circle_rows(20)), material_file(tmp_path, circle_rows(20), "q.px")
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--strength", "2") == 0
    assert run("shade", f"{q}:a", "--ramp", RAMP, "--strength", "8") == 0
    assert list(tones(p).values()).count("C") > list(tones(q).values()).count("C")


def test_shade_region_limits_the_repaint(tmp_path):
    rows = square_rows(10, pad=0)
    p = material_file(tmp_path, rows)
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--region", "0,0,5,10") == 0
    g = grid_of(p)
    assert all(r[5:] == "CCCCC" for r in g)          # outside the region: untouched
    assert g[5][4] == "C"                            # loop J: the region's cut is no edge (was dark)
    assert g[5][0] in "DE"                           # the lit left edge


def test_shade_base_option(tmp_path):
    p = material_file(tmp_path, square_rows(10, pad=0))
    assert run("shade", f"{p}:a", "--ramp", "A,B,C,D", "--base", "B") == 0
    g = grid_of(p)
    assert g[5][5] == "B" and "A" in "".join(g) and "D" in "".join(g)


def test_shade_base_must_be_in_ramp(tmp_path):
    p = material_file(tmp_path, square_rows(4))
    assert "--base 'o' isn't in --ramp" in run_err("shade", f"{p}:a", "--ramp", RAMP, "--base", "o")


def test_shade_ramp_forms(tmp_path):
    p, q = material_file(tmp_path, circle_rows(12)), material_file(tmp_path, circle_rows(12), "q.px")
    assert run("shade", f"{p}:a", "--ramp", "A,B,C,D,E") == 0 and run("shade", f"{q}:a", "--ramp", "ABCDE") == 0
    assert grid_of(p) == grid_of(q)


@pytest.mark.parametrize("ramp,err", [("A,,B", "wants keys"), ("A,B,A", "names a key twice"), ("A,q", "not in palette"),
                                      ("A,.,B", "can't be a ramp tone")])
def test_shade_bad_ramps(tmp_path, ramp, err):
    p = material_file(tmp_path, square_rows(4))
    assert err in run_err("shade", f"{p}:a", "--ramp", ramp)


def test_shade_bad_strength(tmp_path):
    p = material_file(tmp_path, square_rows(4))
    assert "E_BAD_ARG" in run_err("shade", f"{p}:a", "--ramp", RAMP, "--strength", "0")


# GAMES-295: outline and shade report the pixels they changed, by the key they got, never totals.

def test_outline_rerun_changes_nothing(tmp_path, capsys):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "l") == 0
    text = p.read_text()
    capsys.readouterr()
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "l", "--inside") == 0  # the ring is already o and l
    assert capsys.readouterr().out == f"changed 0 px; no change: {p}\n" and p.read_text() == text


def test_outline_counts_only_changed_pixels(tmp_path, capsys):
    # Half the ring is already 'o': only the other half counts.
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o") == 0
    g = grid_of(p)
    ring = sum(c == "o" for row in g for c in row)
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "l", "--corners") == 0
    out = capsys.readouterr().out.splitlines()[-1]
    g2 = grid_of(p)
    lit = sum(c == "l" for row in g2 for c in row)
    new_o = sum(a != b and b == "o" for r1, r2 in zip(g, g2) for a, b in zip(r1, r2))
    assert out == f"changed {lit + new_o} px: " + ", ".join(f"{n}->{k}" for k, n in (("o", new_o), ("l", lit)) if n) \
        + f"; wrote {p}"
    assert ring > 0


def test_outline_lit_same_as_key_counts_once(tmp_path, capsys):
    p = shape_file(tmp_path, SQUARE)
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "o") == 0
    assert capsys.readouterr().out == f"changed 12 px: 12->o; wrote {p}\n"


def test_outline_preview_writes_only_the_png(tmp_path, capsys):
    p = shape_file(tmp_path, SQUARE)
    before = p.read_text()
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "l", "--preview", tmp_path / "v.png") == 0
    assert p.read_text() == before
    assert capsys.readouterr().out == (f"would change 12 px: 6->o, 6->l; wrote {tmp_path / 'v.png'} (preview; {p} "
                                       "unchanged)\n")
    img = Image.open(tmp_path / "v.png").convert("RGBA")
    doc = pxart.parse(p)
    assert pxart.parse(p).resolved()["o"] in set(pxart.pixels(img))


def test_outline_preview_matches_the_write(tmp_path):
    p = shape_file(tmp_path, SQUARE)
    q = write(tmp_path, "q.px", p.read_text())
    assert run("outline", f"{p}:a", "--key", "o", "--lit", "l", "--preview", tmp_path / "v.png") == 0
    assert run("outline", f"{q}:a", "--key", "o", "--lit", "l") == 0
    assert run("render", f"{q}:a", "-o", tmp_path / "r.png") == 0
    assert list(pxart.pixels(Image.open(tmp_path / "v.png").convert("RGBA"))) == \
        list(pxart.pixels(Image.open(tmp_path / "r.png").convert("RGBA")))


def test_outline_preview_and_o_conflict(tmp_path):
    p = shape_file(tmp_path, SQUARE)
    msg = run_err("outline", f"{p}:a", "--key", "o", "--preview", tmp_path / "v.png", "-o", tmp_path / "o.px")
    assert "E_BAD_ARG" in msg and "drop -o or --preview" in msg and not (tmp_path / "v.png").exists()


def test_shade_rerun_changes_nothing(tmp_path, capsys):
    p = material_file(tmp_path, square_rows(6, pad=0))
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--light", "n") == 0
    capsys.readouterr()
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--light", "n") == 0
    assert capsys.readouterr().out == f"changed 0 px; no change: {p}\n"


def test_shade_preview_says_would_change(tmp_path, capsys):
    p = material_file(tmp_path, square_rows(6, pad=0))
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--light", "n", "--preview", tmp_path / "v.png") == 0
    assert capsys.readouterr().out == (f"would change 24 px: 4->A, 8->B, 8->D, 4->E; wrote {tmp_path / 'v.png'} "
                                       f"(preview; {p} unchanged)\n")


def test_shade_count_sums_over_frames(tmp_path, capsys):
    body = "\n".join(square_rows(6, pad=0))
    p = write(tmp_path, "m.px", SHADE_PAL + f"@frame w/0\n{body}\n@frame w/1\n{body}\n")
    assert run("shade", f"{p}:w", "--ramp", RAMP, "--light", "n") == 0
    assert capsys.readouterr().out == f"changed 48 px: 8->A, 16->B, 16->D, 8->E; wrote {p}\n"


def test_help_documents_changed_counts():
    doc = pxart.__doc__
    assert '"changed 24 px: 4->A, 8->B, 8->D, 4->E"' in doc and '"changed 12 px: 6->o, 6->l"' in doc
    assert "[--corners] [--preview P.png]" in doc and "Prints the count per tone" not in doc


def test_shade_key_list_comma_key():
    assert pxart.key_list(",,a", "--ramp") == [",", "a"]
    assert pxart.key_list("abc", "--ramp") == ["a", "b", "c"] == pxart.key_list("a,b,c", "--ramp")
    assert pxart.key_list("a", "--keys") == ["a"]


def test_shade_prints_counts(tmp_path, capsys):
    p = material_file(tmp_path, square_rows(6, pad=0))
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--light", "n") == 0
    out = capsys.readouterr().out
    assert out == f"changed 24 px: 4->A, 8->B, 8->D, 4->E; wrote {p}\n"


def test_shade_preview_writes_only_the_png(tmp_path, capsys):
    p = material_file(tmp_path, circle_rows(10))
    before = p.read_text()
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--preview", tmp_path / "prev.png") == 0
    assert p.read_text() == before and (tmp_path / "prev.png").exists()
    out = capsys.readouterr().out
    assert "(preview;" in out and "unchanged" in out
    img = Image.open(tmp_path / "prev.png").convert("RGBA")
    assert (0xD0, 0xE0, 0xF0, 255) in set(pxart.pixels(img))  # the lightest tone is in the render


def test_shade_preview_and_o_conflict(tmp_path):
    p = material_file(tmp_path, circle_rows(6))
    assert "drop -o or --preview" in run_err("shade", f"{p}:a", "--ramp", RAMP, "--preview", tmp_path / "x.png",
                                             "-o", tmp_path / "o.px")


def test_shade_every_selected_frame(tmp_path):
    body = "\n".join(square_rows(6, pad=0))
    p = write(tmp_path, "m.px", SHADE_PAL + f"@frame w/0\n{body}\n@frame w/1\n{body}\n@frame x\n{body}\n")
    assert run("shade", f"{p}:w", "--ramp", RAMP) == 0
    doc = pxart.parse(p)
    assert doc.get("w/0").grid == doc.get("w/1").grid != doc.get("x").grid


def test_shade_thin_line_is_base(tmp_path):
    # A 1px horizontal line has outside on both sides: no way is out, so it stays the base tone (ends aside).
    p = material_file(tmp_path, [".........", ".CCCCCCC.", "........."])
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--light", "n") == 0
    assert grid_of(p)[1][3:6] == "CCC"


def test_shade_empty_material_is_no_change(tmp_path, capsys):
    p = material_file(tmp_path, ["...", "..."])
    assert run("shade", f"{p}:a", "--ramp", RAMP) == 0
    assert "no change" in capsys.readouterr().out


def test_nearest_edge_distances():
    sq = {(x, y) for x in range(7) for y in range(7)}
    ne = pxart.nearest_edge(sq)
    assert ne[(0, 3)][0] == 0 and ne[(1, 3)][0] == 1 and ne[(3, 3)][0] == 3
    assert ne[(3, 3)][1] in {(0, 3), (3, 0), (6, 3), (3, 6)}


def test_help_documents_shade():
    doc = pxart.__doc__
    assert "shade FILE[:frame] --ramp d2,d1,base,l1[,l2]" in doc
    for s in ("vector distance transform", "(normal . light direction) * (1 - depth / strength)", "--dither",
              "--preview P.png", "Nothing outside the material changes"):
        assert s in doc, s


# ---------------------------------------------------------------- loop I: the new edits name the command and the input

@pytest.mark.parametrize("argv", [
    ["line", "{b}:hat", "k", "0,0", "1,1"], ["rect", "{b}:hat", "k", "0,0,1,1"], ["ellipse", "{b}:hat", "k", "1,1,1,1"],
    ["arc", "{b}:hat", "k", "1,1,1", "0,90"], ["flood", "{b}:hat", "k", "0,0"], ["rotate", "{b}:hat", "90"],
    ["transpose", "{b}"], ["outline", "{b}", "--key", "k"], ["shade", "{b}", "--ramp", "k"],
])
def test_drawing_commands_name_command_and_input(tmp_path, argv):
    bad = write(tmp_path, "parts.px", BROKEN)
    args = [a.format(b=bad) for a in argv]
    before = bad.read_text()
    lines = broken_lines(run_err(*args))
    assert len(lines) == 2 and all(l.startswith(f"{argv[0]}: FILE ({args[1]}): {bad}:") for l in lines)
    assert bad.read_text() == before


@pytest.mark.parametrize("argv", [
    ["line", "{p}:zz", "k", "0,0", "1,1"], ["shade", "{p}:zz", "--ramp", "k"], ["outline", "{p}:zz", "--key", "k"],
    ["rotate", "{p}:zz", "90"],
])
def test_drawing_commands_bad_selector(tmp_path, argv):
    p = write(tmp_path, "ok.px", "k #000000\n@frame a\nk\n")
    msg = run_err(*[a.format(p=p) for a in argv])
    assert f"{argv[0]}: FILE ({p}:zz): {p}: E_SELECT: no frame 'zz'" in msg


@pytest.mark.parametrize("cmd", ["line", "rect", "ellipse", "arc", "flood", "shade", "outline", "rotate", "transpose"])
def test_new_commands_are_in_help_usage(cmd, capsys):
    with pytest.raises(SystemExit):
        pxart.main([cmd, "-h"])
    assert f"usage: pxart {cmd}" in capsys.readouterr().out


def test_help_keeps_new_commands_under_drawing():
    doc = pxart.__doc__
    drawing = doc[doc.index("\nDRAWING"):doc.index("\nCONVERTING")]
    for cmd in ("line ", "rect ", "ellipse ", "arc ", "flood ", "rotate ", "transpose ", "shade ", "outline "):
        assert f"\n  {cmd}" in drawing, cmd


# ---------------------------------------------------------------- loop J: the rise and the fall of a breath read alike

# A breathing idle whose legs never move: 0 chest down, 1 chest up (clean), 2 up with the arms out, 3 back down with
# the arms in on the way. The fall carries an arm change, which is what made it read "shift" before.
WAVE = BODY[:4] + ["kkkyyyykkk", "ssykyykyss", "ssyyyyyyss", "kyykyykyyk"] + BODY[8:]
ARMS_IN = BODY[:4] + ["skkyyyykks", "kyysyysyyk", "kyyyyyyyyk", "kyykyykyyk"] + BODY[8:]
IDLE_4 = ([EMPTY] + BODY + LEGS, BODY + [BODY[-1]] + LEGS, WAVE + [WAVE[-1]] + LEGS, [EMPTY] + ARMS_IN + LEGS)


def test_breath_fixture_legs_identical_in_every_frame():
    assert all(f[10:] == LEGS for f in IDLE_4) and all(len(f) == 14 and all(len(r) == 10 for r in f) for f in IDLE_4)


def test_breath_fall_alone_fails_the_single_frame_rule(tmp_path):
    # Without the animation around it, the fall (2 -> 3) still reads as a shift: its arm change is too big a
    # share of what the shift leaves changed. This is the case the animation-wide rule fixes.
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, IDLE_4[2], IDLE_4[3])
    assert (dx, dy) == (0, 1) and still is None


def test_breath_rise_alone_passes_the_single_frame_rule(tmp_path):
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, IDLE_4[0], IDLE_4[1])
    assert (dx, dy) == (0, -1) and still == 9


def test_breath_rise_and_fall_both_still(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *IDLE_4)
    assert "no shift then" in lines[1] and "(rows 9+ still; shift +0,-1:" in lines[1]
    assert "no shift then" in lines[3] and "(rows 9+ still; shift +0,+1:" in lines[3]


def test_breath_rise_and_fall_name_the_same_row(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *IDLE_4)
    rows = [l.split("(rows ")[1].split("+")[0] for l in lines if "(rows " in l]
    assert rows == ["9", "9"]


def test_breath_fall_exact_line(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *IDLE_4)
    _, _, n_shift, n_none, _ = motion_of(tmp_path, IDLE_4[2], IDLE_4[3])
    assert lines[3].endswith(f"vs idle/2: no shift then {pc(n_none, IDLE_4[3])} (rows 9+ still; shift +0,+1: {n_shift}px)")


def test_breath_rise_exact_line_unchanged(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *IDLE_4)
    _, _, n_shift, n_none, _ = motion_of(tmp_path, IDLE_4[0], IDLE_4[1])
    assert lines[1].endswith(f"vs idle/0: no shift then {pc(n_none, IDLE_4[1])} (rows 9+ still; shift +0,-1: {n_shift}px)")


def test_breath_unshifted_frames_unchanged(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *IDLE_4)
    assert "vs idle/3: shift +0,+0 then" in lines[0] and "vs idle/1: shift +0,+0 then" in lines[2]


def test_breath_strip_legs_dark_on_rise_and_fall(tmp_path, capsys):
    anim_lines(tmp_path, capsys, *IDLE_4)
    for i in (1, 3):
        rows = magenta_rows(tmp_path, i)
        assert rows and max(rows) < 10, (i, rows)  # legs (rows 10-13) unlit, rise and fall alike


def test_breath_strip_fall_shows_the_body(tmp_path, capsys):
    anim_lines(tmp_path, capsys, *IDLE_4)
    assert magenta_rows(tmp_path, 3) & {0, 1, 2}  # the head coming down is what changed


def test_breath_reversed_order_is_symmetric_too(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *IDLE_4[::-1])
    assert sum("(rows 9+ still;" in l for l in lines) == 2
    assert not any("then" in l and "legs" in l for l in lines)


def test_breath_pingpong_of_a_clean_breath_symmetric(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, IDLE_4[0], IDLE_4[1])
    assert all("(rows 9+ still;" in l for l in lines), lines


def test_breath_pingpong_where_neither_passes_alone_is_symmetric_too(tmp_path, capsys):
    # Both moves carry the arm change and neither passes on its own: both keep the shift, alike.
    lines = anim_lines(tmp_path, capsys, IDLE_4[2], IDLE_4[3])
    assert all(" then " in l and "still" not in l and "shift +0," in l for l in lines), lines


def test_breath_with_moving_legs_keeps_every_shift(tmp_path, capsys):
    # One frame changes the leg pose: the legs move in the animation (a walk), so even the frame that passes on its own
    # (its legs happen to stay put) reads as the bob it is: the smaller, truthful number.
    walky = WAVE + [WAVE[-1]] + LEGS_WIDE
    lines = anim_lines(tmp_path, capsys, IDLE_4[0], IDLE_4[1], walky, IDLE_4[3])
    _, _, n_shift, n_none, _ = motion_of(tmp_path, IDLE_4[0], IDLE_4[1])
    assert lines[1].endswith(f"vs idle/0: shift +0,-1 then {pc(n_shift, IDLE_4[1])} (no shift: {n_none}px)")
    assert "vs idle/2: shift +0,+1 then" in lines[3]
    assert not any("still" in l for l in lines), lines


def test_breath_feet_row_identical_everywhere_counts_as_legs(tmp_path, capsys):
    # Only the bottom row (the feet) is identical in every frame; one frame passes alone, so the fall keeps the feet
    # still too, and names its own first identical row.
    walky = WAVE + [WAVE[-1]] + ["..kbbbbk..", "..kbkkbk..", ".kbk..kbk.", "..kkk.kkk."]
    lines = anim_lines(tmp_path, capsys, IDLE_4[0], IDLE_4[1], walky, IDLE_4[3])
    assert "(rows 9+ still;" in lines[1]
    assert "vs idle/2: no shift then" in lines[3] and "(rows 13+ still; shift +0,+1:" in lines[3]


def test_breath_no_frame_passes_alone_stays_shifted(tmp_path, capsys):
    # Legs identical everywhere, but no frame passes on its own (every move carries an arm change): nothing shows the
    # legs standing, so every frame keeps its shift (a walk over a static shadow reads like this).
    lines = anim_lines(tmp_path, capsys, IDLE_4[2], IDLE_4[3], IDLE_4[2], IDLE_4[3])
    assert all("still" not in l for l in lines), lines


def shadow_walk():
    """A walk over a 1-row static shadow: the body bobs, the legs change pose, the shadow never moves."""
    shadow = "..kkkkkk.."
    down = ["..kbbbbk..", "..kbkkbk..", "..kbkkbk.."]
    return ([EMPTY] + BODY + down + [shadow], BODY + [BODY[-1]] + [".kbbbbk...", ".kbk.kbk..", "kbk...kbk."] + [shadow],
            [EMPTY] + BODY + down + [shadow], BODY + [BODY[-1]] + ["...kbbbbk.", "..kbk.kbk.", ".kbk...kbk"] + [shadow])


def test_shadow_walk_fixture_is_14_rows():
    assert all(len(f) == 14 for f in shadow_walk())


def test_shadow_walk_every_frame_keeps_its_shift(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *shadow_walk())
    assert [l.split(": ", 1)[1] for l in lines] == [
        "shift +0,+1 then 25px (27%) (no shift: 54px)", "shift +0,-1 then 31px (31%) (no shift: 54px)",
        "shift +0,+1 then 25px (27%) (no shift: 54px)", "shift +0,-1 then 31px (31%) (no shift: 54px)"]


def test_shadow_walk_shadow_is_identical_in_every_frame(tmp_path):
    doc = pxart.parse(anim_file(tmp_path, *shadow_walk(), name="sw.px"))
    assert pxart.still_rows([doc.image(f) for f in doc.frames]) == 13


def test_shadow_walk_strip_lights_the_legs(tmp_path, capsys):
    anim_lines(tmp_path, capsys, *shadow_walk())
    for i in range(4):
        assert magenta_rows(tmp_path, i) & {10, 11, 12}, i


def test_still_rows_all_identical_tail():
    imgs = [Image.new("RGBA", (3, 4)) for _ in range(3)]
    for im in imgs:
        im.putpixel((1, 3), (9, 9, 9, 255))
    imgs[1].putpixel((0, 0), (1, 1, 1, 255))
    imgs[2].putpixel((2, 1), (1, 1, 1, 255))
    assert pxart.still_rows(imgs) == 2


def test_still_rows_none_when_bottom_differs():
    imgs = [Image.new("RGBA", (3, 4)) for _ in range(2)]
    imgs[0].putpixel((1, 3), (9, 9, 9, 255))
    assert pxart.still_rows(imgs) is None


def test_still_rows_none_when_tail_is_empty():
    imgs = [Image.new("RGBA", (3, 4)) for _ in range(2)]
    imgs[1].putpixel((0, 0), (1, 1, 1, 255))
    assert pxart.still_rows(imgs) is None  # rows 1+ are identical but empty: nothing standing there


def test_still_rows_whole_frame_identical():
    imgs = [Image.new("RGBA", (2, 2), (5, 5, 5, 255)) for _ in range(3)]
    assert pxart.still_rows(imgs) == 0


def test_motion_legs_argument_turns_the_fall_still(tmp_path):
    doc = pxart.parse(anim_file(tmp_path, IDLE_4[2], IDLE_4[3], name="mo.px"))
    prev, cur = (doc.image(f) for f in doc.frames)
    assert pxart.motion(prev, cur)[4] is None
    assert pxart.motion(prev, cur, legs=10)[4] == 9


def test_motion_legs_argument_needs_the_shift_to_light_them(tmp_path):
    # Legs given, but the frame doesn't move: nothing to call still.
    doc = pxart.parse(anim_file(tmp_path, IDLE_4[0], IDLE_4[0], name="mo.px"))
    prev, cur = (doc.image(f) for f in doc.frames)
    assert pxart.motion(prev, cur, legs=10)[4] is None


def test_motion_first_identical_row_is_reported(tmp_path):
    # Rows 9+ identical; the old tie-break named a lower row whenever the row below had nothing left to explain.
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, IDLE_4[0], IDLE_4[1])
    assert still == 9
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, IDLE_4[1], IDLE_4[0])
    assert still == 9


def test_help_documents_the_breath_symmetry():
    doc = " ".join(pxart.__doc__.split())
    assert "rows Y down are identical in every frame of the animation" in doc
    assert "the rise and the fall of a breath read alike" in doc


# ---------------------------------------------------------------- loop J: -o in another directory re-points @palette

REPOINT_PAL = "k #101010\nr #c02020\ng #20c020\nw #f0f0f0\n\n@variant night\nr #400000\n"
REPOINT_SPRITE = "pxart 1\n# shared colors\n@palette ../pal.px\n\n@anim walk ms=90\n\n@frame walk/0\nkr..\nkrg.\n.kkr\nkkkk\n@frame walk/1\nrk..\nkgr.\n.kkr\nkkkk\n"

# Every command that writes a .px with -o: argv with {p} for the sprite, {s} for a second sprite.
REPOINT_CMDS = {
    "flip": ["flip", "{p}"],
    "flip-sel": ["flip", "{p}:walk/0"],
    "flip-v": ["flip", "{p}", "--v"],
    "rotate": ["rotate", "{p}", "90"],
    "transpose": ["transpose", "{p}"],
    "shift": ["shift", "{p}", "--dx", "1"],
    "shift-wrap": ["shift", "{p}", "--dx", "1", "--wrap"],
    "mask": ["mask", "{p}", "--keep", "0,0,2,2"],
    "recolor": ["recolor", "{p}", "k=r"],
    "recolor-color": ["recolor", "{p}", "g=#00ff00"],
    "set": ["set", "{p}:walk/0", "w", "0,0"],
    "fill": ["fill", "{p}", "w", "--region", "0,0,1,1"],
    "line": ["line", "{p}", "w", "0,0", "3,3"],
    "rect": ["rect", "{p}", "w", "0,0,2,2"],
    "poly": ["poly", "{p}", "w", "0,0", "3,0", "3,3", "--fill"],
    "paste-under": ["paste", "{s}:walk/0", "--into", "{p}", "--at", "1,1", "--under"],
    "ellipse": ["ellipse", "{p}", "w", "1,1,1,1"],
    "arc": ["arc", "{p}", "w", "2,2,2", "0,90"],
    "flood": ["flood", "{p}", "w", "3,0"],
    "outline": ["outline", "{p}", "--key", "w"],
    "shade": ["shade", "{p}", "--ramp", "krw", "--keys", "k"],
    "paste": ["paste", "{s}:walk/0", "--into", "{p}", "--at", "1,1"],
    "dup": ["dup", "{p}:walk/0", "walk/2"],
    "anim-set": ["anim-set", "{p}:walk", "ms=50"],
    "anim-set-frame": ["anim-set", "{p}:walk/1", "ms=50"],
    "extract": ["extract", "{p}:walk/1"],
}


def repoint_setup(tmp_path):
    write(tmp_path, "pal.px", REPOINT_PAL)
    (tmp_path / "sprites").mkdir()
    p = write(tmp_path / "sprites", "h.px", REPOINT_SPRITE)
    s = write(tmp_path / "sprites", "s.px", "@palette ../pal.px\n@frame walk/0\nww\nw.\n")
    return p, s


def repoint_run(tmp_path, name, out):
    p, s = repoint_setup(tmp_path)
    argv = [a.format(p=p, s=s) for a in REPOINT_CMDS[name]] + ["-o", out]
    assert run(*argv) == 0
    return p


@pytest.mark.parametrize("name", sorted(REPOINT_CMDS))
def test_repoint_deeper_directory(tmp_path, name):
    out = tmp_path / "out" / "deep" / "x.px"
    repoint_run(tmp_path, name, out)
    doc = pxart.parse(out)
    assert doc.palette_refs == ["../../pal.px"]
    assert "@palette ../../pal.px\n" in out.read_text() and "@palette ../pal.px" not in out.read_text()


@pytest.mark.parametrize("name", sorted(REPOINT_CMDS))
def test_repoint_parent_directory(tmp_path, name):
    out = tmp_path / "x.px"
    repoint_run(tmp_path, name, out)
    assert pxart.parse(out).palette_refs == ["pal.px"]


@pytest.mark.parametrize("name", sorted(REPOINT_CMDS))
def test_repoint_sibling_directory(tmp_path, name):
    out = tmp_path / "art" / "x.px"
    repoint_run(tmp_path, name, out)
    assert pxart.parse(out).palette_refs == ["../pal.px"]


@pytest.mark.parametrize("name", sorted(REPOINT_CMDS))
def test_repoint_same_directory_keeps_the_line(tmp_path, name):
    out = tmp_path / "sprites" / "x.px"
    repoint_run(tmp_path, name, out)
    assert pxart.parse(out).palette_refs == ["../pal.px"]


@pytest.mark.parametrize("name", sorted(REPOINT_CMDS))
def test_repoint_output_renders_like_the_source_palette(tmp_path, name):
    out = tmp_path / "out" / "deep" / "x.px"
    repoint_run(tmp_path, name, out)
    doc = pxart.parse(out)
    pal = pxart.parse(tmp_path / "pal.px", palette_only=True)
    assert doc.shared == pal.palette and doc.shared_variants == pal.variants
    for f in doc.frames:
        doc.image(f), doc.image(f, "night")  # every key resolves, in every variant


@pytest.mark.parametrize("name", sorted(REPOINT_CMDS))
def test_repoint_leaves_the_source_alone(tmp_path, name):
    p = repoint_run(tmp_path, name, tmp_path / "out" / "x.px")
    assert p.read_text() == REPOINT_SPRITE


@pytest.mark.parametrize("name", sorted(REPOINT_CMDS))
def test_repoint_keeps_the_comment_above_the_import(tmp_path, name):
    out = tmp_path / "out" / "x.px"
    repoint_run(tmp_path, name, out)
    assert "# shared colors\n@palette ../../pal.px\n" not in out.read_text()  # one level down, not two
    assert "# shared colors\n@palette ../pal.px\n" in out.read_text()


@pytest.mark.parametrize("name", sorted(REPOINT_CMDS))
def test_repoint_output_can_be_edited_in_place_after(tmp_path, name):
    out = tmp_path / "out" / "x.px"
    repoint_run(tmp_path, name, out)
    assert run("flip", out) == 0
    assert pxart.parse(out).palette_refs == ["../pal.px"]


def test_repoint_recolor_is_the_reported_case(tmp_path):
    p, _ = repoint_setup(tmp_path)
    out = tmp_path / "other" / "dir" / "x.px"
    assert run("recolor", p, "k=r", "-o", out) == 0
    assert out.read_text().startswith("pxart 1\n# shared colors\n@palette ../../pal.px\n\n@anim walk ms=90\n")
    assert run("check", out) == 0


def test_repoint_recolor_exact_text(tmp_path):
    p, _ = repoint_setup(tmp_path)
    out = tmp_path / "art" / "x.px"
    assert run("recolor", p, "k=r", "-o", out) == 0
    assert out.read_text() == ("pxart 1\n# shared colors\n@palette ../pal.px\n\n@anim walk ms=90\n\n@frame walk/0\n"
                               "rr..\nrrg.\n.rrr\nrrrr\n@frame walk/1\nrr..\nrgr.\n.rrr\nrrrr\n")


def test_repoint_absolute_palette_path_stays(tmp_path):
    pal = write(tmp_path, "pal.px", REPOINT_PAL)
    (tmp_path / "sprites").mkdir()
    p = write(tmp_path / "sprites", "h.px", f"@palette {pal}\n@frame a\nkr\n")
    out = tmp_path / "out" / "deep" / "x.px"
    assert run("flip", p, "-o", out) == 0
    assert pxart.parse(out).palette_refs == [str(pal)]


def test_repoint_two_imports_both_move(tmp_path):
    write(tmp_path, "a.px", "k #000000\n")
    (tmp_path / "pals").mkdir()
    write(tmp_path / "pals", "b.px", "r #ff0000\n")
    (tmp_path / "sprites").mkdir()
    p = write(tmp_path / "sprites", "h.px", "@palette ../a.px\n@palette ../pals/b.px\n@frame a\nkr\n")
    out = tmp_path / "x" / "y" / "z.px"
    assert run("recolor", p, "k=r", "-o", out) == 0
    assert pxart.parse(out).palette_refs == ["../../a.px", "../../pals/b.px"]


def test_repoint_into_the_palettes_own_directory(tmp_path):
    write(tmp_path, "pal.px", "k #000000\nr #ff0000\n")
    (tmp_path / "sprites").mkdir()
    p = write(tmp_path / "sprites", "h.px", "@palette ../pal.px\n@frame a\nkr\n")
    assert run("set", p, "r", "0,0", "-o", tmp_path / "h2.px") == 0
    assert (tmp_path / "h2.px").read_text() == "@palette pal.px\n@frame a\nrr\n"


def test_repoint_relative_cwd_paths(tmp_path, monkeypatch):
    write(tmp_path, "pal.px", "k #000000\nr #ff0000\n")
    (tmp_path / "sprites").mkdir()
    write(tmp_path / "sprites", "h.px", "@palette ../pal.px\n@frame a\nkr\n")
    monkeypatch.chdir(tmp_path)
    assert run("recolor", "sprites/h.px", "k=r", "-o", "art/deep/x.px") == 0
    assert pxart.parse(tmp_path / "art" / "deep" / "x.px").palette_refs == ["../../pal.px"]


def test_repoint_no_palette_is_untouched(tmp_path):
    (tmp_path / "sprites").mkdir()
    p = write(tmp_path / "sprites", "h.px", "k #000000\n@frame a\nk.\n")
    assert run("flip", p, "-o", tmp_path / "o" / "x.px") == 0
    assert (tmp_path / "o" / "x.px").read_text() == "k #000000\n@frame a\n.k\n"


def test_repoint_put_to_another_directory(tmp_path, monkeypatch):
    p, _ = repoint_setup(tmp_path)
    out = tmp_path / "art" / "deep" / "x.px"
    assert put(monkeypatch, "ww\nww\n", f"{p}:walk/1", "-o", out) == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == ["../../pal.px"] and doc.get("walk/1").grid == ["ww", "ww"]


def test_repoint_mask_png_unaffected(tmp_path):
    img = Image.new("RGBA", (2, 2), (9, 9, 9, 255))
    img.save(tmp_path / "a.png")
    assert run("mask", tmp_path / "a.png", "--keep", "0,0,1,1", "-o", tmp_path / "d" / "b.png") == 0
    assert Image.open(tmp_path / "d" / "b.png").getpixel((1, 1))[3] == 0


def test_repoint_helper_directly(tmp_path):
    p, _ = repoint_setup(tmp_path)
    doc = pxart.parse(p)
    pxart.repoint(doc, tmp_path / "a" / "b" / "c.px")
    assert doc.palette_refs == ["../../pal.px"] and ("palref", "../../pal.px") in doc.lead
    pxart.repoint(doc, tmp_path / "sprites" / "same.px")  # doc.path's own directory: nothing to do
    assert doc.palette_refs == ["../../pal.px"]


def test_help_documents_repointing():
    doc = " ".join(pxart.__doc__.split())
    assert "An OUT in another directory gets its @palette lines re-pointed from there" in doc


# ---------------------------------------------------------------- loop J: a new compose OUT keeps the whole palette

CPAL = "k #101010\nd #402020\nm #804040\nl #c08080\nw #f0e0e0\n\n@variant night\nm #202040\nl #303060\n"


def cpal_setup(tmp_path, parts="@palette pal.px\n@still *\n@frame body\nmmm\nmmm\n@frame hat\nk.\nkk\n"):
    write(tmp_path, "pal.px", CPAL)
    return write(tmp_path, "parts.px", parts)


def test_compose_new_out_keeps_shared_palette(tmp_path):
    p = cpal_setup(tmp_path)
    out = tmp_path / "hero.px"
    assert run("compose", "-o", out, f"{p}:body@0,0", f"{p}:hat@0,0") == 0
    assert out.read_text() == "pxart 1\n@palette pal.px\n\nkmm\nkkm\n"


def test_compose_new_out_then_shade_with_unused_ramp_keys(tmp_path):
    # The reported case: the ramp's d, l, w aren't used by any layer; they must still be in OUT's palette.
    p = cpal_setup(tmp_path)
    out = tmp_path / "hero.px"
    assert run("compose", "-o", out, f"{p}:body@0,0") == 0
    assert run("shade", out, "--ramp", "dmlw", "--keys", "m") == 0


def test_compose_new_out_then_recolor_to_unused_key(tmp_path):
    p = cpal_setup(tmp_path)
    out = tmp_path / "hero.px"
    assert run("compose", "-o", out, f"{p}:body@0,0") == 0
    assert run("recolor", out, "m=w") == 0 and pxart.parse(out).frames[0].grid == ["www", "www"]


def test_compose_new_out_in_another_directory_repoints(tmp_path):
    p = cpal_setup(tmp_path)
    out = tmp_path / "art" / "deep" / "hero.px"
    assert run("compose", "-o", out, f"{p}:body@0,0") == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == ["../../pal.px"] and doc.palette == {}
    assert set(doc.resolved()) == set("kdmlw.")


def test_compose_new_out_named_frame_keeps_shared_palette(tmp_path):
    p = cpal_setup(tmp_path)
    out = tmp_path / "hero.px"
    assert run("compose", "-o", f"{out}:idle/0", f"{p}:body@0,0") == 0
    assert out.read_text() == "pxart 1\n@palette pal.px\n\n@frame idle/0\nmmm\nmmm\n"


def test_compose_new_out_variant_comes_from_the_import(tmp_path):
    p = cpal_setup(tmp_path)
    out = tmp_path / "hero.px"
    assert run("compose", "-o", out, f"{p}:body@0,0") == 0
    doc = pxart.parse(out)
    assert doc.image(doc.frames[0], "night").getpixel((0, 0)) == (0x20, 0x20, 0x40, 255)
    assert doc.variants == {}  # nothing to copy: the import brings it


def test_compose_new_out_renders_like_the_layer(tmp_path):
    p = cpal_setup(tmp_path)
    out = tmp_path / "hero.px"
    assert run("compose", "-o", out, f"{p}:body@0,0") == 0
    src, doc = pxart.parse(p), pxart.parse(out)
    for v in (None, "night"):
        assert doc.image(doc.frames[0], v).tobytes() == src.image(src.get("body"), v).tobytes()


def test_compose_new_out_layer_local_keys_all_come(tmp_path):
    p = cpal_setup(tmp_path, "@palette pal.px\nz #00ff00\ny #ffff00\n@frame body\nmz\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:body@0,0") == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == ["pal.px"] and doc.palette == {"z": (0, 255, 0, 255), "y": (255, 255, 0, 255)}


def test_compose_new_out_used_local_keys_come_first(tmp_path):
    p = cpal_setup(tmp_path, "@palette pal.px\nz #00ff00\ny #ffff00\n@frame body\nmy\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:body@0,0") == 0
    assert list(pxart.parse(out).palette) == ["y", "z"]


def test_compose_new_out_local_override_of_import_stays(tmp_path):
    p = cpal_setup(tmp_path, "@palette pal.px\nm #00ff00\n@frame body\nmk\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:body@0,0") == 0
    doc = pxart.parse(out)
    assert doc.palette == {"m": (0, 255, 0, 255)} and doc.resolved()["m"] == (0, 255, 0, 255)
    assert doc.image(doc.frames[0]).tobytes() == pxart.parse(p).image(pxart.parse(p).frames[0]).tobytes()


def test_compose_new_out_unused_override_of_import_stays_too(tmp_path):
    p = cpal_setup(tmp_path, "@palette pal.px\nw #00ff00\n@frame body\nmk\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:body@0,0") == 0
    assert pxart.parse(out).resolved()["w"] == (0, 255, 0, 255)


def test_compose_new_out_different_imports_inline_everything(tmp_path):
    write(tmp_path, "pal.px", CPAL)
    write(tmp_path, "pal2.px", "q #123456\nr #654321\n")
    a = write(tmp_path, "a.px", "@palette pal.px\n@frame body\nmm\n")
    b = write(tmp_path, "b.px", "@palette pal2.px\n@frame hat\nq.\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}:body@0,0", f"{b}:hat@0,0") == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == [] and list(doc.palette) == ["m", "q", "k", "d", "l", "w", "r"]
    assert out.read_text().startswith("pxart 1\nm #804040\nq #123456\nk #101010\n")


def test_compose_new_out_inlined_variants_come_along(tmp_path):
    write(tmp_path, "pal.px", CPAL)
    write(tmp_path, "pal2.px", "q #123456\n")
    a = write(tmp_path, "a.px", "@palette pal.px\n@frame body\nmm\n")
    b = write(tmp_path, "b.px", "@palette pal2.px\n@frame hat\nq.\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}:body@0,0", f"{b}:hat@0,0") == 0
    doc = pxart.parse(out)
    assert doc.variants == {"night": {"m": (0x20, 0x20, 0x40, 255), "l": (0x30, 0x30, 0x60, 255)}}
    src = pxart.parse(a)
    assert doc.image(doc.frames[0], "night").getpixel((1, 0)) == src.image(src.frames[0], "night").getpixel((1, 0))


def test_compose_new_out_one_layer_without_import_inlines(tmp_path):
    write(tmp_path, "pal.px", CPAL)
    a = write(tmp_path, "a.px", "@palette pal.px\n@frame body\nmm\n")
    b = write(tmp_path, "b.px", "q #123456\n@frame hat\nq.\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}:body@0,0", f"{b}:hat@0,0") == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == [] and set(doc.palette) == set("mqkdlw")


def test_compose_new_out_no_imports_inlines_all_keys(tmp_path):
    a = write(tmp_path, "a.px", "k #000000\nz #ffffff\n@frame x\nk\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}:x@0,0") == 0
    assert out.read_text() == "pxart 1\nk #000000\nz #ffffff\n\nk\n"


def test_compose_new_out_local_variant_copied(tmp_path):
    a = write(tmp_path, "a.px", "k #000000\nz #ffffff\n\n@variant night\nz #000080\n@frame x\nk\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}:x@0,0") == 0
    assert pxart.parse(out).variants == {"night": {"z": (0, 0, 0x80, 255)}}


def test_compose_new_out_local_variant_over_kept_import(tmp_path):
    p = cpal_setup(tmp_path, "@palette pal.px\n\n@variant night\nk #ff0000\n@frame body\nmk\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:body@0,0") == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == ["pal.px"] and doc.variants == {"night": {"k": (255, 0, 0, 255)}}
    assert doc.image(doc.frames[0], "night").getpixel((1, 0)) == (255, 0, 0, 255)


def test_compose_new_out_unused_conflicting_key_left_out_with_note(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nz #ffffff\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "j #00ff00\nz #ff0000\n@frame y\nj\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:y@1,0") == 0
    assert pxart.parse(out).palette == {"k": (0, 0, 0, 255), "j": (0, 255, 0, 255), "z": (255, 255, 255, 255)}
    assert capsys.readouterr().out.splitlines()[0] == (
        f"note: {out} leaves out layer 2 ({b}:y)'s colors for z, a key that layer doesn't draw with (so it doesn't "
        f"conflict), and has other layers' colors for it: 'z' #ff0000 (#ffffff there, from layer 1 ({a}:x), which "
        "doesn't draw with it either: the earlier layer's)")


def keynote_layers(tmp_path):
    # GAMES-295 repro: b shares keys with a in other colors; b uses h and n, a uses w; c uses q.
    a = write(tmp_path, "a.px", "h #111111\nn #222222\nr #333333\nw #eee0b8\nk #000000\n\nkw\n")
    b = write(tmp_path, "b.px", "h #aaaaaa\nn #bbbbbb\nr #cccccc\nw #f6ecd2\nq #123456\n\nhn\n")
    c = write(tmp_path, "c.px", "q #654321\n\nq\n")
    return a, b, c


def notes_of(out):
    return [l for l in out.splitlines() if l.startswith("note:") and "leaves out" in l]


def test_compose_key_note_names_only_colors_left_out_and_why(tmp_path, capsys):
    a, b, c = keynote_layers(tmp_path)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "3x3", f"{a}@0,0", f"{b}@0,1", f"{c}@1,1") == 0
    assert notes_of(capsys.readouterr().out) == [
        f"note: {out} leaves out layer 1 ({a})'s colors for h n, keys that layer doesn't draw with (so they don't "
        f"conflict), and has other layers' colors for them: 'h' #111111 (#aaaaaa there, from layer 2 ({b}), which "
        f"draws with it), 'n' #222222 (#bbbbbb there, from layer 2 ({b}), which draws with it)",
        f"note: {out} leaves out layer 2 ({b})'s colors for r w q, keys that layer doesn't draw with (so they don't "
        f"conflict), and has other layers' colors for them: 'r' #cccccc (#333333 there, from layer 1 ({a}), which "
        f"doesn't draw with it either: the earlier layer's), 'w' #f6ecd2 (#eee0b8 there, from layer 1 ({a}), which "
        f"draws with it), 'q' #123456 (#654321 there, from layer 3 ({c}), which draws with it)",
    ]


def test_compose_key_note_matches_the_palette_written(tmp_path, capsys):
    # Every key a note names is in OUT, in the color of the layer the note says it has.
    a, b, c = keynote_layers(tmp_path)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "3x3", f"{a}@0,0", f"{b}@0,1", f"{c}@1,1") == 0
    pal = pxart.parse(out).palette
    assert pal == {"w": pxart.hex2rgba("#eee0b8"), "k": (0, 0, 0, 255), "h": pxart.hex2rgba("#aaaaaa"),
                   "n": pxart.hex2rgba("#bbbbbb"), "q": pxart.hex2rgba("#654321"), "r": pxart.hex2rgba("#333333")}
    docs = {"1": pxart.parse(a), "2": pxart.parse(b), "3": pxart.parse(c)}
    import re
    lines = notes_of(capsys.readouterr().out)
    assert len(lines) == 2
    for line in lines:
        lost = re.match(r"note: .* leaves out layer (\d) ", line).group(1)
        for keys, kept in re.findall(r"'(\w+)' \(layer (\d)'s", line):
            for k in keys:
                assert k in pal and pal[k] == docs[kept].palette[k] != docs[lost].palette[k]
                assert k not in "".join(docs[lost].frames[0].grid)


def test_compose_key_note_absent_when_nothing_is_left_out(tmp_path, capsys):
    a, b, c = keynote_layers(tmp_path)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}@0,0", f"{c}@0,1") == 0
    assert notes_of(capsys.readouterr().out) == []


def test_compose_key_note_same_color_is_not_left_out(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nz #ffffff\n\nk\n")
    b = write(tmp_path, "b.px", "j #00ff00\nz #ffffff\n\nj\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}@0,0", f"{b}@1,0") == 0
    assert notes_of(capsys.readouterr().out) == []


def test_compose_key_note_only_for_a_new_out(tmp_path, capsys):
    a, b, c = keynote_layers(tmp_path)
    out = write(tmp_path, "o.px", "k #000000\n@frame x\nk\n")
    assert run("compose", "-o", f"{out}:y", f"{c}@0,0") == 0
    assert notes_of(capsys.readouterr().out) == []


def test_compose_key_note_later_used_key_beats_both_unused(tmp_path, capsys):
    # z unused in layers 1 and 2 (two colors), used in layer 3: OUT has layer 3's, and both others are named.
    a = write(tmp_path, "a.px", "k #000000\nz #111111\n\nk\n")
    b = write(tmp_path, "b.px", "k #000000\nz #222222\n\nk\n")
    c = write(tmp_path, "c.px", "z #333333\n\nz\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "3x1", f"{a}@0,0", f"{b}@1,0", f"{c}@2,0") == 0
    assert pxart.parse(out).palette["z"] == pxart.hex2rgba("#333333")
    assert notes_of(capsys.readouterr().out) == [
        f"note: {out} leaves out layer 1 ({a})'s colors for z, a key that layer doesn't draw with (so it doesn't "
        f"conflict), and has other layers' colors for it: 'z' #111111 (#333333 there, from layer 3 ({c}), which draws "
        "with it)",
        f"note: {out} leaves out layer 2 ({b})'s colors for z, a key that layer doesn't draw with (so it doesn't "
        f"conflict), and has other layers' colors for it: 'z' #222222 (#333333 there, from layer 3 ({c}), which draws "
        "with it)",
    ]


def test_compose_new_out_used_key_beats_an_unused_one(tmp_path):
    # Layer 1 has z unused (white); layer 2 uses z (red): the used color wins, no conflict.
    a = write(tmp_path, "a.px", "k #000000\nz #ffffff\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "z #ff0000\n@frame y\nz\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:y@1,0") == 0
    doc = pxart.parse(out)
    assert doc.palette["z"] == (255, 0, 0, 255) and doc.frames[0].grid == ["kz"]


def test_compose_new_out_used_conflict_still_errors(tmp_path):
    a = write(tmp_path, "a.px", "k #000000\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "k #ffffff\n@frame y\nk\n")
    msg = run_err("compose", "-o", tmp_path / "o.px", "--size", "2x1", f"{a}:x@0,0", f"{b}:y@1,0")
    assert msg.startswith(f"compose: layer 2 ({b}:y): ") and "E_KEY_CONFLICT" in msg
    assert not (tmp_path / "o.px").exists()


def test_compose_new_out_same_file_twice_keys_once(tmp_path):
    p = cpal_setup(tmp_path)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:body@0,0", f"{p}:body@1,0", f"{p}:hat@0,0") == 0
    assert out.read_text().count("@palette") == 1


def test_compose_new_out_flipped_layer_keeps_palette(tmp_path):
    p = cpal_setup(tmp_path)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:hat+h@0,0") == 0
    assert out.read_text() == "pxart 1\n@palette pal.px\n\n.k\nkk\n"


def test_compose_same_palette_spelled_differently_is_kept(tmp_path):
    write(tmp_path, "pal.px", CPAL)
    (tmp_path / "sub").mkdir()
    a = write(tmp_path, "a.px", "@palette pal.px\n@frame x\nm\n")
    b = write(tmp_path / "sub", "b.px", "@palette ../pal.px\n@frame y\nk\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:y@1,0") == 0
    assert pxart.parse(out).palette_refs == ["pal.px"] and pxart.parse(out).palette == {}


def test_compose_existing_out_keeps_old_behavior(tmp_path):
    p = cpal_setup(tmp_path)
    out = write(tmp_path, "o.px", "j #00ff00\n@frame a\nj\n")
    assert run("compose", "-o", f"{out}:b", f"{p}:hat@0,0") == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == [] and set(doc.palette) == {"j", "k"}  # only the used key joins, as before


def test_compose_existing_palette_only_out_keeps_old_behavior(tmp_path):
    p = cpal_setup(tmp_path)
    out = write(tmp_path, "o.px", "j #00ff00\n")
    assert run("compose", "-o", f"{out}:b", f"{p}:hat@0,0") == 0
    assert set(pxart.parse(out).palette) == {"j", "k"}


def test_crop_new_out_keeps_shared_palette(tmp_path):
    p = cpal_setup(tmp_path)
    out = tmp_path / "c.px"
    assert run("crop", f"{p}:body", "0,0,2,1", "-o", out) == 0
    assert out.read_text() == "pxart 1\n@palette pal.px\n\nmm\n"


def test_crop_new_out_in_another_directory_repoints(tmp_path):
    p = cpal_setup(tmp_path)
    out = tmp_path / "x" / "c.px"
    assert run("crop", f"{p}:body", "0,0,2,1", "-o", out) == 0
    assert pxart.parse(out).palette_refs == ["../pal.px"]


def test_crop_new_out_inline_file_keeps_all_keys(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nz #ffffff\nkk\nkk\n")
    out = tmp_path / "c.px"
    assert run("crop", p, "0,0,1,1", "-o", out) == 0
    assert out.read_text() == "pxart 1\nk #000000\nz #ffffff\n\nk\n"


def test_seed_palette_returns_left_out_keys(tmp_path):
    a = write(tmp_path, "a.px", "k #000000\nz #ffffff\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "j #00ff00\nz #ff0000\n@frame y\nj\n")
    layers = [(pxart.place_item(f"{a}:x", "layer"), 0, 0, "l1"), (pxart.place_item(f"{b}:y", "layer"), 0, 0, "l2")]
    doc = pxart.Doc(tmp_path / "o.px")
    left, whose = pxart.seed_palette(doc, layers)
    assert left == [("z", "l2", "l1", False)] and list(doc.palette) == ["k", "j", "z"]
    assert whose == {"k": ("l1", True), "j": ("l2", True), "z": ("l1", False)}


def test_help_documents_compose_new_palette():
    doc = " ".join(pxart.__doc__.split())
    assert "A new OUT starts with the layers' whole palettes, used or not" in doc
    assert "crop writes a new OUT the same way" in doc


# ---------------------------------------------------------------- loop J: a single unnamed grid goes by the file's name

ANT = "pxart 1\nk #000000\ng #00ff00\n\n...\n.k.\n"


def test_unnamed_grid_selected_by_stem(tmp_path):
    p = write(tmp_path, "ant.px", ANT)
    doc = pxart.parse(p)
    assert doc.select("ant") == doc.frames


def test_unnamed_grid_other_selector_still_e_select(tmp_path):
    p = write(tmp_path, "ant.px", ANT)
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p).select("bee")
    assert codes(e) == ["E_SELECT"] and "frames: ant" in str(e.value)


def test_unnamed_grid_frames_lists_the_stem(tmp_path, capsys):
    p = write(tmp_path, "ant.px", ANT)
    assert run("frames", p) == 0
    assert "  ant  3x2" in capsys.readouterr().out


def test_unnamed_grid_frames_with_stem_selector(tmp_path, capsys):
    p = write(tmp_path, "ant.px", ANT)
    assert run("frames", f"{p}:ant") == 0
    assert "  ant  3x2" in capsys.readouterr().out


def test_new_then_compose_named_by_stem_reported_case(tmp_path, capsys):
    p = tmp_path / "ant.px"
    parts = write(tmp_path, "parts.px", "k #000000\n@frame dot\nk\n")
    assert run("new", p, "--size", "3x2") == 0
    assert run("compose", "-o", f"{p}:ant", f"{parts}:dot@1,1") == 0
    assert p.read_text() == "pxart 1\nk #000000\n\n@frame ant\n...\n.k.\n"
    assert "note: " in capsys.readouterr().out


def test_compose_named_by_stem_keeps_size_of_the_grid(tmp_path):
    p = write(tmp_path, "ant.px", ANT)
    parts = write(tmp_path, "parts.px", "g #00ff00\n@frame dot\ng\n")
    assert run("compose", "-o", f"{p}:ant", f"{parts}:dot@0,0") == 0
    doc = pxart.parse(p)
    assert [f.id for f in doc.frames] == ["ant"] and doc.get("ant").grid == ["g..", "..."]


def test_compose_named_by_stem_prints_a_note(tmp_path, capsys):
    p = write(tmp_path, "ant.px", ANT)
    assert run("compose", "-o", f"{p}:ant", f"{p}:ant@0,0") == 0
    assert f"note: {p}'s unnamed grid is now '@frame ant' (the id it went by)" in capsys.readouterr().out


def test_compose_named_by_stem_same_pixels_writes_the_frame_line(tmp_path):
    p = write(tmp_path, "ant.px", ANT)
    assert run("compose", "-o", f"{p}:ant", f"{p}:ant@0,0") == 0
    assert p.read_text() == "pxart 1\nk #000000\ng #00ff00\n\n@frame ant\n...\n.k.\n"


def test_compose_other_id_promotes_and_adds(tmp_path):
    p = write(tmp_path, "ant.px", ANT)
    assert run("compose", "-o", f"{p}:walk/0", f"{p}:ant@0,0") == 0
    doc = pxart.parse(p)
    assert [f.id for f in doc.frames] == ["ant", "walk/0"] and doc.get("walk/0").grid == doc.get("ant").grid


def test_promote_keeps_comments_above_the_grid(tmp_path):
    p = write(tmp_path, "ant.px", "# top\nk #000000\n\n# the ant\nk.\n.k\n")
    assert run("compose", "-o", f"{p}:ant", f"{p}:ant@0,0") == 0
    assert p.read_text() == "# top\nk #000000\n\n# the ant\n@frame ant\nk.\n.k\n"


def test_promote_without_blank_line_above_the_grid(tmp_path):
    p = write(tmp_path, "ant.px", "k #000000\nk.\n.k\n")
    assert run("compose", "-o", f"{p}:ant", f"{p}:ant@0,0") == 0
    assert p.read_text() == "k #000000\n\n@frame ant\nk.\n.k\n"


def test_promote_keeps_row_spelling_and_crlf(tmp_path):
    p = tmp_path / "ant.px"
    p.write_bytes(b"k #000000\r\n\r\nk.\r\n.k\r\n")
    assert run("compose", "-o", f"{p}:x", f"{p}:ant@0,0") == 0
    assert p.read_bytes() == b"k #000000\r\n\r\n@frame ant\r\nk.\r\n.k\r\n\r\n@frame x\r\nk.\r\n.k\r\n"


def test_promote_result_parses_as_named(tmp_path):
    p = write(tmp_path, "ant.px", ANT)
    assert run("compose", "-o", f"{p}:ant", f"{p}:ant@0,0") == 0
    doc = pxart.parse(p)
    assert not doc.implicit and doc.frames[0].id == "ant"


def test_put_named_by_stem(tmp_path, monkeypatch):
    p = write(tmp_path, "ant.px", ANT)
    assert put(monkeypatch, "kk\nkk\n", f"{p}:ant") == 0
    assert p.read_text() == "pxart 1\nk #000000\ng #00ff00\n\n@frame ant\nkk\nkk\n"


def test_new_named_by_stem_is_dup_frame(tmp_path):
    p = write(tmp_path, "ant.px", ANT)
    assert "E_DUP_FRAME" in run_err("new", f"{p}:ant", "--size", "1x1")
    assert p.read_text() == ANT


def test_crop_into_named_by_stem(tmp_path):
    p = write(tmp_path, "ant.px", ANT)
    src = write(tmp_path, "src.px", "k #000000\nkkk\nk.k\n")
    assert run("crop", src, "0,0,3,2", "-o", f"{p}:ant") == 0
    assert pxart.parse(p).get("ant").grid == ["kkk", "k.k"]


def test_edit_commands_accept_stem_selector(tmp_path):
    p = write(tmp_path, "ant.px", ANT)
    assert run("set", f"{p}:ant", "g", "0,0") == 0
    assert p.read_text() == "pxart 1\nk #000000\ng #00ff00\n\ng..\n.k.\n"  # stays unnamed: only pixels changed


def test_render_accepts_stem_selector(tmp_path):
    p = write(tmp_path, "ant.px", ANT)
    assert run("render", f"{p}:ant", "-o", tmp_path / "r.png") == 0


def test_stem_that_is_not_an_id_stays_mixed(tmp_path):
    p = write(tmp_path, "my ant.px", ANT)
    msg = run_err("compose", "-o", f"{p}:x", f"{p}@0,0")
    assert "E_MIXED_FRAMES" in msg and "'my ant' can't be a frame id" in msg
    assert p.read_text() == ANT


def test_from_png_into_unnamed_grid_file_promotes(tmp_path, capsys):
    p = write(tmp_path, "ant.px", ANT)
    Image.new("RGBA", (3, 2), (0, 0, 0, 255)).save(tmp_path / "leg.png")
    assert run("from-png", tmp_path / "leg.png", "-o", p) == 0
    doc = pxart.parse(p)
    assert [f.id for f in doc.frames] == ["ant", "leg"] and doc.get("leg").grid == ["kkk", "kkk"]
    assert "unnamed grid is now '@frame ant'" in capsys.readouterr().out


def test_from_png_same_stem_replaces_the_promoted_grid(tmp_path):
    p = write(tmp_path, "ant.px", ANT)
    Image.new("RGBA", (3, 2), (0, 0, 0, 255)).save(tmp_path / "ant.png")
    assert run("from-png", tmp_path / "ant.png", "-o", p) == 0
    doc = pxart.parse(p)
    assert [f.id for f in doc.frames] == ["ant"] and doc.get("ant").grid == ["kkk", "kkk"]


def test_doc_promote_directly(tmp_path):
    doc = pxart.parse(write(tmp_path, "ant.px", ANT))
    doc.promote()
    assert not doc.implicit and doc.frames[0].id == "ant" and doc.select("ant") == doc.frames
    assert doc.text() == "pxart 1\nk #000000\ng #00ff00\n\n@frame ant\n...\n.k.\n"


def test_help_documents_unnamed_grid_id():
    doc = " ".join(pxart.__doc__.split())
    assert "A file with one unnamed grid (no @frame) calls it by the file's name, as frames lists it" in doc
    assert "first makes the grid '@frame ant'" in doc


# ---------------------------------------------------------------- loop J: paste takes +h / +v like compose and scene

PASTE_SRC = "k #000000\ng #00ff00\n@frame arm\nkg.\nk..\n"
PASTE_DST = "k #000000\ng #00ff00\n@frame body\n....\n....\n....\n"


def paste_setup(tmp_path):
    return write(tmp_path, "src.px", PASTE_SRC), write(tmp_path, "dst.px", PASTE_DST)


@pytest.mark.parametrize("flip, grid", [
    ("", ["kg..", "k...", "...."]),
    ("+h", [".gk.", "..k.", "...."]),
    ("+v", ["k...", "kg..", "...."]),
    ("+hv", ["..k.", ".gk.", "...."]),
    ("+vh", ["..k.", ".gk.", "...."]),
])
def test_paste_flip_grids(tmp_path, flip, grid):
    src, dst = paste_setup(tmp_path)
    assert run("paste", f"{src}:arm{flip}", "--into", dst, "--at", "0,0") == 0
    assert pxart.parse(dst).get("body").grid == grid


def test_paste_flip_at_offset(tmp_path):
    src, dst = paste_setup(tmp_path)
    assert run("paste", f"{src}:arm+h", "--into", dst, "--at", "1,1") == 0
    assert pxart.parse(dst).get("body").grid == ["....", "..gk", "...k"]


def test_paste_flip_matches_compose_layer_flip(tmp_path):
    src, dst = paste_setup(tmp_path)
    for flip in ("+h", "+v", "+hv"):
        d = write(tmp_path, f"d{flip}.px", PASTE_DST)
        assert run("paste", f"{src}:arm{flip}", "--into", d, "--at", "0,0") == 0
        c = tmp_path / f"c{flip}.px"
        assert run("compose", "-o", c, "--size", "4x3", f"{src}:arm{flip}@0,0") == 0
        assert pxart.parse(d).get("body").grid == pxart.parse(c).frames[0].grid, flip


def test_paste_flip_region_is_in_flipped_coordinates(tmp_path):
    src, dst = paste_setup(tmp_path)
    assert run("paste", f"{src}:arm+h", "--into", dst, "--at", "0,0", "--region", "1,0,2,1") == 0
    assert pxart.parse(dst).get("body").grid == ["gk..", "....", "...."]


def test_paste_flip_with_variant_suffix(tmp_path):
    src = write(tmp_path, "src.px", "k #000000\ng #00ff00\n\n@variant night\ng #004400\n@frame arm\nkg.\nk..\n")
    dst = write(tmp_path, "dst.px", PASTE_DST)
    assert run("paste", f"{src}:arm%night+h", "--into", dst, "--at", "0,0") == 0
    assert pxart.parse(dst).get("body").grid == [".gk.", "..k.", "...."]


def test_paste_flip_leaves_source_alone(tmp_path):
    src, dst = paste_setup(tmp_path)
    assert run("paste", f"{src}:arm+hv", "--into", dst, "--at", "0,0") == 0
    assert src.read_text() == PASTE_SRC


def test_paste_b_suffix_is_bad_arg(tmp_path):
    src, dst = paste_setup(tmp_path)
    msg = run_err("paste", f"{src}:arm+hb", "--into", dst, "--at", "0,0")
    assert "E_BAD_ARG" in msg and "+b anchors a map legend entry" in msg and msg.startswith("paste: SRC (")
    assert dst.read_text() == PASTE_DST


def test_paste_png_source_is_bad_arg_not_a_crash(tmp_path):
    Image.new("RGBA", (1, 1), (0, 0, 0, 255)).save(tmp_path / "s.png")
    dst = write(tmp_path, "dst.px", PASTE_DST)
    msg = run_err("paste", tmp_path / "s.png", "--into", dst, "--at", "0,0")
    assert "E_BAD_ARG" in msg and "paste copies a .px frame" in msg


def test_paste_flip_into_selected_frames(tmp_path):
    src = write(tmp_path, "src.px", PASTE_SRC)
    dst = write(tmp_path, "dst.px", "k #000000\n@frame a/0\n...\n@frame a/1\n...\n")
    assert run("paste", f"{src}:arm+h", "--into", f"{dst}:a", "--at", "0,0") == 0
    assert [f.grid for f in pxart.parse(dst).frames] == [[".gk"], [".gk"]]


def test_paste_flip_on_a_file_with_one_frame(tmp_path):
    src = write(tmp_path, "src.px", "k #000000\nk.\n")
    dst = write(tmp_path, "dst.px", "k #000000\n..\n")
    assert run("paste", f"{src}+h", "--into", dst, "--at", "0,0") == 0
    assert dst.read_text() == "k #000000\n.k\n"


def test_help_documents_paste_flip():
    doc = pxart.__doc__
    assert "paste SRC[+h|+v|+hv] --into DST[:frame]" in doc
    assert "--region is then in the\n      mirrored frame's coordinates" in doc


# ---------------------------------------------------------------- loop J: errors name the command and the right axis

@pytest.mark.parametrize("shape, axis", [
    ("1,1.5,1,1", "cy=1.5 and ry=1"), ("1,1,1,1.5", "cy=1 and ry=1.5"), ("1.5,1,1,1", "cx=1.5 and rx=1"),
    ("1,1,1.5,1", "cx=1 and rx=1.5"), ("1.5,1.5,1,1", "cx=1.5 and rx=1"), ("2,2.5,1.5,1", "cx=2 and rx=1.5"),
])
def test_ellipse_half_pixel_error_names_the_axis(tmp_path, shape, axis):
    p = write(tmp_path, "e.px", "k #000000\n....\n....\n")
    msg = run_err("ellipse", p, "k", shape)
    assert msg.startswith(f"ellipse: E_BAD_ARG: {axis} put the shape's edge on half a pixel")
    assert p.read_text() == "k #000000\n....\n....\n"


@pytest.mark.parametrize("shape, names", [("1,1.5,1,1", ("cy", "ry")), ("1.5,1,1,1", ("cx", "rx"))])
def test_ellipse_half_pixel_error_suggests_that_axis(tmp_path, shape, names):
    p = write(tmp_path, "e.px", "k #000000\n....\n")
    msg = run_err("ellipse", p, "k", shape)
    assert f"give {names[0]} and {names[1]} both whole (7,7,3,3: 7 across)" in msg
    assert f"({names[0]}-{names[1]}..{names[0]}+{names[1]} must be whole pixels)" in msg


def test_ellipse_y_axis_error_never_mentions_cx(tmp_path):
    p = write(tmp_path, "e.px", "k #000000\n....\n")
    msg = run_err("ellipse", p, "k", "1,1.5,1,1")
    assert "cx" not in msg and "rx" not in msg


def test_ellipse_negative_radius_message(tmp_path):
    p = write(tmp_path, "e.px", "k #000000\n....\n")
    assert run_err("ellipse", p, "k", "1,1,1,-1") == "ellipse: E_BAD_ARG: radii must be >= 0, got rx=1, ry=-1"


@pytest.mark.parametrize("circle, axis", [("1,1.5,1", "cy=1.5 and r=1"), ("1.5,1,1", "cx=1.5 and r=1"),
                                          ("1,1,1.5", "cx=1 and r=1.5")])
def test_arc_half_pixel_error_names_the_axis(tmp_path, circle, axis):
    p = write(tmp_path, "e.px", "k #000000\n....\n")
    msg = run_err("arc", p, "k", circle, "0,90")
    assert msg.startswith(f"arc: E_BAD_ARG: {axis} put the shape's edge on half a pixel")
    assert "(7,7,3: 7 across)" in msg and "rx" not in msg


def test_arc_negative_radius_message(tmp_path):
    p = write(tmp_path, "e.px", "k #000000\n....\n")
    assert run_err("arc", p, "k", "1,1,-1", "0,90") == "arc: E_BAD_ARG: r must be >= 0, got r=-1"


def test_ellipse_box_directly():
    assert pxart.ellipse_box(3.5, 3.5, 3.5, 2.5, "ellipse") == (0, 1, 7, 6)
    with pytest.raises(pxart.PxError) as e:
        pxart.ellipse_box(3, 3.5, 3, 3, "ellipse")
    assert "cy=3.5 and ry=3" in str(e.value)


@pytest.mark.parametrize("argv, start", [
    (["ellipse", "{p}", "k", "1,1.5,1,1"], "ellipse: E_BAD_ARG: cy=1.5"),
    (["rect", "{p}", "k", "1,1"], "rect: E_BAD_ARG: rect wants x,y,w,h"),
    (["rect", "{p}", "k", "0,0,0,1"], "rect: E_BAD_ARG: w and h must be >= 1"),
    (["line", "{p}", "k", "0", "1,1"], "line: E_BAD_ARG: the start wants x,y"),
    (["line", "{p}", "k", "0,0", "1,1", "--width", "0"], "line: E_BAD_ARG: --width wants N >= 1"),
    (["arc", "{p}", "k", "1,1,1", "zz"], "arc: E_BAD_ARG: angles are a0,a1"),
    (["flood", "{p}", "k", "9,9"], "flood: E_BAD_ARG: 9,9 is outside"),
    (["set", "{p}", "k", "9"], "set: E_BAD_ARG: points are x,y"),
    (["set", "{p}", "k", "9,9"], "set: E_BAD_ARG: 9,9 is outside"),
    (["set", "{p}", "q", "0,0"], "set: E_SELECT: key 'q' not in palette"),
    (["fill", "{p}", "q"], "fill: E_SELECT: key 'q' not in palette"),
    (["fill", "{p}", "k", "--region", "1"], "fill: E_BAD_ARG: --region wants x,y,w,h"),
    (["shift", "{p}", "--region", "1"], "shift: E_BAD_ARG: --region wants x,y,w,h"),
    (["shift", "{p}", "--fill", "q"], "shift: E_SELECT: --fill key 'q' not in palette"),
    (["recolor", "{p}", "zz"], "recolor: E_BAD_ARG: 'zz' isn't a=b"),
    (["recolor", "{p}", "q=k"], "recolor: E_SELECT: key 'q' not in palette"),
    (["mask", "{p}"], "mask: E_BAD_ARG: mask needs a shape"),
    (["outline", "{p}", "--key", "q"], "outline: E_SELECT: key 'q' not in palette"),
    (["shade", "{p}", "--ramp", "q"], "shade: E_SELECT: key 'q' not in palette"),
    (["tint", "{t}/x.png", "zz"], "tint: E_BAD_COLOR: tint 'zz' isn't"),
    (["render", "{p}", "--bg", "zz", "-o", "{t}/r.png"], "render: E_BAD_COLOR: --bg 'zz' isn't"),
    (["new", "{t}/n.px", "--size", "0x1"], "new: E_BAD_ARG: --size wants WxH"),
    (["export", "{p}"], "export: E_BAD_ARG: give --frames DIR"),
    (["frames", "{p}", "--rm"], "frames: E_MIXED_FRAMES: this file has one unnamed grid"),
])
def test_every_error_line_starts_with_the_command(tmp_path, argv, start):
    p = write(tmp_path, "e.px", "k #000000\n....\n....\n")
    msg = run_err(*[a.format(p=p, t=tmp_path) for a in argv])
    assert msg.startswith(start), msg
    assert not any(l.startswith(":") for l in msg.splitlines())


def test_no_error_line_starts_with_a_bare_colon(tmp_path):
    p = write(tmp_path, "e.px", "k #000000\n....\n")
    for argv in (["ellipse", p, "k", "1,1.5,1,1"], ["set", p, "k", "9"], ["anim-set", p, "ms=3"],
                 ["render", p, "--variant", "zz", "-o", tmp_path / "r.png"]):
        msg = run_err(*argv)
        assert not msg.startswith(":") and msg.startswith(f"{argv[0]}: "), msg


def test_error_with_a_path_and_no_input_label_gets_the_command(tmp_path):
    p = write(tmp_path, "e.px", "k #000000\n....\n")
    assert run_err("anim-set", p, "ms=3").startswith(f"anim-set: {p}: E_SELECT: ")


def test_error_with_an_input_label_unchanged(tmp_path):
    msg = run_err("compose", "-o", tmp_path / "o.px", "bad")
    assert msg == "compose: layer 1 (bad): E_BAD_ARG: expected FILE[:frame][%variant]@x,y, got 'bad'"


def test_issue_str_without_a_path_has_no_leading_colon():
    assert str(pxart.Issue("E_BAD_ARG", "nope")) == "E_BAD_ARG: nope"
    i = pxart.Issue("E_BAD_ARG", "nope")
    i.ctx = "layer 1 (x)"
    assert str(i) == "layer 1 (x): E_BAD_ARG: nope"


def test_said_drops_a_repeated_command_name():
    assert pxart.said("line", pxart.Issue("E_BAD_ARG", "line: the start wants x,y")) == \
        "line: E_BAD_ARG: the start wants x,y"
    assert pxart.said("rect", pxart.Issue("E_BAD_ARG", "rect wants x,y,w,h")) == "rect: E_BAD_ARG: rect wants x,y,w,h"


def test_help_documents_error_prefix():
    doc = " ".join(pxart.__doc__.split())
    assert "Every error line starts with the command ('ellipse: E_BAD_ARG: cy=1.5 and ry=1 ...')" in doc


# ---------------------------------------------------------------- loop J: crop doesn't note the pixels it cuts away

@pytest.mark.parametrize("rect", ["0,0,1,1", "1,1,2,2", "2,2,1,1", "0,0,3,1", "2,2,3,3", "0,0,3,3"])
def test_crop_never_prints_the_cropped_note(tmp_path, capsys, rect):
    p = write(tmp_path, "a.px", "k #000000\n@frame f\nkkk\nkkk\nkkk\n")
    assert run("crop", f"{p}:f", rect, "-o", tmp_path / "o.px") == 0
    assert "fall outside" not in capsys.readouterr().out


def test_crop_output_line_is_all_it_prints(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\n@frame f\nkkk\nkkk\n")
    assert run("crop", f"{p}:f", "0,0,1,1", "-o", f"{p}:g") == 0
    assert capsys.readouterr().out == f"wrote {p} frame g\n"


def test_crop_result_unchanged_by_the_quiet(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\ng #00ff00\n@frame f\nkgk\ngkg\nkgk\n")
    assert run("crop", f"{p}:f", "1,0,2,2", "-o", f"{p}:c") == 0
    assert pxart.parse(p).get("c").grid == ["gk", "kg"]


def test_compose_still_notes_cropped_layers(tmp_path, capsys):
    layer = write(tmp_path, "l.px", "k #000000\nkkk\n")
    assert run("compose", "-o", tmp_path / "o.px", "--size", "2x1", f"{layer}@0,0") == 0
    assert "note: 1 px of l fall outside the 2x1 canvas (size from --size) and were cropped" in capsys.readouterr().out


def test_compose_after_crop_in_same_process_still_notes(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\n@frame f\nkkk\n")
    assert run("crop", f"{p}:f", "0,0,1,1", "-o", tmp_path / "c.px") == 0
    assert run("compose", "-o", tmp_path / "o.px", "--size", "1x1", f"{p}:f@0,0") == 0
    assert "fall outside" in capsys.readouterr().out


def test_help_documents_quiet_crop():
    doc = " ".join(pxart.__doc__.split())
    assert "Quietly: the pixels outside the rectangle are what crop is for, so there's no note about them" in doc


# ---------------------------------------------------------------- loop J: sheet tells same-id frames of several files apart

SAME_IDS = "k #000000\n@frame idle/0\nk\n@frame idle/1\nkk\n"


def labels_of(*args):
    return [it.label for it in pxart.all_items([str(a) for a in args])]


def test_sheet_labels_colliding_ids_with_stems(tmp_path):
    a, b = write(tmp_path, "hero.px", SAME_IDS), write(tmp_path, "beast.px", SAME_IDS)
    assert labels_of(a, b) == ["hero:idle/0", "hero:idle/1", "beast:idle/0", "beast:idle/1"]


def test_sheet_only_colliding_labels_get_a_stem(tmp_path):
    a = write(tmp_path, "hero.px", SAME_IDS)
    b = write(tmp_path, "beast.px", "k #000000\n@frame idle/0\nk\n@frame roar\nk\n")
    assert labels_of(a, b) == ["hero:idle/0", "idle/1", "beast:idle/0", "roar"]


def test_sheet_no_collision_no_prefix(tmp_path):
    a = write(tmp_path, "hero.px", SAME_IDS)
    b = write(tmp_path, "beast.px", "k #000000\n@frame roar/0\nk\n")
    assert labels_of(a, b) == ["idle/0", "idle/1", "roar/0"]


def test_sheet_single_file_never_prefixed(tmp_path):
    a = write(tmp_path, "hero.px", SAME_IDS)
    assert labels_of(a) == ["idle/0", "idle/1"]


def test_sheet_same_file_twice_not_prefixed(tmp_path):
    a = write(tmp_path, "hero.px", SAME_IDS)
    assert labels_of(f"{a}:idle/0", f"{a}:idle") == ["idle/0", "idle/0", "idle/1"]


def test_sheet_same_stem_different_dirs_uses_paths(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a, b = write(tmp_path / "a", "hero.px", SAME_IDS), write(tmp_path / "b", "hero.px", SAME_IDS)
    assert labels_of(a, b) == [f"{a}:idle/0", f"{a}:idle/1", f"{b}:idle/0", f"{b}:idle/1"]


def test_sheet_selectors_of_different_files(tmp_path):
    a, b = write(tmp_path, "hero.px", SAME_IDS), write(tmp_path, "beast.px", SAME_IDS)
    assert labels_of(f"{a}:idle/1", f"{b}:idle/1") == ["hero:idle/1", "beast:idle/1"]


def test_sheet_variant_suffix_uses_the_file_stem(tmp_path):
    t = "k #000000\n\n@variant night\nk #000011\n@frame idle/0\nk\n"
    a, b = write(tmp_path, "hero.px", t), write(tmp_path, "beast.px", t)
    assert labels_of(f"{a}:idle/0%night", f"{b}:idle/0") == ["hero:idle/0", "beast:idle/0"]


def test_sheet_unnamed_grids_with_the_same_stem(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a, b = write(tmp_path / "a", "ant.px", "k #000000\nk\n"), write(tmp_path / "b", "ant.px", "k #000000\nk\n")
    assert labels_of(a, b) == [f"{a}:ant", f"{b}:ant"]


def test_sheet_png_and_px_with_one_name(tmp_path):
    a = write(tmp_path, "ant.px", "k #000000\nk\n")
    Image.new("RGBA", (1, 1), (0, 0, 0, 255)).save(tmp_path / "ant.png")
    assert labels_of(a, tmp_path / "ant.png") == [f"{a}:ant", f"{tmp_path / 'ant.png'}:ant"]


def test_sheet_three_files_two_collide(tmp_path):
    a, b = write(tmp_path, "hero.px", SAME_IDS), write(tmp_path, "beast.px", SAME_IDS)
    c = write(tmp_path, "cat.px", "k #000000\n@frame sit\nk\n")
    assert labels_of(a, b, c) == ["hero:idle/0", "hero:idle/1", "beast:idle/0", "beast:idle/1", "sit"]


def test_sheet_command_writes_with_prefixed_labels(tmp_path):
    a, b = write(tmp_path, "hero.px", SAME_IDS), write(tmp_path, "beast.px", SAME_IDS)
    assert run("sheet", a, b, "-o", tmp_path / "s.png") == 0
    assert (tmp_path / "s.png").exists()


def test_sheet_label_widens_the_cell(tmp_path):
    a, b = write(tmp_path, "hero.px", SAME_IDS), write(tmp_path, "beastlyname.px", SAME_IDS)
    assert run("sheet", a, "-o", tmp_path / "one.png", "--cols", "1") == 0
    assert run("sheet", a, b, "-o", tmp_path / "two.png", "--cols", "1") == 0
    assert Image.open(tmp_path / "two.png").width > Image.open(tmp_path / "one.png").width


def test_anim_lines_use_prefixed_labels(tmp_path, capsys):
    a, b = write(tmp_path, "hero.px", SAME_IDS), write(tmp_path, "beast.px", SAME_IDS)
    assert run("anim", f"{a}:idle/0", f"{b}:idle/0") == 0
    out = capsys.readouterr().out
    assert "hero:idle/0" in out and "vs beast:idle/0" in out


def test_render_uses_prefixed_labels(tmp_path):
    a, b = write(tmp_path, "hero.px", SAME_IDS), write(tmp_path, "beast.px", SAME_IDS)
    assert run("render", a, b, "-o", tmp_path / "r.png") == 0


def test_tell_apart_directly():
    its = [pxart.Item("x", None, 1), pxart.Item("x", None, 1), pxart.Item("y", None, 1)]
    pxart.tell_apart(its, ["p/one.px", "q/two.px", "q/two.px"])
    assert [it.label for it in its] == ["one:x", "two:x", "y"]


def test_help_documents_sheet_prefix():
    doc = " ".join(pxart.__doc__.split())
    assert "Frames with the same id from different files are labeled with their file's stem in front" in doc


# ---------------------------------------------------------------- loop J: shade --region's border is not an edge

@pytest.mark.parametrize("region", ["0,0,5,10", "5,0,5,10", "0,0,10,5", "0,5,10,5", "2,2,6,6", "3,0,1,10", "0,0,1,1",
                                    "9,9,1,1", "4,4,2,2", "0,0,10,10", "-3,-3,8,8", "7,7,20,20"])
@pytest.mark.parametrize("light", ["nw", "se", "n", "e"])
def test_shade_region_matches_that_part_of_the_whole(tmp_path, region, light):
    rows = square_rows(10, pad=0)
    whole, part = material_file(tmp_path, rows, "w.px"), material_file(tmp_path, rows, "p.px")
    assert run("shade", f"{whole}:a", "--ramp", RAMP, "--light", light) == 0
    assert run("shade", f"{part}:a", "--ramp", RAMP, "--light", light, f"--region={region}") == 0
    x0, y0, w, h = map(int, region.split(","))
    W, P = grid_of(whole), grid_of(part)
    for y in range(10):
        for x in range(10):
            want = W[y][x] if x0 <= x < x0 + w and y0 <= y < y0 + h else "C"
            assert P[y][x] == want, (x, y)


@pytest.mark.parametrize("region", ["0,0,6,12", "6,0,6,12", "3,3,6,6"])
def test_shade_region_matches_the_whole_on_a_circle(tmp_path, region):
    rows = circle_rows(10)
    whole, part = material_file(tmp_path, rows, "w.px"), material_file(tmp_path, rows, "p.px")
    assert run("shade", f"{whole}:a", "--ramp", RAMP, "--strength", "5") == 0
    assert run("shade", f"{part}:a", "--ramp", RAMP, "--strength", "5", "--region", region) == 0
    x0, y0, w, h = map(int, region.split(","))
    W, P = grid_of(whole), grid_of(part)
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            assert P[y][x] == (W[y][x] if x0 <= x < x0 + w and y0 <= y < y0 + h else c), (x, y)


def test_shade_region_interior_cut_is_base_tone(tmp_path):
    p = material_file(tmp_path, square_rows(12, pad=0))
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--region", "4,4,4,4") == 0
    g = grid_of(p)
    assert all(g[y][x] == "C" for y in range(4, 8) for x in range(4, 8))  # deep inside: nothing to shade
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--region", "4,4,4,4", "--dither") == 0
    assert all(grid_of(p)[y][x] == "C" for y in range(4, 8) for x in range(4, 8))


def test_shade_region_real_transparent_edge_still_shades(tmp_path):
    p = material_file(tmp_path, square_rows(10))  # 1px of '.' around the square
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--region", "0,0,6,12") == 0
    g = grid_of(p)
    assert g[5][1] in "DE" and g[1][5] in "DE"   # the lit left and top edges: real edges
    assert g[5][5] == "C"                         # at the region's right cut: no edge there


def test_shade_region_other_material_is_an_edge(tmp_path):
    rows = ["CCCCCXCCCC"] * 6
    p = write(tmp_path, "m.px", SHADE_PAL + "X #ff00ff\n@frame a\n" + "\n".join(rows) + "\n")
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--keys", "C", "--region", "0,0,5,6", "--light", "e") == 0
    g = grid_of(p)
    assert g[3][4] in "DE"                        # faces the other material to the east: a real edge, lit
    assert g[3][0] in "AB"                        # the frame side to the west: an edge, dark


def test_shade_region_counts_only_region_pixels(tmp_path, capsys):
    p = material_file(tmp_path, square_rows(10, pad=0))
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--region", "0,0,2,2") == 0
    out = capsys.readouterr().out
    changed = sum(c != "C" for row in grid_of(p) for c in row)
    assert 0 < changed <= 4 and out.startswith(f"changed {changed} px: ")
    assert sum(int(x.split("->")[0]) for x in out.split(": ", 1)[1].split(";")[0].split(", ")) == changed


def test_shade_region_preview_matches_region_write(tmp_path):
    p = material_file(tmp_path, square_rows(10, pad=0))
    before = p.read_text()
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--region", "0,0,5,10", "--preview", tmp_path / "v.png") == 0
    assert p.read_text() == before


def test_shade_region_outside_the_material_changes_nothing(tmp_path, capsys):
    p = material_file(tmp_path, square_rows(4))
    before = p.read_text()
    assert run("shade", f"{p}:a", "--ramp", RAMP, "--region", "0,0,1,1") == 0
    assert p.read_text() == before and "no change" in capsys.readouterr().out


def test_help_documents_shade_region_border():
    doc = " ".join(pxart.__doc__.split())
    assert "the region's border is not an edge, only a real one is" in doc


# ---------------------------------------------------------------- loop J: poly (filled or outlined polygons)

def pix(grid):
    return {(x, y) for y, r in enumerate(grid) for x, c in enumerate(r) if c != "."}


def poly_grid(tmp_path, w, h, *args):
    p = canvas(tmp_path, w, h)
    assert run("poly", f"{p}:a", "k", *args) == 0
    return grid_of(p)


def test_poly_square_outline_is_rect_border(tmp_path):
    g = poly_grid(tmp_path, 6, 6, "0,0", "4,0", "4,4", "0,4")
    assert g == ["kkkkk.", "k...k.", "k...k.", "k...k.", "kkkkk.", "......"]


def test_poly_square_fill_is_rect_fill(tmp_path):
    g = poly_grid(tmp_path, 6, 6, "0,0", "4,0", "4,4", "0,4", "--fill")
    assert g == ["kkkkk.", "kkkkk.", "kkkkk.", "kkkkk.", "kkkkk.", "......"]


def test_poly_matches_rect_command(tmp_path):
    a, b = canvas(tmp_path, 9, 9, "a.px"), canvas(tmp_path, 9, 9, "b.px")
    assert run("poly", f"{a}:a", "k", "1,2", "7,2", "7,6", "1,6", "--fill") == 0
    assert run("rect", f"{b}:a", "k", "1,2,7,5", "--fill") == 0
    assert grid_of(a) == grid_of(b)


def test_poly_triangle_golden(tmp_path):
    g = poly_grid(tmp_path, 7, 5, "3,0", "6,4", "0,4", "--fill")
    # line's pixels: a tie at an edge's midpoint rounds toward its first end in (x, y) order, so the two slopes
    # aren't mirror images on row 2 (as 'line' draws them).
    assert g == ["...k...", "..kkk..", ".kkkk..", ".kkkkk.", "kkkkkkk"]


def test_poly_triangle_outline_golden(tmp_path):
    g = poly_grid(tmp_path, 7, 5, "3,0", "6,4", "0,4")
    assert g == ["...k...", "..k.k..", ".k..k..", ".k...k.", "kkkkkkk"]


def test_poly_outline_is_the_lines(tmp_path):
    pts = [(1, 1), (10, 3), (7, 9), (2, 7)]
    want = set()
    for a, b in zip(pts, pts[1:] + pts[:1]):
        want |= set(pxart.line_points(*a, *b))
    g = poly_grid(tmp_path, 12, 12, *[f"{x},{y}" for x, y in pts])
    assert pix(g) == want


@pytest.mark.parametrize("pts", [
    [(1, 1), (10, 3), (7, 9), (2, 7)], [(0, 0), (11, 0), (6, 11)], [(3, 0), (11, 5), (8, 11), (0, 9), (1, 3)],
    [(5, 0), (7, 4), (11, 5), (8, 8), (9, 11), (5, 9), (1, 11), (2, 8), (0, 5), (4, 4)],
])
@pytest.mark.parametrize("fill", [False, True])
def test_poly_same_pixels_reversed_or_rotated(pts, fill):
    got = pxart.poly_points(pts, fill)
    assert pxart.poly_points(pts[::-1], fill) == got
    for k in range(1, len(pts)):
        assert pxart.poly_points(pts[k:] + pts[:k], fill) == got


@pytest.mark.parametrize("pts", [
    [(1, 1), (10, 3), (7, 9), (2, 7)], [(0, 0), (11, 0), (6, 11)], [(3, 0), (11, 5), (8, 11), (0, 9), (1, 3)],
])
def test_poly_fill_contains_outline_and_stays_in_bbox(pts):
    out, fill = pxart.poly_points(pts), pxart.poly_points(pts, True)
    assert out <= fill
    xs, ys = [x for x, _ in pts], [y for _, y in pts]
    assert all(min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys) for x, y in fill)


@pytest.mark.parametrize("pts", [
    [(1, 1), (10, 3), (7, 9), (2, 7)], [(0, 0), (11, 0), (6, 11)], [(3, 0), (11, 5), (8, 11), (0, 9), (1, 3)],
    [(0, 5), (5, 0), (10, 5), (5, 10)],
])
def test_poly_convex_fill_rows_are_contiguous(pts):
    fill = pxart.poly_points(pts, True)
    for y in {y for _, y in fill}:
        xs = sorted(x for x, yy in fill if yy == y)
        assert xs == list(range(xs[0], xs[-1] + 1)), y


def test_poly_convex_fill_has_no_hole(tmp_path):
    fill = pxart.poly_points([(0, 5), (5, 0), (10, 5), (5, 10)], True)
    assert fill == {(x, y) for y in range(11) for x in range(11) if abs(x - 5) + abs(y - 5) <= 5}


def test_poly_star_is_solid(tmp_path):
    star = [(7, 0), (9, 6), (15, 6), (10, 10), (12, 15), (7, 12), (2, 15), (4, 10), (0, 6), (5, 6)]
    fill = pxart.poly_points(star, True)
    assert {(7, 7), (7, 9), (7, 3), (3, 7), (11, 7)} <= fill


def test_poly_self_crossing_pentagram_center_filled():
    # A pentagram drawn as one self-crossing line: nonzero winding fills its center too.
    pent = [(8, 0), (13, 15), (0, 5), (16, 5), (3, 15)]
    assert (8, 8) in pxart.poly_points(pent, True)
    assert (8, 8) not in pxart.poly_points(pent)


def test_poly_bowtie_both_halves(tmp_path):
    g = poly_grid(tmp_path, 7, 7, "0,0", "6,6", "6,0", "0,6", "--fill")
    assert g[3] == "kkkkkkk" and g[1][0] == "k" and g[1][6] == "k" and g[0][3] == "."


def test_poly_symmetric_shape_is_mirror_symmetric():
    pts = [(5, 0), (10, 4), (8, 10), (2, 10), (0, 4)]
    for fill in (False, True):
        got = pxart.poly_points(pts, fill)
        assert got == {(10 - x, y) for x, y in got}


def test_poly_two_points_is_a_line(tmp_path):
    g = poly_grid(tmp_path, 9, 3, "0,0", "8,2")
    assert pix(g) == set(pxart.line_points(0, 0, 8, 2))


def test_poly_two_points_fill_is_still_a_line():
    assert pxart.poly_points([(0, 0), (8, 2)], True) == set(pxart.line_points(0, 0, 8, 2))


def test_poly_collinear_points_fill_is_the_line():
    assert pxart.poly_points([(0, 0), (4, 0), (8, 0)], True) == {(x, 0) for x in range(9)}


def test_poly_repeated_points(tmp_path):
    a = pxart.poly_points([(0, 0), (4, 0), (4, 0), (4, 4), (0, 4), (0, 0)], True)
    assert a == pxart.poly_points([(0, 0), (4, 0), (4, 4), (0, 4)], True)


def test_poly_one_point_is_bad_arg(tmp_path):
    p = canvas(tmp_path, 3, 3)
    assert run_err("poly", f"{p}:a", "k", "1,1") == \
        "poly: E_BAD_ARG: poly wants at least 2 points x,y x,y ... (3 or more for a shape)"


def test_poly_bad_point_names_which(tmp_path):
    p = canvas(tmp_path, 3, 3)
    msg = run_err("poly", f"{p}:a", "k", "0,0", "1,1", "2")
    assert msg == "poly: E_BAD_ARG: point 3 wants x,y (integers), got '2'"


def test_poly_half_coordinates_rejected(tmp_path):
    p = canvas(tmp_path, 3, 3)
    assert "E_BAD_ARG" in run_err("poly", f"{p}:a", "k", "0,0", "1.5,1", "2,2")


def test_poly_unknown_key(tmp_path):
    p = canvas(tmp_path, 3, 3)
    assert run_err("poly", f"{p}:a", "q", "0,0", "2,2").startswith("poly: E_SELECT: key 'q' not in palette")


def test_poly_negative_points_clip_with_note(tmp_path, capsys):
    p = canvas(tmp_path, 4, 4)
    assert run("poly", f"{p}:a", "k", "-2,-2", "3,-2", "3,3", "-2,3", "--fill") == 0
    out = capsys.readouterr().out
    assert grid_of(p) == ["kkkk"] * 4
    assert "note: 20 px of the poly fall outside a (4x4) and were clipped" in out and "painted 16 px" in out


def test_poly_erases_with_dot(tmp_path):
    p = write(tmp_path, "d.px", "k #000000\n@frame a\nkkk\nkkk\nkkk\n")
    assert run("poly", f"{p}:a", ".", "0,0", "2,0", "2,2", "0,2") == 0
    assert grid_of(p) == ["...", ".k.", "..."]


def test_poly_every_selected_frame(tmp_path):
    p = write(tmp_path, "d.px", "k #000000\n@frame a/0\n...\n...\n@frame a/1\n...\n...\n")
    assert run("poly", f"{p}:a", "k", "0,0", "2,1", "0,1", "--fill") == 0
    doc = pxart.parse(p)
    assert doc.get("a/0").grid == doc.get("a/1").grid == ["kk.", "kkk"]


def test_poly_no_change(tmp_path, capsys):
    p = write(tmp_path, "d.px", "k #000000\n@frame a\nkkk\nkkk\n")
    assert run("poly", f"{p}:a", "k", "0,0", "2,0", "2,1", "--fill") == 0
    assert "painted 0 px; no change" in capsys.readouterr().out


def test_poly_output_file(tmp_path):
    p = canvas(tmp_path, 3, 3)
    before = p.read_text()
    assert run("poly", f"{p}:a", "k", "0,0", "2,2", "-o", tmp_path / "o.px") == 0
    assert p.read_text() == before and grid_of(tmp_path / "o.px") == ["k..", ".k.", "..k"]


def test_poly_rewrites_only_changed_rows(tmp_path):
    p = write(tmp_path, "d.px", "k #000000\n@frame a\n...\n# keep me\n...\n...\n")
    assert run("poly", f"{p}:a", "k", "0,2", "2,2") == 0
    assert p.read_text() == "k #000000\n@frame a\n...\n# keep me\n...\nkkk\n"


def test_poly_in_usage():
    with pytest.raises(SystemExit):
        pxart.main(["poly", "-h"])


def test_help_documents_poly():
    doc = pxart.__doc__
    drawing = doc[doc.index("\nDRAWING"):doc.index("\nCONVERTING")]
    assert "\n  poly FILE[:frame] KEY x,y x,y x,y ... [--fill]" in drawing
    assert "nonzero winding: a self-crossing star" in " ".join(drawing.split())


# ---------------------------------------------------------------- loop J: compose --under / paste --under

UNDER = "k #000000\ng #00ff00\nf #806040\nt transparent\n@frame hero\n.kk.\nk..k\n.kk.\n@frame floor\nffff\nffff\nffff\n"


def test_compose_under_fills_only_empty_pixels(tmp_path):
    p = write(tmp_path, "u.px", UNDER)
    assert run("compose", "-o", f"{p}:hero", "--under", f"{p}:floor@0,0") == 0
    assert pxart.parse(p).get("hero").grid == ["fkkf", "kffk", "fkkf"]


def test_compose_without_under_replaces_the_frame(tmp_path):
    p = write(tmp_path, "u.px", UNDER)
    assert run("compose", "-o", f"{p}:hero", f"{p}:floor@0,0") == 0
    assert pxart.parse(p).get("hero").grid == ["ffff"] * 3


def test_compose_under_layers_stack_among_themselves(tmp_path):
    p = write(tmp_path, "u.px", UNDER + "@frame dot\ng.\n")
    assert run("compose", "-o", f"{p}:hero", "--under", f"{p}:floor@0,0", f"{p}:dot@0,0") == 0
    assert pxart.parse(p).get("hero").grid == ["gkkf", "kffk", "fkkf"]  # dot over floor, both behind the hero


def test_compose_under_offset_and_partial_cover(tmp_path):
    p = write(tmp_path, "u.px", UNDER + "@frame dot\ngg\n")
    assert run("compose", "-o", f"{p}:hero", "--under", f"{p}:dot@2,1") == 0
    assert pxart.parse(p).get("hero").grid == [".kk.", "k.gk", ".kk."]


def test_compose_under_transparent_key_counts_as_empty(tmp_path):
    p = write(tmp_path, "u.px", UNDER.replace("@frame hero\n.kk.", "@frame hero\ntkk."))
    assert run("compose", "-o", f"{p}:hero", "--under", f"{p}:floor@0,0") == 0
    assert pxart.parse(p).get("hero").grid[0] == "fkkf"


def test_compose_under_layer_transparent_pixels_leave_holes_empty(tmp_path):
    p = write(tmp_path, "u.px", UNDER + "@frame ring\nf..f\n")
    assert run("compose", "-o", f"{p}:hero", "--under", f"{p}:ring@0,1") == 0
    assert pxart.parse(p).get("hero").grid == [".kk.", "k..k", ".kk."]  # the ring's pixels land on the hero's k


def test_compose_under_new_frame_is_bad_arg(tmp_path):
    p = write(tmp_path, "u.px", UNDER)
    before = p.read_text()
    msg = run_err("compose", "-o", f"{p}:nope", "--under", f"{p}:floor@0,0")
    assert msg.startswith("compose: E_BAD_ARG: --under draws the layers behind OUT's frame") and p.read_text() == before


def test_compose_under_new_file_is_bad_arg(tmp_path):
    p = write(tmp_path, "u.px", UNDER)
    assert "E_BAD_ARG" in run_err("compose", "-o", tmp_path / "new.px", "--under", f"{p}:floor@0,0")
    assert not (tmp_path / "new.px").exists()


def test_compose_under_other_size_is_bad_arg(tmp_path):
    p = write(tmp_path, "u.px", UNDER)
    msg = run_err("compose", "-o", f"{p}:hero", "--under", "--size", "8x8", f"{p}:floor@0,0")
    assert "--under keeps the frame being replaced, 4x3; drop --size 8x8" in msg


def test_compose_under_same_size_is_fine(tmp_path):
    p = write(tmp_path, "u.px", UNDER)
    assert run("compose", "-o", f"{p}:hero", "--under", "--size", "4x3", f"{p}:floor@0,0") == 0


def test_compose_under_new_key_joins_palette(tmp_path):
    p = write(tmp_path, "u.px", UNDER)
    q = write(tmp_path, "q.px", "z #123456\nzzzz\nzzzz\nzzzz\n")
    assert run("compose", "-o", f"{p}:hero", "--under", f"{q}@0,0") == 0
    doc = pxart.parse(p)
    assert doc.get("hero").grid == ["zkkz", "kzzk", "zkkz"] and doc.palette["z"] == (0x12, 0x34, 0x56, 255)


def test_compose_under_on_single_grid_file(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\nf #806040\n.k\nk.\n")
    q = write(tmp_path, "q.px", "f #806040\nff\nff\n")
    assert run("compose", "-o", p, "--under", f"{q}@0,0") == 0
    assert p.read_text() == "k #000000\nf #806040\nfk\nkf\n"


def test_compose_under_nothing_empty_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "u.px", UNDER)
    assert run("compose", "-o", f"{p}:floor", "--under", f"{p}:hero@0,0") == 0
    assert "no change" in capsys.readouterr().out


def test_compose_under_flipped_layer(tmp_path):
    p = write(tmp_path, "u.px", UNDER + "@frame dot\ng.\n")
    assert run("compose", "-o", f"{p}:hero", "--under", f"{p}:dot+h@2,0") == 0
    assert pxart.parse(p).get("hero").grid == [".kkg", "k..k", ".kk."]


def test_crop_has_no_under_and_still_works(tmp_path):
    p = write(tmp_path, "u.px", UNDER)
    assert run("crop", f"{p}:hero", "0,0,2,2", "-o", f"{p}:c") == 0
    assert pxart.parse(p).get("c").grid == [".k", "k."]


def test_paste_under_fills_only_empty_pixels(tmp_path):
    p = write(tmp_path, "u.px", UNDER)
    assert run("paste", f"{p}:floor", "--into", f"{p}:hero", "--at", "0,0", "--under") == 0
    assert pxart.parse(p).get("hero").grid == ["fkkf", "kffk", "fkkf"]


def test_paste_without_under_covers(tmp_path):
    p = write(tmp_path, "u.px", UNDER)
    assert run("paste", f"{p}:floor", "--into", f"{p}:hero", "--at", "0,0") == 0
    assert pxart.parse(p).get("hero").grid == ["ffff"] * 3


def test_paste_under_with_region_and_flip(tmp_path):
    p = write(tmp_path, "u.px", UNDER + "@frame dot\ngf\n")
    assert run("paste", f"{p}:dot+h", "--into", f"{p}:hero", "--at", "0,0", "--under", "--region", "0,0,1,1") == 0
    assert pxart.parse(p).get("hero").grid == ["fkk.", "k..k", ".kk."]


def test_paste_under_every_selected_frame(tmp_path):
    p = write(tmp_path, "u.px", "k #000000\nf #806040\n@frame a/0\nk.\n@frame a/1\n.k\n@frame fl\nff\n")
    assert run("paste", f"{p}:fl", "--into", f"{p}:a", "--at", "0,0", "--under") == 0
    doc = pxart.parse(p)
    assert doc.get("a/0").grid == ["kf"] and doc.get("a/1").grid == ["fk"]


def test_stamp_under_directly(tmp_path):
    doc = pxart.parse(write(tmp_path, "u.px", UNDER))
    hero, floor = doc.get("hero"), doc.get("floor")
    pxart.stamp(doc, hero, doc, floor, (1, 0), under=True)
    assert hero.grid == [".kkf", "kffk", ".kkf"]


def test_help_documents_under():
    doc = " ".join(pxart.__doc__.split())
    assert "--under keeps OUT's frame and draws the layers behind it" in doc
    assert "--under fills only DST's empty pixels: SRC goes behind" in doc


# ---------------------------------------------------------------- key conflicts: one recolor per source file

FIELD = ("s #00ff00\nt #008800\nu #88ff88\nv #ff00ff\n"
         "@frame grass_a\nst\nts\n@frame grass_c\nsu\nus\n@frame flowers\nvs\nsv\n")
SCENE = "s #111111\nt #222222\nu #333333\nv #444444\n@frame x\nstuv\n"


def field_scene(tmp_path):
    return write(tmp_path, "field.px", FIELD), write(tmp_path, "scene.px", SCENE)


def floor_argv(f, out, n=4):
    frames = ["grass_a", "grass_c", "flowers", "grass_a", "grass_c", "flowers", "grass_a"][:n]
    return ["compose", "-o", f"{out}:floor", "--size", f"{2 * n}x2"] + [f"{f}:{fr}@{2 * i},0" for i, fr in
                                                                         enumerate(frames)]


def test_conflict_one_line_for_a_file_used_as_many_layers(tmp_path):
    f, out = field_scene(tmp_path)
    lines = run_err(*floor_argv(f, out)).splitlines()
    assert lines == [f"compose: layers 1-4 ({f}): E_KEY_CONFLICT: 4 keys of these layers are other colors in {out}: "
                     "'s' #00ff00 (#111111 there), 't' #008800 (#222222 there), 'u' #88ff88 (#333333 there), "
                     "'v' #ff00ff (#444444 there); to keep both colors (no pixel changes color), add --rekey: compose "
                     f"then gives these layers' keys free ones in {out} ('s>a' 't>b' 'u>c' 'v>d') and leaves {f} as it "
                     "is. Or give them those keys in a copy and compose from that: pxart recolor "
                     f"{f} 's>a' 't>b' 'u>c' 'v>d' -o {tmp_path / 'rekeyed' / 'field.px'}"]


def test_conflict_covers_every_frame_the_compose_uses_from_the_file(tmp_path):
    # grass_a has s t, grass_c s u, flowers s v: the one recolor covers all four, not only the first layer's.
    f, out = field_scene(tmp_path)
    msg = run_err(*floor_argv(f, out, 3))
    for k in "stuv":
        assert f"'{k}>" in msg
    assert msg.count("E_KEY_CONFLICT") == 1


def test_conflict_only_the_used_frames_keys(tmp_path):
    f, out = field_scene(tmp_path)
    msg = run_err("compose", "-o", f"{out}:floor", "--size", "4x2", f"{f}:grass_a@0,0", f"{f}:grass_a@2,0")
    assert f"layers 1-2 ({f})" in msg and "'s>a' 't>b'" in msg and "'u>" not in msg and "'v>" not in msg


def test_conflict_same_key_twice_in_a_file_is_named_once(tmp_path):
    f, out = field_scene(tmp_path)
    msg = run_err(*floor_argv(f, out, 7))
    assert msg.count("'s' #00ff00") == 1 and msg.count("'s>") == 2 and "layers 1-7" in msg  # --rekey's and the copy's


def test_conflict_recipe_runs_once_and_the_compose_goes_through(tmp_path):
    import shlex
    f, out = field_scene(tmp_path)
    argv = floor_argv(f, out, 7)
    fix = fix_of(run_err(*argv))
    before = f.read_text()
    assert run(*fix) == 0 and f.read_text() == before
    assert run(*from_copies(argv, [fix])) == 0
    doc = pxart.parse(out)
    img = doc.image(doc.get("floor"))
    assert img.getpixel((0, 0)) == pxart.hex2rgba("#00ff00") and img.getpixel((1, 0)) == pxart.hex2rgba("#008800")
    assert img.getpixel((3, 0)) == pxart.hex2rgba("#88ff88") and img.getpixel((4, 0)) == pxart.hex2rgba("#ff00ff")
    assert doc.image(doc.get("x")).getpixel((0, 0)) == pxart.hex2rgba("#111111")


def test_conflict_layers_of_one_file_split_by_another(tmp_path):
    f, out = field_scene(tmp_path)
    g = write(tmp_path, "g.px", "t #abcdef\n\nt\n")
    msg = run_err("compose", "-o", f"{out}:floor", "--size", "6x2", f"{f}:grass_a@0,0", f"{g}@2,0",
                  f"{f}:flowers@4,0")
    lines = msg.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith(f"compose: layers 1, 3 ({f}): E_KEY_CONFLICT: 3 keys of these layers")
    assert lines[1].startswith(f"compose: layer 2 ({g}): E_KEY_CONFLICT: 1 key of this layer is another color")


def test_conflict_single_layer_keeps_its_label(tmp_path):
    f, out = field_scene(tmp_path)
    msg = run_err("compose", "-o", f"{out}:floor", f"{f}:grass_a@0,0")
    assert msg.startswith(f"compose: layer 1 ({f}:grass_a): E_KEY_CONFLICT: 2 keys of this layer are other colors")
    assert "gives this layer's keys free ones" in msg


def test_conflict_suggestions_of_several_files_never_collide(tmp_path):
    import shlex
    f, out = field_scene(tmp_path)
    g = write(tmp_path, "g.px", "s #0000aa\nt #0000bb\n\nst\n")
    h = write(tmp_path, "h.px", "u #0000cc\n\nu\n")
    argv = ["compose", "-o", f"{out}:floor", "--size", "6x2", f"{f}:grass_a@0,0", f"{g}@2,0", f"{h}@4,0",
            f"{f}:grass_c@4,1"]
    lines = run_err(*argv).splitlines()
    assert len(lines) == 3
    fixes = [fix_of(l) for l in lines]
    new = [m.split(">")[1] for fix in fixes for m in fix[2:-2]]
    assert len(new) == len(set(new)), new
    for fix in reversed(fixes):  # any order works
        assert run(*fix) == 0
    assert run(*from_copies(argv, fixes)) == 0


def test_conflict_fixes_run_in_order_too(tmp_path):
    import shlex
    f, out = field_scene(tmp_path)
    g = write(tmp_path, "g.px", "s #0000aa\n\ns\n")
    argv = ["compose", "-o", f"{out}:floor", "--size", "4x2", f"{f}:grass_a@0,0", f"{g}@2,0", f"{f}:flowers@2,0"]
    fixes = [fix_of(line) for line in run_err(*argv).splitlines()]
    for fix in fixes:
        assert run(*fix) == 0
    assert run(*from_copies(argv, fixes)) == 0


def test_conflict_reuses_a_key_out_has_in_the_same_color(tmp_path):
    f = write(tmp_path, "field.px", FIELD)
    out = write(tmp_path, "scene.px", SCENE.replace("v #444444\n", "v #444444\nJ #00ff00\n"))
    msg = run_err("compose", "-o", f"{out}:floor", f"{f}:grass_a@0,0")
    assert fix_of(msg)[2:4] == ["s>J", "t>a"]


def test_conflict_reuse_is_not_a_key_the_source_has(tmp_path):
    f = write(tmp_path, "field.px", FIELD.replace("v #ff00ff\n", "v #ff00ff\nJ #999999\n"))
    out = write(tmp_path, "scene.px", SCENE.replace("v #444444\n", "v #444444\nJ #00ff00\n"))
    msg = run_err("compose", "-o", f"{out}:floor", f"{f}:grass_a@0,0")
    assert "'s>J'" not in msg and fix_of(msg)[2:4] == ["s>a", "t>b"]


def test_conflict_reuse_never_twice_in_one_recolor(tmp_path):
    # s and t both #00ff00 in the source; OUT has J #00ff00: only one of them can take J (recolor refuses two).
    import shlex
    f = write(tmp_path, "f.px", "s #00ff00\nt #00ff00\n\nst\n")
    out = write(tmp_path, "o.px", "s #111111\nt #222222\nJ #00ff00\n@frame x\nstJ\n")
    msg = run_err("compose", "-o", f"{out}:y", f"{f}@0,0")
    assert fix_of(msg)[2:4] == ["s>J", "t>a"]
    assert run(*fix_of(msg)) == 0
    assert run("compose", "-o", f"{out}:y", f"{fix_of(msg)[-1]}@0,0") == 0


def test_free_order_is_every_key_shell_safe_first():
    assert sorted(pxart.FREE_ORDER) == sorted(pxart.KEYS) and len(set(pxart.FREE_ORDER)) == len(pxart.KEYS)
    safe = [k for k in pxart.FREE_ORDER if k not in pxart.AWKWARD]
    assert pxart.FREE_ORDER[:len(safe)] == safe
    assert "".join(pxart.FREE_ORDER[:62]) == pxart.string.ascii_letters + pxart.string.digits
    assert "".join(safe[62:]) == "%+-/:^_"
    for c in "!$`'*?[]{}~&;|<>(),=":
        assert c in pxart.AWKWARD and pxart.FREE_ORDER.index(c) >= len(safe)
    for c in '"\\#@. ':
        assert c not in pxart.FREE_ORDER


def test_conflict_suggests_digits_then_safe_punctuation_before_awkward(tmp_path):
    letters = pxart.string.ascii_letters
    pal = "".join(f"{k} #{i:06x}\n" for i, k in enumerate(letters + pxart.string.digits[:9], 1))
    out = write(tmp_path, "o.px", pal + "@frame x\na\n")
    f = write(tmp_path, "f.px", "a #fefefe\nb #fdfdfd\nc #fcfcfc\n\nabc\n")
    msg = run_err("compose", "-o", f"{out}:y", f"{f}@0,0")
    assert fix_of(msg)[2:5] == ["a>9", "b>%", "c>+"]


def test_conflict_awkward_keys_only_when_nothing_else_is_free(tmp_path):
    import shlex
    safe = [k for k in pxart.FREE_ORDER if k not in pxart.AWKWARD]
    pal = "".join(f"{k} #{i:06x}\n" for i, k in enumerate(safe, 1))
    out = write(tmp_path, "o.px", pal + "@frame x\na\n")
    f = write(tmp_path, "f.px", "a #fefefe\n\na\n")
    msg = run_err("compose", "-o", f"{out}:y", f"{f}@0,0")
    fix = fix_of(msg)
    assert fix[2][2] == pxart.FREE_ORDER[len(safe)] and fix[2][2] in pxart.AWKWARD
    assert run(*fix) == 0 and run("compose", "-o", f"{out}:y", f"{fix[-1]}@0,0") == 0


def test_new_keys_helper():
    src = {"s": (0, 255, 0, 255), "t": (0, 136, 0, 255), ".": pxart.CLEAR}
    have = {"s": (1, 1, 1, 255), "t": (2, 2, 2, 255), "a": (9, 9, 9, 255), ".": pxart.CLEAR}
    taken = set(have) | set(src)
    assert pxart.new_keys(["s", "t"], src, have, taken) == {"s": "b", "t": "c"}
    assert {"b", "c"} <= taken
    assert pxart.new_keys(["s"], src, have, taken) == {"s": "d"}  # never one it gave out before


def test_new_keys_helper_never_suggests_dot_for_a_transparent_key():
    src = {"z": pxart.CLEAR, ".": pxart.CLEAR}
    have = {"z": (1, 1, 1, 255), ".": pxart.CLEAR}
    assert pxart.new_keys(["z"], src, have, set(have) | set(src)) == {"z": "a"}


def test_new_keys_helper_out_of_keys():
    src = {"s": (0, 255, 0, 255)}
    have = {k: (1, 1, 1, 255) for k in pxart.KEYS}
    assert pxart.new_keys(["s"], src, have, set(have)) is None


@pytest.mark.parametrize("ns, want", [([1], "1"), ([1, 2], "1-2"), ([1, 2, 3, 5], "1-3, 5"),
                                      ([2, 4, 6], "2, 4, 6"), ([1, 3, 4, 5, 9, 10], "1, 3-5, 9-10")])
def test_spans(ns, want):
    assert pxart.spans(ns) == want


def test_paste_and_frames_copy_suggest_shell_safe_keys_too(tmp_path):
    safe = [k for k in pxart.FREE_ORDER if k not in pxart.AWKWARD]
    pal = "".join(f"{k} #{i:06x}\n" for i, k in enumerate(pxart.string.ascii_letters + pxart.string.digits, 1))
    d = write(tmp_path, "d.px", pal + "@frame x\na\n")
    s = write(tmp_path, "s.px", "a #fefefe\n@frame y\na\n")
    assert fix_of(run_err("paste", s, "--into", f"{d}:x", "--at", "0,0"))[2] == "a>%"
    assert fix_of(run_err("frames", s, "--copy-to", d))[2] == "a>%"
    assert safe[62] == "%"


def test_help_documents_conflicts_per_file_and_safe_keys():
    doc = " ".join(pxart.__doc__.split())
    assert "one line per source file (all its layers: 'layers 1-4, 7 (field.px)')" in doc
    assert "chosen once for the whole compose, so no two lines' suggestions collide" in doc
    assert "then letters and digits, then % + - / : ^ _, and only when those run out" in doc


# ---------------------------------------------------------------- --rekey: free keys in OUT, sources untouched

def pixels_of(path, fid):
    doc = pxart.parse(path)
    img = doc.image(doc.get(fid) if fid else doc.frames[0])
    return pxart.pixels(img)


def test_compose_rekey_existing_out(tmp_path, capsys):
    f, out = field_scene(tmp_path)
    before = f.read_text()
    assert run(*floor_argv(f, out, 7), "--rekey") == 0
    got = capsys.readouterr().out
    assert got == (f"note: --rekey gives {f}'s keys free ones in {out}: 's>a' 't>b' 'u>c' 'v>d' ({f} is unchanged)\n"
                   f"wrote {out} frame floor\n")
    assert f.read_text() == before
    doc = pxart.parse(out)
    assert doc.palette == {**pxart.parse(write(tmp_path, "s2.px", SCENE)).palette,
                           "a": pxart.hex2rgba("#00ff00"), "b": pxart.hex2rgba("#008800"),
                           "c": pxart.hex2rgba("#88ff88"), "d": pxart.hex2rgba("#ff00ff")}
    assert doc.get("floor").grid == ["abacdaabacdaab", "bacaadbacaadba"]
    assert doc.get("x").grid == ["stuv"]


def test_compose_rekey_renders_like_the_copy_recipe(tmp_path):
    f, out = field_scene(tmp_path)
    out2 = write(tmp_path, "scene2.px", SCENE)
    argv = floor_argv(f, out, 7)
    fix = fix_of(run_err(*argv))
    assert run(*fix) == 0 and run(*from_copies(argv, [fix])) == 0
    assert run(*floor_argv(f, out2, 7), "--rekey") == 0
    assert pixels_of(out, "floor") == pixels_of(out2, "floor")
    assert pxart.parse(out).text().replace("scene", "") == pxart.parse(out2).text().replace("scene", "")


def test_compose_rekey_again_reuses_the_keys(tmp_path):
    f, out = field_scene(tmp_path)
    assert run(*floor_argv(f, out, 3), "--rekey") == 0
    pal = dict(pxart.parse(out).palette)
    assert run("compose", "-o", f"{out}:more", "--size", "2x2", f"{f}:flowers@0,0", "--rekey") == 0
    doc = pxart.parse(out)
    assert doc.palette == pal and doc.get("more").grid == ["da", "ad"]


def test_compose_rekey_new_out(tmp_path, capsys):
    a, b, c = conflict_layers(tmp_path)
    out = tmp_path / "o.px"
    srcs = [x.read_text() for x in (a, b, c)]
    assert run("compose", "-o", out, "--size", "4x3", f"{a}@0,0", f"{b}@0,1", f"{c}@1,1", "--rekey") == 0
    got = capsys.readouterr().out
    assert f"note: --rekey gives {b}'s keys free ones in {out}: 'h>a' 'n>b' 'w>c' ({b} is unchanged)" in got
    assert f"note: --rekey gives {c}'s keys free ones in {out}: 'q>d' ({c} is unchanged)" in got
    assert "leaves out" not in got
    assert [x.read_text() for x in (a, b, c)] == srcs
    img = pxart.parse(out).image(pxart.parse(out).frames[0])
    want = {(0, 0): "#111111", (1, 0): "#222222", (2, 0): "#eee0b8", (0, 1): "#aaaaaa", (1, 1): "#654321",
            (2, 1): "#f6ecd2", (3, 1): "#123456"}
    for xy, col in want.items():
        assert img.getpixel(xy) == pxart.hex2rgba(col), xy


def test_compose_rekey_prints_each_note_once(tmp_path, capsys):
    f, out = field_scene(tmp_path)
    assert run("compose", "-o", f"{out}:floor", "--size", "1x1", f"{f}:grass_a@0,0", "--rekey") == 0
    got = capsys.readouterr().out.splitlines()
    assert len(got) == 3 and got[0].startswith("note: --rekey") and "were cropped" in got[1]
    assert got[2] == f"wrote {out} frame floor"


def test_compose_rekey_without_conflicts_is_a_plain_compose(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\n\nk\n")
    o1, o2 = tmp_path / "o1.px", tmp_path / "o2.px"
    assert run("compose", "-o", o1, f"{a}@0,0") == 0
    plain = capsys.readouterr().out.replace("o1", "o2")
    assert run("compose", "-o", o2, f"{a}@0,0", "--rekey") == 0
    assert capsys.readouterr().out == plain and o1.read_text() == o2.read_text()


def test_compose_rekey_mirrored_layer(tmp_path):
    f, out = field_scene(tmp_path)
    assert run("compose", "-o", f"{out}:floor", "--size", "2x2", f"{f}:flowers+h@0,0", "--rekey") == 0
    assert pxart.parse(out).get("floor").grid == ["ab", "ba"]  # flowers is v s / s v; s>a v>b, mirrored


def test_compose_rekey_carries_variant_colors_into_a_new_out(tmp_path):
    f = write(tmp_path, "f.px", "s #00ff00\n@variant night\ns #003300\n@frame a\ns\n")
    g = write(tmp_path, "g.px", "s #111111\n@variant night\ns #010101\n@frame x\ns\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{g}:x@0,0", f"{f}:a@1,0", "--rekey") == 0
    doc = pxart.parse(out)
    assert doc.frames[0].grid == ["sa"]
    night = doc.image(doc.frames[0], "night")
    assert night.getpixel((0, 0)) == pxart.hex2rgba("#010101") and night.getpixel((1, 0)) == pxart.hex2rgba("#003300")


def test_compose_rekey_existing_out_variants_as_a_plain_compose(tmp_path):
    # An existing OUT takes a new key's base color only (compose's rule); a rekeyed key is no different.
    f = write(tmp_path, "f.px", "s #00ff00\n@variant night\ns #003300\n@frame a\ns\n")
    out = write(tmp_path, "o.px", "s #111111\n@variant night\ns #010101\n@frame x\ns\n")
    assert run("compose", "-o", f"{out}:y", f"{f}:a@0,0", "--rekey") == 0
    doc = pxart.parse(out)
    assert doc.get("y").grid == ["a"] and doc.palette["a"] == pxart.hex2rgba("#00ff00")
    assert doc.image(doc.get("x"), "night").getpixel((0, 0)) == pxart.hex2rgba("#010101")


def test_compose_rekey_shared_palette_key(tmp_path, capsys):
    # The clashing key comes from the layer's @palette import: OUT gets it under a free key, nothing left out.
    write(tmp_path, "pal.px", "s #00ff00\n")
    f = write(tmp_path, "f.px", "@palette pal.px\n@frame a\ns\n")
    g = write(tmp_path, "g.px", "s #111111\n\ns\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{g}@0,0", f"{f}:a@1,0", "--rekey") == 0
    got = capsys.readouterr().out
    assert "leaves out" not in got and "'s>a'" in got
    doc = pxart.parse(out)
    assert doc.frames[0].grid == ["sa"] and doc.palette == {"s": pxart.hex2rgba("#111111"),
                                                            "a": pxart.hex2rgba("#00ff00")}


def test_compose_rekey_out_of_keys_still_fails(tmp_path):
    keys = pxart.KEYS
    a = write(tmp_path, "a.px", "".join(f"{k} #000000\n" for k in keys) + "\n" + keys[0] + "\n")
    b = write(tmp_path, "b.px", f"{keys[0]} #ffffff\n\n{keys[0]}\n")
    out = tmp_path / "o.px"
    msg = run_err("compose", "-o", out, "--size", "2x1", f"{a}@0,0", f"{b}@1,0", "--rekey")
    assert "aren't enough free keys" in msg and not out.exists()


def test_compose_rekey_other_errors_as_without(tmp_path):
    a = write(tmp_path, "a.px", "k #000000\n\nk\n")
    argv = ["compose", "-o", tmp_path / "o.px", f"{a}:nope@0,0"]
    assert run_err(*argv, "--rekey") == run_err(*argv)


def test_compose_rekey_only_the_clashing_file(tmp_path, capsys):
    f, out = field_scene(tmp_path)
    g = write(tmp_path, "g.px", "z #abcdef\n\nz\n")
    assert run("compose", "-o", f"{out}:floor", "--size", "3x2", f"{f}:grass_a@0,0", f"{g}@2,0", "--rekey") == 0
    got = capsys.readouterr().out
    assert f"{g}'s" not in got and pxart.parse(out).get("floor").grid == ["abz", "ba."]


def test_crop_rekey(tmp_path, capsys):
    f, out = field_scene(tmp_path)
    before = f.read_text()
    assert run("crop", f"{f}:grass_c", "0,0,2,1", "-o", f"{out}:c", "--rekey") == 0
    assert "note: --rekey" in capsys.readouterr().out and f.read_text() == before
    assert pxart.parse(out).get("c").grid == ["ab"]


def test_paste_rekey(tmp_path, capsys):
    f, out = field_scene(tmp_path)
    before = f.read_text()
    assert run("paste", f"{f}:grass_a", "--into", f"{out}:x", "--at", "1,0", "--rekey") == 0
    got = capsys.readouterr().out
    assert got == f"note: --rekey gives {f}'s keys free ones in {out}: 's>a' 't>b' ({f} is unchanged)\nwrote {out}\n"
    assert f.read_text() == before
    doc = pxart.parse(out)
    assert doc.get("x").grid == ["sabv"] and list(doc.palette)[-2:] == ["a", "b"]


def test_paste_rekey_mirrored_and_no_conflict(tmp_path, capsys):
    f, out = field_scene(tmp_path)
    assert run("paste", f"{f}:grass_a+h", "--into", f"{out}:x", "--at", "0,0", "--rekey") == 0
    assert pxart.parse(out).get("x").grid == ["bauv"]
    capsys.readouterr()
    k = write(tmp_path, "k.px", "z #abcdef\n\nz\n")
    assert run("paste", k, "--into", f"{out}:x", "--at", "3,0", "--rekey") == 0
    assert "--rekey" not in capsys.readouterr().out and pxart.parse(out).get("x").grid == ["bauz"]


def test_frames_copy_rekey(tmp_path, capsys):
    s = write(tmp_path, "s.px", CSRC)
    d = write(tmp_path, "d.px", CDST.replace("k #000000\n", "k #000000\nw #eeeeee\n"))
    before = s.read_text()
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey") == 0
    got = capsys.readouterr().out
    # w: another color in d. k: black in both, but only d's night recolors it, so it gets a key of its own too.
    assert got.startswith(f"note: --rekey gives {s}'s keys free ones in {d}: 'k>a' 'w>b' ({s} is unchanged)\n")
    assert "other variant colors" not in got
    assert s.read_text() == before
    doc = pxart.parse(d)
    assert doc.get("walk/0").grid == ["ab", "a."] and doc.palette["b"] == pxart.hex2rgba("#ffffff")
    assert doc.variants["night"]["b"] == pxart.hex2rgba("#888888")
    assert doc.palette["a"] == pxart.hex2rgba("#000000") and "a" not in doc.variants["night"]
    assert doc.get("idle").grid == ["k"]  # d's own k keeps d's night
    assert plays(d, "walk/0")[0][None] == plays(s, "walk/0")[0][None]


def test_frames_copy_rekey_transparent_key(tmp_path):
    s = write(tmp_path, "s.px", "k #000000\nz transparent\n@frame a\nkz\n")
    d = write(tmp_path, "d.px", "k #000000\nz #ff0000\n@frame b\nk\n")
    assert run("frames", s, "--copy-to", d, "--rekey") == 0
    doc = pxart.parse(d)
    assert doc.get("a").grid == ["ka"] and doc.palette["a"] == pxart.CLEAR


def test_rekey_copy_helper(tmp_path):
    taken = set()
    assert pxart.rekey_copy("art/field.px", "out/scene.px", taken) == pathlib.Path("out/rekeyed/field.px")
    assert pxart.rekey_copy("other/field.px", "out/scene.px", taken) == pathlib.Path("out/rekeyed/field-2.px")
    assert pxart.rekey_copy("x/field.px", "out/scene.px", taken) == pathlib.Path("out/rekeyed/field-3.px")
    assert pxart.rekey_copy("art/field.px", "scene.px") == pathlib.Path("rekeyed/field.px")


def test_conflict_two_sources_of_one_name_get_two_copies(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    f1 = write(tmp_path / "a", "t.px", "s #00ff00\n\ns\n")
    f2 = write(tmp_path / "b", "t.px", "s #0000ff\n\ns\n")
    out = write(tmp_path, "o.px", "s #111111\n@frame x\ns\n")
    argv = ["compose", "-o", f"{out}:y", "--size", "2x1", f"{f1}@0,0", f"{f2}@1,0"]
    fixes = [fix_of(l) for l in run_err(*argv).splitlines()]
    assert [f[-1] for f in fixes] == [str(tmp_path / "rekeyed" / "t.px"), str(tmp_path / "rekeyed" / "t-2.px")]
    for fix in fixes:
        assert run(*fix) == 0
    assert run(*from_copies(argv, fixes)) == 0


def test_conflict_from_a_copy_suggests_renaming_it_in_place(tmp_path):
    # Composing from rekeyed/field.px and hitting new keys: the copy is the one to rename, no copy of a copy.
    f, out = field_scene(tmp_path)
    fix = fix_of(run_err("compose", "-o", f"{out}:floor", f"{f}:grass_a@0,0"))
    assert run(*fix) == 0
    copy = fix[-1]
    msg = run_err("compose", "-o", f"{out}:more", f"{copy}:grass_c@0,0")
    assert f"Or give them those keys in {copy} itself: pxart recolor {copy} 'u>" in msg and " -o " not in msg


def test_conflict_copy_goes_beside_out_as_typed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "art").mkdir()
    write(tmp_path / "art", "field.px", FIELD)
    write(tmp_path / "art", "scene.px", SCENE)
    msg = run_err("compose", "-o", "art/scene.px:floor", "art/field.px:grass_a@0,0")
    assert fix_of(msg) == ["recolor", "art/field.px", "s>a", "t>b", "-o", "art/rekeyed/field.px"]


def test_conflict_copy_repoints_its_palette(tmp_path):
    write(tmp_path, "pal.px", "s #00ff00\n")
    f = write(tmp_path, "f.px", "@palette pal.px\n@frame a\ns\n")
    out = write(tmp_path, "o.px", "s #111111\n@frame x\ns\n")
    fix = fix_of(run_err("compose", "-o", f"{out}:y", f"{f}:a@0,0"))
    assert run(*fix) == 0
    assert "@palette ../pal.px" in pathlib.Path(fix[-1]).read_text()
    assert run("compose", "-o", f"{out}:y", f"{fix[-1]}:a@0,0") == 0
    assert pixels_of(out, "y") == [pxart.hex2rgba("#00ff00")]


def test_rekey_helper_moves_every_frame_and_lines(tmp_path):
    doc = pxart.parse(write(tmp_path, "f.px", "s #00ff00\nt #000000\n@variant night\ns #003300\n"
                                            "@frame a\nst\n@frame b\nts\n"))
    extra = pxart.Frame("m", ["ss"])
    pxart.rekey(doc, {"s": "Q"}, [extra])
    assert doc.get("a").grid == ["Qt"] and doc.get("b").grid == ["tQ"] and extra.grid == ["QQ"]
    assert "s" not in doc.palette and doc.palette["Q"] == pxart.hex2rgba("#00ff00")
    assert doc.variants["night"] == {"Q": pxart.hex2rgba("#003300")}


def test_rekey_flags_on_the_commands():
    for cmd in ("compose", "crop", "paste", "frames"):
        assert "--rekey" in pxart.parser()[1].choices[cmd].format_help(), cmd


def test_help_documents_rekey():
    doc = " ".join(pxart.__doc__.split())
    assert ("compose -o OUT[:frame] [--size WxH] [--under] [--rekey [KEYS]] [--used-keys-only] "
            "[--variant-map NAME=V1,V2] [--replace] "
            "LAYER@x,y") in doc
    assert ("--rekey: compose gives those keys the free ones in OUT as it goes (the files are read, never "
            "written)") in doc
    assert "a copy: 'pxart recolor field.px 's>a' 't>b' -o rekeyed/field.px' (rekeyed/ beside OUT)" in doc
    assert "with no -o renames them in field.px itself, in every frame" in doc
    assert "--rekey gives both free keys in DST, as compose's does" in doc
    assert "--rekey gives both free keys in DST. --rekey o,r moves only those keys" in doc


# ---------------------------------------------------------------- each command's E_KEY_CONFLICT in its own nouns

def test_crop_conflict_in_crops_words(tmp_path):
    f, out = field_scene(tmp_path)
    msg = run_err("crop", f"{f}:grass_a", "0,0,1,1", "-o", f"{out}:c")
    assert msg == (f"crop: FILE ({f}:grass_a): E_KEY_CONFLICT: 2 keys of FILE are other colors in {out}: 's' #00ff00 "
                   "(#111111 there), 't' #008800 (#222222 there); to keep both colors (no pixel changes color), add "
                   f"--rekey: crop then gives FILE's keys free ones in {out} ('s>a' 't>b') and leaves {f} as it is. Or "
                   f"give them those keys in a copy and crop from that: pxart recolor {f} 's>a' 't>b' -o "
                   f"{tmp_path / 'rekeyed' / 'field.px'}")


def test_crop_conflict_never_says_layer_or_compose(tmp_path):
    f, out = field_scene(tmp_path)
    msg = run_err("crop", f"{f}:grass_c", "0,0,2,2", "-o", f"{out}:c")
    assert "layer" not in msg and "compose" not in msg and msg.startswith("crop: FILE (")


def test_crop_conflict_recipe_works(tmp_path):
    f, out = field_scene(tmp_path)
    fix = fix_of(run_err("crop", f"{f}:grass_a", "0,0,2,1", "-o", f"{out}:c"))
    assert run(*fix) == 0
    assert run("crop", f"{fix[-1]}:grass_a", "0,0,2,1", "-o", f"{out}:c") == 0
    assert pixels_of(out, "c") == [pxart.hex2rgba("#00ff00"), pxart.hex2rgba("#008800")]


def test_crop_of_a_png_is_a_clear_error(tmp_path):
    Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(tmp_path / "a.png")
    msg = run_err("crop", tmp_path / "a.png", "0,0,1,1", "-o", tmp_path / "c.px")
    assert msg.startswith(f"crop: FILE ({tmp_path / 'a.png'}): E_BAD_ARG: crop cuts a .px frame")
    assert "mask --keep" in msg and "Traceback" not in msg and not (tmp_path / "c.px").exists()


def test_crop_error_inside_names_file_not_layer(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\n@frame a\nk\n@frame b\nk\n")
    msg = run_err("crop", p, "0,0,1,1", "-o", tmp_path / "c.px")
    assert msg.startswith(f"crop: FILE ({p}): E_SELECT") and "layer" not in msg


def test_compose_conflict_still_says_layer_after_a_crop(tmp_path):
    # crop's words ride on its own args; a compose in the same process keeps compose's.
    f, out = field_scene(tmp_path)
    run_err("crop", f"{f}:grass_a", "0,0,1,1", "-o", f"{out}:c")
    msg = run_err("compose", "-o", f"{out}:y", f"{f}:grass_a@0,0")
    assert msg.startswith(f"compose: layer 1 ({f}:grass_a): ") and "then gives this layer's keys" in msg
    assert "compose from that" in msg


def test_frames_copy_conflict_says_file(tmp_path):
    f, out = field_scene(tmp_path)
    msg = run_err("frames", f"{f}:grass_a", "--copy-to", out)
    assert msg.startswith(f"frames: FILE ({f}:grass_a): E_KEY_CONFLICT: 2 keys of FILE are other colors in {out}")
    assert "SRC" not in msg and "copy the frames from that" in msg and "frames --copy-to then gives FILE's" in msg


def test_paste_conflict_says_src(tmp_path):
    f, out = field_scene(tmp_path)
    msg = run_err("paste", f"{f}:grass_a", "--into", f"{out}:x", "--at", "0,0")
    assert msg.startswith(f"paste: SRC ({f}:grass_a): E_KEY_CONFLICT: 2 keys of SRC")
    assert "paste from that" in msg and "layer" not in msg and "compose" not in msg


def test_paste_adds_new_keys_in_sorted_order_every_run(tmp_path):
    # They were added in set order, which Python's per-run string hashing shuffles.
    import subprocess
    orders = set()
    for seed in ("1", "2", "3", "4", "5", "6"):
        d = write(tmp_path, "d.px", "k #000000\n@frame x\nkkkkk\n")
        s = write(tmp_path, "s.px", "q #111111\nb #222222\nz #333333\na #444444\n\nqbza\n")
        env = {**__import__("os").environ, "PYTHONHASHSEED": seed}
        subprocess.run([sys.executable, pxart.__file__, "paste", str(s), "--into", f"{d}:x", "--at", "0,0"], env=env,
                       check=True, capture_output=True)
        orders.add(tuple(pxart.parse(d).palette))
    assert orders == {("k", "a", "b", "q", "z")}


# ---------------------------------------------------------------- palette --extract-to keeps the palette's comments

BEAST = ("# Beast: moss-backed guardian. 6 colors.\n"
         "o #221a26\n# bark: shadow -> light\nx #3e2c34\nX #5e4038\n# spirit glow (eyes, runes)\ne #fff6b0\nE #6ae0cc\n"
         "\n# dusk: the glow (e, E) is left out on purpose so it keeps its base color and reads as light.\n"
         "@variant dusk\no #150f1c\n# bark sinks\nx #261a2a\nX #3a2834\n")


def test_extract_to_carries_key_section_and_variant_comments(tmp_path):
    p = write(tmp_path, "beast.px", BEAST + "\n@frame idle\noxXeE\n")
    out = tmp_path / "pal.px"
    assert run("palette", p, "--extract-to", out) == 0
    assert out.read_text() == ("pxart 1\no #221a26\n# bark: shadow -> light\nx #3e2c34\nX #5e4038\n"
                               "# spirit glow (eyes, runes)\ne #fff6b0\nE #6ae0cc\n"
                               "\n# dusk: the glow (e, E) is left out on purpose so it keeps its base color and reads as "
                               "light.\n@variant dusk\no #150f1c\n# bark sinks\nx #261a2a\nX #3a2834\n")


def test_extract_to_leaves_a_sprites_header_with_the_sprite(tmp_path):
    p = write(tmp_path, "beast.px", BEAST + "\n@frame idle\noxXeE\n")
    out = tmp_path / "pal.px"
    assert run("palette", p, "--extract-to", out) == 0
    assert "# Beast:" not in out.read_text()


def test_extract_to_from_a_palette_file_keeps_its_header(tmp_path):
    p = write(tmp_path, "beast.px", BEAST)
    out = tmp_path / "copy.px"
    assert run("palette", p, "--extract-to", out) == 0
    text = out.read_text()
    assert text.startswith("# Beast: moss-backed guardian. 6 colors.\npxart 1\no #221a26\n# bark: shadow -> light\n")
    assert "# dusk: the glow (e, E) is left out on purpose" in text and "# bark sinks\nx #261a2a" in text


def test_extract_to_carries_an_imports_comments_and_header(tmp_path):
    write(tmp_path, "hero_pal.px", "# Hero palette: keys are per-material.\npxart 1\n# skin\ns #f4c7a0\nk #c98468\n"
                                   "\n# night: skin cools\n@variant night\ns #806070\n")
    p = write(tmp_path, "hero.px", "@palette hero_pal.px\n# cape\nc #8e1f2e\n@frame a\nskc\n")
    out = tmp_path / "all.px"
    assert run("palette", p, "--extract-to", out) == 0
    assert out.read_text() == ("# Hero palette: keys are per-material.\npxart 1\n# skin\ns #f4c7a0\nk #c98468\n# cape\n"
                               "c #8e1f2e\n\n# night: skin cools\n@variant night\ns #806070\n")


def test_extract_to_local_comment_wins_over_the_imports(tmp_path):
    write(tmp_path, "base.px", "pxart 1\n# base's skin\ns #f4c7a0\n")
    p = write(tmp_path, "hero.px", "@palette base.px\n# hero's own skin\ns #ffffff\n@frame a\ns\n")
    out = tmp_path / "all.px"
    assert run("palette", p, "--extract-to", out) == 0
    assert "# hero's own skin\ns #ffffff" in out.read_text() and "base's skin" not in out.read_text()


def test_extract_to_uncommented_local_override_keeps_the_imports_comment(tmp_path):
    write(tmp_path, "base.px", "pxart 1\n# skin\ns #f4c7a0\n")
    p = write(tmp_path, "hero.px", "@palette base.px\ns #ffffff\n@frame a\ns\n")
    out = tmp_path / "all.px"
    assert run("palette", p, "--extract-to", out) == 0
    assert out.read_text() == "pxart 1\n# skin\ns #ffffff\n"


def test_extract_to_nested_imports_and_their_headers(tmp_path):
    write(tmp_path, "a.px", "# A header\n# a key\na #111111\n")
    write(tmp_path, "b.px", "# B header\n@palette a.px\n# b key\nb #222222\n")
    p = write(tmp_path, "s.px", "@palette b.px\n@frame f\nab\n")
    out = tmp_path / "out.px"
    assert run("palette", p, "--extract-to", out) == 0
    # With no version line, a palette file's comments above its first key are its header (the parser can't tell).
    assert out.read_text() == "# A header\n# a key\n# B header\npxart 1\na #111111\n# b key\nb #222222\n"


def test_extract_to_header_of_a_palette_without_version_line(tmp_path):
    write(tmp_path, "base.px", "# base's skin\ns #f4c7a0\n")
    p = write(tmp_path, "hero.px", "@palette base.px\n@frame a\ns\n")
    assert run("palette", p, "--extract-to", tmp_path / "all.px") == 0
    assert (tmp_path / "all.px").read_text() == "# base's skin\npxart 1\ns #f4c7a0\n"


def test_extract_to_blank_only_leads_keep_default_spacing(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\n\n\nj #111111\n@variant x\nk #ffffff\n@frame f\nkj\n")
    out = tmp_path / "out.px"
    assert run("palette", p, "--extract-to", out) == 0
    assert out.read_text() == "pxart 1\nk #000000\nj #111111\n\n@variant x\nk #ffffff\n"


def test_extract_to_output_still_renders_like_the_source(tmp_path):
    p = write(tmp_path, "beast.px", BEAST + "\n@frame idle\noxXeE\n")
    before = renders(p)
    assert run("palette", p, "--extract-to", tmp_path / "pal.px", "--repoint") == 0
    assert renders(p) == before
    assert run("check", tmp_path / "pal.px") == 0


def test_extract_to_repoint_moves_comments_not_copies(tmp_path):
    p = write(tmp_path, "beast.px", BEAST.replace("# Beast", "pxart 1\n# Beast") + "\n@frame idle\noxXeE\n")
    assert run("palette", p, "--extract-to", tmp_path / "pal.px", "--repoint") == 0
    text = p.read_text()
    assert "# bark" not in text and "# dusk" not in text and "# spirit" not in text
    assert "# bark: shadow -> light" in (tmp_path / "pal.px").read_text()


def test_extract_to_repoint_first_key_comment_moves_blank_lines_stay(tmp_path):
    p = write(tmp_path, "s.px", "pxart 1\n\n# the black\nk #000000\n@frame f\nk\n")
    assert run("palette", p, "--extract-to", tmp_path / "pal.px", "--repoint") == 0
    assert p.read_text() == "pxart 1\n\n@palette pal.px\n@frame f\nk\n"
    assert (tmp_path / "pal.px").read_text() == "pxart 1\n\n# the black\nk #000000\n"  # its lead, blank line too


def test_extract_to_repoint_keeps_the_import_lines_comment(tmp_path):
    p = xsetup(tmp_path)
    assert run("palette", p, "--extract-to", tmp_path / "p.px", "--repoint") == 0
    assert p.read_text().startswith("pxart 1\n# my palette\n@palette p.px\n")


def test_palette_notes_helper_cycle_is_safe(tmp_path):
    a = write(tmp_path, "a.px", "@palette b.px\n# a\na #111111\n")
    write(tmp_path, "b.px", "# b\nb #222222\n")
    doc = pxart.parse(a, palette_only=True)
    doc.palette_refs.append("a.px")  # a cycle back to itself, as a nested file might have
    notes, head = pxart.palette_notes(doc)
    assert notes == {("key", "a"): ["# a"]} and head == ["# b"]


def test_help_documents_extract_to_comments():
    doc = " ".join(pxart.__doc__.split())
    assert "with the comments that document them: those above key and @variant lines" in doc
    assert "a sprite's header is about the sprite and stays" in doc


# ---------------------------------------------------------------- palette FILE: what each variant recolors and inherits

def test_palette_lists_each_variants_overrides_and_keeps(tmp_path, capsys):
    p = write(tmp_path, "beast.px", BEAST + "\n@frame idle\noxXeE\n")
    assert run("palette", p) == 0
    out = capsys.readouterr().out.splitlines()
    at = out.index("variants: dusk")
    assert out[at:at + 2] == ["variants: dusk", "  dusk: recolors (darker) o x X; inherits: e E"]


def test_palette_variant_lines_in_palette_order_not_variant_order(tmp_path, capsys):
    p = write(tmp_path, "s.px", "a #000000\nb #111111\nc #222222\n@variant v\nc #ffffff\na #eeeeee\n@frame f\nabc\n")
    assert run("palette", p) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "  v: brightens a c; inherits: b"


def test_palette_variants_several_sorted(tmp_path, capsys):
    p = write(tmp_path, "s.px", "a #000000\nb #111111\n@variant night\na #010101\n@variant dawn\nb #020202\n"
                                "@frame f\nab\n")
    assert run("palette", p) == 0
    assert capsys.readouterr().out.splitlines()[-3:] == ["variants: dawn, night",
                                                         "  dawn: recolors (darker) b; inherits: a",
                                                         "  night: brightens a; inherits: b"]


def test_palette_variant_that_overrides_everything_or_nothing(tmp_path, capsys):
    p = write(tmp_path, "s.px", "a #000000\n@variant all\na #ffffff\n@variant none\n@frame f\na\n")
    assert run("palette", p) == 0
    assert capsys.readouterr().out.splitlines()[-2:] == ["  all: brightens a; inherits: nothing",
                                                         "  none: recolors nothing; inherits: a"]


def test_palette_variant_imported_and_extended_locally(tmp_path, capsys):
    write(tmp_path, "base.px", "a #000000\nb #111111\nc #222222\n@variant dusk\na #010101\n")
    p = write(tmp_path, "s.px", "@palette base.px\nd #333333\n@variant dusk\nd #030303\n@frame f\nabcd\n")
    assert run("palette", p) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "  dusk: recolors (darker) d; brightens a; inherits: b c"


def test_palette_variant_keeps_transparent_keys_and_never_dot(tmp_path, capsys):
    p = write(tmp_path, "s.px", "a #000000\nt transparent\n@variant v\na #ffffff\n@frame f\nat.\n")
    assert run("palette", p) == 0
    line = capsys.readouterr().out.splitlines()[-1]
    assert line == "  v: brightens a; inherits: t" and "." not in line.split(";")[1]


def test_palette_variant_lines_on_a_palette_file(tmp_path, capsys):
    p = write(tmp_path, "beast.px", BEAST)
    assert run("palette", p) == 0
    assert "  dusk: recolors (darker) o x X; inherits: e E" in capsys.readouterr().out.splitlines()


def test_palette_without_variants_prints_no_variant_lines(tmp_path, capsys):
    p = write(tmp_path, "s.px", "a #000000\n\na\n")
    assert run("palette", p) == 0
    assert "variants" not in capsys.readouterr().out and "recolors" not in capsys.readouterr().out


def test_frames_variants_line_is_unchanged(tmp_path, capsys):
    p = write(tmp_path, "beast.px", BEAST + "\n@frame idle\noxXeE\n")
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[-1] == "variants: dusk" and "recolors" not in out


def test_help_documents_variant_overrides():
    doc = " ".join(pxart.__doc__.split())
    assert "then each variant's keys: 'dusk: recolors (darker) o x X c C; inherits: e E q'" in doc


# ---------------------------------------------------------------- anim-set FILE --still: no redundant '@still *'

def test_anim_set_still_star_not_added_when_every_group_is_still(tmp_path, capsys):
    text = "k #000000\n@still ui\n@frame ui/a\nk\n@frame ui/b\nk\n"
    p = write(tmp_path, "ui.px", text)
    assert run("anim-set", p, "--still") == 0
    assert p.read_text() == text
    assert capsys.readouterr().out == (f"already still: every frame is in a still group (@still ui), so '@still *' "
                                       f"would add nothing; no change: {p}\n")


def test_anim_set_still_star_names_every_still_group(tmp_path, capsys):
    text = "k #000000\n@still ui\n@still icons\n@frame ui/a\nk\n@frame icons/b\nk\n"
    p = write(tmp_path, "ui.px", text)
    assert run("anim-set", f"{p}:*", "--still") == 0
    assert p.read_text() == text and "(@still ui, @still icons)" in capsys.readouterr().out


def test_anim_set_still_star_added_when_a_group_animates(tmp_path, capsys):
    p = write(tmp_path, "ui.px", "k #000000\n@still ui\n@frame ui/a\nk\n@frame walk/0\nk\n")
    assert run("anim-set", p, "--still") == 0
    assert pxart.parse(p).stills == ["ui", "*"] and "@still *" in capsys.readouterr().out


def test_anim_set_still_star_added_for_top_level_frames(tmp_path):
    # '@still *' lists a top-level frame as still: not redundant there.
    p = write(tmp_path, "ui.px", "k #000000\n@still ui\n@frame ui/a\nk\n@frame badge\nk\n")
    assert run("anim-set", p, "--still") == 0
    assert pxart.parse(p).stills == ["ui", "*"]


def test_anim_set_still_star_on_a_file_without_still_groups(tmp_path):
    p = write(tmp_path, "ui.px", "k #000000\n@frame ui/a\nk\n")
    assert run("anim-set", p, "--still") == 0
    assert pxart.parse(p).stills == ["*"]


def test_anim_set_still_star_ignores_a_still_line_of_no_frames(tmp_path, capsys):
    # '@still gone' names no frames: every frame (ui/a) is in '@still ui', and only that is named.
    text = "k #000000\n@still ui\n@still gone\n@frame ui/a\nk\n"
    p = write(tmp_path, "ui.px", text)
    assert run("anim-set", p, "--still") == 0
    out = capsys.readouterr().out
    assert p.read_text() == text and "(@still ui)" in out and "gone" not in out


def test_help_documents_redundant_still_star():
    doc = " ".join(pxart.__doc__.split())
    assert "unless every frame already is in a @still group: then it says so and adds nothing" in doc


# ---------------------------------------------------------------- onion: --rows / --feet bands, --tint-a

SWING = ("k #000000\nw #ffffff\n@frame a\n......\n..kk..\n..kk..\n..kk..\n..k.k.\n"
         "@frame b\n....ww\n..kkww\n..kk..\n..kk..\n..k.k.\n"
         "@frame c\n....ww\n..kkww\n..kk..\n..kk..\n..kk..\n")


def test_onion_whole_canvas_readout_lets_a_swing_hide_the_feet(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWING)
    lines = onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b")
    assert lines[2] == "B vs A: left +0, right +1, top -1, bottom +0; best shift +0,+0 then 4px changed (no shift: 4px)"


def test_onion_feet_band_reads_the_feet_only(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWING)
    assert onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b", "--feet", "2") == [
        "A a: opaque x 2..4, y 3..4 (rows 3-4 of the 6x5 canvas, bottom-centered)",
        "B b: opaque x 2..4, y 3..4",
        "B vs A (rows 3-4): left +0, right +0, top +0, bottom +0; best shift +0,+0 then 0px changed (no shift: 0px)",
        f"wrote {tmp_path / 'o.png'}",
    ]


def test_onion_feet_band_sees_a_leg_move(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWING)
    lines = onion_lines(tmp_path, capsys, f"{p}:b", f"{p}:c", "--feet", "1")
    assert lines[0] == "A b: opaque x 2..4, y 4..4 (row 4 of the 6x5 canvas, bottom-centered)"
    # c's feet row is b's row above it moved down: the band's shift takes pixels from above the band.
    assert lines[2] == ("B vs A (row 4): left +0, right -1, top +0, bottom +0; best shift +0,+1 then 0px changed "
                        "(no shift: 2px)")


def test_onion_rows_band(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWING)
    lines = onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b", "--rows", "0-1")
    assert lines == ["A a: opaque x 2..3, y 1..1 (rows 0-1 of the 6x5 canvas, bottom-centered)",
                     "B b: opaque x 2..5, y 0..1",
                     "B vs A (rows 0-1): left +0, right +2, top -1, bottom +0; best shift +0,+0 then 4px changed "
                     "(no shift: 4px)", f"wrote {tmp_path / 'o.png'}"]


def test_onion_band_shift_brings_pixels_in_from_above(tmp_path, capsys):
    # The whole sprite drops 1px: in the feet band the new bottom row came from the row above the band.
    p = write(tmp_path, "d.px", "k #000000\nr #ff0000\n@frame a\n.k.\nrrr\nk.k\n...\n@frame b\n...\n.k.\nrrr\nk.k\n")
    lines = onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b", "--feet", "2")
    assert lines[2] == ("B vs A (rows 2-3): left +0, right +0, top +0, bottom +1; best shift +0,+1 then 0px changed "
                        "(no shift: 5px)")


def test_onion_band_same_as_whole_when_it_is_the_whole_canvas(tmp_path, capsys):
    p = write(tmp_path, "b.px", BOB)
    whole = onion_lines(tmp_path, capsys, f"{p}:w/0", f"{p}:w/1")
    band = onion_lines(tmp_path, capsys, f"{p}:w/0", f"{p}:w/1", "--rows", "0-3")
    assert band[2] == whole[2].replace("B vs A:", "B vs A (rows 0-3):")
    assert band[1] == whole[1] and band[0] == whole[0].replace("on the 3x4 canvas", "rows 0-3 of the 3x4 canvas")


def test_onion_feet_more_than_the_canvas_is_every_row(tmp_path, capsys):
    p = write(tmp_path, "b.px", BOB)
    lines = onion_lines(tmp_path, capsys, f"{p}:w/0", f"{p}:w/1", "--feet", "99")
    assert "(rows 0-3 of the 3x4 canvas" in lines[0]


def test_onion_one_row(tmp_path, capsys):
    p = write(tmp_path, "b.px", BOB)
    lines = onion_lines(tmp_path, capsys, f"{p}:w/0", f"{p}:w/1", "--rows", "3")
    assert "(row 3 of the 3x4 canvas" in lines[0] and lines[2].startswith("B vs A (row 3): ")


def test_onion_band_empty_in_a_or_b(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWING)
    assert onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b", "--rows", "0")[:2] == [
        "A a: nothing opaque (row 0 of the 6x5 canvas, bottom-centered)", "B b: opaque x 4..5, y 0..0"]
    assert onion_lines(tmp_path, capsys, f"{p}:b", f"{p}:a", "--rows", "0")[:3] == [
        "B b: opaque x 4..5, y 0..0 (row 0 of the 6x5 canvas, bottom-centered)".replace("B b", "A b"),
        "B a: nothing opaque in row 0", f"wrote {tmp_path / 'o.png'}"]


def test_onion_band_by_pivot(tmp_path, capsys):
    p = pivot_anim_file(tmp_path, p0="pivot=0,0", p1="pivot=1,0")
    lines = onion_lines(tmp_path, capsys, f"{p}:a/0", f"{p}:a/1", "--rows", "0-1")
    assert lines[0] == "A a/0: opaque x 1..1, y 0..1 (rows 0-1 of the 4x4 canvas, lined up by pivot)"
    assert lines[2].startswith("B vs A (rows 0-1): left +0, right +0, top +0, bottom +0; ")


@pytest.mark.parametrize("flag, val, want", [
    ("--rows", "3-9", "--rows 3-9: the canvas has rows 0-4"),
    ("--rows", "5", "--rows 5: the canvas has rows 0-4"),
    ("--rows", "3-1", "--rows 3-1: the canvas has rows 0-4, and Y0 comes first"),
    ("--rows", "a-b", "--rows wants Y0-Y1"),
    ("--rows", "-1-2", "--rows wants Y0-Y1"),
    ("--feet", "0", "--feet 0: the bottom N rows, N >= 1"),
])
def test_onion_band_errors(tmp_path, flag, val, want):
    p = write(tmp_path, "s.px", SWING)
    msg = run_err("onion", f"{p}:a", f"{p}:b", "-o", tmp_path / "o.png", f"{flag}={val}")
    assert msg.startswith("onion: E_BAD_ARG: ") and want in msg and not (tmp_path / "o.png").exists()


def test_onion_rows_and_feet_are_one_or_the_other(tmp_path):
    p = write(tmp_path, "s.px", SWING)
    assert run("onion", f"{p}:a", f"{p}:b", "-o", tmp_path / "o.png", "--rows", "1-2", "--feet", "1") == 2


def onion_png(tmp_path, *more):
    p = write(tmp_path, "s.px", SWING)
    assert run("onion", f"{p}:a", f"{p}:c", "-o", tmp_path / "o.png", "--scale", "1", *more) == 0
    return Image.open(tmp_path / "o.png").convert("RGBA")


def old_onion(A, B, w, h, spots):
    """onion's PNG at --scale 1 as it was before the flags, the default until --tint-a became it: --fade-a must stay
    byte-identical to it."""
    base = pxart.on_bg(Image.new("RGBA", (1, 1), pxart.CLEAR), w, h)
    faded = A.copy(); faded.putalpha(A.getchannel("A").point(lambda v: v * 35 // 100))
    base.alpha_composite(faded, spots[0])
    top = B.copy(); top.putalpha(B.getchannel("A").point(lambda v: v * 80 // 100))
    base.alpha_composite(top, spots[1])
    return base


def test_onion_fade_a_png_is_the_old_default(tmp_path):
    img = onion_png(tmp_path, "--fade-a")
    doc = pxart.parse(tmp_path / "s.px")
    want = old_onion(doc.image(doc.get("a")), doc.image(doc.get("c")), 6, 5, [(0, 0), (0, 0)])
    assert img.tobytes() == want.tobytes()


def test_onion_fade_a_png_is_the_old_default_at_scale_8(tmp_path):
    p = write(tmp_path, "s.px", SWING)
    assert run("onion", f"{p}:a", f"{p}:b", "-o", tmp_path / "o.png", "--fade-a") == 0
    doc = pxart.parse(p)
    want = pxart.upscale(old_onion(doc.image(doc.get("a")), doc.image(doc.get("b")), 6, 5, [(0, 0), (0, 0)]), 8,
                         grid=True, rulers=True)
    assert Image.open(tmp_path / "o.png").convert("RGBA").tobytes() == want.tobytes()


@pytest.mark.parametrize("look", [[], ["--fade-a"]])
def test_onion_band_darkens_the_rows_outside(tmp_path, look):
    plain, band = onion_png(tmp_path, *look), onion_png(tmp_path, "--feet", "2", *look)
    assert band.getpixel((0, 4)) == plain.getpixel((0, 4)) and band.getpixel((0, 3)) == plain.getpixel((0, 3))
    assert sum(band.getpixel((0, 0))[:3]) < sum(plain.getpixel((0, 0))[:3])
    assert sum(band.getpixel((0, 2))[:3]) < sum(plain.getpixel((0, 2))[:3])


def test_onion_tint_a_default_color(tmp_path):
    img = onion_png(tmp_path, "--tint-a")
    # (4, 4): A's leg only, B empty there: the tint over the backdrop, redder than it.
    bg = pxart.rgba("#3a3a44")
    r, g, b, a = img.getpixel((4, 4))
    assert a == 255 and r > bg[0] + 100 and g < bg[1] + 30
    want = Image.new("RGBA", (1, 1), bg)
    want.alpha_composite(Image.new("RGBA", (1, 1), (0xff, 0x40, 0x60, 0xa0)))
    assert img.getpixel((4, 4)) == want.getpixel((0, 0))


def test_onion_tint_a_custom_opaque_color(tmp_path):
    img = onion_png(tmp_path, "--tint-a", "#40a0ff")
    assert img.getpixel((4, 4)) == (0x40, 0xa0, 0xff, 255)
    assert img.getpixel((0, 0)) == pxart.rgba("#3a3a44")  # empty pixels stay backdrop


def test_onion_tint_a_leaves_b_drawn_over_it(tmp_path):
    tinted, plain = onion_png(tmp_path, "--tint-a", "#40a0ff"), onion_png(tmp_path, "--fade-a")
    assert tinted.getpixel((5, 0)) == plain.getpixel((5, 0))  # B's swing over no A: unchanged by the tint


def test_onion_tint_a_readout_unchanged(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWING)
    assert onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b") == onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b",
                                                                             "--tint-a")


def test_onion_tint_a_bad_color(tmp_path):
    p = write(tmp_path, "s.px", SWING)
    msg = run_err("onion", f"{p}:a", f"{p}:b", "-o", tmp_path / "o.png", "--tint-a", "reddish")
    assert "E_BAD_COLOR" in msg and "--tint-a" in msg


def test_help_documents_onion_bands_fade_and_edges():
    doc = " ".join(pxart.__doc__.split())
    assert "onion A B -o x.png [--scale 8] [--rows Y0-Y1 | --feet N] [--tint-a [COLOR] | --fade-a]" in doc
    assert "B at 80% opacity drawn over A as a flat silhouette in a translucent red (#ff4060a0)" in doc
    assert "The edges are the sides of each frame's opaque bounding box" in doc
    assert "limit the edges and the best shift to that band" in doc
    assert "--tint-a COLOR draws the silhouette in another color" in doc
    assert "--fade-a draws A itself at 35% opacity instead" in doc


# ---------------------------------------------------------------- sheet --fit: cells at their own size

def old_sheet(its, scale=8, cols=8, bg="#3a3a44", grid=False, rulers=False):
    """sheet as it was before --fit, for the byte-identical default."""
    from PIL import ImageDraw
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tiles = [(it, pxart.upscale(it.img, scale, grid, rulers)) for it in its]
    lw = max(max(pxart.text_w(probe, it.label), pxart.text_w(probe, f"{it.img.width}x{it.img.height} 99c"))
             for it in its)
    iw = max((it.img.width for it in its if it.img.height <= 22), default=0)
    cw = max(max(t.width for _, t in tiles), lw + iw + 8)
    ch = max(t.height for _, t in tiles)
    pad, lab = 10, 26
    cols = max(1, min(cols, len(tiles)))
    rows = (len(tiles) + cols - 1) // cols
    s = Image.new("RGBA", (pad + cols * (cw + pad), pad + rows * (ch + lab + pad)), (30, 30, 36, 255))
    d = ImageDraw.Draw(s)
    for n, (it, big) in enumerate(tiles):
        x, y = pad + (n % cols) * (cw + pad), pad + (n // cols) * (ch + lab + pad)
        d.rectangle([x, y, x + cw - 1, y + ch - 1], fill=pxart.rgba(bg))
        s.alpha_composite(big, (x + (cw - big.width) // 2, y + ch - big.height))
        if it.img.height <= lab - 4 and it.img.width <= cw - lw - 6:
            s.alpha_composite(it.img, (x + cw - it.img.width - 2, y + ch + 4))
        d.text((x, y + ch + 2), it.label, fill=(220, 220, 220, 255))
        d.text((x, y + ch + 13), f"{it.img.width}x{it.img.height} {pxart.n_colors(it, bg)}c", fill=(150, 150, 160, 255))
    return s


MIXED = ("k #000000\ng #00ff00\n@frame tile\n" + "g" * 4 + "\n" + ("gkkg\n" * 3) +
         "@frame beast\n" + ("k" * 12 + "\n") * 10 + "@frame dot\nk\n@frame wide\n" + "g" * 20 + "\n")


@pytest.mark.parametrize("cols, scale, grid", [(8, 8, False), (2, 4, True), (1, 1, False), (3, 2, False)])
def test_sheet_default_is_byte_identical(tmp_path, cols, scale, grid):
    p = write(tmp_path, "m.px", MIXED)
    argv = ["sheet", p, "-o", tmp_path / "s.png", "--cols", cols, "--scale", scale] + (["--grid"] if grid else [])
    assert run(*argv) == 0
    want = old_sheet(pxart.all_items([str(p)]), scale, cols, grid=grid)
    assert Image.open(tmp_path / "s.png").convert("RGBA").tobytes() == want.tobytes()


def fit_sheet(tmp_path, *more, text=MIXED):
    p = write(tmp_path, "m.px", text)
    assert run("sheet", p, "-o", tmp_path / "s.png", "--fit", *more) == 0
    return Image.open(tmp_path / "s.png").convert("RGBA")


def test_sheet_fit_is_smaller_than_max_cells(tmp_path):
    p = write(tmp_path, "m.px", MIXED)
    assert run("sheet", p, "-o", tmp_path / "a.png") == 0
    big = Image.open(tmp_path / "a.png")
    small = fit_sheet(tmp_path)
    assert small.width < big.width and small.height == big.height  # one row: its tallest frame, the beast


def test_sheet_fit_cells_are_their_own_width(tmp_path):
    from PIL import ImageDraw
    img = fit_sheet(tmp_path, "--scale", "4", "--cols", "4")
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    its = pxart.all_items([str(tmp_path / "m.px")])
    lws = [max(pxart.text_w(probe, it.label), pxart.text_w(probe, f"{it.img.width}x{it.img.height} 99c")) for it in its]
    cws = [max(it.img.width * 4, l + (it.img.width if it.img.height <= 22 else 0) + 8) for it, l in zip(its, lws)]
    assert img.width == 10 + sum(w + 10 for w in cws)
    assert img.height == 10 + 40 + 26 + 10  # the beast is 10 tall at scale 4


def test_sheet_fit_rows_are_as_tall_as_their_tallest(tmp_path):
    img = fit_sheet(tmp_path, "--scale", "4", "--cols", "2")
    # row 1: tile (4 tall) and beast (10): 40; row 2: dot (1) and wide (1): 4
    assert img.height == 10 + (40 + 26 + 10) + (4 + 26 + 10)


def test_sheet_fit_frames_bottom_aligned_in_their_row(tmp_path):
    img = fit_sheet(tmp_path, "--scale", "1", "--cols", "4")
    bg, fill = pxart.rgba("#3a3a44"), (0, 255, 0, 255)
    # tile is 4x4 in a 10-tall row: rows 0-5 of its cell are backdrop, its top row (all g) is at y 10+6.
    from PIL import ImageDraw
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    cw = max(4, max(pxart.text_w(probe, "tile"), pxart.text_w(probe, "4x4 99c")) + 4 + 8)
    x0 = 10 + (cw - 4) // 2  # centered across its cell
    assert img.getpixel((10, 10)) == bg
    col = [img.getpixel((x0, 10 + y)) for y in range(10)]
    assert col[:6] == [bg] * 6 and col[6] == fill


def test_sheet_fit_one_cell_a_row_is_each_frames_width(tmp_path):
    img = fit_sheet(tmp_path, "--scale", "8", "--cols", "1")
    assert img.height == 10 + sum(h * 8 + 26 + 10 for h in (4, 10, 1, 1))


def test_sheet_fit_one_frame_is_the_default(tmp_path):
    p = write(tmp_path, "one.px", "k #000000\n\nkk\n")
    assert run("sheet", p, "-o", tmp_path / "a.png") == 0
    assert run("sheet", p, "-o", tmp_path / "b.png", "--fit") == 0
    assert Image.open(tmp_path / "a.png").tobytes() == Image.open(tmp_path / "b.png").tobytes()


def test_sheet_fit_keeps_labels_and_1x_copy(tmp_path):
    img = fit_sheet(tmp_path, "--scale", "4", "--cols", "4")
    # the 1x copy of 'tile' (4x4, under 22 tall) sits right of its label, below the cell.
    x_tile = 10
    from PIL import ImageDraw
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lw = max(pxart.text_w(probe, "tile"), pxart.text_w(probe, "4x4 99c"))
    cw = max(16, lw + 4 + 8)
    y = 10 + 40 + 4
    assert img.getpixel((x_tile + cw - 4 - 2, y)) == (0, 255, 0, 255)


def test_sheet_fit_mixed_files_and_pngs(tmp_path):
    p = write(tmp_path, "m.px", MIXED)
    Image.new("RGBA", (30, 2), (9, 9, 9, 255)).save(tmp_path / "x.png")
    assert run("sheet", p, tmp_path / "x.png", "-o", tmp_path / "s.png", "--fit", "--scale", "1") == 0
    assert Image.open(tmp_path / "s.png").height == 10 + 10 + 26 + 10


def test_help_documents_sheet_fit():
    doc = " ".join(pxart.__doc__.split())
    assert "[--bg #3a3a44] [--fit]" in doc
    assert "--fit makes each cell its own frame's width (or its label's, if wider)" in doc


# ---------------------------------------------------------------- compose --used-keys-only

CLOAK = "X #1a1020\nx #302040\nc #504070\nC #7060a0\nw #a090d0\nk #000000\n@variant night\nc #202040\nC #303050\n" \
        "@frame cloak\n.cc.\ncccc\n.kk.\n"


def test_compose_new_out_keeps_whole_palette_by_default(tmp_path, capsys):
    p = write(tmp_path, "c.px", CLOAK)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:cloak@0,0") == 0
    assert list(pxart.parse(out).palette) == ["c", "k", "X", "x", "C", "w"]
    capsys.readouterr()
    assert run("check", out) == 0 and "unused keys XxCw" in capsys.readouterr().out
    assert run("shade", out, "--ramp", "XxcCw", "--keys", "c") == 0  # why it's the default


def test_compose_used_keys_only_new_out(tmp_path, capsys):
    p = write(tmp_path, "c.px", CLOAK)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:cloak@0,0", "--used-keys-only") == 0
    doc = pxart.parse(out)
    assert list(doc.palette) == ["c", "k"] and doc.variants == {"night": {"c": pxart.hex2rgba("#202040")}}
    capsys.readouterr()
    assert run("check", out) == 0 and "unused" not in capsys.readouterr().out


def test_compose_used_keys_only_renders_the_same(tmp_path):
    p = write(tmp_path, "c.px", CLOAK)
    a, b = tmp_path / "a.px", tmp_path / "b.px"
    assert run("compose", "-o", a, f"{p}:cloak@0,0") == 0
    assert run("compose", "-o", b, f"{p}:cloak@0,0", "--used-keys-only") == 0
    assert renders(a) == renders(b)


def test_compose_used_keys_only_then_shade_ramp_needs_the_keys(tmp_path):
    p = write(tmp_path, "c.px", CLOAK)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:cloak@0,0", "--used-keys-only") == 0
    assert run("shade", out, "--ramp", "XxcCw", "--keys", "c") != 0


def test_compose_used_keys_only_keeps_a_shared_import(tmp_path):
    write(tmp_path, "pal.px", "X #1a1020\nc #504070\nC #7060a0\n")
    p = write(tmp_path, "c.px", "@palette pal.px\nz #ffffff\n@frame a\ncz\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:a@0,0", "--used-keys-only") == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == ["pal.px"] and list(doc.palette) == ["z"]


def test_compose_used_keys_only_several_layers_no_left_out_notes(tmp_path, capsys):
    a = write(tmp_path, "a.px", "h #111111\nn #222222\nq #999999\n\nh\n")
    b = write(tmp_path, "b.px", "h #111111\nn #bbbbbb\nw #333333\n\nw\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}@0,0", f"{b}@1,0", "--used-keys-only") == 0
    got = capsys.readouterr().out
    assert "leaves out" not in got and list(pxart.parse(out).palette) == ["h", "w"]


def test_compose_default_several_layers_notes_left_out_as_before(tmp_path, capsys):
    a = write(tmp_path, "a.px", "h #111111\nn #222222\n\nh\n")
    b = write(tmp_path, "b.px", "h #111111\nn #bbbbbb\nw #333333\n\nw\n")
    assert run("compose", "-o", tmp_path / "o.px", "--size", "2x1", f"{a}@0,0", f"{b}@1,0") == 0
    assert "leaves out" in capsys.readouterr().out


def test_compose_used_keys_only_existing_out_is_the_plain_compose(tmp_path):
    p = write(tmp_path, "c.px", CLOAK)
    o1 = write(tmp_path, "o1.px", "k #000000\n@frame x\nk\n")
    o2 = write(tmp_path, "o2.px", "k #000000\n@frame x\nk\n")
    assert run("compose", "-o", f"{o1}:y", f"{p}:cloak@0,0") == 0
    assert run("compose", "-o", f"{o2}:y", f"{p}:cloak@0,0", "--used-keys-only") == 0
    assert o1.read_text() == o2.read_text() and list(pxart.parse(o1).palette) == ["k", "c"]


def test_compose_used_keys_only_with_rekey(tmp_path):
    a = write(tmp_path, "a.px", "s #111111\nq #999999\n\ns\n")
    b = write(tmp_path, "b.px", "s #00ff00\nr #888888\n\ns\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}@0,0", f"{b}@1,0", "--used-keys-only", "--rekey") == 0
    doc = pxart.parse(out)
    assert doc.frames[0].grid == ["sa"] and list(doc.palette) == ["s", "a"]


def test_crop_used_keys_only(tmp_path):
    p = write(tmp_path, "c.px", CLOAK)
    out = tmp_path / "o.px"
    assert run("crop", f"{p}:cloak", "0,2,4,1", "-o", out, "--used-keys-only") == 0
    assert list(pxart.parse(out).palette) == ["k"]


def test_help_documents_used_keys_only():
    doc = " ".join(pxart.__doc__.split())
    assert "--used-keys-only gives a new OUT only the keys its frame uses" in doc
    assert "It isn't the default because the unused keys are often a material's ramp" in doc


def test_compose_used_keys_only_drops_keys_cropped_off_the_canvas(tmp_path):
    p = write(tmp_path, "c.px", CLOAK)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "4x2", f"{p}:cloak@0,0", "--used-keys-only") == 0
    doc = pxart.parse(out)
    assert list(doc.palette) == ["c"] and doc.frames[0].grid == [".cc.", "cccc"]


def test_compose_used_keys_only_drops_an_empty_variant_key_set_but_keeps_the_variant(tmp_path):
    p = write(tmp_path, "c.px", CLOAK)
    out = tmp_path / "o.px"
    assert run("crop", f"{p}:cloak", "0,2,4,1", "-o", out, "--used-keys-only") == 0
    doc = pxart.parse(out)
    assert doc.variants == {"night": {}}
    assert doc.image(doc.frames[0], "night").getpixel((1, 0)) == pxart.hex2rgba("#000000")


# ---------------------------------------------------------------- crop -h: the full story

def test_crop_help_has_the_full_story(capsys):
    out = " ".join(cmd_help(capsys, "crop").split())
    assert "crop FILE:frame x,y,w,h -o OUT[:frame] [--rekey [KEYS]] [--used-keys-only]" in out
    assert "'crop hero.px:idle/0 4,0,8,8 -o parts.px:head'" in out
    assert "a rectangle that runs past the frame's edge (or starts at a negative x,y) gets '.' there" in out
    assert "a new OUT starts with FILE's whole palette (so shade ramps still find their keys)" in out
    assert "OUT:frame of an existing OUT adds that frame" in out and "or replaces it when it exists" in out
    assert "A plain OUT with one unnamed grid has the grid replaced" in out
    assert "A key the cut uses that OUT has in another color is E_KEY_CONFLICT" in out
    assert "--rekey gives the cut those keys in OUT and leaves FILE as it is" in out
    assert "See also, in pxart help all: compose (" in out


def test_crop_help_claims_hold(tmp_path):
    # Each behaviour crop -h describes, run.
    src = write(tmp_path, "c.px", "k #000000\ng #00ff00\n@frame a\nkg\ngk\n")
    assert run("crop", f"{src}:a", "1,1,3,2", "-o", tmp_path / "past.px") == 0
    assert pxart.parse(tmp_path / "past.px").frames[0].grid == ["k..", "..."]
    assert run("crop", f"{src}:a", "-1,0,2,1", "-o", tmp_path / "neg.px") == 0
    assert pxart.parse(tmp_path / "neg.px").frames[0].grid == [".k"]
    u = write(tmp_path, "u.px", "k #000000\n\nk\n")
    assert run("crop", f"{src}:a", "0,0,2,1", "-o", u) == 0
    assert pxart.parse(u).implicit and pxart.parse(u).frames[0].grid == ["kg"]
    n = write(tmp_path, "n.px", "k #000000\n@frame x\nk\n")
    assert "E_SELECT" in run_err("crop", f"{src}:a", "0,0,1,1", "-o", n)
    assert run("crop", f"{src}:a", "0,0,1,1", "-o", f"{n}:x") == 0 and pxart.parse(n).get("x").grid == ["k"]
    u2 = write(tmp_path, "u2.px", "k #000000\n\nk\n")
    assert run("crop", f"{src}:a", "0,0,2,1", "-o", f"{u2}:y") == 0
    assert [f.id for f in pxart.parse(u2).frames] == ["u2", "y"]


def test_crop_takes_a_negative_rectangle_without_dashes(tmp_path):
    src = write(tmp_path, "c.px", "k #000000\n@frame a\nkk\n")
    assert run("crop", f"{src}:a", "-2,-1,3,2", "-o", tmp_path / "o.px") == 0
    assert pxart.parse(tmp_path / "o.px").frames[0].grid == ["...", "..k"]


def test_tint_help_stands_alone(capsys):
    out = cmd_help(capsys, "tint")
    assert "scene --tint on a PNG (a rendered scene): lays the color, at its alpha, over every" in out
    assert "scene (--tint, items, maps)" in see_also(out) and "The same on a PNG" not in out


def test_rotate_help_still_pastes_transposes_shared_paragraph(capsys):
    out = cmd_help(capsys, "rotate")
    assert "transpose (from pxart help all):" in out and "For deriving path edges and corners" in out


def test_command_help_is_much_shorter_than_before(capsys):
    # crop -h was 86 lines with EDITING, FORMAT and compose pasted in.
    assert len(cmd_help(capsys, "crop").splitlines()) < 50
    assert len(cmd_help(capsys, "line").splitlines()) < 30


# ---------------------------------------------------------------- anim: a walk frame whose legs stay put reads as its bob

# A walk: 0 legs together, 1 the body dips with the legs where they were (the keeper's walk/down/1), 2 the legs step.
# The legs move in the animation, so frame 1's still legs are a bob, not an idle's breath.
DIP_WALK = ([EMPTY] + BODY + LEGS, BODY + [BODY[-1]] + LEGS, BODY + LEGS_WIDE + [EMPTY])
GLOW = [r.replace("k", "y").replace("b", "y").replace("s", "y") for r in IDLE_4[1]]  # the breath's top, recolored whole
SHADOW_BIG, SHADOW_SMALL = "..kkkkkk..", "...kkkk..."


def test_dip_walk_fixture():
    assert all(len(f) == 14 and all(len(r) == 10 for r in f) for f in DIP_WALK)
    assert DIP_WALK[0][10:] == DIP_WALK[1][10:] == LEGS and DIP_WALK[2][10:] != LEGS


def test_dip_walk_frame_passes_the_single_frame_rule(tmp_path):
    # On its own (motion, no animation around it) the dip looks like a breath: that is what hid the bob.
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, DIP_WALK[0], DIP_WALK[1])
    assert (dx, dy) == (0, -1) and still == 9 and n_shift < n_none


def test_dip_walk_legs_move_in_the_animation(tmp_path):
    doc = pxart.parse(anim_file(tmp_path, *DIP_WALK, name="dw.px"))
    imgs = [doc.image(f) for f in doc.frames]
    assert pxart.still_rows(imgs) is None and pxart.still_rows(imgs, shape=True) is None


def test_dip_walk_frame_reads_as_its_bob(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *DIP_WALK)
    _, _, n_shift, n_none, _ = motion_of(tmp_path, DIP_WALK[0], DIP_WALK[1])
    assert lines[1].endswith(f"vs idle/0: shift +0,-1 then {pc(n_shift, DIP_WALK[1])} (no shift: {n_none}px)")


def test_dip_walk_no_frame_says_rows_still(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *DIP_WALK)
    assert len(lines) == 3 and not any("still" in l or "no shift then" in l for l in lines), lines


def test_dip_walk_headline_is_the_smaller_number(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *DIP_WALK)
    _, _, n_shift, n_none, _ = motion_of(tmp_path, DIP_WALK[0], DIP_WALK[1])
    head = lines[1].split(": ", 1)[1]
    assert head.startswith(f"shift +0,-1 then {n_shift}px") and n_shift < n_none


def test_dip_walk_other_frames_as_before(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *DIP_WALK)
    for i, (a, b) in ((0, (DIP_WALK[2], DIP_WALK[0])), (2, (DIP_WALK[1], DIP_WALK[2]))):
        dx, dy, n_shift, n_none, _ = motion_of(tmp_path, a, b)
        assert f"shift {dx:+d},{dy:+d} then {pc(n_shift, b)}" in lines[i], lines[i]


def test_dip_walk_strip_lights_the_still_legs(tmp_path, capsys):
    # The strip shows what the bob leaves changed: the legs that stayed put while the body dipped.
    anim_lines(tmp_path, capsys, *DIP_WALK)
    assert magenta_rows(tmp_path, 1) & {10, 11, 12, 13}


def test_dip_walk_order_does_not_matter(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, DIP_WALK[2], DIP_WALK[0], DIP_WALK[1])
    assert not any("still" in l for l in lines), lines


def test_dip_without_the_step_is_an_idle(tmp_path, capsys):
    # The same two frames without the stepping one: the legs never move, so the breath reading stays.
    lines = anim_lines(tmp_path, capsys, DIP_WALK[0], DIP_WALK[1])
    assert all("(rows 9+ still;" in l for l in lines), lines


def test_breath_idle_unchanged_by_the_walk_rule(tmp_path, capsys):
    lines = anim_lines(tmp_path, capsys, *IDLE_4)
    assert sum("(rows 9+ still;" in l for l in lines) == 2


def test_still_rows_shape_ignores_color():
    imgs = [Image.new("RGBA", (2, 3)) for _ in range(2)]
    imgs[0].putpixel((0, 2), (9, 9, 9, 255))
    imgs[1].putpixel((0, 2), (200, 9, 9, 255))  # same pixel, another color
    assert pxart.still_rows(imgs) is None and pxart.still_rows(imgs, shape=True) == 0  # the empty rows above too


def test_still_rows_shape_sees_a_moved_pixel():
    imgs = [Image.new("RGBA", (2, 3)) for _ in range(2)]
    imgs[0].putpixel((0, 2), (9, 9, 9, 255))
    imgs[1].putpixel((1, 2), (9, 9, 9, 255))
    assert pxart.still_rows(imgs, shape=True) is None


def test_still_rows_shape_same_as_exact_for_identical_frames():
    imgs = [Image.new("RGBA", (2, 3)) for _ in range(3)]
    for im in imgs:
        im.putpixel((1, 1), (5, 5, 5, 255))
    assert pxart.still_rows(imgs, shape=True) == pxart.still_rows(imgs) == 0


def test_glow_frame_is_not_the_legs_moving(tmp_path, capsys):
    # An idle with a frame recolored whole (a flash): the legs keep their shape, so the breath still reads still.
    lines = anim_lines(tmp_path, capsys, IDLE_4[0], IDLE_4[1], GLOW)
    assert "(rows 9+ still;" in lines[1], lines


def test_glow_fixture_same_shape_as_the_breath():
    assert [[c != "." for c in r] for r in GLOW] == [[c != "." for c in r] for r in IDLE_4[1]] and GLOW != IDLE_4[1]


def test_bob_over_a_shadow_that_changes_shape_keeps_its_shift(tmp_path, capsys):
    # A floating drop bobbing over its shadow; the shadow shrinks at the top of the bob, so the rows under the drop
    # aren't still in the animation, and the dip's frame reads as a shift.
    low, high = [EMPTY] + BODY + [EMPTY, SHADOW_BIG, EMPTY], BODY + [EMPTY, EMPTY, SHADOW_BIG, EMPTY]
    top = BODY + [EMPTY, EMPTY, SHADOW_SMALL, EMPTY]
    lines = anim_lines(tmp_path, capsys, low, high, top)
    assert not any("still" in l for l in lines), lines
    assert lines[1].split(": ", 1)[1].startswith("shift +0,-1 then ")


def test_bob_over_a_steady_shadow_still_reads_still(tmp_path, capsys):
    # The same drop over a shadow that never changes: rows still in every frame, as before.
    low, high = [EMPTY] + BODY + [EMPTY, SHADOW_BIG, EMPTY], BODY + [EMPTY, EMPTY, SHADOW_BIG, EMPTY]
    lines = anim_lines(tmp_path, capsys, low, high)
    assert all("(rows 10+ still;" in l for l in lines), lines


def test_help_documents_the_walk_rule():
    doc = " ".join(pxart.__doc__.split())
    assert "whose legs keep their shape in every frame of the animation" in doc
    assert "a frame whose legs happen to stay put is the body's bob" in doc
    assert "A frame recolored whole (a glow) doesn't count as the legs moving" in doc


def test_readme_documents_the_walk_rule():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "a walk frame whose legs happen to stay put reads as its bob" in readme


# ---------------------------------------------------------------- onion: two different sprites get their edges only

KEEPER_ISH = "k #000000\ny #ffff00\n@frame a\n.kk.\nkyyk\nkyyk\n.kk.\n"
KID_ISH = "k #000000\ns #ff8080\n@frame a\ns..s\n.ss.\n.ss.\ns..s\n"   # same 4x4 size, nearly every pixel different
TALL = "k #000000\n@anim w ms=100\n@frame w/0\n.k.\nkkk\nk.k\n@frame w/1\n.k.\n.k.\nkkk\nk.k\n@frame x\n.k.\nkkk\nk.k\nk.k\n"


def test_onion_different_characters_same_size_edges_only(tmp_path, capsys):
    a, b = write(tmp_path, "keeper.px", KEEPER_ISH), write(tmp_path, "kid.px", KID_ISH)
    lines = onion_lines(tmp_path, capsys, f"{a}:a", f"{b}:a")
    assert lines[2] == "B vs A: left +0, right +0, top +0, bottom +0; different sprites: edges only"
    assert "best shift" not in "\n".join(lines)


def test_onion_different_characters_band_edges_only_too(tmp_path, capsys):
    # The band doesn't make them one sprite: the whole sprites decide.
    a, b = write(tmp_path, "keeper.px", KEEPER_ISH), write(tmp_path, "kid.px", KID_ISH)
    lines = onion_lines(tmp_path, capsys, f"{a}:a", f"{b}:a", "--feet", "1")
    assert lines[2] == "B vs A (row 3): left -1, right +1, top +0, bottom +0; different sprites: edges only"


def test_onion_different_sizes_different_files_edges_only(tmp_path, capsys):
    a = write(tmp_path, "keeper.px", KEEPER_ISH)
    b = write(tmp_path, "small.px", "k #000000\ny #ffff00\n@frame a\n.kk.\nkyyk\n.kk.\n")  # 4x3: nearly the same art
    lines = onion_lines(tmp_path, capsys, f"{a}:a", f"{b}:a")
    assert lines[2].endswith("; different sprites: edges only") and lines[2].startswith("B vs A: left +0, right +0, ")


def test_onion_different_sizes_one_animation_keeps_the_best_shift(tmp_path, capsys):
    # Frames of one animation may differ in size (an attack frame): still one sprite.
    p = write(tmp_path, "t.px", TALL)
    lines = onion_lines(tmp_path, capsys, f"{p}:w/0", f"{p}:w/1")
    assert "; best shift " in lines[2] and "different sprites" not in lines[2]


def test_onion_different_sizes_other_group_of_one_file_edges_only(tmp_path, capsys):
    p = write(tmp_path, "t.px", TALL)
    lines = onion_lines(tmp_path, capsys, f"{p}:w/0", f"{p}:x")
    assert lines[2].endswith("; different sprites: edges only")


def test_onion_same_size_similar_frames_keep_the_best_shift(tmp_path, capsys):
    p = write(tmp_path, "b.px", BOB)
    lines = onion_lines(tmp_path, capsys, f"{p}:w/0", f"{p}:w/1")
    assert lines[2].endswith("; best shift +0,+1 then 3px changed (no shift: 5px)")


def test_onion_exactly_half_changed_is_still_one_sprite(tmp_path, capsys):
    # 2 of 4 opaque pixels changed at the best shift: not more than half.
    p = write(tmp_path, "h.px", "k #000000\nr #ff0000\n@frame a\nkk\nkk\n@frame b\nkr\nrk\n")
    lines = onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b")
    assert lines[2] == "B vs A: left +0, right +0, top +0, bottom +0; best shift +0,+0 then 2px changed (no shift: 2px)"


def test_onion_more_than_half_changed_is_two_sprites(tmp_path, capsys):
    p = write(tmp_path, "h.px", "k #000000\nr #ff0000\n@frame a\nkk\nkk\n@frame b\nkr\nrr\n")
    lines = onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b")
    assert lines[2] == "B vs A: left +0, right +0, top +0, bottom +0; different sprites: edges only"


def test_onion_different_sprites_png_image_unchanged(tmp_path, capsys):
    # Only the readout changes: the picture is drawn as always.
    a, b = write(tmp_path, "keeper.px", KEEPER_ISH), write(tmp_path, "kid.px", KID_ISH)
    onion_lines(tmp_path, capsys, f"{a}:a", f"{b}:a")
    img = Image.open(tmp_path / "o.png")
    assert img.size == (4 * 8 + 16, 4 * 8 + 16)


def test_onion_pngs_of_two_sizes_are_two_sprites(tmp_path, capsys):
    Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(tmp_path / "a.png")
    Image.new("RGBA", (2, 1), (1, 2, 3, 255)).save(tmp_path / "b.png")
    lines = onion_lines(tmp_path, capsys, tmp_path / "a.png", tmp_path / "b.png")
    assert lines[2] == "B vs A: left +0, right +0, top +1, bottom +0; different sprites: edges only"


def test_onion_one_png_against_itself_keeps_the_shift(tmp_path, capsys):
    Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(tmp_path / "a.png")
    lines = onion_lines(tmp_path, capsys, tmp_path / "a.png", tmp_path / "a.png")
    assert lines[2].endswith("best shift +0,+0 then 0px changed (no shift: 0px)")


def test_help_documents_onion_different_sprites():
    doc = " ".join(pxart.__doc__.split())
    assert "different sprites: edges only" in doc and "two frames of one animation in one file are always one sprite" in doc
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`different sprites: edges only`" in readme


# ---------------------------------------------------------------- palette FILE: a variant's same-color relists

LAMP_NIGHT = ("k #2a1f33\nw #f6f1e4\nl #fff4b0\ng #ffc861\n"
              "# night: lamp colors (l, g) stay lit\n@variant night\nk #120e22\nw #9fb0d4\nl #fff4b0\ng #ffc861\n")


def test_palette_variant_relists_unchanged_apart_from_recolors(tmp_path, capsys):
    p = write(tmp_path, "pal.px", LAMP_NIGHT)
    assert run("palette", p) == 0
    assert capsys.readouterr().out.splitlines()[-2:] == [
        "  night: recolors (darker) k w; relists unchanged: l g; inherits: nothing",
        "    # night: lamp colors (l, g) stay lit"]


def test_palette_variant_without_relists_has_no_relists_part(tmp_path, capsys):
    p = write(tmp_path, "s.px", "a #000000\nb #111111\n@variant v\na #ffffff\n@frame f\nab\n")
    assert run("palette", p) == 0
    line = capsys.readouterr().out.splitlines()[-1]
    assert line == "  v: brightens a; inherits: b" and "relists" not in line


def test_palette_variant_that_only_relists(tmp_path, capsys):
    p = write(tmp_path, "s.px", "a #000000\nb #111111\n@variant v\na #000000\n@frame f\nab\n")
    assert run("palette", p) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "  v: recolors nothing; relists unchanged: a; inherits: b"


def test_palette_relists_compare_with_the_rendered_base(tmp_path, capsys):
    # An imported variant lists a in the import's base color, but the file overrides a locally: that recolors.
    write(tmp_path, "base.px", "a #000000\nb #111111\n@variant dusk\na #000000\nb #111111\n")
    p = write(tmp_path, "s.px", "@palette base.px\na #ff0000\n@frame f\nab\n")
    assert run("palette", p) == 0
    assert capsys.readouterr().out.splitlines()[-1] == ("  dusk: recolors (darker) a; relists unchanged: b; inherits: "
                                                         "nothing")


def test_palette_relists_in_an_imported_variant(tmp_path, capsys):
    write(tmp_path, "pal.px", LAMP_NIGHT)
    p = write(tmp_path, "s.px", "@palette pal.px\n@frame f\nkwlg\n")
    assert run("palette", p) == 0
    assert "  night: recolors (darker) k w; relists unchanged: l g; inherits: nothing" \
        in capsys.readouterr().out.splitlines()


def test_palette_relists_in_palette_order(tmp_path, capsys):
    p = write(tmp_path, "s.px", "a #000000\nb #111111\nc #222222\n@variant v\nc #222222\na #000000\nb #ffffff\n"
                                "@frame f\nabc\n")
    assert run("palette", p) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "  v: brightens b; relists unchanged: a c; inherits: nothing"


def test_palette_relists_a_translucent_color_exactly(tmp_path, capsys):
    # Same rgb, other alpha: a recolor, not a relist (black either way: as bright).
    p = write(tmp_path, "s.px", "a #00000080\n@variant v\na #000000\n@frame f\na\n")
    assert run("palette", p) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "  v: recolors (as bright) a; inherits: nothing"


def test_palette_relists_transparent_key(tmp_path, capsys):
    p = write(tmp_path, "s.px", "a #000000\nt transparent\n@variant v\nt transparent\n@frame f\nat\n")
    assert run("palette", p) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "  v: recolors nothing; relists unchanged: t; inherits: a"


def test_help_documents_relists():
    doc = " ".join(pxart.__doc__.split())
    assert "'night: recolors (darker) k w; relists unchanged: l g; inherits: nothing'" in doc
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`night: recolors (darker) k w; brightens y; relists unchanged: l g; inherits: e E q`" in readme


# ---------------------------------------------------------------- check / sheet / stats DIR; palette files in sheet

def pack_dir(tmp_path):
    """A pack folder: a palette file, two sprites (one in a subfolder), a map, and a PNG render."""
    d = tmp_path / "pack"
    (d / "rooms").mkdir(parents=True)
    write(d, "palette.px", "# pack palette\nk #000000\ny #ffff00\n@variant night\ny #202000\n")
    write(d, "hero.px", "@palette palette.px\n@frame idle\nky\n")
    write(d / "rooms", "hall.px", "@palette ../palette.px\n@frame floor\nkk\nyy\n")
    write(d, "room.map", "h hero.px:idle\n\nh.\n")
    Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(d / "_render.png")
    return d


def test_in_dirs_expands_sorted_by_path(tmp_path):
    d = pack_dir(tmp_path)
    assert pxart.in_dirs([str(d)]) == [str(d / "hero.px"), str(d / "palette.px"), str(d / "rooms" / "hall.px")]


def test_in_dirs_with_maps(tmp_path):
    d = pack_dir(tmp_path)
    assert pxart.in_dirs([str(d)], (".px", ".map")) == [str(d / "hero.px"), str(d / "palette.px"),
                                                        str(d / "room.map"), str(d / "rooms" / "hall.px")]


def test_in_dirs_keeps_files_and_order(tmp_path):
    d = pack_dir(tmp_path)
    got = pxart.in_dirs([str(d / "rooms" / "hall.px"), str(d / "rooms"), "x.px:a"])
    assert got == [str(d / "rooms" / "hall.px"), str(d / "rooms" / "hall.px"), "x.px:a"]


def test_in_dirs_empty_directory_is_e_file(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(pxart.PxError) as e:
        pxart.in_dirs([str(tmp_path / "empty")])
    assert codes(e) == ["E_FILE"] and "no *.px files under it" in str(e.value.issues[0])


def test_check_dir_checks_every_px_and_map(tmp_path, capsys):
    d = pack_dir(tmp_path)
    assert run("check", d) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == f"ok   {d / 'hero.px'}:idle: 2x1 2c"
    assert out[1] == f"ok   {d / 'palette.px'}: palette file, 2 key(s), variants night"
    assert out[2].startswith(f"ok   {d / 'room.map'}")
    assert out[3] == f"ok   {d / 'rooms' / 'hall.px'}:floor: 2x2 2c"
    assert out[4] == "4 files, 2 frames, 0 warnings" and len(out) == 5


def test_check_dir_is_no_longer_a_directory_error(tmp_path, capsys):
    d = pack_dir(tmp_path)
    run("check", d)
    out = capsys.readouterr()
    assert "Is a directory" not in out.out + out.err


def test_check_dir_fails_on_a_broken_file_inside(tmp_path, capsys):
    d = pack_dir(tmp_path)
    write(d / "rooms", "bad.px", "k #000000\nkk\nk\n")
    assert run("check", d) == 1
    out = capsys.readouterr().out
    assert f"FAIL {d / 'rooms' / 'bad.px'}: 1 error(s)" in out and "E_ROW_WIDTH" in out


def test_check_dir_and_file_checked_once(tmp_path, capsys):
    d = pack_dir(tmp_path)
    run("check", d / "hero.px", d)
    out = capsys.readouterr().out
    assert out.count(f"{d / 'hero.px'}:idle: 2x1") == 1


def test_check_empty_dir_is_e_file(tmp_path):
    (tmp_path / "e").mkdir()
    msg = run_err("check", tmp_path / "e")
    assert msg.startswith("check: E_FILE: ") and "no *.px or *.map files under it" in msg


def test_sheet_dir_skips_the_palette_file_with_a_note(tmp_path, capsys):
    d = pack_dir(tmp_path)
    assert run("sheet", d, "-o", tmp_path / "s.png", "--scale", "1") == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [f"note: sheet skips {d / 'palette.px'}: a palette file, no frames", f"wrote {tmp_path / 's.png'}"]


def test_sheet_dir_same_as_listing_the_files(tmp_path, capsys):
    d = pack_dir(tmp_path)
    run("sheet", d, "-o", tmp_path / "a.png")
    run("sheet", d / "hero.px", d / "rooms" / "hall.px", "-o", tmp_path / "b.png")
    a, b = (Image.open(tmp_path / n).convert("RGBA") for n in ("a.png", "b.png"))
    assert a.size == b.size and a.tobytes() == b.tobytes()


def test_sheet_dir_leaves_pngs_out(tmp_path, capsys):
    d = pack_dir(tmp_path)
    run("sheet", d, "-o", d / "_sheet.png")
    run("sheet", d, "-o", tmp_path / "again.png")  # the sheet rendered into the folder isn't picked up
    a, b = (Image.open(p).convert("RGBA") for p in (d / "_sheet.png", tmp_path / "again.png"))
    assert a.tobytes() == b.tobytes()


def test_sheet_palette_file_among_files_skipped(tmp_path, capsys):
    d = pack_dir(tmp_path)
    assert run("sheet", d / "palette.px", d / "hero.px", "-o", tmp_path / "s.png") == 0
    assert capsys.readouterr().out.splitlines()[0] == f"note: sheet skips {d / 'palette.px'}: a palette file, no frames"


def test_sheet_palette_file_alone_is_still_e_no_frames(tmp_path):
    d = pack_dir(tmp_path)
    msg = run_err("sheet", d / "palette.px", "-o", tmp_path / "s.png")
    assert "E_NO_FRAMES" in msg and not (tmp_path / "s.png").exists()


def test_sheet_two_palette_files_alone_still_error(tmp_path):
    d = pack_dir(tmp_path)
    write(d, "other.px", "q #123456\n")
    assert "E_NO_FRAMES" in run_err("sheet", d / "palette.px", d / "other.px", "-o", tmp_path / "s.png")


def test_sheet_dir_of_only_a_palette_file_is_e_no_frames(tmp_path):
    (tmp_path / "p").mkdir()
    write(tmp_path / "p", "palette.px", "k #000000\n")
    assert "E_NO_FRAMES" in run_err("sheet", tmp_path / "p", "-o", tmp_path / "s.png")


def test_sheet_broken_palette_file_is_an_error_not_skipped(tmp_path):
    # A palette file with an error has no clean parse as one: it is read as a sprite and fails loudly.
    d = pack_dir(tmp_path)
    write(d, "bad.px", "k #zzzzzz\n")
    msg = run_err("sheet", d, "-o", tmp_path / "s.png")
    assert "E_BAD_COLOR" in msg


def test_sheet_palette_file_with_a_selector_is_not_skipped(tmp_path):
    # FILE:SEL asks for frames: an error, not a skip.
    d = pack_dir(tmp_path)
    assert "E_NO_FRAMES" in run_err("sheet", f"{d / 'palette.px'}:idle", d / "hero.px", "-o", tmp_path / "s.png")


def test_stats_dir(tmp_path, capsys):
    d = pack_dir(tmp_path)
    assert run("stats", d) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == f"note: stats skips {d / 'palette.px'}: a palette file, no frames"
    assert out[1].startswith(f"{d / 'hero.px'}:idle: 2x1 ") and out[2].startswith(f"{d / 'rooms' / 'hall.px'}:floor: 2x2 ")
    assert len(out) == 3


def test_stats_palette_file_alone_still_errors(tmp_path):
    d = pack_dir(tmp_path)
    assert "E_NO_FRAMES" in run_err("stats", d / "palette.px")


def test_render_dir_is_still_a_file_error(tmp_path):
    # Only check, sheet and stats take directories.
    d = pack_dir(tmp_path)
    assert "E_FILE" in run_err("render", d, "-o", tmp_path / "r.png")


def test_help_documents_directories_and_palette_files(capsys):
    doc = " ".join(pxart.__doc__.split())
    assert "check FILE|DIR..." in doc and "A directory checks every .px and .map under it, recursively, sorted by path" in doc
    assert "sheet FILE|DIR..." in doc and "A directory stands for every .px under it, recursively, sorted by path" in doc
    assert "'note: sheet skips palette.px: a palette file, no frames'); given alone it is E_NO_FRAMES" in doc
    assert "stats FILE|DIR..." in doc
    for cmd in ("check", "sheet"):
        out = " ".join(cmd_help(capsys, cmd).split())
        assert "directory" in out and "palette file" in out, cmd
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`check crossover/` checks every `.px` and `.map` under it" in readme
    assert "a directory stands for every `.px` under it, sorted by path, and palette files are skipped" in readme


# ---------------------------------------------------------------- palette --variant NAME --add / --keep, --hoist

def looks(doc):
    """Every frame's pixels in the base palette and every variant: what an edit that 'renders as before' keeps."""
    names = [None] + sorted(set(doc.variants) | set(doc.shared_variants))
    return {(f.id, n): pxart.pixels(doc.image(f, n)) for f in doc.frames for n in names}


def test_palette_add_takes_a_palette_line_too(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\nk\n")
    assert run("palette", p, "--add", "z #123456") == 0
    assert pxart.parse(p).palette["z"] == (0x12, 0x34, 0x56, 255)


def test_palette_add_key_equals_sign(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\nk\n")
    assert run("palette", p, "--add", "==#123456") == 0
    assert pxart.parse(p).palette["="] == (0x12, 0x34, 0x56, 255)


def test_palette_add_key_equals_sign_as_a_line(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\nk\n")
    assert run("palette", p, "--add", "= #123456") == 0
    assert pxart.parse(p).palette["="] == (0x12, 0x34, 0x56, 255)


def test_palette_add_bad_color_names_both_forms(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\nk\n")
    msg = run_err("palette", p, "--add", "z #12345")
    assert "E_BAD_COLOR" in msg and "'k #rrggbb'" in msg


def test_palette_variant_add_makes_the_variant(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\nw #ffffff\n\n@frame a\nkw\n")
    assert run("palette", p, "--variant", "night", "--add", "k=#101010", "w #202020") == 0
    assert capsys.readouterr().out == f"new @variant night; sets k #101010 w #202020; wrote {p}\n"
    assert p.read_text() == "k #000000\nw #ffffff\n\n@variant night\nk #101010\nw #202020\n\n@frame a\nkw\n"


def test_palette_variant_add_renders(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\nw #ffffff\n\n@frame a\nkw\n")
    run("palette", p, "--variant", "night", "--add", "k=#101010")
    doc = pxart.parse(p)
    assert pxart.pixels(doc.image(doc.frames[0], "night")) == [(16, 16, 16, 255), (255, 255, 255, 255)]


def test_palette_variant_add_overrides_one_line_only(tmp_path, capsys):
    text = "k #000000\nw #ffffff\n\n# night: cool\n@variant night\nk #101010\nw #202020\n\n@frame a\nkw\n"
    p = write(tmp_path, "s.px", text)
    assert run("palette", p, "--variant", "night", "--add", "w=#303030") == 0
    assert capsys.readouterr().out == f"@variant night; sets w #303030; wrote {p}\n"
    assert p.read_text() == text.replace("w #202020", "w #303030")


def test_palette_variant_add_adds_a_line_to_an_existing_variant(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\nw #ffffff\n\n@variant night\nk #101010\n\n@frame a\nkw\n")
    run("palette", p, "--variant", "night", "--add", "w=#303030")
    assert p.read_text() == "k #000000\nw #ffffff\n\n@variant night\nk #101010\nw #303030\n\n@frame a\nkw\n"


def test_palette_variant_add_same_again_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\n\n@variant night\nk #101010\n\n@frame a\nk\n")
    assert run("palette", p, "--variant", "night", "--add", "k=#101010") == 0
    assert capsys.readouterr().out == f"@variant night; k is already #101010 in night; unchanged; no change: {p}\n"


def test_palette_variant_add_base_color_is_a_relist(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\nl #fff4b0\n\n@variant night\nk #101010\n\n@frame a\nkl\n")
    assert run("palette", p, "--variant", "night", "--add", "l=#fff4b0") == 0
    assert capsys.readouterr().out == f"@variant night; sets l #fff4b0 (its base color); wrote {p}\n"
    run("palette", p)
    assert capsys.readouterr().out.splitlines()[-1] == ("  night: brightens k; relists unchanged: l; inherits: "
                                                         "nothing")


def test_palette_variant_add_in_a_palette_file(tmp_path):
    p = write(tmp_path, "pal.px", "k #000000\n")
    assert run("palette", p, "--variant", "dusk", "--add", "k=#111111") == 0
    assert pxart.parse(p, palette_only=True).variants == {"dusk": {"k": (17, 17, 17, 255)}}


def test_palette_variant_add_over_an_imported_variant(tmp_path, capsys):
    write(tmp_path, "pal.px", "k #000000\nw #ffffff\n@variant night\nk #101010\n")
    p = write(tmp_path, "s.px", "@palette pal.px\n\n@frame a\nkw\n")
    assert run("palette", p, "--variant", "night", "--add", "w=#202020") == 0
    assert capsys.readouterr().out == f"@variant night; sets w #202020; wrote {p}\n"  # FILE had night, by import
    doc = pxart.parse(p)
    assert doc.variants == {"night": {"w": (32, 32, 32, 255)}}
    assert pxart.pixels(doc.image(doc.frames[0], "night")) == [(16, 16, 16, 255), (32, 32, 32, 255)]


def test_palette_variant_add_key_not_in_base(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\n@frame a\nk\n")
    msg = run_err("palette", p, "--variant", "night", "--add", "z=#101010")
    assert "E_VARIANT_KEY" in msg and "--add 'z=#rrggbb'" in msg
    assert "@variant" not in p.read_text()


def test_palette_variant_add_dot_is_refused(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\n@frame a\nk\n")
    assert "E_VARIANT_KEY" in run_err("palette", p, "--variant", "night", "--add", ".=#101010")


@pytest.mark.parametrize("name", ["base", "no good", "a/b", "x%y"])
def test_palette_variant_bad_names(tmp_path, name):
    p = write(tmp_path, "s.px", "k #000000\n\n@frame a\nk\n")
    assert "E_BAD_ARG" in run_err("palette", p, "--variant", name, "--add", "k=#101010")


def test_palette_variant_alone_is_an_error(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\n@frame a\nk\n")
    msg = run_err("palette", p, "--variant", "night")
    assert "E_BAD_ARG" in msg and "--add" in msg and "--keep" in msg


def test_palette_keep_without_variant_is_an_error(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\n@variant night\nk #111111\n\n@frame a\nk\n")
    msg = run_err("palette", p, "--keep", "k")
    assert "E_BAD_ARG" in msg and "--variant NAME" in msg


def test_palette_keep_removes_the_line(tmp_path, capsys):
    text = "k #000000\nl #fff4b0\n\n@variant night\nk #101010\n# lamp\nl #999999\n\n@frame a\nkl\n"
    p = write(tmp_path, "s.px", text)
    assert run("palette", p, "--variant", "night", "--keep", "l") == 0
    assert capsys.readouterr().out == f"@variant night; l inherits the base color; wrote {p}\n"
    assert p.read_text() == "k #000000\nl #fff4b0\n\n@variant night\nk #101010\n\n@frame a\nkl\n"  # comment goes too


def test_palette_keep_two_keys_both_forms(tmp_path, capsys):
    for i, keys in enumerate(("l,g", "lg")):
        p = write(tmp_path, f"s{i}.px", "l #fff4b0\ng #ffc861\n\n@variant night\nl #111111\ng #222222\n\n@frame a\nlg\n")
        assert run("palette", p, "--variant", "night", "--keep", keys) == 0
        assert capsys.readouterr().out == f"@variant night; l g inherit the base colors; wrote {p}\n"
        assert pxart.parse(p).variants == {"night": {}}


def test_palette_keep_a_relist_goes_and_renders_the_same(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\nl #fff4b0\n\n@variant night\nk #101010\nl #fff4b0\n\n@frame a\nkl\n")
    before = looks(pxart.parse(p))
    run("palette", p, "--variant", "night", "--keep", "l")
    assert looks(pxart.parse(p)) == before and "l" not in pxart.parse(p).variants["night"]


def test_palette_keep_pins_a_key_an_import_recolors(tmp_path, capsys):
    write(tmp_path, "pal.px", "k #000000\nl #fff4b0\n@variant night\nk #101010\nl #333333\n")
    p = write(tmp_path, "s.px", "@palette pal.px\n\n@frame a\nkl\n")
    assert run("palette", p, "--variant", "night", "--keep", "l") == 0
    assert capsys.readouterr().out == (f"@variant night; l listed in its base color (the imported @variant night "
                                       f"recolors it); wrote {p}\n")
    doc = pxart.parse(p)
    assert doc.variants == {"night": {"l": (0xff, 0xf4, 0xb0, 255)}}
    assert doc.image(doc.frames[0], "night").getpixel((1, 0)) == (0xff, 0xf4, 0xb0, 255)


def test_palette_keep_local_line_over_import_is_replaced_by_the_base_color(tmp_path, capsys):
    write(tmp_path, "pal.px", "l #fff4b0\n@variant night\nl #333333\n")
    p = write(tmp_path, "s.px", "@palette pal.px\n@variant night\nl #444444\n\n@frame a\nl\n")
    assert run("palette", p, "--variant", "night", "--keep", "l") == 0
    assert pxart.parse(p).variants == {"night": {"l": (0xff, 0xf4, 0xb0, 255)}}
    assert "listed in its base color" in capsys.readouterr().out


def test_palette_keep_already_inheriting(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\nl #fff4b0\n\n@variant night\nk #101010\n\n@frame a\nkl\n")
    assert run("palette", p, "--variant", "night", "--keep", "l") == 0
    assert capsys.readouterr().out == f"@variant night; l already inherits the base color; no change: {p}\n"


def test_palette_keep_on_a_missing_variant(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\n@variant night\nk #111111\n\n@frame a\nk\n")
    msg = run_err("palette", p, "--variant", "dawn", "--keep", "k")
    assert "E_SELECT" in msg and "no @variant 'dawn' (have: night)" in msg


def test_palette_keep_key_not_in_base(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\n@variant night\nk #111111\n\n@frame a\nk\n")
    assert "E_VARIANT_KEY" in run_err("palette", p, "--variant", "night", "--keep", "z")


def test_palette_add_and_keep_in_one_call(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\nl #fff4b0\n\n@variant night\nl #111111\n\n@frame a\nkl\n")
    assert run("palette", p, "--variant", "night", "--add", "k=#101010", "--keep", "l") == 0
    assert capsys.readouterr().out == f"@variant night; sets k #101010; l inherits the base color; wrote {p}\n"
    assert pxart.parse(p).variants == {"night": {"k": (16, 16, 16, 255)}}


def test_palette_add_and_keep_same_key_is_an_error(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n\n@variant night\nk #111111\n\n@frame a\nk\n")
    msg = run_err("palette", p, "--variant", "night", "--add", "k=#101010", "--keep", "k")
    assert "E_BAD_ARG" in msg and "set in the variant or inherits" in msg


def test_palette_variant_new_with_add_and_keep(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\nl #fff4b0\n\n@frame a\nkl\n")
    assert run("palette", p, "--variant", "dusk", "--add", "k=#101010", "--keep", "l") == 0
    out = capsys.readouterr().out
    assert out.startswith("new @variant dusk; sets k #101010; l already inherits the base color; wrote ")


def test_palette_variant_edit_prints_no_listing(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\n\n@frame a\nk\n")
    run("palette", p, "--variant", "dusk", "--add", "k=#101010")
    assert "used" not in capsys.readouterr().out


def test_palette_authoring_the_keepers_night(tmp_path, capsys):
    # The keeper's night, written with the tool: recolor the cloth, relist the lamp, listed as the author meant it.
    p = write(tmp_path, "pal.px", "k #2a1f33\nw #f6f1e4\nl #fff4b0\ng #ffc861\n")
    assert run("palette", p, "--variant", "night", "--add", "k=#120e22", "w=#9fb0d4", "l=#fff4b0", "g=#ffc861") == 0
    capsys.readouterr()
    run("palette", p)
    assert capsys.readouterr().out.splitlines()[-1] == ("  night: recolors (darker) k w; relists unchanged: l g; "
                                                         "inherits: nothing")


HOIST_PAL = "# pack palette\nk #000000\n@variant night\nk #111111\n"
HOIST_HERO = ("@palette pal.px\n# lamp glass\nl #fff4b0\ng #ffc861\n\n# night: lamps stay lit\n@variant night\n"
              "l #fff4b0\ng #ffc861\n\n@frame a\nklg\n")


def test_hoist_moves_keys_and_comments(tmp_path, capsys):
    pal, hero = write(tmp_path, "pal.px", HOIST_PAL), write(tmp_path, "hero.px", HOIST_HERO)
    assert run("palette", hero, "--hoist", "l,g") == 0
    assert capsys.readouterr().out == f"hoisted l g to pal.px; wrote {pal}; wrote {hero}\n"
    assert pal.read_text() == ("# pack palette\nk #000000\n# lamp glass\nl #fff4b0\ng #ffc861\n\n"
                               "# night: lamps stay lit\n@variant night\nk #111111\nl #fff4b0\ng #ffc861\n")
    assert hero.read_text() == "@palette pal.px\n\n@frame a\nklg\n"


def test_hoist_renders_as_before(tmp_path):
    write(tmp_path, "pal.px", HOIST_PAL)
    hero = write(tmp_path, "hero.px", HOIST_HERO)
    before = looks(pxart.parse(hero))
    run("palette", hero, "--hoist", "lg")
    assert looks(pxart.parse(hero)) == before


def test_hoist_other_importers_get_the_keys(tmp_path):
    write(tmp_path, "pal.px", HOIST_PAL)
    hero = write(tmp_path, "hero.px", HOIST_HERO)
    other = write(tmp_path, "lamp.px", "@palette pal.px\n\n@frame a\nk\n")
    run("palette", hero, "--hoist", "lg")
    doc = pxart.parse(other)
    assert doc.resolved()["l"] == (0xff, 0xf4, 0xb0, 255) and doc.resolved("night")["g"] == (0xff, 0xc8, 0x61, 255)


def test_hoist_one_key_leaves_the_other(tmp_path):
    pal = write(tmp_path, "pal.px", HOIST_PAL)
    hero = write(tmp_path, "hero.px", HOIST_HERO)
    before = looks(pxart.parse(hero))
    assert run("palette", hero, "--hoist", "l") == 0
    doc = pxart.parse(hero)
    assert list(doc.palette) == ["g"] and doc.variants == {"night": {"g": (0xff, 0xc8, 0x61, 255)}}
    assert "l #fff4b0" in pal.read_text() and looks(doc) == before


def test_hoist_makes_the_variant_in_the_palette_file(tmp_path):
    pal = write(tmp_path, "pal.px", "k #000000\n")
    hero = write(tmp_path, "hero.px", "@palette pal.px\nl #fff4b0\n@variant dusk\nl #806040\n\n@frame a\nkl\n")
    before = looks(pxart.parse(hero))
    assert run("palette", hero, "--hoist", "l") == 0
    assert pxart.parse(pal, palette_only=True).variants == {"dusk": {"l": (0x80, 0x60, 0x40, 255)}}
    assert looks(pxart.parse(hero)) == before and "@variant" not in hero.read_text()


def test_hoist_keeps_a_variant_line_the_palette_file_has_otherwise(tmp_path, capsys):
    pal = write(tmp_path, "pal.px", "k #000000\nl #fff4b0\n@variant night\nl #333333\n")
    hero = write(tmp_path, "hero.px", "@palette pal.px\nl #fff4b0\n@variant night\nl #444444\n\n@frame a\nkl\n")
    before = looks(pxart.parse(hero))
    assert run("palette", hero, "--hoist", "l") == 0
    out = capsys.readouterr().out
    assert "l in @variant night stays in" in out and "(pal.px has its own color for it)" in out
    assert looks(pxart.parse(hero)) == before and "l #444444" in hero.read_text() and "l #333333" in pal.read_text()


def test_hoist_same_color_key_already_in_the_palette_file(tmp_path, capsys):
    pal = write(tmp_path, "pal.px", "k #000000\nl #fff4b0\n")
    hero = write(tmp_path, "hero.px", "@palette pal.px\nl #fff4b0\n\n@frame a\nkl\n")
    text = pal.read_text()
    assert run("palette", hero, "--hoist", "l") == 0
    assert pal.read_text() == text and "l #" not in hero.read_text()
    assert f"no change: {pal}" in capsys.readouterr().out


def test_hoist_other_color_in_the_palette_file_is_a_conflict(tmp_path):
    pal = write(tmp_path, "pal.px", "k #000000\nl #ffffff\n")
    hero = write(tmp_path, "hero.px", "@palette pal.px\nl #fff4b0\n\n@frame a\nkl\n")
    texts = pal.read_text(), hero.read_text()
    msg = run_err("palette", hero, "--hoist", "l")
    assert "E_KEY_CONFLICT" in msg and "would recolor every sprite that imports pal.px" in msg and "'l>K'" in msg
    assert (pal.read_text(), hero.read_text()) == texts


def test_hoist_needs_an_import(tmp_path):
    hero = write(tmp_path, "hero.px", "l #fff4b0\n\n@frame a\nl\n")
    msg = run_err("palette", hero, "--hoist", "l")
    assert "E_BAD_ARG" in msg and "--extract-to P.px --repoint" in msg


def test_hoist_needs_one_import(tmp_path):
    write(tmp_path, "a.px", "k #000000\n")
    write(tmp_path, "b.px", "w #ffffff\n")
    hero = write(tmp_path, "hero.px", "@palette a.px\n@palette b.px\nl #fff4b0\n\n@frame a\nl\n")
    msg = run_err("palette", hero, "--hoist", "l")
    assert "E_BAD_ARG" in msg and "imports 2: a.px, b.px" in msg


def test_hoist_an_imported_key_is_an_error(tmp_path):
    write(tmp_path, "pal.px", HOIST_PAL)
    hero = write(tmp_path, "hero.px", HOIST_HERO)
    msg = run_err("palette", hero, "--hoist", "k")
    assert "E_SELECT" in msg and "it comes from pal.px already" in msg


def test_hoist_an_unknown_key_is_an_error(tmp_path):
    write(tmp_path, "pal.px", HOIST_PAL)
    hero = write(tmp_path, "hero.px", HOIST_HERO)
    assert "no such key" in run_err("palette", hero, "--hoist", "z")


def test_hoist_is_given_alone(tmp_path):
    write(tmp_path, "pal.px", HOIST_PAL)
    hero = write(tmp_path, "hero.px", HOIST_HERO)
    assert "E_BAD_ARG" in run_err("palette", hero, "--hoist", "l", "--add", "z=#000000")


def test_hoist_from_a_subdirectory(tmp_path):
    pal = write(tmp_path, "pal.px", HOIST_PAL)
    (tmp_path / "sprites").mkdir()
    hero = write(tmp_path / "sprites", "hero.px", HOIST_HERO.replace("@palette pal.px", "@palette ../pal.px"))
    before = looks(pxart.parse(hero))
    assert run("palette", hero, "--hoist", "lg") == 0
    assert "l #fff4b0" in pal.read_text() and looks(pxart.parse(hero)) == before
    assert hero.read_text().startswith("@palette ../pal.px\n")


def test_hoist_keeps_a_dot_line_in_place(tmp_path):
    write(tmp_path, "pal.px", "k #000000\n")
    hero = write(tmp_path, "hero.px", "@palette pal.px\nl #fff4b0\n. transparent\nw #ffffff\n\n@frame a\nklw\n")
    assert run("palette", hero, "--hoist", "l") == 0
    assert hero.read_text() == "@palette pal.px\n. transparent\nw #ffffff\n\n@frame a\nklw\n"


def test_hoist_keeps_the_local_variant_when_the_palette_file_lacks_it_and_lines_stay(tmp_path):
    # A relist of a key the palette file has no variant for moves, making the variant there.
    pal = write(tmp_path, "pal.px", "k #000000\n")
    hero = write(tmp_path, "hero.px", "@palette pal.px\nl #fff4b0\n@variant night\nl #fff4b0\n\n@frame a\nkl\n")
    assert run("palette", hero, "--hoist", "l") == 0
    assert pxart.parse(pal, palette_only=True).variants == {"night": {"l": (0xff, 0xf4, 0xb0, 255)}}
    assert pxart.parse(hero).resolved("night")["l"] == (0xff, 0xf4, 0xb0, 255)


def test_help_documents_variant_authoring(capsys):
    doc = " ".join(pxart.__doc__.split())
    assert "palette FILE [--add k=#hex ...] [--variant NAME [--add k=#hex ...] [--keep KEYS]]" in doc
    assert "[--comment-header 'text'] [--hoist KEYS]" in doc
    assert "Authoring a variant: with --variant NAME, --add sets the keys in that variant instead" in doc
    assert "--variant NAME --keep l,g lets keys inherit the base colors" in doc
    assert "--hoist l,g moves FILE's own keys into the palette file it imports" in doc
    out = " ".join(cmd_help(capsys, "palette").split())
    assert "Authoring a variant" in out and "--hoist" in out and "--keep" in out
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "with `--variant night` it sets keys in that variant, making it if needed" in readme


BLOCK6 = "\n".join(["kkkkkk"] * 6)
CHECK6 = "\n".join(["r.r.r.", ".r.r.r"] * 3)  # every pixel another color or gone, whatever the shift


def test_onion_frames_of_one_animation_are_one_sprite_however_much_changed(tmp_path, capsys):
    # A wing flap changes most of a small sprite's pixels: still one animation, still a best shift.
    p = write(tmp_path, "m.px", f"k #000000\nr #ff0000\n@anim fly ms=100\n@frame fly/0\n{BLOCK6}\n@frame fly/1\n{CHECK6}\n")
    lines = onion_lines(tmp_path, capsys, f"{p}:fly/0", f"{p}:fly/1")
    assert "; best shift " in lines[2] and "different sprites" not in lines[2]


def test_onion_same_frames_in_other_groups_can_be_two_sprites(tmp_path, capsys):
    p = write(tmp_path, "m.px", f"k #000000\nr #ff0000\n@frame a/0\n{BLOCK6}\n@frame b/0\n{CHECK6}\n")
    lines = onion_lines(tmp_path, capsys, f"{p}:a/0", f"{p}:b/0")
    assert lines[2].endswith("; different sprites: edges only")


def test_onion_top_level_frames_are_not_one_animation(tmp_path, capsys):
    p = write(tmp_path, "m.px", f"k #000000\nr #ff0000\n@frame a\n{BLOCK6}\n@frame b\n{CHECK6}\n")
    lines = onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b")
    assert lines[2].endswith("; different sprites: edges only")


# ---------------------------------------------------------------- compose across packs: comments, variants, lost keys

MARKET_PAL = ("# Harbor market palette: warm stone, one hot accent (awning red)\nk #2b1e2f\nr #c4473a\nl #bcb6b4\n"
              "g #8f8a96\ny #f3cf6b\n\n@variant dusk\nk #1b1326\nr #a33a4c\nl #978ca6\ng #726a8a\ny #ffd66e\n")
KEEPER_PAL = ("# Cozy seaside\nk #2a1f33\nr #c4473a\ns #f0c29a\n# lamp glass\nl #fff4b0\ng #ffc861\n\n"
              "# night: cool moonlight; lamp colors (l, g) stay lit\n@variant night\nk #120e22\nr #83344e\n"
              "s #b88f8c\nl #fff4b0\ng #ffc861\n")
CANDLE_PAL = ("k #1a1423\nw #f6eed8\n# light-emitting keys: flame. Not in @variant dark, so it stays warm.\n"
              "f #ffe07a\n\n# darkness: everything that only reflects light goes cold\n@variant dark\nk #0c0a18\n"
              "w #403f4a\n")


def three_packs(tmp_path):
    """The crossover in small: a market (dusk), a keeper (night, lamps kept lit) and a candle (dark, flame kept warm),
    each with its own palette file; the keeper's red is the market's awning red."""
    for d in ("market", "keeper", "candle"):
        (tmp_path / d).mkdir()
    write(tmp_path / "market", "palette.px", MARKET_PAL)
    stall = write(tmp_path / "market", "stall.px", "@palette palette.px\n@frame stall\nkrl\nggy\n")
    write(tmp_path / "keeper", "palette.px", KEEPER_PAL)
    keeper = write(tmp_path / "keeper", "keeper.px", "@palette palette.px\n@frame idle\nkrs\nkrs\n@frame lantern\nlgk\n"
                                                      "kkk\n")
    write(tmp_path / "candle", "pal.px", CANDLE_PAL)
    candle = write(tmp_path / "candle", "player.px", "@palette pal.px\n@frame idle\n.f.\nkwk\n")
    return stall, keeper, candle


def compose_packs(tmp_path, *more, name="scene.px"):
    stall, keeper, candle = three_packs(tmp_path)
    out = tmp_path / name
    code = run("compose", "-o", out, "--size", "9x2", f"{stall}:stall@0,0", f"{keeper}:idle@3,0", f"{candle}:idle@6,0",
               *more)
    return code, out, (stall, keeper, candle)


def looks_as_its_file(out, layer_specs, vmap=None):
    """Each layer's pixels in each of OUT's variants look as its own file draws them in that variant (vmap: OUT's name ->
    the names a file may give it, first one it has), or in its base colors when its file has no such variant."""
    doc = pxart.parse(out)
    names = [None] + sorted(set(doc.variants) | set(doc.shared_variants))
    for v in names:
        img = doc.image(doc.frames[0], v)
        for path, fid, x0, y0 in layer_specs:
            src = pxart.parse(path)
            have = set(src.variants) | set(src.shared_variants)
            want = next((n for n in (vmap or {}).get(v, [v]) if n in have), None) if v else None
            simg = src.image(src.get(fid), want)
            for y in range(simg.height):
                for x in range(simg.width):
                    p = simg.getpixel((x, y))
                    if p[3]:
                        assert img.getpixel((x0 + x, y0 + y)) == p, (v, path.name, fid, x, y, want)
    return True


def test_three_packs_need_rekey(tmp_path):
    code, out, _ = compose_packs(tmp_path)
    assert code == 1 and not out.exists()


def test_three_packs_rekey_every_layer_keeps_its_look(tmp_path, capsys):
    code, out, (stall, keeper, candle) = compose_packs(tmp_path, "--rekey")
    assert code == 0
    assert looks_as_its_file(out, [(stall, "stall", 0, 0), (keeper, "idle", 3, 0), (candle, "idle", 6, 0)])


def test_three_packs_rekey_separates_the_shared_awning_red(tmp_path, capsys):
    # r is #c4473a in both the market and the keeper, but dusk and night recolor it differently: two keys in OUT.
    code, out, (stall, keeper, candle) = compose_packs(tmp_path, "--rekey")
    doc = pxart.parse(out)
    reds = [k for k, c in doc.palette.items() if c == pxart.hex2rgba("#c4473a")]
    assert len(reds) == 2 and "r" in reds
    new = next(k for k in reds if k != "r")
    assert doc.variants["dusk"]["r"] == pxart.hex2rgba("#a33a4c") and "r" not in doc.variants["night"]
    assert doc.variants["night"][new] == pxart.hex2rgba("#83344e") and new not in doc.variants["dusk"]
    assert doc.frames[0].grid[0][4] == new  # the keeper's scarf


def test_three_packs_rekey_note_names_the_red(tmp_path, capsys):
    code, out, (stall, keeper, candle) = compose_packs(tmp_path, "--rekey")
    line = next(l for l in capsys.readouterr().out.splitlines() if l.startswith(f"note: --rekey gives {keeper}'s"))
    assert "'r>" in line and "'k>" in line and "'l>" in line and "'g>" in line


def test_three_packs_rekey_keeps_the_keepers_lamp_keys(tmp_path, capsys):
    # l g: unused in the idle frame, the market holds those letters, but the lantern draws with them and night keeps them
    # lit: --rekey gives them free keys instead of leaving them out, relisted in night as the keeper's palette has them.
    code, out, _ = compose_packs(tmp_path, "--rekey")
    doc = pxart.parse(out)
    lamp = {k for k, c in doc.palette.items() if c in (pxart.hex2rgba("#fff4b0"), pxart.hex2rgba("#ffc861"))}
    assert len(lamp) == 2 and not lamp & {"l", "g"}
    assert {k: doc.variants["night"][k] for k in lamp} == {k: doc.palette[k] for k in lamp}  # relisted unchanged
    assert "WARNING" not in capsys.readouterr().out


def test_three_packs_rekey_listing_shows_the_lamps_relisted(tmp_path, capsys):
    code, out, _ = compose_packs(tmp_path, "--rekey")
    doc = pxart.parse(out)
    lamp = [k for k, c in doc.palette.items() if c in (pxart.hex2rgba("#fff4b0"), pxart.hex2rgba("#ffc861"))]
    capsys.readouterr()
    run("palette", out)
    night = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("  night:"))
    assert f"relists unchanged: {' '.join(lamp)}" in night


def test_three_packs_without_rekey_prints_no_warning_for_the_file_it_didnt_write(tmp_path, capsys):
    code, out, (stall, keeper, candle) = compose_packs(tmp_path)
    got = capsys.readouterr()
    assert code == 1 and not out.exists()
    assert not [l for l in got.out.splitlines() if l.startswith(("WARNING:", "note:"))]


def test_three_packs_left_out_is_one_line_per_file(tmp_path, capsys):
    compose_packs(tmp_path, "--rekey")
    lines = [l for l in capsys.readouterr().out.splitlines() if "leaves out" in l]
    assert len(lines) == len({l.split("leaves out ")[1].split("'s colors")[0] for l in lines}) <= 3


def test_three_packs_rekey_coverage_notes(tmp_path, capsys):
    code, out, (stall, keeper, candle) = compose_packs(tmp_path, "--rekey")
    lines = capsys.readouterr().out.splitlines()
    assert f"note: {out}'s @variant dusk covers layer 1 ({stall}:stall) only: layer 2 ({keeper}:idle) and layer 3 " \
           f"({candle}:idle) stay at base colors in it" in lines
    assert f"note: {out}'s @variant night covers layer 2 ({keeper}:idle) only: layer 1 ({stall}:stall) and layer 3 " \
           f"({candle}:idle) stay at base colors in it" in lines
    assert f"note: {out}'s @variant dark covers layer 3 ({candle}:idle) only: layer 1 ({stall}:stall) and layer 2 " \
           f"({keeper}:idle) stay at base colors in it" in lines
    assert ("note: to give every layer one variant, merge them: --variant-map dusk=night,dark (each layer takes the "
            "first of dusk, night, dark its file has)") in lines


def test_three_packs_notes_come_before_wrote(tmp_path, capsys):
    compose_packs(tmp_path, "--rekey")
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1].startswith("wrote ") and all(l.startswith("note:") for l in lines[:-1])


def test_three_packs_variant_map_merges_one_dusk(tmp_path, capsys):
    code, out, (stall, keeper, candle) = compose_packs(tmp_path, "--rekey", "--variant-map", "dusk=night,dark")
    assert code == 0
    doc = pxart.parse(out)
    assert set(doc.variants) == {"dusk"} and not doc.shared_variants
    assert looks_as_its_file(out, [(stall, "stall", 0, 0), (keeper, "idle", 3, 0), (candle, "idle", 6, 0)],
                             {"dusk": ["dusk", "night", "dark"]})
    assert "covers" not in capsys.readouterr().out  # every layer is in it


def test_three_packs_variant_map_keeps_the_flame_and_lamps_lit(tmp_path, capsys):
    code, out, _ = compose_packs(tmp_path, "--rekey", "--variant-map", "dusk=night,dark")
    doc = pxart.parse(out)
    flame = next(k for k, c in doc.palette.items() if c == pxart.hex2rgba("#ffe07a"))
    assert flame not in doc.variants["dusk"]  # left out of dark, so out of the merged dusk too
    capsys.readouterr()
    run("palette", out)
    dusk = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("  dusk:"))
    assert "relists unchanged:" in dusk and dusk.endswith(f"inherits: {flame}")


def test_three_packs_variant_map_comment_names_its_sources(tmp_path, capsys):
    code, out, _ = compose_packs(tmp_path, "--rekey", "--variant-map", "dusk=night,dark")
    text = out.read_text()
    head = text.split("@variant dusk")[0].splitlines()
    assert head[-1] == "# dusk: stall.px's dusk, keeper.px's night, player.px's dark (compose --variant-map)"
    assert "# night: cool moonlight; lamp colors (l, g) stay lit (renamed " in text
    assert "# darkness: everything that only reflects light goes cold" in text


def test_three_packs_comments_come_along(tmp_path, capsys):
    code, out, _ = compose_packs(tmp_path, "--rekey")
    lines = out.read_text().splitlines()
    flame = next(i for i, l in enumerate(lines) if l.endswith("#ffe07a"))
    assert lines[flame - 1].startswith("# light-emitting keys: flame. Not in @variant dark, so it stays warm.")
    night = lines.index("@variant night")
    assert lines[night - 1].startswith("# night: cool moonlight; lamp colors (l, g) stay lit (renamed l>")
    dark = lines.index("@variant dark")
    assert lines[dark - 1] == "# darkness: everything that only reflects light goes cold (from player.px's @variant dark)"


def test_three_packs_renamed_lamp_comment_names_both_keys(tmp_path, capsys):
    code, out, _ = compose_packs(tmp_path, "--rekey")
    doc = pxart.parse(out)
    new = {c: k for k, c in doc.palette.items()}
    l, g = new[pxart.hex2rgba("#fff4b0")], new[pxart.hex2rgba("#ffc861")]
    assert (f"# night: cool moonlight; lamp colors (l, g) stay lit (renamed l>{l} g>{g}; from keeper.px's @variant "
            "night)") in out.read_text()
    assert f"# lamp glass (renamed l>{l}; from keeper.px)" in out.read_text()  # above the renamed key line itself


def test_three_packs_comments_survive_extract_to(tmp_path, capsys):
    code, out, _ = compose_packs(tmp_path, "--rekey")
    assert run("palette", out, "--extract-to", tmp_path / "shared.px") == 0
    text = (tmp_path / "shared.px").read_text()
    assert "# light-emitting keys: flame." in text and "# night: cool moonlight;" in text and "# darkness:" in text


def test_three_packs_output_renders_like_the_sources_in_base(tmp_path):
    code, out, (stall, keeper, candle) = compose_packs(tmp_path, "--rekey")
    doc, s = pxart.parse(out), pxart.parse(stall)
    assert doc.image(doc.frames[0]).crop((0, 0, 3, 2)).tobytes() == s.image(s.get("stall")).tobytes()


def test_three_packs_check_strict_passes(tmp_path, capsys):
    code, out, _ = compose_packs(tmp_path, "--rekey")
    assert run("check", "--strict", out) == 0


# ---------------------------------------------------------------- compose: a shared key whose variants differ

AWNING = "r #c4473a\nk #000000\n@variant dusk\nr #a33a4c\n@frame a\nrk\n"
SCARF = "r #c4473a\nk #000000\n@variant night\nr #83344e\n@frame s\nr.\n"


def test_variant_clash_note_without_rekey(tmp_path, capsys):
    a, b = write(tmp_path, "awning.px", AWNING), write(tmp_path, "scarf.px", SCARF)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1") == 0
    lines = capsys.readouterr().out.splitlines()
    assert (f"WARNING: layer 2 ({b}:s) draws 'r' #c4473a in {out}'s variant colors, not scarf.px's: dusk #a33a4c "
            "(scarf.px: #c4473a), night #c4473a (scarf.px: #83344e); compose --rekey r gives it a key of its own") \
        in lines


def test_variant_clash_owner_decides_without_rekey(tmp_path, capsys):
    # OUT's r belongs to layer 1 (the awning): dusk recolors it, night doesn't. The scarf's night is lost (noted), and the
    # awning isn't recolored by the scarf's night any more.
    a, b = write(tmp_path, "awning.px", AWNING), write(tmp_path, "scarf.px", SCARF)
    out = tmp_path / "o.px"
    run("compose", "-o", out, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1")
    doc = pxart.parse(out)
    assert doc.variants == {"dusk": {"r": pxart.hex2rgba("#a33a4c")}, "night": {}}  # night's only key is the awning's
    assert doc.image(doc.frames[0], "night").getpixel((0, 0)) == pxart.hex2rgba("#c4473a")


def test_variant_clash_rekey_gives_the_scarf_its_own_key(tmp_path, capsys):
    a, b = write(tmp_path, "awning.px", AWNING), write(tmp_path, "scarf.px", SCARF)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1", "--rekey") == 0
    assert capsys.readouterr().out.splitlines()[0] == (
        f"note: --rekey gives {b}'s keys free ones in {out}: 'r>a' ({b} is unchanged): r has {out}'s base color but "
        "other variant colors")
    doc = pxart.parse(out)
    assert doc.frames[0].grid == ["rk", "a."]
    assert doc.variants == {"dusk": {"r": pxart.hex2rgba("#a33a4c")}, "night": {"a": pxart.hex2rgba("#83344e")}}
    assert looks_as_its_file(out, [(a, "a", 0, 0), (b, "s", 0, 1)])


def test_variant_clash_rekey_order_of_layers(tmp_path, capsys):
    # The scarf first: it owns r now, and the awning's r is the one that moves.
    a, b = write(tmp_path, "awning.px", AWNING), write(tmp_path, "scarf.px", SCARF)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x2", f"{b}:s@0,1", f"{a}:a@0,0", "--rekey") == 0
    doc = pxart.parse(out)
    assert doc.frames[0].grid[1] == "r." and doc.frames[0].grid[0][0] != "r"
    assert looks_as_its_file(out, [(a, "a", 0, 0), (b, "s", 0, 1)])


def test_variant_clash_not_when_variants_agree(tmp_path, capsys):
    a = write(tmp_path, "a.px", "r #c4473a\n@variant dusk\nr #a33a4c\n@frame a\nr\n")
    b = write(tmp_path, "b.px", "r #c4473a\n@variant dusk\nr #a33a4c\n@frame b\nr\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:a@0,0", f"{b}:b@1,0", "--rekey") == 0
    out_text = capsys.readouterr().out
    assert "--rekey gives" not in out_text and "draws 'r'" not in out_text and "covers" not in out_text
    assert pxart.parse(out).frames[0].grid == ["rr"]


def test_variant_clash_not_without_any_variants(tmp_path, capsys):
    a = write(tmp_path, "a.px", "r #c4473a\n@frame a\nr\n")
    b = write(tmp_path, "b.px", "r #c4473a\n@frame b\nr\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:a@0,0", f"{b}:b@1,0") == 0
    assert capsys.readouterr().out == f"wrote {out}\n"


def test_variant_clash_variantless_layer_stays_base(tmp_path, capsys):
    # A layer whose file has no variants stays at its base colors in OUT's variants: a shared key is separated.
    a, b = write(tmp_path, "awning.px", AWNING), write(tmp_path, "plain.px", "r #c4473a\n@frame p\nr\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x2", f"{a}:a@0,0", f"{b}:p@0,1", "--rekey") == 0
    assert looks_as_its_file(out, [(a, "a", 0, 0), (b, "p", 0, 1)])
    assert f"@variant dusk covers layer 1 ({a}:a) only: layer 2 ({b}:p) stays at base colors in it" \
        in capsys.readouterr().out


def test_variant_clash_existing_out_note_without_rekey(tmp_path, capsys):
    # An existing OUT keeps its own variants, and its dusk would color the scarf's r like the awning's: a note.
    b = write(tmp_path, "scarf.px", SCARF)
    out = write(tmp_path, "o.px", AWNING)
    assert run("compose", "-o", f"{out}:b", f"{b}:s@0,0") == 0
    got = capsys.readouterr().out.splitlines()
    assert got == [f"WARNING: layer 1 ({b}:s) draws 'r' #c4473a in {out}'s variant colors, not scarf.px's: dusk "
                   "#a33a4c (scarf.px: #c4473a); compose --rekey r gives it a key of its own", f"wrote {out} frame b"]
    assert pxart.parse(out).get("b").grid == ["r."]


def test_variant_clash_existing_out_rekey_gives_the_scarf_its_own_key(tmp_path, capsys):
    b = write(tmp_path, "scarf.px", SCARF)
    out = write(tmp_path, "o.px", AWNING)
    assert run("compose", "-o", f"{out}:b", f"{b}:s@0,0", "--rekey") == 0
    got = capsys.readouterr().out.splitlines()
    # one line per reason: what --rekey did and why, then the dusk its new key doesn't get
    assert got[0] == (f"note: --rekey gives {b}'s keys free ones in {out}: 'r>a' ({b} is unchanged): r has {out}'s "
                      "base color but other variant colors")
    assert got[1] == (f"note: scarf.px has no @variant dusk (it has night), so the keys layer 1 ({b}:s) adds to {out} "
                      "(a) stay at base colors in its dusk; --variant-map dusk=night reads its night as dusk")
    assert got[2] == f"wrote {out} frame b"
    doc = pxart.parse(out)
    assert doc.get("b").grid == ["a."] and doc.palette["a"] == pxart.hex2rgba("#c4473a")
    assert doc.variants == {"dusk": {"r": pxart.hex2rgba("#a33a4c")}}  # the scarf stays at its base color at dusk
    assert doc.image(doc.get("b"), "dusk").getpixel((0, 0)) == pxart.hex2rgba("#c4473a")
    assert doc.image(doc.get("a"), "dusk").getpixel((0, 0)) == pxart.hex2rgba("#a33a4c")  # the awning as it was


def test_variant_clash_existing_out_variant_map_reads_night_as_dusk(tmp_path, capsys):
    b = write(tmp_path, "scarf.px", SCARF)
    out = write(tmp_path, "o.px", AWNING)
    assert run("compose", "-o", f"{out}:b", f"{b}:s@0,0", "--rekey", "--variant-map", "dusk=night") == 0
    got = capsys.readouterr().out
    assert "'r>a'" in got and "stay at base colors" not in got
    doc = pxart.parse(out)
    assert doc.get("b").grid == ["a."]
    assert doc.variants["dusk"] == {"r": pxart.hex2rgba("#a33a4c"), "a": pxart.hex2rgba("#83344e")}


def test_variant_clash_existing_out_second_compose_reuses_the_split_key(tmp_path, capsys):
    # Composing from the same file again with the same map finds OUT's 'a' looks like the scarf's r everywhere.
    b = write(tmp_path, "scarf.px", SCARF)
    out = write(tmp_path, "o.px", AWNING)
    run("compose", "-o", f"{out}:b", f"{b}:s@0,0", "--rekey", "--variant-map", "dusk=night")
    before = dict(pxart.parse(out).palette)
    capsys.readouterr()
    assert run("compose", "-o", f"{out}:c", f"{b}:s@0,0", "--rekey", "--variant-map", "dusk=night") == 0
    assert "'r>a'" in capsys.readouterr().out
    doc = pxart.parse(out)
    assert doc.get("c").grid == ["a."] and dict(doc.palette) == before


def test_variant_clash_existing_out_new_keys_get_their_variant_colors(tmp_path, capsys):
    # A key OUT hasn't got comes with the layer's colors in OUT's variants of the same name.
    b = write(tmp_path, "lamp.px", "q #fff4b0\nz #223344\n@variant dusk\nz #111111\nq #fff4b0\n@frame l\nqz\n")
    out = write(tmp_path, "o.px", AWNING)
    assert run("compose", "-o", f"{out}:b", f"{b}:l@0,0") == 0
    doc = pxart.parse(out)
    assert doc.variants["dusk"]["z"] == pxart.hex2rgba("#111111")
    assert doc.variants["dusk"]["q"] == pxart.hex2rgba("#fff4b0")  # listed in its base color: a lamp kept lit
    assert "note:" not in capsys.readouterr().out


def test_variant_map_existing_out_needs_the_name_in_out(tmp_path):
    a = write(tmp_path, "scarf.px", SCARF)
    out = write(tmp_path, "o.px", AWNING)
    before = out.read_text()
    msg = run_err("compose", "-o", f"{out}:b", f"{a}:s@0,0", "--variant-map", "eve=night")
    assert "E_SELECT" in msg and f"{out} has no @variant 'eve' (it has: dusk)" in msg and out.read_text() == before


def test_new_keys_fits_skips_a_same_color_key_that_looks_different(tmp_path):
    pick = pxart.new_keys(["r"], {"r": (1, 1, 1, 255)}, {"z": (1, 1, 1, 255), "q": (2, 2, 2, 255)}, {"z", "q", "r"},
                          fits=lambda k, c: c != "z")
    assert pick["r"] not in ("z", "q", "r")
    assert pxart.new_keys(["r"], {"r": (1, 1, 1, 255)}, {"z": (1, 1, 1, 255)}, {"z", "r"}) == {"r": "z"}


# ---------------------------------------------------------------- compose --variant-map

def test_variant_map_bad_syntax(tmp_path):
    a = write(tmp_path, "awning.px", AWNING)
    for bad in ("dusk", "dusk=", "=night", "base=night", "du sk=night", "dusk=ni/ght"):
        msg = run_err("compose", "-o", tmp_path / "o.px", f"{a}:a@0,0", "--variant-map", bad)
        assert "E_BAD_ARG" in msg and "NAME=V1,V2" in msg, bad


def test_variant_map_one_source_in_two_maps(tmp_path, capsys):
    # The map adds: one file's night may be OUT's dusk and OUT's eve both.
    a = write(tmp_path, "a.px", "r #c4473a\n@variant night\nr #000001\n@frame a\nr\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}:a@0,0", "--variant-map", "dusk=night", "--variant-map", "eve=night") == 0
    assert pxart.parse(out).variants == {"dusk": {"r": (0, 0, 1, 255)}, "eve": {"r": (0, 0, 1, 255)}}


def test_variant_map_same_name_mapped_twice(tmp_path):
    a = write(tmp_path, "awning.px", AWNING)
    msg = run_err("compose", "-o", tmp_path / "o.px", f"{a}:a@0,0", "--variant-map", "dusk=night",
                  "--variant-map", "dusk=dark")
    assert "E_BAD_ARG" in msg and "'dusk' is mapped twice (dusk=night and dusk=dark)" in msg
    assert "dusk=V1,V2" in msg and not (tmp_path / "o.px").exists()


def test_variant_map_unknown_source(tmp_path):
    a = write(tmp_path, "awning.px", AWNING)
    msg = run_err("compose", "-o", tmp_path / "o.px", f"{a}:a@0,0", "--variant-map", "dusk=nigth")
    assert "E_SELECT" in msg and "no layer's file has @variant 'nigth' (they have: dusk)" in msg
    assert not (tmp_path / "o.px").exists()


def test_variant_map_existing_out_reads_the_layers_variants(tmp_path, capsys):
    a = write(tmp_path, "awning.px", AWNING)
    out = write(tmp_path, "o.px", AWNING)
    assert run("compose", "-o", f"{out}:b", f"{a}:a@0,0", "--variant-map", "dusk=dusk") == 0
    assert capsys.readouterr().out == f"wrote {out} frame b\n"
    assert pxart.parse(out).get("b").grid == ["rk"]


def test_variant_map_renames_one_files_variant(tmp_path, capsys):
    a, b = write(tmp_path, "awning.px", AWNING), write(tmp_path, "scarf.px", SCARF)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1", "--rekey",
               "--variant-map", "dusk=night") == 0
    doc = pxart.parse(out)
    assert set(doc.variants) == {"dusk"}
    assert looks_as_its_file(out, [(a, "a", 0, 0), (b, "s", 0, 1)], {"dusk": ["dusk", "night"]})


def test_variant_map_same_red_both_dimmed_needs_no_rekey_when_colors_agree(tmp_path, capsys):
    # Merged, the two reds dim to the same color: one key is enough.
    a = write(tmp_path, "a.px", "r #c4473a\n@variant dusk\nr #a33a4c\n@frame a\nr\n")
    b = write(tmp_path, "b.px", "r #c4473a\n@variant night\nr #a33a4c\n@frame b\nr\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:a@0,0", f"{b}:b@1,0", "--rekey",
               "--variant-map", "dusk=night") == 0
    assert "--rekey gives" not in capsys.readouterr().out and pxart.parse(out).frames[0].grid == ["rr"]


def test_variant_map_first_listed_variant_a_file_has_wins(tmp_path, capsys):
    a = write(tmp_path, "a.px", "r #c4473a\n@variant night\nr #000001\n@variant dark\nr #000002\n@frame a\nr\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}:a@0,0", "--variant-map", "dusk=dark,night") == 0
    # dusk takes dark; night, which the map didn't read as dusk here, stays a variant of its own (the map adds)
    assert pxart.parse(out).variants == {"dusk": {"r": (0, 0, 2, 255)}, "night": {"r": (0, 0, 1, 255)}}


def test_variant_map_leaves_unmapped_variants_alone(tmp_path, capsys):
    a = write(tmp_path, "a.px", "r #c4473a\n@variant night\nr #000001\n@variant dawn\nr #000003\n@frame a\nr\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}:a@0,0", "--variant-map", "dusk=night") == 0
    assert pxart.parse(out).variants == {"dusk": {"r": (0, 0, 1, 255)}, "dawn": {"r": (0, 0, 3, 255)}}


def test_variant_map_inlines_a_shared_import(tmp_path, capsys):
    write(tmp_path, "pal.px", "r #c4473a\n@variant night\nr #000001\n")
    a = write(tmp_path, "a.px", "@palette pal.px\n@frame a\nr\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}:a@0,0", "--variant-map", "dusk=night") == 0
    doc = pxart.parse(out)
    assert doc.palette_refs == [] and doc.variants == {"dusk": {"r": (0, 0, 1, 255)}}


def test_variant_map_without_rekey_still_notes_a_clash(tmp_path, capsys):
    a, b = write(tmp_path, "awning.px", AWNING), write(tmp_path, "scarf.px", SCARF)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1", "--variant-map", "dusk=night") == 0
    assert "draws 'r' #c4473a in " in (got := capsys.readouterr().out)
    assert "variant colors, not scarf.px's: dusk #a33a4c (scarf.px: #83344e)" in got


# ---------------------------------------------------------------- compose: left-out keys, one line per file

def test_left_out_two_layers_of_one_file_one_line(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nz #ffffff\n@frame x\nk\n@frame y\nk\n")
    b = write(tmp_path, "b.px", "z #ff0000\n@frame z\nz\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "3x1", f"{a}:x@0,0", f"{a}:y@1,0", f"{b}:z@2,0") == 0
    lines = [l for l in capsys.readouterr().out.splitlines() if "leaves out" in l]
    assert lines == [f"note: {out} leaves out layers 1-2 ({a})'s colors for z, a key those layers don't draw with (so it "
                     f"doesn't conflict), and has other layers' colors for it: 'z' #ffffff (#ff0000 there, from layer "
                     f"3 ({b}:z), which draws with it)"]


def test_left_out_key_drawn_elsewhere_in_its_file_is_a_warning(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nl #ffff00\n@frame x\nk\n@frame lamp\nl\n")
    b = write(tmp_path, "b.px", "l #ff0000\n@frame z\nl\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:z@1,0") == 0
    assert capsys.readouterr().out.splitlines()[0] == (
        f"WARNING: {out} leaves out layer 1 ({a}:x)'s colors for l, a key that layer doesn't draw with (so it doesn't "
        f"conflict), and has other layers' colors for it: 'l' #ffff00 (#ff0000 there, from layer 2 ({b}:z), which "
        f"draws with it; a.px needs it: its frame lamp draws with it); compose --rekey keeps l under free keys in {out}")


def test_left_out_relisted_key_is_a_warning(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nl #ffff00\n@variant night\nk #000011\nl #ffff00\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "l #ff0000\n@frame z\nl\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:z@1,0") == 0
    assert (f"'l' #ffff00 (#ff0000 there, from layer 2 ({b}:z), which draws with it; a.px needs it: @variant night "
            "relists it unchanged)") in capsys.readouterr().out


def test_left_out_key_kept_out_of_a_dark_variant_is_a_warning(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nw #ffffff\nc #808080\nf #ffe07a\n@variant dark\nk #000011\nw #111111\n"
                                "c #222222\n@frame x\nkwc\n")
    b = write(tmp_path, "b.px", "f #ff0000\n@frame z\nf\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "4x1", f"{a}:x@0,0", f"{b}:z@3,0") == 0
    assert (f"'f' #ffe07a (#ff0000 there, from layer 2 ({b}:z), which draws with it; a.px needs it: @variant dark keeps "
            "it while it recolors most keys)") in capsys.readouterr().out


def test_left_out_plain_key_is_a_note(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nz #ffffff\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "z #ff0000\n@frame z\nz\n")
    out = tmp_path / "o.px"
    run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:z@1,0")
    got = capsys.readouterr().out
    assert "WARNING" not in got and got.startswith("note: ")


def test_left_out_warning_rekey_keeps_the_key(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nl #ffff00\n@frame x\nk\n@frame lamp\nl\n")
    b = write(tmp_path, "b.px", "l #ff0000\n@frame z\nl\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:z@1,0", "--rekey") == 0
    got = capsys.readouterr().out
    assert got.splitlines()[0] == (f"note: --rekey gives {a}'s keys free ones in {out}: 'l>a' ({a} is unchanged): its "
                                   "layers here don't draw with l, but a.px needs it (l: its frame lamp draws with it)")
    assert "WARNING" not in got and "leaves out" not in got
    assert pxart.parse(out).palette == {"k": (0, 0, 0, 255), "l": (255, 0, 0, 255), "a": (255, 255, 0, 255)}


def test_left_out_warning_rekey_not_for_plain_keys(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nz #ffffff\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "z #ff0000\n@frame z\nz\n")
    out = tmp_path / "o.px"
    run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:z@1,0", "--rekey")
    got = capsys.readouterr().out
    assert "--rekey gives" not in got and "leaves out layer 1" in got


def test_special_keys(tmp_path):
    doc = pxart.parse(write(tmp_path, "s.px", "k #000000\nl #ffff00\nq #123456\nf #ffe07a\nw #ffffff\n"
                                              "@variant night\nk #000011\nl #ffff00\nw #111111\nq #222222\n"
                                              "@frame a\nk\n@frame b\nq\n"))
    why = pxart.special_keys(doc)
    assert why == {"k": ["its frame a draws with it"], "q": ["its frame b draws with it"],
                   "l": ["@variant night relists it unchanged"],
                   "f": ["@variant night keeps it while it recolors most keys"]}


def test_special_keys_a_variant_recoloring_few_keeps_nothing_special(tmp_path):
    doc = pxart.parse(write(tmp_path, "s.px", "k #000000\na #111111\nb #222222\nc #333333\n@variant v\nk #000011\n"
                                              "@frame a\nk\n"))
    assert pxart.special_keys(doc) == {"k": ["its frame a draws with it"]}


# ---------------------------------------------------------------- compose: palette comments come along

def test_compose_carries_key_and_variant_comments(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\n# glow: left out of dusk\nf #ffe07a\n\n# dusk: dim\n@variant dusk\n"
                                "# the dark outline\nk #000011\n@frame x\nkf\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}:x@0,0") == 0
    assert out.read_text() == ("pxart 1\nk #000000\n# glow: left out of dusk\nf #ffe07a\n\n# dusk: dim\n@variant dusk\n"
                               "# the dark outline\nk #000011\n\nkf\n")


def test_compose_carries_comments_from_the_layers_imports(tmp_path, capsys):
    write(tmp_path, "pal.px", "# header\npxart 1\n# ink\nk #000000\n")
    write(tmp_path, "pal2.px", "pxart 1\n# the sun\ny #ffff00\n")
    a = write(tmp_path, "a.px", "@palette pal.px\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "@palette pal2.px\n@frame y\ny\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:y@1,0") == 0
    # the palette files' headers come too, at the top, each saying whose it is
    assert out.read_text() == ("pxart 1\n\n# header (from a.px)\n\n# ink (from a.px)\nk #000000\n# the sun (from b.px)\n"
                               "y #ffff00\n\nky\n")


def test_compose_comment_of_a_left_out_key_goes(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\n# a white\nz #ffffff\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "pxart 1\n# a red\nz #ff0000\n@frame y\nz\n")
    out = tmp_path / "o.px"
    run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:y@1,0")
    assert "# a red (from b.px)\nz #ff0000" in out.read_text() and "# a white" not in out.read_text()


def test_compose_a_sprites_header_comment_stays_with_it(tmp_path, capsys):
    # Comments above a file's first line are its header, about the sprite: not a key's comment.
    a = write(tmp_path, "a.px", "# the hero\nk #000000\n@frame x\nk\n")
    out = tmp_path / "o.px"
    run("compose", "-o", out, f"{a}:x@0,0")
    assert "# the hero" not in out.read_text()


def test_compose_comments_not_for_an_existing_out(tmp_path, capsys):
    a = write(tmp_path, "a.px", "pxart 1\n# ink\nk #000000\n@frame x\nk\n")
    out = write(tmp_path, "o.px", "w #ffffff\n@frame y\nw\n")
    run("compose", "-o", f"{out}:z", f"{a}:x@0,0")
    assert "# ink" not in out.read_text()


def test_compose_used_keys_only_drops_the_comments_of_dropped_keys(tmp_path, capsys):
    a = write(tmp_path, "a.px", "pxart 1\n# ink\nk #000000\n# unused\nz #ffffff\n@frame x\nk\n")
    out = tmp_path / "o.px"
    run("compose", "-o", out, f"{a}:x@0,0", "--used-keys-only")
    assert out.read_text() == "pxart 1\n# ink\nk #000000\n\nk\n"


def test_compose_rekey_renamed_key_comment_says_so(tmp_path, capsys):
    a = write(tmp_path, "a.px", "s #111111\n@frame x\ns\n")
    b = write(tmp_path, "b.px", "pxart 1\n# grass (s) and its shadow\ns #00ff00\n@frame y\ns\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:y@1,0", "--rekey") == 0
    assert "# grass (s) and its shadow (renamed s>a; from b.px)\na #00ff00" in out.read_text()


def test_compose_rekey_renamed_key_own_comment_without_the_letter(tmp_path, capsys):
    a = write(tmp_path, "a.px", "s #111111\n@frame x\ns\n")
    b = write(tmp_path, "b.px", "pxart 1\n# grass\ns #00ff00\n@frame y\ns\n")
    out = tmp_path / "o.px"
    run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:y@1,0", "--rekey")
    assert "# grass (renamed s>a; from b.px)\na #00ff00" in out.read_text()


def test_renamed_lead_words_and_punctuation():
    lead = ["", "# a lamp (l, g) stays lit; the glass", "# kl is not l"]
    assert pxart.renamed_lead(lead, {"l": "P", "g": "Q"}) == [
        "", "# a lamp (l, g) stays lit; the glass (renamed l>P g>Q)", "# kl is not l (renamed l>P)"]


def test_renamed_lead_punctuation_keys_only_by_their_own_line():
    assert pxart.renamed_lead(["# 50% gray"], {"%": "a"}) == ["# 50% gray"]
    assert pxart.renamed_lead(["# 50% gray"], {"%": "a"}, ("%", "a")) == ["# 50% gray (renamed %>a)"]


def test_renamed_lead_own_key_already_named():
    assert pxart.renamed_lead(["# l: the lamp"], {"l": "P"}, ("l", "P")) == ["# l: the lamp (renamed l>P)"]


def test_renamed_lead_blank_only_lead_unchanged():
    assert pxart.renamed_lead(["", ""], {"l": "P"}, ("l", "P")) == ["", ""]


def test_recolor_rename_keeps_a_relist(tmp_path, capsys):
    # 'l>L' where night lists l in its base color (kept lit): L is listed the same way, not left to inherit.
    write(tmp_path, "pal.px", "l #fff4b0\nk #000000\n@variant night\nk #000011\nl #fff4b0\n")
    p = write(tmp_path, "s.px", "@palette pal.px\n@frame a\nkl\n")
    assert run("recolor", p, "l>L") == 0
    doc = pxart.parse(p)
    assert doc.variants == {"night": {"L": (0xff, 0xf4, 0xb0, 255)}} and doc.frames[0].grid == ["kL"]


def test_help_documents_compose_across_packs(capsys):
    doc = " ".join(pxart.__doc__.split())
    assert "That line is a WARNING when the file needs a key it lost" in doc
    assert "--rekey then keeps such keys under free keys in OUT" in doc
    assert "The comments above the layers' key and @variant lines come along, as for palette --extract-to" in doc
    assert "'# lamp colors (l, g) stay lit (renamed l>I g>J)'" in doc
    assert "so one file's variant never recolors another file's pixels" in doc
    assert "--variant-map dusk=night,dark (repeatable) builds OUT's dusk from each layer's first of dusk, night, dark" \
        in doc
    assert "--rekey gives such a key a free key of its own" in doc
    out = " ".join(cmd_help(capsys, "compose").split())
    assert "--variant-map" in out and "WARNING" in out
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`--variant-map dusk=night,dark` merges several files' variants into one" in readme
    assert "a key two files have in one color but recolor differently in their variants" in readme


# ---------------------------------------------------------------- notes only for writes that happen

def test_unsaid_drops_notes_and_warnings_keeps_the_rest():
    text = "note: a\nwrote x.png\nWARNING: b\n  walk/0  vs walk/1\nnote: c\n"
    assert pxart.unsaid(text) == "wrote x.png\n  walk/0  vs walk/1\n"


def test_unsaid_keeps_a_line_that_only_mentions_a_note():
    assert pxart.unsaid("a note: here\n  note: indented\n") == "a note: here\n  note: indented\n"


def test_unsaid_of_nothing():
    assert pxart.unsaid("") == ""


def test_failed_copy_to_prints_no_rename_note(tmp_path, capsys):
    # DST's unnamed grid would become '@frame d', but the copy fails: no note, and DST is as it was.
    s = write(tmp_path, "s.px", "k #000000\n@frame walk/0\nk\n")
    d = write(tmp_path, "d.px", "k #ff0000\n.\n")
    before = d.read_text()
    capsys.readouterr()
    msg = run_err("frames", s, "--copy-to", d)
    got = capsys.readouterr()
    assert "E_KEY_CONFLICT" in msg and "unnamed grid" not in got.out and "note:" not in got.out
    assert d.read_text() == before


def test_copy_to_that_succeeds_still_prints_the_rename_note(tmp_path, capsys):
    s = write(tmp_path, "s.px", "k #000000\n@frame walk/0\nk\n")
    d = write(tmp_path, "d.px", "k #000000\n.\n")
    capsys.readouterr()
    assert run("frames", s, "--copy-to", d) == 0
    out = capsys.readouterr().out
    assert f"note: {d}'s unnamed grid is now '@frame d' (the id it went by)" in out and f"wrote {d}" in out


def test_failed_compose_into_unnamed_grid_prints_no_rename_note(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nk\n")
    o = write(tmp_path, "o.px", "k #ff0000\nk\n")
    before = o.read_text()
    capsys.readouterr()
    assert "E_KEY_CONFLICT" in run_err("compose", "-o", f"{o}:x", f"{a}@0,0")
    assert "note:" not in capsys.readouterr().out and o.read_text() == before


def test_failed_edit_with_o_prints_no_whole_file_note(tmp_path, capsys):
    p = write(tmp_path, "p.px", MULTI)
    capsys.readouterr()
    assert "E_SELECT" in run_err("set", f"{p}:idle", "Z", "0,0", "-o", tmp_path / "q.px")
    assert "note:" not in capsys.readouterr().out and not (tmp_path / "q.px").exists()


def test_edit_with_o_that_succeeds_prints_the_whole_file_note(tmp_path, capsys):
    p = write(tmp_path, "p.px", MULTI)
    capsys.readouterr()
    assert run("set", f"{p}:idle", "g", "0,0", "-o", tmp_path / "q.px") == 0
    assert f"note: {tmp_path / 'q.px'} gets all of {p} with idle edited" in capsys.readouterr().out


def test_failed_rekey_prints_no_rekey_note(tmp_path, capsys):
    # --rekey found moves, then the copy fails on a duplicate frame: the rekey note would describe a write that
    # didn't happen.
    s = write(tmp_path, "s.px", "k #000000\n@frame walk/0\nk\n")
    d = write(tmp_path, "d.px", "k #ff0000\n@frame walk/0\nk\n")
    capsys.readouterr()
    assert "E_DUP_FRAME" in run_err("frames", s, "--copy-to", d, "--rekey")
    assert "note:" not in capsys.readouterr().out


def test_failed_put_prints_no_size_note(tmp_path, capsys, monkeypatch):
    import io
    p = write(tmp_path, "p.px", "k #000000\n@frame a\nkk\n")
    before = p.read_text()
    monkeypatch.setattr("sys.stdin", io.StringIO("k #ff0000\nk\n"))
    capsys.readouterr()
    assert "E_KEY_CONFLICT" in run_err("put", f"{p}:a")
    assert "note:" not in capsys.readouterr().out and p.read_text() == before


def test_check_output_still_printed_when_it_exits_1(tmp_path, capsys):
    bad = write(tmp_path, "bad.px", "k #000000\nkq\n")
    good = write(tmp_path, "good.px", "k #000000\nk\n")
    assert run("check", good, bad) == 1
    out = capsys.readouterr().out
    assert "good.px" in out and "E_UNKNOWN_KEY" in out


def test_successful_command_output_is_in_order(tmp_path, capsys):
    p = write(tmp_path, "p.px", MULTI)
    capsys.readouterr()
    assert run("set", f"{p}:idle", "g", "0,0", "-o", tmp_path / "q.px") == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("note:") and lines[-1] == f"wrote {tmp_path / 'q.px'}"


def test_help_and_readme_say_a_failed_command_prints_no_notes():
    doc = " ".join(pxart.__doc__.split())
    assert "A command that fails prints none of its notes or WARNINGs" in doc
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "A command that fails prints no notes or WARNINGs" in readme


# ---------------------------------------------------------------- new --empty

def empty_pal(tmp_path):
    return write(tmp_path, "pal.px", "# shared\nk #000000\nw #ffffff\n@variant night\nk #000011\n")


def test_new_empty_with_palette_writes_only_the_import(tmp_path, capsys):
    pal = empty_pal(tmp_path)
    out = tmp_path / "party.px"
    assert run("new", out, "--empty", "--palette", pal) == 0
    assert out.read_text() == "pxart 1\n@palette pal.px\n"
    assert capsys.readouterr().out == f"wrote {out} (no frames; imports pal.px)\n"


def test_new_empty_without_palette_is_the_version_line(tmp_path, capsys):
    out = tmp_path / "e.px"
    assert run("new", out, "--empty") == 0
    assert out.read_text() == "pxart 1\n" and capsys.readouterr().out == f"wrote {out} (no frames)\n"


def test_new_empty_repoints_the_palette_from_a_subdirectory(tmp_path):
    empty_pal(tmp_path)
    out = tmp_path / "a" / "b" / "party.px"
    assert run("new", out, "--empty", "--palette", tmp_path / "pal.px") == 0
    assert out.read_text() == "pxart 1\n@palette ../../pal.px\n"
    assert pxart.parse(out, allow_empty=True).resolved()["w"] == (255, 255, 255, 255)


def test_new_empty_file_parses_as_a_palette_file(tmp_path):
    pal = empty_pal(tmp_path)
    out = tmp_path / "party.px"
    run("new", out, "--empty", "--palette", pal)
    doc = pxart.parse(out, palette_only=True)
    assert doc.frames == [] and doc.palette == {} and doc.shared_variants["night"]["k"] == (0, 0, 0x11, 255)


def test_new_empty_then_copy_to_fills_it(tmp_path, capsys):
    pal = empty_pal(tmp_path)
    out = tmp_path / "party.px"
    run("new", out, "--empty", "--palette", pal)
    s = write(tmp_path, "s.px", "@palette pal.px\n@anim walk ms=90\n@frame walk/0\nkw\n@frame walk/1\nwk\n")
    capsys.readouterr()
    assert run("frames", f"{s}:walk", "--copy-to", out) == 0
    got = capsys.readouterr().out
    assert "note:" not in got and got == f"copied walk/0, walk/1 to {out}; added @anim walk; wrote {out}\n"
    assert out.read_text() == ("pxart 1\n@palette pal.px\n\n@anim walk ms=90\n\n@frame walk/0\nkw\n\n"
                               "@frame walk/1\nwk\n")


def test_new_empty_then_compose_frame_fills_it(tmp_path):
    pal = empty_pal(tmp_path)
    out = tmp_path / "party.px"
    run("new", out, "--empty", "--palette", pal)
    s = write(tmp_path, "s.px", "@palette pal.px\n@frame a\nkw\n")
    assert run("compose", "-o", f"{out}:x", f"{s}:a@0,0") == 0
    doc = pxart.parse(out)
    assert [f.id for f in doc.frames] == ["x"] and doc.frames[0].grid == ["kw"] and doc.palette == {}


def test_new_empty_check_and_frames_accept_it(tmp_path, capsys):
    pal = empty_pal(tmp_path)
    out = tmp_path / "party.px"
    run("new", out, "--empty", "--palette", pal)
    capsys.readouterr()
    assert run("check", out, "--strict") == 0
    assert run("frames", out) == 0


@pytest.mark.parametrize("extra, bit", [
    (["--size", "2x2"], "--size"),
    (["--key", "k"], "--key"),
    (["--still"], "--still"),
    (["--size", "2x2", "--key", "k"], "--size, --key"),
])
def test_new_empty_rejects_frame_flags(tmp_path, extra, bit):
    pal = empty_pal(tmp_path)
    out = tmp_path / "party.px"
    msg = run_err("new", out, "--empty", "--palette", pal, *extra)
    assert "E_BAD_ARG" in msg and f"so {bit} has nothing to apply to" in msg and not out.exists()


def test_new_empty_rejects_a_frame_selector(tmp_path):
    out = tmp_path / "party.px"
    msg = run_err("new", f"{out}:walk/0", "--empty")
    assert "E_BAD_ARG" in msg and "drop :walk/0" in msg and not out.exists()


def test_new_empty_rejects_an_existing_file(tmp_path):
    p = write(tmp_path, "p.px", MULTI)
    msg = run_err("new", p, "--empty")
    assert "E_BAD_ARG" in msg and "exists" in msg and p.read_text() == MULTI


def test_new_empty_with_palette_rejects_an_existing_file(tmp_path):
    pal = empty_pal(tmp_path)
    p = write(tmp_path, "p.px", MULTI)
    assert "E_BAD_ARG" in run_err("new", p, "--empty", "--palette", pal) and p.read_text() == MULTI


def test_new_empty_missing_palette_is_an_error(tmp_path):
    out = tmp_path / "party.px"
    msg = run_err("new", out, "--empty", "--palette", tmp_path / "no.px")
    assert "E_PALETTE_FILE" in msg and not out.exists()


def test_new_without_size_or_empty_says_which(tmp_path):
    out = tmp_path / "a.px"
    msg = run_err("new", out)
    assert "E_BAD_ARG" in msg and "--size WxH" in msg and "--empty" in msg and not out.exists()


def test_copy_to_missing_dst_hint_names_new_empty(tmp_path):
    s = write(tmp_path, "s.px", CSRC)
    d = tmp_path / "no.px"
    msg = run_err("frames", f"{s}:walk", "--copy-to", d)
    assert f"pxart extract {s}:walk -o {d}" in msg and f"pxart new {d} --empty --palette P.px" in msg
    assert "with these frames and" in msg and not d.exists()


def test_new_help_has_both_usage_lines(capsys):
    out = cmd_help(capsys, "new")
    assert "  new OUT[:frame] --size WxH" in out and "  new OUT --empty [--palette P.px]" in out
    assert "--empty starts a new OUT with no frames" in out and "'new party.px --empty --palette palette.px'" in out


def test_reference_takes_a_second_usage_line_of_the_same_command():
    sec = pxart.reference("new")
    assert sec.splitlines()[1] == "  new OUT --empty [--palette P.px]" and "--empty starts" in sec


def test_frames_help_says_how_to_start_dst(capsys):
    out = " ".join(cmd_help(capsys, "frames").split())
    assert "'new DST --empty --palette P.px' one with no frames that imports P" in out


def test_readme_documents_new_empty():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`new party.px --empty --palette palette.px` starts a file with no frames that imports a palette" in readme


# ---------------------------------------------------------------- every path that imports keys is variant-aware
# The keeper's scarf r and the market's awning r share a base color (#c4473a) but not a dusk: the awning's file dims it
# to #a33a4c, the keeper's file has no dusk (its night makes the scarf #83344e). copy-to, paste, crop and compose into
# an existing file used to keep r as one key, so the scarf took the awning's dusk.

SCARF_WALK = ("r #c4473a\nk #000000\nq #fff4b0\n@variant night\nr #83344e\nk #000011\nq #fff4b0\n"
              "@anim walk ms=90\n@frame walk/0\nrk\nq.\n@frame walk/1\nkr\n.q\n")
MARKET = "r #c4473a\nk #000000\n@variant dusk\nr #a33a4c\n@frame awning\nrk\n"


def scarf_market(tmp_path, market=MARKET):
    return write(tmp_path, "keeper.px", SCARF_WALK), write(tmp_path, "party.px", market)


def dusk_of(path, fid, xy=(0, 0)):
    doc = pxart.parse(path)
    return doc.image(doc.get(fid), "dusk").getpixel(xy)


def test_copy_to_rekey_splits_a_key_whose_variants_differ(tmp_path, capsys):
    s, d = scarf_market(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey") == 0
    got = capsys.readouterr().out
    assert got.splitlines()[0] == f"note: --rekey gives {s}'s keys free ones in {d}: 'r>a' ({s} is unchanged)"
    doc = pxart.parse(d)
    assert doc.get("walk/0").grid == ["ak", "q."] and doc.get("awning").grid == ["rk"]
    assert dusk_of(d, "walk/0") == pxart.hex2rgba("#c4473a")  # the scarf: its file has no dusk, so base
    assert dusk_of(d, "awning") == pxart.hex2rgba("#a33a4c")  # the awning, as the market dims it


def test_copy_to_without_rekey_notes_the_shared_key(tmp_path, capsys):
    s, d = scarf_market(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d) == 0
    got = capsys.readouterr().out
    assert (f"WARNING: FILE ({s}:walk) draws 'r' #c4473a in {d}'s variant colors, not keeper.px's: dusk #a33a4c "
            "(keeper.px: #c4473a); frames --copy-to --rekey r gives it a key of its own") in got.splitlines()
    assert pxart.parse(d).get("walk/0").grid == ["rk", "q."]


def test_copy_to_note_names_every_key_that_differs(tmp_path, capsys):
    # The market dims its outline k at dusk too: one WARNING per key, and --rekey moves both.
    s, d = scarf_market(tmp_path, MARKET.replace("@variant dusk\n", "@variant dusk\nk #000011\n"))
    run("frames", f"{s}:walk", "--copy-to", d)
    got = [l for l in capsys.readouterr().out.splitlines() if l.startswith("WARNING:")]
    assert got == [f"WARNING: FILE ({s}:walk) draws 'k' #000000 in {d}'s variant colors, not keeper.px's: dusk #000011 "
                   "(keeper.px: #000000); frames --copy-to --rekey k gives it a key of its own",
                   f"WARNING: FILE ({s}:walk) draws 'r' #c4473a in {d}'s variant colors, not keeper.px's: dusk #a33a4c "
                   "(keeper.px: #c4473a); frames --copy-to --rekey r gives it a key of its own"]


def test_copy_to_rekey_moves_every_key_that_differs(tmp_path, capsys):
    s, d = scarf_market(tmp_path, MARKET.replace("@variant dusk\n", "@variant dusk\nk #000011\n"))
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey") == 0
    assert f"free ones in {d}: 'k>a' 'r>b'" in capsys.readouterr().out
    assert pxart.parse(d).get("walk/0").grid == ["ba", "q."]


def test_copy_to_rekey_with_variant_map_reads_night_as_dusk(tmp_path, capsys):
    s, d = scarf_market(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "--variant-map", "dusk=night") == 0
    got = capsys.readouterr().out
    assert "stay at base colors" not in got
    doc = pxart.parse(d)
    new = doc.get("walk/0").grid[0][0]
    assert new not in ("r", "k") and doc.variants["dusk"][new] == pxart.hex2rgba("#83344e")
    assert dusk_of(d, "walk/0") == pxart.hex2rgba("#83344e") and dusk_of(d, "awning") == pxart.hex2rgba("#a33a4c")


def test_copy_to_rekey_reuses_a_key_that_looks_the_same_in_every_variant(tmp_path, capsys):
    # DST already has the scarf as I (base and dusk as the keeper's night reads): --rekey with the map picks I, not a
    # free key, and not r (same base, other dusk).
    s, d = scarf_market(tmp_path, MARKET.replace("k #000000\n", "k #000000\nI #c4473a\n").replace(
        "@variant dusk\n", "@variant dusk\nI #83344e\n"))
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "--variant-map", "dusk=night") == 0
    assert "'r>I'" in capsys.readouterr().out
    assert pxart.parse(d).get("walk/0").grid[0][0] == "I"


def test_copy_to_rekey_skips_a_same_base_key_that_looks_different(tmp_path, capsys):
    # Without the map the scarf stays base at dusk: I (dusk #83344e) doesn't fit, and neither does r: a free key.
    s, d = scarf_market(tmp_path, MARKET.replace("k #000000\n", "k #000000\nI #c4473a\n").replace(
        "@variant dusk\n", "@variant dusk\nI #83344e\n"))
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey") == 0
    key = pxart.parse(d).get("walk/0").grid[0][0]
    assert key not in ("r", "I") and dusk_of(d, "walk/0") == pxart.hex2rgba("#c4473a")


def test_copy_to_new_keys_come_with_their_variant_colors_by_map(tmp_path):
    s, d = scarf_market(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "--variant-map", "dusk=night") == 0
    doc = pxart.parse(d)
    assert doc.variants["dusk"]["q"] == pxart.hex2rgba("#fff4b0")  # the lamp, relisted as kept lit


def test_copy_to_new_keys_without_map_stay_base_and_say_so(tmp_path, capsys):
    s, d = scarf_market(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d) == 0
    assert "q" not in pxart.parse(d).variants["dusk"]
    assert (f"note: keeper.px has no @variant dusk (it has night), so the keys FILE ({s}:walk) adds to {d} (q) stay "
            "at base colors in its dusk; --variant-map dusk=night reads its night as dusk") \
        in capsys.readouterr().out.splitlines()


def test_copy_to_variant_map_unknown_source_variant(tmp_path):
    s, d = scarf_market(tmp_path)
    before = d.read_text()
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--variant-map", "dusk=nigth")
    assert "E_SELECT" in msg and "no source file has @variant 'nigth' (they have: night)" in msg
    assert d.read_text() == before


def test_copy_to_variant_map_name_dst_lacks(tmp_path):
    s, d = scarf_market(tmp_path)
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--variant-map", "eve=night")
    assert "E_SELECT" in msg and f"{d} has no @variant 'eve' (it has: dusk)" in msg


def test_copy_to_variant_map_bad_syntax(tmp_path):
    s, d = scarf_market(tmp_path)
    assert "E_BAD_ARG" in run_err("frames", f"{s}:walk", "--copy-to", d, "--variant-map", "dusk")


def test_copy_to_key_conflict_suggestion_is_what_rekey_gives(tmp_path, capsys):
    # k is another color in DST. DST's R is the keeper's black, but DST dims R at dusk and the keeper (no dusk) doesn't:
    # neither the error's suggestion nor --rekey reuses R.
    market = MARKET.replace("k #000000", "k #101010").replace("@variant dusk\n", "R #000000\n@variant dusk\n"
                                                                                   "R #000011\n")
    s, d = scarf_market(tmp_path, market)
    msg = run_err("frames", f"{s}:walk", "--copy-to", d)
    suggested = next(m for m in fix_of(msg) if m.startswith("k>"))
    assert "E_KEY_CONFLICT" in msg and suggested != "k>R"
    capsys.readouterr()
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey") == 0
    assert shlex_quote(suggested) in capsys.readouterr().out


def test_copy_to_key_conflict_suggestion_reuses_a_key_that_fits(tmp_path, capsys):
    # DST's K is the keeper's black and stays black at dusk, as the keeper's k does: suggested and reused.
    market = MARKET.replace("k #000000", "k #101010").replace("@variant dusk\n", "K #000000\n@variant dusk\n")
    s, d = scarf_market(tmp_path, market)
    msg = run_err("frames", f"{s}:walk", "--copy-to", d)
    assert "k>K" in fix_of(msg)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey") == 0
    assert pxart.parse(d).get("walk/0").grid[0][1] == "K"


def shlex_quote(s):
    import shlex
    return shlex.quote(s)


def test_copy_to_same_variants_no_note_no_split(tmp_path, capsys):
    # Both files dim r the same way at dusk: one key, no note.
    s = write(tmp_path, "s.px", "r #c4473a\n@variant dusk\nr #a33a4c\n@frame a\nr\n")
    d = write(tmp_path, "d.px", "r #c4473a\n@variant dusk\nr #a33a4c\n@frame b\nr\n")
    assert run("frames", s, "--copy-to", d, "--rekey") == 0
    got = capsys.readouterr().out
    assert "note:" not in got and pxart.parse(d).get("a").grid == ["r"]


def test_copy_to_dst_without_variants_no_note(tmp_path, capsys):
    s = write(tmp_path, "s.px", SCARF_WALK)
    d = write(tmp_path, "d.px", "r #c4473a\n@frame b\nr\n")
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey") == 0
    got = capsys.readouterr().out
    assert "note:" not in got and pxart.parse(d).get("walk/0").grid[0][0] == "r"


def test_paste_rekey_splits_a_key_whose_variants_differ(tmp_path, capsys):
    s, d = scarf_market(tmp_path)
    assert run("paste", f"{s}:walk/0", "--into", f"{d}:awning", "--at", "0,0", "--rekey") == 0
    got = capsys.readouterr().out
    assert got.splitlines()[0] == f"note: --rekey gives {s}'s keys free ones in {d}: 'r>a' ({s} is unchanged)"
    doc = pxart.parse(d)
    assert doc.get("awning").grid == ["ak"] and doc.image(doc.get("awning"), "dusk").getpixel((0, 0)) == \
        pxart.hex2rgba("#c4473a")


def test_paste_without_rekey_notes_the_shared_key(tmp_path, capsys):
    s, d = scarf_market(tmp_path)
    assert run("paste", f"{s}:walk/0", "--into", f"{d}:awning", "--at", "0,0") == 0
    assert (f"WARNING: SRC ({s}:walk/0) draws 'r' #c4473a in {d}'s variant colors, not keeper.px's: dusk #a33a4c "
            "(keeper.px: #c4473a); paste --rekey r gives it a key of its own" in capsys.readouterr().out.splitlines())


def test_paste_new_keys_come_with_their_variant_colors(tmp_path, capsys):
    # Before, paste added a new key in its base color only, whatever the DST's variants.
    s = write(tmp_path, "s.px", "z #223344\n@variant dusk\nz #111111\n@frame a\nz\n")
    d = write(tmp_path, "d.px", MARKET)
    assert run("paste", s, "--into", f"{d}:awning", "--at", "0,0") == 0
    doc = pxart.parse(d)
    assert doc.variants["dusk"]["z"] == pxart.hex2rgba("#111111") and doc.get("awning").grid == ["zk"]
    assert "note:" not in capsys.readouterr().out


def test_paste_variant_map(tmp_path, capsys):
    s, d = scarf_market(tmp_path)
    assert run("paste", f"{s}:walk/0", "--into", f"{d}:awning", "--at", "0,0", "--rekey", "--variant-map",
               "dusk=night") == 0
    doc = pxart.parse(d)
    key = doc.get("awning").grid[0][0]
    assert doc.variants["dusk"][key] == pxart.hex2rgba("#83344e")


def test_paste_variant_map_name_dst_lacks(tmp_path):
    s, d = scarf_market(tmp_path)
    assert "E_SELECT" in run_err("paste", f"{s}:walk/0", "--into", f"{d}:awning", "--at", "0,0", "--variant-map",
                                 "eve=night")


def test_crop_into_existing_out_rekey_splits(tmp_path, capsys):
    s, d = scarf_market(tmp_path)
    assert run("crop", f"{s}:walk/0", "0,0,1,1", "-o", f"{d}:scarf", "--rekey") == 0
    doc = pxart.parse(d)
    key = doc.get("scarf").grid[0]
    assert key != "r" and doc.image(doc.get("scarf"), "dusk").getpixel((0, 0)) == pxart.hex2rgba("#c4473a")
    assert "'r>" in capsys.readouterr().out


def test_crop_into_existing_out_without_rekey_notes(tmp_path, capsys):
    s, d = scarf_market(tmp_path)
    assert run("crop", f"{s}:walk/0", "0,0,1,1", "-o", f"{d}:scarf") == 0
    got = capsys.readouterr().out
    assert (f"WARNING: FILE ({s}:walk/0) draws 'r' #c4473a in {d}'s variant colors, not keeper.px's: dusk #a33a4c "
            "(keeper.px: #c4473a); crop --rekey r gives it a key of its own") in got.splitlines()


def test_crop_into_existing_out_variant_map(tmp_path, capsys):
    s, d = scarf_market(tmp_path)
    assert run("crop", f"{s}:walk/0", "0,0,2,2", "-o", f"{d}:scarf", "--rekey", "--variant-map", "dusk=night") == 0
    doc = pxart.parse(d)
    assert doc.image(doc.get("scarf"), "dusk").getpixel((0, 0)) == pxart.hex2rgba("#83344e")
    assert doc.image(doc.get("scarf"), "dusk").getpixel((0, 1)) == pxart.hex2rgba("#fff4b0")


def test_compose_into_existing_out_splits_like_a_new_one(tmp_path, capsys):
    s, d = scarf_market(tmp_path)
    assert run("compose", "-o", f"{d}:both", "--size", "2x2", f"{d}:awning@0,0", f"{s}:walk/0@0,1", "--rekey") == 0
    doc = pxart.parse(d)
    g = doc.get("both").grid
    assert g[0] == "rk" and g[1][0] not in ("r", "k")
    img = doc.image(doc.get("both"), "dusk")
    assert img.getpixel((0, 0)) == pxart.hex2rgba("#a33a4c") and img.getpixel((0, 1)) == pxart.hex2rgba("#c4473a")


def test_put_stdin_key_in_files_color_keeps_files_variants(tmp_path, capsys, monkeypatch):
    # stdin has no variants: its palette lines declare FILE's own keys, so r stays r and takes FILE's dusk, no note.
    import io
    d = write(tmp_path, "d.px", MARKET)
    monkeypatch.setattr("sys.stdin", io.StringIO("r #c4473a\nkr\n"))
    assert run("put", f"{d}:awning") == 0
    got = capsys.readouterr().out
    assert "note:" not in got and pxart.parse(d).get("awning").grid == ["kr"]
    assert dusk_of(d, "awning", (1, 0)) == pxart.hex2rgba("#a33a4c")


def test_put_stdin_new_key_stays_base_in_variants(tmp_path, capsys, monkeypatch):
    import io
    d = write(tmp_path, "d.px", MARKET)
    monkeypatch.setattr("sys.stdin", io.StringIO("z #223344\nzr\n"))
    assert run("put", f"{d}:awning") == 0
    doc = pxart.parse(d)
    assert doc.palette["z"] == pxart.hex2rgba("#223344") and "z" not in doc.variants["dusk"]


def test_import_keys_helper(tmp_path):
    s = pxart.parse(write(tmp_path, "s.px", SCARF_WALK))
    d = pxart.parse(write(tmp_path, "d.px", MARKET))
    assert pxart.import_keys(d, s, {"q", "r", "k", "."}) == ["q"]
    assert "q" not in d.variants["dusk"]
    d2 = pxart.parse(tmp_path / "d.px")
    assert pxart.import_keys(d2, s, {"q"}, {"dusk": ["dusk", "night"]}) == ["q"]
    assert d2.variants["dusk"]["q"] == pxart.hex2rgba("#fff4b0")


def test_import_keys_transparent_only_with_clear(tmp_path):
    s = pxart.parse(write(tmp_path, "s.px", "z transparent\n@frame a\nz\n"))
    d = pxart.parse(write(tmp_path, "d.px", "k #000000\n@frame b\nk\n"))
    assert pxart.import_keys(d, s, {"z"}) == [] and "z" not in d.palette
    assert pxart.import_keys(d, s, {"z"}, clear=True) == ["z"] and d.palette["z"] == pxart.CLEAR


def test_vclashes_helper(tmp_path):
    s = pxart.parse(write(tmp_path, "s.px", SCARF_WALK))
    d = pxart.parse(write(tmp_path, "d.px", MARKET))
    assert pxart.vclashes(d, s, {"r", "k", "q"}) == ["r"]  # k: black at dusk in both
    assert pxart.vclashes(d, s, {"r"}, {"dusk": ["dusk", "night"]}) == ["r"]  # night's #83344e isn't dusk's #a33a4c
    plain = pxart.parse(write(tmp_path, "p.px", "r #c4473a\n@frame a\nr\n"))
    assert pxart.vclashes(plain, s, {"r"}) == []  # a DST without variants
    assert pxart.vclashes(d, d, {"r", "k"}) == []  # a file against itself


def test_colors_in_helper(tmp_path):
    s = pxart.parse(write(tmp_path, "s.px", SCARF_WALK))
    assert pxart.colors_in(s, "r", ["dusk", "night"]) == [pxart.hex2rgba("#c4473a"), pxart.hex2rgba("#83344e")]
    assert pxart.colors_in(s, "r", ["dusk"], {"dusk": ["dusk", "night"]}) == [pxart.hex2rgba("#83344e")]


def test_rekey_moves_helper(tmp_path):
    s = pxart.parse(write(tmp_path, "s.px", SCARF_WALK))
    d = pxart.parse(write(tmp_path, "d.px", MARKET))
    assert pxart.rekey_moves(d, s, {"q"}) == {}
    moves = pxart.rekey_moves(d, s, {"r", "k"})
    assert set(moves) == {"r"} and not set(moves.values()) & {"r", "k", "q"}


def test_help_documents_variant_aware_imports(capsys):
    doc = " ".join(pxart.__doc__.split())
    assert "Their keys join DST's palette and DST's variants as compose's layers join an existing OUT" in doc
    assert "--variant-map dusk=night reads FILE's night as DST's dusk" in doc
    assert "crop, paste and frames --copy-to bring keys in the same way" in doc
    assert "With an existing OUT, whose variants stay its own, the map says which of each layer's variants" in doc
    assert "Stdin has no variants: a key in FILE's color is FILE's key, variant colors and all" in doc
    assert "An existing OUT keeps its own palette, @palette and variants" in doc
    for cmd in ("paste", "crop", "frames"):
        assert "--variant-map NAME=V1,V2" in cmd_help(capsys, cmd)
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`frames keeper.px:walk --copy-to party.px --rekey --variant-map dusk=night` reads the keeper's night" in readme


# ---------------------------------------------------------------- compose's report: one summary per source file
# The crossover repro: the market's tiles and the kid don't draw with S, the keeper does (in another color). The note
# for the market said its S was left out "for layer 3's" while layer 3's conflict didn't list S; a WARNING said the
# kid's file "draws with" S, meaning frames that weren't being composed.

R_TILES = "pxart 1\nk #2b1e2f\ng #8f8a96\nS #b9745c\n@frame cobble\ngk\n@frame sign\nSk\n"
R_FOLK = "pxart 1\nk #2b1e2f\np #d8718c\nS #b9745c\n@frame kid/0\npk\n@frame fm/0\nSk\n@frame fm/1\nkS\n"
R_KEEPER = "pxart 1\nk #2a1f33\nS #c98a6e\ny #f2c14e\n@frame idle/0\nSk\n"


def report_packs(tmp_path):
    return (write(tmp_path, "tiles.px", R_TILES), write(tmp_path, "folk.px", R_FOLK),
            write(tmp_path, "keeper.px", R_KEEPER))


def report_compose(tmp_path, *more):
    t, f, k = report_packs(tmp_path)
    out = tmp_path / "dock.px"
    code = run("compose", "-o", out, "--size", "6x1", f"{t}:cobble@0,0", f"{f}:kid/0@2,0", f"{k}:idle/0@4,0", *more)
    return code, out, (t, f, k)


def test_report_failed_compose_prints_only_the_errors(tmp_path, capsys):
    code, out, (t, f, k) = report_compose(tmp_path)
    got = capsys.readouterr()
    assert code == 1 and got.out == "" and not out.exists()


def test_report_error_lists_what_rekey_moves_and_why(tmp_path, capsys):
    code, out, (t, f, k) = report_compose(tmp_path)
    capsys.readouterr()
    msg = run_err("compose", "-o", out, "--size", "6x1", f"{t}:cobble@0,0", f"{f}:kid/0@2,0", f"{k}:idle/0@4,0")
    assert msg.startswith(f"compose: layer 3 ({k}:idle/0): E_KEY_CONFLICT: 1 key of this layer is another color in the "
                          f"new {out}: 'k' #2a1f33 (#2b1e2f there, from layer 1 ({t}:cobble))")
    assert "'S'" not in msg.split("; to keep")[0]  # OUT has the keeper's S: no conflict for it


def test_report_error_moves_are_the_moves_rekey_makes(tmp_path, capsys):
    t, f, k = report_packs(tmp_path)
    out = tmp_path / "dock.px"
    argv = ["compose", "-o", out, "--size", "6x1", f"{t}:cobble@0,0", f"{f}:kid/0@2,0", f"{k}:idle/0@4,0"]
    offered = [m for m in fix_of(run_err(*argv)) if ">" in m]
    capsys.readouterr()
    assert run(*argv, "--rekey") == 0
    line = next(l for l in capsys.readouterr().out.splitlines() if f"--rekey gives {k}'s" in l)
    assert line.split(": ", 2)[2].split(" (")[0] == " ".join(f"'{m}'" for m in offered)


def test_report_note_for_the_tiles_says_why_s_is_no_conflict(tmp_path, capsys):
    # Tiles with no frame that draws with S: their S is left out, and the line says why that's no conflict.
    t, f, k = report_packs(tmp_path)
    t = write(tmp_path, "tiles.px", "pxart 1\nk #2b1e2f\ng #8f8a96\nS #b9745c\n@frame cobble\ngk\n")
    out = tmp_path / "dock.px"
    assert run("compose", "-o", out, "--size", "6x1", f"{t}:cobble@0,0", f"{f}:kid/0@2,0", f"{k}:idle/0@4,0",
               "--rekey") == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == (f"note: {out} leaves out layer 1 ({t}:cobble)'s colors for S, a key that layer doesn't draw "
                        f"with (so it doesn't conflict), and has other layers' colors for it: 'S' #b9745c (#c98a6e "
                        f"there, from layer 3 ({k}:idle/0), which draws with it)")
    assert len([l for l in lines if str(t) in l]) == 1


def test_report_tiles_rekey_keeps_s_needed_by_a_frame_not_composed(tmp_path, capsys):
    code, out, (t, f, k) = report_compose(tmp_path, "--rekey")
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == (f"note: --rekey gives {t}'s keys free ones in {out}: 'S>b' ({t} is unchanged): its layers here "
                        "don't draw with S, but tiles.px needs it (S: its frame sign draws with it)")


def test_report_tiles_need_s_only_in_a_frame_not_composed(tmp_path, capsys):
    # Without --rekey but with the keeper's k renamed first, the compose succeeds: the tiles' sign draws with S, so
    # the tiles line is a WARNING naming that frame, not the composed cobble.
    t, f, k = report_packs(tmp_path)
    k2 = write(tmp_path, "keeper2.px", R_KEEPER.replace("k #2a1f33", "j #2a1f33").replace("Sk", "Sj"))
    out = tmp_path / "dock.px"
    assert run("compose", "-o", out, "--size", "6x1", f"{t}:cobble@0,0", f"{f}:kid/0@2,0", f"{k2}:idle/0@4,0") == 0
    lines = capsys.readouterr().out.splitlines()
    tiles = next(l for l in lines if f"layer 1 ({t}:cobble)'s colors" in l)
    assert tiles.startswith("WARNING:") and "tiles.px needs it: its frame sign draws with it" in tiles
    assert "cobble draws" not in tiles and f"compose --rekey keeps S under free keys in {out}" in tiles
    folk = next(l for l in lines if f"layer 2 ({f}:kid/0)'s colors" in l)
    assert "folk.px needs it: its frames fm/0, fm/1 draw with it" in folk and "kid/0 draw" not in folk


def test_report_one_line_per_source_file(tmp_path, capsys):
    code, out, (t, f, k) = report_compose(tmp_path, "--rekey")
    lines = [l for l in capsys.readouterr().out.splitlines() if l.startswith(("note:", "WARNING:"))]
    for path in (t, f, k):
        assert len([l for l in lines if str(path) in l.split(" leaves out ")[0].split(" free ones")[0]]) <= 1


def test_report_rekey_and_left_out_of_one_file_share_its_line(tmp_path, capsys):
    # The folk file: --rekey keeps its needed S under a free key; that is the one line for the file.
    code, out, (t, f, k) = report_compose(tmp_path, "--rekey")
    lines = capsys.readouterr().out.splitlines()
    folk = [l for l in lines if str(f) in l]
    assert len(folk) == 1 and folk[0].startswith(f"note: --rekey gives {f}'s keys free ones in {out}: 'S>")
    assert "its layers here don't draw with S, but folk.px needs it (S: its frames fm/0, fm/1 draw with it)" in folk[0]


def test_report_keeper_line_says_its_key_moved_for_its_color(tmp_path, capsys):
    code, out, (t, f, k) = report_compose(tmp_path, "--rekey")
    line = next(l for l in capsys.readouterr().out.splitlines() if f"--rekey gives {k}'s" in l)
    assert line == f"note: --rekey gives {k}'s keys free ones in {out}: 'k>a' ({k} is unchanged)"


def test_report_rekey_reasons_grouped(tmp_path, capsys):
    # One file whose keys move for all three reasons: another color, other variant colors, needed elsewhere.
    a = write(tmp_path, "a.px", "r #c4473a\nk #000000\nl #ffff00\n@variant dusk\nr #a33a4c\n@frame a\nrk\n"
                                "@frame b\nl.\n")
    b = write(tmp_path, "b.px", "r #c4473a\nk #111111\nl #fff000\n@variant night\nr #83344e\n@frame s\nrk\n"
                                "@frame lamp\nl.\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1", "--rekey") == 0
    line = next(l for l in capsys.readouterr().out.splitlines() if f"--rekey gives {b}'s" in l)
    assert line == (f"note: --rekey gives {b}'s keys free ones in {out}: 'k>a' 'r>b' 'l>c' ({b} is unchanged): k is "
                    f"another color there; r has {out}'s base color but other variant colors; its layers here don't "
                    "draw with l, but b.px needs it (l: its frame lamp draws with it)")


def test_report_error_names_the_other_reasons(tmp_path, capsys):
    a = write(tmp_path, "a.px", "r #c4473a\nk #000000\nl #ffff00\n@variant dusk\nr #a33a4c\n@frame a\nrk\n"
                                "@frame b\nl.\n")
    b = write(tmp_path, "b.px", "r #c4473a\nk #111111\nl #fff000\n@variant night\nr #83344e\n@frame s\nrk\n"
                                "@frame lamp\nl.\n")
    out = tmp_path / "o.px"
    msg = run_err("compose", "-o", out, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1")
    assert (f"add --rekey: compose then gives this layer's keys free ones in the new {out} ('k>a' 'r>b' 'l>c'; r: the "
            f"new {out}'s base color but other variant colors; l: unused here, but b.px needs it) and leaves {b} as it "
            "is") in msg
    assert fix_of(msg)[:5] == ["recolor", str(b), "k>a", "r>b", "l>c"]


def test_report_recolor_recipe_matches_rekey(tmp_path, capsys):
    # Recoloring a copy with the error's recipe and composing from it looks the same as --rekey, in every variant.
    a = write(tmp_path, "a.px", "r #c4473a\nk #000000\nl #ffff00\n@variant dusk\nr #a33a4c\n@frame a\nrk\n"
                                "@frame b\nl.\n")
    b = write(tmp_path, "b.px", "r #c4473a\nk #111111\nl #fff000\n@variant night\nr #83344e\n@frame s\nrk\n"
                                "@frame lamp\nl.\n")
    o1, o2 = tmp_path / "o1.px", tmp_path / "o2.px"
    fix = fix_of(run_err("compose", "-o", o1, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1"))
    assert run(*fix) == 0
    assert run("compose", "-o", o1, "--size", "2x2", f"{a}:a@0,0", f"{fix[-1]}:s@0,1") == 0
    assert run("compose", "-o", o2, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1", "--rekey") == 0
    d1, d2 = pxart.parse(o1), pxart.parse(o2)
    assert d1.frames[0].grid == d2.frames[0].grid
    for v in (None, "dusk", "night"):
        assert list(pxart.pixels(d1.image(d1.frames[0], v))) == list(pxart.pixels(d2.image(d2.frames[0], v)))


def test_report_listed_helper():
    assert pxart.listed([]) == ""
    assert pxart.listed(["a"]) == "a"
    assert pxart.listed(["a", "b", "c", "d"]) == "a, b, c, d"
    assert pxart.listed(["a", "b", "c", "d", "e"]) == "a, b, c and 2 more"
    assert pxart.listed(list("abcdefghij"), most=2) == "a, b and 8 more"


def test_report_special_keys_names_frames(tmp_path):
    doc = pxart.parse(write(tmp_path, "f.px", R_FOLK))
    why = pxart.special_keys(doc)
    assert why["S"] == ["its frames fm/0, fm/1 draw with it"] and why["p"] == ["its frame kid/0 draws with it"]


def test_report_special_keys_many_frames(tmp_path):
    text = "k #000000\n" + "".join(f"@frame w/{i}\nk\n" for i in range(9))
    why = pxart.special_keys(pxart.parse(write(tmp_path, "m.px", text)))
    assert why["k"] == ["its frames w/0, w/1, w/2 and 6 more draw with it"]


def test_report_implicit_frame_named_by_file(tmp_path):
    why = pxart.special_keys(pxart.parse(write(tmp_path, "ant.px", "k #000000\nk\n")))
    assert why["k"] == ["its frame ant draws with it"]


def test_report_copy_to_one_line_per_reason_for_vclash_and_base_note(tmp_path, capsys):
    s = write(tmp_path, "keeper.px", "r #c4473a\nq #fff4b0\n@variant night\nr #83344e\n@frame w/0\nrq\n")
    d = write(tmp_path, "party.px", "r #c4473a\n@variant dusk\nr #a33a4c\n@frame a\nr\n")
    assert run("frames", s, "--copy-to", d) == 0
    lines = capsys.readouterr().out.splitlines()
    warns, notes = [l for l in lines if l.startswith("WARNING:")], [l for l in lines if l.startswith("note:")]
    assert len(warns) == 1 and "draws 'r' #c4473a" in warns[0] and "no @variant" not in warns[0]
    assert len(notes) == 1 and notes[0].startswith("note: keeper.px has no @variant dusk")


def test_help_documents_the_compose_report(capsys):
    doc = " ".join(pxart.__doc__.split())
    assert "compose reports per source file, in layer order, one line per reason" in doc
    assert "which of the file's frames draw with a key it lost" in doc


def test_readme_documents_the_compose_report():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "it reports per source file, one line per reason, with what `--rekey` moved and why" in readme


# ---------------------------------------------------------------- carried comments stay true in the new OUT

GLOW_PAL = ("# WICK shared palette: cellar and flame\nk #1a1423\nw #f6eed8\n"
            "# light-emitting keys: flame and oil glint. Not in @variant dark, so they stay warm.\n"
            "f #ffe07a\na #f58b3c\ni #fff6d0\n\n# darkness: everything that only reflects light goes cold\n"
            "@variant dark\nk #0c0a18\nw #403f4a\n")


def glow_packs(tmp_path):
    (tmp_path / "wick").mkdir()
    write(tmp_path / "wick", "pal.px", GLOW_PAL)
    candle = write(tmp_path / "wick", "player.px", "@palette pal.px\n@frame idle\nfai\nkwk\n")
    stall, keeper, _ = three_packs(tmp_path)
    return stall, keeper, candle


def glow_compose(tmp_path, *more):
    stall, keeper, candle = glow_packs(tmp_path)
    out = tmp_path / "scene.px"
    code = run("compose", "-o", out, "--size", "9x2", f"{stall}:stall@0,0", f"{keeper}:idle@3,0", f"{candle}:idle@6,0",
               "--rekey", *more)
    return code, out


def test_carried_key_comment_says_a_merged_variant_is_another_here(tmp_path, capsys):
    code, out = glow_compose(tmp_path, "--variant-map", "dusk=night,dark")
    text = out.read_text()
    assert code == 0
    assert ("# light-emitting keys: flame and oil glint. Not in @variant dark, so they stay warm. (from player.px, "
            "whose dark is dusk here)") in text


def test_carried_key_comment_without_map_names_only_its_file(tmp_path, capsys):
    code, out = glow_compose(tmp_path)
    text = out.read_text()
    assert "Not in @variant dark, so they stay warm. (from player.px)" in text and "dusk here" not in text


def test_carried_key_comment_keeps_the_keys_it_is_about_under_it(tmp_path, capsys):
    # f a i sit under the comment in the candle's palette; in OUT they still do, whatever order the keys came in.
    code, out = glow_compose(tmp_path, "--variant-map", "dusk=night,dark")
    lines = out.read_text().splitlines()
    at = next(i for i, l in enumerate(lines) if l.startswith("# light-emitting keys"))
    got = [l.split()[1] for l in lines[at + 1:at + 4]]
    assert got == ["#ffe07a", "#f58b3c", "#fff6d0"]


def test_carried_block_follows_a_renamed_head(tmp_path, capsys):
    # The candle's f clashes with nothing here, but k w do; make f clash too: the block moves under the renamed key.
    a = write(tmp_path, "a.px", "f #000000\nz #111111\n@frame x\nfz\n")
    write(tmp_path, "pal.px", "pxart 1\n# glow keys\nf #ffe07a\na #f58b3c\ni #fff6d0\n")
    b = write(tmp_path, "b.px", "@palette pal.px\n@frame y\nfai\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "5x1", f"{a}:x@0,0", f"{b}:y@2,0", "--rekey") == 0
    lines = out.read_text().splitlines()
    at = next(i for i, l in enumerate(lines) if l.startswith("# glow keys"))
    assert lines[at] == "# glow keys (renamed f>b; from b.px)"
    assert [l.split()[1] for l in lines[at + 1:at + 4]] == ["#ffe07a", "#f58b3c", "#fff6d0"]


def test_carried_block_leaves_another_files_key_where_it_is(tmp_path, capsys):
    # a is the first layer's (another color, used there): the comment's block takes only b.px's keys.
    a = write(tmp_path, "a.px", "a #123456\n@frame x\na\n")
    write(tmp_path, "pal.px", "pxart 1\n# glow keys\nf #ffe07a\nq #f58b3c\ni #fff6d0\n")
    b = write(tmp_path, "b.px", "@palette pal.px\n@frame y\nf.i\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "4x1", f"{a}:x@0,0", f"{b}:y@1,0") == 0
    doc = pxart.parse(out)
    order = list(doc.palette)
    assert order.index("q") == order.index("f") + 1 and order.index("i") == order.index("f") + 2
    assert order[0] == "a"


def test_carried_block_stops_at_a_blank_line(tmp_path):
    doc = pxart.parse(write(tmp_path, "p.px", "pxart 1\n# glow\nf #ffe07a\na #f58b3c\n\ni #fff6d0\n# ink\nk #000000\n"
                                              "w #ffffff\n"), palette_only=True)
    assert pxart.comment_blocks(doc) == {"f": ["a"], "k": ["w"]}


def test_comment_blocks_through_an_import(tmp_path):
    write(tmp_path, "pal.px", "pxart 1\n# glow\nf #ffe07a\na #f58b3c\n")
    doc = pxart.parse(write(tmp_path, "s.px", "@palette pal.px\n# own\nz #000000\ny #111111\n@frame a\nf\n"))
    assert pxart.comment_blocks(doc) == {"f": ["a"], "z": ["y"]}


def test_comment_blocks_a_files_header_is_no_block(tmp_path):
    # Comments above a file's first line are its header (palette_notes), not a key's comment.
    doc = pxart.parse(write(tmp_path, "p.px", "# header\nf #ffe07a\na #f58b3c\n"), palette_only=True)
    assert pxart.comment_blocks(doc) == {}


def test_comment_blocks_a_lone_commented_key_is_no_block(tmp_path):
    doc = pxart.parse(write(tmp_path, "p.px", "pxart 1\n# one\nf #ffe07a\n\na #f58b3c\n"), palette_only=True)
    assert pxart.comment_blocks(doc) == {}


def test_carried_variant_comments_say_whose_they_are(tmp_path, capsys):
    code, out = glow_compose(tmp_path, "--variant-map", "dusk=night,dark")
    lines = out.read_text().splitlines()
    dusk = lines.index("@variant dusk")
    assert lines[dusk - 4] == ""
    assert lines[dusk - 3].startswith("# night: cool moonlight; lamp colors (l, g) stay lit (renamed l>")
    assert lines[dusk - 3].endswith("; from keeper.px's @variant night, dusk here)")
    assert lines[dusk - 2] == ("# darkness: everything that only reflects light goes cold (from player.px's @variant "
                               "dark, dusk here)")
    assert lines[dusk - 1] == "# dusk: stall.px's dusk, keeper.px's night, player.px's dark (compose --variant-map)"


def test_carried_variant_comment_of_its_own_name_says_only_its_file(tmp_path, capsys):
    code, out = glow_compose(tmp_path)
    lines = out.read_text().splitlines()
    dark = lines.index("@variant dark")
    assert lines[dark - 1] == ("# darkness: everything that only reflects light goes cold (from player.px's @variant "
                               "dark)")


def test_carried_variant_comment_of_a_shared_palette_said_once_naming_both(tmp_path, capsys):
    write(tmp_path, "pal.px", "k #000000\nr #ff0000\n\n# dusk: warm\n@variant dusk\nr #aa0000\n")
    a = write(tmp_path, "a.px", "@palette pal.px\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "@palette pal.px\n@frame y\nr\n")
    c = write(tmp_path, "c.px", "q #00ff00\n@variant dusk\nq #008800\n@frame z\nq\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "3x1", f"{a}:x@0,0", f"{b}:y@1,0", f"{c}:z@2,0") == 0
    text = out.read_text()
    assert text.count("# dusk: warm") == 1 and "# dusk: warm (from a.px's and b.px's @variant dusk)" in text


def test_carried_comments_single_file_unlabeled(tmp_path, capsys):
    a = write(tmp_path, "a.px", "# my sprite\npxart 1\nk #000000\n# ink\nw #ffffff\n\n# night\n@variant night\n"
                                "k #000011\n@frame x\nkw\n")
    out = tmp_path / "o.px"
    assert run("crop", f"{a}:x", "0,0,2,1", "-o", out) == 0
    assert out.read_text() == "pxart 1\nk #000000\n# ink\nw #ffffff\n\n# night\n@variant night\nk #000011\n\nkw\n"


def test_carried_comments_single_file_importing_keeps_the_import(tmp_path, capsys):
    write(tmp_path, "pal.px", "# header\nk #000000\n# ink\nw #ffffff\n\n# night\n@variant night\nk #000011\n")
    a = write(tmp_path, "a.px", "@palette pal.px\n@frame x\nkw\n")
    out = tmp_path / "o.px"
    assert run("crop", f"{a}:x", "0,0,2,1", "-o", out) == 0
    assert out.read_text() == "pxart 1\n@palette pal.px\n\nkw\n"


def test_carried_comments_single_file_with_map_say_the_merge(tmp_path, capsys):
    write(tmp_path, "pal.px", "k #000000\n# ink, kept dark in night\nw #ffffff\n\n# night: moonlit\n@variant night\n"
                              "k #000011\n")
    a = write(tmp_path, "a.px", "@palette pal.px\n@frame x\nkw\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{a}:x@0,0", "--variant-map", "dusk=night") == 0
    text = out.read_text()
    assert "# ink, kept dark in night (night is dusk here)" in text
    assert "# night: moonlit (@variant night, dusk here)" in text and "from a.px" not in text


def test_mapped_mentions_whole_words_only(tmp_path):
    d = pxart.parse(write(tmp_path, "d.px", "k #000000\n@variant dark\nk #000011\n@frame a\nk\n"))
    vmap = {"dusk": ["dusk", "dark"]}
    assert pxart.mapped_mentions(["# not in @variant dark"], d, vmap) == ["dark is dusk here"]
    assert pxart.mapped_mentions(["# darkness falls", "# dark-blue ink"], d, vmap) == []
    assert pxart.mapped_mentions(["# dark"], d, {}) == []


def test_labeled_helper():
    assert pxart.labeled(["# a (renamed l>M)"], "from k.px") == ["# a (renamed l>M; from k.px)"]
    assert pxart.labeled(["# a", ""], "from k.px") == ["# a (from k.px)", ""]
    assert pxart.labeled(["# a", "# b"], "x") == ["# a", "# b (x)"]
    assert pxart.labeled(["# a"], "") == ["# a"]
    assert pxart.labeled([""], "x") == [""]
    assert pxart.labeled(["# lamps (l, g) (see above)"], "x") == ["# lamps (l, g) (see above) (x)"]


def test_carried_header_at_the_top_labeled(tmp_path, capsys):
    code, out = glow_compose(tmp_path, "--variant-map", "dusk=night,dark")
    lines = out.read_text().splitlines()
    assert lines[:6] == ["pxart 1", "", "# Harbor market palette: warm stone, one hot accent (awning red) (from stall.px)",
                         "# Cozy seaside (from keeper.px)", "# WICK shared palette: cellar and flame (from player.px)",
                         ""]


def test_carried_header_one_line_for_files_that_share_it(tmp_path, capsys):
    write(tmp_path, "pal.px", "# the one palette\nk #000000\nr #ff0000\n")
    a = write(tmp_path, "a.px", "@palette pal.px\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "@palette pal.px\n@frame y\nr\n")
    c = write(tmp_path, "c.px", "q #00ff00\n@frame z\nq\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "3x1", f"{a}:x@0,0", f"{b}:y@1,0", f"{c}:z@2,0") == 0
    assert "# the one palette (from a.px, b.px)" in out.read_text()


def test_carried_header_not_when_out_imports_the_palette(tmp_path, capsys):
    write(tmp_path, "pal.px", "# the one palette\nk #000000\nr #ff0000\n")
    a = write(tmp_path, "a.px", "@palette pal.px\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "@palette pal.px\n@frame y\nr\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:y@1,0") == 0
    assert "the one palette" not in out.read_text() and "@palette pal.px" in out.read_text()


def test_carried_header_not_a_sprites_own(tmp_path, capsys):
    a = write(tmp_path, "a.px", "# my hero sprite\nk #000000\n@frame x\nk\n")
    b = write(tmp_path, "b.px", "q #00ff00\n@frame z\nq\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x1", f"{a}:x@0,0", f"{b}:z@1,0") == 0
    assert "my hero sprite" not in out.read_text()


def test_carried_header_goes_to_an_extracted_palette(tmp_path, capsys):
    code, out = glow_compose(tmp_path, "--variant-map", "dusk=night,dark")
    pal = tmp_path / "shared.px"
    assert run("palette", out, "--extract-to", pal, "--repoint") == 0
    assert "# Cozy seaside (from keeper.px)" in pal.read_text() and "Cozy seaside" not in out.read_text()


def test_carried_header_with_used_keys_only(tmp_path, capsys):
    code, out = glow_compose(tmp_path, "--variant-map", "dusk=night,dark", "--used-keys-only")
    lines = out.read_text().splitlines()
    assert "# Cozy seaside (from keeper.px)" in lines
    first_key = next(i for i, l in enumerate(lines) if len(l) > 2 and l[1] == " " and l[2] == "#")
    assert lines.index("# Cozy seaside (from keeper.px)") < first_key


def test_carried_header_renders_the_same(tmp_path, capsys):
    code, out = glow_compose(tmp_path, "--variant-map", "dusk=night,dark")
    doc = pxart.parse(out)
    stall, keeper, candle = tmp_path / "market" / "stall.px", tmp_path / "keeper" / "keeper.px", tmp_path / "wick" / \
        "player.px"
    assert looks_as_its_file(out, [(stall, "stall", 0, 0), (keeper, "idle", 3, 0), (candle, "idle", 6, 0)],
                             {"dusk": ["dusk", "night", "dark"]})
    assert doc.frames[0].id is None


def test_help_documents_carried_comment_labels():
    doc = " ".join(pxart.__doc__.split())
    assert "each saying which file's it is ('from keeper.px's @variant night, dusk here')" in doc
    assert "the palette files' header comments" in doc


def test_readme_documents_carried_comment_labels():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "each naming its file when there are several (`from keeper.px's @variant night, dusk here`)" in readme


def test_carried_comments_two_layers_of_one_file_unlabeled(tmp_path, capsys):
    a = write(tmp_path, "a.px", "pxart 1\nk #000000\n# ink\nw #ffffff\n\n# night\n@variant night\nk #000011\n"
                                "@frame x\nkw\n@frame y\nwk\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x2", f"{a}:x@0,0", f"{a}:y@0,1") == 0
    assert out.read_text() == "pxart 1\nk #000000\n# ink\nw #ffffff\n\n# night\n@variant night\nk #000011\n\nkw\nwk\n"


# ---------------------------------------------------------------- palette --add of a color a key already has

def test_palette_variant_add_same_and_new_says_both(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\nw #ffffff\n\n@variant night\nk #101010\n\n@frame a\nkw\n")
    assert run("palette", p, "--variant", "night", "--add", "k=#101010", "w=#303030") == 0
    assert capsys.readouterr().out == (f"@variant night; sets w #303030; k is already #101010 in night; unchanged; "
                                       f"wrote {p}\n")


def test_palette_variant_add_two_same(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\nw #ffffff\n\n@variant night\nk #101010\nw #303030\n\n@frame a\nkw\n")
    before = p.read_text()
    assert run("palette", p, "--variant", "night", "--add", "k=#101010", "w=#303030") == 0
    assert capsys.readouterr().out == (f"@variant night; k is already #101010, w is already #303030 in night; "
                                       f"unchanged; no change: {p}\n")
    assert p.read_text() == before


def test_palette_variant_add_same_as_an_imported_variant_writes_the_line(tmp_path, capsys):
    # The imported night already says #101010, but FILE's own line doesn't: setting it here is a change (a local line).
    write(tmp_path, "pal.px", "k #000000\n@variant night\nk #101010\n")
    p = write(tmp_path, "s.px", "@palette pal.px\n@frame a\nk\n")
    assert run("palette", p, "--variant", "night", "--add", "k=#101010") == 0
    assert capsys.readouterr().out == f"@variant night; sets k #101010; wrote {p}\n"


def test_palette_variant_add_base_color_again_is_unchanged(tmp_path, capsys):
    p = write(tmp_path, "s.px", "k #000000\n\n@variant night\nk #000000\n\n@frame a\nk\n")
    assert run("palette", p, "--variant", "night", "--add", "k=#000000") == 0
    assert capsys.readouterr().out == f"@variant night; k is already #000000 in night; unchanged; no change: {p}\n"


def test_palette_add_same_and_new_base_keys(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    assert run("palette", p, "--add", "k=#000000", "w=#ffffff") == 0
    assert capsys.readouterr().out == f"k is already #000000; unchanged; wrote {p}\n"


def test_palette_add_new_key_says_only_wrote(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    assert run("palette", p, "--add", "w=#ffffff") == 0
    assert capsys.readouterr().out == f"wrote {p}\n"


def test_palette_add_same_as_an_imported_key_is_no_change_without_the_clause(tmp_path, capsys):
    # add_key keeps an imported key as it is (no local line): no change, and no claim about FILE's own lines.
    write(tmp_path, "pal.px", "k #000000\n")
    p = write(tmp_path, "s.px", "@palette pal.px\n@frame a\nk\n")
    assert run("palette", p, "--add", "k=#000000") == 0
    assert capsys.readouterr().out == f"no change: {p}\n"


def test_already_helper():
    assert pxart.said_already([("k", (15, 15, 34, 255))], " in dusk") == "k is already #0f0f22 in dusk; unchanged"
    assert pxart.said_already([("k", (0, 0, 0, 255)), ("w", pxart.CLEAR)]) == \
        "k is already #000000, w is already transparent; unchanged"


def test_help_documents_palette_add_already():
    assert "'k is already #0f0f22 in night; unchanged'" in " ".join(pxart.__doc__.split())


# ---------------------------------------------------------------- sheet --align pivot

# walk/1's art is 1px higher in its grid, and its pivot says so: its feet are on row 23, not 24. (25 rows tall: a
# sheet draws no 1x copy beside the label of a frame that tall, so the only red is the cells'.)
PIVOT_WALK = ("r #ff0000\n@anim walk pivot=1,24\n@frame walk/0\n" + "...\n" * 22 + ".r.\n.r.\n.r.\n"
              "@frame walk/1 pivot=1,23\n" + "...\n" * 22 + ".r.\n.r.\n...\n@frame lone\n" + "r\n" * 25)


def red_rows(png, scale=1):
    """For each run of columns holding red pixels (one per cell), the lowest row that has red."""
    img = Image.open(png).convert("RGBA")
    cols = {}
    for y in range(img.height):
        for x in range(img.width):
            if img.getpixel((x, y))[:3] == (255, 0, 0):
                cols[x] = max(cols.get(x, -1), y)
    runs, prev = [], None
    for x in sorted(cols):
        if prev is None or x != prev + 1:
            runs.append([])
        runs[-1].append(cols[x])
        prev = x
    return [max(r) for r in runs]


def test_sheet_align_bottom_is_the_default(tmp_path):
    p = write(tmp_path, "w.px", PIVOT_WALK)
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    assert run("sheet", p, "-o", a) == 0 and run("sheet", p, "-o", b, "--align", "bottom") == 0
    assert a.read_bytes() == b.read_bytes()


def test_sheet_align_pivot_without_pivots_is_the_default(tmp_path):
    p = write(tmp_path, "m.px", MULTI)
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    assert run("sheet", p, "-o", a) == 0 and run("sheet", p, "-o", b, "--align", "pivot") == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("fit", [[], ["--fit"]])
def test_sheet_bottom_shows_the_float(tmp_path, fit):
    p = write(tmp_path, "w.px", PIVOT_WALK)
    out = tmp_path / "s.png"
    assert run("sheet", f"{p}:walk", "-o", out, "--scale", "1", *fit) == 0
    low = red_rows(out)
    assert len(low) == 2 and low[1] == low[0] - 1  # walk/1 looks 1px high


@pytest.mark.parametrize("fit", [[], ["--fit"]])
def test_sheet_align_pivot_lines_up_the_feet(tmp_path, fit):
    p = write(tmp_path, "w.px", PIVOT_WALK)
    out = tmp_path / "s.png"
    assert run("sheet", f"{p}:walk", "-o", out, "--scale", "1", "--align", "pivot", *fit) == 0
    low = red_rows(out)
    assert len(low) == 2 and low[0] == low[1]


@pytest.mark.parametrize("scale", ["1", "4"])
def test_sheet_align_pivot_at_any_scale(tmp_path, scale):
    p = write(tmp_path, "w.px", PIVOT_WALK)
    out = tmp_path / "s.png"
    assert run("sheet", f"{p}:walk", "-o", out, "--scale", scale, "--align", "pivot", "--fit") == 0
    low = red_rows(out)
    assert low[0] == low[1]


def test_sheet_align_pivot_leaves_top_level_frames_alone(tmp_path):
    p = write(tmp_path, "w.px", PIVOT_WALK)
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    assert run("sheet", f"{p}:lone", "-o", a) == 0 and run("sheet", f"{p}:lone", "-o", b, "--align", "pivot") == 0
    assert a.read_bytes() == b.read_bytes()


def test_sheet_align_pivot_groups_are_per_file(tmp_path):
    # The same group in two files: each file's frames line up among themselves only.
    p = write(tmp_path, "w.px", PIVOT_WALK)
    q = write(tmp_path, "v.px", "r #ff0000\n@frame walk/0\n" + "..\n" * 24 + "rr\n")
    out = tmp_path / "s.png"
    assert run("sheet", f"{p}:walk", f"{q}:walk", "-o", out, "--scale", "1", "--align", "pivot") == 0
    low = red_rows(out)
    assert len(low) == 3 and low[0] == low[1]


def test_sheet_align_pivot_frame_without_pivot_uses_bottom_centre(tmp_path):
    # walk/0 has none (bottom-centre 1,24); walk/1's pivot 1,23: the same feet row as walk/0's bottom.
    p = write(tmp_path, "w.px", PIVOT_WALK.replace("@anim walk pivot=1,24\n", ""))
    out = tmp_path / "s.png"
    assert run("sheet", f"{p}:walk", "-o", out, "--scale", "1", "--align", "pivot") == 0
    low = red_rows(out)
    assert low[0] == low[1]


def test_sheet_align_bad_choice(tmp_path, capsys):
    p = write(tmp_path, "w.px", PIVOT_WALK)
    assert run("sheet", p, "-o", tmp_path / "s.png", "--align", "top") == 2


def test_help_documents_sheet_align(capsys):
    out = " ".join(cmd_help(capsys, "sheet").split())
    assert "[--fit] [--align bottom|pivot]" in out and "--align pivot lines up each animation group's frames by pivot" \
        in out
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`--align pivot` lines up each animation's frames by pivot" in readme


# ---------------------------------------------------------------- onion draws A tinted by default

def test_onion_default_is_the_tint(tmp_path):
    assert onion_png(tmp_path).tobytes() == onion_png(tmp_path, "--tint-a").tobytes()
    assert onion_png(tmp_path).tobytes() == onion_png(tmp_path, "--tint-a", "#ff4060a0").tobytes()


def test_onion_default_differs_from_fade(tmp_path):
    assert onion_png(tmp_path).tobytes() != onion_png(tmp_path, "--fade-a").tobytes()


def test_onion_default_pixel_is_the_tint_over_the_backdrop(tmp_path):
    img = onion_png(tmp_path)
    want = Image.new("RGBA", (1, 1), pxart.rgba("#3a3a44"))
    want.alpha_composite(Image.new("RGBA", (1, 1), (0xff, 0x40, 0x60, 0xa0)))
    assert img.getpixel((4, 4)) == want.getpixel((0, 0))


def test_onion_tint_and_fade_together_is_an_error(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWING)
    assert run("onion", f"{p}:a", f"{p}:b", "-o", tmp_path / "o.png", "--tint-a", "--fade-a") == 2
    assert not (tmp_path / "o.png").exists()


def test_onion_readout_same_tinted_or_faded(tmp_path, capsys):
    p = write(tmp_path, "s.px", SWING)
    assert onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b") == onion_lines(tmp_path, capsys, f"{p}:a", f"{p}:b",
                                                                             "--fade-a")


def test_onion_fade_a_help(capsys):
    assert "--fade-a" in cmd_help(capsys, "onion")


def test_readme_documents_onion_tint_default():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`onion` (B over A drawn as a red silhouette" in readme and "`--fade-a` draws A faded instead" in readme


# ---------------------------------------------------------------- palette --comment / --comment-header

CMT_PAL = "pxart 1\nk #000000\nw #ffffff\n\n@variant night\nk #000011\n"


def test_palette_comment_key(tmp_path, capsys):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--comment", "k", "ink") == 0
    assert capsys.readouterr().out == f"commented k; wrote {p}\n"
    assert p.read_text() == "pxart 1\n# ink\nk #000000\nw #ffffff\n\n@variant night\nk #000011\n"


def test_palette_comment_replaces_the_comment_lines(tmp_path):
    p = write(tmp_path, "p.px", "pxart 1\nk #000000\n\n# old one\n# old two\nw #ffffff\n")
    assert run("palette", p, "--comment", "w", "new") == 0
    assert p.read_text() == "pxart 1\nk #000000\n\n# new\nw #ffffff\n"


def test_palette_comment_empty_removes_it_keeps_blank_lines(tmp_path, capsys):
    p = write(tmp_path, "p.px", "pxart 1\nk #000000\n\n# old\nw #ffffff\n")
    assert run("palette", p, "--comment", "w", "") == 0
    assert capsys.readouterr().out == f"uncommented w; wrote {p}\n"
    assert p.read_text() == "pxart 1\nk #000000\n\nw #ffffff\n"


def test_palette_comment_same_again_is_unchanged(tmp_path, capsys):
    p = write(tmp_path, "p.px", "pxart 1\n# ink\nk #000000\n")
    before = p.read_text()
    assert run("palette", p, "--comment", "k", "ink") == 0
    assert capsys.readouterr().out == f"the comment above k is already that; unchanged; no change: {p}\n"
    assert p.read_text() == before


def test_palette_comment_variant_line(tmp_path, capsys):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--comment", "@variant", "night", "night: only lamps glow") == 0
    assert capsys.readouterr().out == f"commented @variant night; wrote {p}\n"
    assert p.read_text() == "pxart 1\nk #000000\nw #ffffff\n\n# night: only lamps glow\n@variant night\nk #000011\n"


def test_palette_comment_variant_as_one_argument(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--comment", "@variant night", "moonlit") == 0
    assert "# moonlit\n@variant night" in p.read_text()


def test_palette_comment_variant_without_a_blank_line_above_keeps_the_spacing(tmp_path):
    # A @variant written by the tool (no lead of its own) keeps its blank line above the new comment.
    p = write(tmp_path, "p.px", "pxart 1\nk #000000\n@frame a\nk\n")
    assert run("palette", p, "--variant", "night", "--add", "k=#000011") == 0
    assert run("palette", p, "--comment", "@variant", "night", "moonlit") == 0
    assert "k #000000\n\n# moonlit\n@variant night\nk #000011\n" in p.read_text()


def test_palette_comment_key_in_a_variant(tmp_path, capsys):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--variant", "night", "--comment", "k", "ink, dimmed") == 0
    assert capsys.readouterr().out == f"commented k in @variant night; wrote {p}\n"
    assert p.read_text().endswith("@variant night\n# ink, dimmed\nk #000011\n")
    assert pxart.parse(p, palette_only=True).variants == {"night": {"k": pxart.hex2rgba("#000011")}}


def test_palette_comment_with_add_in_one_call(tmp_path, capsys):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--variant", "night", "--add", "w=#fff4b0", "--comment", "w", "lamp glass, kept lit") == 0
    assert capsys.readouterr().out == f"@variant night; sets w #fff4b0; commented w in @variant night; wrote {p}\n"
    assert p.read_text().endswith("k #000011\n# lamp glass, kept lit\nw #fff4b0\n")


def test_palette_comment_base_key_added_in_the_same_call(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--add", "y=#ffff00", "--comment", "y", "the sun") == 0
    assert "w #ffffff\n# the sun\ny #ffff00\n" in p.read_text()


def test_palette_comment_repeats(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--comment", "k", "ink", "--comment", "w", "paper") == 0
    assert p.read_text().startswith("pxart 1\n# ink\nk #000000\n# paper\nw #ffffff\n")


def test_palette_comment_two_lines(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--comment", "k", "ink\nthe outline") == 0
    assert p.read_text().startswith("pxart 1\n# ink\n# the outline\nk #000000\n")


def test_palette_comment_text_with_its_own_hash_not_doubled(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--comment", "k", "# ink") == 0
    assert p.read_text().startswith("pxart 1\n# ink\nk #000000\n")


def test_palette_comment_header(tmp_path, capsys):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--comment-header", "crossover palette") == 0
    assert capsys.readouterr().out == f"commented the header; wrote {p}\n"
    assert p.read_text().startswith("# crossover palette\npxart 1\n")


def test_palette_comment_header_replaces_and_removes(tmp_path, capsys):
    p = write(tmp_path, "p.px", "# old header\n# more\n\npxart 1\nk #000000\n")
    assert run("palette", p, "--comment-header", "new") == 0
    assert p.read_text() == "# new\n\npxart 1\nk #000000\n"
    assert run("palette", p, "--comment-header", "") == 0
    assert p.read_text() == "\npxart 1\nk #000000\n"


def test_palette_comment_header_same_is_unchanged(tmp_path, capsys):
    p = write(tmp_path, "p.px", "# h\npxart 1\nk #000000\n")
    assert run("palette", p, "--comment-header", "h") == 0
    assert capsys.readouterr().out == f"the header is already that; unchanged; no change: {p}\n"


def test_palette_comment_header_carried_by_extract_to(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL)
    run("palette", p, "--comment-header", "crossover palette", "--comment", "@variant", "night", "moonlit")
    out = tmp_path / "q.px"
    assert run("palette", p, "--extract-to", out) == 0
    assert out.read_text().startswith("# crossover palette\n") and "# moonlit\n@variant night" in out.read_text()


def test_palette_comment_on_a_sprite(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\n@frame a\nk\n")
    assert run("palette", p, "--comment", "k", "ink") == 0
    # (With no version line, a comment above the first line reads as the file's header when parsed again.)
    assert p.read_text() == "# ink\nk #000000\n@frame a\nk\n"
    assert pxart.parse(p).frames[0].grid == ["k"]


def test_palette_comment_renders_the_same(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL + "@frame a\nkw\n")
    doc = pxart.parse(p)
    before = [list(pxart.pixels(doc.image(doc.frames[0], v))) for v in (None, "night")]
    run("palette", p, "--comment", "k", "ink", "--comment", "@variant", "night", "moon", "--comment-header", "h")
    doc = pxart.parse(p)
    assert [list(pxart.pixels(doc.image(doc.frames[0], v))) for v in (None, "night")] == before


def test_palette_comment_imported_key_says_where(tmp_path):
    write(tmp_path, "pal.px", "k #000000\n")
    p = write(tmp_path, "s.px", "@palette pal.px\n@frame a\nk\n")
    msg = run_err("palette", p, "--comment", "k", "ink")
    assert "E_SELECT" in msg and "isn't one of" in msg and "it comes from pal.px; comment it there" in msg


def test_palette_comment_unknown_key(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL)
    msg = run_err("palette", p, "--comment", "q", "x")
    assert "E_SELECT" in msg and "'q' isn't one of" in msg and p.read_text() == CMT_PAL


def test_palette_comment_imported_variant_says_where(tmp_path):
    write(tmp_path, "pal.px", "k #000000\n@variant night\nk #000011\n")
    p = write(tmp_path, "s.px", "@palette pal.px\n@frame a\nk\n")
    msg = run_err("palette", p, "--comment", "@variant", "night", "x")
    assert "E_SELECT" in msg and "pxart palette pal.px --comment @variant night" in msg


def test_palette_comment_unknown_variant(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL)
    msg = run_err("palette", p, "--comment", "@variant", "dusk", "x")
    assert "E_SELECT" in msg and "(it has: night)" in msg


def test_palette_comment_variant_key_not_listed(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL)
    msg = run_err("palette", p, "--variant", "night", "--comment", "w", "x")
    assert "E_SELECT" in msg and "has no line for 'w'" in msg and "--variant night --add 'w=#rrggbb'" in msg


def test_palette_comment_variant_target_with_another_variant_flag(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL.replace("@variant night", "@variant dusk\nk #000001\n@variant night"))
    before = p.read_text()
    msg = run_err("palette", p, "--variant", "dusk", "--comment", "@variant", "night", "x")
    assert "E_BAD_ARG" in msg and "--comment @variant night names its variant, and --variant dusk another" in msg
    assert p.read_text() == before


def test_palette_comment_variant_target_with_the_same_variant_flag(tmp_path, capsys):
    # The redundant form the help's own example uses: --variant night ... --comment @variant night.
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--variant", "night", "--comment", "@variant", "night", "x") == 0
    lines = p.read_text().splitlines()
    assert lines[lines.index("@variant night") - 1] == "# x"


def test_palette_comment_help_example_runs(tmp_path, capsys):
    p = write(tmp_path, "pal.px", "k #000000\nw #ffffff\n")
    assert run("palette", p, "--variant", "night", "--add", "k=#120e22", "--comment", "@variant", "night",
               "night: only lamps glow") == 0
    assert "# night: only lamps glow\n@variant night\nk #120e22" in p.read_text()


def test_palette_comment_pairs_in_one_flag(tmp_path, capsys):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--comment", "k", "ink", "w", "paper") == 0
    lines = p.read_text().splitlines()
    assert lines[lines.index("k #000000") - 1] == "# ink" and lines[lines.index("w #ffffff") - 1] == "# paper"


def test_palette_comment_pairs_and_variant_in_one_flag(tmp_path, capsys):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--comment", "k", "ink", "@variant", "night", "dark", "w", "paper") == 0
    text = p.read_text()
    assert "# ink\nk #" in text and "# dark\n@variant night" in text and "# paper\nw #" in text


def test_palette_comment_quoted_variant_form_in_pairs(tmp_path, capsys):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--comment", "@variant night", "dark", "k", "ink") == 0
    assert "# dark\n@variant night" in p.read_text()


def test_palette_comment_pairs_repeat_flag_too(tmp_path, capsys):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert run("palette", p, "--comment", "k", "ink", "--comment", "w", "paper") == 0
    assert "# ink\nk #" in p.read_text() and "# paper\nw #" in p.read_text()


def test_comment_args_pairs():
    assert pxart.comment_args([["y", "a", "E", "b"]]) == [(("key", "y"), "a"), (("key", "E"), "b")]
    assert pxart.comment_args([["@variant", "n", "t", "y", "a"]]) == [(("variant", "n"), "t"), (("key", "y"), "a")]
    assert pxart.comment_args([["y", ""]]) == [(("key", "y"), "")]


@pytest.mark.parametrize("args,why", [(["y", "a", "E"], "'E' has no text after it"),
                                      (["y", "a", "Ex", "b"], "'Ex' isn't a key"),
                                      (["@variant", "n"], "'@variant' has no text after it")])
def test_comment_args_odd(args, why):
    with pytest.raises(pxart.PxError) as e:
        pxart.comment_args([args])
    assert why in str(e.value)


def test_palette_comment_metavar(capsys):
    out = cmd_help(capsys, "palette")
    assert "--comment KEY TEXT [KEY TEXT ...]" in out


@pytest.mark.parametrize("args", [["k"], ["kk", "text"], ["@variant", "night", "a", "b"], ["@variant"]])
def test_palette_comment_bad_shapes(tmp_path, args):
    p = write(tmp_path, "p.px", CMT_PAL)
    msg = run_err("palette", p, "--comment", *args)
    assert "E_BAD_ARG" in msg and "--comment KEY 'text'" in msg and p.read_text() == CMT_PAL


@pytest.mark.parametrize("extra", [["--extract-to", "q.px"], ["--export", "q.gpl"]])
def test_palette_comment_not_with_extract_or_export(tmp_path, extra):
    p = write(tmp_path, "p.px", CMT_PAL)
    msg = run_err("palette", p, "--comment", "k", "ink", *[str(tmp_path / e) if e.endswith(("px", "gpl")) else e
                                                          for e in extra])
    assert "E_BAD_ARG" in msg and p.read_text() == CMT_PAL


def test_palette_comment_not_with_hoist(tmp_path):
    p = write(tmp_path, "p.px", CMT_PAL)
    assert "give it alone" in run_err("palette", p, "--comment", "k", "ink", "--hoist", "k")


def test_palette_comment_prints_no_listing(tmp_path, capsys):
    p = write(tmp_path, "p.px", CMT_PAL)
    run("palette", p, "--comment", "k", "ink")
    assert "variants:" not in capsys.readouterr().out


def test_comment_lines_helper():
    assert pxart.comment_lines("a") == ["# a"]
    assert pxart.comment_lines("a\nb") == ["# a", "# b"]
    assert pxart.comment_lines("#a") == ["#a"]
    assert pxart.comment_lines("") == [] and pxart.comment_lines("  ") == []
    assert pxart.comment_lines("a\n") == ["# a", "#"]


def test_help_documents_palette_comment(capsys):
    out = " ".join(cmd_help(capsys, "palette").split())
    assert "[--comment KEY|@variant NAME 'text' [KEY 'text' ...]] [--comment-header 'text']" in out
    assert "--comment KEY 'text' sets the comment right above FILE's line for KEY" in out
    assert "--comment-header 'text' sets the comment at the top of FILE" in out


def test_readme_documents_palette_comment():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`--comment k 'text'`, `--comment @variant night 'text'` and `--comment-header 'text'` write the comment" \
        in readme


# ---------------------------------------------------------------- palette --variant NAME --derive-from

DPAL = "pxart 1\nk #000000\nw #c8c8c8\ny #ffd040\nh #804020\n\n@variant dusk\nw #a0a0b0\ny #ffe080\n"


def dv(path, name, k):
    return pxart.parse(path, palette_only=True).resolved(name)[k]


def test_derive_darken_from_base(tmp_path, capsys):
    p = write(tmp_path, "p.px", DPAL)
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.5") == 0
    assert capsys.readouterr().out == (f"new @variant night; derived from base (darkened 50%): recolors 3 key(s); "
                                       f"wrote {p}\n")
    assert dv(p, "night", "w") == (100, 100, 100, 255) and dv(p, "night", "y") == (128, 104, 32, 255)
    assert dv(p, "night", "h") == (64, 32, 16, 255)
    assert "k" not in pxart.parse(p, palette_only=True).variants["night"]  # black stays black: no line


def test_derive_rounds_half_up_like_round(tmp_path):
    p = write(tmp_path, "p.px", "pxart 1\nq #030303\n")
    assert run("palette", p, "--variant", "n", "--derive-from", "base", "--darken", "0.5") == 0
    assert dv(p, "n", "q") == (2, 2, 2, 255)  # round(1.5) is 2


def test_derive_tint_is_scene_tint_math(tmp_path):
    p = write(tmp_path, "p.px", DPAL)
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--tint", "#10183080") == 0
    for k, c in (("w", "#c8c8c8"), ("y", "#ffd040"), ("h", "#804020")):
        want = pxart.tinted(Image.new("RGBA", (1, 1), pxart.hex2rgba(c)), pxart.hex2rgba("#10183080")).getpixel((0, 0))
        assert dv(p, "night", k) == want


def test_derive_darken_then_tint(tmp_path):
    p = write(tmp_path, "p.px", DPAL)
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.35", "--tint",
               "#10183060") == 0
    dark = tuple(int(round(v * 0.65)) for v in (0xc8, 0xc8, 0xc8)) + (255,)
    want = pxart.tinted(Image.new("RGBA", (1, 1), dark), pxart.hex2rgba("#10183060")).getpixel((0, 0))
    assert dv(p, "night", "w") == want


def test_derive_keep_lit_relists_at_base(tmp_path, capsys):
    p = write(tmp_path, "p.px", DPAL)
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.5", "--keep-lit", "y") == 0
    out = capsys.readouterr().out
    assert "y kept lit (in its base color)" in out
    doc = pxart.parse(p, palette_only=True)
    assert doc.variants["night"]["y"] == doc.palette["y"]  # listed: a relist
    capsys.readouterr()
    run("palette", p)
    night = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("  night:"))
    assert "relists unchanged: y" in night


def test_derive_from_a_variant(tmp_path, capsys):
    p = write(tmp_path, "p.px", DPAL)
    assert run("palette", p, "--variant", "night", "--derive-from", "dusk", "--darken", "0.5", "--keep-lit", "y") == 0
    assert "derived from dusk (darkened 50%)" in capsys.readouterr().out
    assert dv(p, "night", "w") == (80, 80, 88, 255)  # dusk's #a0a0b0, halved
    assert dv(p, "night", "y") == pxart.hex2rgba("#ffe080")  # kept at its dusk color
    assert dv(p, "night", "h") == (64, 32, 16, 255)  # dusk doesn't recolor h: its base, halved


def test_derive_then_add_overrides_one_key(tmp_path, capsys):
    p = write(tmp_path, "p.px", DPAL)
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.5", "--add",
               "y=#fff4d0") == 0
    out = capsys.readouterr().out
    assert out.startswith("new @variant night; derived from base") and "sets y #fff4d0" in out
    assert dv(p, "night", "y") == pxart.hex2rgba("#fff4d0")


def test_derive_existing_variant_is_rewritten(tmp_path, capsys):
    p = write(tmp_path, "p.px", DPAL)
    assert run("palette", p, "--variant", "dusk", "--derive-from", "base", "--darken", "0.5") == 0
    assert capsys.readouterr().out.startswith("@variant dusk; derived from base")
    assert dv(p, "dusk", "w") == (100, 100, 100, 255) and dv(p, "dusk", "y") == (128, 104, 32, 255)


def test_derive_existing_line_back_at_base_goes(tmp_path):
    # With nothing to darken, a derived color is its base color: dusk's lines go (the keys inherit).
    p = write(tmp_path, "p.px", DPAL)
    assert run("palette", p, "--variant", "dusk", "--derive-from", "base") == 0
    assert pxart.parse(p, palette_only=True).variants["dusk"] == {}


def test_derive_copy_of_a_variant(tmp_path):
    p = write(tmp_path, "p.px", DPAL)
    assert run("palette", p, "--variant", "night", "--derive-from", "dusk") == 0
    doc = pxart.parse(p, palette_only=True)
    assert doc.variants["night"] == doc.variants["dusk"]


def test_derive_imported_keys_get_lines_too(tmp_path):
    write(tmp_path, "pal.px", "k #000000\nw #c8c8c8\n")
    p = write(tmp_path, "s.px", "@palette pal.px\nq #804020\n@frame a\nwq\n")
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.5") == 0
    doc = pxart.parse(p)
    assert doc.variants["night"] == {"w": (100, 100, 100, 255), "q": (64, 32, 16, 255)}
    assert (tmp_path / "pal.px").read_text() == "k #000000\nw #c8c8c8\n"


def test_derive_keeps_alpha_and_skips_transparent(tmp_path):
    p = write(tmp_path, "p.px", "pxart 1\ng #80808080\nz transparent\n")
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.5") == 0
    doc = pxart.parse(p, palette_only=True)
    assert doc.variants["night"] == {"g": (64, 64, 64, 128)}


def test_derive_renders_lamp_lit(tmp_path):
    p = write(tmp_path, "s.px", "k #000000\nw #c8c8c8\ny #ffd040\n@frame a\nwy\n")
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.6", "--keep-lit", "y") == 0
    doc = pxart.parse(p)
    img = doc.image(doc.frames[0], "night")
    assert img.getpixel((1, 0)) == pxart.hex2rgba("#ffd040") and img.getpixel((0, 0)) == (80, 80, 80, 255)


def test_derive_twice_is_no_change(tmp_path, capsys):
    p = write(tmp_path, "p.px", DPAL)
    argv = ("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.35", "--keep-lit", "y")
    run(*argv)
    before = p.read_text()
    capsys.readouterr()
    assert run(*argv) == 0
    assert capsys.readouterr().out.endswith(f"no change: {p}\n") and p.read_text() == before


@pytest.mark.parametrize("args, bit", [
    (["--darken", "0.5"], "--derive-from"),
    (["--variant", "night", "--tint", "#101830"], "--derive-from"),
    (["--variant", "night", "--keep-lit", "y"], "--derive-from"),
    (["--derive-from", "base"], "give --variant NAME"),
])
def test_derive_flag_combinations(tmp_path, args, bit):
    p = write(tmp_path, "p.px", DPAL)
    msg = run_err("palette", p, *args)
    assert "E_BAD_ARG" in msg and bit in msg and p.read_text() == DPAL


@pytest.mark.parametrize("darken", ["-0.1", "1.5"])
def test_derive_darken_out_of_range(tmp_path, darken):
    p = write(tmp_path, "p.px", DPAL)
    msg = run_err("palette", p, "--variant", "night", "--derive-from", "base", "--darken", darken)
    assert "E_BAD_ARG" in msg and "from 0 (as is) to 1 (black)" in msg and p.read_text() == DPAL


def test_derive_from_unknown_variant(tmp_path):
    p = write(tmp_path, "p.px", DPAL)
    msg = run_err("palette", p, "--variant", "night", "--derive-from", "eve")
    assert "E_SELECT" in msg and "have: dusk" in msg


def test_derive_keep_lit_unknown_key(tmp_path):
    p = write(tmp_path, "p.px", DPAL)
    assert "E_VARIANT_KEY" in run_err("palette", p, "--variant", "night", "--derive-from", "base", "--keep-lit", "Q")


def test_derive_bad_tint(tmp_path):
    p = write(tmp_path, "p.px", DPAL)
    msg = run_err("palette", p, "--variant", "night", "--derive-from", "base", "--tint", "bluish")
    assert "E_BAD_COLOR" in msg and "--tint" in msg


def test_derive_base_name_refused(tmp_path):
    p = write(tmp_path, "p.px", DPAL)
    assert "E_BAD_ARG" in run_err("palette", p, "--variant", "base", "--derive-from", "dusk")


def test_derived_helper():
    assert pxart.derived((200, 100, 50, 255), 0.5, None) == (100, 50, 25, 255)
    assert pxart.derived((200, 100, 50, 255), 0, None) == (200, 100, 50, 255)
    assert pxart.derived((200, 100, 50, 255), 1, None) == (0, 0, 0, 255)
    assert pxart.derived((10, 10, 10, 255), 0, pxart.CLEAR) == (10, 10, 10, 255)


def test_help_documents_derive(capsys):
    out = " ".join(cmd_help(capsys, "palette").split())
    assert "[--variant NAME --derive-from base|VARIANT [--darken F] [--tint COLOR] [--keep-lit KEYS]]" in out
    assert "Deriving a variant: --variant night --derive-from base --darken 0.35 --tint '#10183060' --keep-lit y,W" \
        in out
    assert "the math of scene --tint" in out


def test_readme_documents_derive():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "--derive-from base --darken 0.35 --tint '#10183060' --keep-lit y,W` builds a whole night" in readme


# ---------------------------------------------------------------- pxart -h is an overview; pxart help all the reference

def top_help(capsys, *argv):
    with pytest.raises(SystemExit) as e:
        pxart.main(list(argv))
    assert e.value.code == 0
    return capsys.readouterr().out


def help_out(capsys, *argv):
    assert run("help", *argv) == 0
    return capsys.readouterr().out


def test_top_help_is_short(capsys):
    out = top_help(capsys, "-h")
    assert len(out.splitlines()) < 60 and "pxart: pixel art as text." in out
    assert "'pxart help all' prints the whole reference" in " ".join(out.split())


def test_top_help_long_flag_same(capsys):
    assert top_help(capsys, "-h") == top_help(capsys, "--help")


def test_top_help_lists_every_command_once(capsys):
    out = top_help(capsys, "-h")
    table = out[out.index("Commands by topic"):out.index("Topics:")]
    words = " ".join(l.split(None, 1)[1] for l in table.splitlines()[1:] if l.strip()).split()
    assert sorted(words) == sorted(COMMANDS) and len(words) == len(set(words))


def test_top_help_has_the_format_sample(capsys):
    out = top_help(capsys, "-h")
    assert "    k #3f2631                palette: one key char" in out and "    ....kkkk....             grid rows" in out
    doc = pxart.__doc__.splitlines()
    sample = out[out.index("A sprite is"):out.index("Commands by topic")].splitlines()[1:]
    assert all(l in doc for l in sample)


def test_top_help_no_longer_the_whole_reference(capsys):
    out = top_help(capsys, "-h")
    assert "Bresenham" not in out and "ERROR CODES" not in out


def test_commands_by_topic():
    got = pxart.commands_by_topic()
    assert list(got) == ["LOOKING", "CHECKING", "EDITING", "DRAWING", "CONVERTING", "HELP"]
    assert got["LOOKING"] == ["render", "sheet", "anim", "onion", "scene", "tint"]
    assert "frames" in got["CHECKING"] and "transpose" in got["DRAWING"] and "flood" in got["DRAWING"]
    assert got["CONVERTING"] == ["export", "from-png"] and got["HELP"] == ["help"]


@pytest.mark.parametrize("cmd", COMMANDS)
def test_commands_by_topic_puts_each_under_its_sections_heading(cmd):
    doc = pxart.__doc__.splitlines()
    start = pxart.section_start(cmd)
    heading = next(l for l in reversed(doc[:start]) if l[:1].isupper())
    where = next(t for t, cs in pxart.commands_by_topic().items() if cmd in cs)
    assert heading.startswith(pxart.TOPICS[where])


def test_help_without_topic_is_the_overview(capsys):
    assert help_out(capsys) == top_help(capsys, "-h")


def test_help_all_is_the_whole_reference(capsys):
    assert help_out(capsys, "all") == pxart.__doc__.rstrip() + "\n"


@pytest.mark.parametrize("name", list(pxart.TOPICS))
def test_help_topic_is_its_part_of_the_reference(capsys, name):
    out = help_out(capsys, name)
    assert out.startswith(pxart.TOPICS[name]) and out.rstrip("\n") in pxart.__doc__
    if name.lower() not in COMMANDS:  # 'help help' is the command's own -h
        assert help_out(capsys, name.lower()) == out


def test_help_topics_cover_the_reference():
    doc = pxart.__doc__.rstrip()
    parts = [pxart.topic(t) for t in pxart.TOPICS]
    assert sum(len(p.splitlines()) for p in parts) + len(parts) >= len(doc.splitlines()) - 3
    assert "\n\n".join(parts) in doc.replace("\n\n\n", "\n\n") or all(p in doc for p in parts)


def test_help_topic_editing_ends_before_drawing(capsys):
    out = help_out(capsys, "EDITING")
    assert "  compose -o OUT[:frame]" in out and "DRAWING" not in out.splitlines()[-1] and "  line FILE" not in out


@pytest.mark.parametrize("cmd", ["compose", "poly", "frames", "help"])
def test_help_cmd_is_cmd_dash_h(capsys, cmd):
    assert help_out(capsys, cmd).rstrip() == cmd_help(capsys, cmd).rstrip()


def test_help_unknown_topic(capsys):
    msg = run_err("help", "nope")
    assert msg.startswith("help: E_BAD_ARG: help 'nope': no such topic or command; topics: all, FORMAT") and \
        "commands:" in msg


def test_help_section_in_the_reference():
    ref = pxart.reference("help")
    assert ref.startswith("  help [all | TOPIC | CMD]") and "'pxart help all' prints this whole reference" in " ".join(
        ref.split())


def test_command_help_footer_names_help_all(capsys):
    assert "\n\npxart help all has the whole reference, pxart help TOPIC one part of it.\n" in cmd_help(capsys, "set")


def test_help_upper_help_is_the_topic(capsys):
    assert help_out(capsys, "HELP").startswith("HELP\n  help [all | TOPIC | CMD]")


def test_readme_documents_help_topics():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`pxart -h` is a short overview: the format in a few lines and the commands by topic." in readme
    assert "`pxart help all` has the full reference, `pxart help TOPIC` one part of it" in readme


# ---------------------------------------------------------------- --variant-map adds to the same-name lookup
# The crossover's palette has dusk and night; the keeper's only night. 'dusk=night' reads the keeper's night as DST's
# dusk, and DST's night still reads the keeper's night: the map never stops a same-named variant being read.

NIGHT_ONLY = ("r #c4473a\nk #000000\nz #20c020\n@variant night\nr #83344e\nk #000011\nz #103010\n"
              "@anim walk ms=90\n@frame walk/0\nrk\nz.\n@frame walk/1\nkr\n.z\n")
DUSK_NIGHT = ("r #c4473a\nk #000000\n@variant dusk\nr #a33a4c\n@variant night\nr #501020\n"
              "@frame awning\nrk\n..\n")
DUSK_NIGHT_RAIN = DUSK_NIGHT.replace("@frame", "@variant rain\nr #405060\n@frame")


def night_pack(tmp_path, dst=DUSK_NIGHT):
    return write(tmp_path, "keeper.px", NIGHT_ONLY), write(tmp_path, "party.px", dst)


def reads_as(dst, fid, src, sfid, vmap, at=(0, 0)):
    """dst's frame fid, in every variant of dst (and base), shows src's frame sfid's opaque pixels as src's file draws
    them: in dst's variant V, src's first of vmap[V] (or V itself) its file has, else src's base colors."""
    d, sd = pxart.parse(dst), pxart.parse(src)
    have = pxart.variant_names(sd)
    for v in [None] + pxart.variant_names(d):
        want = next((n for n in vmap.get(v, [v]) if n in have), None) if v else None
        img, simg = d.image(d.get(fid), v), sd.image(sd.get(sfid), want)
        for y in range(simg.height):
            for x in range(simg.width):
                p = simg.getpixel((x, y))
                if p[3]:
                    assert img.getpixel((at[0] + x, at[1] + y)) == p, (v, want, x, y)
    return True


def color_in(path, fid, variant, xy):
    doc = pxart.parse(path)
    return doc.image(doc.get(fid), variant).getpixel(xy)


NIGHT_Z = pxart.hex2rgba("#103010")
KEEPER_NIGHT_R = pxart.hex2rgba("#83344e")
DST_NIGHT_R = pxart.hex2rgba("#501020")


def test_layer_variants_map_adds_to_the_same_name():
    doc = pxart.Doc()
    doc.variants = {"night": {}}
    assert pxart.layer_variants(doc, {}) == {"night": "night"}
    assert pxart.layer_variants(doc, {"dusk": ["dusk", "night"]}) == {"dusk": "night", "night": "night"}


def test_layer_variants_a_file_with_the_map_name_uses_its_own():
    doc = pxart.Doc()
    doc.variants = {"dusk": {}, "night": {}}
    assert pxart.layer_variants(doc, {"dusk": ["dusk", "night"]}) == {"dusk": "dusk", "night": "night"}


def test_layer_variants_one_source_into_two_maps():
    doc = pxart.Doc()
    doc.variants = {"night": {}}
    got = pxart.layer_variants(doc, {"dusk": ["dusk", "night"], "rain": ["rain", "night"]})
    assert got == {"dusk": "night", "rain": "night", "night": "night"}


def test_layer_variants_map_name_never_read_by_same_name():
    # A file whose own 'dusk' the map doesn't pick (dusk=dark,dusk would pick dark first) gives dark, not dusk.
    doc = pxart.Doc()
    doc.variants = {"dusk": {}, "dark": {}}
    assert pxart.layer_variants(doc, {"dusk": ["dusk", "dark"]}) == {"dusk": "dusk", "dark": "dark"}
    assert pxart.layer_variants(doc, {"eve": ["eve", "dark", "dusk"]}) == {"eve": "dark", "dusk": "dusk",
                                                                           "dark": "dark"}


def test_layer_variants_no_variants():
    assert pxart.layer_variants(pxart.Doc(), {"dusk": ["dusk", "night"]}) == {}


def test_merged_away_only_when_every_file_gave_it():
    keeper, both = pxart.Doc(), pxart.Doc()
    keeper.variants, both.variants = {"night": {}}, {"dusk": {}, "night": {}}
    vmap = {"dusk": ["dusk", "night"]}
    assert pxart.merged_away([keeper], vmap) == {"night"}
    assert pxart.merged_away([keeper, both], vmap) == set()
    assert pxart.merged_away([both], vmap) == set()
    assert pxart.merged_away([keeper], {}) == set()


def test_copy_to_map_still_reads_the_same_named_night(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--variant-map", "dusk=night") == 0
    doc = pxart.parse(d)
    assert doc.variants["night"]["z"] == NIGHT_Z and doc.variants["dusk"]["z"] == NIGHT_Z
    assert color_in(d, "walk/0", "night", (0, 1)) == NIGHT_Z


def test_copy_to_map_new_key_not_at_base_in_night(tmp_path, capsys):
    # The symptom: a new key stayed at its base color in DST's night.
    s, d = night_pack(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--variant-map", "dusk=night")
    assert color_in(d, "walk/1", "night", (1, 1)) != pxart.hex2rgba("#20c020")


def test_copy_to_map_no_base_color_note_for_night(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--variant-map", "dusk=night")
    assert "stay at base colors" not in capsys.readouterr().out


def test_copy_to_map_rekey_every_variant_reads_as_its_file(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "--variant-map", "dusk=night") == 0
    vmap = {"dusk": ["dusk", "night"]}
    assert reads_as(d, "walk/0", s, "walk/0", vmap) and reads_as(d, "walk/1", s, "walk/1", vmap)
    assert color_in(d, "walk/0", "night", (0, 0)) == KEEPER_NIGHT_R
    assert color_in(d, "awning", "night", (0, 0)) == DST_NIGHT_R


def test_copy_to_map_rekey_moves_the_shared_red(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "--variant-map", "dusk=night")
    assert pxart.parse(d).get("walk/0").grid[0][0] != "r"


def test_copy_to_map_rekey_reuses_a_key_that_looks_the_same_in_dusk_and_night(tmp_path, capsys):
    # DST's I is the scarf in base, dusk and night alike, as the keeper's night reads: --rekey picks I.
    dst = DUSK_NIGHT.replace("k #000000\n", "k #000000\nI #c4473a\n").replace(
        "@variant dusk\n", "@variant dusk\nI #83344e\n").replace("@variant night\n", "@variant night\nI #83344e\n")
    s, d = night_pack(tmp_path, dst)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "--variant-map", "dusk=night") == 0
    assert "'r>I'" in capsys.readouterr().out
    assert pxart.parse(d).get("walk/0").grid[0][0] == "I"


def test_copy_to_map_rekey_skips_a_key_that_differs_only_in_night(tmp_path, capsys):
    # I matches the scarf in dusk but not in night: before the fix night wasn't compared as the keeper's, now it is.
    dst = DUSK_NIGHT.replace("k #000000\n", "k #000000\nI #c4473a\n").replace(
        "@variant dusk\n", "@variant dusk\nI #83344e\n").replace("@variant night\n", "@variant night\nI #222222\n")
    s, d = night_pack(tmp_path, dst)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "--variant-map", "dusk=night") == 0
    assert pxart.parse(d).get("walk/0").grid[0][0] not in ("I", "r")


def test_copy_to_map_rain_left_at_base_is_said(tmp_path, capsys):
    s, d = night_pack(tmp_path, DUSK_NIGHT_RAIN)
    run("frames", f"{s}:walk", "--copy-to", d, "--variant-map", "dusk=night")
    out = capsys.readouterr().out
    assert ("keeper.px has no @variant rain (it has night), so the keys FILE (" in out
            and "stay at base colors in its rain; --variant-map rain=night reads its night as rain" in out)
    assert "@variant night or rain" not in out


def test_copy_to_map_one_source_into_two_maps(tmp_path, capsys):
    s, d = night_pack(tmp_path, DUSK_NIGHT_RAIN)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "--variant-map", "dusk=night",
               "--variant-map", "rain=night") == 0
    assert "stay at base colors" not in capsys.readouterr().out
    vmap = {"dusk": ["dusk", "night"], "rain": ["rain", "night"]}
    assert reads_as(d, "walk/0", s, "walk/0", vmap) and reads_as(d, "walk/1", s, "walk/1", vmap)


def test_copy_to_without_map_night_still_read(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey") == 0
    assert reads_as(d, "walk/0", s, "walk/0", {})
    assert color_in(d, "walk/0", "dusk", (0, 1)) == pxart.hex2rgba("#20c020")  # no dusk in keeper.px: base


def test_paste_map_still_reads_the_same_named_night(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    assert run("paste", f"{s}:walk/0", "--into", f"{d}:awning", "--at", "0,0", "--rekey",
               "--variant-map", "dusk=night") == 0
    assert reads_as(d, "awning", s, "walk/0", {"dusk": ["dusk", "night"]})
    assert color_in(d, "awning", "night", (0, 1)) == NIGHT_Z


def test_paste_map_without_rekey_new_key_in_night(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    assert run("paste", f"{s}:walk/0", "--into", f"{d}:awning", "--at", "0,1", "--variant-map", "dusk=night") == 0
    assert pxart.parse(d).variants["night"]["z"] == NIGHT_Z


def test_crop_existing_map_still_reads_the_same_named_night(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    assert run("crop", f"{s}:walk/0", "0,0,2,2", "-o", f"{d}:cut", "--rekey", "--variant-map", "dusk=night") == 0
    assert reads_as(d, "cut", s, "walk/0", {"dusk": ["dusk", "night"]})
    assert color_in(d, "cut", "night", (0, 0)) == KEEPER_NIGHT_R


def test_crop_new_map_renames_night_to_dusk(tmp_path, capsys):
    # One file whose night the map reads as dusk: every file having night gave it away, so the new OUT has only dusk.
    s, _ = night_pack(tmp_path)
    out = tmp_path / "cut.px"
    assert run("crop", f"{s}:walk/0", "0,0,2,2", "-o", out, "--variant-map", "dusk=night") == 0
    assert set(pxart.parse(out).variants) == {"dusk"}


def test_compose_existing_map_still_reads_the_same_named_night(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    assert run("compose", "-o", f"{d}:c", f"{s}:walk/1@0,0", "--rekey", "--variant-map", "dusk=night") == 0
    assert reads_as(d, "c", s, "walk/1", {"dusk": ["dusk", "night"]})
    assert color_in(d, "c", "night", (1, 1)) == NIGHT_Z


def test_compose_existing_map_without_rekey_new_key_in_night(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    assert run("compose", "-o", f"{d}:c", f"{s}:walk/1@0,0", "--variant-map", "dusk=night") == 0
    doc = pxart.parse(d)
    assert doc.variants["night"]["z"] == NIGHT_Z and doc.variants["dusk"]["z"] == NIGHT_Z


def test_compose_new_map_keeps_a_night_another_file_has(tmp_path, capsys):
    # party.px has dusk and night: OUT keeps both, and the keeper's pixels read its night in each.
    s, d = night_pack(tmp_path)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "4x2", f"{d}:awning@0,0", f"{s}:walk/0@2,0", "--rekey",
               "--variant-map", "dusk=night") == 0
    doc = pxart.parse(out)
    assert set(doc.variants) == {"dusk", "night"}
    vmap = {"dusk": ["dusk", "night"]}
    assert looks_as_its_file(out, [(d, "awning", 0, 0), (s, "walk/0", 2, 0)], vmap)
    assert doc.image(doc.frames[0], "night").getpixel((2, 0)) == KEEPER_NIGHT_R
    assert doc.image(doc.frames[0], "night").getpixel((0, 0)) == DST_NIGHT_R


def test_compose_new_map_night_covers_both_layers(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    out = tmp_path / "o.px"
    run("compose", "-o", out, "--size", "4x2", f"{d}:awning@0,0", f"{s}:walk/0@2,0", "--rekey",
        "--variant-map", "dusk=night")
    assert "covers" not in capsys.readouterr().out


def test_compose_new_without_map_night_covers_both_dusk_only_the_party(tmp_path, capsys):
    s, d = night_pack(tmp_path)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "4x2", f"{d}:awning@0,0", f"{s}:walk/0@2,0", "--rekey") == 0
    got = capsys.readouterr().out
    assert f"@variant dusk covers layer 1 ({d}:awning) only" in got and "@variant night covers" not in got
    assert looks_as_its_file(out, [(d, "awning", 0, 0), (s, "walk/0", 2, 0)])


def test_compose_new_map_three_packs_still_one_dusk(tmp_path, capsys):
    code, out, _ = compose_packs(tmp_path, "--rekey", "--variant-map", "dusk=night,dark")
    assert code == 0 and set(pxart.parse(out).variants) == {"dusk"}


def test_help_says_the_map_adds(capsys):
    text = " ".join(pxart.__doc__.split())
    assert ("The map adds to the same-name lookup, never replaces it: it says only where OUT's dusk comes from, and "
            "OUT's other variants, night among them, still read each file's variant of the same name") in text
    assert "reads FILE's night as DST's dusk, and still as DST's night: the map adds, see compose" in text


def test_readme_says_the_map_adds():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "it adds to the same-name lookup, never replaces it: OUT's night still reads each file's night" in readme


# ---------------------------------------------------------------- frames --copy-to --prefix / --rename, frames --rename
# Wick's walk/* met the keeper's walk/* in party.px: the copies need other ids, and a group needs renaming in place.

RSRC = ("pxart 1\nk #000000\nw #ffffff\n\n# the walk\n@anim walk/down ms=150 pivot=0,1\n@anim walk/up ms=140\n"
        "@still ui\n\n# first step\n@frame walk/down/0\nkw\nk.\n@frame walk/down/1 ms=200\nwk\n.k\n"
        "@frame walk/up/0\nkk\nww\n@frame ui/a\nw\n@frame idle\nkk\n")
RDST = "pxart 1\nk #000000\nw #ffffff\n@anim walk/down ms=90\n@frame walk/down/0\nk\n@frame walk/down/1\nw\n"


def rpair(tmp_path, src=RSRC, dst=RDST):
    return write(tmp_path, "wick.px", src), write(tmp_path, "party.px", dst)


def test_copy_to_same_ids_is_dup_and_names_prefix(tmp_path):
    s, d = rpair(tmp_path)
    msg = run_err("frames", f"{s}:walk", "--copy-to", d)
    assert "E_DUP_FRAME" in msg and "--prefix P, or --rename GROUP NEWGROUP" in msg


def test_copy_to_prefix_renames_every_copy(tmp_path, capsys):
    s, d = rpair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--prefix", "wick/") == 0
    assert ids(d) == ["walk/down/0", "walk/down/1", "wick/walk/down/0", "wick/walk/down/1", "wick/walk/up/0"]


def test_copy_to_prefix_brings_the_anim_lines_renamed(tmp_path, capsys):
    s, d = rpair(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--prefix", "wick/")
    doc = pxart.parse(d)
    def said(g):
        return {k: v for k, v in doc.anims[g].items() if v is not None}
    assert said("wick/walk/down") == {"ms": 150, "pivot": (0, 1)}
    assert said("wick/walk/up") == {"ms": 140}
    assert said("walk/down") == {"ms": 90}  # DST's own stays


def test_copy_to_prefix_keeps_timing_and_pivots(tmp_path, capsys):
    s, d = rpair(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--prefix", "wick/")
    src, dst = pxart.parse(s), pxart.parse(d)
    for fid in ("walk/down/0", "walk/down/1", "walk/up/0"):
        f, g = src.get(fid), dst.get("wick/" + fid)
        assert g.grid == f.grid and dst.ms(g) == src.ms(f) and dst.pivot(g) == src.pivot(f), fid


def test_copy_to_prefix_says_what_it_renamed(tmp_path, capsys):
    s, d = rpair(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--prefix", "wick/")
    assert capsys.readouterr().out == (
        f"copied walk/down/0, walk/down/1, walk/up/0 to {d}, walk as wick/walk; added @anim wick/walk/down; added "
        f"@anim wick/walk/up; wrote {d}\n")


def test_copy_to_prefix_leaves_the_source_alone(tmp_path, capsys):
    s, d = rpair(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--prefix", "wick/")
    assert s.read_text() == RSRC


def test_copy_to_prefix_without_slash(tmp_path, capsys):
    s, d = rpair(tmp_path)
    assert run("frames", f"{s}:walk/up", "--copy-to", d, "--prefix", "wick-") == 0
    assert "wick-walk/up/0" in ids(d) and "wick-walk/up" in pxart.parse(d).anims


def test_copy_to_prefix_whole_file_top_level_and_still(tmp_path, capsys):
    s, d = rpair(tmp_path)
    assert run("frames", s, "--copy-to", d, "--prefix", "w/") == 0
    doc = pxart.parse(d)
    assert {"w/idle", "w/ui/a", "w/walk/up/0"} <= set(ids(d)) and "w/ui" in doc.stills


def test_copy_to_prefix_by_ids(tmp_path, capsys):
    s, d = rpair(tmp_path)
    assert run("frames", s, "--copy-to", d, "walk/up/0", "--prefix", "wick/") == 0
    assert ids(d)[-1] == "wick/walk/up/0" and len(ids(d)) == 3


def test_copy_to_prefix_bad(tmp_path):
    s, d = rpair(tmp_path)
    for bad in ("", "a b/", "x//"):
        msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--prefix", bad)
        assert "E_BAD_ID" in msg and "--prefix" in msg, bad
    assert d.read_text() == RDST


def test_copy_to_prefix_still_collides(tmp_path):
    s, d = rpair(tmp_path, dst=RDST + "@frame wick/walk/up/0\nk\n")
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--prefix", "wick/")
    assert "E_DUP_FRAME" in msg and "already has wick/walk/up/0" in msg


def test_prefix_needs_copy_to(tmp_path):
    s, _ = rpair(tmp_path)
    msg = run_err("frames", s, "--prefix", "wick/")
    assert "E_BAD_ARG" in msg and "--prefix names the copies --copy-to DST makes" in msg and "--rename" in msg


def test_prefix_and_rename_not_both(tmp_path):
    s, d = rpair(tmp_path)
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--prefix", "a/", "--rename", "walk", "b/walk")
    assert "E_BAD_ARG" in msg and "not both" in msg


def test_copy_to_rename_one_group(tmp_path, capsys):
    s, d = rpair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rename", "walk", "wick/walk") == 0
    assert ids(d)[2:] == ["wick/walk/down/0", "wick/walk/down/1", "wick/walk/up/0"]
    assert f"to {d}, walk as wick/walk;" in capsys.readouterr().out


def test_copy_to_rename_a_subgroup_only(tmp_path, capsys):
    s, d = rpair(tmp_path, dst=RDST.replace("walk/down", "run"))
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rename", "walk/up", "climb") == 0
    assert ids(d) == ["run/0", "run/1", "walk/down/0", "walk/down/1", "climb/0"]
    assert set(pxart.parse(d).anims) == {"run", "walk/down", "climb"}


def test_copy_to_rename_repeats(tmp_path, capsys):
    s, d = rpair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rename", "walk/down", "a", "--rename", "walk/up", "b") == 0
    assert ids(d)[2:] == ["a/0", "a/1", "b/0"]


def test_copy_to_rename_a_single_frame(tmp_path, capsys):
    s, d = rpair(tmp_path)
    assert run("frames", f"{s}:idle", "--copy-to", d, "--rename", "idle", "wick-idle") == 0
    assert ids(d)[-1] == "wick-idle"


def test_copy_to_rename_that_names_nothing(tmp_path):
    s, d = rpair(tmp_path)
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--rename", "run", "x")
    assert "E_SELECT" in msg and "--rename run x: no frame 'run' or run/..." in msg
    assert d.read_text() == RDST


def test_copy_to_rename_prefix_of_a_name_is_not_a_match(tmp_path):
    s, d = rpair(tmp_path)
    assert "E_SELECT" in run_err("frames", f"{s}:walk", "--copy-to", d, "--rename", "wal", "x")


def test_copy_to_rename_bad_new_id(tmp_path):
    s, d = rpair(tmp_path)
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--rename", "walk", "bad id")
    assert "E_BAD_ID" in msg


def test_copy_to_rename_after_a_frame(tmp_path, capsys):
    s, d = rpair(tmp_path)
    assert run("frames", f"{s}:walk/up", "--copy-to", d, "--rename", "walk/up", "wick/up", "--after",
               "walk/down/0") == 0
    assert ids(d) == ["walk/down/0", "wick/up/0", "walk/down/1"]


def test_copy_to_rename_with_rekey_and_map(tmp_path, capsys):
    src = RSRC.replace("\n\n# the walk", "\n@variant night\nw #111111\n\n# the walk")
    dst = RDST.replace("@anim", "@variant dusk\nw #222222\n@anim")
    s, d = rpair(tmp_path, src, dst)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "--variant-map", "dusk=night", "--prefix",
               "wick/") == 0
    doc = pxart.parse(d)
    f = doc.get("wick/walk/down/0")
    assert doc.image(f, "dusk").getpixel((1, 0)) == pxart.hex2rgba("#111111")


def test_rename_in_place_group(tmp_path, capsys):
    s, _ = rpair(tmp_path)
    assert run("frames", s, "--rename", "walk", "wick/walk") == 0
    assert ids(s) == ["wick/walk/down/0", "wick/walk/down/1", "wick/walk/up/0", "ui/a", "idle"]
    assert list(pxart.parse(s).anims) == ["wick/walk/down", "wick/walk/up"]


def test_rename_in_place_says_what(tmp_path, capsys):
    s, _ = rpair(tmp_path)
    run("frames", s, "--rename", "walk", "wick/walk")
    assert capsys.readouterr().out == (f"renamed walk -> wick/walk (3 frame(s)); @anim wick/walk/down, @anim "
                                       f"wick/walk/up; wrote {s}\n")


def test_rename_in_place_keeps_everything_else(tmp_path, capsys):
    s, _ = rpair(tmp_path)
    run("frames", s, "--rename", "walk", "wick/walk")
    assert s.read_text() == RSRC.replace("walk/", "wick/walk/")


def test_rename_in_place_keeps_timing_and_pivots(tmp_path, capsys):
    s, _ = rpair(tmp_path)
    before = pxart.parse(s)
    run("frames", s, "--rename", "walk/down", "run")
    after = pxart.parse(s)
    for i in (0, 1):
        f, g = before.get(f"walk/down/{i}"), after.get(f"run/{i}")
        assert g.grid == f.grid and after.ms(g) == before.ms(f) and after.pivot(g) == before.pivot(f)


def test_rename_in_place_comments_move_with_their_lines(tmp_path, capsys):
    s, _ = rpair(tmp_path)
    run("frames", s, "--rename", "walk/down", "run")
    lines = s.read_text().splitlines()
    assert lines[lines.index("@anim run ms=150 pivot=0,1") - 1] == "# the walk"
    assert lines[lines.index("@frame run/0") - 1] == "# first step"


def test_rename_in_place_still_group(tmp_path, capsys):
    s, _ = rpair(tmp_path)
    assert run("frames", s, "--rename", "ui", "hud") == 0
    doc = pxart.parse(s)
    assert doc.stills == ["hud"] and "hud/a" in ids(s)
    assert "@still hud" in capsys.readouterr().out


def test_rename_in_place_one_frame(tmp_path, capsys):
    s, _ = rpair(tmp_path)
    assert run("frames", s, "--rename", "walk/up/0", "walk/up/9") == 0
    assert "walk/up/9" in ids(s) and "walk/up" in pxart.parse(s).anims


def test_rename_in_place_top_level_frame(tmp_path, capsys):
    s, _ = rpair(tmp_path)
    assert run("frames", s, "--rename", "idle", "rest") == 0
    assert ids(s)[-1] == "rest"


def test_rename_in_place_repeats(tmp_path, capsys):
    s, _ = rpair(tmp_path)
    assert run("frames", s, "--rename", "walk/down", "a", "--rename", "walk/up", "b") == 0
    assert ids(s)[:3] == ["a/0", "a/1", "b/0"]


def test_rename_in_place_swap_is_not_a_collision(tmp_path, capsys):
    # walk/down <-> walk/up in one call: each lands where the other was.
    s, _ = rpair(tmp_path, src=RSRC.replace("@frame walk/up/0", "@frame walk/up/1\nkk\nkk\n@frame walk/up/0"))
    assert run("frames", s, "--rename", "walk/down", "walk/up", "--rename", "walk/up", "walk/down") == 0


def test_rename_in_place_into_an_existing_group(tmp_path):
    s, _ = rpair(tmp_path)
    before = s.read_text()
    msg = run_err("frames", s, "--rename", "walk/down", "walk/up")
    assert "E_DUP_FRAME" in msg and "already has walk/up" in msg
    assert s.read_text() == before


def test_rename_in_place_onto_an_existing_frame(tmp_path):
    s, _ = rpair(tmp_path)
    msg = run_err("frames", s, "--rename", "walk/up/0", "idle")
    assert "E_DUP_FRAME" in msg and "already has idle" in msg


def test_rename_in_place_names_nothing(tmp_path):
    s, _ = rpair(tmp_path)
    msg = run_err("frames", s, "--rename", "run", "x")
    assert "E_SELECT" in msg and f"no frame 'run' or run/... in {s}" in msg


def test_rename_in_place_bad_id(tmp_path):
    s, _ = rpair(tmp_path)
    assert "E_BAD_ID" in run_err("frames", s, "--rename", "walk", "a b")


def test_rename_in_place_with_selection_is_refused(tmp_path):
    s, _ = rpair(tmp_path)
    msg = run_err("frames", f"{s}:walk", "--rename", "walk", "x")
    assert "E_BAD_ARG" in msg and f"frames {s} --rename walk NEWGROUP" in msg


def test_rename_in_place_not_with_rm(tmp_path):
    s, _ = rpair(tmp_path)
    assert "E_BAD_ARG" in run_err("frames", s, "--rename", "walk", "x", "--rm", "idle")


def test_rename_in_place_unnamed_grid(tmp_path):
    s = write(tmp_path, "ant.px", "k #000000\nk\n")
    assert "E_MIXED_FRAMES" in run_err("frames", s, "--rename", "ant", "x")


def test_rename_in_place_renders_the_same(tmp_path, capsys):
    s, _ = rpair(tmp_path)
    before = pxart.parse(s)
    run("frames", s, "--rename", "walk", "w")
    after = pxart.parse(s)
    for f in before.frames:
        g = after.get(pxart.renamed_id(f.id, [("walk", "w")]))
        assert list(pxart.pixels(before.image(f))) == list(pxart.pixels(after.image(g)))


def test_renamed_id():
    r = [("walk", "wick/walk"), ("idle", "rest")]
    assert pxart.renamed_id("walk", r) == "wick/walk"
    assert pxart.renamed_id("walk/down/0", r) == "wick/walk/down/0"
    assert pxart.renamed_id("walker/0", r) == "walker/0"
    assert pxart.renamed_id("idle", r) == "rest"
    assert pxart.renamed_id("idle/0", r) == "rest/0"
    assert pxart.renamed_id("run/walk", r) == "run/walk"


def test_help_documents_rename_and_prefix():
    text = " ".join(pxart.__doc__.split())
    assert "--prefix wick/ puts wick/ in front of every copy's id" in text
    assert "--rename GROUP NEWGROUP without --copy-to renames in FILE itself" in text


def test_readme_documents_rename_and_prefix():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "under other ids with `--prefix wick/` or `--rename walk wick/walk`" in readme
    assert "`frames hero.px --rename walk hero/walk` renames a group in place" in readme


# ---------------------------------------------------------------- --rekey KEYS | KEY=DSTKEY, and one WARNING per key
# --rekey was all or nothing, and couldn't say "use DST's j anyway"; the scarf-on-awning trap was buried in a long note.

AWN_I = ("r #c4473a\nk #000000\nI #c4473a\n@variant dusk\nr #a33a4c\nI #903040\nk #000011\n"
         "@frame awning\nrk\nI.\n")  # DST: I is the scarf's base red, dimmed otherwise at dusk; k dims too


def rk_pair(tmp_path, dst=AWN_I):
    return write(tmp_path, "keeper.px", SCARF_WALK), write(tmp_path, "party.px", dst)


def test_rekey_spec_values():
    assert pxart.rekey_spec(None) is None
    assert pxart.rekey_spec("") == (None, {}, {})
    assert pxart.rekey_spec("o,r") == ({"o", "r"}, {}, {})
    assert pxart.rekey_spec("k=j,n=q") == (set(), {"k": "j", "n": "q"}, {})
    assert pxart.rekey_spec("k=j,n") == ({"n"}, {"k": "j"}, {})
    assert pxart.rekey_spec("r=r") == (set(), {"r": "r"}, {})
    assert pxart.rekey_spec("0") == ({"0"}, {}, {})


@pytest.mark.parametrize("bad", ["ab", "k=", "k=jj", ".", "k=.", "k,,n", ",k", "k=j=q", "#", "k=@"])
def test_rekey_spec_bad(bad):
    with pytest.raises(pxart.PxError) as e:
        pxart.rekey_spec(bad)
    assert codes(e) == ["E_BAD_ARG"] and "want keys, comma-separated" in str(e.value)


def test_rekey_spec_twice():
    with pytest.raises(pxart.PxError) as e:
        pxart.rekey_spec("k,k=j")
    assert "names 'k' twice" in str(e.value)


def test_rekey_spec_target_also_listed():
    with pytest.raises(pxart.PxError) as e:
        pxart.rekey_spec("k=j,j")
    assert "j is where --rekey puts another key" in str(e.value)


@pytest.mark.parametrize("argv,want", [
    (["compose", "-o", "o.px", "--rekey", "a.px:x@0,0"], ["compose", "-o", "o.px", "--rekey=", "a.px:x@0,0"]),
    (["frames", "a.px", "--copy-to", "d.px", "--rekey"], ["frames", "a.px", "--copy-to", "d.px", "--rekey="]),
    (["frames", "a.px", "--rekey", "--copy-to", "d.px"], ["frames", "a.px", "--rekey=", "--copy-to", "d.px"]),
    (["frames", "a.px", "--rekey", "o,r"], ["frames", "a.px", "--rekey", "o,r"]),
    (["frames", "a.px", "--rekey", "k=j"], ["frames", "a.px", "--rekey", "k=j"]),
    (["frames", "a.px", "--rekey", "k"], ["frames", "a.px", "--rekey", "k"]),
    (["crop", "a.px:x", "--rekey", "0,0,2,2", "-o", "o.px"], ["crop", "a.px:x", "--rekey=", "0,0,2,2", "-o", "o.px"]),
    (["crop", "a.px:x", "--rekey", "-1,0,2,2", "-o", "o.px"], ["crop", "a.px:x", "--rekey=", "-1,0,2,2", "-o", "o.px"]),
    (["crop", "a.px:x", "0,0,2,2", "--rekey", "1,2", "-o", "o"],
     ["crop", "a.px:x", "0,0,2,2", "--rekey", "1,2", "-o", "o"]),
    (["frames", "a.px", "--rekey=o"], ["frames", "a.px", "--rekey=o"]),
])
def test_rekey_args(argv, want):
    assert pxart.rekey_args(argv) == want


def test_bare_rekey_before_a_layer_still_works(tmp_path, capsys):
    a, b = write(tmp_path, "awning.px", AWNING), write(tmp_path, "scarf.px", SCARF)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--rekey", "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1") == 0
    assert run("compose", "-o", f"{out}:z", "--rekey", f"{b}:s@0,0") == 0


def test_crop_rekey_before_the_rectangle(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("crop", f"{s}:walk/0", "--rekey", "0,0,2,2", "-o", f"{d}:cut") == 0
    assert pxart.parse(d).get("cut").size == (2, 2)


def test_crop_rekey_equals_digit_keys(tmp_path):
    s, d = rk_pair(tmp_path)
    msg = run_err("crop", f"{s}:walk/0", "0,0,2,2", "--rekey=1,2,3,4", "-o", f"{d}:cut")
    assert "E_SELECT" in msg and "--rekey 1,2,3,4: no layer draws with 1 2 3 4" in msg


# --- one WARNING per key

def test_vclash_warning_per_key_copy_to(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d) == 0
    warns = [l for l in capsys.readouterr().out.splitlines() if l.startswith("WARNING:")]
    assert len(warns) == 2
    assert warns[0].startswith(f"WARNING: FILE ({s}:walk) draws 'k' #000000 in {d}'s variant colors, not keeper.px's:")
    assert warns[1].startswith(f"WARNING: FILE ({s}:walk) draws 'r' #c4473a in {d}'s variant colors, not keeper.px's:")
    assert warns[1].endswith("frames --copy-to --rekey r gives it a key of its own")


def test_vclash_warning_names_each_variant_that_differs(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d)
    out = capsys.readouterr().out
    assert "draws 'r' #c4473a in " in out and "not keeper.px's: dusk #a33a4c (keeper.px: #c4473a);" in out


def test_vclash_warning_is_short(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d)
    assert all(len(l.replace(str(tmp_path), "T")) < 200 for l in capsys.readouterr().out.splitlines())


def test_vclash_warnings_every_key_on_its_own_line_many_keys(tmp_path, capsys):
    # Twelve keys, one line each (the session's note was one 1500-char line).
    keys = "abcdefghijmn"
    src = "".join(f"{k} #10{i:02d}10\n" for i, k in enumerate(keys)) + "@variant night\n" + "".join(
        f"{k} #00{i:02d}00\n" for i, k in enumerate(keys)) + "@frame w/0\n" + keys + "\n"
    dst = "".join(f"{k} #10{i:02d}10\n" for i, k in enumerate(keys)) + "@variant night\n" + "".join(
        f"{k} #20{i:02d}20\n" for i, k in enumerate(keys)) + "@frame a\n" + keys + "\n"
    s, d = write(tmp_path, "s.px", src), write(tmp_path, "d.px", dst)
    assert run("frames", s, "--copy-to", d) == 0
    lines = capsys.readouterr().out.splitlines()
    warns = [l for l in lines if l.startswith("WARNING:")]
    assert len(warns) == 12 and all(f"draws {k!r}" in w for k, w in zip(keys, warns))
    assert all(len(l.replace(str(tmp_path), "T")) < 200 for l in lines)


def test_vclash_warning_paste(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("paste", f"{s}:walk/0", "--into", f"{d}:awning", "--at", "0,0") == 0
    warns = [l for l in capsys.readouterr().out.splitlines() if l.startswith("WARNING:")]
    assert [w.split(" draws ")[1][:3] for w in warns] == ["'k'", "'r'"]
    assert all(w.endswith("gives it a key of its own") and "paste --rekey" in w for w in warns)


def test_vclash_warning_compose_existing(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("compose", "-o", f"{d}:c", f"{s}:walk/0@0,0") == 0
    warns = [l for l in capsys.readouterr().out.splitlines() if l.startswith("WARNING:")]
    assert len(warns) == 2 and all(f"layer 1 ({s}:walk/0) draws" in w for w in warns)
    assert "compose --rekey k gives" in warns[0] and "compose --rekey r gives" in warns[1]


def test_vclash_warning_crop_existing(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("crop", f"{s}:walk/0", "0,0,2,2", "-o", f"{d}:cut") == 0
    assert "crop --rekey r gives it a key of its own" in capsys.readouterr().out


def test_vclash_warning_compose_new(tmp_path, capsys):
    a, b = write(tmp_path, "awning.px", AWNING), write(tmp_path, "scarf.px", SCARF)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1") == 0
    warns = [l for l in capsys.readouterr().out.splitlines() if l.startswith("WARNING:")]
    assert len(warns) == 1 and "draws 'r'" in warns[0]


def test_no_vclash_warning_with_rekey(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey") == 0
    assert "WARNING" not in capsys.readouterr().out


def test_vclash_warning_not_printed_when_the_command_fails(tmp_path, capsys):
    s, d = rk_pair(tmp_path, AWN_I.replace("k #000000", "k #101010"))  # k: another color: E_KEY_CONFLICT
    code = run("frames", f"{s}:walk", "--copy-to", d)
    assert code == 1 and "WARNING" not in capsys.readouterr().out


def test_report_rekey_note_and_uncovered_note_on_lines_of_their_own(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--rekey")
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith(f"note: --rekey gives {s}'s keys free ones in {d}:")
    assert any(l.startswith("note: keeper.px has no @variant dusk") for l in lines[1:])


# --- --rekey KEYS: only those

def test_rekey_only_listed_keys_move(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "r") == 0
    out = capsys.readouterr().out
    g = pxart.parse(d).get("walk/0").grid
    assert g[0][1] == "k" and g[0][0] not in ("r", "k")  # r moved, k stayed
    warns = [l for l in out.splitlines() if l.startswith("WARNING:")]
    assert len(warns) == 1 and "draws 'k'" in warns[0]


def test_rekey_only_two_keys(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "k,r") == 0
    g = pxart.parse(d).get("walk/0").grid
    assert g[0][0] not in ("r", "k") and g[0][1] not in ("r", "k") and "WARNING" not in capsys.readouterr().out


def test_rekey_only_leaves_a_color_conflict_an_error(tmp_path, capsys):
    s, d = rk_pair(tmp_path, AWN_I.replace("k #000000", "k #101010"))
    before = d.read_text()
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--rekey", "r")
    assert "E_KEY_CONFLICT" in msg and "'k' #000000" in msg and d.read_text() == before


def test_rekey_only_key_that_needs_no_move(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "q,r") == 0
    assert f"note: --rekey q: it needs no other key; {d} has it in the same colors" in capsys.readouterr().out


def test_rekey_only_key_not_drawn(tmp_path):
    s, d = rk_pair(tmp_path)
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--rekey", "z")
    assert "E_SELECT" in msg and f"--rekey z: FILE ({s}:walk) doesn't draw with z" in msg


def test_rekey_only_paste(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("paste", f"{s}:walk/0", "--into", f"{d}:awning", "--at", "0,0", "--rekey", "r") == 0
    g = pxart.parse(d).get("awning").grid
    assert g[0][1] == "k" and g[0][0] not in ("r", "k")


def test_rekey_only_compose_existing(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("compose", "-o", f"{d}:c", f"{s}:walk/0@0,0", "--rekey", "r") == 0
    g = pxart.parse(d).get("c").grid
    assert g[0][1] == "k" and g[0][0] not in ("r", "k")
    assert "compose --rekey k gives it a key of its own" in capsys.readouterr().out


def test_rekey_only_compose_key_no_layer_draws(tmp_path):
    s, d = rk_pair(tmp_path)
    msg = run_err("compose", "-o", f"{d}:c", f"{s}:walk/0@0,0", "--rekey", "z")
    assert "E_SELECT" in msg and "--rekey z: no layer draws with z" in msg


def test_rekey_only_compose_needless(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("compose", "-o", f"{d}:c", f"{s}:walk/0@0,0", "--rekey", "q,r") == 0
    assert f"note: --rekey q: no other key needed; {d} has it in the same colors" in capsys.readouterr().out


def test_rekey_only_compose_new_three_packs(tmp_path, capsys):
    # Only r moves: the other clashes stay E_KEY_CONFLICT.
    code, out, _ = compose_packs(tmp_path, "--rekey", "r")
    assert code == 1 and not out.exists()


def test_rekey_only_crop_existing(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("crop", f"{s}:walk/0", "0,0,2,2", "-o", f"{d}:cut", "--rekey", "r") == 0
    assert pxart.parse(d).get("cut").grid[0][1] == "k"


# --- --rekey KEY=DSTKEY

def test_rekey_explicit_uses_dsts_key(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "r=I,k") == 0
    g = pxart.parse(d).get("walk/0").grid
    assert g[0][0] == "I" and g[0][1] not in ("k", "r", "I")


def test_rekey_explicit_warns_per_variant_color(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "r=I,k")
    warns = [l for l in capsys.readouterr().out.splitlines() if l.startswith("WARNING:")]
    assert warns == [f"WARNING: --rekey r=I: FILE ({s}:walk)'s 'r' #c4473a is {d}'s 'I', which {d}'s variants color "
                     "otherwise: dusk #903040 (keeper.px: #c4473a); those pixels take party.px's colors there"
                     .replace("party.px's colors", f"{d}'s colors")]


def test_rekey_explicit_says_what_it_did(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "r=I,k")
    line = capsys.readouterr().out.splitlines()[0]
    assert line.startswith(f"note: --rekey gives {s}'s keys other ones in {d}: ")
    assert "'r>I'" in line and line.endswith("; r as --rekey named, k free")


def test_rekey_explicit_renders_dst_colors_in_variants(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "r=I,k")
    assert color_in(d, "walk/0", "dusk", (0, 0)) == pxart.hex2rgba("#903040")
    assert color_in(d, "walk/0", None, (0, 0)) == pxart.hex2rgba("#c4473a")


def test_rekey_explicit_other_base_color_is_an_error(tmp_path):
    s, d = rk_pair(tmp_path)
    before = d.read_text()
    d.write_text(AWN_I.replace("I #c4473a\n", "I #c4473a\nX #123456\n"))
    before = d.read_text()
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--rekey", "r=X")
    assert "E_KEY_CONFLICT" in msg and f"--rekey r=X: {d}'s 'X' is #123456, and FILE ({s}:walk)'s 'r' #c4473a" in msg
    assert "--rekey r" in msg and d.read_text() == before


def test_rekey_explicit_onto_a_source_key_is_an_error(tmp_path):
    s, d = rk_pair(tmp_path)
    msg = run_err("frames", f"{s}:walk", "--copy-to", d, "--rekey", "r=q")
    assert "E_KEY_CONFLICT" in msg and "has a key 'q' of its own" in msg


def test_rekey_explicit_to_a_free_key(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "r=Z,k=Y") == 0
    doc = pxart.parse(d)
    assert doc.get("walk/0").grid[0] == "ZY" and doc.palette["Z"] == pxart.hex2rgba("#c4473a")
    assert "WARNING" not in capsys.readouterr().out
    assert reads_as(d, "walk/0", s, "walk/0", {})


def test_rekey_explicit_keep_on_purpose(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "r=r,k=k") == 0
    out = capsys.readouterr().out
    assert pxart.parse(d).get("walk/0").grid[0] == "rk" and "--rekey gives" not in out
    warns = [l for l in out.splitlines() if l.startswith("WARNING:")]
    assert len(warns) == 2 and warns[0].startswith("WARNING: --rekey k=k:")
    assert warns[1].startswith("WARNING: --rekey r=r:")


def test_rekey_explicit_not_drawn(tmp_path):
    s, d = rk_pair(tmp_path)
    assert "doesn't draw with z" in run_err("frames", f"{s}:walk", "--copy-to", d, "--rekey", "z=I")


def test_rekey_explicit_paste(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("paste", f"{s}:walk/0", "--into", f"{d}:awning", "--at", "0,0", "--rekey", "r=I,k") == 0
    assert pxart.parse(d).get("awning").grid[0][0] == "I"
    assert "WARNING: --rekey r=I: SRC" in capsys.readouterr().out


def test_rekey_explicit_paste_mirrored(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("paste", f"{s}:walk/0+h", "--into", f"{d}:awning", "--at", "0,0", "--rekey", "r=I,k") == 0
    assert pxart.parse(d).get("awning").grid[0][1] == "I"


def test_rekey_explicit_compose_existing(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("compose", "-o", f"{d}:c", f"{s}:walk/0@0,0", "--rekey", "r=I,k") == 0
    out = capsys.readouterr().out
    assert pxart.parse(d).get("c").grid[0][0] == "I"
    assert f"WARNING: --rekey r=I: layer 1 ({s}:walk/0)'s 'r' #c4473a is {d}'s 'I'" in out
    assert "r as --rekey named" in out


def test_rekey_explicit_compose_existing_other_base_color(tmp_path):
    s, d = rk_pair(tmp_path)
    before = d.read_text()
    msg = run_err("compose", "-o", f"{d}:c", f"{s}:walk/0@0,0", "--rekey", "r=k")
    assert "E_KEY_CONFLICT" in msg and d.read_text() == before


def test_rekey_explicit_compose_two_layers_of_one_file(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("compose", "-o", f"{d}:c", "--size", "4x2", f"{s}:walk/0@0,0", f"{s}:walk/1@2,0", "--rekey",
               "r=I,k") == 0
    g = pxart.parse(d).get("c").grid
    assert g[0][0] == "I" and g[0][3] == "I"


def test_rekey_explicit_compose_new_free_name(tmp_path, capsys):
    a, b = write(tmp_path, "awning.px", AWNING), write(tmp_path, "scarf.px", SCARF)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1", "--rekey", "r") == 0
    capsys.readouterr()
    out2 = tmp_path / "o2.px"
    assert run("compose", "-o", out2, "--size", "2x2", f"{a}:a@0,0", f"{b}:s@0,1", "--rekey", "r=S") == 0
    doc = pxart.parse(out2)
    assert doc.frames[0].grid[1][0] == "S" and doc.variants["night"]["S"] == pxart.hex2rgba("#83344e")
    assert looks_as_its_file(out2, [(a, "a", 0, 0), (b, "s", 0, 1)])


def test_rekey_explicit_crop_existing(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("crop", f"{s}:walk/0", "0,0,2,2", "-o", f"{d}:cut", "--rekey", "r=I,k") == 0
    assert pxart.parse(d).get("cut").grid[0][0] == "I"


def test_rekey_explicit_source_file_unchanged(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "r=I,k")
    assert s.read_text() == SCARF_WALK


# --- the note that offers DST's same-base key anyway

def test_rekey_hint_names_the_same_base_key(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey") == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == (f"note: {d} has the base colors of r as I, in other variant colors; --rekey k,r=I uses those "
                        "anyway (a warning then says which variant colors change)")


def test_rekey_hint_list_works(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "k,r=I") == 0
    assert pxart.parse(d).get("walk/0").grid[0][0] == "I"


def test_rekey_hint_not_for_the_same_key_name(tmp_path, capsys):
    s, d = rk_pair(tmp_path, AWN_I.replace("I #c4473a\n", "").replace("I #903040\n", "").replace("I.", ".."))
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey") == 0
    assert "uses those anyway" not in capsys.readouterr().out


def test_rekey_hint_compose_existing(tmp_path, capsys):
    s, d = rk_pair(tmp_path)
    assert run("compose", "-o", f"{d}:c", f"{s}:walk/0@0,0", "--rekey") == 0
    assert f"note: {d} has the base colors of r as I, in other variant colors; --rekey " in capsys.readouterr().out


def test_help_documents_rekey_keys():
    text = " ".join(pxart.__doc__.split())
    assert "--rekey KEYS touches only the keys it lists" in text
    assert "--rekey k=j,n=q uses OUT's j and q, which must be in k's and n's base colors" in text
    assert "r=r keeps r as it is on purpose" in text
    assert "write --rekey=1,2,3,4 to name four digit keys there" in text
    assert "one WARNING per key OUT's variants color otherwise" in text


def test_cmd_help_rekey_keys(capsys):
    for cmd in ("frames", "paste", "crop", "compose"):
        assert "KEY=OUTKEY to use OUT's key" in " ".join(cmd_help(capsys, cmd).split()), cmd


def test_readme_documents_rekey_keys():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`--rekey o,r` moves only those keys, and `--rekey k=j,n=q` puts k and n on OUT's own j and q" in readme


# ---------------------------------------------------------------- palette --remove KEYS [--to KEY]

RM = ("pxart 1\n@palette pal.px\n# the outline\nk #000000\nj #000000\n. transparent\nn #123456\nz #ffffff\n"
      "@variant night\nk #000011\n# lit\nz #ffffff\n\n@frame a\nkj\nz.\n@frame b\njj\n..\n")
RM_PAL = "p #445566\nk #999999\n@variant night\np #112233\n"


def rm_file(tmp_path, text=RM):
    write(tmp_path, "pal.px", RM_PAL)
    return write(tmp_path, "s.px", text)


def test_remove_unused_key(tmp_path, capsys):
    s = rm_file(tmp_path)
    assert run("palette", s, "--remove", "n") == 0
    assert capsys.readouterr().out == f"removed n; wrote {s}\n"
    assert s.read_text() == RM.replace("n #123456\n", "")


def test_remove_key_with_variant_line_and_comments(tmp_path, capsys):
    s = rm_file(tmp_path, RM.replace("kj\n", "nj\n").replace("z.\n", "n.\n"))
    assert run("palette", s, "--remove", "z") == 0
    assert capsys.readouterr().out == f"removed z (and its line in @variant night); wrote {s}\n"
    text = s.read_text()
    assert "z #" not in text and "# lit" not in text and "@variant night\nk #000011\n" in text


def test_remove_used_key_is_an_error(tmp_path):
    s = rm_file(tmp_path)
    before = s.read_text()
    msg = run_err("palette", s, "--remove", "j")
    assert "E_SELECT" in msg and "frames still draw with j (j: 3 px in a, b)" in msg
    assert f"pxart palette {s} --remove j --to K" in msg and s.read_text() == before


def test_remove_used_key_to_another(tmp_path, capsys):
    s = rm_file(tmp_path)
    assert run("palette", s, "--remove", "j", "--to", "k") == 0
    assert capsys.readouterr().out == f"repainted 3 px of j as k; removed j; wrote {s}\n"
    doc = pxart.parse(s)
    assert "j" not in doc.palette and doc.get("a").grid == ["kk", "z."] and doc.get("b").grid == ["kk", ".."]


def test_remove_to_renders_the_same_when_colors_match(tmp_path, capsys):
    s = rm_file(tmp_path)
    before = pxart.parse(s)
    imgs = [list(pxart.pixels(before.image(f))) for f in before.frames]
    run("palette", s, "--remove", "j", "--to", "k")
    after = pxart.parse(s)
    assert [list(pxart.pixels(after.image(f))) for f in after.frames] == imgs


def test_remove_several_keys(tmp_path, capsys):
    s = rm_file(tmp_path)
    assert run("palette", s, "--remove", "j,n", "--to", "k") == 0
    doc = pxart.parse(s)
    assert "j" not in doc.palette and "n" not in doc.palette
    assert capsys.readouterr().out == f"repainted 3 px of j as k; removed j, n; wrote {s}\n"


def test_remove_several_keys_compact_form(tmp_path, capsys):
    s = rm_file(tmp_path)
    assert run("palette", s, "--remove", "jn", "--to", "k") == 0
    assert "n" not in pxart.parse(s).palette


def test_remove_keeps_the_dot_line_in_place(tmp_path, capsys):
    s = rm_file(tmp_path)
    run("palette", s, "--remove", "j", "--to", "k")
    assert "k #000000\n. transparent\nn #123456\n" in s.read_text()


def test_remove_imported_key(tmp_path, capsys):
    # s.px doesn't draw with p and nothing else under tmp_path imports pal.px: p goes from pal.px, night line too.
    s = rm_file(tmp_path)
    before = s.read_text()
    assert run("palette", s, "--remove", "p") == 0
    out = capsys.readouterr().out
    assert f"removed p (and its line in @variant night) from {tmp_path / 'pal.px'} (no other .px under " in out
    assert f"no change: {s}; wrote {tmp_path / 'pal.px'}" in out
    assert s.read_text() == before and pxart.parse(tmp_path / "pal.px", palette_only=True).palette == {
        "k": pxart.hex2rgba("#999999")}


def test_remove_local_override_gets_the_imported_color(tmp_path, capsys):
    s = rm_file(tmp_path, RM.replace("kj\n", "jj\n"))
    assert run("palette", s, "--remove", "k") == 0
    assert "k now has the imported color (k #999999)" in capsys.readouterr().out
    assert pxart.parse(s).resolved()["k"] == pxart.hex2rgba("#999999")


def test_remove_missing_key(tmp_path):
    s = rm_file(tmp_path)
    assert f"{s} has no key 'q'" in run_err("palette", s, "--remove", "q")


def test_remove_dot(tmp_path):
    s = rm_file(tmp_path)
    assert "E_BAD_ARG" in run_err("palette", s, "--remove", ".")


def test_remove_to_bad(tmp_path):
    s = rm_file(tmp_path)
    assert "not a key of" in run_err("palette", s, "--remove", "j", "--to", "Q")
    assert "it is being removed" in run_err("palette", s, "--remove", "j,k", "--to", "k")
    assert "'.' erases" in run_err("palette", s, "--remove", "j", "--to", ".")


def test_remove_to_imported_key(tmp_path, capsys):
    s = rm_file(tmp_path)
    assert run("palette", s, "--remove", "j", "--to", "p") == 0
    assert pxart.parse(s).get("b").grid == ["pp", ".."]


def test_to_needs_remove(tmp_path):
    s = rm_file(tmp_path)
    msg = run_err("palette", s, "--to", "k")
    assert "E_BAD_ARG" in msg and "--to k goes with --remove KEYS" in msg


@pytest.mark.parametrize("more", [["--add", "q=#010101"], ["--hoist", "n"], ["--variant", "night", "--keep", "k"],
                                  ["--comment", "n", "x"], ["--comment-header", ""], ["--export", "x.gpl"]])
def test_remove_alone(tmp_path, more):
    s = rm_file(tmp_path)
    msg = run_err("palette", s, "--remove", "n", *more)
    assert "E_BAD_ARG" in msg and "--remove takes keys out of FILE: give it alone" in msg


def test_remove_from_a_palette_file(tmp_path, capsys):
    rm_file(tmp_path)
    p = tmp_path / "pal.px"
    assert run("palette", p, "--remove", "p") == 0
    out = capsys.readouterr().out
    assert "removed p (and its line in @variant night)" in out
    assert "sprites that import pal.px and draw with p no longer can (check them)" in out
    assert pxart.parse(p, palette_only=True).variants == {"night": {}}


def test_remove_twice_is_an_error_the_second_time(tmp_path, capsys):
    s = rm_file(tmp_path)
    run("palette", s, "--remove", "n")
    assert "has no key 'n'" in run_err("palette", s, "--remove", "n")


def test_remove_file_still_parses_and_checks(tmp_path, capsys):
    s = rm_file(tmp_path)
    run("palette", s, "--remove", "j,n,z", "--to", "k")
    doc = pxart.parse(s, strict=True)
    assert set(doc.palette) == {"k"}


def test_help_documents_remove():
    text = " ".join(pxart.__doc__.split())
    assert "[--remove KEYS [--to KEY]]" in text
    assert "--remove k,n takes FILE's own keys out" in text and "'palette party.px --remove k,n --to j'" in text


def test_readme_documents_remove():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`--remove k,n` takes out keys no frame draws with (`--to j` repaints their pixels as j first; an " \
        "imported key then goes from its palette file only when no other `.px` under the directory holding both, or " \
        "`--in DIR`, uses it)" in readme


# ---------------------------------------------------------------- every example command line in the help runs
# The help's examples are what a newcomer copies. Each one quoted in pxart help all runs here, in a fresh copy of a
# directory of fixture files, and must exit 0: an example can't drift from the tool.

def help_examples(doc):
    """The example command lines quoted in the reference: 'CMD ...' or 'pxart CMD ...' in single quotes, joined across
    wrapped lines; quotes inside ('s>a') are kept."""
    cmds = set(pxart.parser(describe=False)[1].choices)
    flat = " ".join(l.strip() for l in doc.splitlines())
    out = []
    for m in re.finditer(r"(?<![\w'])'(pxart )?([a-z][a-z-]*) ", flat):
        if m.group(2) not in cmds:
            continue
        i, inner = m.end(), False
        while i < len(flat):
            if flat[i] == "'":
                if inner:
                    inner = False
                elif flat[i - 1] == " " and i + 1 < len(flat) and flat[i + 1] != " ":
                    inner = True
                else:
                    break
            i += 1
        out.append(flat[m.start() + 1:i])
    return out


# Not runnable as written, on purpose: placeholders (FILE, DST, TOPIC...) and fragments of a sentence.
EXAMPLE_SKIP = {
    "extract FILE:SEL -o DST": "placeholders",
    "new DST --empty --palette P.px": "placeholders",
    "pxart recolor FILE ... -o rekeyed/FILE.px": "placeholders",
    "shade --ramp": "a fragment ('a later 'shade --ramp' or recolor')",
    "shade --ramp XxcCw": "a fragment (the ramp a cloak needs)",
    "pxart help TOPIC": "placeholder",
    "pxart help CMD": "placeholder",
}


def hero_frame(w, h, fill):
    rows = [("k" + fill * (w - 2) + "k") if 0 < y < h - 1 else "k" * w for y in range(h)]
    return "\n".join(rows) + "\n"


def help_fixtures(d):
    """The files the reference's examples name, each just enough for its example."""
    (d / "crossover").mkdir()
    hero_pal = "pxart 1\nk #1a1423\nX #202040\nx #404080\nc #6060c0\nC #8080e0\nw #c0c0ff\nW #ffffff\n"
    hero = hero_pal + "@anim walk/down ms=100\n"
    for fid in ("idle/0", "idle/1", "idle/2", "idle/3", "walk/down/0", "walk/down/1", "walk/left/0", "walk/left/1",
                "attack/2"):
        hero += f"@frame {fid}\n" + hero_frame(32, 32, "c")
    (d / "hero.px").write_text(hero)
    (d / "beast.px").write_text(hero_pal + "".join(f"@frame idle/{i}\n" + hero_frame(16, 16, "x") for i in range(4)))
    (d / "w1.txt").write_text(hero_frame(32, 32, "C"))
    (d / "palette.px").write_text("# shared\nj #2a1f33\nq #3d4f86\n@variant night\nj #0f0f22\n")
    (d / "party.px").write_text("pxart 1\n@palette palette.px\nk #1a1423\nn #3d4f86\n@frame idle\nkjn\nqqj\n")
    (d / "keeper.px").write_text("pxart 1\nk #2b1e2f\nr #c4473a\n@variant night\nr #83344e\n@anim walk ms=150\n"
                                 "@frame walk/0\nkr\nrk\n@frame walk/1\nrk\nkr\n")
    (d / "wick.px").write_text("pxart 1\nk #1a1423\no #f58b3c\n@frame walk/down/0\nko\n@frame walk/down/1\nok\n")
    (d / "pal.px").write_text("k #1a1423\nw #efe6d2\ny #f3cf6b\nE #ffe07a\n")
    (d / "rock.px").write_text("o #6a6a6a\n" + ("." * 16 + "\n") * 16)
    (d / "field.px").write_text("s #00ff00\nt #008800\nst\nts\n")
    (d / "crossover" / "dock.px").write_text("pxart 1\nk #1a1423\n@frame a\nkk\n")
    (d / "harbor.px").write_text("pxart 1\ng #808080\nb #2040a0\n@frame cobble\n" + ("g" * 16 + "\n") * 16
                                 + "".join(f"@frame water/{i}\n" + ("b" * 16 + "\n") * 16 for i in range(2))
                                 + "@frame stall\n" + ("g" * 32 + "\n") * 32)
    (d / "tiles.px").write_text("pxart 1\ng #808080\nb #2040a0\no #8b5a3c\n@frame cobble\n" + ("g" * 16 + "\n") * 16
                                + "".join(f"@frame water/{i}\n" + ("b" * 16 + "\n") * 16 for i in range(2))
                                + "@frame crate\n" + ("o" * 15 + ".\n") * 16)
    (d / "stall.px").write_text("r #c4473a\n" + ("r" * 32 + "\n") * 32)
    (d / "boy.px").write_text("pxart 1\nk #965340\no #141b1b\n\nko\n")
    (d / "lamp.px").write_text("y #f3cf6b\n" + ("." * 7 + "yy" + "." * 7 + "\n") * 32)
    (d / "market.map").write_text("# ground layer, then props\nc tiles.px:cobble\nw tiles.px:water/0\n"
                                  "x tiles.px:crate+h\nS stall.px+b\nL lamp.px+b\nl lamp.px+hb\n\n"
                                  "cccccc\ncccccc\nwwwwww\n---\n......\n.S.L.l\nx.....\n")
    Image.new("RGBA", (96, 48), (40, 60, 80, 255)).save(d / "scene.png")


def test_help_examples_are_found():
    got = help_examples(pxart.__doc__)
    assert len(got) >= 25
    assert "palette pal.px --variant night --add k=#120e22 --comment @variant night \"night: only lamps glow\"" in got
    assert "pxart recolor field.px 's>a' 't>b' -o rekeyed/field.px" in got
    assert set(EXAMPLE_SKIP) <= set(got)  # a skip that no longer matches an example goes too


@pytest.mark.parametrize("example", [e for e in help_examples(pxart.__doc__) if e not in EXAMPLE_SKIP])
def test_help_example_runs(tmp_path, capsys, monkeypatch, example):
    help_fixtures(tmp_path)
    monkeypatch.chdir(tmp_path)
    argv = shlex.split(example)
    if argv[0] == "pxart":
        argv = argv[1:]
    stdin = None
    if "<" in argv:
        at = argv.index("<")
        stdin, argv = (tmp_path / argv[at + 1]).read_text(), argv[:at]
    if argv[0] == "new" and "--empty" in argv:  # it starts the file the next example copies frames into
        (tmp_path / argv[1]).unlink(missing_ok=True)
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    try:
        pxart.main(argv)
        code = 0
    except SystemExit as e:
        code = e.code
    got = capsys.readouterr()
    assert code in (0, None), (example, code, got.out, got.err)



# ---------------------------------------------------------------- every error line starts with the command
# The zsh-modifier E_FILE line had no 'render: ' in front and showed an absolute path; ERRORS says every line has it.

def test_zsh_hint_line_has_the_command_and_is_one_line(tmp_path):
    msg = run_err("render", tmp_path / "hero.pxalk" / "0", "-o", tmp_path / "x.png")
    assert msg.startswith(f"render: {tmp_path / 'hero.pxalk' / '0'}: E_FILE: No such file or directory; ")
    assert "\n" not in msg and "zsh ate a ':'" in msg


def test_missing_input_under_cwd_shows_a_relative_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    msg = run_err("render", tmp_path / "hero.pxalk" / "0", "-o", "x.png")
    assert msg.startswith("render: hero.pxalk/0: E_FILE: ") and str(tmp_path) not in msg


def test_missing_input_as_typed_relative(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_err("flip", "sub/nope.px").startswith("flip: sub/nope.px: E_FILE: No such file or directory")


def test_missing_input_outside_cwd_stays_absolute(tmp_path, monkeypatch):
    (tmp_path / "here").mkdir()
    monkeypatch.chdir(tmp_path / "here")
    assert run_err("flip", tmp_path / "nope.px").startswith(f"flip: {tmp_path / 'nope.px'}: E_FILE")


def test_file_error_unit():
    e = FileNotFoundError(2, "No such file or directory", "a.pxb")
    assert pxart.file_error("check", e).startswith("check: a.pxb: E_FILE: No such file or directory; 'a.pxb' looks")
    e = PermissionError(13, "Permission denied", "b.px")
    assert pxart.file_error("flip", e) == "flip: b.px: E_FILE: Permission denied"
    assert pxart.file_error("flip", OSError("boom")) == "flip: E_FILE: boom"


ERR_PX = "k #000000\nw #ffffff\n@anim walk ms=100\n@frame walk/0\nkw\nwk\n@frame walk/1\nwk\nkw\n"


def error_cases(t):
    """(cmd argv, one failing call) for every command: a missing input, a bad argument, a bad selection."""
    f, m, o, png = t / "f.px", t / "missing.px", t / "o.px", t / "o.png"
    return [
        ["render", m], ["render", f"{f}:nope"], ["render", f, "--variant", "night"],
        ["sheet", m, "-o", png], ["sheet", t / "p.px", "-o", png],
        ["anim", m], ["anim", f"{f}:nope"], ["anim", f, "--variant", "x"],
        ["onion", m, f, "-o", png], ["onion", f"{f}:walk/0", f"{f}:walk/1", "-o", png, "--rows", "x"],
        ["scene", "-o", png, f"{m}@0,0"], ["scene", "-o", png, f"{f}:walk/0"], ["scene", "-o", png, "--tint", "zz"],
        ["tint", t / "missing.png", "#000000"], ["tint", t / "a.png", "nope"],
        ["stats", m], ["stats", f"{f}:nope"],
        ["frames", m], ["frames", f, "--rm", "nope"], ["frames", f, "--copy-to", m],
        ["frames", f, "--move", "walk"], ["frames", f, "--rename", "nope", "x"], ["frames", f, "--prefix", "a/"],
        ["flip", m], ["flip", f"{f}:nope"],
        ["rotate", m, "90"], ["transpose", m],
        ["shift", m, "--dx", "1"], ["shift", f, "--fill", "Q"],
        ["mask", m, "--keep", "0,0,1,1"], ["mask", f, "--keep", "x"],
        ["recolor", m, "k=w"], ["recolor", f, "q=w"], ["recolor", f, "k=#zz"],
        ["set", m, "k", "0,0"], ["set", f, "k", "9,9"], ["set", f, "Q", "0,0"],
        ["crop", m, "0,0,1,1", "-o", o], ["crop", f"{f}:walk/0", "x", "-o", o],
        ["paste", m, "--into", f, "--at", "0,0"], ["paste", f"{f}:walk/0", "--into", m, "--at", "0,0"],
        ["new", o, "--size", "zz"], ["new", o], ["new", o, "--empty", "--palette", m],
        ["put", f"{m}:x"],
        ["fill", m, "k"], ["fill", f, "Q"],
        ["line", m, "k", "0,0", "1,1"], ["line", f, "k", "x", "1,1"],
        ["rect", f, "k", "0,0"], ["poly", f, "Q", "0,0", "1,1"], ["ellipse", f, "k", "1,1,1"],
        ["arc", f, "k", "1,1,1", "x"], ["flood", f, "k", "9,9"],
        ["outline", m, "--key", "k"], ["outline", f, "--key", "Q"],
        ["shade", m, "--ramp", "kw"], ["shade", f, "--ramp", "Q"],
        ["extract", m, "-o", o], ["extract", f"{f}:nope", "-o", o],
        ["compose", "-o", o, f"{m}@0,0"], ["compose", "-o", o, f"{f}:walk/0@x"],
        ["compose", "-o", o, f"{f}:walk/0@0,0", "--rekey", "Q"],
        ["dup", m, "x"], ["dup", f"{f}:walk/0", "walk/1"],
        ["anim-set", m], ["anim-set", f"{f}:walk", "ms=x"],
        ["palette", m], ["palette", f, "--add", "k"], ["palette", f, "--remove", "k"],
        ["palette", f, "--comment", "k"],
        ["export", m, "--frames", t / "d"], ["export", f, "--frames", t / "d", "--variant", "x"],
        ["help", "nope"],
        ["from-png", t / "missing.png"],
    ]


def test_error_cases_cover_every_command(tmp_path):
    cmds = {c[0] for c in error_cases(tmp_path)} | {"check"}  # check reports per file: its own test
    assert cmds == set(pxart.parser(describe=False)[1].choices)


@pytest.mark.parametrize("n", range(len(error_cases(pathlib.Path("/t")))))
def test_every_error_line_starts_with_the_command(tmp_path, capsys, n):
    write(tmp_path, "f.px", ERR_PX)
    write(tmp_path, "p.px", "k #000000\n")
    Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(tmp_path / "a.png")
    argv = [str(a) for a in error_cases(tmp_path)[n]]
    with pytest.raises(SystemExit) as e:
        pxart.main(argv)
    msg = e.value.code
    assert isinstance(msg, str), (argv, msg)  # an error line, not a bare exit code
    lines = msg.splitlines()
    assert lines and all(l.startswith(f"{argv[0]}: ") or l.startswith(" ") for l in lines), (argv, msg)
    assert "E_" in lines[0], (argv, msg)


def test_check_missing_file_has_the_command(tmp_path):
    assert run_err("check", tmp_path / "missing.px").startswith("check: ")


def test_help_documents_e_file_prefix():
    assert "'render: hero.pxalk/0: E_FILE: No such file or directory; 'hero.pxalk/0' looks like zsh" in " ".join(
        pxart.__doc__.split())



# ---------------------------------------------------------------- palette FILE explains its variants
# 'recolors' hid that lamps are set brighter at night; the palette's own comments weren't shown; a palette file's usage
# column was blank.

EXPLAIN = ("# Harbor palette: warm lamps, cool sea.\n# second header line\npxart 1\nk #2a1f33\n# the lamp\ny #f3cf6b\n"
           "W #efe6d2\n# glass\n# (two lines)\ng #808080\n\n# night: only the lamp stays lit\n@variant night\n"
           "k #0f0f22\n# lit: brighter at night\ny #ffd66e\nW #fff4d0\ng #808080\n\n@variant fog\nk #2a1f40\n")


def pal_lines(tmp_path, capsys, text=EXPLAIN, *more):
    p = write(tmp_path, "pal.px", text)
    assert run("palette", p, *more) == 0
    return capsys.readouterr().out.splitlines()


def test_explain_header_first(tmp_path, capsys):
    lines = pal_lines(tmp_path, capsys)
    assert lines[:2] == ["# Harbor palette: warm lamps, cool sea.", "# second header line"]


def test_explain_key_comment_inline(tmp_path, capsys):
    lines = pal_lines(tmp_path, capsys)
    assert "y #f3cf6b     local  # the lamp" in lines and "W #efe6d2     local" in lines


def test_explain_two_line_key_comment_joined(tmp_path, capsys):
    assert "g #808080     local  # glass / (two lines)" in pal_lines(tmp_path, capsys)


def test_explain_palette_file_has_no_usage_column_or_trailing_space(tmp_path, capsys):
    lines = pal_lines(tmp_path, capsys)
    assert "k #2a1f33     local" in lines and all(l == l.rstrip() for l in lines)
    assert not any(" used" in l for l in lines)


def test_explain_brightens_the_lamps(tmp_path, capsys):
    lines = pal_lines(tmp_path, capsys)
    assert "  night: recolors (darker) k; brightens y W; relists unchanged: g; inherits: nothing" in lines


def test_explain_as_bright_recolor(tmp_path, capsys):
    text = "a #ff0000\nb #000000\n@variant v\na #fe0000\nb #000000\n"
    lines = pal_lines(tmp_path, capsys, text)
    assert lines[-1] == "  v: recolors (darker) a; relists unchanged: b; inherits: nothing"
    text = "a #00000080\n@variant v\na #000000\n"
    assert pal_lines(tmp_path, capsys, text)[-1] == "  v: recolors (as bright) a; inherits: nothing"


def test_explain_all_three_kinds_in_order(tmp_path, capsys):
    text = "a #808080\nb #808080\nc #00000080\n@variant v\nb #ffffff\nc #000000\na #000000\n"
    assert pal_lines(tmp_path, capsys, text)[-1] == ("  v: recolors (darker) a; recolors (as bright) c; brightens b; "
                                                      "inherits: nothing")


def test_explain_variant_comment_under_its_line(tmp_path, capsys):
    lines = pal_lines(tmp_path, capsys)
    at = next(i for i, l in enumerate(lines) if l.startswith("  night:"))
    assert lines[at + 1] == "    # night: only the lamp stays lit"


def test_explain_variant_key_comment(tmp_path, capsys):
    lines = pal_lines(tmp_path, capsys)
    at = next(i for i, l in enumerate(lines) if l.startswith("  night:"))
    assert lines[at + 2] == "    y: # lit: brighter at night" and len(lines) == at + 3


def test_explain_variant_without_comments(tmp_path, capsys):
    lines = pal_lines(tmp_path, capsys)
    at = next(i for i, l in enumerate(lines) if l.startswith("  fog:"))
    assert lines[at] == "  fog: brightens k; inherits: y W g" and lines[at + 1].startswith("  night:")


def test_explain_imported_palettes_comments_in_a_sprite(tmp_path, capsys):
    write(tmp_path, "pal.px", EXPLAIN)
    s = write(tmp_path, "s.px", "# the sprite's own header\n@palette pal.px\n@frame a\nky\n")
    assert run("palette", s) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "# Harbor palette: warm lamps, cool sea." and "# the sprite's own header" not in lines
    assert "y #f3cf6b     shared   used 1  # the lamp" in lines
    assert "    # night: only the lamp stays lit" in lines


def test_explain_sprite_keeps_used_column(tmp_path, capsys):
    s = write(tmp_path, "s.px", "k #000000\n# ink\nw #ffffff\n@frame a\nkw\n")
    assert run("palette", s) == 0
    assert "w #ffffff     local    used 1  # ink" in capsys.readouterr().out.splitlines()


def test_palette_in_dir_counts_importers(tmp_path, capsys):
    write(tmp_path, "pal.px", EXPLAIN)
    write(tmp_path, "a.px", "@palette pal.px\n@frame a\nky\n")
    write(tmp_path, "b.px", "@palette pal.px\nk #111111\n@frame a\nkW\n")  # its own k: not pal's
    write(tmp_path, "c.px", "q #000000\n@frame a\nq\n")  # imports nothing
    (tmp_path / "sub").mkdir()
    write(tmp_path / "sub", "d.px", "@palette ../pal.px\n@frame a\ny\n")
    lines = pal_lines(tmp_path, capsys, EXPLAIN, "--in", tmp_path)
    assert f"imported by 3 of the .px files under {tmp_path}: {tmp_path / 'a.px'}, {tmp_path / 'b.px'}, " \
           f"{tmp_path / 'sub' / 'd.px'}" in lines
    assert "k #2a1f33     local    used by 1 file" in lines
    assert "y #f3cf6b     local    used by 2 files  # the lamp" in lines
    assert "W #efe6d2     local    used by 1 file" in lines
    assert "g #808080     local    used by 0 files  # glass / (two lines)" in lines


def test_palette_in_dir_through_a_nested_import(tmp_path, capsys):
    write(tmp_path, "pal.px", EXPLAIN)
    write(tmp_path, "mid.px", "@palette pal.px\nq #010101\n")
    write(tmp_path, "a.px", "@palette mid.px\n@frame a\nyq\n")
    lines = pal_lines(tmp_path, capsys, EXPLAIN, "--in", tmp_path)
    assert f"imported by 2 of the .px files under {tmp_path}: {tmp_path / 'a.px'}, {tmp_path / 'mid.px'}" in lines
    assert "y #f3cf6b     local    used by 1 file  # the lamp" in lines


def test_palette_in_dir_nobody(tmp_path, capsys):
    lines = pal_lines(tmp_path, capsys, EXPLAIN, "--in", tmp_path)
    assert f"imported by 0 of the .px files under {tmp_path}" in lines


def test_palette_in_dir_needs_a_palette_file(tmp_path):
    s = write(tmp_path, "s.px", "k #000000\n@frame a\nk\n")
    msg = run_err("palette", s, "--in", tmp_path)
    assert "E_BAD_ARG" in msg and "counts the files that import a palette file" in msg


def test_brightness():
    assert pxart.brightness((255, 255, 255, 255)) == pytest.approx(255)
    assert pxart.brightness((0, 0, 0, 255)) == 0
    assert pxart.brightness((0, 255, 0, 255)) > pxart.brightness((255, 0, 0, 255)) > pxart.brightness((0, 0, 255, 255))
    assert pxart.brightness((255, 255, 255, 0)) == 0


def test_comment_text():
    assert pxart.comment_text(None) == "" and pxart.comment_text(["", "  "]) == ""
    assert pxart.comment_text(["# a", "#b", "", "#  c "]) == "# a / b / c"
    assert pxart.comment_text(["#"]) == ""


def test_help_documents_palette_explained():
    text = " ".join(pxart.__doc__.split())
    assert "A recolor is darker, brighter ('brightens y W': lamps lit brighter at night) or as bright" in text
    assert "--in DIR counts the .px files under DIR that import it" in text
    assert "[--remove KEYS [--to KEY]] [--in DIR]" in text


# ---------------------------------------------------------------- sheet --rows group: one animation group per row

ROWS_SRC = ("pxart 1\nk #000000\nw #ffffff\n@anim walk/down ms=100\n@anim walk/up ms=100\n"
            + "".join(f"@frame walk/down/{i}\nkw\nwk\n" for i in range(3))
            + "".join(f"@frame walk/up/{i}\nkkk\nwww\nkkk\n" for i in range(2))
            + "@frame icon\nk\n@frame badge\nw\n")


def rows_items(tmp_path, text=ROWS_SRC, name="p.px"):
    return pxart.all_items([str(write(tmp_path, name, text))])


def test_sheet_rows_default_is_cols(tmp_path):
    its = rows_items(tmp_path)
    assert pxart.sheet_rows(its, 3) == [[0, 1, 2], [3, 4, 5], [6]]
    assert pxart.sheet_rows(its, 3, "cols") == [[0, 1, 2], [3, 4, 5], [6]]


def test_sheet_rows_group_one_row_each(tmp_path):
    its = rows_items(tmp_path)
    assert pxart.sheet_rows(its, 8, "group") == [[0, 1, 2], [3, 4], [5, 6]]


def test_sheet_rows_group_wraps_within_a_long_group(tmp_path):
    its = rows_items(tmp_path)
    assert pxart.sheet_rows(its, 2, "group") == [[0, 1], [2], [3, 4], [5, 6]]


def test_sheet_rows_group_one_col(tmp_path):
    its = rows_items(tmp_path)
    assert pxart.sheet_rows(its, 1, "group") == [[0], [1], [2], [3], [4], [5], [6]]


def test_sheet_rows_group_interleaved_frames_gather(tmp_path):
    text = "k #000000\n@frame a/0\nk\n@frame b/0\nk\n@frame a/1\nk\n"
    assert pxart.sheet_rows(rows_items(tmp_path, text), 8, "group") == [[0, 2], [1]]


def test_sheet_rows_group_same_group_two_files(tmp_path):
    a = write(tmp_path, "a.px", "k #000000\n@frame walk/0\nk\n@frame walk/1\nk\n")
    b = write(tmp_path, "b.px", "k #000000\n@frame walk/0\nk\n")
    its = pxart.all_items([str(a), str(b)])
    assert pxart.sheet_rows(its, 8, "group") == [[0, 1], [2]]


def test_sheet_rows_group_pngs_alone(tmp_path):
    for n in "xy":
        Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(tmp_path / f"{n}.png")
    its = pxart.all_items([str(tmp_path / "x.png"), str(tmp_path / "y.png")])
    assert pxart.sheet_rows(its, 8, "group") == [[0], [1]]


def test_sheet_rows_group_unnamed_grid(tmp_path):
    its = rows_items(tmp_path, "k #000000\nkk\n")
    assert pxart.sheet_rows(its, 8, "group") == [[0]]


def test_sheet_fit_rows_group_image_is_one_row_per_group(tmp_path, capsys):
    p = write(tmp_path, "p.px", ROWS_SRC)
    one, grouped = tmp_path / "one.png", tmp_path / "g.png"
    assert run("sheet", p, "--fit", "-o", one, "--scale", "4") == 0
    assert run("sheet", p, "--fit", "--rows", "group", "-o", grouped, "--scale", "4") == 0
    a, b = Image.open(one), Image.open(grouped)
    assert b.height > a.height and b.width < a.width
    # three rows: each as tall as its tallest frame (8, 12, 4 px at scale 4) plus the label band and padding
    assert b.height == 10 + (8 + 26 + 10) + (12 + 26 + 10) + (4 + 26 + 10)


def test_sheet_rows_group_without_fit(tmp_path, capsys):
    p = write(tmp_path, "p.px", ROWS_SRC)
    out = tmp_path / "g.png"
    assert run("sheet", p, "--rows", "group", "-o", out, "--scale", "4") == 0
    img = Image.open(out)
    cells_h = 3 * 4 + 26 + 10
    assert img.height == 10 + 3 * cells_h


def test_sheet_rows_cols_is_the_default_bytes(tmp_path, capsys):
    p = write(tmp_path, "p.px", ROWS_SRC)
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    assert run("sheet", p, "--fit", "-o", a, "--cols", "3") == 0
    assert run("sheet", p, "--fit", "--rows", "cols", "-o", b, "--cols", "3") == 0
    assert a.read_bytes() == b.read_bytes()


def test_sheet_rows_group_with_align_pivot(tmp_path, capsys):
    p = write(tmp_path, "p.px", ROWS_SRC.replace("@anim walk/down ms=100", "@anim walk/down ms=100 pivot=1,1"))
    assert run("sheet", p, "--fit", "--rows", "group", "--align", "pivot", "-o", tmp_path / "s.png") == 0


def test_sheet_rows_bad_choice(tmp_path):
    p = write(tmp_path, "p.px", ROWS_SRC)
    with pytest.raises(SystemExit) as e:
        pxart.main(["sheet", str(p), "--rows", "anim", "-o", str(tmp_path / "s.png")])
    assert e.value.code == 2


def test_sheet_rows_group_labels_every_frame_once(tmp_path, capsys):
    # every frame is drawn: the sheet with rows by group has the same cells, only placed otherwise
    its = rows_items(tmp_path)
    got = sorted(n for row in pxart.sheet_rows(its, 2, "group") for n in row)
    assert got == list(range(len(its)))


def test_help_documents_sheet_rows_group():
    text = " ".join(pxart.__doc__.split())
    assert "[--fit] [--align bottom|pivot] [--rows cols|group]" in text
    assert "--rows group starts a row for each animation group" in text


def test_readme_documents_sheet_rows_group():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`--rows group` puts each animation group on a row of its own" in readme


# ---------------------------------------------------------------- check: a line per file, -v for a line per frame

CHK = ("pxart 1\nk #000000\nw #ffffff\nz #ff0000\n@anim walk ms=100\n"
       + "".join(f"@frame walk/{i}\nkw\nwk\n" for i in range(4)) + "@frame big\nkwk\nwkw\nkkk\n")


def chk(tmp_path, capsys, *more, text=CHK, name="c.px"):
    p = write(tmp_path, name, text)
    code = run("check", p, *more)
    return code, p, capsys.readouterr().out.splitlines()


def test_check_one_line_per_file(tmp_path, capsys):
    code, p, out = chk(tmp_path, capsys)
    assert code == 0
    assert out == [f"ok   {p}: 5 frames, 2x2, 3x3, 2c", f"     {p}: unused keys z"]


def test_check_verbose_a_line_per_frame(tmp_path, capsys):
    code, p, out = chk(tmp_path, capsys, "-v")
    assert out == [f"ok   {p}:walk/{i}: 2x2 2c" for i in range(4)] + [f"ok   {p}:big: 3x3 2c",
                                                                     f"     {p}: unused keys z"]


def test_check_verbose_long_flag(tmp_path, capsys):
    code, p, out = chk(tmp_path, capsys, "--verbose")
    assert len(out) == 6


def test_check_color_range(tmp_path, capsys):
    text = CHK.replace("@frame big\nkwk\nwkw\nkkk\n", "@frame big\nkwz\nwkw\nkkk\n")
    code, p, out = chk(tmp_path, capsys, text=text)
    assert out[0] == f"ok   {p}: 5 frames, 2x2, 3x3, 2-3c"


def test_check_failing_frames_listed_without_v(tmp_path, capsys):
    code, p, out = chk(tmp_path, capsys, "--size", "2x2")
    assert code == 1
    assert out[:2] == [f"FAIL {p}: 1 of 5 frames fail", f"     FAIL {p}:big: 3x3 2c; size 3x3 != 2x2"]


def test_check_failing_frames_verbose(tmp_path, capsys):
    code, p, out = chk(tmp_path, capsys, "--size", "2x2", "-v")
    assert code == 1 and f"FAIL {p}:big: 3x3 2c; size 3x3 != 2x2" in out and f"ok   {p}:walk/0: 2x2 2c" in out


def test_check_single_frame_file_line_is_the_frames(tmp_path, capsys):
    code, p, out = chk(tmp_path, capsys, text="k #000000\nkk\n", name="one.px")
    assert out == [f"ok   {p}: 2x1 1c"]


def test_check_single_named_frame(tmp_path, capsys):
    code, p, out = chk(tmp_path, capsys, text="k #000000\n@frame idle\nkk\n", name="one.px")
    assert out == [f"ok   {p}:idle: 2x1 1c"]


def test_check_many_sizes_listed_short(tmp_path, capsys):
    text = "k #000000\n" + "".join(f"@frame f{i}\n" + ("k" * (i + 1) + "\n") for i in range(7))
    code, p, out = chk(tmp_path, capsys, text=text)
    assert out[0] == f"ok   {p}: 7 frames, 1x1, 2x1, 3x1, 4x1 and 3 more, 1c"


def test_check_summary_for_several_files(tmp_path, capsys):
    a = write(tmp_path, "a.px", CHK)
    b = write(tmp_path, "b.px", "k #000000\nkk\n")
    assert run("check", a, b) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == "2 files, 6 frames, 1 warning"


def test_check_summary_counts_failures(tmp_path, capsys):
    a = write(tmp_path, "a.px", CHK)
    b = write(tmp_path, "b.px", "k #000000\nkk\nk\n")
    c = write(tmp_path, "c.px", "k #000000\nkkk\n")
    assert run("check", a, b, c, "--size", "2x1") == 1
    assert capsys.readouterr().out.splitlines()[-1] == "3 files, 6 frames, 1 warning, 3 failed"


def test_check_summary_counts_palette_files_and_maps(tmp_path, capsys):
    d = pack_dir(tmp_path)
    run("check", d)
    assert capsys.readouterr().out.splitlines()[-1] == "4 files, 2 frames, 0 warnings"


def test_check_summary_counts_lookalike_notes(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nkk\n")
    b = write(tmp_path, "b.px", "к #000000\nкк\n")  # Cyrillic ka
    run("check", a, b)
    assert capsys.readouterr().out.splitlines()[-1].startswith("2 files, ")


def test_check_no_summary_for_one_file(tmp_path, capsys):
    code, p, out = chk(tmp_path, capsys)
    assert not any("files," in l for l in out)


def test_check_strict_quiet_by_default(tmp_path, capsys):
    # The session's crossover: ~150 frames printed one per line; now one line per file.
    text = "pxart 1\nk #000000\n@anim walk ms=100\n" + "".join(f"@frame walk/{i}\nk\n" for i in range(150))
    code, p, out = chk(tmp_path, capsys, "--strict", text=text)
    assert code == 0 and out == [f"ok   {p}: 150 frames, 1x1, 1c"]


def test_check_strict_verbose_still_per_frame(tmp_path, capsys):
    text = "pxart 1\nk #000000\n@anim walk ms=100\n" + "".join(f"@frame walk/{i}\nk\n" for i in range(150))
    code, p, out = chk(tmp_path, capsys, "--strict", "-v", text=text)
    assert len(out) == 150


def test_check_file_error_still_fails_in_the_summary(tmp_path, capsys):
    a = write(tmp_path, "a.px", CHK)
    b = write(tmp_path, "b.px", "k #000000\nkq\n")
    assert run("check", a, b) == 1
    out = capsys.readouterr().out.splitlines()
    assert f"FAIL {b}: 1 error(s)" in out and out[-1] == "2 files, 5 frames, 1 warning, 1 failed"


def test_check_exit_code_after_a_failing_then_passing_file(tmp_path, capsys):
    a = write(tmp_path, "a.px", "k #000000\nkq\n")
    b = write(tmp_path, "b.px", CHK)
    assert run("check", a, b) == 1


def test_help_documents_check_per_file():
    text = " ".join(pxart.__doc__.split())
    assert "check FILE|DIR... [--palette P] [--size WxH] [--max-colors N] [--strict] [-v]" in text
    assert "'FAIL party.px: 2 of 40 frames fail'" in text and "'6 files, 150 frames, 3 warnings'" in text


def test_readme_documents_check_per_file():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "one line per file, the failing frames under it, and a summary like `6 files, 150 frames, 3 warnings`" \
        in readme and "`-v` for a line per frame" in readme


# ---------------------------------------------------------------- recolor: renames apply together (a key renamed away
# is free for another; 'a>b' 'b>a' swaps names)

CHAIN = ("pxart 1\n# the grass\ng #56864c\n# the dirt\nd #965340\nr #d14b34\n\n@variant dusk\ng #546d45\nd #83473b\n\n"
         "@frame a\ngdr\n@frame b\nddg\n")


def test_recolor_rename_into_a_key_renamed_away(tmp_path, capsys):
    # The reported call's shape: 'g>G' frees g in the same call, so 'd>g' gives d's pixels g's old name, in d's colors.
    p = write(tmp_path, "c.px", CHAIN)
    before = renders(p)
    assert run("recolor", p, "g>G", "d>g") == 0
    doc = pxart.parse(p)
    assert grids(p) == {"a": ["Ggr"], "b": ["ggG"]}
    assert doc.palette == {"G": pxart.hex2rgba("#56864c"), "g": pxart.hex2rgba("#965340"), "r": pxart.hex2rgba("#d14b34")}
    assert doc.variants["dusk"] == {"G": pxart.hex2rgba("#546d45"), "g": pxart.hex2rgba("#83473b")}
    assert renders(p) == before
    assert capsys.readouterr().out == f"applied to 2 frames; wrote {p}\n"


def test_recolor_rename_into_a_freed_key_any_order(tmp_path):
    a = write(tmp_path, "a.px", CHAIN)
    b = write(tmp_path, "b.px", CHAIN)
    assert run("recolor", a, "g>G", "d>g") == 0
    assert run("recolor", b, "d>g", "g>G") == 0
    assert a.read_text() == b.read_text()


def test_recolor_rename_into_a_freed_key_keeps_the_comments_with_the_colors(tmp_path):
    p = write(tmp_path, "c.px", CHAIN)
    assert run("recolor", p, "g>G", "d>g") == 0
    text = p.read_text()
    assert "# the grass\nG #56864c\n# the dirt\ng #965340\n" in text


def test_recolor_rename_swap_of_names(tmp_path):
    p = write(tmp_path, "c.px", CHAIN)
    before = renders(p)
    assert run("recolor", p, "g>d", "d>g") == 0
    doc = pxart.parse(p)
    assert grids(p) == {"a": ["dgr"], "b": ["ggd"]}
    assert doc.palette == {"d": pxart.hex2rgba("#56864c"), "g": pxart.hex2rgba("#965340"), "r": pxart.hex2rgba("#d14b34")}
    assert list(doc.palette) == ["d", "g", "r"]
    assert doc.variants["dusk"] == {"d": pxart.hex2rgba("#546d45"), "g": pxart.hex2rgba("#83473b")}
    assert renders(p) == before


def test_recolor_rename_swap_twice_is_the_original(tmp_path):
    p = write(tmp_path, "c.px", CHAIN)
    assert run("recolor", p, "g>d", "d>g") == 0
    assert run("recolor", p, "g>d", "d>g") == 0
    assert p.read_text() == CHAIN


def test_recolor_rename_rotation_of_three(tmp_path):
    p = write(tmp_path, "c.px", CHAIN)
    before = renders(p)
    assert run("recolor", p, "g>d", "d>r", "r>g") == 0
    assert grids(p) == {"a": ["drg"], "b": ["rrd"]}
    doc = pxart.parse(p)
    assert doc.palette == {"d": pxart.hex2rgba("#56864c"), "r": pxart.hex2rgba("#965340"), "g": pxart.hex2rgba("#d14b34")}
    assert renders(p) == before


def test_recolor_rename_chain_into_a_new_key(tmp_path):
    # g>d d>Q: d's pixels take the new Q, g's take d's old name; nothing collides.
    p = write(tmp_path, "c.px", CHAIN)
    before = renders(p)
    assert run("recolor", p, "g>d", "d>Q") == 0
    assert grids(p) == {"a": ["dQr"], "b": ["QQd"]}
    assert renders(p) == before


def test_recolor_rename_swap_with_output_leaves_source(tmp_path):
    p = write(tmp_path, "c.px", CHAIN)
    o = tmp_path / "o.px"
    assert run("recolor", p, "g>d", "d>g", "-o", o) == 0
    assert p.read_text() == CHAIN and grids(o) == {"a": ["dgr"], "b": ["ggd"]}
    assert renders(o) == renders(p)


def test_recolor_rename_swap_with_a_move(tmp_path):
    # r=g paints r's pixels with g as the file has it before the call: g then stays, so d>g can't take its name.
    p = write(tmp_path, "c.px", CHAIN)
    msg = run_err("recolor", p, "g>G", "d>g", "r=g")
    assert "E_BAD_ARG" in msg and "'d>g' needs a new key, and 'g' stays one: 'g>G' leaves it in the palette " \
        "('r=g' paints pixels g)" in msg
    assert p.read_text() == CHAIN


def test_recolor_rename_into_a_key_kept_by_the_region(tmp_path):
    p = write(tmp_path, "c.px", CHAIN)
    msg = run_err("recolor", p, "g>G", "d>g", "--region", "0,0,1,1")
    assert "E_BAD_ARG" in msg and "'g' stays one: 'g>G' leaves it in the palette (pixels outside the recolor " \
        "still draw with it)" in msg
    assert p.read_text() == CHAIN


def test_recolor_rename_into_a_key_kept_by_other_frames(tmp_path):
    p = write(tmp_path, "c.px", CHAIN)
    msg = run_err("recolor", f"{p}:a", "g>G", "d>g")
    assert "'g' stays one" in msg and "pixels outside the recolor still draw with it" in msg
    assert p.read_text() == CHAIN


def test_recolor_rename_into_a_key_kept_by_its_import(tmp_path):
    write(tmp_path, "pal.px", "g #56864c\n")
    p = write(tmp_path, "c.px", "@palette pal.px\nd #965340\n\ngd\n")
    msg = run_err("recolor", p, "g>G", "d>g")
    assert "'g' stays one: 'g>G' leaves it in the palette (it comes from an imported palette file)" in msg


def test_recolor_rename_into_a_taken_key_names_free_keys_not_a_repaint(tmp_path):
    # The old message said 'write d=g', which repaints d's pixels in g's color: not what 'd>g' asks for.
    p = write(tmp_path, "c.px", CHAIN)
    msg = run_err("recolor", p, "d>g")
    assert "'d>g' needs a new key, and 'g' is already one (#56864c): name a free key ('d>a'; free: a b c), or " \
        "free 'g' in the same call: 'g>a' 'd>g'" in msg
    assert "d=g" not in msg and p.read_text() == CHAIN


def test_recolor_rename_into_a_taken_imported_key_offers_no_freeing(tmp_path):
    write(tmp_path, "pal.px", "g #56864c\n")
    p = write(tmp_path, "c.px", "@palette pal.px\nd #965340\n\ngd\n")
    msg = run_err("recolor", p, "d>g")
    assert "'g' is already one (#56864c): name a free key ('d>a'; free: a b c)" in msg and "same call" not in msg


def test_recolor_rename_the_suggested_fix_works(tmp_path):
    p = write(tmp_path, "c.px", CHAIN)
    before = renders(p)
    msg = run_err("recolor", p, "d>g")
    fix = msg.split("in the same call: ")[1]
    assert run("recolor", p, *shlex.split(fix)) == 0
    assert grids(p) == {"a": ["agr"], "b": ["gga"]} and renders(p) == before


def test_recolor_rename_swap_with_a_shared_variant(tmp_path):
    # pal.px's dusk recolors key d; after the swap local d is the old g, which dusk must not recolor: a line of its own.
    write(tmp_path, "pal.px", "q #000000\n\n@variant dusk\nd #010203\n")
    p = write(tmp_path, "c.px", "@palette pal.px\ng #56864c\nd #965340\n\ngdq\n")
    before = renders(p)
    assert run("recolor", p, "g>d", "d>g") == 0
    assert pxart.parse(p).frames[0].grid == ["dgq"]
    assert renders(p) == before


def test_recolor_rename_swap_keeps_relists(tmp_path):
    # night lists l in its base color (kept lit): after the swap its new name is listed the same way.
    p = write(tmp_path, "c.px", "l #fff4b0\nk #000000\n\n@variant night\nk #000011\nl #fff4b0\n\nkl\n")
    before = renders(p)
    assert run("recolor", p, "l>k", "k>l") == 0
    doc = pxart.parse(p)
    assert doc.variants["night"] == {"l": (0, 0, 0x11, 255), "k": (0xff, 0xf4, 0xb0, 255)}
    assert doc.frames[0].grid == ["lk"] and renders(p) == before


def test_recolor_rename_swap_adds_no_relist(tmp_path):
    # g has no dusk line (it inherits) and d has one: after the swap the key that inherits still has none.
    p = write(tmp_path, "c.px", "g #56864c\nd #965340\n\n@variant dusk\nd #83473b\n\ngd\n")
    assert run("recolor", p, "g>d", "d>g") == 0
    assert pxart.parse(p).variants["dusk"] == {"g": pxart.hex2rgba("#83473b")}


def test_recolor_rename_new_key_twice_names_both_moves(tmp_path):
    p = write(tmp_path, "c.px", CHAIN)
    msg = run_err("recolor", p, "g>Q", "d>Q")
    assert "'d>Q' and 'g>Q' both give pixels the new key 'Q'" in msg and p.read_text() == CHAIN


def test_recolor_rename_to_itself_is_bad_arg(tmp_path):
    p = write(tmp_path, "c.px", CHAIN)
    msg = run_err("recolor", p, "g>g")
    assert "E_BAD_ARG" in msg and "'g>g' gives g's pixels the key they have" in msg


def test_recolor_rename_chain_through_a_real_shell(tmp_path):
    import shutil, subprocess
    script = pathlib.Path(pxart.__file__)
    shell = ["zsh", "-f", "-c"] if shutil.which("zsh") else ["bash", "-c"] if shutil.which("bash") else None
    if not shell:
        pytest.skip("no zsh or bash")
    p = write(tmp_path, "c.px", CHAIN)
    r = subprocess.run(shell + [f'"{sys.executable}" "{script}" recolor "{p}" \'g>d\' \'d>g\''], capture_output=True,
                       text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert grids(p) == {"a": ["dgr"], "b": ["ggd"]}


def test_help_documents_recolor_renames_together():
    text = " ".join(pxart.__doc__.split())
    assert "a key another 'a>b' of the call renames away is free for a new key, so 'g>r' 'd>g' renames g to r and d " \
        "to g, and 'a>b' 'b>a' swaps two keys' names (every pixel keeps its look)" in text


def test_readme_documents_recolor_swap_of_names():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "a key renamed away is free for another: `'a>b' 'b>a'` swaps two names" in readme


# ---------------------------------------------------------------- palette FILE --remove of an imported key: repaint
# FILE, then take it out of the palette file only when no other .px under DIR uses it

CAST_PAL = "# cast palette\no #141b1b\n# boy's white\nw #e3f1f5\nt #548789\nx #4e484a\n\n@variant dusk\no #10121a\nw #bcbcc2\n"
CAST_BOY = "pxart 1\n@palette pal.px\n\n@frame boy/0\nowt\nwwo\n"
CAST_GIRL = "pxart 1\n@palette pal.px\n\n@frame girl/0\noxt\n"


def cast(tmp_path, boy=CAST_BOY, girl=CAST_GIRL, sub=""):
    d = tmp_path / sub if sub else tmp_path
    d.mkdir(parents=True, exist_ok=True)
    pal = write(tmp_path, "pal.px", CAST_PAL)
    b = write(d, "boy.px", boy.replace("@palette pal.px", f"@palette {'../' * len(pathlib.Path(sub).parts)}pal.px"))
    g = write(tmp_path, "girl.px", girl) if girl is not None else None
    return pal, b, g


def test_remove_imported_key_only_this_file_uses(tmp_path, capsys):
    pal, b, g = cast(tmp_path, girl="pxart 1\n@palette pal.px\n\n@frame girl/0\noxo\n")
    girl_before = renders(g)
    assert run("palette", b, "--remove", "w", "--to", "t") == 0
    out = capsys.readouterr().out
    assert out == (f"repainted 3 px of w as t; removed w (and its line in @variant dusk) from {pal} (no other .px "
                   f"under {tmp_path}/ uses it); wrote {b}; wrote {pal}\n")
    assert pxart.parse(b).frames[0].grid == ["ott", "tto"]
    pdoc = pxart.parse(pal, palette_only=True)
    assert "w" not in pdoc.palette and "w" not in pdoc.variants["dusk"]
    assert "# boy's white" not in pal.read_text() and "# cast palette" in pal.read_text()
    assert renders(g) == girl_before


def test_remove_imported_key_scope_relative_to_the_current_directory(tmp_path, capsys, monkeypatch):
    pal, b, g = cast(tmp_path, girl="pxart 1\n@palette pal.px\n\n@frame girl/0\noxo\n")
    (tmp_path / "cast").mkdir()
    for f in (pal, b, g):
        f.rename(tmp_path / "cast" / f.name)
    monkeypatch.chdir(tmp_path)
    assert run("palette", "cast/boy.px", "--remove", "w", "--to", "t") == 0
    assert capsys.readouterr().out == ("repainted 3 px of w as t; removed w (and its line in @variant dusk) from "
                                       "cast/pal.px (no other .px under cast/ uses it); wrote cast/boy.px; wrote "
                                       "cast/pal.px\n")


def test_remove_imported_key_another_file_draws_stays(tmp_path, capsys):
    pal, b, g = cast(tmp_path)
    before_pal = pal.read_text()
    girl_before = renders(g)
    assert run("palette", b, "--remove", "t", "--to", "o") == 0
    out = capsys.readouterr().out
    assert out.startswith("repainted 1 px of t as o; t stays in ")
    assert f"t stays in {pal}: girl.px uses it (of the .px files under " in out and out.rstrip().endswith(f"wrote {b}")
    assert pal.read_text() == before_pal and renders(g) == girl_before
    assert pxart.parse(b).frames[0].grid == ["owo", "wwo"]


def test_remove_imported_key_listed_in_another_files_variant_stays(tmp_path, capsys):
    # girl.px doesn't draw with w, but its dusk lists it: removing w from pal.px would break girl.px.
    pal, b, g = cast(tmp_path, girl="pxart 1\n@palette pal.px\n\n@variant dusk\nw #000000\n\n@frame girl/0\noxt\n")
    before_pal = pal.read_text()
    assert run("palette", b, "--remove", "w", "--to", "t") == 0
    assert "w stays in" in capsys.readouterr().out and pal.read_text() == before_pal
    assert run("check", g) == 0


def test_remove_imported_key_a_file_with_its_own_line_is_no_user(tmp_path, capsys):
    pal, b, g = cast(tmp_path, girl="pxart 1\n@palette pal.px\nw #ffffff\n\n@frame girl/0\nowt\n")
    assert run("palette", b, "--remove", "w", "--to", "t") == 0
    assert "removed w (and its line in @variant dusk) from" in capsys.readouterr().out
    assert run("check", g) == 0


def test_remove_imported_key_users_outside_the_directory_are_not_seen_without_in(tmp_path, capsys):
    # boy.px sits in sprites/ beside a far-away user; the default scope is the directory holding boy.px and pal.px
    # (tmp_path itself here), so girl.px at the top is seen.
    pal, b, g = cast(tmp_path, sub="sprites")
    assert run("palette", b, "--remove", "t", "--to", "o") == 0
    assert "t stays in" in capsys.readouterr().out and "t #548789" in pal.read_text()


def test_remove_imported_key_in_dir_narrows_the_scope(tmp_path, capsys):
    pal, b, g = cast(tmp_path, sub="sprites")
    assert run("palette", b, "--remove", "t", "--to", "o", "--in", tmp_path / "sprites") == 0
    out = capsys.readouterr().out
    assert f"removed t from {pal} (no other .px under {tmp_path / 'sprites'}/ uses it)" in out
    assert "t #" not in pal.read_text()


def test_remove_imported_key_in_dir_widens_the_scope(tmp_path, capsys):
    # pal.px and boy.px in pal/ and sprites/, girl.px in tiles/: the default scope (tmp_path) sees it anyway;
    # --in tiles says so too.
    (tmp_path / "pal").mkdir()
    (tmp_path / "sprites").mkdir()
    (tmp_path / "tiles").mkdir()
    pal = write(tmp_path / "pal", "pal.px", CAST_PAL)
    b = write(tmp_path / "sprites", "boy.px", CAST_BOY.replace("pal.px", "../pal/pal.px"))
    write(tmp_path / "tiles", "girl.px", CAST_GIRL.replace("pal.px", "../pal/pal.px"))
    assert run("palette", b, "--remove", "t", "--to", "o") == 0
    assert "tiles/girl.px uses it" in capsys.readouterr().out and "t #548789" in pal.read_text()
    assert run("palette", b, "--remove", "x", "--in", tmp_path / "tiles") == 0
    assert "x stays in" in capsys.readouterr().out


def test_remove_imported_key_used_needs_to(tmp_path):
    pal, b, g = cast(tmp_path)
    before = (pal.read_text(), b.read_text())
    msg = run_err("palette", b, "--remove", "w")
    assert "E_SELECT" in msg and "frames still draw with w" in msg and f"pxart palette {b} --remove w --to K" in msg
    assert (pal.read_text(), b.read_text()) == before


def test_remove_imported_key_the_suggested_command_is_safe(tmp_path, capsys):
    # The error's recipe (with a real key for K) leaves every file checking and rendering.
    pal, b, g = cast(tmp_path)
    girl_before = renders(g)
    msg = run_err("palette", b, "--remove", "w")
    cmd = shlex.split(msg.split("KEY: ")[1].replace(" K", " t"))
    assert cmd[:2] == ["pxart", "palette"]
    assert run(*cmd[1:]) == 0
    assert run("check", tmp_path) == 0 and renders(g) == girl_before


def test_remove_imported_key_unused_here_and_elsewhere(tmp_path, capsys):
    pal, b, g = cast(tmp_path)
    assert run("palette", b, "--remove", "x") == 0
    out = capsys.readouterr().out
    assert out.startswith("x stays in") and "girl.px uses it" in out and f"no change: {b}" in out


def test_remove_imported_key_nobody_uses(tmp_path, capsys):
    pal, b, g = cast(tmp_path, girl=None)
    write(tmp_path, "pal.px", CAST_PAL.replace("x #4e484a\n", "x #4e484a\nq #010203\n"))
    assert run("palette", b, "--remove", "q") == 0
    out = capsys.readouterr().out
    assert "removed q from" in out and f"no change: {b}; wrote {pal}" in out
    assert "q #" not in pal.read_text()


def test_remove_imported_key_drops_this_files_variant_line_when_it_goes(tmp_path, capsys):
    pal, b, g = cast(tmp_path, boy="pxart 1\n@palette pal.px\n\n@variant dusk\nw #111111\n\n@frame boy/0\nowt\nwwo\n")
    assert run("palette", b, "--remove", "w", "--to", "t") == 0
    out = capsys.readouterr().out
    assert "and boy.px's lines for it in @variant dusk" in out
    assert pxart.parse(b).variants == {"dusk": {}} and run("check", b) == 0


def test_remove_imported_key_keeps_this_files_variant_line_when_it_stays(tmp_path, capsys):
    pal, b, g = cast(tmp_path, boy="pxart 1\n@palette pal.px\n\n@variant dusk\nt #111111\n\n@frame boy/0\nowt\nwwo\n")
    assert run("palette", b, "--remove", "t", "--to", "o") == 0
    assert "t stays in" in capsys.readouterr().out
    assert pxart.parse(b).variants == {"dusk": {"t": pxart.hex2rgba("#111111")}}


def test_remove_imported_and_local_keys_in_one_call(tmp_path, capsys):
    pal, b, g = cast(tmp_path, boy="pxart 1\n@palette pal.px\nZ #abcdef\n\n@frame boy/0\nowZ\nwwo\n")
    assert run("palette", b, "--remove", "w,Z", "--to", "o") == 0
    out = capsys.readouterr().out
    assert out.startswith("repainted 3 px of w, 1 px of Z as o; removed Z; removed w (and its line in @variant dusk)")
    assert pxart.parse(b).frames[0].grid == ["ooo", "ooo"] and "Z" not in pxart.parse(b).palette


def test_remove_imported_key_through_a_chain_goes_from_the_file_that_defines_it(tmp_path, capsys):
    base = write(tmp_path, "base.px", "q #010203\nk #000000\n")
    mid = write(tmp_path, "mid.px", "@palette base.px\nm #445566\n")
    b = write(tmp_path, "s.px", "@palette mid.px\n\nqm\n")
    assert run("palette", b, "--remove", "q", "--to", "m") == 0
    out = capsys.readouterr().out
    assert f"removed q from {base}" in out and "q #" not in base.read_text() and "m #" in mid.read_text()
    assert run("check", tmp_path) == 0


def test_remove_imported_key_later_import_wins(tmp_path, capsys):
    a = write(tmp_path, "a.px", "q #010203\n")
    c = write(tmp_path, "c.px", "q #010203\n")
    b = write(tmp_path, "s.px", "@palette a.px\n@palette c.px\n\nq\n")
    assert run("palette", b, "--remove", "q", "--to", ".") != 0
    assert run("palette", b, "--remove", "q") != 0
    capsys.readouterr()
    write(tmp_path, "s.px", "@palette a.px\n@palette c.px\nz #000000\n\nz\n")
    assert run("palette", b, "--remove", "q") == 0
    assert f"removed q from {c}" in capsys.readouterr().out and "q #" in a.read_text() and "q #" not in c.read_text()


def test_remove_imported_key_renders_the_rest_the_same(tmp_path, capsys):
    pal, b, g = cast(tmp_path)
    before = renders(g)
    assert run("palette", b, "--remove", "w", "--to", "t") == 0
    assert renders(g) == before and run("check", tmp_path) == 0


def test_help_documents_remove_of_an_imported_key():
    text = " ".join(pxart.__doc__.split())
    assert "An imported key is repainted the same way in FILE, then removed from the palette file that defines it " \
        "only when no other .px under DIR uses it (draws with it, or lists it in a variant, with no key line of its " \
        "own); DIR is --in DIR, else the directory holding both FILE and the palette file" in text
    assert "'b stays in pal.px: cavegirl.px uses it'" in text
    assert "remove it there" not in text


# ---------------------------------------------------------------- scene: pixels past the edge are cropped with a note,
# and at the default size (96x64) a note says so and names the --size that holds every item

def big(tmp_path, name="big.px", w=192, h=144):
    return write(tmp_path, name, "k #000000\n\n" + ("k" * w + "\n") * h)


def test_scene_default_size_crop_says_so(tmp_path, capsys):
    b = big(tmp_path)
    out_png = tmp_path / "s.png"
    assert run("scene", "-o", out_png, f"{b}@0,0") == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [f"note: {192 * 144 - 96 * 64} px of item 1 ({b}) fall outside the 96x64 scene (size from the "
                   "default) and were cropped",
                   "note: 96x64 (six 16x16 tiles by four) is scene's size when nothing sizes it (no --size, no --map); "
                   "--size 192x144 holds every item",
                   f"wrote {out_png}"]
    assert Image.open(out_png).size == (96 * 4, 64 * 4)


def test_scene_default_size_suggestion_fits(tmp_path, capsys):
    b = big(tmp_path)
    s = write(tmp_path, "s.px", "k #000000\n\nkk\nkk\n")
    assert run("scene", "-o", tmp_path / "s.png", f"{b}@0,0", f"{s}@200,150") == 0
    out = capsys.readouterr().out
    assert "--size 202x152 holds every item" in out
    assert run("scene", "-o", tmp_path / "s.png", "--size", "202x152", f"{b}@0,0", f"{s}@200,150") == 0
    assert "note" not in capsys.readouterr().out


def test_scene_default_size_no_note_when_everything_fits(tmp_path, capsys):
    s = write(tmp_path, "s.px", "k #000000\n\nkk\nkk\n")
    assert run("scene", "-o", tmp_path / "s.png", f"{s}@94,62") == 0
    assert capsys.readouterr().out == f"wrote {tmp_path / 's.png'}\n"


def test_scene_transparent_pixels_past_the_edge_are_no_crop(tmp_path, capsys):
    s = write(tmp_path, "s.px", "k #000000\n\nk.\n..\n")
    assert run("scene", "-o", tmp_path / "s.png", f"{s}@95,63") == 0
    assert capsys.readouterr().out == f"wrote {tmp_path / 's.png'}\n"


def test_scene_counts_only_the_pixels_outside(tmp_path, capsys):
    s = write(tmp_path, "s.px", "k #000000\n\nkkkk\nkkkk\n")
    assert run("scene", "-o", tmp_path / "s.png", f"{s}@94,63") == 0
    out = capsys.readouterr().out
    assert f"note: 6 px of item 1 ({s}) fall outside the 96x64 scene (size from the default) and were cropped" in out


@pytest.mark.parametrize("at, n", [("-1,0", 2), ("0,-1", 4), ("-4,0", 8), ("-10,-10", 8), ("96,0", 8), ("0,64", 8),
                                   ("-2,-1", 6)])
def test_scene_negative_and_far_positions_count(tmp_path, capsys, at, n):
    s = write(tmp_path, "s.px", "k #000000\n\nkkkk\nkkkk\n")
    assert run("scene", "-o", tmp_path / "s.png", f"{s}@{at}") == 0
    assert f"note: {n} px of item 1 ({s}) fall outside" in capsys.readouterr().out


def test_scene_with_size_crop_note_names_size(tmp_path, capsys):
    s = write(tmp_path, "s.px", "k #000000\n\nkkkk\nkkkk\n")
    assert run("scene", "-o", tmp_path / "s.png", "--size", "3x3", f"{s}@0,0") == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == f"note: 2 px of item 1 ({s}) fall outside the 3x3 scene (size from --size) and were cropped"
    assert "holds every item" not in "\n".join(out)


def test_scene_same_file_twice_gets_a_note_each(tmp_path, capsys):
    s = write(tmp_path, "s.px", "k #000000\n\nkk\n")
    assert run("scene", "-o", tmp_path / "s.png", f"{s}@95,0", f"{s}@-1,5") == 0
    out = capsys.readouterr().out
    assert f"1 px of item 1 ({s})" in out and f"1 px of item 2 ({s})" in out


def test_scene_map_overhang_gets_one_note(tmp_path, capsys):
    write(tmp_path, "t.px", "k #000000\n\n" + ("k" * 4 + "\n") * 4)
    write(tmp_path, "tall.px", "k #000000\n\n" + ("k" * 4 + "\n") * 8)
    m = write(tmp_path, "m.map", "t t.px\nL tall.px+b\n\ntt\nLL\n")
    assert run("scene", "--map", m, "--tile", "4x4", "-o", tmp_path / "s.png") == 0
    out = capsys.readouterr().out
    assert out.count("note:") == 0  # the tall props rise into row 0, still inside
    m2 = write(tmp_path, "m2.map", "L tall.px+b\n\nLL\n")
    assert run("scene", "--map", m2, "--tile", "4x4", "-o", tmp_path / "s.png") == 0
    out = capsys.readouterr().out
    assert "note: 32 px of the map fall outside the 8x4 scene (size from --map) and were cropped" in out
    assert "holds every item" not in out


def test_scene_png_item_crop(tmp_path, capsys):
    png = tmp_path / "p.png"
    Image.new("RGBA", (100, 10), (255, 0, 0, 255)).save(png)
    assert run("scene", "-o", tmp_path / "s.png", f"{png}@0,0") == 0
    out = capsys.readouterr().out
    assert f"note: 40 px of item 1 ({png}) fall outside the 96x64 scene" in out and "--size 100x10 holds" in out


def test_scene_crop_render_unchanged(tmp_path, capsys):
    # The note is all that's new: the picture is what it was.
    b = big(tmp_path)
    assert run("scene", "-o", tmp_path / "s.png", "--scale", "1", f"{b}@-5,-5") == 0
    img = Image.open(tmp_path / "s.png")
    assert img.size == (96, 64) and img.getpixel((0, 0)) == (0, 0, 0, 255)


def test_help_documents_scene_default_size():
    text = " ".join(pxart.__doc__.split())
    assert "Size: --size, else the map's, else 96x64 (six 16x16 tiles by four). Pixels past the edge are cropped, " \
        "with a note per item (and one for the map) saying how many; at the default size a note also names the " \
        "--size that holds every item." in text


def test_readme_documents_scene_default_size():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "on a 96x64 scene unless `--size` or `--map` says otherwise, pixels past its edge cropped with a note" in readme


# ---------------------------------------------------------------- compose --rekey: a color two source files share
# (the same in every variant) keeps the one key it was given; FILE.px:KEY=OUTKEY scopes an entry to one file

REUSE_GROUND = "pxart 1\no #2b1d32\nT #74c8d4\nk #9e5a52\n\n@variant dusk\no #1a1020\nT #3a6470\nk #6a3a36\n\no\nT\nk\n"
REUSE_PAL = "o #141b1b\nT #345a52\nk #965340\n\n@variant dusk\no #10121a\nT #3a4c49\nk #83473b\n"
REUSE_BOY = "pxart 1\n@palette pal.px\n\n@frame boy/0\noTk\n"
REUSE_GIRL = "pxart 1\n@palette pal.px\n\n@frame girl/0\nkTo\n"


def reuse_files(tmp_path, girl=REUSE_GIRL, pal2=None):
    g = write(tmp_path, "ground.px", REUSE_GROUND)
    write(tmp_path, "pal.px", REUSE_PAL)
    b = write(tmp_path, "boy.px", REUSE_BOY)
    if pal2 is not None:
        write(tmp_path, "pal2.px", pal2)
        girl = girl.replace("pal.px", "pal2.px")
    c = write(tmp_path, "girl.px", girl)
    return g, b, c


def looks_all(path, fid=None):
    doc = pxart.parse(path)
    f = doc.get(fid) if fid else doc.frames[0]
    return {n: list(pxart.pixels(doc.image(f, n))) for n in [None] + sorted(set(doc.variants) | set(doc.shared_variants))}


def test_compose_rekey_reuses_a_key_given_earlier_in_the_compose(tmp_path, capsys):
    g, b, c = reuse_files(tmp_path)
    out = tmp_path / "glade.px"
    assert run("compose", "-o", out, "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1", f"{c}:girl/0@0,2", "--rekey") == 0
    got = capsys.readouterr().out
    assert f"note: --rekey gives {b}'s keys free ones in {out}: 'T>a' 'k>b' 'o>c' ({b} is unchanged)" in got
    assert (f"note: --rekey gives {c}'s keys free ones in {out}: 'T>a' 'k>b' 'o>c' ({c} is unchanged); T k o share "
            f"the keys {b} got for the same colors (in every variant too)") in got
    doc = pxart.parse(out)
    assert doc.frames[0].grid == ["o..", "cab", "bac"]
    assert set(doc.palette) == {"o", "T", "k", "a", "b", "c"}


def test_compose_rekey_reuse_renders_like_the_sources(tmp_path, capsys):
    g, b, c = reuse_files(tmp_path)
    out = tmp_path / "glade.px"
    assert run("compose", "-o", out, "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1", f"{c}:girl/0@0,2", "--rekey") == 0
    doc = pxart.parse(out)
    for n in (None, "dusk"):
        img = doc.image(doc.frames[0], n)
        boy = pxart.parse(b).image(pxart.parse(b).get("boy/0"), n)
        girl = pxart.parse(c).image(pxart.parse(c).get("girl/0"), n)
        assert [img.getpixel((x, 1)) for x in range(3)] == [boy.getpixel((x, 0)) for x in range(3)]
        assert [img.getpixel((x, 2)) for x in range(3)] == [girl.getpixel((x, 0)) for x in range(3)]


def test_compose_rekey_reuse_needs_the_same_variant_colors(tmp_path, capsys):
    # girl's palette file has the same base colors but its own dusk for T: T can't share boy's key.
    pal2 = REUSE_PAL.replace("T #3a4c49", "T #000000")
    g, b, c = reuse_files(tmp_path, pal2=pal2)
    out = tmp_path / "glade.px"
    assert run("compose", "-o", out, "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1", f"{c}:girl/0@0,2", "--rekey") == 0
    got = capsys.readouterr().out
    assert f"note: --rekey gives {c}'s keys free ones in {out}: 'T>d' 'k>b' 'o>c' ({c} is unchanged); k o share" in got
    doc = pxart.parse(out)
    assert doc.resolved("dusk")["d"] == (0, 0, 0, 255) and doc.resolved("dusk")["a"] == pxart.hex2rgba("#3a4c49")


def test_compose_rekey_reuse_skips_a_key_the_file_has(tmp_path, capsys):
    # girl.px has a key 'a' of its own: boy's T went to a, so girl's T needs another key.
    girl = "pxart 1\n@palette pal.px\na #fefefe\n\n@frame girl/0\nkTa\n"
    g, b, c = reuse_files(tmp_path, girl=girl)
    out = tmp_path / "glade.px"
    assert run("compose", "-o", out, "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1", f"{c}:girl/0@0,2", "--rekey") == 0
    doc = pxart.parse(out)
    row = doc.frames[0].grid[2]
    assert row[1] != "a" and doc.resolved()[row[1]] == pxart.hex2rgba("#345a52")
    assert doc.resolved()[row[2]] == pxart.hex2rgba("#fefefe")


def test_compose_conflict_suggestions_reuse_too(tmp_path):
    # Without --rekey the E_KEY_CONFLICT lines offer the same moves, the shared keys included.
    g, b, c = reuse_files(tmp_path)
    msg = run_err("compose", "-o", tmp_path / "glade.px", "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1",
                  f"{c}:girl/0@0,2")
    lines = msg.splitlines()
    assert "('T>a' 'k>b' 'o>c')" in lines[0] and "('T>a' 'k>b' 'o>c')" in lines[1]


def test_compose_rekey_reuse_into_an_existing_out(tmp_path, capsys):
    g, b, c = reuse_files(tmp_path)
    out = write(tmp_path, "glade.px", REUSE_GROUND.replace("o\nT\nk\n", "@frame bg\no\n"))
    assert run("compose", "-o", f"{out}:scene", "--size", "3x2", f"{b}:boy/0@0,0", f"{c}:girl/0@0,1", "--rekey") == 0
    doc = pxart.parse(out)
    assert doc.get("scene").grid == ["cab", "bac"]
    assert set(doc.palette) == {"o", "T", "k", "a", "b", "c"}
    assert looks_all(out, "scene")["dusk"][:3] == looks_all(b)["dusk"]


def test_compose_rekey_reuse_across_the_needed_keys(tmp_path, capsys):
    # boy.px's walk frames draw with p, which its layer here doesn't: a new OUT keeps it under a free key; girl's p,
    # the same color, shares it.
    pal = REUSE_PAL.replace("k #965340\n", "k #965340\np #d3a2c0\n")
    g = write(tmp_path, "ground.px", REUSE_GROUND.replace("k #9e5a52\n", "k #9e5a52\np #5c9488\n") + "p\n")
    write(tmp_path, "pal.px", pal)
    b = write(tmp_path, "boy.px", REUSE_BOY + "@frame boy/1\npTk\n")
    c = write(tmp_path, "girl.px", REUSE_GIRL + "@frame girl/1\npTo\n")
    out = tmp_path / "glade.px"
    assert run("compose", "-o", out, "--size", "3x4", f"{g}@0,0", f"{b}:boy/0@0,2", f"{c}:girl/0@0,3", "--rekey") == 0
    got = capsys.readouterr().out
    moved = [l for l in got.splitlines() if l.startswith("note: --rekey gives")]
    boy_p = re.search(r"'p>(.)'", moved[0]).group(1)
    assert f"'p>{boy_p}'" in moved[1] and "T k o p share the keys" in moved[1]


def test_compose_rekey_three_files_share_one_key(tmp_path, capsys):
    g, b, c = reuse_files(tmp_path)
    d = write(tmp_path, "d.px", REUSE_GIRL.replace("girl", "dog"))
    out = tmp_path / "glade.px"
    assert run("compose", "-o", out, "--size", "3x4", f"{g}@0,0", f"{b}:boy/0@0,1", f"{c}:girl/0@0,2",
               f"{d}:dog/0@0,3", "--rekey") == 0
    doc = pxart.parse(out)
    assert doc.frames[0].grid[2] == doc.frames[0].grid[3] == "bac"
    assert f"T k o share the keys {b} got" in capsys.readouterr().out


def test_compose_rekey_free_keys_run_past_letters_only_when_taken(tmp_path, capsys):
    # Every letter and digit taken by the layers' files: the next free keys are % + - / : ^ _, never ! or $ first.
    keys = pxart.string.ascii_letters + pxart.string.digits
    big = write(tmp_path, "big.px", "".join(f"{k} #{i:06x}\n" for i, k in enumerate(keys, 1)) + "\n" + keys + "\n")
    s = write(tmp_path, "s.px", "a #fefefe\nb #fdfdfd\n\nab\n")
    t = write(tmp_path, "t.px", "a #fefefe\nb #fdfdfd\n\nba\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{big}@0,0", f"{s}@0,0", f"{t}@2,0", "--rekey") == 0
    got = capsys.readouterr().out
    assert f"'a>%' 'b>+'" in got and "!" not in got and "$" not in got
    assert pxart.parse(out).frames[0].grid[0][:4] == "%++%"


def test_rekey_spec_scoped_entries():
    assert pxart.rekey_spec("girl.px:T=V") == (set(), {}, {"girl.px": (set(), {"T": "V"})})
    assert pxart.rekey_spec("o,girl.px:T=V,girl.px:k") == ({"o"}, {}, {"girl.px": ({"k"}, {"T": "V"})})
    assert pxart.rekey_spec("cast/girl.px:T=V,boy.px:T=W") == (set(), {}, {"cast/girl.px": (set(), {"T": "V"}),
                                                                         "boy.px": (set(), {"T": "W"})})
    assert pxart.rekey_spec("a.px::=V") == (set(), {}, {"a.px": (set(), {":": "V"})})
    assert pxart.rekey_spec("a.px:%") == (set(), {}, {"a.px": ({"%"}, {})})


@pytest.mark.parametrize("bad, bit", [("girl.px:T=V,girl.px:T", "names girl.px:'T' twice"),
                                      ("girl.px:TT", "want keys"), ("girl.px:T=", "want keys"),
                                      ("girl.px:#", "want keys"), ("girl.png:T", "want keys")])
def test_rekey_spec_scoped_bad(bad, bit):
    with pytest.raises(pxart.PxError) as e:
        pxart.rekey_spec(bad)
    assert codes(e) == ["E_BAD_ARG"] and bit in str(e.value)


def test_rekey_args_scoped_entry_is_the_value():
    assert pxart.rekey_args(["compose", "-o", "o.px", "--rekey", "girl.px:T=V", "a.px@0,0"]) == \
        ["compose", "-o", "o.px", "--rekey", "girl.px:T=V", "a.px@0,0"]
    assert pxart.rekey_args(["compose", "-o", "o.px", "--rekey", "o,cast/girl.px:T=V", "a.px@0,0"])[3:5] == \
        ["--rekey", "o,cast/girl.px:T=V"]
    assert pxart.rekey_args(["compose", "-o", "o.px", "--rekey", "girl.px:idle@0,0"])[3] == "--rekey="


def test_compose_rekey_scoped_puts_one_files_key_on_a_named_key(tmp_path, capsys):
    g, b, c = reuse_files(tmp_path)
    out = tmp_path / "glade.px"
    assert run("compose", "-o", out, "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1", f"{c}:girl/0@0,2",
               "--rekey", f"T,k,o,{c}:T=V") == 0
    got = capsys.readouterr().out
    assert f"note: --rekey gives {c}'s keys other ones in {out}: 'T>V' " in got and "T as --rekey named" in got
    doc = pxart.parse(out)
    # boy's T, the same color in every variant, then shares V: OUT has it by then
    assert doc.frames[0].grid[2][1] == doc.frames[0].grid[1][1] == "V"
    assert doc.resolved()["V"] == pxart.hex2rgba("#345a52")


def test_compose_rekey_scoped_by_name(tmp_path, capsys):
    g, b, c = reuse_files(tmp_path)
    out = tmp_path / "glade.px"
    assert run("compose", "-o", out, "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1", f"{c}:girl/0@0,2",
               "--rekey", "T,k,o,girl.px:T=V") == 0
    assert pxart.parse(out).frames[0].grid[2][1] == "V"


def test_compose_rekey_scoped_leaves_the_other_files_key(tmp_path):
    # Only girl.px's T is named: boy.px's T still clashes with the ground's, so it's E_KEY_CONFLICT for boy alone.
    g, b, c = reuse_files(tmp_path)
    msg = run_err("compose", "-o", tmp_path / "glade.px", "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1",
                  f"{c}:girl/0@0,2", "--rekey", "k,o,girl.px:T=V")
    assert "E_KEY_CONFLICT" in msg and "'T' #345a52" in msg and "boy.px" in msg and "girl.px" not in msg.split("(")[0]
    assert len(msg.splitlines()) == 1


def test_compose_rekey_scoped_wins_over_the_list(tmp_path, capsys):
    g, b, c = reuse_files(tmp_path)
    out = tmp_path / "glade.px"
    assert run("compose", "-o", out, "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1", f"{c}:girl/0@0,2",
               "--rekey", "T=Q,k,o,girl.px:T=V") == 0
    grid = pxart.parse(out).frames[0].grid
    assert grid[1][1] == "Q" and grid[2][1] == "V"


def test_compose_rekey_scoped_unknown_file(tmp_path):
    g, b, c = reuse_files(tmp_path)
    msg = run_err("compose", "-o", tmp_path / "glade.px", "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1",
                  f"{c}:girl/0@0,2", "--rekey", "T,k,o,dog.px:T=V")
    assert "E_SELECT" in msg and "dog.px is no source file here (they are: " in msg


def test_compose_rekey_scoped_ambiguous_name(tmp_path):
    g, b, c = reuse_files(tmp_path)
    (tmp_path / "x").mkdir()
    write(tmp_path / "x", "pal.px", REUSE_PAL)
    c2 = write(tmp_path / "x", "girl.px", REUSE_GIRL)
    msg = run_err("compose", "-o", tmp_path / "glade.px", "--size", "3x4", f"{g}@0,0", f"{b}:boy/0@0,1",
                  f"{c}:girl/0@0,2", f"{c2}:girl/0@0,3", "--rekey", "T,k,o,girl.px:T=V")
    assert "E_SELECT" in msg and "girl.px is the name of several source files; give its path" in msg


def test_compose_rekey_scoped_key_the_file_doesnt_draw(tmp_path):
    g, b, c = reuse_files(tmp_path)
    msg = run_err("compose", "-o", tmp_path / "glade.px", "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1",
                  f"{c}:girl/0@0,2", "--rekey", f"T,k,o,{b}:q=V")
    assert "E_SELECT" in msg and "layers don't draw with q" in msg


def test_compose_rekey_scoped_to_a_key_of_another_color(tmp_path):
    g, b, c = reuse_files(tmp_path)
    msg = run_err("compose", "-o", tmp_path / "glade.px", "--size", "3x3", f"{g}@0,0", f"{b}:boy/0@0,1",
                  f"{c}:girl/0@0,2", "--rekey", f"T,k,o,{c}:T=o")
    assert "E_KEY_CONFLICT" in msg and "--rekey T=o" in msg


def test_paste_rekey_scoped_to_its_source(tmp_path, capsys):
    f, out = field_scene(tmp_path)
    assert run("paste", f"{f}:grass_a", "--into", f"{out}:x", "--at", "1,0", "--rekey", f"{f.name}:s,{f.name}:t") == 0
    assert "'s>a' 't>b'" in capsys.readouterr().out and pxart.parse(out).get("x").grid == ["sabv"]


def test_paste_rekey_scoped_to_another_file(tmp_path):
    f, out = field_scene(tmp_path)
    msg = run_err("paste", f"{f}:grass_a", "--into", f"{out}:x", "--at", "1,0", "--rekey", "other.px:s")
    assert "E_SELECT" in msg and "other.px is no source file here" in msg


def test_frames_copy_rekey_scoped(tmp_path, capsys):
    s = write(tmp_path, "s.px", CSRC)
    d = write(tmp_path, "d.px", CDST.replace("k #000000\n", "k #000000\nw #eeeeee\n"))
    assert run("frames", f"{s}:walk", "--copy-to", d, "--rekey", "s.px:w=Q,k") == 0
    got = capsys.readouterr().out
    assert "'w>Q'" in got and pxart.parse(d).palette["Q"] == pxart.hex2rgba("#ffffff")


def test_help_documents_rekey_reuse_and_scope():
    text = " ".join(pxart.__doc__.split())
    assert "then the key an earlier file of this compose was given for a color that looks the same in every variant " \
        "(two packs' one outline share one key, and the note says so)" in text
    assert "A key any layer's file has isn't free, used here or not." in text
    assert "An entry FILE.px:KEY[=OUTKEY] is for that source file alone: --rekey o,girl.px:T=V puts girl.px's T on " \
        "V, gives every file's o a free key, and leaves the other files' T alone" in text


def test_readme_documents_rekey_reuse_and_scope():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`--rekey girl.px:T=V` is for one source file's T only; a color two files share, alike in every variant, " \
        "keeps the one key it got first" in readme


# ---------------------------------------------------------------- compose into a plain OUT that exists: a note says it
# keeps its palette; --replace starts it fresh

def stale_setup(tmp_path):
    a = write(tmp_path, "a.px", "pxart 1\nk #000000\nw #ffffff\n\n@variant dusk\nw #888888\n\nkw\n")
    b = write(tmp_path, "b.px", "pxart 1\nk #000000\nr #ff0000\n\nrk\n")
    out = tmp_path / "o.px"
    return a, b, out


def test_compose_plain_existing_out_notes_its_palette(tmp_path, capsys):
    a, b, out = stale_setup(tmp_path)
    assert run("compose", "-o", out, f"{a}@0,0") == 0
    capsys.readouterr()
    assert run("compose", "-o", out, f"{b}@0,0") == 0
    got = capsys.readouterr().out.splitlines()
    assert got[0] == f"note: {out} exists: keeping its palette (2 keys, @variant dusk); --replace starts it fresh"
    assert set(pxart.parse(out).palette) == {"k", "w", "r"}  # w: stale, from the first run


def test_compose_replace_starts_fresh(tmp_path, capsys):
    a, b, out = stale_setup(tmp_path)
    assert run("compose", "-o", out, f"{a}@0,0") == 0
    capsys.readouterr()
    assert run("compose", "-o", out, f"{b}@0,0", "--replace") == 0
    got = capsys.readouterr().out
    assert "keeping its palette" not in got and got.endswith(f"wrote {out}\n")
    doc = pxart.parse(out)
    assert set(doc.palette) == {"k", "r"} and doc.variants == {} and doc.frames[0].grid == ["rk"]


def test_compose_replace_is_the_same_as_a_new_out(tmp_path, capsys):
    a, b, out = stale_setup(tmp_path)
    new = tmp_path / "new.px"
    assert run("compose", "-o", out, f"{a}@0,0") == 0
    assert run("compose", "-o", out, f"{b}@0,0", f"{a}@0,1", "--size", "2x2", "--replace") == 0
    assert run("compose", "-o", new, f"{b}@0,0", f"{a}@0,1", "--size", "2x2") == 0
    assert out.read_text() == new.read_text()


def test_compose_replace_of_a_missing_out_is_a_plain_compose(tmp_path, capsys):
    a, b, out = stale_setup(tmp_path)
    assert run("compose", "-o", out, f"{a}@0,0", "--replace") == 0
    assert capsys.readouterr().out == f"wrote {out}\n"


def test_compose_replace_drops_frames_and_everything(tmp_path, capsys):
    a, b, out = stale_setup(tmp_path)
    write(tmp_path, "o.px", "pxart 1\n# old header\nq #123456\n@anim x ms=1\n@frame x/0\nq\n@frame x/1\nq\n")
    msg = run_err("compose", "-o", out, f"{b}@0,0")
    assert "E_SELECT" in msg and "has named frames" in msg
    assert run("compose", "-o", out, f"{b}@0,0", "--replace") == 0
    assert "old header" not in out.read_text() and pxart.parse(out).implicit


def test_compose_replace_with_frame_is_bad_arg(tmp_path):
    a, b, out = stale_setup(tmp_path)
    assert run("compose", "-o", out, f"{a}@0,0") == 0
    before = out.read_text()
    msg = run_err("compose", "-o", f"{out}:x", f"{b}@0,0", "--replace")
    assert "E_BAD_ARG" in msg and f"with -o {out}:x that would drop its other frames too" in msg
    assert out.read_text() == before


def test_compose_replace_with_under_is_bad_arg(tmp_path):
    a, b, out = stale_setup(tmp_path)
    assert run("compose", "-o", out, f"{a}@0,0") == 0
    msg = run_err("compose", "-o", out, f"{b}@0,0", "--replace", "--under")
    assert "E_BAD_ARG" in msg and "--under draws behind the frame it has: give one" in msg


def test_compose_replace_with_rekey(tmp_path, capsys):
    # The stale white would clash with a new file's w; --replace --rekey starts over, so nothing needs a new key.
    a, b, out = stale_setup(tmp_path)
    assert run("compose", "-o", out, f"{a}@0,0") == 0
    c = write(tmp_path, "c.px", "pxart 1\nw #00ff00\n\nw\n")
    msg = run_err("compose", "-o", out, f"{c}@0,0")
    assert "E_KEY_CONFLICT" in msg and f"({out} exists, and keeps its palette: --replace starts it fresh, as if new)" \
        in msg
    capsys.readouterr()
    assert run("compose", "-o", out, f"{c}@0,0", "--replace", "--rekey") == 0
    got = capsys.readouterr().out
    assert "--rekey gives" not in got and pxart.parse(out).palette == {"w": pxart.hex2rgba("#00ff00")}


def test_compose_frame_of_existing_out_has_no_plain_note(tmp_path, capsys):
    a, b, out = stale_setup(tmp_path)
    write(tmp_path, "o.px", "pxart 1\nk #000000\n@frame x\nk\n")
    assert run("compose", "-o", f"{out}:y", f"{b}@0,0") == 0
    assert "keeping its palette" not in capsys.readouterr().out


def test_compose_under_has_no_plain_note(tmp_path, capsys):
    a, b, out = stale_setup(tmp_path)
    assert run("compose", "-o", out, f"{a}@0,0") == 0
    capsys.readouterr()
    assert run("compose", "-o", out, f"{b}@0,0", "--under") == 0
    assert "keeping its palette" not in capsys.readouterr().out


def test_crop_into_plain_existing_out_has_no_compose_note(tmp_path, capsys):
    a, b, out = stale_setup(tmp_path)
    assert run("compose", "-o", out, f"{a}@0,0") == 0
    capsys.readouterr()
    assert run("crop", a, "0,0,1,1", "-o", out) == 0
    assert "keeping its palette" not in capsys.readouterr().out


def test_compose_plain_note_names_imports(tmp_path, capsys):
    write(tmp_path, "pal.px", "k #000000\n@variant night\nk #000011\n")
    s = write(tmp_path, "s.px", "@palette pal.px\n\nk\n")
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{s}@0,0") == 0
    capsys.readouterr()
    assert run("compose", "-o", out, f"{s}@0,0") == 0
    assert f"note: {out} exists: keeping its palette (0 keys, @palette pal.px, @variant night); --replace starts it " \
        "fresh" in capsys.readouterr().out


def test_help_documents_compose_replace():
    text = " ".join(pxart.__doc__.split())
    assert "[--variant-map NAME=V1,V2] [--replace] LAYER@x,y ..." in text
    assert "A plain OUT that exists (no :frame) keeps its palette too, keys from an earlier run included, and a note " \
        "says so" in text
    assert "--replace starts it as if new: the layers' palettes, nothing of the old file (not with OUT:frame, whose " \
        "other frames it would drop, or with --under)." in text


def test_readme_documents_compose_replace():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "a plain OUT that exists keeps its palette, with a note, and `--replace` starts it as if new" in readme


# ---------------------------------------------------------------- palette FILE --import P.px: add '@palette P.px',
# drop FILE's key lines P has in the same colors, render the same

IMP_PAL = "# cast palette\no #141b1b\n# teal\nt #548789\nk #965340\n\n@variant dusk\no #10121a\nt #526e72\nk #83473b\n"
IMP_BOY = "pxart 1\n# boy\no #141b1b\nt #548789\nz #abcdef\n\n@variant dusk\no #10121a\nt #000000\n\n@frame b/0\notz\n"


def imp(tmp_path, boy=IMP_BOY, pal=IMP_PAL):
    return write(tmp_path, "pal.px", pal), write(tmp_path, "boy.px", boy)


def test_import_adds_the_line_and_drops_same_keys(tmp_path, capsys):
    pal, b = imp(tmp_path)
    before = renders(b)
    assert run("palette", b, "--import", pal) == 0
    out = capsys.readouterr().out
    assert out == (f"imported {pal} (@palette pal.px); dropped o t (their key lines and 1 line in @variant dusk: the "
                   f"same colors in {pal}); wrote {b}\n")
    doc = pxart.parse(b)
    assert doc.palette_refs == ["pal.px"] and doc.palette == {"z": pxart.hex2rgba("#abcdef")}
    assert doc.variants == {"dusk": {"t": (0, 0, 0, 255)}}  # boy's own dusk t stays: pal's differs
    assert renders(b) == before


def test_import_text(tmp_path, capsys):
    pal, b = imp(tmp_path)
    assert run("palette", b, "--import", pal) == 0
    # '# boy' sat above o's line, so it goes with it, as a removed key's comment does
    assert b.read_text() == "pxart 1\n@palette pal.px\nz #abcdef\n\n@variant dusk\nt #000000\n\n@frame b/0\notz\n"


def test_import_from_another_directory_is_repointed(tmp_path, capsys):
    (tmp_path / "pal").mkdir()
    (tmp_path / "sprites").mkdir()
    pal = write(tmp_path / "pal", "cast.px", IMP_PAL)
    b = write(tmp_path / "sprites", "boy.px", IMP_BOY)
    before = renders(b)
    assert run("palette", b, "--import", pal) == 0
    assert pxart.parse(b).palette_refs == ["../pal/cast.px"] and renders(b) == before


def test_import_keeps_a_variant_the_file_had(tmp_path, capsys):
    # boy's dusk lists nothing for k; pal's dusk recolors k: boy's dusk gets k's color on a line of its own.
    pal, b = imp(tmp_path, boy="pxart 1\nk #965340\n\n@variant dusk\nq #111111\nq #111111\n\nk\n".replace(
        "@variant dusk\nq #111111\nq #111111\n", "q #111111\n@variant dusk\nq #222222\n"))
    before = renders(b)
    assert run("palette", b, "--import", pal) == 0
    out = capsys.readouterr().out
    assert f"@variant dusk lists k in boy.px's colors ({pal}'s dusk recolors it)" in out
    assert pxart.parse(b).variants["dusk"]["k"] == pxart.hex2rgba("#965340")
    assert renders(b) == before


def test_import_brings_a_new_variant(tmp_path, capsys):
    pal, b = imp(tmp_path, boy="pxart 1\nk #965340\n\nk\n")
    assert run("palette", b, "--import", pal) == 0
    out = capsys.readouterr().out
    assert f"boy.px now has {pal}'s @variant dusk" in out
    doc = pxart.parse(b)
    assert doc.palette == {} and doc.resolved("dusk")["k"] == pxart.hex2rgba("#83473b")


def test_import_conflict(tmp_path):
    pal, b = imp(tmp_path, boy=IMP_BOY.replace("t #548789", "t #ff0000"))
    before = b.read_text()
    msg = run_err("palette", b, "--import", pal)
    assert "E_KEY_CONFLICT" in msg and f"1 key of {b} is another color in {pal}: 't' #ff0000 ({pal}: #548789)" in msg
    assert f"give {b}'s one free keys first (no pixel changes color): pxart recolor {b} 't>a', then palette {b} " \
        f"--import {pal}" in msg
    assert b.read_text() == before


def test_import_conflict_recipe_works(tmp_path, capsys):
    pal, b = imp(tmp_path, boy=IMP_BOY.replace("t #548789", "t #ff0000"))
    before = renders(b)
    msg = run_err("palette", b, "--import", pal)
    recolor = shlex.split(msg.split("first (no pixel changes color): ")[1].split(", then ")[0])
    assert run(*recolor[1:]) == 0
    assert run("palette", b, "--import", pal) == 0
    assert renders(b) == before and run("check", b) == 0


def test_import_conflict_with_an_earlier_import(tmp_path):
    write(tmp_path, "old.px", "t #ff0000\n")
    pal, b = imp(tmp_path, boy="pxart 1\n@palette old.px\n\nt\n")
    msg = run_err("palette", b, "--import", pal)
    assert "E_KEY_CONFLICT" in msg and "'t' #ff0000" in msg


def test_import_several_conflicts_get_distinct_keys(tmp_path):
    pal, b = imp(tmp_path, boy="pxart 1\no #ff0000\nt #00ff00\na #0000ff\n\nota\n")
    msg = run_err("palette", b, "--import", pal)
    assert "2 keys of" in msg and "'o>b' 't>c'" in msg


def test_import_already(tmp_path, capsys):
    pal, b = imp(tmp_path)
    assert run("palette", b, "--import", pal) == 0
    text = b.read_text()
    capsys.readouterr()
    assert run("palette", b, "--import", pal) == 0
    assert capsys.readouterr().out == f"{b} already imports {pal}; no change: {b}\n" and b.read_text() == text


def test_import_already_through_a_chain(tmp_path, capsys):
    pal, b = imp(tmp_path, boy="pxart 1\n@palette mid.px\n\nk\n")
    write(tmp_path, "mid.px", "@palette pal.px\nm #000000\n")
    assert run("palette", b, "--import", pal) == 0
    assert "already imports" in capsys.readouterr().out


def test_import_itself(tmp_path):
    pal, b = imp(tmp_path)
    assert "can't import itself" in run_err("palette", pal, "--import", pal)


def test_import_a_cycle(tmp_path):
    a = write(tmp_path, "a.px", "q #000000\n")
    c = write(tmp_path, "c.px", "@palette a.px\nr #000001\n")
    msg = run_err("palette", a, "--import", c)
    assert "E_BAD_ARG" in msg and f"can't import itself ({c} imports it)" in msg


def test_import_missing_file(tmp_path):
    pal, b = imp(tmp_path)
    msg = run_err("palette", b, "--import", tmp_path / "nope.px")
    assert "E_PALETTE_FILE" in msg or "E_FILE" in msg


def test_import_a_file_with_frames_is_no_palette(tmp_path):
    pal, b = imp(tmp_path)
    other = write(tmp_path, "other.px", "k #000000\n\nk\n")
    msg = run_err("palette", b, "--import", other)
    assert "E_PALETTE_FILE" in msg or "can't contain grid rows" in msg


@pytest.mark.parametrize("more", [["--add", "q=#010101"], ["--hoist", "z"], ["--remove", "z"],
                                  ["--comment-header", ""], ["--export", "x.gpl"]])
def test_import_alone(tmp_path, more):
    pal, b = imp(tmp_path)
    msg = run_err("palette", b, "--import", pal, *more)
    assert "E_BAD_ARG" in msg and "--import adds a @palette line to FILE: give it alone" in msg


def test_import_into_a_palette_file(tmp_path, capsys):
    pal, b = imp(tmp_path)
    mine = write(tmp_path, "mine.px", "# mine\nk #965340\nq #123123\n")
    assert run("palette", mine, "--import", pal) == 0
    doc = pxart.parse(mine, palette_only=True)
    assert doc.palette == {"q": pxart.hex2rgba("#123123")} and doc.palette_refs == ["pal.px"]


def test_import_keeps_the_dot_line(tmp_path, capsys):
    pal, b = imp(tmp_path, boy="o #141b1b\n. transparent\nz #abcdef\n\noz.\n")
    assert run("palette", b, "--import", pal) == 0
    assert b.read_text() == "@palette pal.px\n. transparent\nz #abcdef\n\noz.\n"


def test_import_drops_the_comments_of_dropped_keys(tmp_path, capsys):
    pal, b = imp(tmp_path, boy="pxart 1\n# the outline\no #141b1b\n# mine\nz #abcdef\n\noz\n")
    assert run("palette", b, "--import", pal) == 0
    text = b.read_text()
    assert "# the outline" not in text and "# mine\nz #abcdef" in text


def test_import_keeps_a_commented_empty_variant(tmp_path, capsys):
    pal, b = imp(tmp_path, boy="pxart 1\no #141b1b\n\n# my dusk\n@variant dusk\no #10121a\n\no\n")
    assert run("palette", b, "--import", pal) == 0
    doc = pxart.parse(b)
    assert "# my dusk\n@variant dusk" in b.read_text() and doc.variants == {"dusk": {}}


def test_import_drops_an_uncommented_empty_variant(tmp_path, capsys):
    pal, b = imp(tmp_path, boy="pxart 1\no #141b1b\n\n@variant dusk\no #10121a\n\no\n")
    assert run("palette", b, "--import", pal) == 0
    assert "@variant" not in b.read_text() and pxart.parse(b).resolved("dusk")["o"] == pxart.hex2rgba("#10121a")


def test_import_keeps_a_variant_only_the_file_has(tmp_path, capsys):
    pal, b = imp(tmp_path, boy="pxart 1\no #141b1b\n\n@variant night\no #000000\n\no\n")
    before = renders(b)
    assert run("palette", b, "--import", pal) == 0
    doc = pxart.parse(b)
    assert doc.variants == {"night": {"o": (0, 0, 0, 255)}}
    got = renders(b)
    assert {k: v for k, v in got.items() if k[1] != "dusk"} == before


def test_import_then_check_and_compose(tmp_path, capsys):
    pal, b = imp(tmp_path)
    assert run("palette", b, "--import", pal) == 0
    assert run("check", b) == 0
    assert run("compose", "-o", tmp_path / "o.px", f"{b}:b/0@0,0") == 0
    assert pxart.parse(tmp_path / "o.px").palette_refs == ["pal.px"]


def test_help_documents_import():
    text = " ".join(pxart.__doc__.split())
    assert "[--remove KEYS [--to KEY]] [--in DIR] [--import P.px]" in text
    assert "--import P.px adds '@palette P.px' to FILE (re-pointed from FILE's directory) and drops FILE's key lines P " \
        "has in the same colors" in text
    assert "FILE renders as before, in every variant it had" in text


def test_readme_documents_import():
    readme = " ".join((pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text().split())
    assert "`--import pal.px` adds a `@palette pal.px` line to a sprite and drops its key lines pal.px has in the " \
        "same colors, so it renders as before" in readme
