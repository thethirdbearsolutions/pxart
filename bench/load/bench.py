"""Load each scenario x option in a real page, in Chromium, N cold-cache runs per profile, and print
one JSON line per run.

    python3 bench/load/bench.py WORK_DIR CERT_DIR [--runs N] [--profiles a,b] [--scenarios a,b]
                                [--options a,b] [--parity]

Each run is a fresh browser context (no cache), served over HTTP/2 + TLS with brotli for text
(web/server.mjs). A run records when the page could first draw, when every sprite had been drawn
once, the runtime's own timings, decoded bitmap bytes, JS heap, main-thread task and script time
(Chrome's Performance.getMetrics, which counts the page's main thread only), and the bytes and requests on the
wire (response bodies as encoded: the pack's files under /sc/, and the whole page). --parity runs
the drawn-parity page instead, once per scenario.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent


def start_server(work: Path, certs: Path) -> tuple[subprocess.Popen, int]:
    """web/server.mjs on a free port: (the process, its port). Fails if it doesn't come up."""
    proc = subprocess.Popen(["node", str(HERE / "web/server.mjs"), str(work.resolve()), "0", str(certs.resolve())],
                            stdout=subprocess.PIPE, text=True)
    line = proc.stdout.readline()
    if not line.startswith("listening "):
        proc.kill()
        raise SystemExit(f"the bench server didn't start (node 22.18 or newer?): {line!r}")
    return proc, int(line.rsplit(":", 1)[1])


def net(down_mbps: float, up_mbps: float, rtt_ms: float) -> dict:
    """Chrome DevTools network throttling: latency per request, throughput in bytes per second."""
    return {"offline": False, "latency": rtt_ms, "downloadThroughput": down_mbps * 1e6 / 8, "uploadThroughput": up_mbps * 1e6 / 8}


# Lighthouse's mobile network: 1.6 Mbps down, 750 kbps up, 150 ms RTT
NET_4G = net(1.6, 0.75, 150)
PROFILES = {
    "desktop": {"net": None, "cpu": 1, "device": None, "about": "desktop CPU, no throttling"},
    "desktop-100mbps": {"net": net(100, 20, 20), "cpu": 1, "device": None, "about": "desktop CPU, 100 Mbps down / 20 up, 20 ms RTT"},
    "desktop-20mbps": {"net": net(20, 5, 40), "cpu": 1, "device": None, "about": "desktop CPU, 20 Mbps down / 5 up, 40 ms RTT"},
    "desktop-4g": {"net": NET_4G, "cpu": 1, "device": None, "about": "desktop CPU, Lighthouse 4G: 1.6 Mbps down / 750 kbps up, 150 ms RTT"},
    "mobile": {"net": NET_4G, "cpu": 4, "device": "Pixel 7", "about": "Playwright's Pixel 7 (viewport, DPR, UA, touch), CPU throttled 4x, Lighthouse 4G"},
}
SCENARIOS = ("s300", "s300v2", "s650v2")
OPTIONS = (
    "frames", "frames.oxi", "frames.webp",
    "atlas", "atlas.oxi", "atlas.webp",
    "atlas+", "atlas+.oxi", "atlas+.webp",
    "render", "render.gzip",
)
# GAMES-443's whole-cast format (bench/cast/build_pxc.py), when it is built
PXC_OPTIONS = ("pxc", "pxc.gzip", "pxc.main")


def run_page(browser, pw, profile: dict, url: str) -> dict:
    kw = dict(pw.devices[profile["device"]]) if profile["device"] else {"viewport": {"width": 1280, "height": 800}}
    ctx = browser.new_context(ignore_https_errors=True, **kw)
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    if profile["net"]:
        cdp.send("Network.emulateNetworkConditions", profile["net"])
    if profile["cpu"] > 1:
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": profile["cpu"]})
    cdp.send("Performance.enable")
    requests = []
    page.on("requestfinished", lambda r: requests.append(r))
    page.goto(url)
    page.wait_for_function("window.__results", timeout=900_000, polling=50)
    res = page.evaluate("window.__results")
    cdp.send("HeapProfiler.collectGarbage")
    metrics = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}
    res["jsHeapAfterGC"] = metrics.get("JSHeapUsedSize")
    # the page's main thread, from navigation to here: every task, and the script inside them, ms
    res["mainThreadTaskMs"] = round(metrics.get("TaskDuration", 0) * 1000, 1)
    res["mainThreadScriptMs"] = round(metrics.get("ScriptDuration", 0) * 1000, 1)
    sizes = [(r.url, r.sizes()["responseBodySize"]) for r in requests]
    res["requests"] = len(sizes)
    res["packRequests"] = sum(1 for u, _ in sizes if "/sc/" in u)
    res["packBytes"] = sum(n for u, n in sizes if "/sc/" in u)
    res["pageBytes"] = sum(n for _, n in sizes)
    ctx.close()
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("work", type=Path)
    ap.add_argument("certs", type=Path)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--profiles", default=",".join(PROFILES))
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    ap.add_argument("--options", default=",".join(OPTIONS))
    ap.add_argument("--parity", action="store_true")
    a = ap.parse_args()
    server, port = start_server(a.work, a.certs)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--enable-precise-memory-info"])
            print(json.dumps({"browser": browser.version}), flush=True)
            for sc in a.scenarios.split(","):
                if a.parity:
                    opts = [o for o in OPTIONS + PXC_OPTIONS if o != "frames" and (a.work / sc / f"out-{o}").is_dir()]
                    r = run_page(browser, pw, PROFILES["desktop"], f"https://localhost:{port}/parity.html?sc={sc}&opts={quote(','.join(opts))}")
                    print(json.dumps({"parity": sc, **r}), flush=True)
            if a.parity:
                return
            for name in a.profiles.split(","):
                for sc in a.scenarios.split(","):
                    for opt in a.options.split(","):
                        for run in range(a.runs):
                            t = time.time()
                            url = f"https://localhost:{port}/game.html?sc={sc}&opt={quote(opt)}&cpu={PROFILES[name]['cpu']}"
                            r = run_page(browser, pw, PROFILES[name], url)
                            print(json.dumps({"profile": name, "run": run, "wall": round(time.time() - t, 2), **r}), flush=True)
            browser.close()
    finally:
        server.terminate()


if __name__ == "__main__":
    sys.exit(main())
