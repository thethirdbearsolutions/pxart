"""put --rows repairs a frame whose rows are the wrong width, and --text gives rows without stdin."""
import subprocess
import sys
from pathlib import Path

PXART = Path(__file__).resolve().parent.parent / "pxart.py"
SRC = "pxart 1\nk #000000\no #ff8800\n\n@frame a\n..kk..\n.koook.\n.kook.\n..kk..\n\n@frame b\n.kkkk.\n.kook.\n.kook.\n.kkkk.\n"


def run(tmp, *argv):
    p = subprocess.run([sys.executable, str(PXART), *argv], cwd=tmp, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout + p.stderr


def test_check_names_the_repair(tmp_path):
    (tmp_path / "f.px").write_text(SRC)
    code, out = run(tmp_path, "check", "f.px")
    assert code != 0 and "put FILE:a --rows 1 --text ROW" in out


def test_rows_repairs_ragged_frame(tmp_path):
    (tmp_path / "f.px").write_text(SRC)
    code, out = run(tmp_path, "put", "f.px:a", "--rows", "1", "--text", ".kook.")
    assert code == 0, out
    assert run(tmp_path, "check", "f.px")[0] == 0
    assert "@frame b\n.kkkk.\n.kook.\n.kook.\n.kkkk.\n" in (tmp_path / "f.px").read_text()


def test_rows_refuses_a_partial_repair(tmp_path):
    src = SRC.replace("..kk..\n\n@frame b", "..kk...\n\n@frame b")  # rows 1 and 3 off
    (tmp_path / "f.px").write_text(src)
    code, out = run(tmp_path, "put", "f.px:a", "--rows", "1", "--text", ".kook.")
    assert code != 0 and "row(s) 3" in out and "nothing written" in out
    assert (tmp_path / "f.px").read_text() == src


def test_text_rows_wrong_width_name_text(tmp_path):
    (tmp_path / "f.px").write_text(SRC)
    code, out = run(tmp_path, "put", "f.px:a", "--rows", "1", "--text", ".koo.")
    assert code != 0 and "--text has 1 of 5" in out


def _unused_other_frames_still_checked(tmp_path):
    (tmp_path / "f.px").write_text(SRC.replace(".kkkk.\n.kook.\n.kook.\n.kkkk.", ".kkkk.\n.kook.\n.koook.\n.kkkk."))
    code, out = run(tmp_path, "put", "f.px:a", "--rows", "1", "--text", ".kook.")
    assert code != 0 and "frame b" in out


def test_text_replaces_whole_frame(tmp_path):
    (tmp_path / "f.px").write_text(SRC.replace(".koook.", ".kook."))
    code, out = run(tmp_path, "put", "f.px:b", "--text", "kk", "--text", "oo")
    assert code == 0, out
    assert "@frame b\nkk\noo\n" in (tmp_path / "f.px").read_text()


def test_at_on_ragged_frame_still_refused(tmp_path):
    (tmp_path / "f.px").write_text(SRC)
    code, out = run(tmp_path, "put", "f.px:a", "--at", "0,0", "--text", "k")
    assert code != 0 and "E_ROW_WIDTH" in out


def test_rows_edits_a_frame_while_another_is_ragged(tmp_path):
    (tmp_path / "f.px").write_text(SRC)  # frame a is ragged; edit b
    code, out = run(tmp_path, "put", "f.px:b", "--rows", "0", "--text", "kkkkkk")
    assert code == 0, out
    assert "note: a still has rows of the wrong width" in out
    text = (tmp_path / "f.px").read_text()
    assert "@frame b\nkkkkkk\n" in text and ".koook." in text  # a's rows kept as typed


TIE = "pxart 1\nk #000000\no #ff8800\n\n@frame a\n.kook..\n.kook..\n.kook.\n.kook.\n"


def test_rows_covering_the_frame_set_any_width(tmp_path):
    (tmp_path / "t.px").write_text(TIE)
    code, out = run(tmp_path, "put", "t.px:a", "--rows", "0-3", *sum((["--text", ".kook."] for _ in range(4)), []))
    assert code == 0, out
    assert run(tmp_path, "check", "t.px")[0] == 0


def test_whole_frame_put_replaces_a_ragged_frame(tmp_path):
    (tmp_path / "t.px").write_text(TIE)
    code, out = run(tmp_path, "put", "t.px:a", "--text", "kk", "--text", "oo")
    assert code == 0, out
    assert run(tmp_path, "check", "t.px")[0] == 0


def test_count_includes_added_pixels(tmp_path):
    (tmp_path / "t.px").write_text(TIE)
    code, out = run(tmp_path, "put", "t.px:a", "--rows", "2-3", "--text", ".kook..", "--text", ".kook..")
    assert code == 0 and "changed 2 px" in out, out


def test_no_repair_hint_on_input_rows(tmp_path):
    (tmp_path / "f.px").write_text(SRC.replace(".koook.", ".kook."))
    code, out = run(tmp_path, "put", "f.px:a", "--text", "..", "--text", "kkk")
    assert code != 0 and "E_ROW_WIDTH" in out and "retype it" not in out
