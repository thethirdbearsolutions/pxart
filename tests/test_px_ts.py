"""js/px.ts draws what pxart.py renders, byte for byte.

Every frame of every .px under examples/ (and tests/fixtures/px_ts/, for alpha colors, slot lists
and variants that come through @palette), in the base palette and in each variant, is drawn by px.ts
under node (js/px-dump.ts) and by pxart.py's Doc.image: the same frames in the same order, and
identical RGBA bytes. px.ts doesn't validate, so a file pxart.py refuses (examples/09-check/broken.px)
is left out. Needs node 22.18 or newer, which runs TypeScript as is; without it the test skips,
except under CI (CI set), where it fails.
"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

NODE = shutil.which("node")
REFUSED = {"broken.px"}  # check's worked example: pxart.py reports its errors and draws nothing


def example_files():
    found = [*(ROOT / "examples").rglob("*.px"), *(ROOT / "tests" / "fixtures" / "px_ts").glob("*.px")]
    return sorted(p for p in found if p.name not in REFUSED)


def pxart_renders(path):
    """[((frame id, variant or ''), (w, h, RGBA bytes))], in order, as pxart.py renders them."""
    doc = pxart.parse(path, palette_only=not pxart._has_grid(path))
    out = []
    for variant in ["", *pxart.variant_names(doc)]:
        for f in doc.frames:
            im = doc.image(f, variant or None)
            out.append(((f.id or "", variant), (im.width, im.height, im.tobytes())))
    return out


def skip(reason):
    if os.environ.get("CI"):
        pytest.fail(f"{reason}: CI must run this test")
    pytest.skip(reason)


def test_px_ts_draws_every_example_as_pxart_does():
    if not NODE:
        skip("node isn't installed")
def test_px_ts_draws_every_example_as_pxart_does():
    files = example_files()
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [NODE, str(ROOT / "js" / "px-dump.ts"), tmp, *map(str, files)], capture_output=True, text=True
        )
        if proc.returncode != 0 and "Unknown file extension" in proc.stderr:
            skip("this node can't run TypeScript directly (needs 22.18 or newer)")
        assert proc.returncode == 0, proc.stderr
        index = json.loads((pathlib.Path(tmp) / "index.json").read_text())
        blob = (pathlib.Path(tmp) / "rgba.bin").read_bytes()

    errors = [f"{e['file']}: {e['error']}" for e in index if "error" in e]
    assert not errors, "px.ts couldn't read:\n" + "\n".join(errors)
    ours = {}
    for e in index:
        ours.setdefault(e["file"], []).append(
            ((e["frame"], e["variant"]), (e["w"], e["h"], blob[e["offset"] : e["offset"] + e["w"] * e["h"] * 4]))
        )

    checked, problems = 0, []
    for path in files:
        want_list = pxart_renders(path)
        got_list = ours.get(str(path), [])
        rel = path.relative_to(ROOT).as_posix()
        if [k for k, _ in got_list] != [k for k, _ in want_list]:
            problems.append(f"{rel}: px.ts lists frames x variants {[k for k, _ in got_list][:6]}..., "
                            f"pxart.py {[k for k, _ in want_list][:6]}... (order or count differs)")
        want, got = dict(want_list), dict(got_list)
        for key in sorted(set(want) | set(got)):
            name = f"{rel}:{key[0]}{'%' + key[1] if key[1] else ''}"
            if key not in got:
                problems.append(f"{name}: px.ts has no such frame")
            elif key not in want:
                problems.append(f"{name}: pxart.py has no such frame")
            elif got[key] != want[key]:
                (w, h, a), (W, H, b) = got[key], want[key]
                n = sum(a[i : i + 4] != b[i : i + 4] for i in range(0, len(b), 4)) if (w, h) == (W, H) else None
                problems.append(f"{name}: " + (f"{w}x{h} vs pxart's {W}x{H}" if n is None else f"{n} px differ"))
            checked += 1
    assert checked > 250, f"only {checked} frames x variants checked"
    assert not problems, f"{len(problems)} of {checked} differ:\n" + "\n".join(problems[:40])
