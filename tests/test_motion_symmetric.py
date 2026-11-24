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
    assert "b/1                        100ms  vs b/0: shift +0,+1 then 4px (40%; 4 past the edge)" in out
    assert "b/2                        100ms  vs b/1: shift +0,-1 then 4px" in out


def test_random_pairs_read_the_same_count_both_ways():
    """A property: for random small pairs, A->B and B->A give the same count after the best shift. (Whether a pair
    reads 'rows N+ still' can still differ in rare pairs: pixels pushed past the top count above row N one way and
    past the bottom below it the other; the PR #30 review's case is test_review_1.)"""
    import random
    rng = random.Random(55)
    colors = [(0, 0, 0, 0), (27, 20, 32, 255), (67, 225, 179, 255)]
    for _ in range(400):
        w, h = rng.randint(2, 5), rng.randint(2, 5)
        a, b = Image.new("RGBA", (w, h)), Image.new("RGBA", (w, h))
        a.putdata([rng.choice(colors) for _ in range(w * h)])
        b.putdata([rng.choice(colors) for _ in range(w * h)])
        there, back = pxart.motion(a, b), pxart.motion(b, a)
        assert there[2] == back[2], (list(a.getdata()), list(b.getdata()))



def test_review_1_a_still_reading_holds_both_ways():
    a, b = img(["kg.", "g.k", "g.k"]), img(["g..", "kk.", "g.k"])
    there, back = pxart.motion(a, b), pxart.motion(b, a)
    assert (there[4] is None) == (back[4] is None)


def test_review_9_past_the_edge_in_onion_and_a_still_reading(tmp_path, capsys):
    a, b = OFF_BOTTOM
    f = write(tmp_path, "s.px", "g #43e1b3\nk #1b1420\n" + "".join(
        f"@frame s/{i}\n" + "\n".join(rows) + "\n" for i, rows in enumerate([a, b])))
    assert run("onion", f"{f}:s/0", f"{f}:s/1", "--dry-run") == 0
    assert "past the edge" in capsys.readouterr().out
