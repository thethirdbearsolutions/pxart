"""The website's data comes from pxart itself and must match what's committed.

site/scripts/gen_reference.py writes site/src/data/reference.json (pxart's help, command by
command) and playground.json (the home page's samples, from `pxart extract`). A change to
pxart's help or to those examples fails here until the data is regenerated:

    python3 site/scripts/gen_reference.py
"""
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "site" / "scripts" / "gen_reference.py"

if not SCRIPT.exists():
    pytest.skip("no site/ in this checkout", allow_module_level=True)


def gen():
    spec = importlib.util.spec_from_file_location("gen_reference", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reference_is_current():
    mod = gen()
    assert mod.OUT.read_text(encoding="utf-8") == mod.render(mod.build()), (
        "site/src/data/reference.json is stale: run python3 site/scripts/gen_reference.py"
    )


def test_playground_is_current():
    mod = gen()
    assert mod.PLAYGROUND.read_text(encoding="utf-8") == mod.render(mod.samples()), (
        "site/src/data/playground.json is stale: run python3 site/scripts/gen_reference.py"
    )


def test_every_command_has_a_page():
    data = json.loads((ROOT / "site" / "src" / "data" / "reference.json").read_text(encoding="utf-8"))
    names = {c["name"] for c in data["commands"]}
    assert names, "no commands in reference.json"
    for c in data["commands"]:
        assert c["summary"], f"{c['name']}: no summary found under its usage line"
        assert c["text"].startswith("usage: pxart " + c["name"]), c["name"]
