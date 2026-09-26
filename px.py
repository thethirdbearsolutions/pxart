#!/usr/bin/env python3
"""px — pixel-art workbench. Sprites are text files; renders are PNGs you can look at.

Sprite format (.px):
    # optional comments
    . transparent          <- palette: one char, then a #rrggbb color or 'transparent'
    k #2b1d2a
    g #6a8a3a
                           <- blank line ends the palette
    ....kkkk....
    ...kggggk...           <- grid: every row the same width, only palette chars

Looking:
    px render a.px [b.px ...] [-o preview.png] [--scale 8] [--no-grid]
        Writes each sprite's 1x PNG next to it, plus a preview sheet with a pixel grid
        and x/y coordinate rulers (every 4px) so you can find columns without counting.
    px sheet FILES... -o sheet.png [--scale 8] [--cols 8] [--grid]
        Compare any mix of .px/.png, labeled with dir/name, WxH and color count.
    px anim f0.px f1.px ... -o walk.gif [--fps 8] [--scale 8]
        Animated GIF, plus walk.strip.png: row 1 = frames in order, row 2 = what changed
        from the previous frame AFTER removing the whole-body shift (label: "shift dx,dy then
        N px"). A walk that is only a bob shows "shift +0,+1 then 0px": legs didn't move.
        Read the strip; the Read tool shows only a GIF's first frame.
    px onion a.px b.px -o x.png [--scale 8]
        b drawn over a faded a: see how far each part moved between two frames.
    px scene -o scene.png [--scale 4] [--size 96x64] [--bg #472d3c] file@x,y ...

Checking:
    px check FILES... [--palette P] [--size 16x16] [--max-colors N]
        Row widths/palette keys (parse), size, colors outside palette P, color count,
        unused palette keys. P is a .px, .gpl, .hex, or any text file of #rrggbb.
        Exit status 1 if anything fails.
    px stats FILES...
        Size, opaque bbox, distinct color count, colors.

Editing (all write .px; -o may equal the input to edit in place):
    px flip IN -o OUT [--v]                    mirror left-right (or top-bottom with --v)
    px shift IN -o OUT --dx N --dy N [--region x,y,w,h]
        Move the whole sprite or one rectangle; vacated pixels become transparent '.'.
    px recolor IN -o OUT a=b [c=#rrggbb ...]
        a=b: repaint key a's pixels as key b.  c=#hex: change key c's color.
    px paste SRC -o OUT --into DST --at x,y [--region x,y,w,h]
        Stamp SRC (or a rectangle of it) onto DST; SRC's transparent pixels don't overwrite.
        Palette keys are merged; conflicting keys are an error.
    px from-png ref.png [-o ref.px]           PNG -> .px so you can read exact pixels
"""
import argparse, pathlib, re, string, sys, warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
from PIL import Image, ImageDraw

CHARS = string.ascii_letters + string.digits + "!@$%&*+=?<>~^"
CLEAR = (0, 0, 0, 0)


class PxError(Exception):
    pass


def hex2rgba(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) if len(h) == 8 else 255)


def rgba2hex(c):
    return "#%02x%02x%02x" % c[:3] + ("%02x" % c[3] if c[3] < 255 else "")


class Sprite:
    def __init__(self, palette, grid, comments=()):
        self.palette, self.grid, self.comments = dict(palette), list(grid), list(comments)

    @property
    def size(self):
        return (len(self.grid[0]), len(self.grid))

    def image(self):
        w, h = self.size
        img = Image.new("RGBA", (w, h))
        img.putdata([self.palette[c] for row in self.grid for c in row])
        return img

    def text(self):
        pal = [f"{k} transparent" if v[3] == 0 else f"{k} {rgba2hex(v)}" for k, v in self.palette.items()]
        return "".join(c + "\n" for c in self.comments) + "\n".join(pal) + "\n\n" + "\n".join(self.grid) + "\n"

    def save(self, path):
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(path).write_text(self.text())

    def clear_key(self):
        for k, v in self.palette.items():
            if v[3] == 0:
                return k
        self.palette["."] = CLEAR
        return "."


def parse_px(path):
    raw = pathlib.Path(path).read_text().splitlines()
    comments = [l for l in raw if l.lstrip().startswith("#")]
    lines = [l.rstrip() for l in raw if not l.lstrip().startswith("#")]
    palette, i = {}, 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    while i < len(lines) and lines[i].strip():
        parts = lines[i].split()
        if len(parts) != 2 or len(parts[0]) != 1:
            raise PxError(f"{path}: palette line {lines[i]!r} must be '<char> <#rrggbb|transparent>' "
                     "(did you forget the blank line between palette and grid?)")
        palette[parts[0]] = CLEAR if parts[1] == "transparent" else hex2rgba(parts[1])
        i += 1
    grid = [l.strip() for l in lines[i:] if l.strip()]
    if not grid:
        raise PxError(f"{path}: no grid rows after palette")
    widths = [len(r) for r in grid]
    if len(set(widths)) > 1:
        expect = max(set(widths), key=lambda w: (widths.count(w), w == widths[0]))
        bad = [f"row {n} is {w} wide: {grid[n]!r}" for n, w in enumerate(widths) if w != expect]
        raise PxError(f"{path}: rows should all be {expect} wide; " + "; ".join(bad))
    for n, row in enumerate(grid):
        unknown = set(row) - set(palette)
        if unknown:
            cols = [x for x, c in enumerate(row) if c in unknown]
            raise PxError(f"{path}: row {n} uses keys not in palette {''.join(sorted(unknown))!r} at x={cols}")
    return Sprite(palette, grid, comments)


def load(path):
    p = str(path)
    return parse_px(p).image() if p.endswith(".px") else Image.open(p).convert("RGBA")


def colors(img):
    return sorted({p for p in img.getdata() if p[3] > 0})


def label(path, common):
    p = pathlib.Path(path).resolve()
    try:
        rel = p.relative_to(common)
    except ValueError:
        rel = pathlib.Path(p.name)
    return str(rel.with_suffix(""))


def common_dir(paths):
    import os
    return pathlib.Path(os.path.commonpath([str(pathlib.Path(p).resolve().parent) for p in paths]))


def upscale(img, scale, grid=False, rulers=False):
    big = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    if not grid or scale < 4:
        return big
    ov = Image.new("RGBA", big.size, CLEAR)
    d = ImageDraw.Draw(ov)
    for x in range(1, img.width):
        d.line([(x * scale, 0), (x * scale, big.height)], fill=(255, 255, 255, 70 if x % 4 == 0 else 22))
    for y in range(1, img.height):
        d.line([(0, y * scale), (big.width, y * scale)], fill=(255, 255, 255, 70 if y % 4 == 0 else 22))
    big.alpha_composite(ov)
    if not rulers:
        return big
    m = 16
    out = Image.new("RGBA", (big.width + m, big.height + m), CLEAR)
    out.alpha_composite(big, (m, m))
    d = ImageDraw.Draw(out)
    for x in range(0, img.width, 4):
        d.text((m + x * scale + 2, 2), str(x), fill=(255, 210, 90, 255))
    for y in range(0, img.height, 4):
        d.text((1, m + y * scale + 2), str(y), fill=(255, 210, 90, 255))
    return out


def sheet(paths, out, scale=8, cols=8, bg="#3a3a44", grid=False, rulers=False):
    common = common_dir(paths)
    imgs = [(label(p, common), load(p)) for p in paths]
    tiles = [(name, img, upscale(img, scale, grid, rulers)) for name, img in imgs]
    cw = max(t.width for _, _, t in tiles)
    ch = max(t.height for _, _, t in tiles)
    pad, lab = 10, 26
    cols = min(cols, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    s = Image.new("RGBA", (pad + cols * (cw + pad), pad + rows * (ch + lab + pad)), (30, 30, 36, 255))
    d = ImageDraw.Draw(s)
    for n, (name, img, big) in enumerate(tiles):
        x, y = pad + (n % cols) * (cw + pad), pad + (n // cols) * (ch + lab + pad)
        d.rectangle([x, y, x + cw - 1, y + ch - 1], fill=hex2rgba(bg))
        s.alpha_composite(big, (x + (cw - big.width) // 2, y + ch - big.height))
        s.alpha_composite(img, (x + cw - img.width - 2, y + ch + 4))  # 1x inset beside the label
        d.text((x, y + ch + 2), name, fill=(220, 220, 220, 255))
        d.text((x, y + ch + 13), f"{img.width}x{img.height} {len(colors(img))}c", fill=(150, 150, 160, 255))
    s.save(out)
    return out


def on_bg(img, w, h, bg="#3a3a44"):
    b = Image.new("RGBA", (w, h), hex2rgba(bg))
    b.alpha_composite(img, ((w - img.width) // 2, h - img.height))
    return b


def shifted(img, dx, dy):
    out = Image.new("RGBA", img.size, CLEAR)
    out.alpha_composite(img, (0, 0)) if (dx, dy) == (0, 0) else out.paste(img, (dx, dy))
    return out


def best_shift(prev, cur, reach=2):
    """The whole-sprite (dx, dy) that best explains cur as a moved prev: i.e. the body bob."""
    best = None
    cd = list(cur.getdata())
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            n = sum(1 for a, b in zip(shifted(prev, dx, dy).getdata(), cd) if a != b)
            key = (n, abs(dx) + abs(dy))
            if best is None or key < best[0]:
                best = (key, dx, dy)
    return best[1], best[2]


def diff_frame(prev, cur):
    """cur dimmed, with pixels that differ from prev in magenta."""
    out = Image.new("RGBA", cur.size, CLEAR)
    pp, cp = prev.load(), cur.load()
    for y in range(cur.height):
        for x in range(cur.width):
            a, b = pp[x, y], cp[x, y]
            if a != b:
                out.putpixel((x, y), (255, 40, 200, 255))
            elif b[3]:
                out.putpixel((x, y), (b[0] // 3, b[1] // 3, b[2] // 3, 255))
    return out


def load_palette(path):
    p = str(path)
    if p.endswith(".px"):
        return {c[:3] for c in parse_px(p).palette.values() if c[3]}
    text = pathlib.Path(p).read_text()
    if p.endswith(".gpl"):
        cols = set()
        for line in text.splitlines():
            m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d+)", line)
            if m:
                cols.add(tuple(int(v) for v in m.groups()))
        return cols
    return {hex2rgba(h)[:3] for h in re.findall(r"#?\b([0-9a-fA-F]{6})\b", text)}


def parse_rect(s, sprite):
    if not s:
        w, h = sprite.size
        return 0, 0, w, h
    return tuple(int(v) for v in s.split(","))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render"); r.add_argument("files", nargs="+"); r.add_argument("-o", default="preview.png")
    r.add_argument("--scale", type=int, default=8); r.add_argument("--bg", default="#3a3a44")
    r.add_argument("--no-grid", action="store_true")
    s = sub.add_parser("sheet"); s.add_argument("files", nargs="+"); s.add_argument("-o", required=True)
    s.add_argument("--scale", type=int, default=8); s.add_argument("--cols", type=int, default=8)
    s.add_argument("--bg", default="#3a3a44"); s.add_argument("--grid", action="store_true")
    a = sub.add_parser("anim"); a.add_argument("files", nargs="+"); a.add_argument("-o", required=True)
    a.add_argument("--fps", type=int, default=8); a.add_argument("--scale", type=int, default=8)
    o = sub.add_parser("onion"); o.add_argument("a"); o.add_argument("b"); o.add_argument("-o", required=True)
    o.add_argument("--scale", type=int, default=8)
    c = sub.add_parser("scene"); c.add_argument("specs", nargs="+"); c.add_argument("-o", required=True)
    c.add_argument("--scale", type=int, default=4); c.add_argument("--bg", default="#472d3c")
    c.add_argument("--size", default="96x64", help="scene size in 1x pixels, WxH")
    k = sub.add_parser("check"); k.add_argument("files", nargs="+"); k.add_argument("--palette")
    k.add_argument("--size"); k.add_argument("--max-colors", type=int)
    t = sub.add_parser("stats"); t.add_argument("files", nargs="+")
    fl = sub.add_parser("flip"); fl.add_argument("src"); fl.add_argument("-o", required=True)
    fl.add_argument("--v", action="store_true")
    sh = sub.add_parser("shift"); sh.add_argument("src"); sh.add_argument("-o", required=True)
    sh.add_argument("--dx", type=int, default=0); sh.add_argument("--dy", type=int, default=0)
    sh.add_argument("--region")
    rc = sub.add_parser("recolor"); rc.add_argument("src"); rc.add_argument("maps", nargs="+")
    rc.add_argument("-o", required=True)
    pa = sub.add_parser("paste"); pa.add_argument("src"); pa.add_argument("-o", required=True)
    pa.add_argument("--into", required=True); pa.add_argument("--at", required=True); pa.add_argument("--region")
    f = sub.add_parser("from-png"); f.add_argument("png"); f.add_argument("-o")
    args = ap.parse_args()

    if args.cmd == "render":
        for p in args.files:
            if str(p).endswith(".px"):
                load(p).save(pathlib.Path(p).with_suffix(".png"))
        print("wrote", sheet(args.files, args.o, args.scale, bg=args.bg,
                             grid=not args.no_grid, rulers=not args.no_grid))
    elif args.cmd == "sheet":
        print("wrote", sheet(args.files, args.o, args.scale, args.cols, args.bg, grid=args.grid))
    elif args.cmd == "anim":
        frames = [load(p) for p in args.files]
        w, h = max(f.width for f in frames), max(f.height for f in frames)
        framed = [on_bg(f, w, h) for f in frames]
        gif = [f.resize((w * args.scale, h * args.scale), Image.NEAREST).convert("P", palette=Image.ADAPTIVE)
               for f in framed]
        gif[0].save(args.o, save_all=True, append_images=gif[1:], duration=1000 // args.fps, loop=0, disposal=2)
        pad, lab = 8, 14
        n = len(framed)
        strip = Image.new("RGBA", (pad + n * (w * args.scale + pad), pad + 2 * (h * args.scale + lab + pad)),
                          (30, 30, 36, 255))
        d = ImageDraw.Draw(strip)
        common = common_dir(args.files)
        for i, fr in enumerate(framed):
            x = pad + i * (w * args.scale + pad)
            strip.alpha_composite(upscale(fr, args.scale, grid=True), (x, pad))
            d.text((x, pad + h * args.scale + 1), label(args.files[i], common), fill=(220, 220, 220, 255))
            prev, cur = frames[i - 1], frames[i]
            dx, dy = best_shift(prev, cur)
            moved = shifted(prev, dx, dy)
            y2 = pad * 2 + h * args.scale + lab
            strip.alpha_composite(upscale(on_bg(diff_frame(moved, cur), w, h, "#1e1e24"), args.scale, grid=True), (x, y2))
            changed = sum(1 for a, b in zip(moved.getdata(), cur.getdata()) if a != b)
            d.text((x, y2 + h * args.scale + 1), f"shift {dx:+d},{dy:+d} then {changed}px", fill=(255, 120, 220, 255))
        sp = pathlib.Path(args.o).with_suffix(".strip.png")
        strip.save(sp)
        print("wrote", args.o, "and", sp)
    elif args.cmd == "onion":
        A, B = load(args.a), load(args.b)
        w, h = max(A.width, B.width), max(A.height, B.height)
        base = on_bg(Image.new("RGBA", (1, 1), CLEAR), w, h)
        faded = A.copy(); faded.putalpha(A.getchannel("A").point(lambda v: v * 35 // 100))
        base.alpha_composite(faded, ((w - A.width) // 2, h - A.height))
        top = B.copy(); top.putalpha(B.getchannel("A").point(lambda v: v * 80 // 100))
        base.alpha_composite(top, ((w - B.width) // 2, h - B.height))
        upscale(base, args.scale, grid=True, rulers=True).save(args.o)
        print("wrote", args.o)
    elif args.cmd == "scene":
        W, H = map(int, args.size.split("x"))
        sc = Image.new("RGBA", (W, H), hex2rgba(args.bg))
        for spec in args.specs:
            path, _, xy = spec.rpartition("@")
            x, y = map(int, xy.split(","))
            sc.alpha_composite(load(path), (x, y))
        sc.resize((W * args.scale, H * args.scale), Image.NEAREST).save(args.o)
        print("wrote", args.o)
    elif args.cmd == "check":
        allowed = load_palette(args.palette) if args.palette else None
        want = tuple(map(int, args.size.split("x"))) if args.size else None
        failed = False
        for p in args.files:
            probs, notes = [], []
            try:
                img = load(p)
            except PxError as e:
                failed = True
                print(f"FAIL {e}")
                continue
            if want and img.size != want:
                probs.append(f"size {img.width}x{img.height} != {want[0]}x{want[1]}")
            cs = colors(img)
            if allowed is not None:
                off = [rgba2hex(c) for c in cs if c[:3] not in allowed]
                if off:
                    probs.append("off-palette " + " ".join(off))
            if args.max_colors and len(cs) > args.max_colors:
                probs.append(f"{len(cs)} colors > {args.max_colors}")
            if str(p).endswith(".px"):
                spr = parse_px(p)
                used = set("".join(spr.grid))
                unused = [k for k, v in spr.palette.items() if k not in used and v[3]]
                if unused:
                    notes.append("unused keys " + "".join(unused))
            failed |= bool(probs)
            print(f"{'FAIL' if probs else 'ok  '} {p}: {img.width}x{img.height} {len(cs)}c"
                  + "".join(f"; {x}" for x in probs + notes))
        sys.exit(1 if failed else 0)
    elif args.cmd == "stats":
        for p in args.files:
            img = load(p)
            cs = colors(img)
            print(f"{p}: {img.width}x{img.height} bbox={img.getchannel('A').getbbox()} colors={len(cs)} "
                  + " ".join(rgba2hex(c) for c in cs[:32]))
    elif args.cmd == "flip":
        spr = parse_px(args.src)
        spr.grid = spr.grid[::-1] if args.v else [row[::-1] for row in spr.grid]
        spr.save(args.o); print("wrote", args.o)
    elif args.cmd == "shift":
        spr = parse_px(args.src)
        clear = spr.clear_key()
        x0, y0, w, h = parse_rect(args.region, spr)
        W, H = spr.size
        g = [list(r) for r in spr.grid]
        block = [[g[y][x] for x in range(x0, x0 + w)] for y in range(y0, y0 + h)]
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                g[y][x] = clear
        for y in range(h):
            for x in range(w):
                tx, ty = x0 + x + args.dx, y0 + y + args.dy
                if 0 <= tx < W and 0 <= ty < H and spr.palette[block[y][x]][3]:
                    g[ty][tx] = block[y][x]
        spr.grid = ["".join(r) for r in g]
        spr.save(args.o); print("wrote", args.o)
    elif args.cmd == "recolor":
        spr = parse_px(args.src)
        for m in args.maps:
            a, _, b = m.partition("=")
            if a not in spr.palette:
                sys.exit(f"recolor: key {a!r} not in palette")
            if b.startswith("#") or b == "transparent":
                spr.palette[a] = CLEAR if b == "transparent" else hex2rgba(b)
            else:
                if b not in spr.palette:
                    sys.exit(f"recolor: key {b!r} not in palette")
                spr.grid = [row.replace(a, b) for row in spr.grid]
        spr.save(args.o); print("wrote", args.o)
    elif args.cmd == "paste":
        src, dst = parse_px(args.src), parse_px(args.into)
        for key, col in src.palette.items():
            if key in dst.palette and dst.palette[key] != col and col[3]:
                sys.exit(f"paste: key {key!r} is {rgba2hex(col)} in src but {rgba2hex(dst.palette[key])} in dst; "
                         "recolor one first")
            if col[3]:
                dst.palette.setdefault(key, col)
        x0, y0, w, h = parse_rect(args.region, src)
        ax, ay = map(int, args.at.split(","))
        W, H = dst.size
        g = [list(r) for r in dst.grid]
        for y in range(h):
            for x in range(w):
                ch = src.grid[y0 + y][x0 + x]
                tx, ty = ax + x, ay + y
                if src.palette[ch][3] and 0 <= tx < W and 0 <= ty < H:
                    g[ty][tx] = ch
        dst.grid = ["".join(r) for r in g]
        dst.save(args.o); print("wrote", args.o)
    elif args.cmd == "from-png":
        img = load(args.png)
        pal = {CLEAR: "."}
        for col in colors(img):
            if len(pal) > len(CHARS):
                sys.exit(f"{args.png}: too many colors ({len(colors(img))}) for .px text")
            pal[col] = CHARS[len(pal) - 1]
        spr = Sprite({v: k for k, v in pal.items()},
                     ["".join(pal[p] if p[3] else "." for p in [img.getpixel((x, y)) for x in range(img.width)])
                      for y in range(img.height)])
        spr.save(args.o) if args.o else print(spr.text(), end="")
        if args.o:
            print("wrote", args.o)


if __name__ == "__main__":
    try:
        main()
    except PxError as e:
        sys.exit(str(e))
