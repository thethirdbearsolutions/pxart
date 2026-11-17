"""A cast with variant axes, for the whole-cast compression spike: the load bench's synthetic s300
cast, in 3 times of day x 4 seasons (palettes) and 3 damage states x 3 expressions (overlays).

    python3 bench/cast/make_axes.py OUT_DIR [--axes T,S,D,E]

Writes OUT_DIR/s300ax/cast/ (palette.px and the five characters) and OUT_DIR/s300ax/layers.json.
--axes takes the first T times of day, S seasons, D damage states and E expressions (3,4,3,3 by
default), into OUT_DIR/s300ax-T-S-D-E/ when it isn't the full set: how cost grows with the axes.

- **Palettes:** palette.px's base is day-summer. Its 11 other combinations are @variant blocks named
  <time>-<season>, each color computed as time(season(color)), per channel v*mul+add, rounded half
  up and clamped. layers.json keeps the axes as that data.
- **Overlays:** every frame is drawn in all 9 damage x expression combinations, so pxart renders each
  as its own frame: <damage>-<expression>/<action>/<facing>/<i>, 540 per character, 2,700 in all.
  A damage overlay is stamped at the body's centre, then an expression overlay at the head's (none
  from behind). Right-facing frames take the overlays mirrored. layers.json keeps the overlays
  and each frame's anchors, so a format can draw the combinations instead of shipping them.

Every frame in every palette is what pxart renders: that is what a format must match.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "load"))
import make_cast as mc  # noqa: E402

# (mul, add) per channel, r g b; alpha is left alone
TIME = {
    "day": ((1, 1, 1), (0, 0, 0)),
    "dawn": ((1.0, 0.88, 0.72), (18, 6, 0)),
    "dusk": ((0.55, 0.6, 0.8), (0, 0, 24)),
}
SEASON = {
    "summer": ((1, 1, 1), (0, 0, 0)),
    "spring": ((0.95, 1.05, 0.95), (8, 10, 12)),
    "autumn": ((1.08, 0.9, 0.7), (10, 0, 0)),
    "winter": ((0.8, 0.85, 0.95), (30, 34, 44)),
}
DAMAGE = ("none", "scuffed", "wounded")
EXPRESSION = ("neutral", "happy", "angry")
SKIN = 1  # the expression overlay paints eyes over the skin's mid tone


def axis(c: int, mul: float, add: float) -> int:
    return max(0, min(255, int(c * mul + add + 0.5)))


def combine(rgb: tuple[int, int, int], time: str, season: str) -> tuple[int, int, int]:
    (sm, sa), (tm, ta) = SEASON[season], TIME[time]
    s = [axis(rgb[i], sm[i], sa[i]) for i in range(3)]
    return tuple(axis(s[i], tm[i], ta[i]) for i in range(3))


def palette_text(times=TIME, seasons=SEASON) -> str:
    base = mc.palette_text()
    entries = []
    for line in base.splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 1 and parts[1].startswith("#"):
            entries.append((parts[0], parts[1]))
    out = [base.rstrip("\n")]
    for time in times:
        for season in seasons:
            if (time, season) == ("day", "summer"):
                continue
            out.append(f"\n@variant {time}-{season}")
            for k, h in entries:
                n = int(h[1:7], 16)
                r, g, b = combine(((n >> 16) & 255, (n >> 8) & 255, n & 255), time, season)
                out.append(f"{k} #{r:02x}{g:02x}{b:02x}{h[7:]}")
    return "\n".join(out) + "\n"


def grid(w: int, h: int) -> list[list[str]]:
    return [["."] * w for _ in range(h)]


def expression_overlay(ch: dict, expr: str, side: bool) -> dict | None:
    """Rows centred on the head anchor; None for the neutral face (the base frame has it)."""
    if expr == "neutral":
        return None
    hr = ch["head"]
    size = 2 * hr + 1
    g = grid(size, size)
    skin = mc.KEY[(ch["skin"], SKIN)]
    eyes = (-1,) if side else (-1, 1)  # side: facing left (right-facing frames mirror it)
    for e in eyes:
        ex = hr + math.floor(e * hr * (0.55 if side else 0.4))  # as draw's int(cx + ...), cx whole
        ey = hr + 1
        for dy in range(3):  # paint the neutral eye out
            for dx in range(2):
                g[ey + dy][ex + dx] = skin
        if expr == "happy":  # a closed, upturned eye
            for x, y in ((0, 1), (1, 0), (2, 1)):
                g[ey + y][ex + x - (1 if e < 0 else 0)] = mc.EYE
        else:  # angry: a slanted brow over a narrowed eye
            for k in range(4):
                g[ey - 2 + (k if e > 0 else 3 - k) // 2][ex - 1 + k] = mc.OUTLINE
            g[ey + 1][ex] = g[ey + 1][ex + 1] = mc.EYE
    return {"rows": ["".join(r) for r in g], "at": "head", "dx": -hr, "dy": -hr}


def damage_overlay(ch: dict, damage: str) -> dict | None:
    """Rows centred on the body anchor; marks stay inside the body's outline."""
    if damage == "none":
        return None
    bw, bh = ch["body"]
    w, h = 2 * bw + 1, bh + 1
    g = grid(w, h)
    cx, cy = bw, bh // 2
    marks = [(-0.45, -0.2), (0.2, -0.3), (0.35, 0.1)] + ([(-0.2, 0.2), (0.05, 0.0), (-0.5, 0.05)] if damage == "wounded" else [])
    for fx, fy in marks:
        x0, y0 = cx + int(fx * bw), cy + int(fy * bh)
        for k in range(4):
            g[y0 + k // 2][x0 + k] = mc.OUTLINE
    if damage == "wounded":
        red = mc.KEY[("red", 1)]
        for fx, fy in ((-0.3, 0.1), (0.25, -0.05)):
            x0, y0 = cx + int(fx * bw), cy + int(fy * bh)
            for dy in range(2):
                for dx in range(3):
                    g[y0 + dy][x0 + dx] = red
        band = cy - 1  # a bandage across the chest
        for x in range(cx - int(bw * 0.55), cx + int(bw * 0.55)):
            g[band][x] = mc.KEY[("snow", 0)]
            g[band + 1][x] = mc.KEY[("snow", 1)]
    return {"rows": ["".join(r) for r in g], "at": "body", "dx": -bw, "dy": -bh // 2}


def stamp(rows: list[str], ov: dict | None, anchors: dict, mirror: bool) -> list[str]:
    if ov is None:
        return rows
    px = [list(r) for r in rows]
    ax, ay = anchors[ov["at"]]
    for y, r in enumerate(ov["rows"]):
        for x, k in enumerate(r if not mirror else r[::-1]):
            if k == ".":
                continue
            dx = ov["dx"] + x if not mirror else -(ov["dx"] + len(r) - 1) + x
            X, Y = ax + dx, ay + ov["dy"] + y
            if 0 <= Y < len(px) and 0 <= X < len(px[0]):
                px[Y][X] = k
    return ["".join(r) for r in px]


def overlays_for(ch: dict, facing: str, damage: str, expr: str) -> list[dict | None]:
    return [damage_overlay(ch, damage), None if facing == "up" else expression_overlay(ch, expr, facing in ("left", "right"))]


def main(out: Path, counts: tuple[int, int, int, int] = (3, 4, 3, 3)) -> None:
    global DAMAGE, EXPRESSION
    times = dict(list(TIME.items())[: counts[0]])
    seasons = dict(list(SEASON.items())[: counts[1]])
    DAMAGE, EXPRESSION = DAMAGE[: counts[2]], EXPRESSION[: counts[3]]
    name = "s300ax" if counts == (3, 4, 3, 3) else "s300ax-" + "-".join(map(str, counts))
    dest = out / name / "cast"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    (dest / "palette.px").write_text(palette_text(times, seasons))
    layers = {
        "axes": {"time": times, "season": seasons, "order": ["season", "time"], "base": ["day", "summer"]},
        "damage": DAMAGE, "expression": EXPRESSION, "characters": {},
    }
    total = 0
    for ch in mc.CHARACTERS:
        W, H = ch["size"]
        text = ["pxart 1", "@palette palette.px"]
        for d in DAMAGE:
            for e in EXPRESSION:
                for action, facing, n in mc.ACTIONS:
                    text.append(f"@anim {d}-{e}/{action}/{facing} direction=forward ms={mc.MS[action]} pivot={W // 2},{H - 6}")
        text.append("")
        anchors_of, base = {}, {}
        for action, facing, n in mc.ACTIONS:
            for i in range(n):
                a: dict = {}
                fid = f"{action}/{facing}/{i}"
                base[fid] = mc.draw_facing(ch, facing, action, i, n, a)
                anchors_of[fid] = {"head": list(a["head"]), "body": list(a["body"]), "mirror": facing == "right", "facing": facing}
        for d in DAMAGE:
            for e in EXPRESSION:
                for fid, rows in base.items():
                    a = {k: tuple(v) for k, v in anchors_of[fid].items() if k in ("head", "body")}
                    for ov in overlays_for(ch, anchors_of[fid]["facing"], d, e):
                        rows = stamp(rows, ov, a, anchors_of[fid]["mirror"])
                    text.append(f"@frame {d}-{e}/{fid}")
                    text += rows
                    text.append("")
                    total += 1
        (dest / f"{ch['name']}.px").write_text("\n".join(text))
        layers["characters"][ch["name"]] = {
            "anchors": anchors_of,
            "overlays": {
                **{f"damage:{d}": damage_overlay(ch, d) for d in DAMAGE if d != "none"},
                **{f"expression:{e}:{s}": expression_overlay(ch, e, s == "side") for e in EXPRESSION if e != "neutral" for s in ("front", "side")},
            },
        }
    (out / name / "layers.json").write_text(json.dumps(layers, separators=(",", ":")))
    print(f"{name}: {total} frames in {len(mc.CHARACTERS)} characters, {len(times) * len(seasons)} palettes")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--axes", default="3,4,3,3")
    a = ap.parse_args()
    main(a.out, tuple(int(n) for n in a.axes.split(",")))
