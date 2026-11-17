"""The axes scenario (make_axes.py, built by build_axes.py) in Chromium: each option loads the cast
in one combination, draws it, switches to another and draws that, N cold-cache runs per profile.
One JSON line per run, with the load bench's profiles and per-run measures (bench/load/bench.py).

    python3 bench/cast/bench_axes.py WORK_DIR CERT_DIR [--scenario axes/s300ax] [--runs 3] [--profiles ...]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "load"))
from bench import PROFILES, run_page, start_server  # noqa: E402

OPTIONS = ("sheets", "recolour", "px", "pxc")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("work", type=Path)
    ap.add_argument("certs", type=Path)
    ap.add_argument("--scenario", default="axes/s300ax")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--profiles", default=",".join(PROFILES))
    ap.add_argument("--options", default=",".join(OPTIONS))
    a = ap.parse_args()
    server, port = start_server(a.work, a.certs)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--enable-precise-memory-info"])
            print(json.dumps({"browser": browser.version}), flush=True)
            for name in a.profiles.split(","):
                for opt in a.options.split(","):
                    for run in range(a.runs):
                        t = time.time()
                        r = run_page(browser, pw, PROFILES[name], f"https://localhost:{port}/pxc/axes.html?sc={a.scenario}&opt={opt}&cpu={PROFILES[name]['cpu']}")
                        print(json.dumps({"profile": name, "run": run, "wall": round(time.time() - t, 2), **r}), flush=True)
            browser.close()
    finally:
        server.terminate()


if __name__ == "__main__":
    main()
