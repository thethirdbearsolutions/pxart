"""Write the site's data from pxart itself, so the site says what the tool says:

- site/src/data/reference.json: pxart's help, command by command and topic by topic;
- site/src/data/playground.json: the home page's sample sprites, extracted from examples/
  with `pxart extract --inline-palette`, so each stands alone in the browser.

tests/test_site.py fails when either is stale; after changing pxart.py or an example, run:

    python3 site/scripts/gen_reference.py
"""
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "site" / "src" / "data"
OUT = DATA / "reference.json"
PLAYGROUND = DATA / "playground.json"

# The editors on the site ("try me"). Each is a little folder: files by the name the editor shows,
# from examples/ as they are (`extract:` runs pxart extract --inline-palette, so the sample stands
# alone), or from site/src/content. mode: "frames" plays the main file's frames, "sheet" draws every
# .px in the folder side by side (a pack), "map" draws the main .map. `selector` adds a selector box.
EX = "examples/"
SAMPLES = {
    "walk": {"label": "hero walk", "mode": "frames", "files": {"walk.px": "extract:examples/02-animation/hero.px:walk/down"}},
    "face": {"label": "blinking face", "mode": "frames", "files": {"face.px": "site/src/content/blink.px"}},
    "lamp": {"label": "harbor lamp", "mode": "frames", "files": {"lamp.px": "extract:examples/01-format/lamp.px"}},
    "gem": {"label": "gem", "mode": "frames", "files": {"gem.px": EX + "01-format/gem.px"}},
    "palette": {"label": "a sprite and its palette file", "mode": "frames",
                "files": {"lamp.px": EX + "01-format/lamp.px", "palette.px": EX + "01-format/palette.px"}},
    "variants": {"label": "the coast, by day and night", "mode": "sheet",
                 "files": {"coast.px": EX + "03-variants/coast.px", "palette.px": EX + "03-variants/palette.px"}},
    "selectors": {"label": "the hero, by selector", "mode": "frames", "selector": "walk/down%dusk",
                  "files": {"hero.px": EX + "02-animation/hero.px", "hero-palette.px": EX + "02-animation/hero-palette.px"}},
    "pack": {"label": "a pack: one palette, several sprites", "mode": "sheet",
             "files": {"palette.px": EX + "01-format/palette.px", "barrel.px": EX + "01-format/barrel.px",
                       "lamp.px": EX + "01-format/lamp.px", "gem-shared.px": EX + "01-format/gem-shared.px"}},
    "map": {"label": "a map of tiles and props", "mode": "map",
            "files": {"quay.map": "site/src/content/samples/quay.map", "tiles.px": EX + "08-export/harbor.px",
                      "harbor-palette.px": EX + "08-export/harbor-palette.px", "lamp.px": EX + "01-format/lamp.px",
                      "palette.px": EX + "01-format/palette.px", "barrel.px": EX + "01-format/barrel.px"}},
    # tutorial 10's rooms, laid out as in examples/10-map-variants (a variant list's picks hash the
    # room's name, the map's file name, so these draw as the tutorial's pictures do)
    "map-variants": {"label": "variant tiles: grass, flowers and a pond", "mode": "map",
                     "files": {"rooms/pond.map": EX + "10-map-variants/rooms/pond.map",
                               "tiles/field.px": EX + "10-map-variants/tiles/field.px",
                               "pal/field.px": EX + "10-map-variants/pal/field.px",
                               "tiles/harbor.px": EX + "10-map-variants/tiles/harbor.px",
                               "tiles/harbor-palette.px": EX + "10-map-variants/tiles/harbor-palette.px"}},
    "map-picks": {"label": "a variant list's picks, made visible", "mode": "map",
                  "files": {"picks/meadow.map": EX + "10-map-variants/picks/meadow.map",
                            "tiles/field.px": EX + "10-map-variants/tiles/field.px",
                            "pal/field.px": EX + "10-map-variants/pal/field.px"}},
}
# the home page's editor offers these, the first shown first
HOME = ["walk", "face", "lamp", "gem"]

# Topics in the order `pxart -h` lists them, then the ones with pages of their own.
TOPICS = ["FORMAT", "LOOKING", "CHECKING", "EDITING", "DRAWING", "CONVERTING", "HELP", "ERRORS"]
EXTRA = {"recipes": "Recipes", "worlds": "Worlds", "slots": "Palette slots"}


def pxart(*args):
    env = dict(os.environ, COLUMNS="100", PYTHONIOENCODING="utf-8")
    proc = subprocess.run([sys.executable, str(ROOT / "pxart.py"), *args], capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise SystemExit(f"pxart {' '.join(args)} failed:\n{proc.stderr}")
    return proc.stdout.rstrip() + "\n"


def split_head(text):
    """The synopsis block under argparse's usage: the command's own usage line(s) and the line
    or three saying what it's for (indented 6, or after the usage on its one line)."""
    block = text.split("\n\n")[1].splitlines()
    synopsis, summary = [], []
    for line in block:
        if re.match(r"^      \S", line):
            summary.append(line.strip())
        elif not summary:
            m = re.match(r"^(  \S.*?)\s{3,}(\S.*)$", line)
            if m and not synopsis:
                synopsis.append(m.group(1).strip())
                summary.append(m.group(2).strip())
            else:
                synopsis.append(line.strip())
    summary = " ".join(summary)
    return " ".join(synopsis), summary[:1].upper() + summary[1:]


def build():
    overview = pxart("-h")
    by_topic = {}
    for line in overview.splitlines():
        m = re.match(r"^  ([A-Z]+)\s{2,}([a-z][a-z\- ]+)$", line)
        if m and m.group(1) in TOPICS:
            by_topic[m.group(1)] = m.group(2).split()
    commands = []
    for topic in TOPICS:
        for name in by_topic.get(topic, []):
            text = pxart("help", name)
            synopsis, summary = split_head(text)
            commands.append({"name": name, "topic": topic, "synopsis": synopsis, "summary": summary, "text": text})
    topics = [{"id": t.lower(), "title": t.capitalize(), "text": pxart("help", t)} for t in TOPICS]
    topics += [{"id": k, "title": v, "text": pxart("help", k)} for k, v in EXTRA.items()]
    version = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M).group(1)
    return {"version": version, "overview": overview, "commands": commands, "topics": topics, "all": pxart("help", "all")}


def samples():
    import tempfile

    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, spec in SAMPLES.items():
            files = {}
            for fname, src in spec["files"].items():
                if src.startswith("extract:"):
                    path, _, frames = src[len("extract:"):].partition(":")
                    dest = pathlib.Path(tmp) / f"{name}-{fname}"
                    pxart("extract", f"{ROOT / path}:{frames or '*'}", "-o", str(dest), "--inline-palette")
                    files[fname] = dest.read_text(encoding="utf-8")
                else:
                    files[fname] = (ROOT / src).read_text(encoding="utf-8")
            out[name] = {"label": spec["label"], "mode": spec["mode"], "main": next(iter(spec["files"])),
                         "selector": spec.get("selector"), "files": files}
    return {"home": HOME, "samples": out}


def render(data):
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(build()), encoding="utf-8")
    PLAYGROUND.write_text(render(samples()), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} and {PLAYGROUND.relative_to(ROOT)}")
