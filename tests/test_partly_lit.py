"""check names the keys a file's own @variant night leaves at base when its @palette's night can't know them either
(PX-71): a night written for a few keys (compose/crop write one for a lamp) says nothing of the walls, which stay
day-bright while the rest of the room goes dark."""
import pathlib
import shlex
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

PAL = "k #3f2631\ng #40a040\n\n@variant night\nk #1a1020\ng #183020\n"
A = "@palette pal.px\nW #c0b090\n\nkWg\n"
B = "@palette pal.px\nW #c0b090\nm #ffd070\n\n@variant night\nm #ffe090\n\nkWmg\n"


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def files(tmp_path, **more):
    (tmp_path / "pal.px").write_text(PAL)
    for name, text in more.items():
        (tmp_path / f"{name}.px").write_text(text)
    return tmp_path


def test_a_local_night_for_one_key_leaves_the_others_named(tmp_path, capsys):
    files(tmp_path, b=B)
    run("check", tmp_path / "b.px")
    out = capsys.readouterr().out
    assert "neither gives key W a night color" in out
    assert "--add 'm=#ffe090'" in out


def test_the_printed_fix_runs_and_keeps_the_lamp(tmp_path, capsys):
    files(tmp_path, b=B)
    run("check", tmp_path / "b.px")
    out = capsys.readouterr().out
    cmd = out.split("run: ", 1)[1].split(" (add any", 1)[0]
    assert run(*shlex.split(cmd)[1:]) == 0
    capsys.readouterr()
    doc = pxart.parse(tmp_path / "b.px")
    night = doc.resolved("night")
    assert night["m"] == pxart.parse_color("#ffe090") and night["W"] != doc.resolved()["W"]
    run("check", tmp_path / "b.px")
    assert "neither gives" not in capsys.readouterr().out


def test_a_night_listing_every_drawn_key_is_silent(tmp_path, capsys):
    files(tmp_path, b=B.replace("m #ffe090\n", "m #ffe090\nW #403020\n"))
    run("check", tmp_path / "b.px")
    assert "neither gives" not in capsys.readouterr().out


def test_a_key_relisted_in_its_base_color_is_kept_lit_not_named(tmp_path, capsys):
    files(tmp_path, b=B.replace("m #ffe090\n", "m #ffe090\nW #c0b090\n"))
    run("check", tmp_path / "b.px")
    assert "neither gives" not in capsys.readouterr().out


def test_a_relisted_key_goes_to_keep_lit_in_the_fix(tmp_path, capsys):
    files(tmp_path, b=B.replace("m #ffe090\n", "m #ffd070\n").replace("kWmg", "kWmgT").replace(
        "m #ffd070\n\n@variant", "m #ffd070\nT #806040\n\n@variant"))
    run("check", tmp_path / "b.px")
    out = capsys.readouterr().out
    assert "--keep-lit m" in out and "neither gives keys W T" in out


def test_the_import_only_case_is_unchanged(tmp_path, capsys):
    files(tmp_path, a=A)
    run("check", tmp_path / "a.px")
    out = capsys.readouterr().out
    assert "comes only from its @palette" in out and "neither gives" not in out


def test_a_file_without_an_import_is_left_alone(tmp_path, capsys):
    # a night of its own that leaves a lamp out on purpose: the convention lit_keys reads as a light
    (tmp_path / "c.px").write_text("k #3f2631\nL #ffd070\n\n@variant night\nk #1a1020\n\nkL\n")
    run("check", tmp_path / "c.px")
    assert "neither gives" not in capsys.readouterr().out
