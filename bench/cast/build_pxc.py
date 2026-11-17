"""The PXC1 options for the load bench, next to build.py's: out-pxc/ (the cast as one .pxc, served
brotli, decoded in a worker), out-pxc.gzip/ (served gzip-only) and out-pxc.main/ (decoded on the
main thread). Run build.py's render mode first: the manifest is its, pointed at cast.pxc.

    python3 bench/cast/build_pxc.py SCENARIO_DIR
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pxc import encode  # noqa: E402


def main(scenario: Path) -> None:
    t0 = time.perf_counter()
    layers_file = scenario / "layers.json"
    layers = json.loads(layers_file.read_text()) if layers_file.exists() else None
    data, stats = encode(scenario / "cast", layers)
    secs = time.perf_counter() - t0
    manifest = json.loads((scenario / "out-render" / "manifest.json").read_text())
    manifest["pack"].pop("sources", None)
    manifest["pack"]["pxc"] = "cast.pxc"
    for opt in ("pxc", "pxc.gzip", "pxc.main"):
        out = scenario / f"out-{opt}"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir()
        (out / "cast.pxc").write_bytes(data)
        (out / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
        (out / "build.json").write_text(json.dumps({"encode": secs, "files": ["cast.pxc", "manifest.json"], **stats}, indent=1))
    print(f"{scenario.name} pxc: {len(data)} bytes, {secs:.1f}s")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
