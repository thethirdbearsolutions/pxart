"""onion --feet / --rows count the band's rows of both frames, and pixels pushed past an edge, so a pair read A->B and
B->A gives the same count with opposite shifts (PX-61), as the whole canvas does since PX-55."""
import pathlib
import random
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402
from test_pxart import run, write  # noqa: E402

COLORS = [(0, 0, 0, 0), (27, 20, 32, 255), (67, 225, 179, 255)]
PAL = {".": COLORS[0], "k": COLORS[1], "g": COLORS[2]}


def img(rows):
    im = Image.new("RGBA", (len(rows[0]), len(rows)))
    im.putdata([PAL[c] for r in rows for c in r])
    return im


def both_ways(a, b, y0, y1):
    there, back = pxart.band_shift(a, b, y0, y1), pxart.band_shift(b, a, y0, y1)
    return there, back


def test_random_band_pairs_read_the_same_both_ways():
    rng = random.Random(61)
    for _ in range(400):
        w, h = rng.randint(2, 6), rng.randint(2, 6)
        a, b = Image.new("RGBA", (w, h)), Image.new("RGBA", (w, h))
        a.putdata([rng.choice(COLORS) for _ in range(w * h)])
        b.putdata([rng.choice(COLORS) for _ in range(w * h)])
        y0 = rng.randint(0, h - 1)
        y1 = rng.randint(y0, h - 1)
        there, back = both_ways(a, b, y0, y1)
        assert there[2] == back[2] and there[3] == back[3], (y0, y1, list(a.getdata()), list(b.getdata()))


def test_a_clear_winner_gives_opposite_shifts():
    # a 2-wide foot steps 1 right; nothing else on the canvas
    a, b = img(["......", "......", ".kk...", ".gg..."]), img(["......", "......", "..kk..", "..gg.."])
    there, back = both_ways(a, b, 2, 3)
    assert there[:3] == (1, 0, 0) and back[:3] == (-1, 0, 0)


def test_a_ghost_against_the_left_wall():
    # B is A moved 1 left, its left column pushed past the wall: 2px gone both ways, not 0 one way and 1 the other
    a, b = img(["kg..", "gk..", "...."]), img(["g...", "k...", "...."])
    there, back = both_ways(a, b, 0, 1)
    assert (there[0], there[2]) == (-1, 2) and (back[0], back[2]) == (1, 2)
    assert there[4] == 2  # both pushed past the edge


def test_pixels_moving_into_the_band_count_as_pixels_moving_out():
    # the whole sprite drops a row into a 1-row feet band: B's band row came from above it, A's band row left it
    a, b = img(["kk..", "gg..", "...."]), img(["....", "kk..", "gg.."])
    there, back = both_ways(a, b, 2, 2)
    assert there[2] == back[2] == 0 and there[:2] == (0, 1) and back[:2] == (0, -1)


def test_onion_band_readout_is_the_same_both_ways_and_names_the_edge(tmp_path, capsys):
    p = write(tmp_path, "g.px", "k #1b1420\ng #43e1b3\n@frame a\nkg..\ngk..\n@frame b\ng...\nk...\n")

    def line(x, y):
        assert run("onion", f"{p}:{x}", f"{p}:{y}", "--rows", "0-1", "--dry-run") == 0
        return next(s for s in capsys.readouterr().out.splitlines() if s.startswith("B vs A"))
    there, back = line("a", "b"), line("b", "a")
    assert "best shift -1,+0 then 2px changed (2 past the edge)" in there
    # the way back, the same 2px are A's left column, on the canvas
    assert "best shift +1,+0 then 2px changed (no shift: 4px)" in back
