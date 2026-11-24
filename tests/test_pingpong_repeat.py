"""repeat=N on a pingpong means what it means in Aseprite: N one-way passes (PX-56). Aseprite's own tests
(src/doc/playback_tests.cpp, SimplePingPong2/3Repeats) play a 0..2 pingpong with repeat 3 as 0 1 2 1 0 1 2, and a
2-frame one with repeat 2 as 0 1 0."""
import json
import pathlib
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402
from test_pxart import run, write  # noqa: E402


def group(tmp_path, n, direction, repeat):
    rows = ["k" + "." * (n - 1)]
    for i in range(1, n):
        rows.append("." * i + "k" + "." * (n - 1 - i))
    return write(tmp_path, "p.px", f"k #000000\n@anim p ms=100 direction={direction}"
                 + (f" repeat={repeat}" if repeat is not None else "") + "\n"
                 + "".join(f"@frame p/{i}\n{r}\n" for i, r in enumerate(rows)))


@pytest.mark.parametrize("n,direction,repeat,played", [
    (3, "pingpong", 1, "0 1 2"), (3, "pingpong", 2, "0 1 2 1 0"), (3, "pingpong", 3, "0 1 2 1 0 1 2"),
    (2, "pingpong", 2, "0 1 0"), (4, "pingpong_reverse", 2, "3 2 1 0 1 2 3")])
def test_passes_as_aseprite_counts_them(tmp_path, capsys, n, direction, repeat, played):
    f = group(tmp_path, n, direction, repeat)
    assert run("anim", f"{f}:p", "-o", tmp_path / "p.gif") == 0
    out = capsys.readouterr().out
    assert f"as Aseprite counts them: {played} (" in out
    gif = Image.open(tmp_path / "p.gif")
    assert gif.n_frames == len(played.split()) and gif.info.get("loop") is None  # written out, played once


def test_forever_still_loops_one_cycle(tmp_path, capsys):
    f = group(tmp_path, 3, "pingpong", None)
    assert run("anim", f"{f}:p", "-o", tmp_path / "p.gif") == 0
    assert "plays pingpong: 0 1 2 1 (4 frames, 400 ms), then again" in capsys.readouterr().out
    gif = Image.open(tmp_path / "p.gif")
    assert gif.n_frames == 4 and gif.info.get("loop") == 0


def test_many_passes_are_capped_with_a_note(tmp_path, capsys):
    f = group(tmp_path, 3, "pingpong", 500)
    assert run("anim", f"{f}:p", "-o", tmp_path / "p.gif") == 0
    assert f"(the GIF writes the first {pxart.PASSES_MAX} passes)" in capsys.readouterr().out
    assert Image.open(tmp_path / "p.gif").n_frames == 3 + (pxart.PASSES_MAX - 1) * 2


def test_export_aseprite_writes_the_repeat_aseprite_reads(tmp_path):
    f = group(tmp_path, 3, "pingpong", 2)
    assert run("export", f, "--aseprite", tmp_path / "s.json") == 0
    tag = json.loads((tmp_path / "s.json").read_text())["meta"]["frameTags"][0]
    assert tag["direction"] == "pingpong" and tag["repeat"] == "2"


def test_check_hold_on_a_one_pass_pingpong_counts_each_frame_once(tmp_path, capsys):
    f = write(tmp_path, "h.px", "k #000000\n@anim p ms=100 direction=pingpong repeat=1\n"
              "@frame p/0\nk.\n@frame p/1\n.k\n@frame p/2\n.k\n")
    run("check", f)
    out = capsys.readouterr().out
    assert "ms=200" in out  # 100 + 100: one pass plays the end frame once, no turn to double the rest


@pytest.mark.parametrize("repeat,hold", [(1, 600), (2, 600), (3, 900), (0, 900)])
def test_check_hold_at_the_start_doubles_only_where_a_pass_turns(tmp_path, capsys, repeat, hold):
    # 0 and 1 identical at the starting end: no pass turns there under repeat 1 or 2 (0 1 2 3 2 1 0 stops on 0), so
    # each shows once a visit; from 3 passes, or forever, the turn there plays 1 0 1 (PX-56 loop)
    f = write(tmp_path, "d.px", f"k #000000\n@anim d ms=300 direction=pingpong repeat={repeat}\n"
              "@frame d/0\nk.\n@frame d/1\nk.\n@frame d/2\n.k\n@frame d/3\nkk\n")
    run("check", f, "-v")
    assert f"give d/0 ms={hold}" in capsys.readouterr().out
