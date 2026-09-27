"""examples/ is rebuilt from its .px sources and must match what's committed, byte for byte.

examples/build.sh regenerates every output (PNG, GIF, JSON, .px, and the text commands
print) with pxart commands. These tests run it into a temp dir with this checkout's
pxart.py, so a pxart change that alters any example fails here. When the change is
intended, run examples/build.sh and commit what it rewrites.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
BUILD = EXAMPLES / "build.sh"

# Hand-written files that build.sh doesn't produce or copy.
NOT_BUILT = {"README.md", "build.sh"}


def committed_files():
    return sorted(
        p.relative_to(EXAMPLES).as_posix()
        for p in EXAMPLES.rglob("*")
        if p.is_file() and p.name not in NOT_BUILT
    )


COMMITTED = committed_files()

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="build.sh needs bash")


def run_build(dest):
    env = dict(os.environ, PYTHON=sys.executable)
    proc = subprocess.run(
        ["bash", str(BUILD), str(dest)], env=env, capture_output=True, text=True, cwd=ROOT
    )
    assert proc.returncode == 0, f"build.sh failed:\n{proc.stdout}\n{proc.stderr}"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    dest = tmp_path_factory.mktemp("examples")
    run_build(dest)
    return dest


def test_examples_exist():
    assert (EXAMPLES / "README.md").is_file()
    assert BUILD.is_file()
    dirs = sorted(p.name for p in EXAMPLES.iterdir() if p.is_dir())
    assert len(dirs) >= 9, dirs
    for d in dirs:
        assert (EXAMPLES / d / "README.md").is_file(), f"{d} has no README.md"


def test_build_writes_nothing_uncommitted(built):
    made = sorted(p.relative_to(built).as_posix() for p in built.rglob("*") if p.is_file())
    extra = sorted(set(made) - set(COMMITTED))
    assert not extra, f"build.sh makes files that aren't committed: {extra}"


def test_every_committed_file_is_built(built):
    missing = [f for f in COMMITTED if not (built / f).is_file()]
    assert not missing, f"committed but not made by build.sh (stale?): {missing}"


@pytest.mark.parametrize("rel", COMMITTED)
def test_output_is_byte_identical(built, rel):
    got = (built / rel).read_bytes()
    want = (EXAMPLES / rel).read_bytes()
    assert got == want, (
        f"examples/{rel} differs from what build.sh makes now "
        f"({len(want)} bytes committed, {len(got)} built); "
        "if the change is intended, run examples/build.sh and commit"
    )


def test_build_is_deterministic(built, tmp_path):
    """A second build makes the same bytes as the first (no timestamps, no ordering luck)."""
    run_build(tmp_path)
    for p in built.rglob("*"):
        if p.is_file():
            rel = p.relative_to(built)
            assert (tmp_path / rel).read_bytes() == p.read_bytes(), f"{rel} differs between builds"


def test_readme_images_exist():
    """Every image a README shows is a committed file."""
    for readme in EXAMPLES.rglob("README.md"):
        for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme.read_text()):
            assert (readme.parent / target).is_file(), f"{readme}: {target} is missing"


def test_readme_links_exist():
    """Every relative link in the examples' READMEs points at a file or folder that exists."""
    for readme in EXAMPLES.rglob("README.md"):
        for target in re.findall(r"\]\(([^)#]+)\)", readme.read_text()):
            if "://" in target:
                continue
            assert (readme.parent / target).exists(), f"{readme}: {target} is missing"
