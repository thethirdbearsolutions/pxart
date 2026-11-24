"""anim's GIF plays as often as the group's repeat says; a cell label's size and color count don't run together, and a
16x24 frame gets its 1x copy beside the label (PX-50)."""
import pathlib
import sys

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402
from test_pxart import run, write  # noqa: E402


def idle(repeat):
    head = "k #3f2631\ng #43e1b3\n" + (f"@anim idle ms=100 repeat={repeat}\n" if repeat is not None else "")
    return head + "@frame idle/0\nkg\n@frame idle/1\ngk\n@frame idle/2\nkk\n"


@pytest.mark.parametrize("repeat,loop", [(None, 0), (0, 0), (1, None), (3, 2)])
def test_the_gif_loops_as_repeat_says(tmp_path, capsys, repeat, loop):
    f = write(tmp_path, "a.px", idle(repeat))
    assert run("anim", f"{f}:idle", "-o", tmp_path / "a.gif") == 0
    assert Image.open(tmp_path / "a.gif").info.get("loop") == loop  # None: no loop extension, it plays once


@pytest.mark.parametrize("repeat,said", [(None, "300 ms a loop"), (1, "300 ms, played once (repeat=1)"),
                                         (3, "300 ms a pass, 3 passes (repeat=3)")])
def test_the_dry_run_says_how_often(tmp_path, capsys, repeat, said):
    f = write(tmp_path, "a.px", idle(repeat))
    assert run("anim", f"{f}:idle", "-o", tmp_path / "a.gif", "--dry-run") == 0
    assert said in capsys.readouterr().out


def labels(monkeypatch, tmp_path, w, h):
    said = []
    real = ImageDraw.ImageDraw.text

    def text(self, xy, s, *a, **k):
        said.append((xy, s))
        return real(self, xy, s, *a, **k)
    monkeypatch.setattr(ImageDraw.ImageDraw, "text", text)
    grid = "\n".join(("kgy" * w)[y % 3:y % 3 + w] for y in range(h))
    f = write(tmp_path, f"s{w}x{h}.px", f"k #3f2631\ng #43e1b3\ny #fee761\n\n{grid}\n")
    assert run("sheet", f, "-o", tmp_path / f"s{w}x{h}.png", "--scale", "4") == 0
    return f, said


@pytest.mark.parametrize("w,h", [(16, 24), (8, 8)])
def test_size_and_colors_are_drawn_apart(monkeypatch, tmp_path, w, h):
    _, said = labels(monkeypatch, tmp_path, w, h)
    (sx, sy), size = next((xy, s) for xy, s in said if s == f"{w}x{h}")
    (cx, cy), colors = next((xy, s) for xy, s in said if s == "3c")
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    assert cy == sy and cx == sx + pxart.text_w(probe, size) + pxart.LABEL_GAP


@pytest.mark.parametrize("w,h", [(16, 24), (8, 8)])
def test_the_1x_copy_sits_beside_the_label(monkeypatch, tmp_path, w, h):
    f, _ = labels(monkeypatch, tmp_path, w, h)
    sheet = Image.open(tmp_path / f"s{w}x{h}.png").convert("RGBA")
    # the 1x copy is the only place the sheet has the sprite's exact pixels at 1x: find its top-left row
    want = [pxart.parse(f).resolved()[c] for c in pxart.parse(f).frames[0].grid[0]]
    rows = [[sheet.getpixel((x, y)) for x in range(sheet.width)] for y in range(sheet.height)]
    found = any(r[x:x + w] == want for r in rows for x in range(sheet.width - w))
    assert found
