"""GAMES-358: palette slots. A key line may list alternatives after its color ('f #e0ac69 | #f5cfa0'): the first is
the key's base color, which every command draws and exports as before; render/sheet --slots show combinations, and
export --indexed hands a game the key grids and the palette to recolor at runtime."""
import json
import pathlib
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

VILL = """# a villager
pxart 1
h #6b3e1f | #2b1a0e | #d9a441
f #e0ac69 | #f5cfa0 | #c68642 | #8d5524 | #ffdbac
k #1a1a1a
c #3498db | #e74c3c | #9b59b6

@anim walk ms=125
@frame walk/0 pivot=1,3
.hh.
.fk.
fccf
.cc.
@frame walk/1
.hh.
.kf.
.ccf
fcc.
"""


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


def write(tmp_path, name, text):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def rgb(h):
    return pxart.hex2rgba(h)


# ---------------------------------------------------------------- the format

def test_every_existing_file_round_trips_byte_for_byte():
    # no file had slots before: each parses and writes back exactly as it was
    n = 0
    for p in sorted(list((ROOT / "examples").rglob("*.px")) + list((ROOT / "tests" / "fixtures").rglob("*.px"))):
        text = p.read_text()
        try:
            doc = pxart.parse(p)
        except pxart.PxError:
            try:
                doc = pxart.parse(p, palette_only=True)
            except pxart.PxError:
                continue
        assert doc.text() == text, p
        assert not doc.slots(), p
        n += 1
    assert n > 20


def test_a_slot_line_parses_to_its_base_color_with_alternatives(tmp_path):
    doc = pxart.parse(write(tmp_path, "v.px", VILL))
    f = doc.palette["f"]
    assert f == rgb("#e0ac69") and isinstance(f, pxart.Slot)
    assert f.alts == tuple(rgb(x) for x in ("#f5cfa0", "#c68642", "#8d5524", "#ffdbac"))
    assert doc.palette["k"] == rgb("#1a1a1a") and not isinstance(doc.palette["k"], pxart.Slot)
    assert list(doc.slots()) == ["h", "f", "c"] and doc.slots()["h"][0] == rgb("#6b3e1f")
    assert doc.image(doc.frames[0]).getpixel((1, 1)) == rgb("#e0ac69")  # the base color


def test_slot_lines_keep_their_spelling_and_new_ones_are_written_spaced(tmp_path):
    text = "pxart 1\nf #e0ac69|#f5cfa0 |  #C68642\nk #1a1a1a\n\nfk\n"
    p = write(tmp_path, "a.px", text)
    doc = pxart.parse(p)
    assert doc.text() == text
    assert pxart.fmt_key(doc.palette["f"]) == "#e0ac69 | #f5cfa0 | #c68642"
    assert run("set", f"{p}", "k", "0,0") == 0
    assert p.read_text() == text.replace("\nfk\n", "\nkk\n")


def test_key_value():
    assert pxart.key_value("#112233") == (0x11, 0x22, 0x33, 255)
    assert pxart.key_value("transparent") == pxart.CLEAR
    s = pxart.key_value("#112233 | transparent|#44556680")
    assert s.alts == (pxart.CLEAR, (0x44, 0x55, 0x66, 0x80))
    assert pxart.key_value("#112233 | nope") is None
    assert pxart.same_key(pxart.key_value("#112233"), (0x11, 0x22, 0x33, 255))
    assert not pxart.same_key(s, (0x11, 0x22, 0x33, 255)) and s == (0x11, 0x22, 0x33, 255)


@pytest.mark.parametrize("text,bit", [
    ("f #e0ac69 | #zzz\n\nf\n", "'#e0ac69 | #zzz' isn't #rrggbb"),
    ("f #e0ac69 | \n\nf\n", "(a slot is 'k #rrggbb | #rrggbb ...')"),
    ("f #e0ac69\n@variant night\nf #000000 | #111111\n\nf\n", "a variant sets one color per key"),
    (". transparent | #000000\nf #e0ac69\n\nf\n", "alternatives (a slot) go on a base palette line, not '.'"),
])
def test_bad_slots_are_bad_colors(tmp_path, text, bit):
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(write(tmp_path, "a.px", text))
    assert e.value.issues[0].code == "E_BAD_COLOR" and bit in str(e.value.issues[0])


def test_existing_outputs_use_base_colors(tmp_path):
    p = write(tmp_path, "v.px", VILL)
    plain = p.read_text().replace(" | #2b1a0e | #d9a441", "").replace(" | #f5cfa0 | #c68642 | #8d5524 | #ffdbac", "") \
        .replace(" | #e74c3c | #9b59b6", "")
    q = write(tmp_path, "plain.px", plain)
    for src, d in ((p, "a"), (q, "b")):
        assert run("export", src, "--frames", tmp_path / d, "--aseprite", tmp_path / f"{d}.json",
                   "--tiled", tmp_path / f"{d}.tsj") == 0
        assert run("render", f"{src}:walk/0", "--plain", "-o", tmp_path / f"{d}-r.png") == 0
    for name in ("walk/0.png", "walk/1.png"):
        assert Image.open(tmp_path / "a" / name).tobytes() == Image.open(tmp_path / "b" / name).tobytes()
    for name in ("a.png", "a-r.png"):
        assert Image.open(tmp_path / name).tobytes() == Image.open(tmp_path / name.replace("a", "b", 1)).tobytes()
    assert json.loads((tmp_path / "a.json").read_text())["frames"] == json.loads((tmp_path / "b.json").read_text())["frames"]


# ---------------------------------------------------------------- check

def test_check_passes_slots_and_notes_a_repeated_color(tmp_path):
    p = write(tmp_path, "v.px", VILL)
    assert run("check", p) == 0
    q = write(tmp_path, "d.px", "f #e0ac69 | #f5cfa0 | #e0ac69\n\nf\n")
    assert run("check", q) == 0


def test_check_notes_a_repeated_slot_color(tmp_path, capsys):
    q = write(tmp_path, "d.px", "f #e0ac69 | #f5cfa0 | #e0ac69\n\nf\n")
    run("check", q)
    assert "slot 'f' lists #e0ac69 more than once" in capsys.readouterr().out


def test_check_palette_fails_an_alternative_off_the_palette(tmp_path, capsys):
    p = write(tmp_path, "v.px", VILL)
    allowed = write(tmp_path, "allowed.hex", "#6b3e1f\n#2b1a0e\n#d9a441\n#e0ac69\n#1a1a1a\n#3498db\n#e74c3c\n#9b59b6\n")
    assert run("check", p, "--palette", allowed) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "slot alternatives off-palette: f #f5cfa0 #c68642 #8d5524 #ffdbac" in out
    # a palette file with slots allows its alternatives too
    pal = write(tmp_path, "pal.px", "\n".join(VILL.split("\n")[2:6]) + "\n")
    assert run("check", p, "--palette", pal) == 0


# ---------------------------------------------------------------- variants and palette files

def test_slots_come_from_a_palette_file_and_a_local_line_replaces_them(tmp_path, capsys):
    write(tmp_path, "pal.px", "h #6b3e1f | #2b1a0e\nf #e0ac69 | #f5cfa0\n@variant night\nh #000000\n")
    p = write(tmp_path, "a.px", "pxart 1\n@palette pal.px\n\nhf\n")
    doc = pxart.parse(p)
    assert doc.slots() == {"h": (rgb("#6b3e1f"), rgb("#2b1a0e")), "f": (rgb("#e0ac69"), rgb("#f5cfa0"))}
    q = write(tmp_path, "b.px", "pxart 1\n@palette pal.px\nf #e0ac69\n\nhf\n")
    assert list(pxart.parse(q).slots()) == ["h"]
    assert run("check", q) == 0
    assert "local keys override @palette colors: f" in capsys.readouterr().out
    r = write(tmp_path, "c.px", "pxart 1\n@palette pal.px\nf #e0ac69 | #f5cfa0\n\nhf\n")
    run("check", r)
    assert "local keys repeat @palette colors: f" in capsys.readouterr().out


# ---------------------------------------------------------------- every writer keeps the alternatives

SLOT_F = "f #e0ac69 | #f5cfa0 | #c68642 | #8d5524 | #ffdbac"


def test_compose_new_and_existing_out_keep_slot_lines(tmp_path):
    p = write(tmp_path, "v.px", VILL)
    out = tmp_path / "o.px"
    assert run("compose", "-o", out, f"{p}:walk/0@0,0") == 0
    assert SLOT_F in out.read_text() and "h #6b3e1f | #2b1a0e | #d9a441" in out.read_text()
    dst = write(tmp_path, "dst.px", "pxart 1\nz #000000\n\n@frame a\nzzzz\nzzzz\nzzzz\nzzzz\n")
    assert run("compose", "-o", f"{dst}:b", f"{p}:walk/0@0,0") == 0
    assert SLOT_F in dst.read_text()


def test_paste_frames_copy_extract_and_put_keep_slot_lines(tmp_path):
    p = write(tmp_path, "v.px", VILL)
    dst = write(tmp_path, "dst.px", "pxart 1\nz #000000\n\n@frame a\nzzzz\nzzzz\nzzzz\nzzzz\n")
    assert run("paste", f"{p}:walk/0", "--into", f"{dst}:a", "--at", "0,0") == 0
    assert SLOT_F in dst.read_text()
    dst2 = write(tmp_path, "dst2.px", "pxart 1\nz #000000\n\n@frame a\nz\n")
    assert run("frames", f"{p}:walk", "--copy-to", dst2) == 0
    assert SLOT_F in dst2.read_text()
    assert run("extract", f"{p}:walk/1", "-o", tmp_path / "x.px") == 0
    assert SLOT_F in (tmp_path / "x.px").read_text()
    put = write(tmp_path, "put.px", "pxart 1\nz #000000\n\n@frame a\nz\n")
    sys_stdin = sys.stdin
    try:
        sys.stdin = type("T", (), {"read": lambda self: "g #111111 | #222222\ngz\n", "isatty": lambda self: False})()
        assert run("put", f"{put}:a") == 0
    finally:
        sys.stdin = sys_stdin
    assert "g #111111 | #222222" in put.read_text()


def test_recolor_keeps_alternatives_through_renames_and_base_changes(tmp_path):
    p = write(tmp_path, "v.px", VILL)
    assert run("recolor", p, "f>s") == 0  # a rename: f's line becomes s's
    assert SLOT_F.replace("f #", "s #") in p.read_text() and "\nf #" not in p.read_text()
    assert run("recolor", f"{p}:walk/0", "s>t") == 0  # s stays for walk/1; t is added in s's color, slot too
    assert SLOT_F.replace("f #", "t #") in p.read_text() and SLOT_F.replace("f #", "s #") in p.read_text()
    assert run("recolor", p, "s=#abcdef") == 0
    assert "s #abcdef | #f5cfa0 | #c68642 | #8d5524 | #ffdbac" in p.read_text()


def test_palette_edits_keep_and_move_slots(tmp_path, capsys):
    p = write(tmp_path, "v.px", VILL)
    assert run("palette", p, "--extract-to", tmp_path / "pal.px", "--repoint") == 0
    pal = (tmp_path / "pal.px").read_text()
    assert SLOT_F in pal and "\nf #" not in p.read_text()
    assert pxart.parse(p).slots()["f"][1] == rgb("#f5cfa0")
    # --add a new slot, then set another key's alternatives, then list
    assert run("palette", p, "--add", "g=#111111|#222222") == 0
    assert "g #111111 | #222222" in p.read_text()
    assert run("palette", p, "--add", "g=#111111|#333333") == 0
    assert "g #111111 | #333333" in p.read_text()
    capsys.readouterr()
    assert run("palette", p) == 0
    assert "| #333333" in capsys.readouterr().out
    # --hoist moves the slot line into the palette file
    assert run("palette", p, "--hoist", "g") == 0
    assert "g #111111 | #333333" in (tmp_path / "pal.px").read_text() and "g #" not in p.read_text()
    # a variant --add can't take alternatives
    assert "a variant sets one color per key" in run_err("palette", p, "--variant", "night", "--add", "k=#000000|#111111")


def test_palette_import_drops_only_lines_the_file_says_the_same(tmp_path):
    write(tmp_path, "pal.px", "f #e0ac69 | #f5cfa0\nk #1a1a1a\n")
    a = write(tmp_path, "a.px", "pxart 1\nf #e0ac69 | #f5cfa0\nk #1a1a1a\n\nfk\n")
    assert run("palette", a, "--import", tmp_path / "pal.px") == 0
    assert "\nf #" not in a.read_text() and pxart.parse(a).slots()["f"][1] == rgb("#f5cfa0")
    b = write(tmp_path, "b.px", "pxart 1\nf #e0ac69 | #c68642\nk #1a1a1a\n\nfk\n")
    assert run("palette", b, "--import", tmp_path / "pal.px") == 0
    assert "f #e0ac69 | #c68642" in b.read_text()  # other alternatives: the local line stays, an override
    assert pxart.parse(b).slots()["f"][1] == rgb("#c68642")


def test_extract_inline_palette_keeps_imported_slots(tmp_path):
    write(tmp_path, "pal.px", "f #e0ac69 | #f5cfa0\n")
    a = write(tmp_path, "a.px", "pxart 1\n@palette pal.px\n\n@frame x\nf\n")
    assert run("extract", f"{a}:x", "-o", tmp_path / "out" / "x.px", "--inline-palette") == 0
    assert "f #e0ac69 | #f5cfa0" in (tmp_path / "out" / "x.px").read_text()


def test_every_palette_line_is_written_by_one_function():
    # Doc.lines() is the one place a key line is spelled; any other would drop the alternatives
    src = (ROOT / "pxart.py").read_text()
    assert src.count("fmt_key(v)}") == 1 and 'f"{k} {fmt_color(v)}") for k, v in self.palette' not in src
