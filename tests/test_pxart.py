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
    with pytest.raises(SystemExit):
        pxart.main(["mask", str(p), "--keep", "0,0,1,1", "--keep-circle", "1,1,1"])


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
    assert "walk/down/1  4x2  200ms" in out and "idle  4x2  100ms" in out and "variants: night" in out


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

def test_crop_note_names_crop_rectangle(tmp_path, capsys):
    p = write(tmp_path, "a.px", "k #000000\n@frame f\nkkk\nkkk\nkkk\n")
    assert run("crop", f"{p}:f", "1,1,2,2", "-o", f"{p}:g") == 0
    out = capsys.readouterr().out
    assert "(size from the crop rectangle)" in out and "--size" not in out
    assert "5 px of f fall outside the 2x2 canvas" in out
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
    assert capsys.readouterr().out == f"moved a/1 after a/0; no change: {p}\n" and untouched(p, before, m)


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
    return pxart.motion(doc.image(doc.frames[0]), doc.image(doc.frames[1]))


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
    assert lines[1].endswith(f"vs idle/0: no shift then {n_none}px (rows 9+ still; shift +0,-1: {n_shift}px)")
    _, _, n_shift, n_none, still = motion_of(tmp_path, BREATHE_1, BREATHE_0)  # chest back down
    assert lines[0].endswith(f"vs idle/1: no shift then {n_none}px (rows {still}+ still; shift +0,+1: {n_shift}px)")
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
    assert lines[1].endswith(f"vs idle/0: shift +0,+1 then 0px (no shift: {n_none}px)")
    assert lines[0].endswith(f"vs idle/1: shift +0,-1 then 0px (no shift: {n_none}px)")


def test_bob_strip_shows_nothing_changed(tmp_path, capsys):
    anim_lines(tmp_path, capsys, BOB_0, BOB_1)
    assert magenta_rows(tmp_path, 1) == set() and magenta_rows(tmp_path, 0) == set()


def test_walk_with_bob_and_new_leg_pose_reports_shift(tmp_path, capsys):
    dx, dy, n_shift, n_none, still = motion_of(tmp_path, WALK_0, WALK_1)
    assert (dx, dy) == (0, -1) and still is None and 0 < n_shift < n_none
    lines = anim_lines(tmp_path, capsys, WALK_0, WALK_1)
    assert f"shift +0,-1 then {n_shift}px (no shift: {n_none}px)" in lines[1]


def test_walk_strip_lights_the_legs_not_the_body(tmp_path, capsys):
    anim_lines(tmp_path, capsys, WALK_0, WALK_1)
    rows = magenta_rows(tmp_path, 1)
    assert rows and min(rows) >= 8, rows  # only the leg rows changed once the bob is removed


def test_no_shift_line_has_no_alternative(tmp_path, capsys):
    same = [EMPTY] + BODY + LEGS
    lines = anim_lines(tmp_path, capsys, same, same)
    assert lines[1].endswith("vs idle/0: shift +0,+0 then 0px")


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
    assert (dx, dy) == (0, -1) and still is not None and still >= 12


def test_strip_png_is_taller_for_the_second_label_line(tmp_path, capsys):
    anim_lines(tmp_path, capsys, BOB_0, BOB_1)
    strip = Image.open(tmp_path / "a.strip.png")
    assert strip.height == 8 + 2 * (14 * 8 + 8) + 14 + 26


def test_help_documents_breathing_strip():
    doc = pxart.__doc__
    assert '"shift dx,dy then N px (no shift: M px)"' in doc
    assert '"no shift then M px (rows Y+ still; shift dx,dy: N px)"' in doc and "Both counts are always shown" in doc


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


def test_top_level_frames_without_still_star_show_ms(tmp_path, capsys):
    p = write(tmp_path, "p.px", TOPLEVEL.replace("@still *\n", ""))
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "icon  1x1  100ms" in out and "[still]" not in out


def test_named_still_group_does_not_cover_top_level(tmp_path, capsys):
    p = write(tmp_path, "p.px", TOPLEVEL.replace("@still *", "@still hat"))
    assert run("frames", p) == 0
    out = capsys.readouterr().out
    assert "icon  1x1  100ms" in out and "hat/big  2x1  still" in out
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
    assert capsys.readouterr().out == f"wrote {out} \n"
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


def test_new_frame_into_single_grid_file_is_mixed(tmp_path):
    p = write(tmp_path, "a.px", "k #000000\nk\n")
    assert "E_MIXED_FRAMES" in run_err("new", f"{p}:x", "--size", "1x1")


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
    assert capsys.readouterr().out == f"removed walk/0, walk/1, walk/2; wrote {p}\n"
    assert ids(p) == ["idle/0", "icon"]


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
