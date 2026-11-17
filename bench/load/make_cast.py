"""A synthetic cast for the load bench: five characters drawn by code, from a seed, so anyone can
regenerate the exact same files.

    python3 bench/load/make_cast.py OUT_DIR

Writes OUT_DIR/<scenario>/cast/*.px for three scenarios:
- s300:    five characters and a shared palette.px, 60 frames each (300 frames), no palette variants;
- s300v2:  the same, with two palette variants, dawn and dusk, in palette.px;
- s650v2:  645 frames: each one-facing action (attack-with-light, eat, jump, make-a-slash) gains up,
           left and right facings, so every action has all four, plus dawn and dusk.

The shape follows the private cast the first runs of this bench used: five characters of about 60
frames on canvases of about 100x100 pixels, a shared palette, the same action names, and the same
synthetic facings for s650v2 (left: the down frames mirrored; right: mirrored and shifted a pixel;
up: shifted two pixels). The art is not that cast's: it is drawn here from ellipses, rectangles and
lines, shaded and outlined, with a little dither. Its bytes compress differently from hand-drawn
art, so compare options within one cast, not numbers across casts.
"""

from __future__ import annotations

import argparse
import math
import random
import re
import shutil
from pathlib import Path

SCENARIOS = ("s300", "s300v2", "s650v2")
ONE_FACING = ("attack-with-light", "eat", "jump", "make-a-slash")
FACINGS = ("down", "up", "left", "right")

# The shared palette: an outline, then ramps of three (light, mid, dark) for each material.
RAMPS = {
    "skin": ("#f7d3b5", "#e0a982", "#b5785a"),
    "fur": ("#d9a066", "#a86b3c", "#704325"),
    "snow": ("#f4f4f8", "#c9cbd6", "#8f93a8"),
    "steel": ("#c7d0dc", "#8a96a8", "#56607a"),
    "red": ("#e8604c", "#b33a3a", "#7a2335"),
    "blue": ("#6fa8dc", "#3d6fb0", "#29477a"),
    "green": ("#8cc66a", "#4f9a4a", "#2f6340"),
    "purple": ("#b48ae0", "#7d56b8", "#4f3580"),
    "gold": ("#ffe17a", "#e0a83a", "#a8702a"),
    "brown": ("#a87a54", "#7a5236", "#4f3424"),
    "teal": ("#7fe0d0", "#3fae9e", "#2a7468"),
    "pink": ("#ffb3c8", "#e07a9a", "#a84f6f"),
}
SPECIAL = {"outline": "#2a1f2e", "eye": "#1a1420", "shine": "#ffffff", "light": "#fff6a8", "glow": "#ffd84a80"}

KEYS = iter("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdfghijlmnopqrstuvxz0123456789")  # not k e w y ~
KEY: dict[tuple[str, int], str] = {}
for _name in RAMPS:
    for _i in range(3):
        KEY[(_name, _i)] = next(KEYS)
OUTLINE, EYE, SHINE, LIGHT, GLOW = "k", "e", "w", "y", "~"
TEXTURE = 22  # percent of a textured shape's pixels that take a band other than their light gives

# Five characters. Each: canvas, body proportions and materials, and an accessory.
CHARACTERS = [
    dict(name="fox", size=(96, 96), head=18, body=(21, 24), skin="fur", cloth="green", trim="snow", extra="tail", seed=1),
    dict(name="owl", size=(92, 100), head=20, body=(25, 22), skin="brown", cloth="snow", trim="gold", extra="wings", seed=2),
    dict(name="knight", size=(104, 104), head=17, body=(24, 28), skin="skin", cloth="steel", trim="red", extra="plume", seed=3),
    dict(name="wizard", size=(100, 104), head=17, body=(22, 30), skin="skin", cloth="purple", trim="gold", extra="hat", seed=4),
    dict(name="sprite", size=(88, 96), head=19, body=(17, 21), skin="teal", cloth="pink", trim="blue", extra="halo", seed=5),
]

# Per character: (action, facing) -> frame count. 60 frames each.
ACTIONS = [("idle", f, 2) for f in FACINGS] + [("walk", f, 6) for f in FACINGS] + [
    ("hurt", "down", 2),
    ("sit", "down", 3),
    ("attack-with-light", "down", 6),
    ("eat", "down", 5),
    ("jump", "down", 6),
    ("make-a-slash", "down", 6),
]
MS = {"idle": 400, "walk": 110, "hurt": 120, "sit": 200, "attack-with-light": 90, "eat": 160, "jump": 100, "make-a-slash": 80}


class Canvas:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.px = [["."] * w for _ in range(h)]

    def put(self, x: int, y: int, key: str) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = key

    def shaded_ellipse(self, cx: float, cy: float, rx: float, ry: float, ramp: str, dither: bool = False) -> None:
        """An ellipse lit from the top left: light, mid and dark bands, a checker where two meet."""
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                dx, dy = (x + 0.5 - cx) / max(rx, 0.5), (y + 0.5 - cy) / max(ry, 0.5)
                d = dx * dx + dy * dy
                if d > 1:
                    continue
                lit = -dx * 0.6 - dy * 0.8 + (1 - d) * 0.5
                band = 0 if lit > 0.45 else 1 if lit > -0.25 else 2
                if dither and abs(lit - 0.45) < 0.08 and (x + y) % 2:
                    band = 1
                if dither and abs(lit + 0.25) < 0.08 and (x + y) % 2:
                    band = 2
                if dither:  # texture (fur, cloth weave) fixed to the shape, so it moves with it
                    h = (int(x - cx + 64) * 73856093) ^ (int(y - cy + 64) * 19349663) ^ (len(ramp) * 83492791)
                    if (h >> 3) % 100 < TEXTURE:
                        band = (h >> 11) % 3
                self.put(x, y, KEY[(ramp, band)])

    def shaded_rect(self, x0: int, y0: int, w: int, h: int, ramp: str) -> None:
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                band = 0 if x - x0 < max(1, w // 4) else 2 if x - x0 >= w - max(1, w // 4) else 1
                if y == y0 + h - 1:
                    band = 2
                self.put(x, y, KEY[(ramp, band)])

    def line(self, x0: float, y0: float, x1: float, y1: float, key: str, thick: int = 1) -> None:
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            t = i / n
            x, y = round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t)
            for ox in range(thick):
                for oy in range(thick):
                    self.put(x + ox, y + oy, key)

    def outline(self) -> None:
        """Every empty pixel touching a filled one (not glow) becomes the outline."""
        solid = [[c not in (".", GLOW) for c in row] for row in self.px]
        for y in range(self.h):
            for x in range(self.w):
                if self.px[y][x] != ".":
                    continue
                if any(0 <= x + dx < self.w and 0 <= y + dy < self.h and solid[y + dy][x + dx]
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    self.px[y][x] = OUTLINE

    def rows(self) -> list[str]:
        return ["".join(r) for r in self.px]


def pose(action: str, i: int, n: int) -> dict:
    """What the body does in frame i of n: bob, stride, arm swing, lift, and an effect."""
    t = i / n
    p = dict(bob=0, stride=0.0, arm=0.0, lift=0, squash=0, effect=None, lean=0)
    if action == "idle":
        p["bob"] = i % 2
    elif action == "walk":
        p["stride"] = math.sin(t * 2 * math.pi)
        p["arm"] = -p["stride"]
        p["bob"] = 1 if i % 3 == 1 else 0
    elif action == "hurt":
        p["lean"] = 3 if i == 0 else 1
        p["effect"] = "flash" if i == 0 else None
    elif action == "sit":
        p["squash"] = min(i * 3, 6)
    elif action == "attack-with-light":
        p["arm"] = -1.2 + t * 2.4
        p["effect"] = ("light", t)
    elif action == "eat":
        p["arm"] = -1.6 if i % 2 else -0.6
        p["bob"] = i % 2
    elif action == "jump":
        p["lift"] = int(14 * math.sin(t * math.pi))
        p["squash"] = 3 if i in (0, n - 1) else 0
    elif action == "make-a-slash":
        p["arm"] = -1.8 + t * 3.6
        p["effect"] = ("slash", t)
    return p


def draw(ch: dict, facing: str, action: str, i: int, n: int, anchors: dict | None = None) -> list[str]:
    """One frame's rows. `anchors`, if given, gets the head's and the body's centre (x, y)."""
    W, H = ch["size"]
    c = Canvas(W, H)
    rng = random.Random(f"{ch['seed']}:{facing}:{action}:{i}")
    p = pose(action, i, n)
    bw, bh = ch["body"]
    cx = W / 2 + p["lean"]
    ground = H - 6
    leg_h = 14
    body_top = ground - leg_h - bh - p["lift"] + p["bob"] + p["squash"]
    side = facing in ("left", "right")
    # legs: two, swinging with the stride
    for leg in (-1, 1):
        sw = p["stride"] * 5 * leg
        x = cx + leg * (bw / 3 if not side else 2) + (sw if side else 0)
        lh = leg_h - (p["squash"] // 2) - (abs(sw) // 3 if not side else 0)
        c.shaded_rect(int(x - 4), int(ground - lh - p["lift"]), 8, int(lh), ch["cloth"] if leg < 0 else ch["trim"])
        c.shaded_ellipse(x + (2 if facing == "right" else -2 if facing == "left" else 0), ground - p["lift"] - 1, 5.5, 3, "brown")
    # tail or wings behind the body
    if ch["extra"] == "tail" and facing != "down":
        c.shaded_ellipse(cx + (-bw if facing != "left" else bw), body_top + bh * 0.7, 8, 4, ch["skin"], dither=True)
    if ch["extra"] == "wings":
        flap = 3 * math.sin(i * 1.3)
        for s in (-1, 1) if not side else (1,):
            c.shaded_ellipse(cx + s * (bw + 3), body_top + bh / 2 + flap * s, 6, bh / 2, ch["skin"], dither=True)
    # body
    c.shaded_ellipse(cx, body_top + bh / 2, bw, bh / 2, ch["cloth"], dither=True)
    c.shaded_rect(int(cx - bw * 0.7), int(body_top + bh * 0.55), int(bw * 1.4), 3, ch["trim"])
    for _ in range(4):  # buttons, studs, patches: a few fixed details per frame's seed
        c.put(int(cx + rng.randint(-bw // 2, bw // 2)), int(body_top + rng.randint(2, bh - 2)), KEY[(ch["trim"], rng.randint(0, 2))])
    # arms
    for arm in (-1, 1) if not side else (1,):
        a = p["arm"] * arm + (0.3 * arm if not side else 0)
        sx = cx + arm * (bw - 1) if not side else cx + (4 if facing == "right" else -4)
        sy = body_top + 5
        ex, ey = sx + math.sin(a) * 15 * (arm if not side else (1 if facing == "right" else -1)), sy + math.cos(a) * 15
        c.line(sx, sy, ex, ey, KEY[(ch["cloth"], 1)], thick=4)
        c.shaded_ellipse(ex + 1, ey + 1, 3.5, 3.5, ch["skin"])
    # head
    hr = ch["head"]
    hy = body_top - hr + 3
    c.shaded_ellipse(cx, hy, hr, hr * 0.9, ch["skin"], dither=True)
    if facing != "up":
        eyes = (-1, 1) if not side else ((1,) if facing == "right" else (-1,))
        for e in eyes:
            ex = int(cx + e * hr * (0.4 if not side else 0.55))
            ey = int(hy + 1)
            blink = action == "idle" and i == 1 and facing == "down"
            for dy in range(1 if blink else 3):
                c.put(ex, ey + dy + (1 if blink else 0), EYE)
                c.put(ex + 1, ey + dy + (1 if blink else 0), EYE)
            if not blink:
                c.put(ex, ey, SHINE)
        if action == "eat":
            c.shaded_ellipse(cx, hy + hr * 0.5, 2.5, 1.5 + i % 2, "red")
    else:
        for k in range(hr):  # the back of the head: hair strands
            c.line(cx - hr + 2 * k, hy - hr * 0.6, cx - hr + 2 * k + 1, hy + hr * 0.4, KEY[(ch["skin"], 2)])
    # accessory on top
    if ch["extra"] == "hat":
        c.shaded_ellipse(cx, hy - hr * 0.6, hr * 1.4, 3, ch["cloth"])
        for k in range(10):
            c.shaded_ellipse(cx + k * 0.6, hy - hr * 0.6 - k * 2, 7 - k * 0.6, 2, ch["cloth"])
        c.put(int(cx + 6), int(hy - hr - 18), KEY[(ch["trim"], 0)])
    elif ch["extra"] == "plume":
        for k in range(8):
            c.shaded_ellipse(cx - 2 + k, hy - hr - k * 1.2, 2, 2, ch["trim"])
    elif ch["extra"] == "halo":
        for a in range(0, 360, 10):
            r = math.radians(a)
            c.put(int(cx + math.cos(r) * hr * 0.9), int(hy - hr - 4 + math.sin(r) * 2), KEY[("gold", 0 if a < 180 else 1)])
    elif ch["extra"] == "tail" and facing == "down":
        c.shaded_ellipse(cx + bw, body_top + bh * 0.8, 6, 3, ch["skin"], dither=True)
    # ears for the fox and owl
    if ch["extra"] in ("tail", "wings"):
        for e in (-1, 1):
            c.shaded_ellipse(cx + e * hr * 0.7, hy - hr * 0.9, 3, 5, ch["skin"])
    c.outline()
    if anchors is not None:
        anchors["head"] = (int(cx), int(hy))
        anchors["body"] = (int(cx), int(body_top + bh / 2))
    # effects drawn over the outline: a glow and a light, or a slash arc
    if p["effect"] == "flash":
        for _ in range(30):
            c.put(rng.randint(0, W - 1), rng.randint(0, H - 1), SHINE)
    elif p["effect"] and p["effect"][0] == "light":
        t = p["effect"][1]
        r = 5 + 13 * t
        lx, ly = cx + bw + 8, body_top + 4
        for y in range(int(ly - r), int(ly + r) + 1):
            for x in range(int(lx - r), int(lx + r) + 1):
                d = math.hypot(x - lx, y - ly)
                if d <= r:
                    c.put(x, y, LIGHT if d < r * 0.4 else GLOW if (x + y) % 2 or d < r * 0.7 else c.px[y][x] if 0 <= y < H and 0 <= x < W else ".")
    elif p["effect"] and p["effect"][0] == "slash":
        t = p["effect"][1]
        for a in range(int(-60 + 160 * t) - 50, int(-60 + 160 * t)):
            r = math.radians(a)
            for rr in (30, 31, 32):
                c.put(int(cx + math.cos(r) * rr), int(body_top + bh / 2 - math.sin(r) * rr), SHINE if rr == 31 else LIGHT)
    return c.rows()


def draw_facing(ch: dict, facing: str, action: str, i: int, n: int, anchors: dict | None = None) -> list[str]:
    """Right is left drawn the other way and nudged a pixel, as artists often draw it."""
    if facing != "right":
        return draw(ch, facing, action, i, n, anchors)
    rows = draw(ch, "left", action, i, n, anchors)
    if anchors is not None:  # x -> W-1-x, then a pixel left
        anchors.update({k: (len(rows[0]) - 2 - x, y) for k, (x, y) in anchors.items()})
    return [r[::-1][1:] + "." for r in rows]


def palette_text() -> str:
    lines = ["pxart 1", "# the shared palette: an outline, eyes, lights, and a light/mid/dark ramp per material"]
    for k, name in ((OUTLINE, "outline"), (EYE, "eye"), (SHINE, "shine"), (LIGHT, "light"), (GLOW, "glow")):
        lines.append(f"{k} {SPECIAL[name]}")
    for name, ramp in RAMPS.items():
        for i, color in enumerate(ramp):
            lines.append(f"{KEY[(name, i)]} {color}")
    return "\n".join(lines) + "\n"


def character_text(ch: dict) -> str:
    W, H = ch["size"]
    out = ["pxart 1", "@palette palette.px"]
    for action, facing, n in ACTIONS:
        out.append(f"@anim {action}/{facing} direction=forward ms={MS[action]} pivot={W // 2},{H - 6}")
    out.append("")
    for action, facing, n in ACTIONS:
        for i in range(n):
            out.append(f"@frame {action}/{facing}/{i}")
            out += draw_facing(ch, facing, action, i, n)
            out.append("")
    return "\n".join(out)


# ---- variants and synthetic facings, as the first runs of this bench made them -------------------

def _variant_block(name: str, palette: str, fn) -> str:
    out = [f"@variant {name}"]
    for line in palette.splitlines():
        m = re.match(r"^(\S)\s+#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?\s*$", line.strip())
        if not m:
            continue
        n = int(m.group(2), 16)
        r, g, b = fn((n >> 16) & 255, (n >> 8) & 255, n & 255)
        clamp = lambda v: max(0, min(255, int(round(v))))  # noqa: E731
        out.append(f"{m.group(1)} #{clamp(r):02x}{clamp(g):02x}{clamp(b):02x}{m.group(3) or ''}")
    return "\n".join(out) + "\n"


def with_variants(palette: str) -> str:
    dusk = _variant_block("dusk", palette, lambda r, g, b: (r * 0.55, g * 0.6, b * 0.8 + 24))
    dawn = _variant_block("dawn", palette, lambda r, g, b: (r * 1.0 + 18, g * 0.88 + 6, b * 0.72))
    return palette.rstrip("\n") + "\n\n" + dawn + "\n" + dusk


def _shift(row: str, n: int) -> str:
    return ("." * n + row)[: len(row)] if n >= 0 else (row[-n:] + "." * -n)


TRANSFORMS = {
    "left": lambda rows: [r[::-1] for r in rows],
    "right": lambda rows: [_shift(r[::-1], 1) for r in rows],
    "up": lambda rows: [_shift(r, 2) for r in rows],
}


def add_facings(text: str) -> str:
    """Each one-facing action's down frames copied into up/left/right, with @anim lines to match."""
    lines = text.splitlines()
    frames: dict[str, list[str]] = {}
    anims: dict[str, str] = {}
    cur = None
    for line in lines:
        s = line.strip()
        if s.startswith("@frame "):
            cur = s.split()[1]
            frames[cur] = []
        elif s.startswith("@anim "):
            name, _, rest = s[len("@anim "):].partition(" ")
            anims[name] = " " + rest if rest else ""
            cur = None
        elif s.startswith("@"):
            cur = None
        elif cur is not None and s and not s.startswith("#"):
            frames[cur].append(s)
    extra_anims, extra_frames = [], []
    for action in ONE_FACING:
        group = f"{action}/down"
        ids = [fid for fid in frames if fid.rsplit("/", 1)[0] == group]
        for facing, fn in TRANSFORMS.items():
            settings = anims.get(group, "")
            m = re.search(r"pivot=(\d+),(\d+)", settings)
            if m and facing in ("left", "right"):
                w = len(frames[ids[0]][0])
                px = w - 1 - int(m.group(1)) + (1 if facing == "right" else 0)
                settings = settings.replace(m.group(0), f"pivot={px},{m.group(2)}")
            elif m and facing == "up":
                settings = settings.replace(m.group(0), f"pivot={int(m.group(1)) + 2},{m.group(2)}")
            extra_anims.append(f"@anim {action}/{facing}{settings}")
            for fid in ids:
                extra_frames.append(f"@frame {action}/{facing}/{fid.rsplit('/', 1)[1]}")
                extra_frames += fn(frames[fid])
                extra_frames.append("")
    first = next(i for i, line in enumerate(lines) if line.strip().startswith("@frame "))
    head, tail = lines[:first], lines[first:]
    while head and not head[-1].strip():
        head.pop()
    return "\n".join(head + extra_anims + [""] + tail + [""] + extra_frames) + "\n"


def main(out: Path) -> None:
    base = {"palette.px": palette_text(), **{c["name"] + ".px": character_text(c) for c in CHARACTERS}}
    for scenario in SCENARIOS:
        dest = out / scenario / "cast"
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        n = 0
        for name, text in base.items():
            if name == "palette.px" and scenario != "s300":
                text = with_variants(text)
            elif name != "palette.px" and scenario == "s650v2":
                text = add_facings(text)
            (dest / name).write_text(text)
            n += text.count("\n@frame ")
        print(f"{scenario}: {n} frames in {len(base) - 1} characters")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", type=Path)
    main(ap.parse_args().out)
