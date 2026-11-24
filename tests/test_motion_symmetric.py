"""anim's shifted comparison counts pixels moved past the canvas edge, so a pair of frames reads the same both ways:
the same pixel count, opposite shifts (PX-55). Before, A->B said 'shift +0,+1 then 0px' (A's bottom row moved off the
canvas, uncounted) while B->A said 4px."""
import pathlib
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402
from test_pxart import run, write  # noqa: E402

PAL = {"g": (67, 225, 179, 255), "k": (27, 20, 32, 255), ".": (0, 0, 0, 0)}
OFF_BOTTOM = ([".kk.", "kggk", "kgkk", "kkgk"], ["....", ".kk.", "kggk", "kgkk"])  # B: A a row down, its last row gone
OFF_RIGHT = (["k.gk", "gkkg", "kgkk"], [".k.g", ".gkk", ".kgk"])  # B: A a column right, its last column gone


def img(rows):
    im = Image.new("RGBA", (len(rows[0]), len(rows)))
    im.putdata([PAL[c] for r in rows for c in r])
    return im


@pytest.mark.parametrize("a,b,shift,n", [(*OFF_BOTTOM, (0, 1), 4), (*OFF_RIGHT, (1, 0), 3)])
def test_a_pair_reads_the_same_both_ways(a, b, shift, n):
    there, back = pxart.motion(img(a), img(b)), pxart.motion(img(b), img(a))
    assert there[:3] == (*shift, n)  # the pixels moved past the edge count
    assert back[:3] == (-shift[0], -shift[1], n)


def test_anim_prints_the_same_count_on_both_legs(tmp_path, capsys):
    a, b = OFF_BOTTOM
    f = write(tmp_path, "s.px", "g #43e1b3\nk #1b1420\n@anim b ms=100 direction=pingpong\n"
              + "".join(f"@frame b/{i}\n" + "\n".join(rows) + "\n" for i, rows in enumerate([a, b, a])))
    assert run("anim", f"{f}:b") == 0
    out = capsys.readouterr().out
    assert "b/1                        100ms  vs b/0: shift +0,+1 then 4px" in out
    assert "b/2                        100ms  vs b/1: shift +0,-1 then 4px" in out
