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

# (name, label, source selector in examples/, or a file in site/src/content)
SAMPLES = [
    ("face", "blinking face", "site/src/content/blink.px"),
    ("lamp", "harbor lamp", "examples/01-format/lamp.px"),
    ("gem", "gem", "examples/01-format/gem.px"),
    ("walk", "hero walk", "examples/02-animation/hero.px:walk/down"),
]

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

    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, label, sel in SAMPLES:
            path, _, frames = sel.partition(":")
            if path.startswith("site/"):
                text = (ROOT / path).read_text(encoding="utf-8")
            else:
                dest = pathlib.Path(tmp) / f"{name}.px"
                pxart("extract", f"{ROOT / path}:{frames or '*'}", "-o", str(dest), "--inline-palette")
                text = dest.read_text(encoding="utf-8")
            out.append({"name": name, "label": label, "source": path, "text": text})
    return out


def render(data):
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(build()), encoding="utf-8")
    PLAYGROUND.write_text(render(samples()), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} and {PLAYGROUND.relative_to(ROOT)}")
