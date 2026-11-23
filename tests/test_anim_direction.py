"""anim follows a group's @anim direction (PX-42): a pingpong GIF plays 0 1 2 3 2 1, and the numbers compare the pairs
that really play, with no forward wrap from the last frame to the first."""
import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def walk(tmp_path, direction, extra=""):
    p = tmp_path / "w.px"
    p.write_text(f"pxart 1\nk #000000\n@anim walk direction={direction} ms=130{extra}\n"
                 + "".join(f"@frame walk/{i}\n" + "." * i + "k" + "." * (3 - i) + "\n" for i in range(4)))
    return p


def pairs(out):
    return [(l.split()[0], l.split("vs ")[1].split(":")[0]) for l in out.splitlines() if " vs " in l]


def test_pingpong_compares_the_pairs_it_plays(tmp_path, capsys):
    assert run("anim", walk(tmp_path, "pingpong")) == 0
    out = capsys.readouterr().out
    assert "note: walk plays pingpong: 0 1 2 3 2 1 (6 frames, 780 ms), then again; the GIF and the numbers follow " \
        "it, the way back marked 'back'" in out
    assert pairs(out) == [("walk/0", "walk/1 back"), ("walk/1", "walk/0"), ("walk/2", "walk/1"), ("walk/3", "walk/2"),
                          ("walk/2", "walk/3"), ("walk/1", "walk/2 back")]
    assert "  walk/2 back " in out and "  walk/1 back " in out
    assert ("walk/0", "walk/3") not in pairs(out)  # a pingpong never plays 3 -> 0


def test_the_gif_plays_the_turnaround(tmp_path, capsys):
    out = tmp_path / "w.gif"
    assert run("anim", walk(tmp_path, "pingpong"), "-o", out) == 0
    gif = Image.open(out)
    assert gif.n_frames == 6
    xs = []
    for i in range(gif.n_frames):
        gif.seek(i)
        im = gif.convert("RGBA")
        xs.append(next(x for x in range(4) if im.getpixel((x * 8 + 1, 1))[:3] == (0, 0, 0)))
    assert xs == [0, 1, 2, 3, 2, 1]


def test_reverse_and_pingpong_reverse(tmp_path, capsys):
    assert run("anim", walk(tmp_path, "reverse")) == 0
    assert [a for a, _ in pairs(capsys.readouterr().out)] == ["walk/3", "walk/2", "walk/1", "walk/0"]
    assert run("anim", walk(tmp_path, "pingpong_reverse")) == 0
    out = capsys.readouterr().out
    assert "plays pingpong_reverse: 3 2 1 0 1 2 (6 frames, 780 ms), then again" in out
    assert [a for a, _ in pairs(out)] == ["walk/3", "walk/2", "walk/1", "walk/0", "walk/1", "walk/2"]


def test_forward_says_nothing_new(tmp_path, capsys):
    assert run("anim", walk(tmp_path, "forward")) == 0
    out = capsys.readouterr().out
    assert "plays" not in out and pairs(out)[0] == ("walk/0", "walk/3")


def test_pingpong_played_once_has_no_wrap(tmp_path, capsys):
    assert run("anim", walk(tmp_path, "pingpong", " repeat=1")) == 0
    out = capsys.readouterr().out
    assert "walk/0" in out and "plays once (repeat=1); no wrap-around" in out
    assert "plays pingpong: 0 1 2 3 2 1 (6 frames, 780 ms), once;" in out
    assert len(pairs(out)) == 5


def test_a_two_frame_pingpong_plays_as_forward_and_says_nothing(tmp_path, capsys):
    p = tmp_path / "t.px"
    p.write_text("k #000000\n@anim a direction=pingpong ms=100\n@frame a/0\nk.\n@frame a/1\n.k\n")
    assert run("anim", p) == 0
    assert "plays" not in capsys.readouterr().out


def test_repeat_n_says_how_many_times_and_fps_sets_the_total(tmp_path, capsys):
    assert run("anim", walk(tmp_path, "pingpong", " repeat=3"), "--fps", 10) == 0
    assert "(6 frames, 600 ms), 3 times;" in capsys.readouterr().out


def test_a_part_of_a_group_plays_as_selected(tmp_path, capsys):
    p = walk(tmp_path, "pingpong")
    assert run("anim", f"{p}:walk/0,walk/1,walk/3") == 0
    out = capsys.readouterr().out
    assert "plays" not in out and [a for a, _ in pairs(out)] == ["walk/0", "walk/1", "walk/3"]
    p = walk(tmp_path, "reverse")
    assert run("anim", f"{p}:walk/2,walk/0") == 0
    out = capsys.readouterr().out
    assert "plays" not in out and [a for a, _ in pairs(out)] == ["walk/2", "walk/0"]


def test_reverse_marks_nothing_back(tmp_path, capsys):
    assert run("anim", walk(tmp_path, "reverse")) == 0
    out = capsys.readouterr().out
    assert "plays reverse: 3 2 1 0 (4 frames, 520 ms), then again; the GIF and the numbers follow it\n" in out
    assert "back" not in out
    assert ("walk/3", "walk/0") in pairs(out)  # the reverse's wrap: 0 -> 3


def test_a_still_group_with_a_direction_is_not_played(tmp_path, capsys):
    p = tmp_path / "s.px"
    p.write_text("k #000000\n@anim ui direction=pingpong\n@still ui\n@frame ui/0\nk.\n@frame ui/1\n.k\n@frame ui/2\nkk\n")
    run("anim", p)
    assert "plays pingpong" not in capsys.readouterr().out


def test_the_gif_durations_follow_the_order(tmp_path):
    p = tmp_path / "d.px"
    p.write_text("k #000000\n@anim a direction=pingpong ms=100\n@frame a/0 ms=300\nk..\n@frame a/1\n.k.\n"
                 "@frame a/2 ms=200\n..k\n")
    out = tmp_path / "d.gif"
    assert run("anim", p, "-o", out) == 0
    gif = pxart.Image.open(out)
    durs = []
    for i in range(gif.n_frames):
        gif.seek(i)
        durs.append(gif.info["duration"])
    assert durs == [300, 100, 200, 100]


def test_dir_output_plays_each_group_its_way(tmp_path, capsys):
    p = tmp_path / "m.px"
    p.write_text("k #000000\n@anim a direction=pingpong ms=100\n@anim b direction=reverse ms=100\n"
                 + "".join(f"@frame a/{i}\n" + "." * i + "k" + "." * (2 - i) + "\n" for i in range(3))
                 + "".join(f"@frame b/{i}\n" + "." * i + "k" + "." * (2 - i) + "\n" for i in range(3)))
    assert run("anim", p, "-o", tmp_path / "out") == 0
    out = capsys.readouterr().out
    assert "a plays pingpong: 0 1 2 1" in out and "b plays reverse: 2 1 0" in out
    assert pxart.Image.open(tmp_path / "out" / "a.gif").n_frames == 4
