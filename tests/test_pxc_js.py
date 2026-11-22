"""bench/cast/web/pxc.js gunzips a cast by its bytes, not its URL (PX-29): bench/cast/web/pxc.test.mjs under node --test.
A cache-busting query (cast.pxc.gz?r=2) still gunzips, and a .gz a server already decoded isn't gunzipped twice. Needs
node; without it the test skips, except under CI (CI set), where it fails."""
import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


def test_fetch_cast_gunzips_by_content():
    if not NODE:
        if os.environ.get("CI"):
            pytest.fail("node isn't installed: CI must run this test")
        pytest.skip("node isn't installed")
    proc = subprocess.run([NODE, "--test", "--test-reporter=tap", "bench/cast/web/pxc.test.mjs"], cwd=ROOT,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-2000:]
    assert "# pass 5" in proc.stdout
