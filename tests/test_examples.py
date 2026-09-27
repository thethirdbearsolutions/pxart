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
# Scratch a reader leaves behind (a browser preview of a rendered page), never committed.
SCRATCH = ("_preview.html",)


def tracked_files():
    """examples/'s git-tracked files, or None when git (or the repository) isn't there."""
    try:
        proc = subprocess.run(["git", "ls-files", "-z", "--", "."], cwd=EXAMPLES, capture_output=True, text=True)
    except OSError:
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    return [EXAMPLES / rel for rel in proc.stdout.split("\0") if rel]


def committed_files():
    """The files build.sh must make: examples/'s tracked files (every file under it without git), less the
    hand-written ones and scratch."""
    found = tracked_files()
    if found is None:
        found = EXAMPLES.rglob("*")
    return sorted(
        p.relative_to(EXAMPLES).as_posix()
        for p in found
        if p.is_file() and p.name not in NOT_BUILT and not p.name.endswith(SCRATCH)
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


def test_untracked_files_are_not_expected(tmp_path):
    """A file git doesn't track (a reader's _preview.html, a stray render) isn't one build.sh must make."""
    if tracked_files() is None:
        pytest.skip("no git")
    stray = [EXAMPLES / "01-format" / "_stray.txt", EXAMPLES / "02-animation" / "walk_preview.html"]
    try:
        for p in stray:
            p.write_text("scratch\n")
        got = committed_files()
    finally:
        for p in stray:
            p.unlink()
    assert "01-format/_stray.txt" not in got and "02-animation/walk_preview.html" not in got
    assert got == COMMITTED


def test_scratch_is_ignored_without_git(monkeypatch):
    """With no git, every file under examples/ counts, except scratch previews."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no git")))
    assert tracked_files() is None
    got = committed_files()
    assert not any(rel.endswith("_preview.html") for rel in got)
    assert set(COMMITTED) <= set(got)


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


def fenced_blocks(text):
    """(info string, lines) for each ``` block of a Markdown file."""
    return [
        (m.group(1).strip(), m.group(2).splitlines())
        for m in re.finditer(r"^```([^\n]*)\n(.*?)^```", text, flags=re.S | re.M)
    ]


EXAMPLE_READMES = sorted(EXAMPLES.glob("*/README.md")) + [EXAMPLES / "README.md"]


@pytest.mark.parametrize("path", EXAMPLE_READMES + [BUILD], ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_unbraced_variable_before_a_colon(path):
    """zsh reads "$H:cobble" as $H with a :c modifier; the commands must say "${H}:cobble"."""
    text = path.read_text()
    chunks = [text] if path == BUILD else ["\n".join(lines) for _, lines in fenced_blocks(text)]
    for chunk in chunks:
        bad = re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*:", chunk)
        assert not bad, f"{path.relative_to(ROOT)}: write ${{NAME}}: in zsh-safe form, not {bad}"


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*/README.md")), ids=lambda p: p.parent.name)
def test_quoted_output_appears_verbatim(path):
    """Every line of a ```text block is a line of one of the example's committed .txt files.

    A line ending in '...' only has to start one; a line that is just '...' marks a cut.
    """
    lines = set()
    here = path.parent.name + "/"
    for txt in (EXAMPLES / rel for rel in COMMITTED if rel.startswith(here) and rel.endswith(".txt")):
        lines.update(line.rstrip() for line in txt.read_text().splitlines())
    blocks = [block for info, block in fenced_blocks(path.read_text()) if info == "text"]
    for block in blocks:
        for line in block:
            line = line.rstrip()
            if not line or line.strip() == "...":
                continue
            if line.endswith("..."):
                prefix = line[:-3].rstrip()
                assert any(have.startswith(prefix) for have in lines), (
                    f"{path.parent.name}/README.md quotes output no .txt starts with: {prefix!r}"
                )
            else:
                assert line in lines, (
                    f"{path.parent.name}/README.md quotes output no .txt has: {line!r}"
                )
