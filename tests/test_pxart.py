import json
import math
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
    assert capsys.readouterr().out == f"no change: {p}\n" and untouched(p, before, m)


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
    assert run("check", m, tmp_path / "tiles.px") == 0
    out = capsys.readouterr().out
    assert "map 2x1 tiles" in out and "tiles.px:floor" in out


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
    assert out.read_text() == ("pxart 1\nw #ffffff\nq #00ff00\nk #000000\n\n@variant night\nw #101010\nk #000011\n"
                               "\n@variant day\nk #222222\n")
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
    assert capsys.readouterr().out == f"copied walk/0, walk/1 to {d}; added @anim walk; wrote {d}\n"
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
    assert msg.startswith(f"frames: FILE ({s}:walk): E_KEY_CONFLICT: 1 key of SRC is another color in {d}: 'w' #ffffff "
                          "(#eeeeee there)")
    assert d.read_text() == before
    assert run(*shlex.split(msg.split("again: pxart ", 1)[1])) == 0
    assert run("frames", f"{s}:walk", "--copy-to", d) == 0
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
    assert "[--copy-to DST [ID...]]" in doc and "'frames hero.px:walk --copy-to beast.px --after idle/3'" in doc


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


def test_compose_conflict_new_out_lists_every_key_both_colors_and_origin(tmp_path):
    a, b, c = conflict_layers(tmp_path)
    out = tmp_path / "o.px"
    msg = run_err("compose", "-o", out, "--size", "4x3", f"{a}@0,0", f"{b}@0,1")
    assert msg == (f"compose: layer 2 ({b}): E_KEY_CONFLICT: 3 keys of this layer are other colors in the new {out}: "
                   f"'h' #aaaaaa (#111111 there, from layer 1 ({a})), 'n' #bbbbbb (#222222 there, from layer 1 ({a})), "
                   f"'w' #f6ecd2 (#eee0b8 there, from layer 1 ({a})); to keep both colors, give this layer's keys free "
                   f"ones (no pixel changes color), then compose again: pxart recolor {b} 'h>a' 'n>b' 'w>c'")
    assert not out.exists()
    assert " here" not in msg and "recolor one side" not in msg


def test_compose_conflict_every_layer_at_once(tmp_path):
    a, b, c = conflict_layers(tmp_path)
    out = tmp_path / "o.px"
    lines = run_err("compose", "-o", out, "--size", "4x3", f"{a}@0,0", f"{b}@0,1", f"{c}@1,1").splitlines()
    assert len(lines) == 2
    assert lines[0].startswith(f"compose: layer 2 ({b}): E_KEY_CONFLICT: 3 keys")
    assert lines[1] == (f"compose: layer 3 ({c}): E_KEY_CONFLICT: 1 key of this layer is another color in the new "
                        f"{out}: 'q' #654321 (#123456 there, from layer 2 ({b})); to keep both colors, give this layer's "
                        f"keys free ones (no pixel changes color), then compose again: pxart recolor {c} 'q>d'")


def test_compose_conflict_recipe_works(tmp_path, capsys):
    # The fix the message gives, run as it says, lets the compose through, and every layer's colors survive.
    import shlex
    a, b, c = conflict_layers(tmp_path)
    out = tmp_path / "o.px"
    argv = ["compose", "-o", out, "--size", "4x3", f"{a}@0,0", f"{b}@0,1", f"{c}@1,1"]
    for line in run_err(*argv).splitlines():
        fix = shlex.split(line.split("again: pxart ", 1)[1])
        assert run(*fix) == 0
    assert run(*argv) == 0
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
                   "'h' #aaaaaa (#111111 there), 'w' #f6ecd2 (#eee0b8 there); to keep both colors, give this layer's "
                   f"keys free ones (no pixel changes color), then compose again: pxart recolor {b} 'h>a' 'w>b'")
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
    assert msg.endswith(f"pxart recolor {b} 'k>d'")


def test_compose_conflict_quotes_paths_and_keys_for_the_shell(tmp_path):
    import shlex
    d = tmp_path / "my parts"
    d.mkdir()
    a = write(d, "a.px", "' #000000\n\n'\n")
    b = write(d, "b.px", "' #ffffff\n\n'\n")
    msg = run_err("compose", "-o", tmp_path / "o.px", "--size", "2x1", f"{a}@0,0", f"{b}@1,0")
    fix = shlex.split(msg.split("again: pxart ", 1)[1])
    assert fix == ["recolor", str(b), "'>a"]
    assert run(*fix) == 0 and pxart.parse(b).frames[0].grid == ["a"]


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
                   "there), 'n' #bbbbbb (#222222 there), 'w' #f6ecd2 (#eee0b8 there); to keep both colors, give SRC's "
                   f"keys free ones (no pixel changes color), then paste again: pxart recolor {b} 'h>a' 'n>b' 'w>c'")
    assert a.read_text() == before


def test_paste_conflict_recipe_works(tmp_path):
    import shlex
    a, b, c = conflict_layers(tmp_path)
    fix = shlex.split(run_err("paste", b, "--into", a, "--at", "0,0").split("again: pxart ", 1)[1])
    assert run(*fix) == 0
    assert run("paste", b, "--into", a, "--at", "0,0") == 0
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
    ("w>k", "E_BAD_ARG", "to repaint w's pixels as k write w=k"),
    ("w>w", "E_BAD_ARG", "'w' is already one"),
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
    assert "E_BAD_ARG" in msg and "'Z' is already one" in msg and p.read_text() == RENAME


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
    assert msg.startswith(f"{tmp_path / 'nope.px'}: E_FILE")


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


def test_breath_with_moving_legs_keeps_the_fall_shifted(tmp_path, capsys):
    # One frame changes the leg pose: the legs aren't identical in every frame, so only the frame that passes on its
    # own is still, as before.
    walky = WAVE + [WAVE[-1]] + LEGS_WIDE
    lines = anim_lines(tmp_path, capsys, IDLE_4[0], IDLE_4[1], walky, IDLE_4[3])
    assert "(rows 9+ still;" in lines[1]
    assert "vs idle/2: shift +0,+1 then" in lines[3]


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
    assert capsys.readouterr().out.splitlines()[0] == (f"note: {out} leaves out layer 2 ({b}:y)'s color for 'z' "
                                                       f"(unused there): it has layer 1 ({a}:x)'s, the earlier layer's")


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
        f"note: {out} leaves out layer 1 ({a})'s colors for 'hn' (unused there): it has layer 2 ({b})'s, which that "
        "layer uses",
        f"note: {out} leaves out layer 2 ({b})'s color for 'r' (unused there): it has layer 1 ({a})'s, the earlier "
        "layer's",
        f"note: {out} leaves out layer 2 ({b})'s color for 'w' (unused there): it has layer 1 ({a})'s, which that "
        "layer uses",
        f"note: {out} leaves out layer 2 ({b})'s color for 'q' (unused there): it has layer 3 ({c})'s, which that "
        "layer uses",
    ]


def test_compose_key_note_matches_the_palette_written(tmp_path, capsys):
    # Every key a note names is in OUT, in the color of the layer the note says it has.
    a, b, c = keynote_layers(tmp_path)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, "--size", "3x3", f"{a}@0,0", f"{b}@0,1", f"{c}@1,1") == 0
    pal = pxart.parse(out).palette
    assert pal == {"w": pxart.hex2rgba("#eee0b8"), "k": (0, 0, 0, 255), "h": pxart.hex2rgba("#aaaaaa"),
                   "n": pxart.hex2rgba("#bbbbbb"), "q": pxart.hex2rgba("#654321"), "r": pxart.hex2rgba("#333333")}
    docs = {str(a): pxart.parse(a), str(b): pxart.parse(b), str(c): pxart.parse(c)}
    import re
    for line in notes_of(capsys.readouterr().out):
        m = re.match(r"note: .* leaves out layer \d \((.*)\)'s colors? for '(\w+)' \(unused there\): it has layer \d "
                     r"\((.*)\)'s", line)
        lost, keys, kept = m.groups()
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
        f"note: {out} leaves out layer 1 ({a})'s color for 'z' (unused there): it has layer 3 ({c})'s, which that "
        "layer uses",
        f"note: {out} leaves out layer 2 ({b})'s color for 'z' (unused there): it has layer 3 ({c})'s, which that "
        "layer uses",
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
    assert "(quietly: the pixels outside the rectangle are what crop is for, so there's no note)" in pxart.__doc__


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
