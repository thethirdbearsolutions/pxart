# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=11", "pyoxipng>=9", "brotli>=1.1", "playwright==1.63.0"]
# ///
"""The whole load bench in one command: make the synthetic cast, build every option, optimise the
images, check parity, load every option in Chromium, and summarise.

    uv run bench/load/run.py --out bench/load/results/my-run

Needs node 22.18 or newer (the server, and px.ts with its types stripped), openssl (a localhost
certificate), and a Chromium that Playwright can launch (`uv run --with playwright==1.63.0
playwright install chromium` once, if you have none). Writes to OUT: machine.json, optimize.jsonl,
parity.jsonl, sizes.json, bench.jsonl and bench-summary.md. The work directory (casts and builds,
about 150 MB) is OUT/work unless --work says otherwise; --keep-work reuses its builds.

--runs, --profiles, --scenarios and --options narrow the bench (see bench.py for the profiles).
--options pxc,pxc.gzip,pxc.main (GAMES-443's whole-cast format) builds those options too.
It deletes --work only if that directory is new, empty or one it made.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
MARK = ".pxart-load-bench"  # in a work directory this bench made: the only kind it will delete


def sh(args: list, out: Path | None = None) -> None:
    print("+", " ".join(map(str, args)), flush=True)
    if out is None:
        subprocess.run(args, check=True)
        return
    with open(out, "a") as f:
        subprocess.run(args, check=True, stdout=f)


def machine() -> dict:
    cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")), None) if Path("/proc/cpuinfo").exists() else None
    if cpu is None and platform.system() == "Darwin":
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
    try:
        mem_gb = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    except (ValueError, OSError):
        mem_gb = None
    from importlib.metadata import version

    import PIL
    from PIL import features

    return {
        "os": platform.platform(), "cpu": cpu, "cores": os.cpu_count(), "memory_gb": mem_gb,
        "python": platform.python_version(), "node": subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip(),
        "pillow": PIL.__version__, "libwebp": features.version("webp"), "pyoxipng": version("pyoxipng"),
        "playwright": version("playwright"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the pxart load bench end to end.")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--work", type=Path)
    ap.add_argument("--keep-work", action="store_true", help="reuse the casts, builds and optimised images in --work")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--profiles", default="desktop,desktop-100mbps,desktop-20mbps,desktop-4g,mobile")
    ap.add_argument("--scenarios", default="s300,s300v2,s650v2")
    ap.add_argument("--options", default=None)
    a = ap.parse_args()
    out = a.out.resolve()
    work = (a.work or out / "work").resolve()
    out.mkdir(parents=True, exist_ok=True)
    for name in ("parity.jsonl", "bench.jsonl") if a.keep_work else ("optimize.jsonl", "parity.jsonl", "bench.jsonl"):
        (out / name).unlink(missing_ok=True)
    scenarios = a.scenarios.split(",")
    if a.keep_work:
        missing = [sc for sc in scenarios if not (work / sc / "out-render").is_dir()]
        if missing:
            sys.exit(f"--keep-work: {work} has no builds for {', '.join(missing)}; run without it first")
    else:
        if work.exists() and any(work.iterdir()) and not (work / MARK).exists():
            sys.exit(f"{work} isn't empty and wasn't made by this bench; give --work an empty or new directory")
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        (work / MARK).write_text("made by bench/load/run.py; deleted and rebuilt by it\n")
        sh([PY, HERE / "make_cast.py", work])
        for sc in scenarios:
            sh([PY, HERE / "build.py", work / sc])
            sh([PY, HERE / "optimize.py", work / sc], out / "optimize.jsonl")
    if a.options and "pxc" in a.options:  # GAMES-443's PXC1 options
        for sc in scenarios:
            sh([PY, HERE.parent / "cast" / "build_pxc.py", work / sc])
    certs = work / "certs"
    if not (certs / "cert.pem").exists():
        certs.mkdir(parents=True, exist_ok=True)
        sh(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", certs / "key.pem",
            "-out", certs / "cert.pem", "-days", "30", "-subj", "/CN=localhost"])
    (out / "sizes.json").unlink(missing_ok=True)
    sh([PY, HERE / "sizes.py", work], out / "sizes.json")
    bench = [PY, HERE / "bench.py", work, certs, "--scenarios", a.scenarios]
    sh([*bench, "--parity"], out / "parity.jsonl")
    for line in (out / "parity.jsonl").read_text().splitlines():
        d = json.loads(line)
        if "parity" not in d:
            continue
        if d.get("error"):
            sys.exit(f"parity page failed: {d['error'][:500]}")
        for opt, v in d["differ"].items():  # reported, not fatal: a difference is a finding
            if v["count"]:
                print(f"PARITY {d['sc']} {opt}: {v['count']} of {d['entries']} entries draw differently from pxart's PNGs "
                      f"(max channel delta {d['maxChannelDelta'][opt]}, translucent pixels only: {d['translucentOnly'][opt]})")
    sh([*bench, "--runs", str(a.runs), "--profiles", a.profiles, *(["--options", a.options] if a.options else [])], out / "bench.jsonl")
    browser = json.loads((out / "bench.jsonl").read_text().splitlines()[0]).get("browser")
    (out / "machine.json").write_text(json.dumps({**machine(), "chromium": browser}, indent=1) + "\n")
    with open(out / "bench-summary.md", "w") as f:
        subprocess.run([PY, HERE / "summarize.py", out / "bench.jsonl", out / "sizes.json"], check=True, stdout=f)
    print(f"done: {out}/bench-summary.md")


if __name__ == "__main__":
    main()
