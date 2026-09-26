#!/usr/bin/env python3
"""pxart: pixel art as text. Sprites are text files; renders are PNGs you can look at.

FORMAT (.px)
    # comments start with '#'
    pxart 1                  optional version line (first non-comment line)
    @palette base.px         optional: import palette keys from another .px file
    k #3f2631                palette: one key char, then #rrggbb, #rrggbbaa, or 'transparent'
    g #43e1b3                ('.' is always transparent; you may omit it)

    ....kkkk....             grid rows: all the same width, only palette keys.
    ...kggggk...             The sprite's size is the grid's size: nothing to count.

  Several frames per file: name each grid with @frame; the id is a path, and frames
  sharing a parent path form an animation (walk/down/0, walk/down/1 -> "walk/down"):
    @anim walk/down direction=forward repeat=0 ms=125
    @frame walk/down/0
    ....kkkk....
    @frame walk/down/1 ms=250          per-frame duration overrides the anim's
    ...
  An animation plays its frames in file order (not by the number in the id).
  direction: forward | reverse | pingpong | pingpong_reverse (Aseprite's words).
  repeat: 0 or absent = loop forever; N = play N times. ms: default frame duration.
  'anim-set hero.px:walk/down ms=125' writes these (and 'hero.px:walk/down/1 ms=250' a frame's).
  Frame groups that aren't animations (UI icons, a parts file): '@still ui/life' keeps them
  out of animation exports and checks; '@still *' marks every frame in the file, top-level
  ids with no '/' included (a parts file). Top-level ids are never animated anyway; '@still *'
  also lists them as 'still' in frames.
  Palette variants (recolors): keys listed after '@variant night' override the base
  palette. Variants in a @palette file are inherited; local keys (and local variant keys)
  override imported ones, and check notes the override.

  Anywhere a command takes FILE, FILE:SEL picks frames: SEL is a frame id or a parent
  path (FILE:walk/down = every walk/down/* frame). No SEL means every frame. Add
  %VARIANT to render with a variant: FILE:idle/0%night. In zsh, "$F:walk" is read as a
  modifier; write "${F}:walk" or quote the whole argument. A missing input whose name has
  letters glued to .px/.png (hero.pxalk/0, hero.pxidle) is reported as that mistake.
  An output under a path that is a file (-o hero.px/walk/0) is E_FILE, not a crash.

LOOKING
  render FILE... [-o preview.png] [--scale 8] [--no-grid] [--variant V] [--png]
      Preview sheet with a pixel grid and x/y rulers every 4px. --png also writes a 1x
      PNG beside each single-frame .px.
  sheet FILE... -o sheet.png [--scale 8] [--cols 8] [--grid] [--variant V]
      Compare any mix of .px/.png frames, labeled with id, WxH and color count.
  anim FILE... -o walk.gif [--scale 8] [--fps N] [--variant V]
      GIF (with 1x and 2x copies alongside), plus walk.strip.png: row 1 = frames,
      row 2 = what changed from the previous frame after removing the whole-sprite
      shift ("shift dx,dy then N px (no shift: M px)"; a walk that's only a bob shows
      "then 0px"). When the bottom of the sprite stays put and only the part above it
      moves (an idle breathing: chest up 1px, legs still), moving the whole sprite would
      light up the legs, so the strip shows the unshifted diff instead:
      "no shift then M px (rows Y+ still; shift dx,dy: N px)". Both counts are always shown.
      Read the strip; the Read tool shows only a GIF's first frame. The same numbers print
      to stdout, one line per frame. Durations come from the file (@anim/@frame ms)
      unless --fps is given.
  onion A B -o x.png [--scale 8]    B drawn over a faded A
  scene -o s.png [--scale 4] [--size WxH] [--bg #472d3c] [--map M --tile 16x16] [--variant V]
        [--tint #rrggbbaa] ITEM@x,y ...
      ITEM is FILE[:frame][%variant][+h|+v|+hv]: +h mirrors it left-right, +v top-bottom
      (hero.px:walk/0+h@3,4 walks the other way; '+' needs no quoting in bash or zsh,
      where '!' would be history expansion). Map legend entries (which also take +b, see
      Placement) and compose layers take +h/+v too. --map draws a text tilemap first:
      legend lines '<char> <FILE[:frame][%variant]>', a blank line, then rows of legend
      chars ('.' = empty). In a legend line the rest of the line is the path, relative to
      the map file: spaces are fine ('b ../png/trees and bushes/bush.png'), "quotes"
      optional. check and scene load every legend entry; one that can't load is an
      error at its legend line.
      Items are then drawn on top. '#' lines are comments only before the first row;
      after that every non-blank line is a row, so '#' works as a map char (a wall row
      '####'). Before the rows, a line that is exactly
      '# FILE.px[:frame][%variant]' or '# FILE.png' (one token after '#', no spaces) is the
      legend line for '#', not a comment, and so is a quoted path ('# "my tiles/wall.png"');
      check and scene print a note for it. Any other line starting with '#' is a comment
      ('# see wall.px' too).
      Layers (a tile and a sprite in one cell): a line '---' after the rows starts another
      grid of rows over the same legend. Layers draw in order, later over earlier, and '.'
      is empty in each; the map is as big as its widest row and tallest layer.
      Placement: a map item draws with its top-left at its cell's top-left (column * tile
      w, row * tile h), so a 32x32 stall on 16x16 tiles hangs right and down over the next
      cells.
      A legend entry ending in +b (with flips: +hb, +vb, +hvb) draws bottom-aligned to its
      cell and centered across it, odd pixel left: x = cell x + (tile w - w) // 2,
      y = cell y + tile h - h. A tall lamp then stands on its cell and rises into the row
      above (cut off at the top edge on row 0). +b is for legend entries only.
      A worked map, market.map, on 16x16 tiles (tiles.px:cobble, :water/0 and :crate are
      16x16, stall.px is 32x32, lamp.px is 16x32):
          # ground layer, then props
          c tiles.px:cobble
          w tiles.px:water/0
          x tiles.px:crate+h
          S stall.px+b
          L lamp.px+b
          l lamp.px+hb

          cccccc
          cccccc
          wwwwww
          ---
          ......
          .S.L.l
          x.....
      'pxart scene --map market.map -o market.png' is 96x48: cobbles and water, then the
      props over them. The stall's cell is 16,16, so it draws at 16 + (16-32)//2,
      16 + 16 - 32 = 8,0; the lamps at 48,0 and 80,0 (mirrored); the crate, mirrored, at its
      cell's top-left, 0,32.
      --variant V renders every map tile and .px item with V (a whole dark room), except
      those with their own %variant, which wins; a .px without V is an E_SELECT error.
      Items and legend entries can be PNGs (hero.png@3,4). x,y may be negative (drawn
      partly off the left/top edge), in scene and in compose.
      --tint '#10183080' lays that color, at its alpha, over the whole finished scene (bg,
      map, every item, those with their own %variant too) at 1x, before --scale: a night
      scene in one step. To keep a light bright, render the scene untinted, mask the lit
      circle out of it, and put that PNG over the tinted one. Quote the color in scripts
      (an unquoted word starting with # is a comment there); the '#' may be left off.
  tint IN.png '#rrggbbaa' [-o OUT.png]
      The same on a PNG (a rendered scene); each pixel keeps its alpha, so transparent
      pixels stay transparent. Without -o, IN is rewritten.
  Centering: frames of different sizes are bottom-aligned and centered, with the odd
  pixel going left (x = (canvas - frame) // 2). --bg works on render, sheet and scene.

CHECKING
  check FILE... [--palette P] [--size WxH] [--max-colors N] [--strict]
      Every format error with a code and location, then size / off-palette colors /
      color budget / unused keys per frame. P is a .px, .gpl, .hex, or text of
      #rrggbb. --strict also rejects unknown @sections. Exit 1 on any failure.
      A .map (scene --map) is checked too: every row char has a legend line and every
      legend entry loads as one frame (errors point at the legend line).
      Non-ASCII chars that look like ASCII (Cyrillic/Greek 'а е о р с х у', fullwidth
      'ｋ') get a note naming the line, row and column and the letter they pass for.
  stats FILE...                     size, bbox, color count, colors per frame
  frames FILE[:SEL] [--rm [ID...]] [--move ID --after|--before ID]
      List frames, sizes, durations ('still' for @still groups; every frame under
      '@still *') and animations; or delete / reorder frames (prints what it removed or
      moved, not the listing). FILE:SEL lists only those frames; 'frames hero.px:walk/left
      --rm' removes them (ids after --rm must be in SEL), and 'frames hero.px:walk/left
      --after idle/3' moves them there as a block, in order. --move ID takes a plain FILE.

EDITING (writes .px; -o defaults to editing the input in place)
  -o OUT always gets the whole file: with FILE:SEL, OUT is a copy of FILE with the selected
  frames edited and every other frame as it was (like editing a copy), and a note says so.
  To get only some frames, extract them first (or after).
  Edits rewrite only what changed: other lines keep their spelling and the blank lines and
  comments above them, and new frames get the file's spacing between @frame blocks.
  An edit that changes nothing (set to the same key, flip of a symmetric frame) prints
  "no change: FILE" and leaves the file untouched.
  Limits: sections are written in a fixed order (palette, @variant, @anim/@still, frames,
  unknown @sections), so an @anim written between frames moves up; a comment inside the
  file stays with the line below it and goes when that line goes (a removed frame, cut rows).
  flip FILE [-o OUT] [--v]          mirror selected frames left-right (--v: top-bottom)
  shift FILE [-o OUT] --dx N --dy N [--region x,y,w,h] [--wrap]
      --wrap scrolls pixels around the edges (for animating tiles) instead of dropping them.
  set FILE[:frame] KEY x,y [x,y ...] [-o OUT]    paint single pixels ('.' erases)
  fill FILE[:frame] KEY [--region x,y,w,h] [-o OUT]   paint a rectangle (default: the frame)
  new OUT[:frame] --size WxH [--key K] [--palette P.px]
      A blank frame ('.'), or one filled with K, in a new file or added to an existing one
      (placed like compose). --palette P.px starts a new OUT that imports P. A frame that
      already exists is E_DUP_FRAME: fill it instead.
  mask FILE[:frame] --keep x,y,w,h | --keep-circle cx,cy,r [--dither N] [--invert] [-o OUT]
      Erase (set to '.') every pixel outside the rectangle or circle (kept: distance from
      the pixel to cx,cy <= r). --dither N fades the circle's last N px inside its edge
      with a 4x4 ordered (Bayer) dither: a light radius in one command. --invert erases
      the inside and keeps the outside: exactly the pixels the plain mask erases, dither
      band mirrored, so a mask and its --invert split the image with no overlap or gap.
      FILE may be a PNG (a rendered scene; no render -> from-png round trip): outside
      pixels become transparent. Coordinates are the PNG's own pixels, so render the scene
      with --scale 1. -o, if given, must be a .png too.
  crop FILE:frame x,y,w,h -o OUT[:frame]         cut a rectangle out into a new frame
  extract FILE:SEL -o OUT
      Write only the selected frames to OUT (replacing it), with FILE's palette, @palette
      imports (re-pointed relative to OUT), variants, and @anim/@still lines (minus those
      of groups left behind): 'extract hero.px:walk/down -o walk.px'.
  recolor FILE a=b ['a<>b'] [c=#rrggbb] [-o OUT] [--region x,y,w,h]
      a=b repaints key a's pixels as key b (optionally only inside --region); 'a<>b' swaps
      keys a and b (in the region) in one step; quote it, since unquoted < and > are shell
      redirections. c=#hex changes key c's color everywhere. '.' works as a source key.
      Order: the key moves of one call apply together, each pixel by the key it had before
      the call, so no move feeds another: 'a<>b' c=a turns a's pixels to b and b's and c's
      to a, and a=b b=a is a swap too. A key moved twice is E_BAD_ARG. Color changes set
      the palette and don't move pixels, so c=#hex and c=d can share a call.
  paste SRC --into DST[:frame] --at x,y [--region x,y,w,h] [-o OUT]
  compose -o OUT[:frame] [--size WxH] LAYER@x,y [LAYER@x,y ...]
      Stack single frames (later layers on top; '.' never overwrites) into one frame.
      Layers can be frames of one parts file: parts.px:hat@3,0 parts.px:body@0,8.
      The output keeps its own palette and @palette; each layer's keys are added to it
      unless the key already exists with the same color (a different color is
      E_KEY_CONFLICT).
      With OUT:frame, adds or replaces that frame in OUT and keeps its other frames
      (OUT may be a palette-only file). A new frame goes after the last frame of its
      animation (like dup), or at the end when the animation is new. Canvas size: --size, else the frame being
      replaced, else the other frames of its animation, else the first layer. Pixels
      that land outside the canvas are cropped, with a note saying how many.
      compose and dup note an output path that doesn't end in .px (zsh "$OUT:frame").
  dup FILE:ID NEWID [--after ID] [-o OUT]
      Copy a frame under a new id, placed after the last frame of NEWID's animation, or
      when that animation is new, after the source's whole animation (or after --after).
      A new animation inherits the source animation's @anim timing. Then edit the copy.
  anim-set FILE:GROUP [ms=N] [direction=D] [repeat=N] [-o OUT]
      Write timing: updates the '@anim GROUP' line, or adds one after the other @anim lines.
      FILE:GROUP/ID (one frame) takes only ms=N and sets that frame's own duration
      ('@frame ID ms=N'), which wins over the group's. KEY= with no value clears a setting.
      A path that is both a group and a frame means the group. Only that one line changes.
  palette FILE [--add k=#hex ...] [--export out.gpl|out.hex [--used]]

CONVERTING
  export FILE [--frames DIR] [--aseprite sheet.json] [--tiled tiles.tsj] [--variant V]
      --frames: one PNG per frame at DIR/<frame id>.png
      --aseprite: sheet PNG + Aseprite-style JSON (frames, durations, frameTags)
      --tiled: sheet PNG + Tiled tileset JSON with per-tile animations
      (--aseprite x.json and --tiled x.tsj share one identical x.png)
  from-png A.png [B.png ...] [-o OUT.px] [--id PREFIX]
      PNG -> .px with exact pixels. One PNG and no --id: a single unnamed grid.
      Several PNGs, --id, or an existing OUT: frames named PREFIX/<png stem>, added
      to OUT (replacing same-id frames). Colors already in OUT keep their keys, so
      frames imported in separate runs share one palette. --palette P.px starts a new
      OUT that imports P and reuses its keys.

ERROR CODES
  E_VERSION E_BAD_KEY E_DOT_RESERVED E_BAD_COLOR E_DUP_KEY E_PALETTE_AFTER_GRID
  E_PALETTE_FILE E_BAD_ROW E_ROW_WIDTH E_UNKNOWN_KEY E_EMPTY_FRAME E_NO_FRAMES
  E_BAD_ID E_DUP_FRAME E_MIXED_FRAMES E_BAD_ARG E_VARIANT_KEY E_UNKNOWN_SECTION
  E_SELECT E_KEY_CONFLICT E_TILE_SIZE E_FILE
  Frames of different sizes in one animation are allowed; check notes them.
"""
import argparse, json, math, os, pathlib, re, string, sys, unicodedata
from PIL import Image, ImageDraw

FORMAT_VERSION = 1
CLEAR = (0, 0, 0, 0)
DEFAULT_MS = 100
# Keys: printable ASCII minus whitespace and chars with a job ('#' comment, '@' section,
# '.' transparent) or that break XPM export ('"', '\').
KEYS = [c for c in string.ascii_letters + string.digits + string.punctuation if c not in '#@."\\']
DIRECTIONS = ("forward", "reverse", "pingpong", "pingpong_reverse")
ID_RE = re.compile(r"^[A-Za-z0-9_\-.]+(/[A-Za-z0-9_\-.]+)*$")
COLOR_RE = re.compile(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
PAL_RE = re.compile(r"^(\S)\s+(\S+)$")
PAL_SKIP = "\n     (unknown-key checks were skipped: those keys may come from this palette)"


# ---------------------------------------------------------------------------- errors

class Issue:
    def __init__(self, code, msg, path=None, line=None, frame=None, row=None, cols=None):
        self.code, self.msg, self.path, self.line = code, msg, path, line
        self.frame, self.row, self.cols = frame, row, cols

    def __str__(self):
        where = str(self.path or "")
        if self.line:
            where += f":{self.line}"
        loc = []
        if self.frame:
            loc.append(f"frame {self.frame}")
        if self.row is not None:
            loc.append(f"row {self.row}")
        if self.cols:
            loc.append(f"x={self.cols}")
        return f"{where}: {self.code}" + (f" ({', '.join(loc)})" if loc else "") + f": {self.msg}"


class PxError(Exception):
    def __init__(self, issues):
        self.issues = issues if isinstance(issues, list) else [issues]
        super().__init__("\n".join(str(i) for i in self.issues))


def fail(code, msg, **kw):
    raise PxError(Issue(code, msg, **kw))


# ---------------------------------------------------------------------------- model

def hex2rgba(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) if len(h) == 8 else 255)


def rgba2hex(c):
    return "#%02x%02x%02x" % c[:3] + ("%02x" % c[3] if c[3] < 255 else "")


def fmt_color(c):
    return "transparent" if c[3] == 0 else rgba2hex(c)


class Frame:
    def __init__(self, id, grid=None, ms=None, line=None):
        self.id, self.grid, self.ms, self.line = id, grid if grid is not None else [], ms, line
        self.row_lines = []

    @property
    def size(self):
        return (len(self.grid[0]) if self.grid else 0, len(self.grid))

    @property
    def group(self):
        return self.id.rsplit("/", 1)[0] if self.id and "/" in self.id else ""


class Doc:
    def __init__(self, path=None):
        self.path = pathlib.Path(path) if path else None
        self.version = None
        self.comments = []
        self.palette_refs = []      # @palette paths, as written
        self.shared = {}            # keys imported through @palette
        self.palette = {}           # keys defined in this file (order kept)
        self.variants = {}          # name -> {key: rgba}
        self.shared_variants = {}   # variants imported through @palette
        self.anims = {}             # group -> {"direction", "repeat", "ms"}
        self.stills = []            # groups marked @still: grouped, not animated
        self.frames = []
        self.implicit = False       # one unnamed grid, no @frame
        self.extensions = []        # unknown @sections kept verbatim (lenient mode)
        # Source layout, so an edit rewrites only what changed (see text()).
        self.lead = {}              # anchor -> blank/comment lines just above that line
        self.raw = {}               # anchor -> (line as text() writes it, line as the file had it)
        self.tail = []              # blank/comment lines after the last line
        self.dot_at = None          # where a '. transparent' line sat among the palette keys
        self.frame_gap = None       # blank lines the file puts between @frame blocks
        self.newline, self.final_newline = "\n", True

    @property
    def stem(self):
        return self.path.stem if self.path else "sprite"

    def resolved(self, variant=None):
        pal = {".": CLEAR}
        pal.update(self.shared)
        pal.update(self.palette)
        if variant:
            if variant not in self.variants and variant not in self.shared_variants:
                have = sorted(set(self.variants) | set(self.shared_variants))
                fail("E_SELECT", f"no @variant {variant!r} (have: {', '.join(have) or 'none'})", path=self.path)
            pal.update(self.shared_variants.get(variant, {}))
            pal.update(self.variants.get(variant, {}))
        return pal

    def animated(self, group):
        """Groups are animations unless marked @still (and the ungrouped top level never is)."""
        return bool(group) and group not in self.stills and "*" not in self.stills

    def still(self, group):
        """Marked still: a @still group, or any frame at all (top-level ones too) under '@still *'."""
        return not self.animated(group) and (bool(group) or "*" in self.stills)

    def label(self, f):
        return f.id if f.id else self.stem

    def ms(self, f):
        return f.ms or self.anims.get(f.group, {}).get("ms") or DEFAULT_MS

    def select(self, sel):
        if not sel:
            return list(self.frames)
        got = [f for f in self.frames if f.id == sel or (f.id or "").startswith(sel + "/")]
        if not got:
            fail("E_SELECT", f"no frame {sel!r}; frames: {', '.join(self.label(f) for f in self.frames)}",
                 path=self.path)
        return got

    def get(self, fid):
        for f in self.frames:
            if f.id == fid:
                return f
        return None

    def groups(self, frames=None):
        out = {}
        for f in self.frames if frames is None else frames:
            out.setdefault(f.group, []).append(f)
        return out

    def image(self, f, variant=None):
        pal = self.resolved(variant)
        w, h = f.size
        img = Image.new("RGBA", (w, h))
        img.putdata([pal[c] for row in f.grid for c in row])
        return img

    def add_key(self, key, color):
        """Make key available with this color; error if it already means something else."""
        have = self.resolved()
        if key in have:
            if have[key] != color and not (key == "." and color[3] == 0):
                fail("E_KEY_CONFLICT", f"key {key!r} is {fmt_color(have[key])} here, not {fmt_color(color)}; "
                     "recolor one side first", path=self.path)
            return
        if key not in KEYS:
            fail("E_BAD_KEY", f"{key!r} can't be a palette key", path=self.path)
        self.palette[key] = color

    def lines(self):
        """(anchor, default blank lines above, line) in the order text() writes them."""
        if self.version is not None:
            yield "version", 0, f"pxart {self.version}"
        for r in self.palette_refs:
            yield ("palref", r), 0, f"@palette {r}"
        keys = [(k, f"{k} {fmt_color(v)}") for k, v in self.palette.items()]
        if self.dot_at is not None:
            keys.insert(self.dot_at, (".", ". transparent"))
        for k, line in keys:
            yield ("key", k), 0, line
        for name, over in self.variants.items():
            yield ("variant", name), 1, f"@variant {name}"
            for k, v in over.items():
                yield ("vkey", name, k), 0, f"{k} {fmt_color(v)}"
        for i, (g, a) in enumerate(self.anims.items()):
            parts = [f"@anim {g}"] + [f"{k}={a[k]}" for k in ("direction", "repeat", "ms") if a.get(k) is not None]
            yield ("anim", g), int(i == 0), " ".join(parts)
        for i, g in enumerate(self.stills):
            yield ("still", g), int(i == 0 and not self.anims), f"@still {g}"
        for i, f in enumerate(self.frames):
            if not self.implicit:
                gap = 1 if i == 0 or self.frame_gap is None else self.frame_gap
                yield ("frame", f.id), gap, f"@frame {f.id}" + (f" ms={f.ms}" if f.ms else "")
            for j, row in enumerate(f.grid):
                yield ("row", f.id, j), int(self.implicit and j == 0), row
        for i, e in enumerate(self.extensions):
            yield ("ext", i), int(i == 0), e

    def text(self):
        """The file. Lines the file already had keep their spelling and the blank lines and comments
        above them; new lines follow the file's frame spacing (or the defaults)."""
        out = list(self.comments)
        for anchor, gap, line in self.lines():
            lead = self.lead.get(anchor)
            out += lead if lead is not None else [""] * gap if out else []
            was = self.raw.get(anchor)
            out.append(was[1] if was and was[0] == line else line)
        out += self.tail
        return self.newline.join(out) + (self.newline if self.final_newline else "")

    def save(self, path=None):
        path = outpath(path or self.path)
        with open(path, "w", newline="") as fh:  # the file's own line endings, untranslated
            fh.write(self.text())
        return path


# ---------------------------------------------------------------------------- parser

def _kwargs(tokens, issues, path, n):
    pos, kw = [], {}
    for t in tokens:
        if "=" in t:
            k, _, v = t.partition("=")
            kw[k] = v
        else:
            pos.append(t)
    return pos, kw


def _int_arg(kw, name, issues, path, n, lo=None):
    if name not in kw:
        return None
    v = kw.pop(name)
    if not v.isdigit() or (lo is not None and int(v) < lo):
        issues.append(Issue("E_BAD_ARG", f"{name}={v!r} must be an integer" + (f" >= {lo}" if lo else ""),
                            path, n))
        return None
    return int(v)


def parse(path, strict=False, text=None, palette_only=False, allow_empty=False, _depth=0):
    path = pathlib.Path(path)
    if text is None:
        with open(path, newline="") as fh:
            text = fh.read()
    raw = text
    doc = Doc(path)
    issues = []

    def err(code, msg, n=None, **kw):
        issues.append(Issue(code, msg, str(path), n, **kw))

    state, cur, variant, started, pal_failed = "header", None, None, False, False
    pending, source = [], {}
    if "\r\n" in raw:
        doc.newline = "\r\n"
    doc.final_newline = raw.endswith("\n") or not raw

    def keep(anchor):
        """This line is `anchor`: remember its spelling and the blank/comment lines above it."""
        doc.lead[anchor], source[anchor] = list(pending), line
        pending.clear()

    for n, line in enumerate(raw.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            if not s and state == "variant":
                state = "header"
            (pending if started else doc.comments).append(line)
            continue
        if not started and re.match(r"^pxart\s+\S+$", s):
            started = True
            keep("version")
            v = s.split()[1]
            if v != str(FORMAT_VERSION):
                err("E_VERSION", f"this pxart reads format version {FORMAT_VERSION}, file says {v!r}", n)
            doc.version = int(v) if v.isdigit() else None
            continue
        started = True

        if s.startswith("@"):
            word, *rest = s.split()
            pos, kw = _kwargs(rest, issues, path, n)
            if word == "@frame":
                if doc.implicit:
                    err("E_MIXED_FRAMES", "grid rows appear before the first @frame; put every grid under an @frame",
                        n)
                    continue
                if len(pos) != 1 or not ID_RE.match(pos[0]):
                    err("E_BAD_ID", f"@frame needs one id like walk/down/0 (letters, digits, _ - . and /): {s!r}", n)
                    continue
                if doc.get(pos[0]):
                    err("E_DUP_FRAME", f"frame {pos[0]!r} already defined", n)
                ms = _int_arg(kw, "ms", issues, str(path), n, lo=1)
                for k in kw:
                    err("E_BAD_ARG", f"@frame doesn't take {k}=", n)
                cur = Frame(pos[0], ms=ms, line=n)
                doc.frames.append(cur)
                keep(("frame", cur.id))
                state = "frame"
            elif word == "@palette":
                if doc.frames:
                    err("E_PALETTE_AFTER_GRID", "@palette must come before any grid", n)
                    continue
                if len(pos) != 1:
                    err("E_BAD_ARG", "@palette takes one path", n)
                    continue
                ref = pos[0]
                target = (path.parent / ref)
                pal_failed, before = True, pal_failed  # until the import succeeds
                skip = "" if palette_only else PAL_SKIP
                if _depth > 4:
                    err("E_PALETTE_FILE", "@palette nested too deeply (cycle?)" + skip, n)
                    continue
                try:
                    sub = parse(target, strict, palette_only=True, _depth=_depth + 1)
                except FileNotFoundError:
                    err("E_PALETTE_FILE", f"can't find palette file {ref!r} (relative to this file)" + skip, n)
                    continue
                except PxError as e:
                    err("E_PALETTE_FILE", f"palette file {ref!r} has errors: {e.issues[0]}" + skip, n)
                    continue
                pal_failed = before
                doc.palette_refs.append(ref)
                keep(("palref", ref))
                doc.shared.update(sub.shared)
                doc.shared.update(sub.palette)
                for vname, over in list(sub.shared_variants.items()) + list(sub.variants.items()):
                    doc.shared_variants.setdefault(vname, {}).update(over)
                state = "header"
            elif word == "@variant":
                if len(pos) != 1:
                    err("E_BAD_ARG", "@variant takes one name", n)
                    continue
                variant = pos[0]
                doc.variants.setdefault(variant, {})
                keep(("variant", variant))
                state = "variant"
            elif word == "@anim":
                if len(pos) != 1 or not ID_RE.match(pos[0]):
                    err("E_BAD_ID", f"@anim needs a group path like walk/down: {s!r}", n)
                    continue
                a = {}
                d = kw.pop("direction", None)
                if d is not None:
                    if d not in DIRECTIONS:
                        err("E_BAD_ARG", f"direction={d!r}; use one of {', '.join(DIRECTIONS)}", n)
                    a["direction"] = d
                a["repeat"] = _int_arg(kw, "repeat", issues, str(path), n)
                a["ms"] = _int_arg(kw, "ms", issues, str(path), n, lo=1)
                for k in kw:
                    err("E_BAD_ARG", f"@anim doesn't take {k}=", n)
                doc.anims[pos[0]] = a
                keep(("anim", pos[0]))
                state = "header" if not doc.frames else state
            elif word == "@still":
                if len(pos) != 1 or not (ID_RE.match(pos[0]) or pos[0] == "*") or kw:
                    err("E_BAD_ID", f"@still needs one group path like ui/life, or * for every group: {s!r}", n)
                    continue
                doc.stills.append(pos[0])
                keep(("still", pos[0]))
                state = "header" if not doc.frames else state
            else:
                if strict:
                    err("E_UNKNOWN_SECTION", f"unknown section {word}", n)
                keep(("ext", len(doc.extensions)))
                doc.extensions.append(s)
                state = "ext"
            continue

        if state == "ext":
            keep(("ext", len(doc.extensions)))
            doc.extensions.append(s)
            continue

        m = PAL_RE.match(s)
        if m:
            key, val = m.groups()
            if state in ("frame", "grid"):
                err("E_PALETTE_AFTER_GRID", f"palette line {s!r} after grid rows; palette goes before any grid", n)
                continue
            if val == "transparent":
                color = CLEAR
            elif COLOR_RE.match(val):
                color = hex2rgba(val)
            else:
                err("E_BAD_COLOR", f"{val!r} isn't #rrggbb, #rrggbbaa, or transparent", n)
                continue
            if key == ".":
                if color[3] != 0:
                    err("E_DOT_RESERVED", "'.' is always transparent; pick another key for this color", n)
                elif state != "variant" and doc.dot_at is None:
                    doc.dot_at = len(doc.palette)
                    keep(("key", "."))
                continue
            if key not in KEYS:
                err("E_BAD_KEY", f"{key!r} can't be a palette key (not # @ . \" \\ or whitespace)", n)
                continue
            if state == "variant":
                doc.variants[variant][key] = color
                keep(("vkey", variant, key))
            else:
                if key in doc.palette:
                    err("E_DUP_KEY", f"key {key!r} defined twice", n)
                doc.palette[key] = color
                keep(("key", key))
            continue

        if " " in s or "\t" in s:
            err("E_BAD_ROW", f"grid rows can't contain spaces: {s!r} (palette lines are '<key> <color>')", n)
            continue
        if state in ("header", "variant"):
            if doc.frames:
                err("E_MIXED_FRAMES", "grid rows outside an @frame after other frames", n)
                continue
            doc.implicit = True
            cur = Frame(None, line=n)
            doc.frames.append(cur)
            state = "grid"
        keep(("row", cur.id, len(cur.grid)))
        cur.grid.append(s)
        cur.row_lines.append(n)

    doc.tail = pending
    doc.raw = {a: (text_line, source[a]) for a, _, text_line in doc.lines() if a in source}
    gaps = [doc.lead[("frame", f.id)].count("") for f in doc.frames[1:] if ("frame", f.id) in doc.lead]
    doc.frame_gap = max(set(gaps), key=gaps.count) if gaps else None

    # --- whole-document checks
    if palette_only:
        if doc.frames:
            err("E_PALETTE_FILE", "a palette file can't contain grid rows", doc.frames[0].line)
        if issues:
            raise PxError(issues)
        return doc

    pal = doc.resolved()
    if not doc.frames and not allow_empty:
        err("E_NO_FRAMES", "no grid rows")
    for f in doc.frames:
        if not f.grid:
            err("E_EMPTY_FRAME", "frame has no rows", f.line, frame=f.id)
            continue
        widths = [len(r) for r in f.grid]
        expect = max(set(widths), key=lambda w: (widths.count(w), w == widths[0]))
        for i, (r, w) in enumerate(zip(f.grid, widths)):
            if w != expect:
                err("E_ROW_WIDTH", f"row is {w} wide, but {widths.count(expect)} of {len(widths)} rows are "
                    f"{expect} wide: {r!r}",
                    f.row_lines[i], frame=f.id, row=i)
            bad = [] if pal_failed else [x for x, c in enumerate(r) if c not in pal]
            if bad:
                err("E_UNKNOWN_KEY", f"keys {''.join(sorted(set(r[x] for x in bad)))!r} aren't in the palette",
                    f.row_lines[i], frame=f.id, row=i, cols=bad)
    for name, over in ({} if pal_failed else doc.variants).items():
        for k in over:
            if k not in pal and k not in doc.shared_variants.get(name, {}):
                err("E_VARIANT_KEY", f"@variant {name} sets {k!r}, which the base palette doesn't define")
    if issues:
        raise PxError(issues)
    return doc


# ---------------------------------------------------------------------------- inputs

def split_variant(arg):
    """'hero.px:walk/down%frost' -> ('hero.px:walk/down', 'frost')."""
    left, sep, right = arg.rpartition("%")
    if sep and left and re.match(r"^[A-Za-z0-9_\-]+$", right):
        return left, right
    return arg, None


def split_sel(arg):
    """'hero.px:walk/down' -> (path, 'walk/down'); a plain path -> (path, None)."""
    arg = split_variant(arg)[0]
    left, sep, right = arg.rpartition(":")
    if sep and left and pathlib.Path(left).suffix in (".px", ".png") and not os.path.exists(arg):
        return left, right
    return arg, None


FLIP_RE = re.compile(r"^(.+)\+([hvb]{1,3})(%[A-Za-z0-9_\-]+)?$")


def split_flip(arg):
    """'hero.px:walk/0%night+h' -> ('hero.px:walk/0%night', 'h'); '+h%night' works too. No flip -> ''. The letters
    are h, v and (map legend entries only) b for bottom-anchored, each at most once: '+hb', '+vh'."""
    m = FLIP_RE.match(arg)
    if not m or len(set(m.group(2))) < len(m.group(2)):
        return arg, ""
    return m.group(1) + (m.group(3) or ""), m.group(2)


def flipped(img, how):
    T = getattr(Image, "Transpose", Image)
    if "h" in how:
        img = img.transpose(T.FLIP_LEFT_RIGHT)
    if "v" in how:
        img = img.transpose(T.FLIP_TOP_BOTTOM)
    return img


def split_at(arg):
    left, sep, right = arg.rpartition("@")
    m = re.match(r"^(-?\d+,-?\d+)%([A-Za-z0-9_\-]+)$", right)
    if sep and m:
        fail("E_BAD_ARG", f"%variant goes before @ (FILE:frame%variant@x,y): write "
             f"{left}%{m.group(2)}@{m.group(1)}, not {arg!r}")
    m = re.match(r"^(-?\d+,-?\d+)\+([hvb]{1,3})$", right)
    if sep and m:
        fail("E_BAD_ARG", f"+{m.group(2)} goes before @ (FILE:frame%variant+h@x,y): write "
             f"{left}+{m.group(2)}@{m.group(1)}, not {arg!r}")
    if not sep or not re.match(r"^-?\d+,-?\d+$", right):
        fail("E_BAD_ARG", f"expected FILE[:frame][%variant]@x,y, got {arg!r}")
    x, y = map(int, right.split(","))
    return left, x, y


class Item:
    """One frame to look at: label, image, duration, and (for .px) its doc/frame."""
    def __init__(self, label, img, ms, doc=None, frame=None):
        self.label, self.img, self.ms, self.doc, self.frame = label, img, ms, doc, frame


def items(arg, variant=None, strict=False):
    variant = split_variant(arg)[1] or variant
    path, sel = split_sel(arg)
    if path.endswith(".png") or path.endswith(".gif"):
        return [Item(pathlib.Path(path).stem, Image.open(path).convert("RGBA"), DEFAULT_MS)]
    doc = parse(path, strict)
    return [Item(doc.label(f), doc.image(f, variant), doc.ms(f), doc, f) for f in doc.select(sel)]


def all_items(args, variant=None):
    out = []
    for a in args:
        out += items(a, variant)
    return out


def one_frame(arg, what="input", variant=None):
    got = items(arg, variant)
    if len(got) != 1:
        fail("E_SELECT", f"{what} {arg!r} is {len(got)} frames; pick one with FILE:frame-id")
    return got[0]


def place_item(arg, what, variant=None, anchor=False):
    """One frame for scene/compose/maps, mirrored by a +h / +v / +hv suffix: the Item, with its image and
    (for .px) a frame whose grid is flipped the same way. +b (bottom anchor) is for map legend entries only."""
    arg, how = split_flip(arg)
    if "b" in how and not anchor:
        fail("E_BAD_ARG", f"+b anchors a map legend entry to the bottom of its cell; a {what} is placed at its x,y "
             f"(its top-left), so drop the b: {arg}+{how.replace('b', '')}".rstrip("+"))
    it = one_frame(arg, what, variant)
    how = how.replace("b", "")
    if how:
        it.img = flipped(it.img, how)
        if it.frame:
            g = [r[::-1] for r in it.frame.grid] if "h" in how else list(it.frame.grid)
            it.frame = Frame(it.frame.id, g[::-1] if "v" in how else g, it.frame.ms)
    return it


def pixels(img):
    """Flat list of RGBA tuples (get_flattened_data where Pillow has it, else getdata)."""
    return list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())


def colors(img):
    return sorted({p for p in pixels(img) if p[3] > 0})


# ---------------------------------------------------------------------------- drawing

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


def text_w(d, s):
    return int(d.textlength(s)) if hasattr(d, "textlength") else 6 * len(s)


def outpath(p):
    """Output path with its directory created; a file where a directory should be is a clear E_FILE."""
    p = pathlib.Path(p)
    for d in reversed(p.parents):
        if d.exists() and not d.is_dir():
            hint = f" (a frame goes after ':', as in {d}:{p.relative_to(d).as_posix()})" if d.suffix == ".px" else ""
            fail("E_FILE", f"can't write {p}: {d} is a file, not a directory{hint}")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


ZSH_EATEN_RE = re.compile(r"\.(px|png)[A-Za-z]")


def file_error(e):
    """An OSError as an E_FILE line; a missing input like 'hero.pxalk/0' gets the zsh-modifier hint."""
    name = e.filename or ""
    msg = f"{name}: E_FILE: {e.strerror or e}"
    if isinstance(e, FileNotFoundError) and any(ZSH_EATEN_RE.search(part) for part in pathlib.Path(name).parts):
        msg += (f"\n  {name!r} looks like zsh ate a ':' as a modifier (\"$F:walk/0\" applies :w to $F, \"$F:t\" "
                "applies :t). Write \"${F}:walk/0\" or quote the whole argument.")
    return msg


def sheet(its, out, scale=8, cols=8, bg="#3a3a44", grid=False, rulers=False):
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tiles = [(it, upscale(it.img, scale, grid, rulers)) for it in its]
    lw = max(max(text_w(probe, it.label), text_w(probe, f"{it.img.width}x{it.img.height} 99c")) for it in its)
    iw = max((it.img.width for it in its if it.img.height <= 22), default=0)
    cw = max(max(t.width for _, t in tiles), lw + iw + 8)
    ch = max(t.height for _, t in tiles)
    pad, lab = 10, 26
    cols = max(1, min(cols, len(tiles)))
    rows = (len(tiles) + cols - 1) // cols
    s = Image.new("RGBA", (pad + cols * (cw + pad), pad + rows * (ch + lab + pad)), (30, 30, 36, 255))
    d = ImageDraw.Draw(s)
    for n, (it, big) in enumerate(tiles):
        x, y = pad + (n % cols) * (cw + pad), pad + (n // cols) * (ch + lab + pad)
        d.rectangle([x, y, x + cw - 1, y + ch - 1], fill=hex2rgba(bg))
        s.alpha_composite(big, (x + (cw - big.width) // 2, y + ch - big.height))
        if it.img.height <= lab - 4 and it.img.width <= cw - lw - 6:
            s.alpha_composite(it.img, (x + cw - it.img.width - 2, y + ch + 4))  # 1x beside the label
        d.text((x, y + ch + 2), it.label, fill=(220, 220, 220, 255))
        d.text((x, y + ch + 13), f"{it.img.width}x{it.img.height} {len(colors(it.img))}c", fill=(150, 150, 160, 255))
    s.save(outpath(out))
    return out


def on_bg(img, w, h, bg="#3a3a44"):
    b = Image.new("RGBA", (w, h), hex2rgba(bg))
    b.alpha_composite(img, ((w - img.width) // 2, h - img.height))
    return b


def shifted(img, dx, dy):
    out = Image.new("RGBA", img.size, CLEAR)
    out.paste(img, (dx, dy))
    return out


def best_shift(prev, cur, reach=2):
    """The whole-sprite (dx, dy) that best explains cur as a moved prev: the body bob."""
    best, cd = None, pixels(cur)
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            n = sum(1 for a, b in zip(pixels(shifted(prev, dx, dy)), cd) if a != b)
            key = (n, abs(dx) + abs(dy))
            if best is None or key < best[0]:
                best = (key, dx, dy)
    return best[1], best[2]


def motion(prev, cur):
    """How cur differs from prev: the whole-sprite shift (dx, dy), px changed after it, px changed with
    no shift, and `still`: the row from which down the sprite stayed put, when that explains cur far
    better than moving everything (an idle whose chest rises while the legs stay), else None."""
    dx, dy = best_shift(prev, cur)
    w, h = cur.size
    C, P, M = pixels(cur), pixels(prev), pixels(shifted(prev, dx, dy))
    moved = [sum(M[i] != C[i] for i in range(y * w, y * w + w)) for y in range(h)]
    kept = [sum(P[i] != C[i] for i in range(y * w, y * w + w)) for y in range(h)]
    n_shift, n_none, still = sum(moved), sum(kept), None
    if (dx, dy) != (0, 0):
        # Rows above y moved by (dx, dy), rows from y down stayed put: the best y, and what it leaves changed.
        split = [sum(moved[:y]) + sum(kept[y:]) for y in range(h)]
        y = min(range(h), key=lambda y: (split[y], -y))
        if 3 * split[y] < n_shift and any(c[3] for c in C[y * w:]):
            still = y
    return dx, dy, n_shift, n_none, still


def diff_frame(prev, cur):
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


def pack(its):
    """Lay frames on a sheet: returns (sheet, [(x, y)]) with a near-square grid of max-size cells."""
    cw, ch = max(i.img.width for i in its), max(i.img.height for i in its)
    cols = max(1, math.ceil(math.sqrt(len(its))))
    rows = math.ceil(len(its) / cols)
    s = Image.new("RGBA", (cols * cw, rows * ch), CLEAR)
    spots = []
    for n, it in enumerate(its):
        x, y = (n % cols) * cw, (n // cols) * ch
        s.alpha_composite(it.img, (x, y))
        spots.append((x, y))
    return s, spots, cols, cw, ch


def grouped(its):
    """Frames ordered so each animation group is contiguous (first-appearance order)."""
    order = {}
    for it in its:
        order.setdefault(it.frame.group if it.frame else "", len(order))
    return sorted(its, key=lambda it: order[it.frame.group if it.frame else ""])


def load_palette(path):
    p = str(path)
    if p.endswith(".px"):
        doc = parse(p, palette_only=not _has_grid(p))
        return {c[:3] for c in doc.resolved().values() if c[3]}
    text = pathlib.Path(p).read_text()
    if p.endswith(".gpl"):
        return {tuple(int(v) for v in m.groups())
                for m in (re.match(r"\s*(\d+)\s+(\d+)\s+(\d+)", l) for l in text.splitlines()) if m}
    return {hex2rgba(h)[:3] for h in re.findall(r"#?\b([0-9a-fA-F]{6})\b", text)}


def _has_grid(p):
    try:
        parse(p, palette_only=True)
        return False
    except PxError:
        return True


def parse_rect(s, size):
    if not s:
        return (0, 0) + tuple(size)
    try:
        x, y, w, h = (int(v) for v in s.split(","))
    except ValueError:
        fail("E_BAD_ARG", f"--region wants x,y,w,h, got {s!r}")
    return x, y, w, h


# ---------------------------------------------------------------------------- editing helpers

def note_suffix(path):
    """A .px output that doesn't end in .px is usually zsh reading "$VAR:sel" as a modifier."""
    if not str(path).endswith(".px"):
        print(f"note: output {str(path)!r} doesn't end in .px; if you wrote \"$VAR:sel\" in zsh, the :sel "
              f"was read as a modifier; write \"${{VAR}}:sel\"")


def write_doc(doc, path=None):
    """Save doc unless the file already holds exactly its text; returns what to print."""
    path = pathlib.Path(path or doc.path)
    text = doc.text()
    try:
        with open(path, newline="") as fh:
            if fh.read() == text:
                return f"no change: {path}"
    except (OSError, ValueError):  # missing, or not text
        pass
    return f"wrote {doc.save(path)}"


def edit_target(arg, out):
    """The shared edit path: (doc, selected frames, where to write). -o gets the whole file with the selection
    edited, never just the selection (that's extract)."""
    path, sel = split_sel(arg)
    doc = parse(path)
    frames = doc.select(sel)
    out = pathlib.Path(out) if out else doc.path
    if sel and out.resolve() != doc.path.resolve():
        print(f"note: {out} gets all of {doc.path} with {sel} edited; for only those frames use "
              f"'pxart extract {doc.path}:{sel} -o {out}'")
    return doc, frames, out


def stamp(dst_doc, dst, src_doc, src, at, region=None):
    """Copy src frame (or a region of it) onto dst frame at `at`; '.'/transparent keys don't overwrite."""
    src_pal = src_doc.resolved()
    for k in set("".join(src.grid)):
        if src_pal[k][3]:
            dst_doc.add_key(k, src_pal[k])
    x0, y0, w, h = parse_rect(region, src.size)
    W, H = dst.size
    g = [list(r) for r in dst.grid]
    for y in range(h):
        for x in range(w):
            if not (0 <= y0 + y < src.size[1] and 0 <= x0 + x < src.size[0]):
                continue
            ch = src.grid[y0 + y][x0 + x]
            tx, ty = at[0] + x, at[1] + y
            if src_pal[ch][3] and 0 <= tx < W and 0 <= ty < H:
                g[ty][tx] = ch
    dst.grid = ["".join(r) for r in g]


# ---------------------------------------------------------------------------- commands

def cmd_render(a):
    its = all_items(a.files, a.variant)
    for f in a.files:
        path, sel = split_sel(f)
        if a.png and path.endswith(".px") and not sel:
            doc = parse(path)
            if len(doc.frames) == 1:
                doc.image(doc.frames[0], a.variant).save(pathlib.Path(path).with_suffix(".png"))
    print("wrote", sheet(its, a.o, a.scale, bg=a.bg, grid=not a.no_grid, rulers=not a.no_grid))


def cmd_sheet(a):
    print("wrote", sheet(all_items(a.files, a.variant), a.o, a.scale, a.cols, a.bg, grid=a.grid))


def cmd_anim(a):
    its = all_items(a.files, a.variant)
    frames = [it.img for it in its]
    durs = [1000 // a.fps if a.fps else it.ms for it in its]
    w, h = max(f.width for f in frames), max(f.height for f in frames)
    framed = [on_bg(f, w, h) for f in frames]
    S, gap = a.scale, 8
    gif = []
    for f in framed:
        canvas = Image.new("RGBA", (w * S + gap * 3 + w * 3, max(h * S, h * 3 + gap)), (30, 30, 36, 255))
        canvas.alpha_composite(f.resize((w * S, h * S), Image.NEAREST), (0, 0))
        canvas.alpha_composite(f, (w * S + gap, 0))                                        # 1x
        canvas.alpha_composite(f.resize((w * 2, h * 2), Image.NEAREST), (w * S + gap * 2 + w, 0))  # 2x
        gif.append(canvas.convert("P", palette=Image.ADAPTIVE))
    gif[0].save(outpath(a.o), save_all=True, append_images=gif[1:], duration=durs, loop=0, disposal=2)
    pad, lab, lab2 = 8, 14, 26
    n = len(framed)
    strip = Image.new("RGBA", (pad + n * (w * S + pad), pad + 2 * (h * S + pad) + lab + lab2), (30, 30, 36, 255))
    d = ImageDraw.Draw(strip)
    for i, fr in enumerate(framed):
        x = pad + i * (w * S + pad)
        strip.alpha_composite(upscale(fr, S, grid=True), (x, pad))
        d.text((x, pad + h * S + 1), f"{its[i].label} {durs[i]}ms", fill=(220, 220, 220, 255))
        # Compare on a shared canvas, bottom-centered as drawn, so frames of different sizes diff too.
        prev, cur = on_bg(frames[i - 1], w, h, "#00000000"), on_bg(frames[i], w, h, "#00000000")
        dx, dy, n_shift, n_none, still = motion(prev, cur)
        if still is None:
            base, head = shifted(prev, dx, dy), f"shift {dx:+d},{dy:+d} then {n_shift}px"
            alt = f"(no shift: {n_none}px)" if (dx, dy) != (0, 0) else ""
        else:
            base, head = prev, f"no shift then {n_none}px"
            alt = f"(rows {still}+ still; shift {dx:+d},{dy:+d}: {n_shift}px)"
        y2 = pad * 2 + h * S + lab
        strip.alpha_composite(upscale(on_bg(diff_frame(base, cur), w, h, "#1e1e24"), S, grid=True), (x, y2))
        d.text((x, y2 + h * S + 1), head, fill=(255, 120, 220, 255))
        d.text((x, y2 + h * S + 13), alt, fill=(200, 140, 190, 255))
        print(f"  {its[i].label:24} {durs[i]:5}ms  vs {its[i - 1].label}: {head}" + (f" {alt}" if alt else ""))
    sp = pathlib.Path(a.o).with_suffix(".strip.png")
    strip.save(sp)
    print("wrote", a.o, "and", sp)


def cmd_onion(a):
    A, B = one_frame(a.a).img, one_frame(a.b).img
    w, h = max(A.width, B.width), max(A.height, B.height)
    base = on_bg(Image.new("RGBA", (1, 1), CLEAR), w, h)
    faded = A.copy(); faded.putalpha(A.getchannel("A").point(lambda v: v * 35 // 100))
    base.alpha_composite(faded, ((w - A.width) // 2, h - A.height))
    top = B.copy(); top.putalpha(B.getchannel("A").point(lambda v: v * 80 // 100))
    base.alpha_composite(top, ((w - B.width) // 2, h - B.height))
    upscale(base, a.scale, grid=True, rulers=True).save(outpath(a.o))
    print("wrote", a.o)


MAP_HASH_RE = re.compile(r"^\S+\.(px(:[A-Za-z0-9_\-./]+)?|png)(%[A-Za-z0-9_\-]+)?$")
MAP_QUOTED_RE = re.compile(r'^"(.+\.(px(:[A-Za-z0-9_\-./]+)?|png)(%[A-Za-z0-9_\-]+)?)"$')
LEGEND_RE = re.compile(r"^(\S)\s+(.+)$")


def parse_map(path):
    """Tilemap file: legend lines '<char> <FILE[:frame][%variant]>' (the rest of the line is the path, relative
    to the map; "quote it" if you like), a blank line, then rows of legend chars; a line '---' starts another
    layer of rows over the same legend. Returns {char: item_arg}, layers [[(line, row)]], notes, and
    {char: (line, path as written)}."""
    path = pathlib.Path(path)
    legend, layers, notes, where, in_rows = {}, [[]], [], {}, False
    rows = layers[0]
    for n, line in enumerate(path.read_text().splitlines(), 1):
        s = line.strip()
        if not s:
            in_rows = in_rows or bool(legend)
            continue
        if s == "---" and (in_rows or legend):
            in_rows = True
            if rows:
                rows = []
                layers.append(rows)
            continue
        m = None if in_rows else LEGEND_RE.match(s)
        if m:
            ch, rest = m.group(1), m.group(2).strip()
            q = MAP_QUOTED_RE.match(rest)
            if ch != "#" or q or MAP_HASH_RE.match(rest):
                target = rest[1:-1] if len(rest) > 1 and rest[0] == rest[-1] == '"' else rest
                legend[ch], where[ch] = str(path.parent / target), (n, target)
                if ch == "#":
                    notes.append(f"{path}:{n}: {s!r} is the legend line for '#', not a comment: '#' in the rows "
                                 f"draws {target}")
                continue
        if not in_rows and s.startswith("#"):
            continue  # comments only before the rows; after that '#' is a map char (a wall row '####')
        in_rows = True
        rows.append((n, s))
    if not layers[-1] and len(layers) > 1:
        layers.pop()
    if "-" in legend and len(layers) > 1:
        notes.append(f"{path}: '---' lines separate layers; they aren't rows of the '-' tile")
    return legend, layers, notes, where


def read_map(path, tile, notes=None):
    """Returns [(item_arg, x, y)] and the map size in px; '#' legend notes go to `notes`."""
    path = pathlib.Path(path)
    legend, layers, found, _ = parse_map(path)
    if notes is not None:
        notes += found
    out = []
    for n, y, row in ((n, y, row) for rows in layers for y, (n, row) in enumerate(rows)):  # later layers on top
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            if ch.isspace():
                fail("E_BAD_ROW", f"map row {row!r} has spaces; a legend line is one char, a space, then the path "
                     "(the rest of the line)", path=str(path), line=n, cols=[x])
            if ch not in legend:
                hint = " (map rows start after the legend's blank line, so '#' there is a map char, not a comment; " \
                    "define it with a legend line '# FILE', or '# \"FILE\"' for a path with spaces)" if ch == "#" else ""
                fail("E_UNKNOWN_KEY", f"map char {ch!r} has no legend line{hint}", path=str(path), line=n, cols=[x])
            out.append((legend[ch], x * tile[0], y * tile[1]))
    width = max((len(r) for rows in layers for _, r in rows), default=0) * tile[0]
    return out, (width, max(len(rows) for rows in layers) * tile[1])


def load_legend(path, variant=None):
    """Load every legend entry as one frame: {item_arg: image}. A target that can't be loaded is an error at
    its legend line, naming the path as written."""
    legend, _, _, where = parse_map(path)
    imgs, issues = {}, []
    for ch, arg in legend.items():
        n, written = where[ch]
        try:
            imgs[arg] = place_item(arg, f"legend {ch!r}", variant, anchor=True).img
        except PxError as e:
            for i in e.issues:
                at = f" ({i.path}:{i.line})" if i.line else ""
                issues.append(Issue(i.code, f"legend {ch!r}: {written!r}: {i.msg}{at}", str(path), n))
        except OSError as e:
            issues.append(Issue("E_FILE", f"legend {ch!r}: can't load {written!r} (relative to the map file): "
                                f"{e.strerror or e}", str(path), n))
    if issues:
        raise PxError(issues)
    return imgs


def cell_spot(arg, img, x, y, tile):
    """Where a map item draws, given its cell's top-left x,y: there (its top-left), or with +b bottom-aligned to the
    cell and centered across it, odd pixel left: (x + (tile w - w) // 2, y + tile h - h)."""
    if "b" not in split_flip(arg)[1]:
        return x, y
    return x + (tile[0] - img.width) // 2, y + tile[1] - img.height


def draw_at(canvas, img, x, y):
    """alpha_composite at x,y, where x,y may be negative (older Pillow refuses a negative dest)."""
    if x < 0 or y < 0:
        if -x >= img.width or -y >= img.height:
            return
        img, x, y = img.crop((max(0, -x), max(0, -y), img.width, img.height)), max(0, x), max(0, y)
    canvas.alpha_composite(img, (x, y))


def parse_tint(s):
    """'#rrggbbaa' (or #rrggbb, or without the '#') -> rgba."""
    v = s if s.startswith("#") else "#" + s
    if not COLOR_RE.match(v):
        fail("E_BAD_COLOR", f"tint {s!r} isn't #rrggbbaa or #rrggbb (in a script, quote it: '#10183080'; "
             "an unquoted word starting with # is a comment there)")
    return hex2rgba(v)


def tinted(img, color):
    """`color` laid over img at the color's alpha; every pixel keeps its own alpha (transparent stays so)."""
    over = Image.blend(img, Image.new("RGBA", img.size, color[:3] + (255,)), color[3] / 255)
    alpha = img.getchannel("A")
    over.putalpha(alpha)
    return Image.composite(over, img, alpha.point(lambda v: 255 if v else 0))


def cmd_tint(a):
    color = parse_tint(a.color)
    if not a.file.endswith(".png") or not str(a.o or a.file).endswith(".png"):
        fail("E_BAD_ARG", "tint reads and writes PNGs (a rendered scene); for a whole scene use scene --tint")
    out = a.o or a.file
    tinted(Image.open(a.file).convert("RGBA"), color).save(outpath(out))
    print("wrote", out)


def cmd_scene(a):
    tint = parse_tint(a.tint) if a.tint else None
    placed = []
    tile = tuple(map(int, a.tile.split("x")))
    if a.map:
        notes = []
        placed, msize = read_map(a.map, tile, notes)
        for n in notes:
            print("note:", n)
    W, H = map(int, a.size.split("x")) if a.size else (msize if a.map else (96, 64))
    sc = Image.new("RGBA", (W, H), hex2rgba(a.bg))
    tiles = load_legend(a.map, a.variant) if a.map else {}
    for arg, x, y in placed:
        draw_at(sc, tiles[arg], *cell_spot(arg, tiles[arg], x, y, tile))
    for spec in a.specs:
        path, x, y = split_at(spec)
        draw_at(sc, place_item(path, "scene item", a.variant).img, x, y)
    if tint:
        sc = tinted(sc, tint)
    sc.resize((W * a.scale, H * a.scale), Image.NEAREST).save(outpath(a.o))
    print("wrote", a.o)


def check_map(path):
    """check for a scene tilemap: every legend entry loads as one frame and every row char has one."""
    issues, legend, layers, notes = [], {}, [[]], []
    try:
        legend, layers, notes, _ = parse_map(path)
    except OSError as e:
        issues.append(Issue("E_FILE", e.strerror or str(e), path))
    for step in (lambda: read_map(path, (1, 1)), lambda: load_legend(path)) if legend or layers[0] else ():
        try:
            step()
        except PxError as e:
            issues += e.issues
    if issues:
        print(f"FAIL {path}: {len(issues)} error(s)")
        for i in issues:
            print(f"     {i}")
    else:
        w = max((len(r) for rows in layers for _, r in rows), default=0)
        print(f"ok   {path}: map {w}x{max(len(rows) for rows in layers)} tiles, {len(legend)} legend char(s)"
              + (f", {len(layers)} layers" if len(layers) > 1 else ""))
    for n in notes:
        print(f"     note: {n}")
    return not issues


# Non-ASCII letters that read as ASCII ones (Cyrillic, Greek); fullwidth and other compatibility forms come
# from NFKC.
LOOKALIKES = dict(zip("аеорсхуіјѕԁһӏԛԝАВЕКМНОРСТХУЅІЈοανρυικχΑΒΕΖΗΙΚΜΝΟΡΤΥΧ",
                      "aeopcxyijsdhlqwABEKMHOPCTXYSIJoavpuikxABEZHIKMNOPTYX"))


def lookalike(ch):
    """The ASCII char a non-ASCII ch passes for, or None."""
    if ord(ch) < 128:
        return None
    n = LOOKALIKES.get(ch) or unicodedata.normalize("NFKC", ch)
    return n if len(n) == 1 and 32 < ord(n) < 127 else None


def lookalike_notes(path):
    """Notes for non-ASCII chars that look like ASCII in a .px's palette/grid lines or a .map's lines, with
    where they are: 'frame F, row R, x=X' for a .px grid row, else the column."""
    try:
        with open(path, newline="") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    px, notes, frame, row, ext = str(path).endswith(".px"), [], None, 0, False
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if not s or (px and s.startswith("#")):
            continue
        if px and s.startswith("@"):
            word, *rest = s.split()
            ext = word not in ("@frame", "@palette", "@variant", "@anim", "@still")
            if word == "@frame":
                frame, row = (rest[0] if rest else None), 0
            continue
        if ext:
            continue
        grid = px and not re.search(r"\s", s)
        lead = len(line) - len(line.lstrip())
        for x, ch in enumerate(s):
            asc = lookalike(ch)
            if not asc:
                continue
            if grid:
                where = (f"frame {frame}, " if frame else "") + f"row {row}, x={x}"
            else:
                where = f"col {lead + x + 1}" + (" (the key)" if px and x == 0 else "")
            notes.append(f"{path}:{n} ({where}): {ch!r} is U+{ord(ch):04X} "
                         f"{unicodedata.name(ch, 'non-ASCII')}, not ASCII {asc!r}")
        row += grid
    return notes


def cmd_check(a):
    allowed = load_palette(a.palette) if a.palette else None
    want = tuple(map(int, a.size.split("x"))) if a.size else None
    failed = False
    for arg in dict.fromkeys(a.files):
        path, sel = split_sel(arg)
        try:
            if path.endswith(".map"):
                failed |= not check_map(path)
                continue
            if path.endswith(".px") and not sel and not _has_grid(path):
                try:
                    pdoc = parse(path, a.strict, palette_only=True)
                    print(f"ok   {path}: palette file, {len(pdoc.palette)} key(s)"
                          + (f", variants {', '.join(pdoc.variants)}" if pdoc.variants else ""))
                except PxError as e:
                    failed = True
                    print(f"FAIL {path}: {len(e.issues)} error(s)")
                    for i in e.issues:
                        print(f"     {i}")
                continue
            try:
                its = items(arg, strict=a.strict)
            except PxError as e:
                failed = True
                print(f"FAIL {path}: {len(e.issues)} error(s)")
                for i in e.issues:
                    print(f"     {i}")
                continue
            notes = []
            if its and its[0].doc:
                doc = its[0].doc
                over = [k for k in doc.palette if k in doc.shared and doc.palette[k] != doc.shared[k]]
                if over:
                    notes.append("local keys override @palette colors: " + "".join(over))
                for g, fs in doc.groups().items():
                    if doc.animated(g) and len({f.size for f in fs}) > 1:
                        notes.append(f"animation {g!r} mixes frame sizes ("
                                     + ", ".join(f"{f.id} {f.size[0]}x{f.size[1]}" for f in fs)
                                     + "); frames draw bottom-centered, and Tiled export needs one size")
                used = set("".join(r for f in doc.frames for r in f.grid))
                unused = [k for k, v in doc.palette.items() if k not in used and v[3]]
                if unused:
                    notes.append("unused keys " + "".join(unused))
            for it in its:
                probs = []
                if want and it.img.size != want:
                    probs.append(f"size {it.img.width}x{it.img.height} != {want[0]}x{want[1]}")
                cs = colors(it.img)
                if allowed is not None:
                    off = [rgba2hex(c) for c in cs if c[:3] not in allowed]
                    if off:
                        probs.append("off-palette " + " ".join(off))
                if a.max_colors and len(cs) > a.max_colors:
                    probs.append(f"{len(cs)} colors > {a.max_colors}")
                failed |= bool(probs)
                name = path if len(its) == 1 and not (it.frame and it.frame.id) else f"{path}:{it.label}"
                print(f"{'FAIL' if probs else 'ok  '} {name}: {it.img.width}x{it.img.height} {len(cs)}c"
                      + "".join(f"; {x}" for x in probs))
            for note in notes:
                print(f"     {path}: {note}")
        finally:  # after the file's own lines, like its other notes
            for note in lookalike_notes(path) if path.endswith((".px", ".map")) else []:
                print(f"     note: {note}")
    sys.exit(1 if failed else 0)


def cmd_stats(a):
    for arg in a.files:
        for it in items(arg):
            cs = colors(it.img)
            print(f"{arg if not (it.frame and it.frame.id) else split_sel(arg)[0] + ':' + it.label}: "
                  f"{it.img.width}x{it.img.height} bbox={it.img.getchannel('A').getbbox()} colors={len(cs)} "
                  + " ".join(rgba2hex(c) for c in cs[:32]))


def cmd_frames(a):
    path, sel = split_sel(a.file)
    doc = parse(path, allow_empty=True)
    picked = doc.select(sel) if sel else doc.frames
    if a.rm is not None or a.move or a.after or a.before:
        if doc.implicit:
            fail("E_MIXED_FRAMES", "this file has one unnamed grid; nothing to move or remove")
        if a.after and a.before:
            fail("E_BAD_ARG", "give --after or --before, not both")
        print("; ".join((frames_sel_edit if sel else frames_edit)(a, doc, sel, picked) + [write_doc(doc)]))
        return
    for g, fs in doc.groups(picked).items():
        meta = doc.anims.get(g, {})
        still = doc.still(g)
        whole = len(doc.groups()[g])
        head = f"{g or '(no group)'}: {len(fs)} frame(s)" + (f" (of {whole})" if len(fs) < whole else "") \
            + (" [still]" if still else "")
        extra = ", ".join(f"{k}={v}" for k, v in meta.items() if v is not None)
        print(head + (f" [{extra}]" if extra else ""))
        for f in fs:
            print(f"  {doc.label(f)}  {f.size[0]}x{f.size[1]}  {'still' if still else f'{doc.ms(f)}ms'}  (line {f.line})")
    if doc.variants:
        print("variants:", ", ".join(doc.variants))


def frames_edit(a, doc, sel, picked):
    """frames FILE --rm ID... / --move ID --after|--before ID: returns what it did."""
    if a.rm == []:
        fail("E_BAD_ARG", "--rm needs frame ids (frames FILE --rm ID...), or FILE:SEL to remove the selection "
             "(frames FILE:SEL --rm)")
    if (a.after or a.before) and not a.move:
        fail("E_BAD_ARG", "--after/--before need --move ID (frames FILE --move ID --after ID), or FILE:SEL to move "
             "the selection (frames FILE:SEL --after ID)")
    did = []
    for fid in a.rm or []:
        f = doc.get(fid)
        if not f:
            fail("E_SELECT", f"--rm {fid!r}: no such frame")
        doc.frames.remove(f)
    if a.rm:
        did.append("removed " + ", ".join(a.rm))
    if a.move:
        f = doc.get(a.move)
        anchor = doc.get(a.after or a.before or "")
        if not f or not anchor or f is anchor:
            fail("E_SELECT", "--move ID needs an existing frame and --after/--before another existing frame")
        doc.frames.remove(f)
        doc.frames.insert(doc.frames.index(anchor) + (1 if a.after else 0), f)
        did.append(f"moved {a.move} {'after' if a.after else 'before'} {anchor.id}")
    return did


def frames_sel_edit(a, doc, sel, picked):
    """frames FILE:SEL --rm [ID...] removes the selection (or those ids in it); FILE:SEL --after|--before ID moves
    the selection there as a block, in its order."""
    if a.move:
        fail("E_BAD_ARG", f"--move takes one frame id and FILE without :SEL; to move the selection {sel!r}, give only "
             f"--after/--before: frames {doc.path}:{sel} --after ID")
    if a.rm is not None and (a.after or a.before):
        fail("E_BAD_ARG", f"with FILE:SEL, give --rm (remove {sel!r}) or --after/--before (move it), not both")
    if a.rm is not None:
        gone = picked
        if a.rm:
            ids = {f.id for f in picked}
            out = [fid for fid in a.rm if fid not in ids]
            if out:
                fail("E_SELECT", f"--rm {', '.join(out)}: not in {sel!r} ({', '.join(sorted(ids))}); drop the :SEL "
                     "to remove frames by id anywhere")
            gone = [f for f in picked if f.id in a.rm]
        for f in gone:
            doc.frames.remove(f)
        return ["removed " + ", ".join(f.id for f in gone)]
    where = a.after or a.before
    anchor = doc.get(where)
    if not anchor:
        fail("E_SELECT", f"--{'after' if a.after else 'before'} {where!r}: no such frame")
    if anchor in picked:
        fail("E_SELECT", f"--{'after' if a.after else 'before'} {where!r} is inside the selection {sel!r}; "
             "name a frame outside it")
    for f in picked:
        doc.frames.remove(f)
    at = doc.frames.index(anchor) + (1 if a.after else 0)
    doc.frames[at:at] = picked
    return [f"moved {sel} ({len(picked)} frame(s)) {'after' if a.after else 'before'} {anchor.id}"]


def cmd_flip(a):
    doc, frames, out = edit_target(a.file, a.o)
    for f in frames:
        f.grid = f.grid[::-1] if a.v else [r[::-1] for r in f.grid]
    print(write_doc(doc, out))


def cmd_shift(a):
    doc, frames, out = edit_target(a.file, a.o)
    pal = doc.resolved()
    for f in frames:
        x0, y0, w, h = parse_rect(a.region, f.size)
        W, H = f.size
        g = [list(r) for r in f.grid]
        block = [[g[y][x] for x in range(x0, min(x0 + w, W))] for y in range(y0, min(y0 + h, H))]
        if a.wrap:
            bh, bw = len(block), len(block[0]) if block else 0
            for y in range(bh):
                for x in range(bw):
                    g[y0 + (y + a.dy) % bh][x0 + (x + a.dx) % bw] = block[y][x]
            f.grid = ["".join(r) for r in g]
            continue
        for y in range(y0, min(y0 + h, H)):
            for x in range(x0, min(x0 + w, W)):
                g[y][x] = "."
        for y, row in enumerate(block):
            for x, ch in enumerate(row):
                tx, ty = x0 + x + a.dx, y0 + y + a.dy
                if 0 <= tx < W and 0 <= ty < H and pal[ch][3]:
                    g[ty][tx] = ch
        f.grid = ["".join(r) for r in g]
    print(write_doc(doc, out))


BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def cmd_mask(a):
    path, sel = split_sel(a.file)
    png = path.endswith(".png")
    if png and sel:
        fail("E_SELECT", f"a PNG has no frames to pick: {a.file!r}")
    if png != str(a.o or path).endswith(".png"):
        fail("E_BAD_ARG", "mask writes what it reads: a .px from a .px, a .png from a .png (-o OUT.png)")
    if a.dither is not None and (a.dither < 1 or not a.keep_circle):
        fail("E_BAD_ARG", "--dither N wants N >= 1 and --keep-circle")
    try:
        if a.keep_circle:
            cx, cy, r = (float(v) for v in a.keep_circle.split(","))
        else:
            x0, y0, w, h = (int(v) for v in a.keep.split(","))
    except ValueError:
        fail("E_BAD_ARG", f"--keep wants x,y,w,h; --keep-circle wants cx,cy,r; got {a.keep or a.keep_circle!r}")

    def keep(x, y):  # --invert keeps exactly what the plain mask erases, dither band included
        return inside(x, y) != a.invert

    def inside(x, y):
        if not a.keep_circle:
            return x0 <= x < x0 + w and y0 <= y < y0 + h
        d = math.hypot(x - cx, y - cy)
        if d > r:
            return False
        if not a.dither or d <= r - a.dither:
            return True
        return (r - d) / a.dither > (BAYER4[y % 4][x % 4] + 0.5) / 16  # ordered-dither falloff

    erased = 0
    if png:
        img = Image.open(path).convert("RGBA")
        px = img.load()
        for y in range(img.height):
            for x in range(img.width):
                if px[x, y][3] and not keep(x, y):
                    px[x, y], erased = CLEAR, erased + 1
        out = a.o or path
        if not erased and pathlib.Path(out).resolve() == pathlib.Path(path).resolve():
            print(f"erased 0 px; no change: {out}")
            return
        img.save(outpath(out))
        print(f"erased {erased} px; wrote {out}")
        return
    doc, frames, out = edit_target(a.file, a.o)
    for f in frames:
        g = [list(row) for row in f.grid]
        for y, row in enumerate(g):
            for x, ch in enumerate(row):
                if ch != "." and not keep(x, y):
                    row[x], erased = ".", erased + 1
        f.grid = ["".join(row) for row in g]
    print(f"erased {erased} px;", write_doc(doc, out))


def cmd_recolor(a):
    """Key moves (a=b, 'a<>b') apply together: each pixel is repainted by the move of the key it had before the
    call, so they can't feed each other. Color changes (c=#hex) set the palette and are independent of moves."""
    doc, frames, out = edit_target(a.file, a.o)
    pal = doc.resolved()
    moves, said = {}, {}
    for m in a.maps:
        if "<>" in m:
            k, _, v = m.partition("<>")
            if v.startswith("#") or v == "transparent":
                fail("E_BAD_ARG", f"recolor: {m!r}: '<>' swaps two keys; to change a color write {k}={v}")
            pairs = [(k, v), (v, k)] if k != v else [(k, v)]
        elif "=" in m:
            k, _, v = m.partition("=")
            pairs = [(k, v)]
        else:
            fail("E_BAD_ARG", f"recolor: {m!r} isn't a=b, c=#rrggbb or 'a<>b' (quote a swap: unquoted, < and > "
                 "are shell redirections, and the shell hands pxart only the part before them)")
        if k not in pal:
            fail("E_SELECT", f"recolor: key {k!r} not in palette")
        if v.startswith("#") or v == "transparent":
            if a.region:
                fail("E_BAD_ARG", "--region only applies to key=key repaints; a color change affects every pixel "
                     "of that key. Add a new key (palette --add) and repaint the region to it instead.")
            if v != "transparent" and not COLOR_RE.match(v):
                fail("E_BAD_COLOR", f"{v!r} isn't #rrggbb or #rrggbbaa")
            if ("#", k) in said:
                fail("E_BAD_ARG", f"recolor: key {k!r} gets two colors ({said[('#', k)]} and {m})")
            said[("#", k)] = m
            # A shared key recolored here becomes a local override for this file only.
            doc.palette[k] = CLEAR if v == "transparent" else hex2rgba(v)
            continue
        if v not in pal:
            fail("E_SELECT", f"recolor: key {v!r} not in palette (add it with palette --add)")
        for k, v in pairs:
            if k in moves:
                fail("E_BAD_ARG", f"recolor: key {k!r} is moved twice ({said[k]} and {m}); key moves apply "
                     "together, so each key can go one place")
            moves[k], said[k] = v, m
    for f in frames:
        x0, y0, w, h = parse_rect(a.region, f.size)
        f.grid = ["".join(moves.get(c, c) if x0 <= x < x0 + w and y0 <= y < y0 + h else c
                          for x, c in enumerate(row)) for y, row in enumerate(f.grid)]
    print(write_doc(doc, out))


def cmd_set(a):
    doc, frames, out = edit_target(a.file, a.o)
    if a.key not in doc.resolved():
        fail("E_SELECT", f"set: key {a.key!r} not in palette (add it with palette --add)")
    for f in frames:
        g = [list(r) for r in f.grid]
        for pt in a.points:
            try:
                x, y = map(int, pt.split(","))
            except ValueError:
                fail("E_BAD_ARG", f"set: points are x,y; got {pt!r}")
            if not (0 <= x < f.size[0] and 0 <= y < f.size[1]):
                fail("E_BAD_ARG", f"set: {x},{y} is outside {doc.label(f)} ({f.size[0]}x{f.size[1]})")
            g[y][x] = a.key
        f.grid = ["".join(r) for r in g]
    print(write_doc(doc, out))


def cmd_crop(a):
    src = one_frame(a.src, "crop source")
    x, y, w, h = parse_rect(a.rect, src.frame.size)
    a.layers, a.size, a.size_from = [f"{a.src}@{-x},{-y}"], f"{w}x{h}", "the crop rectangle"
    cmd_compose(a)


def cmd_paste(a):
    src = one_frame(a.src, "--src")
    ddoc, dframes, out = edit_target(a.into, a.o)
    ax, ay = map(int, a.at.split(","))
    for f in dframes:
        stamp(ddoc, f, src.doc, src.frame, (ax, ay), a.region)
    print(write_doc(ddoc, out))


def cmd_extract(a):
    """Only the selected frames, with the file's palette, @palette imports (re-pointed from OUT's directory),
    variants, and @anim/@still lines except those of groups the selection left behind."""
    path, sel = split_sel(a.file)
    doc = parse(path)
    keep = doc.select(sel)
    gone = {f.group for f in doc.frames} - {f.group for f in keep}  # groups the selection leaves behind
    doc.frames = keep
    out = pathlib.Path(a.o)
    note_suffix(out)
    doc.anims = {g: v for g, v in doc.anims.items() if g not in gone}
    doc.stills = [g for g in doc.stills if g not in gone]
    if out.resolve().parent != doc.path.resolve().parent:
        for i, ref in enumerate(doc.palette_refs):
            new = pathlib.Path(os.path.relpath((doc.path.parent / ref).resolve(), out.resolve().parent)).as_posix()
            doc.palette_refs[i] = new
            doc.lead[("palref", new)] = doc.lead.pop(("palref", ref), [])
    print(write_doc(doc, out), f"({len(doc.frames)} frame(s))")


def frame_slot(opath, osel, palette=None, flag="-o"):
    """Open OUT (or start it, importing `palette`) and find or make the frame OUT[:frame] names: (doc, frame).
    A new frame goes after the last frame of its animation, or at the end when the animation is new."""
    if pathlib.Path(opath).exists():
        doc = parse(opath, allow_empty=True)
    else:
        doc = Doc(opath)
        doc.version = FORMAT_VERSION
        if palette:
            ref = pathlib.Path(os.path.relpath(palette, pathlib.Path(opath).resolve().parent)).as_posix()
            doc = parse(opath, text=f"pxart 1\n@palette {ref}\n", allow_empty=True)
    if osel:
        if doc.implicit:
            fail("E_MIXED_FRAMES", f"{opath} has one unnamed grid; can't add frame {osel!r} to it")
        if not ID_RE.match(osel):
            fail("E_BAD_ID", f"bad frame id {osel!r}")
        target = doc.get(osel)
        if not target:
            target = Frame(osel)
            same = [f for f in doc.frames if f.group == target.group] if target.group else []
            doc.frames.insert(doc.frames.index(same[-1]) + 1 if same else len(doc.frames), target)
    else:
        if doc.frames and not doc.implicit:
            fail("E_SELECT", f"{opath} has named frames; say which one: {flag} {opath}:<frame-id>")
        doc.implicit = True
        doc.frames = [Frame(None)]
        target = doc.frames[0]
    return doc, target


def parse_size(s, what="--size"):
    m = re.match(r"^(\d+)x(\d+)$", s or "")
    if not m or not int(m.group(1)) or not int(m.group(2)):
        fail("E_BAD_ARG", f"{what} wants WxH like 16x16, got {s!r}")
    return int(m.group(1)), int(m.group(2))


def cmd_new(a):
    opath, osel = split_sel(a.out)
    note_suffix(opath)
    if a.palette and pathlib.Path(opath).exists():
        fail("E_BAD_ARG", f"--palette starts a new file, and {opath} exists (it keeps its own palette)")
    w, h = parse_size(a.size)
    had_grid = not osel and pathlib.Path(opath).exists() and parse(opath, allow_empty=True).implicit
    doc, target = frame_slot(opath, osel, a.palette, flag="new")
    if target.grid or had_grid:
        fail("E_DUP_FRAME", f"{opath} already has " + (f"frame {osel!r}" if osel else "its grid")
             + f"; repaint it with 'pxart fill {a.out} KEY'")
    key = a.key or "."
    if key not in doc.resolved():
        fail("E_SELECT", f"new: key {key!r} not in palette (add it with palette --add, or start with --palette)")
    target.grid = [key * w] * h
    print(write_doc(doc, opath), f"frame {osel}" if osel else "")


def cmd_fill(a):
    doc, frames, out = edit_target(a.file, a.o)
    if a.key not in doc.resolved():
        fail("E_SELECT", f"fill: key {a.key!r} not in palette (add it with palette --add)")
    for f in frames:
        x0, y0, w, h = parse_rect(a.region, f.size)
        f.grid = ["".join(a.key if x0 <= x < x0 + w and y0 <= y < y0 + h else c for x, c in enumerate(row))
                  for y, row in enumerate(f.grid)]
    print(write_doc(doc, out))


def cmd_compose(a):
    layers = [(place_item(p, "layer"), x, y) for p, x, y in (split_at(s) for s in a.layers)]
    for lay, _, _ in layers:
        if not lay.doc:
            fail("E_BAD_ARG", f"compose layers must be .px frames, got {lay.label}")
    opath, osel = split_sel(a.o)
    note_suffix(opath)
    doc, target = frame_slot(opath, osel)
    if a.size:
        size, why = tuple(map(int, a.size.split("x"))), getattr(a, "size_from", "--size")
    elif target.grid:
        size, why = target.size, "the frame being replaced"
    elif osel and any(f.grid for f in doc.frames if f.group == target.group and f is not target):
        size = next(f.size for f in doc.frames if f.group == target.group and f.grid and f is not target)
        why = f"the rest of {target.group!r}"
    else:
        size, why = layers[0][0].frame.size, "the first layer"
    target.grid = ["." * size[0]] * size[1]
    for lay, x, y in layers:
        w, h = lay.frame.size
        cut = sum(1 for yy, row in enumerate(lay.frame.grid) for xx, ch in enumerate(row)
                  if ch != "." and lay.doc.resolved()[ch][3]
                  and not (0 <= x + xx < size[0] and 0 <= y + yy < size[1]))
        if cut:
            print(f"note: {cut} px of {lay.label} fall outside the {size[0]}x{size[1]} canvas "
                  f"(size from {why}) and were cropped")
        stamp(doc, target, lay.doc, lay.frame, (x, y))
    print(write_doc(doc, opath), f"frame {osel}" if osel else "")


def cmd_dup(a):
    path, sel = split_sel(a.src)
    doc = parse(path)
    src = doc.get(sel) if sel else None
    if not src:
        fail("E_SELECT", f"dup needs FILE:frame-id of an existing frame; frames: "
             f"{', '.join(doc.label(f) for f in doc.frames)}")
    if doc.get(a.new) or not ID_RE.match(a.new):
        fail("E_DUP_FRAME" if doc.get(a.new) else "E_BAD_ID", f"can't use {a.new!r} as the new frame id")
    new = Frame(a.new, list(src.grid), src.ms)
    if a.after:
        anchor = doc.get(a.after)
        if not anchor:
            fail("E_SELECT", f"--after {a.after!r}: no such frame")
    else:
        same = [f for f in doc.frames if f.group == new.group] if new.group else []
        src_group = [f for f in doc.frames if f.group == src.group] if src.group else [src]
        anchor = same[-1] if same else src_group[-1]
    doc.frames.insert(doc.frames.index(anchor) + 1, new)
    if new.group and new.group not in doc.anims and src.group in doc.anims:
        doc.anims[new.group] = dict(doc.anims[src.group])
    note_suffix(a.o or doc.path)
    print(write_doc(doc, a.o), "frame", a.new)


def timing_value(k, v):
    """An anim-set value as the file would hold it: None to clear (KEY=), else checked like the parser does."""
    if v == "":
        return None
    if k == "direction":
        if v not in DIRECTIONS:
            fail("E_BAD_ARG", f"direction={v!r}; use one of {', '.join(DIRECTIONS)}")
        return v
    if not v.isdigit() or (k == "ms" and int(v) < 1):
        fail("E_BAD_ARG", f"{k}={v!r} must be an integer" + (" >= 1" if k == "ms" else ""))
    return int(v)


def cmd_anim_set(a):
    """Timing: FILE:GROUP updates or adds '@anim GROUP ...'; FILE:GROUP/ID sets that frame's ms=. One line changes."""
    path, sel = split_sel(a.target)
    doc = parse(path)
    out = pathlib.Path(a.o) if a.o else doc.path
    if not sel:
        fail("E_SELECT", f"anim-set needs FILE:GROUP (an animation's @anim line) or FILE:GROUP/ID (one frame's ms=); "
             f"animations: {', '.join(g for g in doc.groups() if g) or 'none'}", path=doc.path)
    kw = {}
    for arg in a.settings:
        k, eq, v = arg.partition("=")
        if not eq or k not in ("ms", "direction", "repeat"):
            fail("E_BAD_ARG", f"anim-set: {arg!r}; settings are ms=N, direction=D, repeat=N (KEY= clears one)", path=doc.path)
        kw[k] = timing_value(k, v)
    if not kw:
        fail("E_BAD_ARG", "anim-set: give ms=N, direction=D and/or repeat=N", path=doc.path)
    groups = doc.groups()
    if sel in groups and sel:
        anim = doc.anims.setdefault(sel, {})
        anim.update(kw)
        line = next(text for anchor, _, text in doc.lines() if anchor == ("anim", sel))
        if kw.get("ms"):
            for f in groups[sel]:
                if f.ms:
                    print(f"note: {f.id} keeps its own ms={f.ms} (anim-set {doc.path}:{f.id} ms= clears it)")
    else:
        f = doc.get(sel)
        if not f:
            fail("E_SELECT", f"{sel!r} is neither an animation nor a frame; animations: "
                 f"{', '.join(g for g in groups if g) or 'none'}", path=doc.path)
        if set(kw) - {"ms"}:
            fail("E_BAD_ARG", f"{sel!r} is one frame, which takes only ms=; direction= and repeat= belong to its "
                 f"animation: anim-set {doc.path}:{f.group or 'GROUP'} ...", path=doc.path)
        f.ms = kw["ms"]
        line = next(text for anchor, _, text in doc.lines() if anchor == ("frame", f.id))
    print(f"{line}; {write_doc(doc, out)}")


def cmd_palette(a):
    doc = parse(a.file, palette_only=not _has_grid(a.file))
    for m in a.add or []:
        k, _, v = m.partition("=")
        if not COLOR_RE.match(v):
            fail("E_BAD_COLOR", f"{m!r}: want key=#rrggbb")
        if len(k) != 1:
            fail("E_BAD_KEY", f"{k!r}: keys are one character")
        doc.add_key(k, hex2rgba(v))
    if a.add:
        print(write_doc(doc))
    pal = doc.resolved()
    used = {}
    for f in doc.frames:
        for r in f.grid:
            for c in r:
                used[c] = used.get(c, 0) + 1
    if a.export:
        cols = [(k, v) for k, v in pal.items() if v[3] and (not a.used or used.get(k))]
        if a.export.endswith(".gpl"):
            body = "GIMP Palette\nName: %s\nColumns: 0\n#\n" % doc.stem
            body += "".join("%3d %3d %3d\t%s\n" % (v[0], v[1], v[2], k) for k, v in cols)
        elif a.export.endswith(".hex"):
            body = "".join("%02x%02x%02x\n" % v[:3] for _, v in cols)
        else:
            fail("E_BAD_ARG", "--export wants a .gpl or .hex path")
        outpath(a.export).write_text(body)
        if any(v[3] < 255 for _, v in cols):
            print("note: .gpl/.hex carry no alpha; translucent colors were written opaque")
        print("wrote", a.export)
    if a.add or a.export:
        return
    for k, v in pal.items():
        src = "shared" if k in doc.shared and k not in doc.palette else ("local" if k != "." else "built-in")
        print(f"{k} {fmt_color(v):11} {src:8}" + (f" used {used.get(k, 0)}" if doc.frames else ""))
    names = sorted(set(doc.variants) | set(doc.shared_variants))
    if names:
        print("variants:", ", ".join(names))


def cmd_export(a):
    doc = parse(a.file)
    its = [Item(doc.label(f), doc.image(f, a.variant), doc.ms(f), doc, f) for f in doc.frames]
    wrote = []
    if a.frames:
        for it in its:
            p = outpath(pathlib.Path(a.frames) / (it.label + ".png"))
            it.img.save(p)
            wrote.append(str(p))
    if a.aseprite:
        its2 = grouped(its)
        sheet_img, spots, _, _, _ = pack(its2)
        jp = outpath(a.aseprite)
        ip = jp.with_suffix(".png")
        sheet_img.save(ip)
        frames, tags, i = [], [], 0
        for it, (x, y) in zip(its2, spots):
            w, h = it.img.size
            frames.append({"filename": it.label, "frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False,
                           "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h},
                           "sourceSize": {"w": w, "h": h}, "duration": it.ms})
        for g, fs in doc.groups().items():
            if not doc.animated(g):
                i += len(fs)
                continue
            meta = doc.anims.get(g, {})
            tag = {"name": g, "from": i, "to": i + len(fs) - 1,
                   "direction": meta.get("direction") or "forward", "color": "#000000ff"}
            if meta.get("repeat"):
                tag["repeat"] = str(meta["repeat"])
            tags.append(tag)
            i += len(fs)
        data = {"frames": frames, "meta": {
            "app": "https://github.com/thethirdbearsolutions/pxart", "version": str(FORMAT_VERSION),
            "image": ip.name, "format": "RGBA8888", "size": {"w": sheet_img.width, "h": sheet_img.height},
            "scale": "1", "frameTags": tags, "layers": [], "slices": []}}
        jp.write_text(json.dumps(data, indent=1) + "\n")
        wrote += [str(ip), str(jp)]
    if a.tiled:
        if len({it.img.size for it in its}) > 1:
            fail("E_TILE_SIZE", "a Tiled tileset needs every frame the same size: "
                 + ", ".join(f"{it.label} {it.img.width}x{it.img.height}" for it in its))
        its = grouped(its)
        sheet_img, spots, cols, cw, ch = pack(its)
        tp = outpath(a.tiled)
        ip = tp.with_suffix(".png")
        sheet_img.save(ip)
        index = {id(it): n for n, it in enumerate(its)}
        tiles = []
        for g, fs in doc.groups().items():
            if not doc.animated(g) or len(fs) < 2:
                continue
            first = next(it for it in its if it.frame is fs[0])
            tiles.append({"id": index[id(first)],
                          "animation": [{"tileid": index[id(next(it for it in its if it.frame is f))],
                                         "duration": doc.ms(f)} for f in fs],
                          "properties": [{"name": "pxart_anim", "type": "string", "value": g}]})
        data = {"type": "tileset", "version": "1.10", "name": doc.stem, "image": ip.name,
                "imagewidth": sheet_img.width, "imageheight": sheet_img.height,
                "tilewidth": cw, "tileheight": ch, "columns": cols, "tilecount": len(its),
                "margin": 0, "spacing": 0, "tiles": tiles}
        tp.write_text(json.dumps(data, indent=1) + "\n")
        wrote += [str(ip), str(tp)]
    if not wrote:
        fail("E_BAD_ARG", "export: give --frames DIR, --aseprite X.json and/or --tiled X.tsj")
    print("wrote", " ".join(wrote))


def cmd_from_png(a):
    """PNG(s) -> .px. Colors already in OUT's palette keep their keys; new colors get free keys."""
    imgs = [(pathlib.Path(p), Image.open(p).convert("RGBA")) for p in a.pngs]
    out = pathlib.Path(a.o) if a.o else None
    if out and out.exists():
        doc = parse(out, allow_empty=True)
    else:
        doc = Doc(out or imgs[0][0].with_suffix(".px"))
        doc.version = FORMAT_VERSION
        if a.palette:
            ref = os.path.relpath(a.palette, (out or imgs[0][0]).resolve().parent)
            doc = parse(doc.path, text=f"pxart 1\n@palette {ref}\n", allow_empty=True)
    named = bool(a.id) or len(imgs) > 1 or (doc.frames and not doc.implicit) or (out and out.exists())
    if named and doc.implicit:
        fail("E_MIXED_FRAMES", f"{out} holds one unnamed grid; import into a new file or one with @frame ids")
    keyof = {c: k for k, c in doc.resolved().items() if c[3]}
    free = [k for k in KEYS if k not in doc.resolved()]
    for path, img in imgs:
        for c in colors(img):
            if c not in keyof:
                if not free:
                    fail("E_BAD_ARG", f"{path}: out of palette keys ({len(KEYS)} max)")
                keyof[c] = free.pop(0)
                doc.palette[keyof[c]] = c
        grid = ["".join(keyof[p] if p[3] else "." for p in (img.getpixel((x, y)) for x in range(img.width)))
                for y in range(img.height)]
        if not named:
            doc.implicit, doc.frames = True, [Frame(None, grid)]
            continue
        fid = f"{a.id}/{path.stem}" if a.id else path.stem
        fid = re.sub(r"[^A-Za-z0-9_\-./]", "_", fid)
        old = doc.get(fid)
        if old:
            old.grid = grid
        else:
            doc.frames.append(Frame(fid, grid))
    if out:
        print(write_doc(doc, out), f"({len(imgs)} frame(s))" if named else "")
    else:
        print(doc.text(), end="")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pxart", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("render"); p.add_argument("files", nargs="+"); p.add_argument("-o", default="preview.png")
    p.add_argument("--png", action="store_true")
    p.add_argument("--scale", type=int, default=8); p.add_argument("--bg", default="#3a3a44")
    p.add_argument("--no-grid", action="store_true"); p.add_argument("--variant")
    p = sub.add_parser("sheet"); p.add_argument("files", nargs="+"); p.add_argument("-o", required=True)
    p.add_argument("--scale", type=int, default=8); p.add_argument("--cols", type=int, default=8)
    p.add_argument("--bg", default="#3a3a44"); p.add_argument("--grid", action="store_true"); p.add_argument("--variant")
    p = sub.add_parser("anim"); p.add_argument("files", nargs="+"); p.add_argument("-o", required=True)
    p.add_argument("--fps", type=int); p.add_argument("--scale", type=int, default=8); p.add_argument("--variant")
    p = sub.add_parser("onion"); p.add_argument("a"); p.add_argument("b"); p.add_argument("-o", required=True)
    p.add_argument("--scale", type=int, default=8)
    p = sub.add_parser("scene"); p.add_argument("specs", nargs="*"); p.add_argument("-o", required=True)
    p.add_argument("--scale", type=int, default=4); p.add_argument("--bg", default="#472d3c")
    p.add_argument("--size", help="WxH; default 96x64, or the map's size with --map")
    p.add_argument("--map", help="tilemap file: legend lines '<char> <FILE[:frame]>' (rest of line = path), blank line, rows")
    p.add_argument("--tile", default="16x16", help="tile size for --map")
    p.add_argument("--variant", help="variant for every map tile and item without its own %%variant")
    p.add_argument("--tint", help="'#rrggbbaa' laid over the finished scene (quote it in scripts)")
    p = sub.add_parser("tint"); p.add_argument("file"); p.add_argument("color"); p.add_argument("-o")
    p = sub.add_parser("check"); p.add_argument("files", nargs="+"); p.add_argument("--palette")
    p.add_argument("--size"); p.add_argument("--max-colors", type=int); p.add_argument("--strict", action="store_true")
    p = sub.add_parser("stats"); p.add_argument("files", nargs="+")
    p = sub.add_parser("frames"); p.add_argument("file"); p.add_argument("--rm", nargs="*")
    p.add_argument("--move"); p.add_argument("--after"); p.add_argument("--before")
    p = sub.add_parser("flip"); p.add_argument("file"); p.add_argument("-o"); p.add_argument("--v", action="store_true")
    p = sub.add_parser("shift"); p.add_argument("file"); p.add_argument("-o")
    p.add_argument("--dx", type=int, default=0); p.add_argument("--dy", type=int, default=0); p.add_argument("--region")
    p.add_argument("--wrap", action="store_true")
    p = sub.add_parser("mask"); p.add_argument("file"); p.add_argument("-o")
    k = p.add_mutually_exclusive_group(required=True)
    k.add_argument("--keep", help="x,y,w,h"); k.add_argument("--keep-circle", help="cx,cy,r")
    p.add_argument("--dither", type=int, help="ordered-dither falloff band N px wide inside the circle's edge")
    p.add_argument("--invert", action="store_true", help="erase inside the shape, keep the outside")
    p = sub.add_parser("recolor"); p.add_argument("file"); p.add_argument("maps", nargs="+"); p.add_argument("-o")
    p.add_argument("--region")
    p = sub.add_parser("set"); p.add_argument("file"); p.add_argument("key"); p.add_argument("points", nargs="+")
    p.add_argument("-o")
    p = sub.add_parser("crop"); p.add_argument("src"); p.add_argument("rect"); p.add_argument("-o", required=True)
    p = sub.add_parser("paste"); p.add_argument("src"); p.add_argument("--into", required=True)
    p.add_argument("--at", required=True); p.add_argument("--region"); p.add_argument("-o")
    p = sub.add_parser("new"); p.add_argument("out"); p.add_argument("--size", required=True)
    p.add_argument("--key", help="fill with this key (default '.')"); p.add_argument("--palette", help="new OUT imports this .px")
    p = sub.add_parser("fill"); p.add_argument("file"); p.add_argument("key"); p.add_argument("--region")
    p.add_argument("-o")
    p = sub.add_parser("extract"); p.add_argument("file"); p.add_argument("-o", required=True)
    p = sub.add_parser("compose"); p.add_argument("layers", nargs="+"); p.add_argument("-o", required=True)
    p.add_argument("--size")
    p = sub.add_parser("dup"); p.add_argument("src"); p.add_argument("new"); p.add_argument("-o")
    p.add_argument("--after")
    p = sub.add_parser("anim-set"); p.add_argument("target"); p.add_argument("settings", nargs="*"); p.add_argument("-o")
    p = sub.add_parser("palette"); p.add_argument("file"); p.add_argument("--add", nargs="+"); p.add_argument("--export")
    p.add_argument("--used", action="store_true")
    p = sub.add_parser("export"); p.add_argument("file"); p.add_argument("--frames"); p.add_argument("--aseprite")
    p.add_argument("--tiled"); p.add_argument("--variant")
    p = sub.add_parser("from-png"); p.add_argument("pngs", nargs="+"); p.add_argument("-o"); p.add_argument("--id")
    p.add_argument("--palette", help="new OUT imports this palette file and reuses its keys")
    a = ap.parse_args(argv)
    try:
        globals()["cmd_" + a.cmd.replace("-", "_")](a)
    except PxError as e:
        sys.exit(str(e))
    except OSError as e:
        sys.exit(file_error(e))


if __name__ == "__main__":
    main()
