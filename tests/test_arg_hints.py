"""Two argument errors that say what to do (PX-21): from-png's output given without -o, and palette --remove's keys
given as separate words. A comma list and a real ',' key read as they should."""
import pathlib
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402
from test_pxart import run, run_err, write  # noqa: E402


def png(tmp_path):
    p = tmp_path / "p.png"
    Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(p)
    return p


def test_from_png_output_without_o_says_to_put_it_after_o(tmp_path):
    p = png(tmp_path)
    err = run_err("from-png", p, tmp_path / "face.px")
    assert "is a .px, and from-png reads PNGs: the output goes after -o: pxart from-png" in err
    assert err.endswith(f"-o {tmp_path / 'face.px'}")
    assert not (tmp_path / "face.px").exists()


def test_from_png_a_px_beside_o_points_at_palette(tmp_path):
    p = png(tmp_path)
    err = run_err("from-png", p, tmp_path / "pal.px", "-o", tmp_path / "out.px")
    assert f"-o {tmp_path / 'out.px'} is the output; to reuse a .px's palette, --palette {tmp_path / 'pal.px'}" in err


def test_palette_remove_with_spaced_keys_says_one_word(tmp_path, capsys):
    f = write(tmp_path, "f.px", "k #000000\nh #ff0000\nj #00ff00\n\nk\n")
    with pytest.raises(SystemExit):
        pxart.main(["palette", str(f), "--remove", "h", "j"])
    assert (f"unrecognized arguments: j (--remove takes its keys as one word: pxart palette {f} --remove hj or "
            f"pxart palette {f} --remove h,j)") in capsys.readouterr().err


@pytest.mark.parametrize("given", ["hj", "h,j"])
def test_palette_remove_reads_a_run_or_a_comma_list(tmp_path, given):
    f = write(tmp_path, "f.px", "k #000000\nh #ff0000\nj #00ff00\n, #0000ff\n\nk\n")
    assert run("palette", f, "--remove", given) == 0
    keys = pxart.parse(f).palette
    assert "h" not in keys and "j" not in keys and "," in keys  # the comma list leaves a real ',' key alone


def test_palette_remove_a_real_comma_key(tmp_path):
    f = write(tmp_path, "f.px", "k #000000\nh #ff0000\n, #0000ff\n\nk\n")
    assert run("palette", f, "--remove", ",") == 0
    assert "," not in pxart.parse(f).palette and "h" in pxart.parse(f).palette


# ---------------------------------------------------------------- the private loop's cases


def test_from_png_hint_keeps_grid_and_the_other_options(tmp_path):
    p = png(tmp_path)
    for argv in (["from-png", p, "--grid", "1x1", "--id", "face", tmp_path / "g.px"],
                 ["from-png", "--grid", "1x1", tmp_path / "g.px", p]):
        err = run_err(*argv)
        assert "--grid 1x1" in err and err.endswith(f"-o {tmp_path / 'g.px'}")


@pytest.mark.parametrize("words,want", [(["h", "j", "--to", "k"], ["--remove hj --to k", "--remove h,j --to k"]),
                                        ([",", "x"], ["--remove ,,x"]), (["x", ","], ["--remove x,,"]),
                                        (["h,", "j"], ["--remove hj", "--remove h,j"])])
def test_remove_hint_is_a_whole_command_that_runs(tmp_path, capsys, words, want):
    f = write(tmp_path, "f.px", "k #000000\nh #ff0000\nj #00ff00\nx #0000ff\n, #0000f0\n\nk\n")
    with pytest.raises(SystemExit):
        pxart.main(["palette", str(f), "--remove", *words, "--dry-run"])
    err = capsys.readouterr().err
    for w in want:
        assert w in err
    import shlex
    cmd = err.split("one word: ")[1].split(" or ")[0].rstrip(")\n")
    assert run(*shlex.split(cmd)[1:]) == 0  # the first suggestion runs as printed
    if "," in words:
        assert " or " not in err  # one form only: 'x,' isn't a run of keys
