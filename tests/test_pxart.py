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
