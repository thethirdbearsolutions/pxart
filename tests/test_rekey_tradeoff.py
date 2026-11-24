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
                    "stay (a key-for-key copy) and take tiles.px's variant colors")
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


# ---------------------------------------------------------------- the PR #13 review's findings


def test_review_1_2_punctuation_or_many_keys_give_bare_rekey(tmp_path, monkeypatch, capsys):
    """A list with ',' '=' or '*' can't be run as written (--rekey splits on commas; a shell globs '*'), and more than six
    keys used to print a literal KEYS: both now offer plain --rekey, which every WARNING's key goes with."""
    monkeypatch.chdir(tmp_path)
    keys = "LE,*+="
    pal = "".join(f"{k} #{i:02x}3a44\n" for i, k in enumerate(keys, 16))
    night = "@variant night\n" + "".join(f"{k} #{i:02x}0000\n" for i, k in enumerate(keys, 16))
    (tmp_path / "d.px").write_text(pal + night + "\n@frame b\n......\n")
    (tmp_path / "s.px").write_text(pal + "\n" + keys + "\n")
    assert run("paste", "s.px", "--into", "d.px:b", "--at", "0,0") == 0
    note = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("note: paste --rekey"))
    assert note.startswith("note: paste --rekey would give those pixels new letters in d.px")
    many = "abcdefg"
    pal = "".join(f"{k} #{i:02x}3a44\n" for i, k in enumerate(many, 16))
    night = "@variant night\n" + "".join(f"{k} #{i:02x}0000\n" for i, k in enumerate(many, 16))
    (tmp_path / "d2.px").write_text(pal + night + "\n@frame b\n.......\n")
    (tmp_path / "s2.px").write_text(pal + "\n" + many + "\n")
    assert run("paste", "s2.px", "--into", "d2.px:b", "--at", "0,0") == 0
    out = capsys.readouterr().out
    assert "note: paste --rekey would give those pixels new letters in d2.px" in out and "KEYS" not in out


def test_review_3_after_a_partial_rekey_the_note_says_add(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    assert run("paste", "quarter.px", "--into", "tiles.px:b", "--at", "0,0", "--rekey", "D,F") == 0
    out = capsys.readouterr().out
    assert ("note: adding E,L to --rekey would give those pixels new letters too in tiles.px; left off, the keys stay "
            "(a key-for-key copy) and take tiles.px's variant colors") in out


# ---------------------------------------------------------------- compose and crop into an existing file (PX-49)


def test_compose_into_an_existing_file_says_what_rekey_would_change(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    assert run("compose", "-o", "tiles.px:c", "quarter.px@0,0") == 0
    lines = capsys.readouterr().out.splitlines()
    warns = [l for l in lines if l.startswith("WARNING")]
    assert len(warns) == 4 and all(" compose --rekey " in w and w.endswith("gives it a key of its own") for w in warns)
    note = ("note: compose --rekey D,E,F,L would give those pixels new letters in tiles.px; left off, the keys stay (a "
            "key-for-key copy) and take tiles.px's variant colors")
    assert note in lines and lines.index(note) == lines.index(warns[-1]) + 1
    assert pxart.parse(tmp_path / "tiles.px").get("c").grid[:2] == ["LE..", "FD.."]  # keys kept


def test_crop_into_an_existing_file_says_it_too(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    assert run("crop", "quarter.px", "0,0,2,1", "-o", "tiles.px:d") == 0
    lines = capsys.readouterr().out.splitlines()
    warns = [l for l in lines if l.startswith("WARNING")]
    note = next(l for l in lines if l.startswith("note: crop --rekey "))
    assert lines.index(note) == lines.index(warns[-1]) + 1
    assert note.endswith(" would give those pixels new letters in tiles.px; left off, the keys stay (a key-for-key "
                         "copy) and take tiles.px's variant colors")
    assert {"E", "L"} <= set(note.split()[3].split(","))  # the cropped LE (crop's WARNINGs name D and F too: PX-58)


def test_compose_after_a_partial_rekey_says_add(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    assert run("compose", "-o", "tiles.px:c", "quarter.px@0,0", "--rekey", "D,F") == 0
    assert ("note: adding E,L to --rekey would give those pixels new letters too in tiles.px"
            in capsys.readouterr().out)


def test_compose_with_rekey_or_into_a_new_file_has_no_note(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    assert run("compose", "-o", "tiles.px:c", "quarter.px@0,0", "--rekey") == 0
    assert "would give those pixels new letters" not in capsys.readouterr().out
    assert run("compose", "-o", "fresh.px", "quarter.px@0,0", "tiles.px:a@0,0") == 0
    assert "would give those pixels new letters" not in capsys.readouterr().out


def test_several_layers_of_one_file_draw(tmp_path, monkeypatch, capsys):  # PX-49 loop: "layers 1-2 (...) draws"
    setup(tmp_path, monkeypatch)
    assert run("compose", "-o", "tiles.px:c", "quarter.px@0,0", "quarter.px@2,2") == 0
    out = capsys.readouterr().out
    assert "WARNING: layers 1-2 (quarter.px) draw 'D'" in out and "draws 'D'" not in out
