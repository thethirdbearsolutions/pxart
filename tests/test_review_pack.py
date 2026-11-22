"""review-pack: renders handed to a reviewer blind, under random ids, with copies to see whether verdicts hold (PX-5).
Two lessons from judging art with model reviewers: a folder name can leak the answer, and one reviewer can change its
verdict on identical frames."""
import json
import pathlib
import sys

import pytest
from PIL import Image, PngImagePlugin

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402


ERR = []  # the error line of the last run that failed, as sys.exit would print it


def run(*argv):
    ERR.clear()
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        if isinstance(e.code, int):
            return e.code
        ERR.append(str(e.code))
        return 1
    return 0


def err():
    return ERR[0] if ERR else ""


def png(path, color, size=(4, 4), text=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    info = None
    if text:
        info = PngImagePlugin.PngInfo()
        info.add_text("Comment", text)
    Image.new("RGBA", size, color).save(path, pnginfo=info)
    return path


@pytest.fixture
def renders(tmp_path, monkeypatch):
    """Two 'eras' of the same sprites, as an origin comparison has them: the era is only in the folder name."""
    monkeypatch.chdir(tmp_path)
    png(tmp_path / "era-old" / "fox.png", (200, 80, 20, 255), text="era-old fox, drawn by method A")
    png(tmp_path / "era-old" / "owl.png", (90, 60, 40, 255))
    png(tmp_path / "era-new" / "fox.png", (210, 90, 30, 255), size=(4, 5))
    return tmp_path


def manifest(tmp_path, name="pack"):
    return json.loads((tmp_path / f"{name}.manifest.json").read_text())


def test_pack_hides_every_name(renders, capsys):
    assert run("review-pack", "era-old", "era-new", "-o", "pack", "--seed", "1") == 0
    out = capsys.readouterr().out
    assert "wrote pack/: 3 item(s), 3 render(s), each as <id>/image.png" in out
    files = sorted(p.relative_to(renders / "pack").as_posix() for p in (renders / "pack").rglob("*") if p.is_file())
    assert len(files) == 3 and all(f.endswith("/image.png") for f in files)
    for f in files:  # nothing of a source's path or name in the reviewer's paths
        assert not any(w in f for w in ("era", "old", "new", "fox", "owl"))
        assert len(f.split("/")[0]) == 12 and int(f.split("/")[0], 16) >= 0
    assert not any(p.suffix == ".json" for p in (renders / "pack").rglob("*"))  # the map isn't in the pack
    m = manifest(renders)
    assert m["pxart_review_pack"] == 1 and m["copies"] == 1
    assert sorted(it["source"] for it in m["items"].values()) == ["era-new/fox.png", "era-old/fox.png",
                                                                  "era-old/owl.png"]


def test_pixels_kept_and_metadata_dropped(renders):
    assert run("review-pack", "era-old/fox.png", "-o", "pack", "--seed", "1") == 0
    (h, it), = manifest(renders)["items"].items()
    img = Image.open(renders / "pack" / h / "image.png")
    assert "Comment" not in img.info and not any("era" in str(v) for v in img.info.values())
    src = Image.open(renders / "era-old" / "fox.png").convert("RGBA")
    assert img.convert("RGBA").tobytes() == src.tobytes() and img.size == src.size


def test_copies_get_different_ids(renders):
    assert run("review-pack", "era-old", "-o", "pack", "--copies", "2", "--seed", "4") == 0
    items = manifest(renders)["items"]
    assert len(items) == 4 and len(set(items)) == 4
    by_src = {}
    for h, it in items.items():
        by_src.setdefault(it["source"], []).append(it["copy"])
    assert {k: sorted(v) for k, v in by_src.items()} == {"era-old/fox.png": [1, 2], "era-old/owl.png": [1, 2]}


def test_seed_repeats_and_no_seed_varies(renders, tmp_path):
    assert run("review-pack", "era-old", "-o", "a", "--seed", "7") == 0
    assert run("review-pack", "era-old", "-o", "b", "--seed", "7") == 0
    assert run("review-pack", "era-old", "-o", "c") == 0
    a, b, c = (set(manifest(renders, n)["items"]) for n in "abc")
    assert a == b and a != c


def test_ids_do_not_follow_source_order(renders):
    """The ids are random, so a listing of the pack (sorted by id) doesn't put the renders in the order given."""
    for i in range(6):
        png(renders / "many" / f"{i:02d}.png", (i * 30, 0, 0, 255))
    orders = set()
    for seed in range(5):
        assert run("review-pack", "many", "-o", f"p{seed}", "--seed", seed) == 0
        items = manifest(renders, f"p{seed}")["items"]
        orders.add(tuple(items[h]["source"] for h in sorted(items)))
    assert len(orders) > 1


def test_score_agreement_and_disagreement(renders, capsys):
    assert run("review-pack", "era-old", "era-new", "-o", "pack", "--copies", "2", "--seed", "2") == 0
    items = manifest(renders)["items"]
    # the reviewer flips on the old owl's second copy, and leaves the new fox's second copy unjudged
    verdicts = {}
    for h, it in items.items():
        if it["source"] == "era-new/fox.png" and it["copy"] == 2:
            continue
        flip = it["source"] == "era-old/owl.png" and it["copy"] == 2
        verdicts[f"{h}/image.png"] = "fail" if flip else "pass"
    verdicts["not-an-id"] = "pass"
    (renders / "v.json").write_text(json.dumps(verdicts))
    capsys.readouterr()
    assert run("review-pack", "--score", "pack", "v.json") == 0
    out = capsys.readouterr().out
    assert 'era-old/fox.png: "pass" (2 copies agree)' in out
    assert "era-old/owl.png: copies DISAGREE: " in out
    assert 'era-new/fox.png: "pass" (1 of 2 copies judged)' in out
    assert "agreement: 1 of 2 render(s) judged in 2+ copies (50%); 1 disagree" in out
    assert "note: 1 of 6 item(s) have no verdict" in out
    assert "note: 1 verdict key(s) name no item of pack: not-an-id" in out
    lines = [l.split(":")[0] for l in out.splitlines() if l.startswith("era-")]
    assert lines == sorted(lines)  # by render, not by id


def test_score_takes_a_list_and_structured_verdicts(renders, capsys):
    assert run("review-pack", "era-old/owl.png", "-o", "pack", "--copies", "2", "--seed", "3") == 0
    ids = sorted(manifest(renders)["items"])
    (renders / "v.json").write_text(json.dumps([{"id": i, "verdict": {"score": 3, "ok": True}} for i in ids]))
    capsys.readouterr()
    assert run("review-pack", "--score", "pack", "v.json") == 0
    out = capsys.readouterr().out
    assert 'era-old/owl.png: {"ok": true, "score": 3} (2 copies agree)' in out
    assert "agreement: 1 of 1 render(s) judged in 2+ copies (100%)" in out


def test_manifest_elsewhere(renders, capsys):
    assert run("review-pack", "era-old", "-o", "pack", "--manifest", "private/m.json") == 0
    assert (renders / "private" / "m.json").exists() and not (renders / "pack.manifest.json").exists()
    ids = json.loads((renders / "private" / "m.json").read_text())["items"]
    (renders / "v.json").write_text(json.dumps({i: 1 for i in ids}))
    assert run("review-pack", "--score", "pack", "v.json") == 1
    assert "no manifest for pack" in err()
    assert run("review-pack", "--score", "pack", "v.json", "--manifest", "private/m.json") == 0


@pytest.mark.parametrize("argv, msg", [
    (["era-old", "-o", "pack", "--manifest", "pack/m.json"], "inside -o pack"),
    (["era-old", "-o", "era-new"], "already has files in it"),
    (["era-old"], "-o DIR is required"),
    (["-o", "pack"], "give the renders to pack"),
    (["era-old", "-o", "pack", "--copies", "0"], "--copies 0"),
    (["missing.png", "-o", "pack"], "E_FILE"),
])
def test_refusals(renders, capsys, argv, msg):
    assert run("review-pack", *argv) == 1
    assert msg in err()
    assert not (renders / "pack").exists() or not any((renders / "pack").iterdir())


def test_a_px_is_refused_with_the_render_to_run(renders, capsys):
    (renders / "s.px").write_text("k #000000\nk\n")
    assert run("review-pack", "s.px", "-o", "pack") == 1
    assert "render it first ('pxart render s.px -o s.png'" in err()


def test_a_png_given_twice_goes_in_once(renders, capsys):
    assert run("review-pack", "era-old", "era-old/fox.png", "-o", "pack") == 0
    assert "note: era-old/fox.png is given twice" in capsys.readouterr().out
    assert len(manifest(renders)["items"]) == 2


def test_dry_run_writes_nothing(renders, capsys):
    assert run("review-pack", "era-old", "-o", "pack", "--dry-run") == 0
    assert "(dry run; nothing written)" in capsys.readouterr().out
    assert not (renders / "pack").exists() and not (renders / "pack.manifest.json").exists()


def test_score_bad_verdicts(renders, capsys):
    assert run("review-pack", "era-old", "-o", "pack", "--seed", "5") == 0
    h = sorted(manifest(renders)["items"])[0]
    (renders / "v.json").write_text("{not json")
    assert run("review-pack", "--score", "pack", "v.json") == 1
    assert "not JSON" in err()
    (renders / "v.json").write_text(json.dumps({h: "a", f"{h}/image.png": "b"}))
    assert run("review-pack", "--score", "pack", "v.json") == 1
    assert "two verdicts" in err()
