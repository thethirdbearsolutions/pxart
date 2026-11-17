"""Pixel parity: every frame x palette a .pxc decodes to (web/pxc.js, under node) against pxart's
render of the cast it was made from, byte for byte (sha256 of the RGBA).

    python3 bench/cast/parity.py CAST_DIR CAST.pxc

A layered cast's combinations are compared with the baked frames pxart renders for them. Prints a
JSON summary and exits 1 on any difference.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pxart  # noqa: E402

HERE = Path(__file__).resolve().parent


def main(cast: Path, pxc: Path) -> int:
    out = subprocess.run(["node", str(HERE / "web" / "pxc-dump.mjs"), str(pxc)], capture_output=True, text=True, check=True).stdout
    got = {}
    for line in out.splitlines():
        key, w, h, sha = line.rsplit(" ", 3)
        got[key] = (int(w), int(h), sha)
    want = {}
    for p in sorted(cast.glob("*.px")):
        if not pxart._has_grid(p):
            continue
        doc = pxart.parse(p)
        for v in [None, *pxart.variant_names(doc)]:
            for f in doc.frames:
                im = doc.image(f, v)
                want[f"{p.name}:{f.id}%{v or 'base'}"] = (im.width, im.height, hashlib.sha256(im.tobytes()).hexdigest())
    differ = sorted(k for k in want if k in got and got[k] != want[k])
    res = {
        "pxart_frames": len(want), "pxc_frames": len(got), "identical": sum(1 for k in want if got.get(k) == want[k]),
        "differ": len(differ), "missing_in_pxc": len(set(want) - set(got)), "extra_in_pxc": len(set(got) - set(want)),
        "first": (differ + sorted(set(want) ^ set(got)))[:5],
    }
    print(json.dumps(res))
    return 0 if res["identical"] == len(want) == len(got) else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
