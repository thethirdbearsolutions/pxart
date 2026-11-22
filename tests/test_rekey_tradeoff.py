"""paste and frames --copy-to: the variant WARNINGs offer --rekey, and a note says what it would change (PX-35). An agent
pasting quarters of tiles key for key got five WARNINGs whose --rekey advice would have renamed stand-in keys a game's
fill code reads by letter."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402

PAL = "L #3a7d44\nE #2b5f8a\nF #c2b280\nD #1e3d2a\nS #8fd3ff\n"
NIGHT = "@variant night\nL #1a3d24\nE #10203a\nF #605840\nD #0f1e15\nS #4060a0\n"
TILES = "@palette pal.px\n@still *\n\n@frame a\nLLLL\nLEEL\nFDDF\nSSSS\n@frame b\n....\n....\n....\n....\n"


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pal.px").write_text(PAL + NIGHT)
    (tmp_path / "tiles.px").write_text(TILES)
    (tmp_path / "quarter.px").write_text(PAL + "\nLE\nFD\n")  # stand-in keys, no night of its own


def test_shared_palette_pastes_without_a_word(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    assert run("paste", "tiles.px:a", "--region", "0,0,2,2", "--into", "tiles.px:b", "--at", "2,2") == 0
    out = capsys.readouterr().out
    assert "WARNING" not in out and "--rekey" not in out


def test_paste_says_what_rekey_would_change(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    assert run("paste", "quarter.px", "--into", "tiles.px:b", "--at", "0,0") == 0
    lines = capsys.readouterr().out.splitlines()
    warns = [l for l in lines if l.startswith("WARNING")]
    assert len(warns) == 4 and all(w.endswith("gives it a key of its own") for w in warns)
    note = next(l for l in lines if l.startswith("note: paste --rekey"))
    assert note == ("note: paste --rekey D,E,F,L would give those pixels new letters in tiles.px; left off, the keys "
                    "stay (a key-for-key copy) and take its variant colors")
    assert lines.index(note) == lines.index(warns[-1]) + 1  # right after the WARNINGs it explains
    assert pxart.parse(tmp_path / "tiles.px").frames[1].grid == ["LE..", "FD..", "....", "...."]  # keys kept


def test_paste_with_rekey_has_no_tradeoff_note(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    assert run("paste", "quarter.px", "--into", "tiles.px:b", "--at", "0,0", "--rekey") == 0
    assert "would give those pixels new letters" not in capsys.readouterr().out


def test_copy_to_says_it_too(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    (tmp_path / "more.px").write_text(PAL + "\n@still *\n\n@frame c\nLE\nFD\n")
    assert run("frames", "more.px", "--copy-to", "tiles.px") == 0
    out = capsys.readouterr().out
    assert "note: frames --copy-to --rekey D,E,F,L would give those pixels new letters in tiles.px" in out
