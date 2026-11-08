"""The website's data comes from pxart itself and must match what's committed.

site/scripts/gen_reference.py writes site/src/data/reference.json (pxart's help, command by
command) and playground.json (the home page's samples, from `pxart extract`). A change to
pxart's help or to those examples fails here until the data is regenerated:

    python3 site/scripts/gen_reference.py
"""
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "site" / "scripts" / "gen_reference.py"

if not SCRIPT.exists():
    pytest.skip("no site/ in this checkout", allow_module_level=True)


def gen():
    spec = importlib.util.spec_from_file_location("gen_reference", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reference_is_current():
    mod = gen()
    assert mod.OUT.read_text(encoding="utf-8") == mod.render(mod.build()), (
        "site/src/data/reference.json is stale: run python3 site/scripts/gen_reference.py"
    )


def test_playground_is_current():
    mod = gen()
    assert mod.PLAYGROUND.read_text(encoding="utf-8") == mod.render(mod.samples()), (
        "site/src/data/playground.json is stale: run python3 site/scripts/gen_reference.py"
    )


def test_every_command_has_a_page():
    data = json.loads((ROOT / "site" / "src" / "data" / "reference.json").read_text(encoding="utf-8"))
    names = {c["name"] for c in data["commands"]}
    assert names, "no commands in reference.json"
    for c in data["commands"]:
        assert c["summary"], f"{c['name']}: no summary found under its usage line"
        assert c["text"].startswith("usage: pxart " + c["name"]), c["name"]


# ---- the site's .px reader draws what pxart draws ------------------------------------------

import hashlib
import shutil
import subprocess
import sys
import tempfile

NODE = shutil.which("node")
SITE = ROOT / "site"


def pxart_frames(path, variant, out):
    """pxart's own renders of every frame of PATH (in VARIANT), as {frame id: (w, h, sha256 of RGBA)}."""
    from PIL import Image

    cmd = [sys.executable, str(ROOT / "pxart.py"), "export", str(path), "--frames", str(out)]
    if variant:
        cmd += ["--variant", variant]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    frames = {}
    for png in out.rglob("*.png"):
        im = Image.open(png).convert("RGBA")
        data = bytearray(im.tobytes())
        for i in range(0, len(data), 4):  # a transparent pixel is transparent, whatever its RGB
            if data[i + 3] == 0:
                data[i : i + 4] = b"\0\0\0\0"
        frames[png.relative_to(out).with_suffix("").as_posix()] = (im.width, im.height, hashlib.sha256(data).hexdigest())
    return frames


@pytest.mark.skipif(not NODE, reason="node isn't installed")
def test_site_reader_renders_every_example_as_pxart_does():
    """site/src/lib/px.ts draws the docs' sprites and the home page's playground. Every frame of every
    example, in every variant, must come out pixel for pixel as pxart's export --frames draws it."""
    files = sorted(p for p in (ROOT / "examples").rglob("*.px") if p.name != "broken.px")
    proc = subprocess.run([NODE, "scripts/px-renders.ts", *map(str, files)], cwd=SITE, capture_output=True, text=True)
    if proc.returncode != 0 and "Unknown file extension" in proc.stderr:
        pytest.skip("this node can't run TypeScript directly (needs 22.18 or newer)")
    assert proc.returncode == 0, proc.stderr
    ours = json.loads(proc.stdout)
    checked, problems = 0, []
    with tempfile.TemporaryDirectory() as tmp:
        for n, path in enumerate(files):
            got = ours[str(path)]
            assert "error" not in got, f"{path}: {got.get('error')}"
            for variant, frames in got.items():
                if not frames:
                    continue  # a palette file
                want = pxart_frames(path, variant, pathlib.Path(tmp) / f"{n}-{variant or 'base'}")
                for fid, (w, h, digest) in frames.items():
                    key = fid or path.stem
                    rel = f"{path.relative_to(ROOT)}:{key}{'%' + variant if variant else ''}"
                    if key not in want:
                        problems.append(f"{rel}: pxart exported no such frame")
                    elif list(want[key]) != [w, h, digest]:
                        problems.append(f"{rel}: differs from pxart's render ({w}x{h} vs {want[key][0]}x{want[key][1]})")
                    checked += 1
    assert checked > 100, f"only {checked} frames checked"
    assert not problems, f"{len(problems)} of {checked} frames differ:\n" + "\n".join(problems[:40])
