"""The argv shapes an author (often an LLM without the reference open) guesses first: dup FILE:a FILE:b,
shift FILE DX DY, set FILE x,y KEY. Each does what was meant, or says the right shape. And a typed row one
char off says where."""

import pytest

import pxart
from test_pxart import run, run_err, write

GRID = """pxart 1
k #000000
o #ff8800

@frame idle/down/0
..kkkk..
.kooook.
.kooook.
..kkkk..
"""


def frame(path, fid):
    return pxart.parse(path).get(fid).grid


def test_dup_takes_newid_written_as_the_same_file_selector(tmp_path):
    p = write(tmp_path, "f.px", GRID)
    assert run("dup", f"{p}:idle/down/0", f"{p}:idle/down/1") == 0
    assert frame(p, "idle/down/1") == frame(p, "idle/down/0")


def test_dup_refuses_another_files_selector_and_says_how(tmp_path):
    p = write(tmp_path, "f.px", GRID)
    g = write(tmp_path, "g.px", GRID)
    msg = run_err("dup", f"{p}:idle/down/0", f"{g}:idle/down/1")
    assert "E_BAD_ARG" in msg and "compose -o" in msg
    assert pxart.parse(p).get("idle/down/1") is None


@pytest.mark.parametrize("delta,flags", [(["0", "1"], ["--dy", "1"]), (["-1", "0"], ["--dx", "-1"])])
def test_shift_takes_positional_dx_dy_as_the_flags(tmp_path, delta, flags):
    a = write(tmp_path, "a.px", GRID)
    b = write(tmp_path, "b.px", GRID)
    assert run("shift", f"{a}:idle/down/0", *delta) == 0
    assert run("shift", f"{b}:idle/down/0", *flags) == 0
    assert frame(a, "idle/down/0") == frame(b, "idle/down/0") != frame(write(tmp_path, "c.px", GRID), "idle/down/0")


def test_shift_positional_and_flags_together_is_refused(tmp_path):
    p = write(tmp_path, "f.px", GRID)
    assert "not both" in run_err("shift", f"{p}:idle/down/0", "0", "1", "--dx", "2")
    assert "two whole numbers" in run_err("shift", f"{p}:idle/down/0", "1")


def test_set_reads_the_key_written_last(tmp_path, capsys):
    p = write(tmp_path, "f.px", GRID)
    assert run("set", f"{p}:idle/down/0", "2,1", "3,1", "k") == 0
    assert frame(p, "idle/down/0")[1] == ".kkkook."
    assert "set takes the key first" in capsys.readouterr().out


def test_set_with_a_point_for_its_key_says_the_order(tmp_path):
    p = write(tmp_path, "f.px", GRID)
    msg = run_err("set", f"{p}:idle/down/0", "2,1", "q")  # 'q' isn't a key: no swap to make
    assert "the key comes first" in msg and "not in palette" not in msg


@pytest.mark.parametrize("row,hint", [
    (".koooook.", "one too many: deleting the 'o' at x=2"),
    (".koook.", "one short: adding 'o' at x=2"),
])
def test_row_one_off_names_the_fix(tmp_path, row, hint):
    p = write(tmp_path, "f.px", GRID.replace(".kooook.\n..kkkk..", row + "\n..kkkk..", 1))
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p)
    assert any(i.code == "E_ROW_WIDTH" and hint in i.msg for i in e.value.issues), [str(i) for i in e.value.issues]


def test_row_further_off_has_no_guess(tmp_path):
    p = write(tmp_path, "f.px", GRID.replace(".kooook.\n..kkkk..", ".koooooooook.\n..kkkk..", 1))
    with pytest.raises(pxart.PxError) as e:
        pxart.parse(p)
    msgs = [i.msg for i in e.value.issues if i.code == "E_ROW_WIDTH"]
    assert msgs and not any("one too many" in m or "one short" in m for m in msgs)


def test_shift_takes_a_comma_pair(tmp_path):
    a = write(tmp_path, "a.px", GRID)
    b = write(tmp_path, "b.px", GRID)
    assert run("shift", f"{a}:idle/down/0", "0,-1") == 0
    assert run("shift", f"{b}:idle/down/0", "--dy", "-1") == 0
    assert frame(a, "idle/down/0") == frame(b, "idle/down/0")


def test_set_reads_separate_numbers_for_points(tmp_path, capsys):
    p = write(tmp_path, "f.px", GRID)
    assert run("set", f"{p}:idle/down/0", "2", "1", "3", "1", "k") == 0
    assert frame(p, "idle/down/0")[1] == ".kkkook."
    assert "points as x,y" in capsys.readouterr().out


def test_dup_takes_the_new_id_from_o_of_the_same_file(tmp_path):
    p = write(tmp_path, "f.px", GRID)
    assert run("dup", f"{p}:idle/down/0", "-o", f"{p}:idle/down/1") == 0
    assert frame(p, "idle/down/1") == frame(p, "idle/down/0")


def test_dup_without_a_new_id_says_so(tmp_path):
    p = write(tmp_path, "f.px", GRID)
    assert "needs the new frame's id" in run_err("dup", f"{p}:idle/down/0")
