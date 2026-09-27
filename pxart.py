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
  pivot=x,y (optional) on '@frame ID' or '@anim GROUP' is the frame's anchor pixel, counted
  from its top-left (the feet: pivot=8,23 on a 16x24 frame). A frame's own wins over its
  anim's; no pivot is the default. anim and onion line frames up by pivot instead of bottom-
  centre (a frame without one then uses its bottom-centre pixel, w // 2, h - 1); export
  writes pivots (Aseprite slices, --frames pivots.json). A pivot may lie outside the frame (a
  hand, the ground under a jump); check notes that in case it's a typo. flip, rotate and
  transpose move a frame's pivot with its pixels: a whole group's @anim pivot moves on its
  @anim line, and a frame flipped alone gets its own. Set it with anim-set ... pivot=8,23.
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
  path (FILE:walk/down = every walk/down/* frame). No SEL means every frame. A file with
  one unnamed grid (no @frame) calls it by the file's name, as frames lists it: ant.px's
  grid is ant.px:ant. Writing a named frame into such a file (compose, crop, new, put -o
  ant.px:ID, or from-png into it) first makes the grid '@frame ant', with a note; with ID
  ant that is the frame written. Add
  %VARIANT to render with a variant: FILE:idle/0%night. In zsh, "$F:walk" is read as a
  modifier; write "${F}:walk" or quote the whole argument. A missing input whose name has
  letters glued to .px/.png (hero.pxalk/0, hero.pxidle) is reported as that mistake.
  An output under a path that is a file (-o hero.px/walk/0) is E_FILE, not a crash.

LOOKING
  render FILE... [-o preview.png] [--scale 8] [--no-grid] [--variant V] [--png]
      Preview sheet with a pixel grid and x/y rulers every 4px (default --scale 8; sheet,
      anim and onion default to 8 too). --png also writes a 1x PNG beside each
      single-frame .px.
  sheet FILE... -o sheet.png [--scale 8] [--cols 8] [--grid] [--variant V] [--bg #3a3a44]
        [--fit]
      Compare any mix of .px/.png frames, labeled with id, WxH and color count. Every cell is
      the largest frame's size, so a 16x16 tile beside a 64x64 beast gets a 64x64 cell;
      --fit makes each cell its own frame's width (or its label's, if wider) and each row
      as tall as its tallest frame, --cols cells to a row, frames bottom-aligned in their
      row. A PNG whose
      four corners are exactly the --bg color (a scene rendered with the same --bg) doesn't
      count that color: it's the backdrop. Frames with the same id from different files are
      labeled with their file's stem in front (hero:idle/0, beast:idle/0; the path as given
      when the stems match too); render and anim label them the same way.
  anim FILE... [-o walk.gif] [--scale 8] [--fps N] [--variant V]
      walk.gif (one file: each frame at --scale, its 1x and 2x copies beside it in the same
      picture), plus walk.strip.png: row 1 = frames,
      row 2 = what changed from the previous frame after removing the whole-sprite
      shift ("shift dx,dy then N px (P%) (no shift: M px)"; P is N as a percent of the
      frame's opaque pixels; a walk that's only a bob shows "then 0px (0%)"). When the
      bottom of the sprite stays exactly put (rows Y down identical, 0 px changed) and only
      the part above it moves (an idle breathing: chest up 1px, legs still), moving the
      whole sprite would light up the legs, so the strip shows the unshifted diff instead:
      "no shift then M px (P%) (rows Y+ still; shift dx,dy: N px)"; Y is the first identical
      row. A walk whose leg moved even 1px keeps the shift. Both counts are always shown.
      That reading is for an idle, whose legs keep their shape in every frame of the
      animation. In a walk the legs move in other frames, so a frame whose legs happen to
      stay put is the body's bob and keeps the smaller, truthful number: "shift +0,+1 then
      23px (6%) (no shift: 201px)". A frame recolored whole (a glow) doesn't count as the
      legs moving; a shadow that changes shape does.
      So the rise and the fall of a breath read alike (the fall may carry an arm move that
      a frame alone would call a shift): once one frame shows rows still, and rows Y down are
      identical in every frame of the animation (legs that never move), every frame whose
      shift would light those rows up shows the unshifted diff too. A walk over a static
      shadow, where no frame shows its legs still on its own, keeps every shift.
      Tiles and overlays scroll with wrap-around (shift --wrap): for frames that fill the
      canvas and are a ground tile (every pixel opaque) or a sparse overlay (at most 1/4
      of the pixels opaque: snow, rain), every scroll is tried too, and one that leaves
      strictly fewer pixels changed than the best plain shift is shown as
      "shift dx,dy (wrap) then N px (P%) (no shift: M px)". A character sprite never wraps.
      Read the strip; the Read tool shows only a GIF's first frame. The same numbers print
      to stdout, one line per frame; without -o, anim prints only those lines and writes
      nothing. Durations come from the file (@anim/@frame ms) unless --fps is given.
  onion A B -o x.png [--scale 8] [--rows Y0-Y1 | --feet N] [--tint-a [COLOR]]
      B drawn over a faded A: A at 35% opacity, then B at 80%, with render's grid and rulers.
      Prints where each frame's opaque pixels sit on the shared canvas and how B's edges moved
      from A's, then the whole-sprite shift that best explains B, as anim finds it:
      "B vs A: left +0, right +0, top -1, bottom +0; best shift +0,-1 then 4px changed (no
      shift: 20px)": the head rose 1px, the feet stayed. y grows down, so +1 is lower. The
      edges are the sides of each frame's opaque bounding box (its leftmost, rightmost, top
      and bottom opaque pixels): 'top -1' is B's top row of pixels 1px above A's.
      --rows Y0-Y1 (canvas rows as the readout prints them, both included; one row: --rows Y)
      or --feet N (the bottom N rows) limit the edges and the best shift to that band, so a
      weapon swing above doesn't hide what the feet did: 'B vs A (rows 20-23): left +0, ...'.
      The shift still moves all of A (pixels come into the band from above) and counts only
      the band's pixels. The PNG darkens the rows outside the band.
      --tint-a draws A as a flat silhouette in one color (default #ff4060a0, a translucent
      red; --tint-a '#40a0ff' for opaque blue) instead of faded, so where A shows past B is
      plain to see. Without these flags the PNG is as it always was.
  scene -o s.png [--scale 4] [--size WxH] [--bg #472d3c] [--map M --tile 16x16] [--variant V]
        [--tint #rrggbbaa] ITEM@x,y ...
      Default --scale 4 (not render's 8): a 256x224 scene is 1024x896. --scale 1 for 1x.
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
      %base is the base palette, so 'lamp.px%base@40,20' (or a legend entry 'L lamp.px%base')
      stays unrecolored in a --variant night scene (a lit window, a glowing lamp). '%base'
      works wherever %variant does, and a variant can't be named base.
      Items and legend entries can be PNGs (hero.png@3,4). x,y may be negative (drawn
      partly off the left/top edge), in scene and in compose.
      --tint '#10183080' lays that color, at its alpha, over the whole finished scene (bg,
      map, every item, those with their own %variant too) at 1x, before --scale: a night
      scene in one step. To keep a light bright, render the scene untinted, mask the lit
      circle out of it, and put that PNG over the tinted one. Quote the color in scripts
      (an unquoted word starting with # is a comment there); the '#' may be left off.
  tint IN.png '#rrggbbaa' [-o OUT.png]
      scene --tint on a PNG (a rendered scene): lays the color, at its alpha, over every
      pixel; each pixel keeps its alpha, so transparent pixels stay transparent. Without -o,
      IN is rewritten. Quote the color in scripts; the '#' may be left off.
  Centering: frames of different sizes are bottom-aligned and centered, with the odd
  pixel going left (x = (canvas - frame) // 2). --bg works on render, sheet and scene, and
  takes #rrggbb, #rrggbbaa or 'transparent' (as does every color typed on the command line:
  --tint, tint, palette --add k=transparent; the '#' may be left off).

CHECKING
  check FILE... [--palette P] [--size WxH] [--max-colors N] [--strict]
      Every format error with a code and location, then size / off-palette colors /
      color budget / unused keys per frame. P is a .px, .gpl, .hex, or text of
      #rrggbb. --strict also rejects unknown @sections and @anim/@still lines whose group has
      no frames (without --strict those are a note). Exit 1 on any failure.
      A .map (scene --map) is checked too: every row char has a legend line and every
      legend entry loads as one frame (errors point at the legend line).
      Non-ASCII chars that look like ASCII (Cyrillic/Greek 'а е о р с х у', fullwidth
      'ｋ') get a note naming the line, row and column and the letter they pass for.
  stats FILE...                     size, bbox, color count, colors per frame
  frames FILE[:SEL] [--rm [ID...]] [--move ID --after|--before ID]
         [--copy-to DST [ID...] [--rekey]]
      List frames, sizes, durations (only for animation frames; 'still' for @still groups
      and every frame under '@still *') and animations; or delete / reorder frames (prints
      what it removed or moved, not the listing; a move to where the frames already are
      prints "already in place" and writes nothing). FILE:SEL lists only those frames; 'frames
      hero.px:walk/left --rm' removes them (ids after --rm must be in SEL), and 'frames
      hero.px:walk/left --after idle/3' moves them there as a block, in order. --move ID
      takes a plain FILE and one frame id (a group moves with FILE:GROUP --after ID).
      Removing a group's last frame removes its @anim and @still lines too.
      --copy-to DST copies FILE's frames (FILE:SEL's, or the ids after DST) into the existing
      DST as they play in FILE: each frame's ms and pivot (on its @frame line when DST's @anim
      would change them), the @anim line of a group DST lacks, and @still. They keep FILE's
      order and land after their group's last frame in DST, at the end for a new group, or
      at --after/--before a DST frame: 'frames hero.px:walk --copy-to beast.px --after idle/3'.
      Their keys join DST's palette (in DST's variants too); a key DST has in another color
      is E_KEY_CONFLICT, as for compose, and --rekey gives it a free key in DST as compose's
      does. A frame id DST already has is E_DUP_FRAME. To put
      back a frame removed by mistake, copy it from a copy of the file, --after its neighbor.

EDITING (writes .px; -o defaults to editing the input in place)
  -o OUT always gets the whole file: with FILE:SEL, OUT is a copy of FILE with the selected
  frames edited and every other frame as it was (like editing a copy), and a note says so.
  To get only some frames, extract them first (or after). An OUT in another directory gets
  its @palette lines re-pointed from there (-o art/x.px of a file with '@palette pal.px'
  writes '@palette ../pal.px'), so it imports the same palette file; an absolute path stays.
  Edits rewrite only what changed: other lines keep their spelling and the blank lines and
  comments above them, and new frames get the file's spacing between @frame blocks.
  An edit that changes nothing (set to the same key, flip of a symmetric frame) prints
  "no change: FILE" and leaves the file untouched.
  Limits: sections are written in a fixed order (palette, @variant, @anim/@still, frames,
  unknown @sections), so an @anim written between frames moves up; a comment inside the
  file stays with the line below it and goes when that line goes (a removed frame, cut rows).
  flip FILE [-o OUT] [--v]          mirror selected frames left-right (--v: top-bottom)
  shift FILE [-o OUT] --dx N --dy N [--region x,y,w,h] [--wrap] [--fill KEY]
      Move the frame's pixels (or only the region's) by dx,dy. Pixels moved past the frame's
      edge are dropped, and the pixels the move leaves behind (vacated) become '.', or KEY
      with --fill KEY (a floor under a moved prop). With --region the moved block may land
      outside the region; its '.' pixels don't overwrite what they land on.
      --wrap scrolls pixels around the edges (for animating tiles) instead of dropping them.
  set FILE[:frame] KEY x,y [x,y ...] [-o OUT]    paint single pixels ('.' erases)
  fill FILE[:frame] KEY [--region x,y,w,h] [-o OUT]   paint a rectangle (default: the frame)
  new OUT[:frame] --size WxH [--key K] [--palette P.px] [--still]
      A blank frame ('.'), or one filled with K, in a new file or added to an existing one
      (placed like compose). --palette P.px starts a new OUT that imports P. A frame that
      already exists is E_DUP_FRAME: fill it instead. --still marks its group '@still GROUP'
      (new ui.px:icons/life --still); a top-level frame is never animated and needs none.
  put FILE[:frame] [-o OUT] < grid.txt
      Replace one frame's grid with the rows on stdin: 'pxart put hero.px:walk/1 < w1.txt'.
      Stdin is rows, or palette lines then rows; the keys the rows use join FILE's palette
      the way compose's layers do (a key FILE has in another color is E_KEY_CONFLICT), and
      other keys must be FILE's. Rows are checked like a file's (widths, keys), errors point
      at stdin's lines, and nothing is written on an error. Only that frame's lines change.
      A frame that doesn't exist yet is added, placed like new; a new FILE is started.
  mask FILE[:frame] --keep x,y,w,h | --keep-circle cx,cy,r ... [--dither N] [--invert]
       [--keep-keys K,K | --drop-keys K,K] [-o OUT]
      Erase (set to '.') every pixel outside the rectangle or circle (kept: distance from
      the pixel to cx,cy <= r). --dither N fades the circle's last N px inside its edge
      with a 4x4 ordered (Bayer) dither: a light radius in one command. --invert erases
      the inside and keeps the outside: exactly the pixels the plain mask erases, dither
      band mirrored, so a mask and its --invert split the image with no overlap or gap.
      --keep and --keep-circle repeat, and mix: the kept area is their union (a pixel kept
      by any shape is kept, where dither bands overlap too), and --dither and --invert
      work over the union. Two lamps in one call:
      'mask scene.png --keep-circle 20,30,12 --keep-circle 70,30,12 --dither 4'.
      FILE may be a PNG (a rendered scene; no render -> from-png round trip): outside
      pixels become transparent. Coordinates are the PNG's own pixels, so render the scene
      with --scale 1. -o, if given, must be a .png too.
      --keep-keys W,T,t (or WTt) erases every pixel whose key isn't one of those; --drop-keys
      erases those keys' pixels. Alone, they mask by key over the whole frame; with shapes, a
      pixel stays only when both keep it (the shapes, --invert and --dither as above). .px only.
  crop FILE:frame x,y,w,h -o OUT[:frame] [--rekey] [--used-keys-only]
      Cut the w x h rectangle at x,y out of one frame into a frame of its own: 'crop
      hero.px:idle/0 4,0,8,8 -o parts.px:head'. Quietly: the pixels outside the rectangle are
      what crop is for, so there's no note about them; a rectangle that runs past the frame's
      edge (or starts at a negative x,y) gets '.' there. FILE:frame must be one .px frame.
      OUT is written as compose writes it:
        a new OUT starts with FILE's whole palette (so shade ramps still find their keys):
          its @palette imports, re-pointed from OUT's directory, its key lines and its
          variants; --used-keys-only keeps only the keys the cut uses.
        OUT:frame of an existing OUT adds that frame (after the last frame of its animation,
          or at the end) or replaces it when it exists, and keeps OUT's other frames and
          its own palette: the cut's keys join it. A plain OUT with one unnamed grid has the
          grid replaced; an OUT with named frames needs OUT:frame; an OUT with one unnamed
          grid, written as OUT:frame, first becomes '@frame STEM' (see FORMAT).
      A key the cut uses that OUT has in another color is E_KEY_CONFLICT, naming every such
      key and both colors, with free keys for them; --rekey gives the cut those keys in OUT
      and leaves FILE as it is (or 'pxart recolor FILE ... -o rekeyed/FILE.px', a copy to
      crop from, as the error line prints it; see compose).
  extract FILE:SEL -o OUT [--inline-palette]
      Write only the selected frames to OUT (replacing it), with FILE's palette, @palette
      imports (re-pointed relative to OUT), variants, and @anim/@still lines (minus those
      of groups left behind; @anim lines in the order of the frames' groups):
      'extract hero.px:walk/down -o walk.px'. --inline-palette
      makes OUT self-contained for a hand-off: the imported keys its frames use (and any a
      local @variant line sets) become key lines in OUT, each variant gets the imported
      colors of the keys OUT has, and the @palette lines go. OUT renders exactly like the
      source frames, in every variant.
  recolor FILE a=b ['a<>b'] ['a>b'] [c=#rrggbb] [-o OUT] [--region x,y,w,h]
      a=b repaints key a's pixels as key b (optionally only inside --region); 'a<>b' swaps
      keys a and b (in the region) in one step; quote it, since unquoted < and > are shell
      redirections. 'a>b' gives a's pixels a new key b, in a's color (and a's variant colors):
      when no pixel keeps a and a is FILE's own key, a's palette lines become b's (a rename),
      else b is added and a stays. It frees a key without a visible change, say before
      compose or frames --copy-to meets that key in another color. c=#hex changes key c's
      color everywhere. '.' works as a source key.
      Order: the key moves of one call apply together, each pixel by the key it had before
      the call, so no move feeds another: 'a<>b' c=a turns a's pixels to b and b's and c's
      to a, and a=b b=a is a swap too. A key moved twice is E_BAD_ARG. Color changes set
      the palette and don't move pixels, so c=#hex and c=d can share a call. FILE with no
      :SEL moves keys in every frame; moves over more than one frame print "applied to N
      frames".
  paste SRC[+h|+v|+hv] --into DST[:frame] --at x,y [--region x,y,w,h] [--under] [--rekey]
        [-o OUT]
      Copy SRC's frame (or --region of it) onto DST at x,y; '.' never overwrites. +h / +v
      mirror SRC first, as for compose layers and scene items (--region is then in the
      mirrored frame's coordinates). --under fills only DST's empty pixels: SRC goes behind.
      Keys SRC uses in other colors than DST's are E_KEY_CONFLICT, all named, as for compose;
      --rekey gives them free keys in DST, as compose's does.
  compose -o OUT[:frame] [--size WxH] [--under] [--rekey] [--used-keys-only] LAYER@x,y ...
      Stack single frames (later layers on top; '.' never overwrites) into one frame.
      --under keeps OUT's frame and draws the layers behind it: they fill only its empty
      pixels (a floor or a shadow under a finished sprite). The frame must exist.
      Layers can be frames of one parts file: parts.px:hat@3,0 parts.px:body@0,8.
      An existing OUT keeps its own palette and @palette; each layer's keys are added to it
      unless the key already exists with the same color. A key a layer uses in another color
      than OUT's (or an earlier layer's) is E_KEY_CONFLICT, one line per source file (all its
      layers: 'layers 1-4, 7 (field.px)') naming every key and both colors, and free keys
      for them ('s>a' 't>b'). The free keys are chosen once for the whole compose, so no two
      lines' suggestions collide: a key OUT already has in that color first, then letters
      and digits, then % + - / : ^ _, and only when those run out the keys a shell reads
      (! $ ` ' * ? [ ] { } ~ & ; | < > ( )) or pxart does (, and =). Two ways to use them,
      both leaving the layers' files as they are:
        --rekey: compose gives those keys the free ones in OUT as it goes (the files are
          read, never written) and a note says which: 'note: --rekey gives field.px's keys
          free ones in scene.px: 's>a' 't>b' (field.px is unchanged)'. Composing from the
          same file into OUT again reuses them (OUT has them in those colors by then).
        a copy: 'pxart recolor field.px 's>a' 't>b' -o rekeyed/field.px' (rekeyed/ beside
          OUT), then compose from rekeyed/field.px; the line prints it ready to run.
      (recolor field.px 's>a' 't>b' with no -o renames them in field.px itself, in every
      frame: right when the file itself should change.) A new OUT
      starts with the layers' whole palettes, used or not, so a later 'shade --ramp' or
      recolor finds its keys: when every layer imports the same
      @palette files, OUT imports them too (re-pointed from OUT's directory); otherwise their
      colors become OUT's key lines. Local keys follow, the keys the layers use first: a key
      layers have in different colors gets the color of the layer that uses it, else the
      earlier layer's, and a note names each layer's color left out and why. Variants come
      along for the keys OUT has (the first layer's win). crop writes a new OUT the same way.
      --used-keys-only gives a new OUT only the keys its frame uses (and their variant
      colors; a @palette they all import is still imported, since it adds no key lines), so
      check has no 'unused keys' to note. It isn't the default because the unused keys are
      often a material's ramp: a cloak drawn in its base key c still needs X x C w for
      'shade --ramp XxcCw' to re-shade it. An existing OUT only ever gets the used keys.
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
  anim-set FILE:GROUP [ms=N] [direction=D] [repeat=N] [pivot=X,Y] [--still | --no-still] [-o OUT]
      Write timing: updates the '@anim GROUP' line, or adds one after the other @anim lines.
      FILE:GROUP/ID (one frame) takes only ms=N and pivot=X,Y and sets that frame's own
      ('@frame ID ms=N pivot=X,Y'), which wins over the group's. KEY= with no value clears
      a setting.
      A path that is both a group and a frame means the group. Only that one line changes.
      --still adds '@still GROUP' (the group is no animation: UI icons, parts), --no-still
      removes it; FILE with no :GROUP (or FILE:*) --still writes '@still *' (every frame),
      unless every frame already is in a @still group: then it says so and adds nothing (a
      top-level frame isn't in one, so '@still *' still lists it as still). An @anim line
      stays, unused while the group is still.
  palette FILE [--add k=#hex ...] [--export out.gpl|out.hex [--used]]
          [--extract-to P.px [--repoint]]
      No flags: lists the keys, their colors, where they come from and how often they're
      used, then each variant's keys: 'dusk: overrides o x X c C; keeps e E q' (the keys it
      recolors, then the base keys it leaves alone, both in palette order).
      --extract-to P.px writes FILE's whole palette as a palette file for @palette: every key
      FILE renders with (imported ones too, local ones winning) and every variant, with the
      comments that document them: those above key and @variant lines (a section comment,
      '# glow: left out of dusk on purpose'), from FILE and the palette files it imports,
      and a palette file's header comment (a sprite's header is about the sprite and
      stays). --repoint then replaces FILE's @palette, key and @variant lines with '@palette
      P.px' (re-pointed from FILE's directory): FILE renders the same, and other sprites can
      share P.px.

DRAWING (edits like EDITING: FILE[:SEL] draws on every selected frame, -o OUT, only changed rows
  are rewritten; KEY must be in the palette, '.' erases). Shapes are clipped to the frame (a note
  says how many px fell outside); x,y may be negative. line, rect, poly, ellipse, arc and
  flood print "painted N px".
  line FILE[:frame] KEY x0,y0 x1,y1 [--width N]
      Bresenham: one pixel per step along the longer axis, 8-connected, no doubled corners;
      the same pixels whichever end comes first (0,0 8,2 is three runs of 3). --width N
      paints N px across the line (down for a mostly-horizontal line, right for a mostly-
      vertical one), centered, the odd pixel down/right.
  rect FILE[:frame] KEY x,y,w,h [--fill]          a 1px border, or filled
  poly FILE[:frame] KEY x,y x,y x,y ... [--fill]
      A closed polygon through the points in order: line's pixels from each point to the
      next and from the last back to the first (1px, the same whichever way round it goes).
      --fill adds every pixel whose center is inside (nonzero winding: a self-crossing star
      is solid). Two points are a line. 'poly rock.px o 2,14 5,6 11,3 14,9 12,14 --fill'.
  ellipse FILE[:frame] KEY cx,cy,rx,ry [--fill]
      The ellipse inscribed in the box cx-rx..cx+rx, cy-ry..cy+ry: 2*rx+1 wide, so a whole
      center and radius give odd sizes (4,4,3,3 is 7x7) and both ending in .5 give even ones
      (3.5,3.5,3.5,2.5 is 8x6 at 0,1). A thin 8-connected outline (Zingl's algorithm), mirror-
      symmetric, no stray pixels; boxes 1 or 2 px across are filled.
  arc FILE[:frame] KEY cx,cy,r a0,a1 [--width N]
      Part of the circle ellipse cx,cy,r,r draws, from angle a0 to a1 in degrees, counter-
      clockwise, 0 = right, 90 = up (0,90 is the upper-right quarter; 300,60 wraps through 0;
      a1 - a0 >= 360 is the whole circle). A pixel is on the arc when the direction from the
      center to it is in the range, ends included. --width N thickens it inward: a smear or
      swoosh ('arc hero.px:attack/2 W 16,20,14 20,160 --width 3').
  flood FILE[:frame] KEY x,y [--diagonal]
      Bucket fill: repaint the region of x,y's key that touches x,y through sides (4-connected),
      or corners too with --diagonal. A hole of another key stops it.
  rotate FILE[:SEL] 90|180|270 [-o OUT]    turn frames clockwise (a WxH frame becomes HxW)
  transpose FILE[:SEL] [-o OUT]            mirror across the top-left/bottom-right diagonal
      For deriving path edges and corners from one tile. The shading turns with the pixels
      (after rotate 90 a top-left light is top-right; transpose keeps top-left but swaps
      top-right and bottom-left), so re-light with shade and outline --selective after. A
      frame's pivot turns with it.
  shade FILE[:frame] --ramp d2,d1,base,l1[,l2] [--keys k1,k2] [--base K] [--light nw]
        [--strength N] [--region x,y,w,h] [--dither] [--preview P.png]
      Re-shade a material: the pixels whose key is in --keys (default: the ramp's keys, so a
      shaded material re-shades) get ramp tones by how they face the light. The ramp runs
      darkest to lightest; the base is its middle key (d2,d1,base,l1: the extra key goes
      dark), or --base K. Keys are 'a,b,c' or 'abc'. Nothing outside the material changes.
      --region x,y,w,h repaints only the material inside it, shaded as part of the whole
      frame's material: the region's border is not an edge, only a real one is (an empty
      pixel, another material, or the frame's side). Shade a half, and it matches that half
      of the whole shading.
      Algorithm, per pixel of the material (the shape: those pixels, over the whole frame;
      everything else, and off the frame, is outside):
        1. depth: its distance to the shape's edge (a vector distance transform from the
           edge pixels, those with an outside side neighbor; ~Euclidean, 0 on the edge);
        2. normal: which way is out from it: the pull of the outside pixels within depth + 4
           px minus that of the shape's, 1/distance-weighted (a staircase reads as its slope);
        3. lighting = (normal . light direction) * (1 - depth / strength), in -1..1: an edge
           facing the light is +1, one facing away -1, and the value fades to 0 (the base
           tone) --strength px in (default 2: a rim; the shape's radius: full form shading);
        4. banding: 0..1 splits evenly over the lights, -1..0 over the darks, rounding to the
           nearest step, ties toward the base; then a stray pixel (no 8-neighbor of its own
           tone) takes its neighbors' commonest tone. Deterministic, no noise.
      --dither mixes adjacent tones with a 4x4 ordered (Bayer) pattern where the lighting is
      within a quarter step of a band boundary (and skips the stray-pixel pass). --light: n
      ne e se s sw w nw (default nw). --preview P.png renders the result (render's grid and
      rulers) and writes nothing else. Prints the pixels it changed, by the tone they got,
      darkest first: "changed 24 px: 4->A, 8->B, 8->D, 4->E" (with --preview, "would change").
      'shade hero.px:idle/0 --ramp XxcCw --keys c' shades the cloak c with the ramp X x c C w.
  outline FILE[:frame] --key K [--outside | --inside] [--lit L [--selective]] [--light nw]
          [--corners] [--preview P.png]
      Outline the frame's shape (every pixel whose color isn't transparent). --outside (the
      default) paints the empty pixels touching the shape on a side; --inside repaints the
      shape's own pixels that have an empty side (off the frame counts as empty). Sides only is
      the pixel-perfect rule: a diagonal edge gets a 1px staircase and a square corner is cut,
      so there are no doubled (L-shaped) corners; --corners also takes the pixels touching only
      at a corner (square corners, a 2px staircase). Selective outline (--lit L, or
      --selective --lit L): outline pixels facing the light get L (a darker tone of the
      material, say) and the rest K. Facing: the outline pixel's outward normal (the pull of
      the empty pixels within 2px minus that of the shape's, 1/distance-weighted, so a
      staircase reads as its slope) dotted with the light's direction; above 0 is lit, so a
      nw light lights the top and left edges and a 45-degree edge (ne, sw) stays K.
      --light: n ne e se s sw w nw (default nw). --preview P.png renders the result, as shade's
      does, and writes nothing else. Prints the pixels it changed, by the key they got:
      "changed 12 px: 6->o, 6->l" (outline pixels that already had their key don't count).

CONVERTING
  export FILE[:SEL]... [--frames DIR] [--aseprite sheet.json] [--tiled tiles.tsj] [--variant V]
      --frames: one PNG per frame at DIR/<frame id>.png, and DIR/pivots.json when frames have
        pivots: {"walk/0": {"x": 8, "y": 23}, ...} (frames without one are left out)
      --aseprite: sheet PNG + Aseprite-style JSON (frames, durations, frameTags; pivots as
        Aseprite writes them: meta.slices = one slice "pivot" with a key per frame index,
        {"frame": N, "bounds": {"x": 0, "y": 0, "w": W, "h": H}, "pivot": {"x": X, "y": Y}},
        bounds = the whole frame, pivot relative to it, "pivot" left out for a frame without)
      --tiled: sheet PNG + Tiled tileset JSON with per-tile animations
      (--aseprite x.json and --tiled x.tsj share one identical x.png)
      FILE:SEL exports only those frames; several selectors of one file add up, in file
      order: 'export harbor.px:cobble harbor.px:water --tiled t.tsj' leaves the 32x32
      props out of a 16x16 tileset.
      Id order (the Aseprite frame index, the Tiled tile id, the sheet position): 0, 1, 2...
      over the exported frames with each animation group contiguous, groups in order of
      first appearance, and all top-level frames (no '/' in the id) together as one group
      where the first of them appears. A file that keeps each group together, and its
      top-level frames together, gets ids in file order; otherwise a frame moves up to its
      group: a/0 b/0 a/1 -> a/0=0 a/1=1 b/0=2, and icon walk/0 walk/1 badge -> icon=0
      badge=1 walk/0=2 walk/1=3. Adding, removing or moving frames can renumber others,
      and a Tiled map painted with the old tileset keeps the old ids.
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
  Every error line starts with the command ('ellipse: E_BAD_ARG: cy=1.5 and ry=1 ...'). An
  error in an input file also says which input it came from, then where in the file:
  'compose: layer 2 (parts.px:hat): parts.px:4: E_ROW_WIDTH (frame hat, ...'.
  Inputs are named like -h names them: FILE, SRC, --into, -o, OUT, A/B, layer N, item N,
  file N (the Nth of several), --map, --palette, stdin. check reports per file instead.
  Frames of different sizes in one animation are allowed; check notes them.
"""
import argparse, contextlib, io, json, math, os, pathlib, re, shlex, string, sys, textwrap, unicodedata
from PIL import Image, ImageChops, ImageDraw

FORMAT_VERSION = 1
CLEAR = (0, 0, 0, 0)
DEFAULT_MS = 100
# Keys: printable ASCII minus whitespace and chars with a job ('#' comment, '@' section,
# '.' transparent) or that break XPM export ('"', '\').
KEYS = [c for c in string.ascii_letters + string.digits + string.punctuation if c not in '#@."\\']
# The order free keys are suggested in (E_KEY_CONFLICT's recolor, --rekey): letters and digits, then punctuation that
# nothing reads specially, and only when those run out the keys a shell reads (! $ ` ' * ? [ ] { } ~ & ; | < > ( )) or
# pxart's own arguments do (',' separates --keep-keys and --keys lists, '=' is recolor's a=b).
AWKWARD = set("!$`'*?[]{}~&;|<>(),=")
FREE_ORDER = [k for k in KEYS if k not in AWKWARD] + [k for k in KEYS if k in AWKWARD]
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
        self.ctx = None  # which input of the command it came from: 'layer 2 (parts.px:hat)' (see reading())

    def __str__(self):
        if self.ctx and self.ctx != str(self.path):
            here = Issue(self.code, self.msg, self.path, self.line, self.frame, self.row, self.cols)
            return f"{self.ctx}: {here}"
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
        return (f"{where}: " if where else "") + self.code + (f" ({', '.join(loc)})" if loc else "") + f": {self.msg}"


class PxError(Exception):
    def __init__(self, issues):
        self.issues = issues if isinstance(issues, list) else [issues]
        super().__init__()

    def __str__(self):
        return "\n".join(str(i) for i in self.issues)


def fail(code, msg, **kw):
    raise PxError(Issue(code, msg, **kw))


@contextlib.contextmanager
def reading(label):
    """Errors inside name the input they came from: 'layer 2 (parts.px:hat)'; main adds the command in front.
    The innermost label wins."""
    try:
        yield
    except PxError as e:
        for i in e.issues:
            i.ctx = i.ctx or label
        raise


# ---------------------------------------------------------------------------- model

def hex2rgba(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) if len(h) == 8 else 255)


def parse_color(s, what="color"):
    """A color given on the command line: #rrggbb, #rrggbbaa (the '#' may be left off) or 'transparent'."""
    if s == "transparent":
        return CLEAR
    v = s if s.startswith("#") else "#" + s
    if not COLOR_RE.match(v):
        fail("E_BAD_COLOR", f"{what} {s!r} isn't #rrggbb, #rrggbbaa or transparent (in a script, quote it: "
             "'#10183080'; an unquoted word starting with # is a comment there)")
    return hex2rgba(v)


def rgba(c):
    """A color as rgba: a tuple as is, else a '#rrggbb[aa]' / 'transparent' string."""
    return c if isinstance(c, tuple) else parse_color(c)


def rgba2hex(c):
    return "#%02x%02x%02x" % c[:3] + ("%02x" % c[3] if c[3] < 255 else "")


def fmt_color(c):
    return "transparent" if c[3] == 0 else rgba2hex(c)


def fmt_setting(v):
    """An @anim/@frame setting as written: pivot (8, 23) -> '8,23'; others as they are."""
    return ",".join(map(str, v)) if isinstance(v, tuple) else str(v)


PIVOT_RE = re.compile(r"^-?\d+,-?\d+$")


class Frame:
    def __init__(self, id, grid=None, ms=None, line=None, pivot=None):
        self.id, self.grid, self.ms, self.line = id, grid if grid is not None else [], ms, line
        self.pivot = pivot          # (x, y) set on its @frame line, or None (then the @anim's, if any)
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
        self.at = {}                # anchor -> its line number in the file as parsed
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
        if variant and variant != "base":  # %base: the base palette, whatever --variant says
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

    def pivot(self, f):
        """The frame's pivot (x, y): its own, else its @anim's, else None."""
        return f.pivot or self.anims.get(f.group, {}).get("pivot")

    def select(self, sel):
        if not sel:
            return list(self.frames)
        if self.implicit and sel == self.stem:  # the unnamed grid goes by the file's name, as frames lists it
            return list(self.frames)
        got = [f for f in self.frames if f.id == sel or (f.id or "").startswith(sel + "/")]
        if not got:
            fail("E_SELECT", f"no frame {sel!r}; frames: {', '.join(self.label(f) for f in self.frames)}",
                 path=self.path)
        return got

    def promote(self):
        """The unnamed grid becomes '@frame <stem>' (the id it already goes by), keeping its rows' spelling and the
        blank/comment lines above the grid, now above the @frame line."""
        f, fid = self.frames[0], self.stem
        for j in range(len(f.grid)):
            for store in (self.lead, self.raw, self.at):
                if ("row", None, j) in store:
                    store[("row", fid, j)] = store.pop(("row", None, j))
        self.lead[("frame", fid)] = self.lead.pop(("row", fid, 0), None) or [""]
        self.implicit, f.id = False, fid

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
                fail("E_KEY_CONFLICT", f"key {key!r} is already {fmt_color(have[key])} in {self.path}, not "
                     f"{fmt_color(color)}: to change its color, 'recolor {self.path} {key}={fmt_color(color)}'; "
                     "to keep both colors, add this one under a free key", path=self.path)
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
            parts = [f"@anim {g}"] + [f"{k}={fmt_setting(a[k])}" for k in ("direction", "repeat", "ms", "pivot")
                                      if a.get(k) is not None]
            yield ("anim", g), int(i == 0), " ".join(parts)
        for i, g in enumerate(self.stills):
            yield ("still", g), int(i == 0 and not self.anims), f"@still {g}"
        for i, f in enumerate(self.frames):
            if not self.implicit:
                gap = 1 if i == 0 or self.frame_gap is None else self.frame_gap
                yield ("frame", f.id), gap, f"@frame {f.id}" + (f" ms={f.ms}" if f.ms else "") \
                    + (f" pivot={fmt_setting(f.pivot)}" if f.pivot else "")
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

def imports(doc, ref, sub):
    """doc gets '@palette ref', whose file parsed as sub: its keys and variants (and those it imports) are shared."""
    doc.palette_refs.append(ref)
    doc.shared.update(sub.shared)
    doc.shared.update(sub.palette)
    for vname, over in list(sub.shared_variants.items()) + list(sub.variants.items()):
        doc.shared_variants.setdefault(vname, {}).update(over)


def start_doc(path, palette=None):
    """A new doc for path, not written yet; with palette (a path as typed), importing it, re-pointed from path's
    directory. Read here, not through the @palette line: path's directory may not exist until the doc is saved."""
    doc = Doc(path)
    doc.version = FORMAT_VERSION
    if palette:
        with reading(f"--palette ({palette})"):
            try:
                sub = parse(palette, palette_only=True)
            except FileNotFoundError:
                fail("E_PALETTE_FILE", f"can't find palette file {str(palette)!r}")
        imports(doc, pathlib.Path(os.path.relpath(pathlib.Path(palette).resolve(),
                                                  pathlib.Path(path).resolve().parent)).as_posix(), sub)
    return doc


def _kwargs(tokens, issues, path, n):
    pos, kw = [], {}
    for t in tokens:
        if "=" in t:
            k, _, v = t.partition("=")
            kw[k] = v
        else:
            pos.append(t)
    return pos, kw


def _pivot_arg(kw, issues, path, n):
    if "pivot" not in kw:
        return None
    v = kw.pop("pivot")
    if not PIVOT_RE.match(v):
        issues.append(Issue("E_BAD_ARG", f"pivot={v!r} must be x,y (integers, e.g. pivot=8,23)", path, n))
        return None
    return tuple(map(int, v.split(",")))


def _int_arg(kw, name, issues, path, n, lo=None):
    if name not in kw:
        return None
    v = kw.pop(name)
    if not v.isdigit() or (lo is not None and int(v) < lo):
        issues.append(Issue("E_BAD_ARG", f"{name}={v!r} must be an integer" + (f" >= {lo}" if lo else ""),
                            path, n))
        return None
    return int(v)


def parse(path, strict=False, text=None, palette_only=False, allow_empty=False, known=None, _depth=0):
    """`known`: keys the rows may use without defining them (put's target file's palette)."""
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
        doc.lead[anchor], source[anchor], doc.at[anchor] = list(pending), line, n
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
                pivot = _pivot_arg(kw, issues, str(path), n)
                for k in kw:
                    err("E_BAD_ARG", f"@frame doesn't take {k}=", n)
                cur = Frame(pos[0], ms=ms, line=n, pivot=pivot)
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
                keep(("palref", ref))
                imports(doc, ref, sub)
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
                pivot = _pivot_arg(kw, issues, str(path), n)
                if pivot is not None:
                    a["pivot"] = pivot
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

    pal = {**(known or {}), **doc.resolved()}
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
    out, paths = [], []
    for n, a in enumerate(args, 1):
        with reading(f"file {n} ({a})"):
            got = items(a, variant)
        out += got
        paths += [split_sel(a)[0]] * len(got)
    tell_apart(out, paths)
    return out


def tell_apart(its, paths):
    """Frames with one label from different files (idle/0 of hero.px and of beast.px) are labeled 'hero:idle/0' and
    'beast:idle/0'; files whose stems are the same too go by their path as given ('a/hero.px:idle/0')."""
    files, stems = {}, {}
    for it, p in zip(its, paths):
        files.setdefault(it.label, set()).add(p)
        stems.setdefault(pathlib.Path(p).stem, set()).add(p)
    for it, p in zip(its, paths):
        if len(files[it.label]) > 1:
            stem = pathlib.Path(p).stem
            it.label = f"{stem if len(stems[stem]) == 1 else p}:{it.label}"


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


def sheet(its, out, scale=8, cols=8, bg="#3a3a44", grid=False, rulers=False, fit=False):
    """Frames in a grid of --cols cells, each labeled. Every cell is the largest frame's size; fit: each cell is its own
    frame's (and label's) width, and each row as tall as its tallest frame, rows packed left to right."""
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tiles = [(it, upscale(it.img, scale, grid, rulers)) for it in its]
    lws = [max(text_w(probe, it.label), text_w(probe, f"{it.img.width}x{it.img.height} 99c")) for it in its]
    lw = max(lws)
    iw = max((it.img.width for it in its if it.img.height <= 22), default=0)
    cw = max(max(t.width for _, t in tiles), lw + iw + 8)
    ch = max(t.height for _, t in tiles)
    pad, lab = 10, 26
    cols = max(1, min(cols, len(tiles)))
    rows = (len(tiles) + cols - 1) // cols
    if fit:
        cws = [max(t.width, l + (it.img.width if it.img.height <= 22 else 0) + 8) for (it, t), l in zip(tiles, lws)]
        chs = [max(t.height for _, t in tiles[r * cols:(r + 1) * cols]) for r in range(rows)]
        spots, y = [], pad
        for r in range(rows):
            x = pad
            for n in range(r * cols, min((r + 1) * cols, len(tiles))):
                spots.append((x, y, cws[n], chs[r], lws[n]))
                x += cws[n] + pad
            y += chs[r] + lab + pad
        size = (max(x + w + pad for x, _, w, _, _ in spots), y)
    else:
        spots = [(pad + (n % cols) * (cw + pad), pad + (n // cols) * (ch + lab + pad), cw, ch, lw)
                 for n in range(len(tiles))]
        size = (pad + cols * (cw + pad), pad + rows * (ch + lab + pad))
    s = Image.new("RGBA", size, (30, 30, 36, 255))
    d = ImageDraw.Draw(s)
    for (it, big), (x, y, cw, ch, lw) in zip(tiles, spots):
        d.rectangle([x, y, x + cw - 1, y + ch - 1], fill=rgba(bg))
        s.alpha_composite(big, (x + (cw - big.width) // 2, y + ch - big.height))
        if it.img.height <= lab - 4 and it.img.width <= cw - lw - 6:
            s.alpha_composite(it.img, (x + cw - it.img.width - 2, y + ch + 4))  # 1x beside the label
        d.text((x, y + ch + 2), it.label, fill=(220, 220, 220, 255))
        d.text((x, y + ch + 13), f"{it.img.width}x{it.img.height} {n_colors(it, bg)}c", fill=(150, 150, 160, 255))
    s.save(outpath(out))
    return out


def n_colors(it, bg):
    """The sheet label's color count. A PNG (a scene rendered with this --bg) whose four corners are exactly the
    --bg color doesn't count that color: it's the backdrop, not the art's."""
    cs, bg = colors(it.img), rgba(bg)
    w, h = it.img.size
    if it.doc is None and bg[3] and all(it.img.getpixel(c) == bg for c in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))):
        cs = [c for c in cs if c != bg]
    return len(cs)


def on_bg(img, w, h, bg="#3a3a44"):
    b = Image.new("RGBA", (w, h), rgba(bg))
    b.alpha_composite(img, ((w - img.width) // 2, h - img.height))
    return b


def pivot_layout(its):
    """Where frames draw on one canvas when any of them has a pivot: every pivot lands on the same pixel (a frame
    without one uses its bottom-centre pixel, x = w // 2, y = h - 1). (W, H, [(x, y)]) with the canvas just big
    enough, or None when no frame has a pivot (then frames are bottom-centered as always)."""
    pvs = [it.doc.pivot(it.frame) if it.doc and it.frame else None for it in its]
    if not any(pvs):
        return None
    pvs = [p or (it.img.width // 2, it.img.height - 1) for p, it in zip(pvs, its)]
    spots = [(-px, -py) for px, py in pvs]
    x0, y0 = min(x for x, _ in spots), min(y for _, y in spots)
    spots = [(x - x0, y - y0) for x, y in spots]
    return (max(x + it.img.width for (x, _), it in zip(spots, its)),
            max(y + it.img.height for (_, y), it in zip(spots, its)), spots)


def placed(img, w, h, at, bg):
    """img on a w x h canvas of bg at `at` (a pivot_layout spot)."""
    b = Image.new("RGBA", (w, h), rgba(bg))
    b.alpha_composite(img, at)
    return b


def shifted(img, dx, dy):
    out = Image.new("RGBA", img.size, CLEAR)
    out.paste(img, (dx, dy))
    return out


def rolled(img, dx, dy):
    """img scrolled by dx, dy with wrap-around, as 'shift --wrap' scrolls a tile."""
    return ImageChops.offset(img, dx, dy)


def n_changed(a, b):
    """How many pixels differ between two same-size RGBA images."""
    d = ImageChops.difference(a, b).split()
    return sum(ImageChops.lighter(ImageChops.lighter(d[0], d[1]), ImageChops.lighter(d[2], d[3])).histogram()[1:])


def may_wrap(prev, cur):
    """Whether cur may be prev scrolled around the edges: a ground tile (every pixel opaque in both, so any plain
    shift uncovers empty pixels) or a sparse overlay (at most 1/4 of the pixels opaque in each: snow, rain). A
    sprite in between (a character: walks, idles) never wraps."""
    def opaque(img):
        return sum(img.getchannel("A").histogram()[1:])
    area = cur.width * cur.height
    if prev.size != cur.size:
        return False
    a, b = opaque(prev), opaque(cur)
    return a == b == area or (4 * a <= area and 4 * b <= area)


def best_shift(prev, cur, reach=2, wrap=False):
    """The whole-sprite (dx, dy) that best explains cur as a moved prev: the body bob. With wrap (a tile that fills
    its frame, like falling snow), every scroll of prev around the edges is tried too, and one wins only when it
    leaves strictly fewer pixels changed than the best plain shift: (dx, dy, wrapped)."""
    best, cd = None, pixels(cur)
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            n = sum(1 for a, b in zip(pixels(shifted(prev, dx, dy)), cd) if a != b)
            key = (n, abs(dx) + abs(dy))
            if best is None or key < best[0]:
                best = (key, dx, dy)
    if wrap:
        w, h = cur.size
        tries = [(dx, dy) for dy in range(-((h - 1) // 2), h // 2 + 1) for dx in range(-((w - 1) // 2), w // 2 + 1)]
        key, dx, dy = min(((n_changed(rolled(prev, dx, dy), cur), abs(dx) + abs(dy)), dx, dy) for dx, dy in tries)
        if key[0] < best[0][0]:
            return dx, dy, True
    return best[1], best[2], False


def motion(prev, cur, wrap=False, legs=None):
    """How cur differs from prev: the whole-sprite shift (dx, dy), px changed after it, px changed with
    no shift, `still`: the row from which down the sprite stayed exactly put (0 px changed there), when
    that explains cur far better than moving everything (an idle whose chest rises while the legs stay),
    else None, and whether the shift wraps around the edges (only tried with wrap: frames that fill the
    canvas). A walk whose leg moved 1px has no identical lower rows, so it keeps its shift.
    `legs`: the row from which down every frame of the animation is identical, given once another frame
    showed them still (see still_rows): then any shift that would light those rows up leaves them still
    here too, so the fall of a breath reads like its rise even when an arm moves on the way down."""
    dx, dy, wrapped = best_shift(prev, cur, wrap=wrap)
    w, h = cur.size
    C, P, M = pixels(cur), pixels(prev), pixels((rolled if wrapped else shifted)(prev, dx, dy))
    moved = [sum(M[i] != C[i] for i in range(y * w, y * w + w)) for y in range(h)]
    kept = [sum(P[i] != C[i] for i in range(y * w, y * w + w)) for y in range(h)]
    n_shift, n_none, still = sum(moved), sum(kept), None
    if (dx, dy) != (0, 0) and not wrapped:
        # Rows above y moved by (dx, dy), rows from y down are identical to prev (not one pixel changed there, so
        # a leg that moved 1px rules y out): the best such y, and what it leaves changed.
        # The first such row is the one reported, the same for the rise and the fall (kept is symmetric).
        y = next((y for y in range(h) if not any(kept[y:]) and any(c[3] for c in C[y * w:])), None)
        if y is not None and (3 * sum(moved[:y]) < n_shift or (legs is not None and any(moved[legs:]))):
            still = y
    return dx, dy, n_shift, n_none, still, wrapped


def still_rows(imgs, shape=False):
    """The first row from which down every image is identical (and not empty), or None: legs that never move. shape:
    compare only which pixels are opaque, so a frame recolored whole (a glow) doesn't count as the legs moving."""
    w, h = imgs[0].size
    rows = [[tuple((0, 0, 0, p[3] > 0) if shape else p for p in px[y * w:y * w + w]) for y in range(h)]
            for px in map(pixels, imgs)]
    return next((y for y in range(h) if all(r[y:] == rows[0][y:] for r in rows)
                 and any(p[3] for row in rows[0][y:] for p in row)), None)


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


def repoint(doc, out):
    """doc is about to be written to `out`: its relative @palette paths are re-pointed from out's directory, so the
    copy imports the same palette file. An absolute path stays as written."""
    if doc.path is None or pathlib.Path(out).resolve().parent == doc.path.resolve().parent:
        return
    for i, ref in enumerate(doc.palette_refs):
        if os.path.isabs(ref):
            continue
        new = pathlib.Path(os.path.relpath((doc.path.parent / ref).resolve(), pathlib.Path(out).resolve().parent)).as_posix()
        doc.palette_refs[i] = new
        doc.lead[("palref", new)] = doc.lead.pop(("palref", ref), [])


def write_doc(doc, path=None):
    """Save doc unless the file already holds exactly its text; returns what to print. Written somewhere else, its
    @palette lines are re-pointed from there (repoint)."""
    path = pathlib.Path(path or doc.path)
    repoint(doc, path)
    text = doc.text()
    try:
        with open(path, newline="") as fh:
            if fh.read() == text:
                return f"no change: {path}"
    except (OSError, ValueError):  # missing, or not text
        pass
    return f"wrote {doc.save(path)}"


def edit_target(arg, out, label="FILE"):
    """The shared edit path: (doc, selected frames, where to write). -o gets the whole file with the selection
    edited, never just the selection (that's extract)."""
    path, sel = split_sel(arg)
    with reading(f"{label} ({arg})"):
        doc = parse(path)
        frames = doc.select(sel)
    out = pathlib.Path(out) if out else doc.path
    if sel and out.resolve() != doc.path.resolve():
        print(f"note: {out} gets all of {doc.path} with {sel} edited; for only those frames use "
              f"'pxart extract {doc.path}:{sel} -o {out}'")
    return doc, frames, out


def clashes(dst_doc, src_doc, keys, clear=False):
    """The keys src uses (its non-transparent ones; every one with clear, when a whole grid is copied, not stamped) that
    dst_doc has in other colors, sorted."""
    src_pal, have = src_doc.resolved(), dst_doc.resolved()
    return [k for k in sorted(keys) if k != "." and (clear or src_pal[k][3]) and k in have and have[k] != src_pal[k]]


def new_keys(bad, src_pal, have, taken):
    """Where src's clashing keys can go, chosen once for the whole command: a key dst already has in the same color (and
    src hasn't), else the first free key in FREE_ORDER (shell-safe first) that isn't in `taken`, which it adds to, so
    no two suggestions collide. {key: new key}, or None when there aren't enough free keys."""
    moves = {}
    for k in bad:
        same = next((c for c, v in have.items() if v == src_pal[k] and c != "." and c not in src_pal
                     and c not in moves.values()), None)
        pick = same or next((c for c in FREE_ORDER if c not in taken and c not in have and c not in src_pal), None)
        if pick is None:
            return None
        moves[k] = pick
        taken.add(pick)
    return moves


def conflict_issue(bad, src_doc, have, what, dst_name, redo, moves, whose=None, copy=None):
    """One E_KEY_CONFLICT naming every clashing key of src, both colors (and whose dst's is: whose, key -> label), and
    two fixes that keep both colors and leave src as it is: `redo` --rekey, which gives src's keys `moves` in dst only,
    or recolor 'k>K' into `copy` (a path under dst's directory) and `redo` from that. A copy that is src itself (it
    already is one) is recolored in place."""
    src_pal = src_doc.resolved()
    if moves is None:
        fix = "; there aren't enough free keys to rename them: repaint some as keys both have in one color"
    else:
        whose_keys = what + ("'" if what.endswith("s") else "'s")  # this layer's, these layers'
        mv = " ".join(shlex.quote(f"{k}>{v}") for k, v in moves.items())
        src = str(src_doc.path)
        copy = pathlib.Path(copy) if copy else None
        same = copy is None or copy.resolve() == src_doc.path.resolve()
        recipe = " ".join(["pxart recolor", shlex.quote(src), mv] + ([] if same else ["-o", shlex.quote(str(copy))]))
        fix = (f"; to keep both colors (no pixel changes color), add --rekey: {redo} then gives {whose_keys} keys "
               f"free ones in {dst_name} ({mv}) and leaves {src} as it is. Or "
               + (f"give them those keys in {src} itself: {recipe}" if same else
                  f"give them those keys in a copy and {REDO_FROM.get(redo, redo)} from that: {recipe}"))
    n = len(bad)
    each = ", ".join(f"{k!r} {fmt_color(src_pal[k])} ({fmt_color(have[k])} there"
                     + (f", from {whose[k]}" if whose and whose.get(k) else "") + ")" for k in bad)
    return Issue("E_KEY_CONFLICT", f"{n} key{'s' * (n > 1)} of {what} "
                 f"{'are other colors' if n > 1 else 'is another color'} in {dst_name}: {each}{fix}")


REDO_FROM = {"frames --copy-to": "copy the frames"}  # '... and copy the frames from that'


def rekey_copy(src, dst, taken=None):
    """Where E_KEY_CONFLICT's recolor writes src's copy: 'rekeyed/' beside dst (its directory as typed), under src's
    name; `taken` (copies already suggested, which it adds to) gets NAME-2.px and so on, so two sources never share
    one."""
    src = pathlib.Path(src)
    base = pathlib.Path(dst).parent / "rekeyed"
    copy, n = base / src.name, 1
    while taken is not None and copy.resolve() in taken:
        n += 1
        copy = base / f"{src.stem}-{n}{src.suffix}"
    if taken is not None:
        taken.add(copy.resolve())
    return copy


def key_conflicts(dst_doc, src_doc, keys, what, dst_name, redo, clear=False, dst_path=None):
    """One source's clashes with dst as an E_KEY_CONFLICT Issue (conflict_issue), or None when there are none."""
    bad = clashes(dst_doc, src_doc, keys, clear)
    if not bad:
        return None
    have = dst_doc.resolved()
    moves = new_keys(bad, src_doc.resolved(), have, set(have) | set(src_doc.resolved()))
    return conflict_issue(bad, src_doc, have, what, dst_name, redo, moves,
                          copy=rekey_copy(src_doc.path, dst_path or dst_name))


def rekey(doc, moves, frames=()):
    """--rekey: doc's keys move in memory only (doc is never saved): each k's pixels become v in every frame (and in
    `frames`, copies such as a mirrored layer), and k's palette and variant lines become v's (rename_key)."""
    for f in {id(f): f for f in list(doc.frames) + list(frames)}.values():
        f.grid = ["".join(moves.get(c, c) for c in r) for r in f.grid]
    for k, v in moves.items():
        rename_key(doc, k, v)


def said_rekey(src, dst, moves):
    return (f"note: --rekey gives {src}'s keys free ones in {dst}: "
            + " ".join(shlex.quote(f"{k}>{v}") for k, v in moves.items()) + f" ({src} is unchanged)")


def spans(ns):
    """[1, 2, 3, 5] -> '1-3, 5'."""
    out = []
    for n in ns:
        if out and out[-1][1] == n - 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in out)


def stamp(dst_doc, dst, src_doc, src, at, region=None, under=False, what="SRC", redo="paste", out=None):
    """Copy src frame (or a region of it) onto dst frame at `at`; '.'/transparent keys don't overwrite. under: only
    onto dst's empty (transparent) pixels, so src goes behind what dst has."""
    src_pal = src_doc.resolved()
    clash = key_conflicts(dst_doc, src_doc, set("".join(src.grid)), what, out or dst_doc.path, redo)
    if clash:
        raise PxError(clash)
    for k in sorted(set("".join(src.grid))):  # sorted: new keys land in one order every run
        if src_pal[k][3]:
            dst_doc.add_key(k, src_pal[k])
    x0, y0, w, h = parse_rect(region, src.size)
    W, H = dst.size
    g = [list(r) for r in dst.grid]
    dst_pal = dst_doc.resolved()
    for y in range(h):
        for x in range(w):
            if not (0 <= y0 + y < src.size[1] and 0 <= x0 + x < src.size[0]):
                continue
            ch = src.grid[y0 + y][x0 + x]
            tx, ty = at[0] + x, at[1] + y
            if src_pal[ch][3] and 0 <= tx < W and 0 <= ty < H and not (under and dst_pal[g[ty][tx]][3]):
                g[ty][tx] = ch
    dst.grid = ["".join(r) for r in g]


# ---------------------------------------------------------------------------- commands

def cmd_render(a):
    a.bg = parse_color(a.bg, "--bg")
    its = all_items(a.files, a.variant)
    for f in a.files:
        path, sel = split_sel(f)
        if a.png and path.endswith(".px") and not sel:
            doc = parse(path)
            if len(doc.frames) == 1:
                doc.image(doc.frames[0], a.variant).save(pathlib.Path(path).with_suffix(".png"))
    print("wrote", sheet(its, a.o, a.scale, bg=a.bg, grid=not a.no_grid, rulers=not a.no_grid))


def cmd_sheet(a):
    a.bg = parse_color(a.bg, "--bg")
    print("wrote", sheet(all_items(a.files, a.variant), a.o, a.scale, a.cols, a.bg, grid=a.grid, fit=a.fit))


def cmd_anim(a):
    """GIF + strip, and one line of numbers per frame; without -o only the numbers (nothing is written)."""
    its = all_items(a.files, a.variant)
    frames = [it.img for it in its]
    durs = [1000 // a.fps if a.fps else it.ms for it in its]
    lay = pivot_layout(its)  # pivots, when the file has them, line up; else frames are bottom-centered
    w, h = lay[:2] if lay else (max(f.width for f in frames), max(f.height for f in frames))

    def fit(i, bg="#3a3a44"):
        return placed(frames[i], w, h, lay[2][i], bg) if lay else on_bg(frames[i], w, h, bg)
    framed = [fit(i) for i in range(len(frames))]
    S, gap = a.scale, 8
    if a.o:
        gif = []
        for f in framed:
            canvas = Image.new("RGBA", (w * S + gap * 3 + w * 3, max(h * S, h * 3 + gap)), (30, 30, 36, 255))
            canvas.alpha_composite(f.resize((w * S, h * S), Image.NEAREST), (0, 0))
            canvas.alpha_composite(f, (w * S + gap, 0))                                        # 1x
            canvas.alpha_composite(f.resize((w * 2, h * 2), Image.NEAREST), (w * S + gap * 2 + w, 0))  # 2x
            gif.append(canvas.convert("P", palette=Image.ADAPTIVE))
        gif[0].save(outpath(a.o), save_all=True, append_images=gif[1:], duration=durs, loop=0, disposal=2)
        pad, lab, lab2 = 8, 14, 26
        size = (pad + len(framed) * (w * S + pad), pad + 2 * (h * S + pad) + lab + lab2)
        strip = Image.new("RGBA", size, (30, 30, 36, 255))
        d = ImageDraw.Draw(strip)
    # Compare on a shared canvas, placed as drawn, so frames of different sizes diff too.
    clear = [fit(i, "#00000000") for i in range(len(frames))]
    pairs = [(clear[i - 1], clear[i], frames[i - 1].size == frames[i].size == (w, h) and may_wrap(clear[i - 1], clear[i]))
             for i in range(len(frames))]
    moves = [motion(p, c, wrap=t) for p, c, t in pairs]
    legs = still_rows(clear)
    if still_rows(clear, shape=True) is None:  # the legs move somewhere in the animation (a walk): a frame whose legs
        moves = [m[:4] + (None,) + m[5:] for m in moves]  # happen to stay put bobbed, and the shift says so
    elif legs is not None and any(m[4] is not None for m in moves):  # one frame showed the legs still; so does every
        # frame whose shift would light them
        moves = [motion(*pairs[i][:2], wrap=pairs[i][2], legs=legs) if m[4] is None and m[:2] != (0, 0) and not m[5]
                 else m for i, m in enumerate(moves)]
    for i, fr in enumerate(framed):
        prev, cur = pairs[i][:2]
        dx, dy, n_shift, n_none, still, wrapped = moves[i]
        opaque = sum(cur.getchannel("A").histogram()[1:])

        def px(n):  # '72px (9%)': of the frame's opaque pixels
            return f"{n}px ({(200 * n + opaque) // (2 * opaque)}%)" if opaque else f"{n}px"
        if wrapped:
            base, head = rolled(prev, dx, dy), f"shift {dx:+d},{dy:+d} (wrap) then {px(n_shift)}"
            alt = f"(no shift: {n_none}px)"
        elif still is None:
            base, head = shifted(prev, dx, dy), f"shift {dx:+d},{dy:+d} then {px(n_shift)}"
            alt = f"(no shift: {n_none}px)" if (dx, dy) != (0, 0) else ""
        else:
            base, head = prev, f"no shift then {px(n_none)}"
            alt = f"(rows {still}+ still; shift {dx:+d},{dy:+d}: {n_shift}px)"
        print(f"  {its[i].label:24} {durs[i]:5}ms  vs {its[i - 1].label}: {head}" + (f" {alt}" if alt else ""))
        if not a.o:
            continue
        x = pad + i * (w * S + pad)
        strip.alpha_composite(upscale(fr, S, grid=True), (x, pad))
        d.text((x, pad + h * S + 1), f"{its[i].label} {durs[i]}ms", fill=(220, 220, 220, 255))
        y2 = pad * 2 + h * S + lab
        strip.alpha_composite(upscale(on_bg(diff_frame(base, cur), w, h, "#1e1e24"), S, grid=True), (x, y2))
        d.text((x, y2 + h * S + 1), head, fill=(255, 120, 220, 255))
        d.text((x, y2 + h * S + 13), alt, fill=(200, 140, 190, 255))
    if not a.o:
        return
    sp = pathlib.Path(a.o).with_suffix(".strip.png")
    strip.save(sp)
    print("wrote", a.o, "and", sp)


def cmd_onion(a):
    with reading(f"A ({a.a})"):
        ia = one_frame(a.a)
    with reading(f"B ({a.b})"):
        ib = one_frame(a.b)
    A, B = ia.img, ib.img
    lay = pivot_layout([ia, ib])
    w, h = lay[:2] if lay else (max(A.width, B.width), max(A.height, B.height))
    spots = lay[2] if lay else [((w - A.width) // 2, h - A.height), ((w - B.width) // 2, h - B.height)]
    band = onion_band(a, h)
    base = on_bg(Image.new("RGBA", (1, 1), CLEAR), w, h)
    if a.tint_a:  # A as a flat silhouette in one color, at that color's alpha: where it shows past B is plain
        c = parse_color(a.tint_a, "--tint-a")
        faded = Image.new("RGBA", A.size, c[:3] + (0,))
        faded.putalpha(A.getchannel("A").point(lambda v: v * c[3] // 255))
    else:
        faded = A.copy(); faded.putalpha(A.getchannel("A").point(lambda v: v * 35 // 100))
    base.alpha_composite(faded, spots[0])
    top = B.copy(); top.putalpha(B.getchannel("A").point(lambda v: v * 80 // 100))
    base.alpha_composite(top, spots[1])
    if band:  # the rows the readout leaves out, darkened
        shade = Image.new("RGBA", (w, h), CLEAR)
        ImageDraw.Draw(shade).rectangle([0, 0, w - 1, h - 1], fill=(0, 0, 0, 150))
        ImageDraw.Draw(shade).rectangle([0, band[0], w - 1, band[1]], fill=CLEAR)
        base.alpha_composite(shade)
    upscale(base, a.scale, grid=True, rulers=True).save(outpath(a.o))
    for line in alignment(ia, ib, w, h, spots, "lined up by pivot" if lay else "bottom-centered", band):
        print(line)
    print("wrote", a.o)


def onion_band(a, h):
    """onion's --rows Y0-Y1 / --feet N as (y0, y1), canvas rows, both included; None for the whole canvas."""
    if a.feet is not None:
        if a.feet < 1:
            fail("E_BAD_ARG", f"--feet {a.feet}: the bottom N rows, N >= 1")
        return max(0, h - a.feet), h - 1
    if a.rows is None:
        return None
    m = re.match(r"^(\d+)(?:-(\d+))?$", a.rows)
    if not m:
        fail("E_BAD_ARG", f"--rows wants Y0-Y1 (canvas rows, both included, like 20-23) or one row Y, got {a.rows!r}")
    y0, y1 = int(m.group(1)), int(m.group(2) or m.group(1))
    if y0 > y1 or y1 >= h:
        fail("E_BAD_ARG", f"--rows {a.rows}: the canvas has rows 0-{h - 1}"
             + (", and Y0 comes first" if y0 > y1 else ""))
    return y0, y1


def band_shift(prev, cur, y0, y1, reach=2):
    """best_shift for a band of rows: all of prev moves (so pixels come in from above and below the band), and only the
    band's pixels count. (dx, dy, px changed after it, px changed with no shift)."""
    box = (0, y0, cur.width, y1 + 1)
    c, best = cur.crop(box), None
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            key = (n_changed(shifted(prev, dx, dy).crop(box), c), abs(dx) + abs(dy))
            if best is None or key < best[0]:
                best = (key, dx, dy)
    return best[1], best[2], best[0][0], n_changed(prev.crop(box), c)


def alignment(ia, ib, w, h, spots, how, band=None):
    """onion's readout: where each frame's opaque pixels sit on the shared canvas, how B's edges moved from A's (a 1px
    jump of the feet is 'bottom +1'), and the whole-sprite shift that best explains B (anim's). band (y0, y1): only
    those canvas rows count, for the edges and the shift (band_shift)."""
    clear = [placed(it.img, w, h, at, "#00000000") for it, at in zip((ia, ib), spots)]
    if band:
        alpha = [c.getchannel("A") for c in clear]
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rectangle([0, band[0], w - 1, band[1]], fill=255)
        boxes = [ImageChops.multiply(al, mask).getbbox() for al in alpha]
        rows = f"row {band[0]}" if band[0] == band[1] else f"rows {band[0]}-{band[1]}"
    else:
        boxes = [c.getchannel("A").getbbox() for c in clear]
    where = f"{rows} of the {w}x{h} canvas" if band else f"on the {w}x{h} canvas"
    lines = [f"{n} {it.label}: " + (f"opaque x {b[0]}..{b[2] - 1}, y {b[1]}..{b[3] - 1}" if b else "empty" if not band
                                    else "nothing opaque" if n == "A" else f"nothing opaque in {rows}")
             + (f" ({where}, {how})" if n == "A" else "")
             for n, it, b in zip("AB", (ia, ib), boxes)]
    if all(boxes):
        (l0, t0, r0, b0), (l1, t1, r1, b1) = boxes
        dx, dy, n_shift, n_none = band_shift(*clear, *band) if band else motion(*clear)[:4]
        lines.append(f"B vs A{f' ({rows})' if band else ''}: left {l1 - l0:+d}, right {r1 - r0:+d}, top {t1 - t0:+d}, "
                     f"bottom {b1 - b0:+d}; best shift {dx:+d},{dy:+d} then {n_shift}px changed (no shift: {n_none}px)")
    return lines


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
    """'#rrggbbaa' (or #rrggbb, or without the '#', or 'transparent': no change) -> rgba."""
    return parse_color(s, "tint")


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
    bg = parse_color(a.bg, "--bg")
    placed = []
    tile = tuple(map(int, a.tile.split("x")))
    if a.map:
        notes = []
        with reading(f"--map ({a.map})"):
            placed, msize = read_map(a.map, tile, notes)
        for n in notes:
            print("note:", n)
    W, H = map(int, a.size.split("x")) if a.size else (msize if a.map else (96, 64))
    sc = Image.new("RGBA", (W, H), bg)
    with reading(f"--map ({a.map})"):
        tiles = load_legend(a.map, a.variant) if a.map else {}
    for arg, x, y in placed:
        draw_at(sc, tiles[arg], *cell_spot(arg, tiles[arg], x, y, tile))
    for n, spec in enumerate(a.specs, 1):
        with reading(f"item {n} ({spec.rpartition('@')[0] or spec})"):
            path, x, y = split_at(spec)
            img = place_item(path, "scene item", a.variant).img
        draw_at(sc, img, x, y)
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
    with reading(f"--palette ({a.palette})"):
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
                for f in doc.frames:
                    pv = doc.pivot(f)
                    if pv and not (0 <= pv[0] < f.size[0] and 0 <= pv[1] < f.size[1]):
                        whose = "its own" if f.pivot else f"@anim {f.group}'s"
                        notes.append(f"frame {f.id}: pivot {fmt_setting(pv)} ({whose}) is outside its {f.size[0]}x"
                                     f"{f.size[1]} frame (allowed: a hand or the ground below the feet; check it's "
                                     "not a typo)")
                if "base" in doc.variants or "base" in doc.shared_variants:
                    notes.append("'@variant base' can't be picked: %base and --variant base mean the base palette; "
                                 "rename it")
                for g, fs in doc.groups().items():
                    if doc.animated(g) and len({f.size for f in fs}) > 1:
                        notes.append(f"animation {g!r} mixes frame sizes ("
                                     + ", ".join(f"{f.id} {f.size[0]}x{f.size[1]}" for f in fs)
                                     + "); frames draw bottom-centered, and Tiled export needs one size")
                for text, n in orphans(doc):
                    msg = f"{text!r} names a group with no frames; remove the line or add frames to it"
                    if a.strict:
                        failed = True
                        print(f"FAIL {path}:{n}: E_SELECT: {msg}")
                    else:
                        notes.append(f"line {n}: {msg} (check --strict fails on it)")
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
    for n, arg in enumerate(a.files, 1):
        with reading(f"file {n} ({arg})"):
            its = items(arg)
        for it in its:
            cs = colors(it.img)
            print(f"{arg if not (it.frame and it.frame.id) else split_sel(arg)[0] + ':' + it.label}: "
                  f"{it.img.width}x{it.img.height} bbox={it.img.getchannel('A').getbbox()} colors={len(cs)} "
                  + " ".join(rgba2hex(c) for c in cs[:32]))


def cmd_frames(a):
    path, sel = split_sel(a.file)
    with reading(f"FILE ({a.file})"):
        doc = parse(path, allow_empty=True)
        picked = doc.select(sel) if sel else doc.frames
    if a.copy_to:
        if a.rm is not None or a.move:
            fail("E_BAD_ARG", "--copy-to copies frames; --rm and --move edit FILE: give one")
        if a.after and a.before:
            fail("E_BAD_ARG", "give --after or --before, not both")
        print(frames_copy(a, doc, sel, picked))
        return
    if a.rm is not None or a.move or a.after or a.before:
        if doc.implicit:
            fail("E_MIXED_FRAMES", "this file has one unnamed grid; nothing to move or remove")
        if a.after and a.before:
            fail("E_BAD_ARG", "give --after or --before, not both")
        had = set(doc.groups())
        did = (frames_sel_edit if sel else frames_edit)(a, doc, sel, picked)
        print("; ".join(did + drop_orphans(doc, had - set(doc.groups())) + [write_doc(doc)]))
        return
    for g, fs in doc.groups(picked).items():
        meta = doc.anims.get(g, {})
        still = doc.still(g)
        whole = len(doc.groups()[g])
        head = f"{g or '(no group)'}: {len(fs)} frame(s)" + (f" (of {whole})" if len(fs) < whole else "") \
            + (" [still]" if still else "")
        extra = ", ".join(f"{k}={fmt_setting(v)}" for k, v in meta.items() if v is not None)
        print(head + (f" [{extra}]" if extra else ""))
        for f in fs:  # a duration only where it plays: a top-level part has none
            when = "still" if still else f"{doc.ms(f)}ms" if doc.animated(g) else None
            pv = f"pivot {fmt_setting(doc.pivot(f))}" if doc.pivot(f) else None
            print("  " + "  ".join(x for x in (doc.label(f), f"{f.size[0]}x{f.size[1]}", when, pv, f"(line {f.line})")
                                   if x))
    if doc.variants:
        print("variants:", ", ".join(doc.variants))


def frames_copy(a, doc, sel, picked):
    """frames SRC[:SEL] --copy-to DST [ID ...] [--after|--before ID]: copy frames into DST as they play in SRC: their
    ids and grids, each frame's ms and pivot (written on its @frame line when DST's @anim would change them), the
    @anim line of a group DST hasn't got, and @still. They land in SRC's order: at --after/--before a DST frame, else
    after the last frame of their group in DST, or at the end. The keys they use join DST's palette."""
    dpath, ids = a.copy_to[0], a.copy_to[1:]
    if doc.implicit:
        fail("E_MIXED_FRAMES", f"{doc.path} has one unnamed grid; name it first (frames need ids to copy): "
             f"pxart put {doc.path}:{doc.stem} -o X.px, or compose -o DST:ID {doc.path}@0,0")
    if split_sel(dpath)[1] is not None:
        fail("E_BAD_ARG", f"--copy-to takes a file ({split_sel(dpath)[0]}): copied frames keep their ids")
    if ids:
        have = {f.id for f in picked}
        missing = [i for i in ids if i not in have]
        if missing:
            fail("E_SELECT", f"--copy-to {', '.join(missing)}: no such frame" + (f" in {sel!r}" if sel else ""))
        picked = [f for f in picked if f.id in ids]
    if not pathlib.Path(dpath).exists():
        fail("E_FILE", f"--copy-to {dpath}: no such file; to start one with these frames: pxart extract "
             f"{doc.path}{':' + sel if sel else ''} -o {dpath}")
    with reading(f"--copy-to ({dpath})"):
        dst = parse(dpath, allow_empty=True)
    if dst.implicit:
        if not ID_RE.match(dst.stem):
            fail("E_MIXED_FRAMES", f"{dpath} has one unnamed grid, and its name {dst.stem!r} can't be a frame id")
        dst.promote()
        print(f"note: {dpath}'s unnamed grid is now '@frame {dst.stem}' (the id it went by)")
    dups = [f.id for f in picked if dst.get(f.id)]
    if dups:
        fail("E_DUP_FRAME", f"{dpath} already has {', '.join(dups)}; remove them first (pxart frames {dpath} --rm "
             f"{' '.join(dups)}) or copy the others")
    anchor = dst.get(a.after or a.before or "")
    if (a.after or a.before) and not anchor:
        fail("E_SELECT", f"--{'after' if a.after else 'before'} {a.after or a.before!r}: no such frame in {dpath}")
    keys = set("".join(r for f in picked for r in f.grid))
    if a.rekey:
        moves = new_keys(clashes(dst, doc, keys, clear=True), doc.resolved(), dst.resolved(),
                         set(dst.resolved()) | set(doc.resolved()))
        if moves:
            rekey(doc, moves)
            keys = set("".join(r for f in picked for r in f.grid))
            print(said_rekey(doc.path, dpath, moves))
    pal = doc.resolved()
    clash = key_conflicts(dst, doc, keys, "FILE", dpath, "frames --copy-to", clear=True)
    if clash:
        clash.ctx = f"FILE ({a.file})"
        raise PxError(clash)
    names = set(dst.variants) | set(dst.shared_variants)
    for k in sorted(keys - set(dst.resolved())):
        dst.palette[k] = pal[k]
        for n in names & (set(doc.variants) | set(doc.shared_variants)):
            if doc.resolved(n)[k] != pal[k]:
                dst.variants.setdefault(n, {})[k] = doc.resolved(n)[k]
    said = []
    for g in dict.fromkeys(f.group for f in picked if f.group):
        if g in doc.anims and g not in dst.anims:
            dst.anims[g] = dict(doc.anims[g])
            said.append(f"added @anim {g}")
        elif g in doc.anims and any(doc.anims[g].get(k) != dst.anims[g].get(k) for k in ("direction", "repeat")):
            print(f"note: {dpath}'s @anim {g} stays (direction and repeat are the group's)")
        if doc.still(g) and not dst.still(g):
            dst.stills.append(g)
            said.append(f"added @still {g}")
    at = dst.frames.index(anchor) + (1 if a.after else 0) if anchor else None
    for f in picked:
        new = Frame(f.id, list(f.grid), f.ms, pivot=f.pivot)
        if at is not None:
            dst.frames.insert(at, new)
            at += 1
        else:
            same = [x for x in dst.frames if x.group == new.group] if new.group else []
            dst.frames.insert(dst.frames.index(same[-1]) + 1 if same else len(dst.frames), new)
        if dst.ms(new) != doc.ms(f):
            new.ms = doc.ms(f)
        if dst.pivot(new) != doc.pivot(f):
            if doc.pivot(f) is None:
                print(f"note: {f.id} has no pivot in {doc.path}, and takes {dpath}'s @anim {f.group} pivot there")
            else:
                new.pivot = doc.pivot(f)
    where = f" ({'after' if a.after else 'before'} {anchor.id})" if anchor else ""
    return "; ".join([f"copied {', '.join(f.id for f in picked)} to {dpath}{where}"] + said + [write_doc(dst)])


def drop_orphans(doc, emptied):
    """The @anim and @still lines of groups that just lost their last frame go too: what went."""
    gone = [f"@anim {g}" for g in doc.anims if g in emptied] + [f"@still {g}" for g in doc.stills if g in emptied]
    doc.anims = {g: v for g, v in doc.anims.items() if g not in emptied}
    doc.stills = [g for g in doc.stills if g not in emptied]
    return [f"removed {', '.join(gone)} (no frames left)"] if gone else []


def orphans(doc):
    """@anim / @still lines that name a group with no frames: [(line text, line number)]."""
    have = set(doc.groups())
    return [(f"@anim {g}", doc.at.get(("anim", g))) for g in doc.anims if g not in have] + \
        [(f"@still {g}", doc.at.get(("still", g))) for g in doc.stills if g != "*" and g not in have]


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
        inside = [g.id for g in doc.frames if (g.id or "").startswith(a.move + "/")]
        if not f and inside:
            where = f"--{'before' if a.before else 'after'} {a.before or a.after or 'ID'}"
            fail("E_BAD_ARG", f"--move {a.move!r} is a group ({', '.join(inside)}); --move takes one frame id. Groups "
                 f"move with 'frames FILE:GROUP --before/--after ID': frames {doc.path}:{a.move} {where}")
        anchor = doc.get(a.after or a.before or "")
        if not f or not anchor or f is anchor:
            fail("E_SELECT", "--move ID needs an existing frame and --after/--before another existing frame")
        was = list(doc.frames)
        doc.frames.remove(f)
        doc.frames.insert(doc.frames.index(anchor) + (1 if a.after else 0), f)
        where = f"{a.move} {'after' if a.after else 'before'} {anchor.id}"
        did.append(f"already in place: {where}" if doc.frames == was else f"moved {where}")
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
    was = list(doc.frames)
    for f in picked:
        doc.frames.remove(f)
    at = doc.frames.index(anchor) + (1 if a.after else 0)
    doc.frames[at:at] = picked
    where = f"{sel} ({len(picked)} frame(s)) {'after' if a.after else 'before'} {anchor.id}"
    return [f"already in place: {where}" if doc.frames == was else f"moved {where}"]


def move_pivot(doc, f, fn):
    """The frame's pixels moved by fn(x, y) -> (x, y): its pivot moves with them. A pivot it inherits from its @anim
    becomes its own when the move changes it (the @anim line is left for the other frames)."""
    was = doc.pivot(f)
    if was is None:
        return
    new = fn(*was)
    if f.pivot is not None or new != was:
        f.pivot = new


def move_pivots(doc, frames, how):
    """The frames' pixels move by how(f) -> fn(x, y) -> (x, y); their pivots move with them. When every frame of a
    group moves and those that use the @anim's pivot all land it on one point, the @anim line's pivot moves (one line,
    no per-frame copies); otherwise each frame gets its own (move_pivot)."""
    picked, done = {id(f) for f in frames}, set()
    for g, fs in doc.groups().items():
        pv = doc.anims.get(g, {}).get("pivot")
        inherit = [f for f in fs if f.pivot is None]
        if not g or pv is None or not inherit or not all(id(f) in picked for f in fs):
            continue
        new = {how(f)(*pv) for f in inherit}
        if len(new) == 1:
            doc.anims[g]["pivot"] = new.pop()
            done |= {id(f) for f in inherit}
    for f in frames:
        if id(f) not in done:
            move_pivot(doc, f, how(f))


def cmd_flip(a):
    doc, frames, out = edit_target(a.file, a.o)
    move_pivots(doc, frames, lambda f: (lambda x, y, h=f.size[1]: (x, h - 1 - y)) if a.v else
                (lambda x, y, w=f.size[0]: (w - 1 - x, y)))
    for f in frames:
        f.grid = f.grid[::-1] if a.v else [r[::-1] for r in f.grid]
    print(write_doc(doc, out))


LIGHTS = {"n": (0, -1), "ne": (1, -1), "e": (1, 0), "se": (1, 1), "s": (0, 1), "sw": (-1, 1), "w": (-1, 0),
          "nw": (-1, -1)}
TURNS = {  # how rotate/transpose move a pixel of a w x h frame, and a direction vector
    "90": (lambda x, y, w, h: (h - 1 - y, x), lambda dx, dy: (-dy, dx)),
    "180": (lambda x, y, w, h: (w - 1 - x, h - 1 - y), lambda dx, dy: (-dx, -dy)),
    "270": (lambda x, y, w, h: (y, w - 1 - x), lambda dx, dy: (dy, -dx)),
    "transpose": (lambda x, y, w, h: (y, x), lambda dx, dy: (dy, dx)),
}


def turn(a, how):
    """rotate / transpose: each selected frame's pixels (and its pivot) move by TURNS[how]."""
    doc, frames, out = edit_target(a.file, a.o)
    move, vec = TURNS[how]
    move_pivots(doc, frames, lambda f: (lambda x, y, w=f.size[0], h=f.size[1]: move(x, y, w, h)))
    for f in frames:
        w, h = f.size
        g = [["."] * (w if how == "180" else h) for _ in range(h if how == "180" else w)]
        for y, row in enumerate(f.grid):
            for x, ch in enumerate(row):
                nx, ny = move(x, y, w, h)
                g[ny][nx] = ch
        f.grid = ["".join(r) for r in g]
        if f.size != (w, h):
            print(f"note: {doc.label(f)} is now {f.size[0]}x{f.size[1]} (was {w}x{h})")
    names = {"nw": "top-left", "ne": "top-right", "se": "bottom-right", "sw": "bottom-left"}
    now = {k: next(n for n, v in LIGHTS.items() if v == vec(*LIGHTS[k])) for k in ("nw", "ne")}
    said = f"a top-left light is now {names[now['nw']]} (--light {now['nw']})" if now["nw"] != "nw" else \
        f"a top-left light stays top-left, a top-right one is now {names[now['ne']]} (--light {now['ne']})"
    msg = write_doc(doc, out)
    if not msg.startswith("no change"):
        print(f"note: the shading turned with the pixels ({said}); re-light with 'shade' and 'outline --selective'")
    print(msg)


def cmd_rotate(a):
    turn(a, a.angle)


def cmd_transpose(a):
    turn(a, "transpose")


def cmd_shift(a):
    """Vacated pixels (in the region, not under the moved block) become '.', or --fill KEY."""
    doc, frames, out = edit_target(a.file, a.o)
    pal = doc.resolved()
    if a.fill is not None and a.wrap:
        fail("E_BAD_ARG", "--fill paints the pixels a shift leaves behind; --wrap leaves none")
    if a.fill is not None and a.fill not in pal:
        fail("E_SELECT", f"shift: --fill key {a.fill!r} not in palette (add it with palette --add)")
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
        bh, bw = len(block), len(block[0]) if block else 0
        for y in range(y0, min(y0 + h, H)):
            for x in range(x0, min(x0 + w, W)):
                under = x0 + a.dx <= x < x0 + bw + a.dx and y0 + a.dy <= y < y0 + bh + a.dy  # the moved block
                g[y][x] = "." if under or a.fill is None else a.fill
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
    by_key = a.keep_keys or a.drop_keys
    if png and by_key:
        fail("E_BAD_ARG", f"--{'keep' if a.keep_keys else 'drop'}-keys picks palette keys, and a PNG has none")
    if not a.keep and not a.keep_circle and not by_key:
        fail("E_BAD_ARG", "mask needs a shape: --keep x,y,w,h and/or --keep-circle cx,cy,r (each repeatable), or "
             "keys: --keep-keys K,K / --drop-keys K,K")
    if a.invert and not a.keep and not a.keep_circle:
        fail("E_BAD_ARG", "--invert turns the shapes inside out, and there are none; to erase keys use --drop-keys")
    if a.dither is not None and (a.dither < 1 or not a.keep_circle):
        fail("E_BAD_ARG", "--dither N wants N >= 1 and --keep-circle")
    shapes = []  # ("rect", x0, y0, w, h) | ("circle", cx, cy, r), in the order given; kept = inside any of them
    for kind, flag, vals, want, conv in (("rect", "--keep", a.keep, "x,y,w,h", int),
                                         ("circle", "--keep-circle", a.keep_circle, "cx,cy,r", float)):
        for v in vals or []:
            try:
                nums = tuple(conv(n) for n in v.split(","))
            except ValueError:
                nums = ()
            if len(nums) != len(want.split(",")):
                fail("E_BAD_ARG", f"{flag} wants {want}, got {v!r}")
            shapes.append((kind,) + nums)

    def keep(x, y):  # --invert keeps exactly what the plain mask erases, dither bands included
        return not shapes or any(inside(s, x, y) for s in shapes) != a.invert

    def inside(s, x, y):
        if s[0] == "rect":
            _, x0, y0, w, h = s
            return x0 <= x < x0 + w and y0 <= y < y0 + h
        _, cx, cy, r = s
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
    keys = set(key_list(by_key, "--keep-keys" if a.keep_keys else "--drop-keys")) if by_key else set()
    if keys - set(doc.resolved()):
        fail("E_SELECT", f"mask: keys {''.join(sorted(keys - set(doc.resolved())))!r} aren't in the palette")
    kept = (lambda ch: ch in keys) if a.keep_keys else (lambda ch: ch not in keys)  # no keys given: every key's kept
    for f in frames:
        g = [list(row) for row in f.grid]
        for y, row in enumerate(g):
            for x, ch in enumerate(row):
                if ch != "." and not (keep(x, y) and kept(ch)):
                    row[x], erased = ".", erased + 1
        f.grid = ["".join(row) for row in g]
    print(f"erased {erased} px;", write_doc(doc, out))


def cmd_recolor(a):
    """Key moves (a=b, 'a<>b') apply together: each pixel is repainted by the move of the key it had before the
    call, so they can't feed each other. Color changes (c=#hex) set the palette and are independent of moves."""
    doc, frames, out = edit_target(a.file, a.o)
    pal = doc.resolved()
    moves, said, renames = {}, {}, {}
    for m in a.maps:
        if len(m) == 3 and m[1] == ">":  # 'a>b': a's pixels get the new key b, in a's color
            k, v = m[0], m[2]
            if k not in pal or k == ".":
                fail("E_SELECT", f"recolor: {m!r}: key {k!r} not in palette" if k != "." else
                     f"recolor: {m!r}: '.' is transparent, not a color to give a new key")
            if v in pal or v in renames.values():
                fail("E_BAD_ARG", f"recolor: {m!r} needs a new key, and {v!r} is already one"
                     + (f" ({fmt_color(pal[v])}); to repaint {k}'s pixels as {v} write {k}={v}" if v in pal else ""))
            if v not in KEYS:
                fail("E_BAD_KEY", f"recolor: {m!r}: {v!r} can't be a palette key")
            if k in moves:
                fail("E_BAD_ARG", f"recolor: key {k!r} is moved twice ({said[k]} and {m}); key moves apply "
                     "together, so each key can go one place")
            moves[k], said[k], renames[k] = v, m, v
            continue
        if "<>" in m:
            k, _, v = m.partition("<>")
            if v.startswith("#") or v == "transparent":
                fail("E_BAD_ARG", f"recolor: {m!r}: '<>' swaps two keys; to change a color write {k}={v}")
            pairs = [(k, v), (v, k)] if k != v else [(k, v)]
        elif "=" in m:
            k, _, v = m.partition("=")
            pairs = [(k, v)]
        else:
            fail("E_BAD_ARG", f"recolor: {m!r} isn't a=b, c=#rrggbb, 'a<>b' or 'a>b' (quote a swap: unquoted, < and > "
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
    for k, v in renames.items():
        rename_key(doc, k, v)
    many = f"applied to {len(frames)} frames; " if moves and len(frames) > 1 else ""  # a whole file is easy to miss
    print(many + write_doc(doc, out))


def rename_key(doc, k, v):
    """recolor 'k>v': the new key v gets k's color, in every variant too. When no frame uses k any more and it is
    this file's own key, its lines become v's in place (a rename); otherwise v is added and k stays."""
    names = sorted(set(doc.variants) | set(doc.shared_variants))
    want = {n: doc.resolved(n)[k] for n in names}
    left = any(k in row for f in doc.frames for row in f.grid)
    if k in doc.palette and not left:
        doc.palette = {v if key == k else key: c for key, c in doc.palette.items()}
        for store in (doc.lead, doc.at):
            if ("key", k) in store:
                store[("key", v)] = store.pop(("key", k))
        for name, over in doc.variants.items():
            if k in over:
                doc.variants[name] = {v if key == k else key: c for key, c in over.items()}
                if ("vkey", name, k) in doc.lead:
                    doc.lead[("vkey", name, v)] = doc.lead.pop(("vkey", name, k))
    else:
        doc.palette[v] = doc.resolved()[k]
        if left:
            print(f"note: {k!r} stays in the palette: pixels outside the recolor still use it")
    for n, c in want.items():
        if doc.resolved(n)[v] != c:
            doc.variants.setdefault(n, {})[v] = c


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
    with reading(f"FILE ({a.src})"):
        src = one_frame(a.src, "crop source")
        if not src.doc:
            fail("E_BAD_ARG", f"crop cuts a .px frame, got {a.src}; for a PNG, 'mask --keep x,y,w,h' erases outside "
                 "the rectangle, or from-png it first")
    x, y, w, h = parse_rect(a.rect, src.frame.size)
    a.layers, a.size, a.cut_note = [f"{a.src}@{-x},{-y}"], f"{w}x{h}", False  # cutting is the point: no note
    a.words = {"label": f"FILE ({a.src})", "what": "FILE", "redo": "crop"}  # crop's nouns, not compose's
    cmd_compose(a)


def cmd_paste(a):
    with reading(f"SRC ({a.src})"):
        src = place_item(a.src, "paste source")
        if not src.doc:
            fail("E_BAD_ARG", f"paste copies a .px frame, got {src.label}")
    ddoc, dframes, out = edit_target(a.into, a.o, "--into")
    ax, ay = map(int, a.at.split(","))
    if a.rekey:
        moves = new_keys(clashes(ddoc, src.doc, set("".join(src.frame.grid))), src.doc.resolved(), ddoc.resolved(),
                         set(ddoc.resolved()) | set(src.doc.resolved()))
        if moves:
            rekey(src.doc, moves, [src.frame])
            print(said_rekey(src.doc.path, out, moves))
    for f in dframes:
        with reading(f"SRC ({a.src})"):
            stamp(ddoc, f, src.doc, src.frame, (ax, ay), a.region, a.under, out=out)
    print(write_doc(ddoc, out))


def cmd_extract(a):
    """Only the selected frames, with the file's palette, @palette imports (re-pointed from OUT's directory),
    variants, and @anim/@still lines except those of groups the selection left behind."""
    path, sel = split_sel(a.file)
    with reading(f"FILE ({a.file})"):
        doc = parse(path)
        keep = doc.select(sel)
    gone = {f.group for f in doc.frames} - {f.group for f in keep}  # groups the selection leaves behind
    doc.frames = keep
    out = pathlib.Path(a.o)
    note_suffix(out)
    order_anims(doc, [f.group for f in keep])
    doc.anims = {g: v for g, v in doc.anims.items() if g not in gone}
    doc.stills = [g for g in doc.stills if g not in gone]
    if a.inline_palette:
        inline_palette(doc)
    print(write_doc(doc, out), f"({len(doc.frames)} frame(s))")


def order_anims(doc, groups):
    """@anim lines in the order `groups` first appear (others after, as they were). Blank lines above them stay
    where they were; a comment moves with its line."""
    old = list(doc.anims)
    new = [g for g in dict.fromkeys(groups) if g in doc.anims] + [g for g in old if g not in groups]
    leads = [doc.lead.get(("anim", g)) for g in old]
    if all(not any(x.strip() for x in lead or []) for lead in leads):
        for g, lead in zip(new, leads):
            doc.lead.pop(("anim", g), None)
            if lead is not None:
                doc.lead[("anim", g)] = lead
    doc.anims = {g: doc.anims[g] for g in new}


def inline_palette(doc):
    """Make doc self-contained: the imported keys its frames use (and any a local @variant sets) become key lines
    ahead of its own, each variant gets the imported colors of every key doc now defines (local ones still win), and
    the @palette lines go, their comments moving to the next line. Renders exactly as before, every variant too."""
    need = set("".join(r for f in doc.frames for r in f.grid)) | {k for over in doc.variants.values() for k in over}
    got = {k: c for k, c in doc.shared.items() if k in need and k not in doc.palette}
    if doc.dot_at is not None:
        doc.dot_at += len(got)
    doc.palette = {**got, **doc.palette}
    for name in list(doc.variants) + [n for n in doc.shared_variants if n not in doc.variants]:
        over = doc.variants.setdefault(name, {})
        for k, c in doc.shared_variants.get(name, {}).items():
            if k in doc.palette and k not in over:
                over[k] = c
    lead = [l for r in doc.palette_refs for l in doc.lead.pop(("palref", r), [])]
    doc.palette_refs, doc.shared, doc.shared_variants = [], {}, {}
    nxt = next((anchor for anchor, _, _ in doc.lines() if anchor != "version"), None)
    if lead and nxt:
        doc.lead[nxt] = lead + (doc.lead.get(nxt) or [])


def frame_slot(opath, osel, palette=None, flag="-o"):
    """Open OUT (or start it, importing `palette`) and find or make the frame OUT[:frame] names: (doc, frame).
    A new frame goes after the last frame of its animation, or at the end when the animation is new."""
    doc = parse(opath, allow_empty=True) if pathlib.Path(opath).exists() else start_doc(opath, palette)
    if osel:
        if doc.implicit:
            if not ID_RE.match(doc.stem):
                fail("E_MIXED_FRAMES", f"{opath} has one unnamed grid, and its name {doc.stem!r} can't be a frame id "
                     f"to give it; can't add frame {osel!r}")
            doc.promote()
            print(f"note: {opath}'s unnamed grid is now '@frame {doc.stem}' (the id it went by)")
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
    with reading(f"OUT ({a.out})"):
        had_grid = not osel and pathlib.Path(opath).exists() and parse(opath, allow_empty=True).implicit
        doc, target = frame_slot(opath, osel, a.palette, flag="new")
    if target.grid or had_grid:
        fail("E_DUP_FRAME", f"{opath} already has " + (f"frame {osel!r}" if osel else "its grid")
             + f"; repaint it with 'pxart fill {a.out} KEY'")
    key = a.key or "."
    if key not in doc.resolved():
        fail("E_SELECT", f"new: key {key!r} not in palette (add it with palette --add, or start with --palette)")
    target.grid = [key * w] * h
    still = ""
    if a.still and target.group and not doc.still(target.group):
        doc.stills.append(target.group)
        still = f"; @still {target.group}"
    elif a.still and not target.group:
        print(f"note: {doc.label(target)} is a top-level frame, never animated: no @still line needed")
    print(write_doc(doc, opath) + (f" frame {osel}" if osel else "") + still)


def cmd_put(a):
    """One frame's grid from stdin (rows, or palette lines then rows) into FILE[:frame]; the file's other lines stay
    as they were. A new frame is placed like new's; the stdin keys the rows use join the palette like compose's."""
    path, sel = split_sel(a.target)
    if sys.stdin is None or sys.stdin.isatty():
        fail("E_BAD_ARG", f"put reads the grid from stdin: pxart put {a.target} < grid.txt")
    out = pathlib.Path(a.o) if a.o else pathlib.Path(path)
    note_suffix(out)
    with reading(f"FILE ({a.target})"):
        doc, target = frame_slot(path, sel, flag="put")
        inside = [f.id for f in doc.frames if f is not target and (f.id or "").startswith(f"{sel}/")] if sel else []
        if inside:
            fail("E_SELECT", f"put writes one frame, and {sel!r} is a group ({', '.join(inside)}); name one frame: "
                 f"put {path}:{inside[0]}", path=path)
    text = sys.stdin.read()
    with reading("stdin"):
        src = parse("stdin", text=text, allow_empty=True, known=doc.resolved())
        if (src.frames and not src.implicit) or src.palette_refs or src.variants or src.anims or src.stills \
                or src.extensions:
            fail("E_BAD_ARG", f"put reads one grid from stdin: palette lines ('k #rrggbb') and rows, no @ lines (the "
                 f"frame is named on the command line: put {path}:FRAME)", path="stdin")
        if not src.frames:
            fail("E_NO_FRAMES", "no grid rows on stdin", path="stdin")
        grid, clash = src.frames[0].grid, []
        for k in sorted(set("".join(grid))):
            if k in src.palette:
                have = doc.resolved().get(k)
                if have and have != src.palette[k]:
                    n = next(n for n, l in enumerate(text.splitlines(), 1)
                             if l.strip()[:1] == k and PAL_RE.match(l.strip()))
                    clash.append(Issue("E_KEY_CONFLICT", f"stdin makes {k!r} {fmt_color(src.palette[k])}, but in "
                                       f"{path} it is {fmt_color(have)}; use another key, or the file's color",
                                       "stdin", n))
                    continue
                doc.add_key(k, src.palette[k])
        if clash:
            raise PxError(sorted(clash, key=lambda i: i.line))
    was = target.size if target.grid else None
    if was and was != (len(grid[0]), len(grid)):
        print(f"note: {doc.label(target)} is now {len(grid[0])}x{len(grid)} (was {was[0]}x{was[1]})")
    target.grid = list(grid)
    if sel and out.resolve() != pathlib.Path(path).resolve():
        print(f"note: {out} gets all of {path} with {sel} replaced")
    print(write_doc(doc, out) + (f" frame {sel}" if sel else ""))


def cmd_fill(a):
    doc, frames, out = edit_target(a.file, a.o)
    if a.key not in doc.resolved():
        fail("E_SELECT", f"fill: key {a.key!r} not in palette (add it with palette --add)")
    for f in frames:
        x0, y0, w, h = parse_rect(a.region, f.size)
        f.grid = ["".join(a.key if x0 <= x < x0 + w and y0 <= y < y0 + h else c for x, c in enumerate(row))
                  for y, row in enumerate(f.grid)]
    print(write_doc(doc, out))


# ---------------------------------------------------------------------------- drawing primitives

def coords(s, names, what, half=False):
    """'3,-4' -> (3, -4): len(names) comma-separated integers; with half, 3.5 too (a center or radius on a pixel
    edge, for an even-sized ellipse)."""
    num = r"-?\d+(\.[05])?" if half else r"-?\d+"
    parts = (s or "").split(",")
    if len(parts) != len(names) or not all(re.fullmatch(num, p) for p in parts):
        fail("E_BAD_ARG", f"{what} wants {','.join(names)} (integers{', or halves like 3.5' if half else ''}), got {s!r}")
    return tuple(float(p) if half else int(p) for p in parts)


def line_points(x0, y0, x1, y1):
    """Bresenham's line from x0,y0 to x1,y1: one pixel per step along the longer axis, so it is 8-connected with no
    doubled corners. The same pixels whichever end comes first, and the same turned 180 degrees: 0,0 -> 8,2 is
    three runs of 3."""
    if (x1, y1) < (x0, y0):
        x0, y0, x1, y1 = x1, y1, x0, y0
    dx, dy = x1 - x0, y1 - y0
    n = max(abs(dx), abs(dy))
    if not n:
        return [(x0, y0)]
    sx, sy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)

    def minor(d, t):  # rounded, ties toward the nearer end, so the line is the same turned 180 degrees
        return (2 * d * t + n - 1) // (2 * n) if 2 * t <= n else d - (2 * d * (n - t) + n - 1) // (2 * n)
    if abs(dx) >= abs(dy):
        return [(x0 + sx * t, y0 + sy * minor(abs(dy), t)) for t in range(n + 1)]
    return [(x0 + sx * minor(abs(dx), t), y0 + sy * t) for t in range(n + 1)]


def widened(pts, width, across_y):
    """A brush `width` px across the line: down (across_y) or right from each point, centered, odd pixel after."""
    lo = -((width - 1) // 2)
    return [(x, y + k) if across_y else (x + k, y) for x, y in pts for k in range(lo, lo + width)]


def poly_points(pts, fill=False):
    """The closed polygon through pts: line_points from each point to the next and from the last back to the first;
    fill adds every pixel strictly inside it by the nonzero winding rule (a self-crossing star is solid), its center
    tested against the edges through the points' centers."""
    ring = [p for a, b in zip(pts, pts[1:] + pts[:1]) for p in line_points(*a, *b)]
    out = set(ring)
    if not fill or len(pts) < 3:
        return out
    xs, ys = [x for x, _ in pts], [y for _, y in pts]
    for py in range(min(ys), max(ys) + 1):
        for px in range(min(xs), max(xs) + 1):
            wind = 0
            for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
                side = (x1 - x0) * (py - y0) - (px - x0) * (y1 - y0)  # which side of the edge px is on
                if y0 <= py < y1 and side > 0:    # the edge crosses the row to px's right, going one way (half-open,
                    wind += 1                     # so a vertex on the row counts once)
                elif y1 <= py < y0 and side < 0:  # ... or going the other way
                    wind -= 1
            if wind:
                out.add((px, py))
    return out


def ellipse_points(x0, y0, x1, y1, fill=False):
    """The ellipse inscribed in the box x0..x1, y0..y1 (inclusive): Alois Zingl's integer algorithm ('A Rasterizing
    Algorithm for Drawing Curves'), a thin 8-connected outline, mirror-symmetric both ways. fill adds every pixel
    between the outline's ends on each row."""
    a, b = abs(x1 - x0), abs(y1 - y0)
    x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    if a < 2 or b < 2:  # 1 or 2 px across: the whole box (the algorithm would drop the tips)
        return {(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}
    b1 = b & 1
    dx, dy = 4 * (1 - a) * b * b, 4 * (b1 + 1) * a * a
    err = dx + dy + b1 * a * a
    y0 += (b + 1) // 2
    y1 = y0 - b1
    aa, bb = 8 * a * a, 8 * b * b
    pts = set()
    while True:
        pts |= {(x1, y0), (x0, y0), (x0, y1), (x1, y1)}
        e2 = 2 * err
        if e2 <= dy:
            y0, y1 = y0 + 1, y1 - 1
            dy += aa
            err += dy
        if e2 >= dx or 2 * err > dy:
            x0, x1 = x0 + 1, x1 - 1
            dx += bb
            err += dx
        if x0 > x1:
            break
    while y0 - y1 <= b:  # a narrow ellipse stops early: finish its tips (Zingl has < b, which drops the last row)
        pts |= {(x0 - 1, y0), (x1 + 1, y0), (x0 - 1, y1), (x1 + 1, y1)}
        y0, y1 = y0 + 1, y1 - 1
    if fill:
        rows = {}
        for x, y in pts:
            lo, hi = rows.get(y, (x, x))
            rows[y] = (min(lo, x), max(hi, x))
        pts = {(x, y) for y, (lo, hi) in rows.items() for x in range(lo, hi + 1)}
    return pts


def ellipse_box(cx, cy, rx, ry, what, radii=("rx", "ry")):
    """cx,cy,rx,ry -> the inclusive box cx-rx..cx+rx, cy-ry..cy+ry, which must fall on whole pixels. An error names
    the axis that doesn't (radii: how the command calls its radii, 'r' for arc's one)."""
    one = radii[0] == radii[1]
    if rx < 0 or ry < 0:
        fail("E_BAD_ARG", f"{what}: {'r' if one else 'radii'} must be >= 0, got {radii[0]}={rx:g}"
             + ("" if one else f", {radii[1]}={ry:g}"))
    eg = ("7,7,3", "7.5,7.5,3.5") if one else ("7,7,3,3", "7.5,7.5,3.5,3.5")
    for c, r, cn, rn in ((cx, rx, "cx", radii[0]), (cy, ry, "cy", radii[1])):
        if c - r != int(c - r):
            fail("E_BAD_ARG", f"{what}: {cn}={c:g} and {rn}={r:g} put the shape's edge on half a pixel "
                 f"({cn}-{rn}..{cn}+{rn} must be whole pixels): give {cn} and {rn} both whole ({eg[0]}: 7 across) "
                 f"or both ending in .5 ({eg[1]}: 8 across)")
    return tuple(int(v) for v in (cx - rx, cy - ry, cx + rx, cy + ry))


def arc_points(cx, cy, r, a0, a1, width=1):
    """The circle of radius r around cx,cy (as ellipse draws it) from angle a0 to a1 degrees, counter-clockwise, 0 =
    right (east), 90 = up. width > 1 thickens it inward: the pixels of the filled circle r that aren't in the filled
    circle r - width. A pixel is on the arc when the direction from the center to its center is in the range."""
    x0, y0, x1, y1 = ellipse_box(cx, cy, r, r, "arc", ("r", "r"))
    if width <= 1:
        ring = ellipse_points(x0, y0, x1, y1)
    else:
        ring = ellipse_points(x0, y0, x1, y1, fill=True)
        if r - width >= 0:
            ring -= ellipse_points(x0 + width, y0 + width, x1 - width, y1 - width, fill=True)
    span = a1 - a0
    if span >= 360 or span <= -360:
        return ring
    span %= 360

    def on(x, y):
        if x == cx and y == cy:
            return True
        ang = round(math.degrees(math.atan2(cy - y, x - cx)), 9)
        return round((ang - a0) % 360, 9) <= span
    return {p for p in ring if on(*p)}


def flood_points(grid, x, y, diagonal=False):
    """The pixels reachable from x,y through pixels of the same key (4-connected, or 8 with diagonal)."""
    w, h = len(grid[0]), len(grid)
    key, seen, todo = grid[y][x], {(x, y)}, [(x, y)]
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)] + ([(1, 1), (1, -1), (-1, 1), (-1, -1)] if diagonal else [])
    while todo:
        px, py = todo.pop()
        for sx, sy in steps:
            q = (px + sx, py + sy)
            if q not in seen and 0 <= q[0] < w and 0 <= q[1] < h and grid[q[1]][q[0]] == key:
                seen.add(q)
                todo.append(q)
    return seen


def paint(f, pts, key):
    """Set f's pixels at pts to key, dropping those outside the frame: (px changed, px clipped)."""
    w, h = f.size
    g = [list(r) for r in f.grid]
    changed, clipped = 0, 0
    for x, y in dict.fromkeys(pts):
        if not (0 <= x < w and 0 <= y < h):
            clipped += 1
        elif g[y][x] != key:
            g[y][x], changed = key, changed + 1
    f.grid = ["".join(r) for r in g]
    return changed, clipped


def draw(a, shape):
    """The drawing commands' shared edit: paint shape(frame) -> pixels with a.key in each selected frame."""
    doc, frames, out = edit_target(a.file, a.o)
    if a.key not in doc.resolved():
        fail("E_SELECT", f"{a.cmd}: key {a.key!r} not in palette (add it with palette --add)")
    changed = 0
    for f in frames:
        c, cut = paint(f, shape(f), a.key)
        changed += c
        if cut:
            print(f"note: {cut} px of the {a.cmd} fall outside {doc.label(f)} ({f.size[0]}x{f.size[1]}) and were "
                  "clipped")
    print(f"painted {changed} px;", write_doc(doc, out))


def cmd_line(a):
    x0, y0 = coords(a.p0, "xy", "line: the start")
    x1, y1 = coords(a.p1, "xy", "line: the end")
    if a.width < 1:
        fail("E_BAD_ARG", "--width wants N >= 1")
    pts = line_points(x0, y0, x1, y1)
    draw(a, lambda f: widened(pts, a.width, abs(x1 - x0) >= abs(y1 - y0)))


def cmd_rect(a):
    x, y, w, h = coords(a.rect, ("x", "y", "w", "h"), "rect")
    if w < 1 or h < 1:
        fail("E_BAD_ARG", f"rect: w and h must be >= 1, got {a.rect!r}")
    pts = [(xx, yy) for yy in range(y, y + h) for xx in range(x, x + w)
           if a.fill or xx in (x, x + w - 1) or yy in (y, y + h - 1)]
    draw(a, lambda f: pts)


def cmd_poly(a):
    pts = [coords(p, "xy", f"poly: point {n}") for n, p in enumerate(a.points, 1)]
    if len(pts) < 2:
        fail("E_BAD_ARG", "poly wants at least 2 points x,y x,y ... (3 or more for a shape)")
    shape = poly_points(pts, a.fill)
    draw(a, lambda f: sorted(shape, key=lambda p: (p[1], p[0])))


def cmd_ellipse(a):
    cx, cy, rx, ry = coords(a.shape, ("cx", "cy", "rx", "ry"), "ellipse", half=True)
    pts = ellipse_points(*ellipse_box(cx, cy, rx, ry, "ellipse"), fill=a.fill)
    draw(a, lambda f: sorted(pts, key=lambda p: (p[1], p[0])))


def cmd_arc(a):
    cx, cy, r = coords(a.circle, ("cx", "cy", "r"), "arc", half=True)
    try:
        a0, a1 = (float(v) for v in a.angles.split(","))
    except ValueError:
        fail("E_BAD_ARG", f"arc: angles are a0,a1 in degrees (0 = right, 90 = up, counter-clockwise), got {a.angles!r}")
    if a.width < 1:
        fail("E_BAD_ARG", "--width wants N >= 1")
    pts = arc_points(cx, cy, r, a0, a1, a.width)
    draw(a, lambda f: sorted(pts, key=lambda p: (p[1], p[0])))


def cmd_flood(a):
    x, y = coords(a.at, "xy", "flood: the start")

    def region(f):
        if not (0 <= x < f.size[0] and 0 <= y < f.size[1]):
            fail("E_BAD_ARG", f"flood: {x},{y} is outside {f.id or 'the frame'} ({f.size[0]}x{f.size[1]})")
        return flood_points(f.grid, x, y, a.diagonal)
    draw(a, region)


SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))
CORNERS = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def light_vec(name):
    dx, dy = LIGHTS[name]
    n = math.hypot(dx, dy)
    return dx / n, dy / n


def normal(p, inside, reach=2):
    """Which way is out at pixel p, as a unit vector (0, 0 when it can't tell, as inside a 1px line): over the
    (2*reach+1)^2 pixels around p, the pull of each outside pixel minus that of each inside one, weighted
    1/distance. Off the frame counts as outside. The same rule for a shape's edge pixels and for the pixels
    just outside it, and it smooths a staircase edge into the slope it stands for."""
    x, y = p
    sx = sy = 0.0
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            if dx or dy:
                s = -1 if (x + dx, y + dy) in inside else 1
                sx, sy = sx + s * dx / (dx * dx + dy * dy), sy + s * dy / (dx * dx + dy * dy)
    n = math.hypot(sx, sy)
    return (sx / n, sy / n) if n > 1e-9 else (0.0, 0.0)


def opaque_set(doc, f):
    pal = doc.resolved()
    return {(x, y) for y, row in enumerate(f.grid) for x, ch in enumerate(row) if pal[ch][3]}


def outline_points(shape, w, h, inside=False, corners=False):
    """The outline of `shape` (a set of pixels) in a w x h frame: outside, the empty pixels touching it on a side
    (with corners, also those touching it only at a corner); inside, its own pixels with an empty side (corners:
    or an empty corner) neighbor, off the frame counting as empty. Sides only is the pixel-perfect outline: a
    diagonal edge gets a 1px staircase and a square corner is cut, with no doubled (L-shaped) corners."""
    near = SIDES + (CORNERS if corners else ())
    if inside:
        return {p for p in shape if any((p[0] + dx, p[1] + dy) not in shape for dx, dy in near)}
    return {(x, y) for y in range(h) for x in range(w)
            if (x, y) not in shape and any((x + dx, y + dy) in shape for dx, dy in near)}


def changes(by, verb="changed"):
    """'changed 41 px: 29->C, 12->X': the pixels an edit changed, by the key they got (in `by`'s order)."""
    n = sum(by.values())
    return f"{verb} {n} px" + (": " + ", ".join(f"{c}->{k}" for k, c in by.items() if c) if n else "")


def preview(doc, frames, png, what):
    """--preview: render the edited frames (render's grid and rulers) to png; the file isn't written."""
    its = [Item(doc.label(f), doc.image(f), doc.ms(f), doc, f) for f in frames]
    return f"{what}; wrote {sheet(its, png, 8, grid=True, rulers=True)} (preview; {doc.path} unchanged)"


def cmd_outline(a):
    """Outline the frame's opaque pixels with a.key; --lit KEY (selective) on the edges facing the light."""
    if a.preview and a.o:
        fail("E_BAD_ARG", "outline: --preview renders the result to a PNG and writes nothing; drop -o or --preview")
    doc, frames, out = edit_target(a.file, a.o)
    pal = doc.resolved()
    if a.selective and not a.lit:
        fail("E_BAD_ARG", "outline --selective needs --lit KEY: the lighter key for the edges facing the light")
    for k in (a.key, a.lit):
        if k is not None and k not in pal:
            fail("E_SELECT", f"outline: key {k!r} not in palette (add it with palette --add)")
    L = light_vec(a.light)
    by = dict.fromkeys([a.key] + ([a.lit] if a.lit else []), 0)
    for f in frames:
        w, h = f.size
        shape = opaque_set(doc, f)
        ring = sorted(outline_points(shape, w, h, a.inside, a.corners), key=lambda p: (p[1], p[0]))
        lit = [p for p in ring if a.lit and sum(n * l for n, l in zip(normal(p, shape), L)) > 0]
        if a.lit:
            by[a.lit] += paint(f, lit, a.lit)[0]
        by[a.key] += paint(f, [p for p in ring if p not in set(lit)], a.key)[0]
    if a.preview:
        print(preview(doc, frames, a.preview, changes(by, "would change")))
        return
    print(f"{changes(by)};", write_doc(doc, out))


def nearest_edge(shape):
    """For each pixel of shape: (its distance to the shape's edge in px, 0 on the edge, and the edge pixel it is
    nearest to). Edge pixels are those with an empty side neighbor (off the frame is empty). Distances spread from
    the edge 8-connected, each pixel taking its neighbors' nearest edge pixel when that is nearer (a vector
    distance transform: close to Euclidean, and deterministic: ties go to the edge pixel first in (y, x) order)."""
    import heapq
    best, todo = {}, []
    for p in sorted(shape, key=lambda p: (p[1], p[0])):
        if any((p[0] + dx, p[1] + dy) not in shape for dx, dy in SIDES):
            best[p] = (0, p[1], p[0])
            heapq.heappush(todo, (0, p[1], p[0], p))
    while todo:
        d2, ey, ex, p = heapq.heappop(todo)
        if best[p] != (d2, ey, ex):
            continue
        for dx, dy in SIDES + CORNERS:
            q = (p[0] + dx, p[1] + dy)
            if q in shape:
                cand = ((q[0] - ex) ** 2 + (q[1] - ey) ** 2, ey, ex)
                if q not in best or cand < best[q]:
                    best[q] = cand
                    heapq.heappush(todo, cand + (q,))
    return {p: (math.sqrt(d2), (ex, ey)) for p, (d2, ey, ex) in best.items()}


def shade_levels(shape, light, strength=2):
    """Each shape pixel's lighting in -1..1 (the shade algorithm, see -h): its outward normal (normal() over a window
    reaching 2px past its depth, so it sees the edges it is near) dotted with the light direction, fading to 0 (the
    base tone) at `strength` px in from the edge."""
    L = light_vec(light)
    out = {}
    for p, (d, _) in nearest_edge(shape).items():
        w = max(0.0, 1 - d / strength)
        if w:
            n = normal(p, shape, int(d) + 4)
            out[p] = (n[0] * L[0] + n[1] * L[1]) * w
        else:
            out[p] = 0.0
    return out


def ramp_key(v, ramp, base, x, y, dither=False):
    """The ramp key for lighting v in -1..1: lights above the base split 0..1 into equal bands, darks below it
    split -1..0; a band's middle is its key, ties go toward the base. dither: in the middle half of the way from
    one key to the next (a quarter band either side of the boundary), a 4x4 ordered (Bayer) pattern mixes them."""
    steps = len(ramp) - 1 - base if v > 0 else base
    m = abs(v) * steps
    if not steps:
        return ramp[base]
    if dither:
        lo = math.floor(m)
        t = (m - lo - 0.25) / 0.5
        k = lo + (1 if t > (BAYER4[y % 4][x % 4] + 0.5) / 16 else 0)
    else:
        k = math.ceil(m - 0.5)
    k = min(k, steps)
    return ramp[base + k] if v > 0 else ramp[base - k]


def shade_tones(shape, ramp, base, light, strength=2, dither=False):
    """{pixel: ramp key} for a material: shade_levels banded by ramp_key, then (without dither) a stray pixel, one
    with no 8-neighbor of its own tone, takes the tone most of its neighbors have (the one nearer the base on a
    tie), in one pass over the pixels as banded: hand-shaded bands, no specks where an edge's staircase wobbles
    across a band boundary."""
    tones = {(x, y): ramp_key(v, ramp, base, x, y, dither) for (x, y), v in shade_levels(shape, light, strength).items()}
    if dither:
        return tones
    fixed = dict(tones)
    for (x, y), k in sorted(tones.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        near = [tones[q] for q in ((x + dx, y + dy) for dx, dy in SIDES + CORNERS) if q in tones]
        if near and k not in near:
            fixed[(x, y)] = max(sorted(set(near)), key=lambda t: (near.count(t), -abs(ramp.index(t) - base)))
    return fixed


def key_list(s, what):
    """'a,b,c' or 'abc' -> ['a', 'b', 'c'] (',' may itself be a key in the comma form: ',,a' is ',' and 'a')."""
    if len(s) >= 3 and len(s) % 2 and all(c == "," for c in s[1::2]):
        keys = list(s[::2])
    elif "," not in s or len(s) == 1:
        keys = list(s)
    else:
        fail("E_BAD_ARG", f"{what} wants keys like a,b,c (or abc), got {s!r}")
    if len(set(keys)) < len(keys):
        fail("E_BAD_ARG", f"{what} names a key twice: {s!r}")
    return keys


def cmd_shade(a):
    """Re-shade a material (the pixels whose key is in --keys) with a ramp, lit from --light."""
    if a.preview and a.o:
        fail("E_BAD_ARG", "shade: --preview renders the result to a PNG and writes nothing; drop -o or --preview")
    doc, frames, out = edit_target(a.file, a.o)
    pal = doc.resolved()
    ramp = key_list(a.ramp, "--ramp")
    keys = key_list(a.keys, "--keys") if a.keys else list(ramp)
    for k in ramp + keys:
        if k not in pal:
            fail("E_SELECT", f"shade: key {k!r} not in palette (add it with palette --add)")
    if "." in ramp:
        fail("E_BAD_ARG", "shade: '.' can't be a ramp tone (it's transparent)")
    if a.base and a.base not in ramp:
        fail("E_BAD_ARG", f"shade: --base {a.base!r} isn't in --ramp {a.ramp!r}")
    base = ramp.index(a.base) if a.base else len(ramp) // 2
    if a.strength <= 0:
        fail("E_BAD_ARG", "shade: --strength wants N > 0 (px from the edge)")
    by = dict.fromkeys(ramp, 0)  # changed pixels, by the tone they got
    for f in frames:
        x0, y0, rw, rh = parse_rect(a.region, f.size)
        # The whole frame's material is the shape, so --region's own border is no edge; only its pixels change.
        shape = {(x, y) for y, row in enumerate(f.grid) for x, ch in enumerate(row) if ch in keys}
        tones = {p: k for p, k in shade_tones(shape, ramp, base, a.light, a.strength, a.dither).items()
                 if x0 <= p[0] < x0 + rw and y0 <= p[1] < y0 + rh}
        g = [list(r) for r in f.grid]
        for (x, y), k in sorted(tones.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            if g[y][x] != k:
                g[y][x] = k
                by[k] += 1
        f.grid = ["".join(r) for r in g]
    if a.preview:
        print(preview(doc, frames, a.preview, changes(by, "would change")))
        return
    print(f"{changes(by)};", write_doc(doc, out))


def seed_palette(doc, layers, gone=None, used_only=False):
    """A new compose OUT starts with its layers' whole palettes, not only the keys they use, so a later shade ramp
    or recolor finds its keys. When every layer imports the same @palette files, OUT imports them too (re-pointed
    from OUT); otherwise their colors become key lines. Then each layer's keys join in layer order, the keys the
    layers use first: a key OUT already has in the same color is skipped, one that overrides an import (as in the
    layer) stays an override, and an unused key whose char another layer has in another color is left out (a used
    one is E_KEY_CONFLICT when stamped). Variants come along for the keys OUT has in the same base color, the
    first layer's winning. Returns what was left out, [(key, the layer it's left out of, the layer whose color OUT
    has, whether that layer uses it)], and {key: (the layer whose color OUT has, whether it uses it)}. gone: {id(layer
    doc): keys --rekey moved away}, which a shared import may still hold: never seeded. used_only
    (--used-keys-only): only the keys the layers use become key lines (a shared @palette is still imported)."""
    docs = list({id(lay.doc): lay.doc for lay, *_ in layers}.values())
    names = {}
    for lay, _, _, label in layers:
        names.setdefault(id(lay.doc), label)
    imports = {tuple((d.path.parent / r).resolve() for r in d.palette_refs) for d in docs}
    keep = imports.pop() if len(imports) == 1 else ()
    if keep:  # the layers' imports, so their colors: no need to read the palette files again
        doc.palette_refs = [pathlib.Path(os.path.relpath(r, doc.path.resolve().parent)).as_posix() for r in keep]
        doc.shared = dict(docs[0].shared)
        doc.shared_variants = {n: dict(v) for n, v in docs[0].shared_variants.items()}
    used = {id(d): {k for lay, *_ in layers if lay.doc is d for k in "".join(lay.frame.grid)} for d in docs}
    left, whose = [], {}  # whose: key -> (the layer whose color OUT has, whether that layer uses it)
    for want_used in (True,) if used_only else (True, False):
        for d in docs:
            for k, c in d.resolved().items():
                if k == "." or (k in used[id(d)]) != want_used or (keep and k in d.shared and k not in d.palette) \
                        or k in (gone or {}).get(id(d), ()):
                    continue
                have = doc.resolved()
                if k not in have or (have[k] != c and k not in doc.palette):
                    doc.palette[k], whose[k] = c, (names[id(d)], want_used)
                elif have[k] != c and not want_used:
                    left.append((k, names[id(d)]) + whose[k])
    for d in docs:
        base = d.resolved()
        for name in list(d.variants) + ([] if keep else [n for n in d.shared_variants if n not in d.variants]):
            over = {**({} if keep else d.shared_variants.get(name, {})), **d.variants.get(name, {})}
            for k, c in over.items():
                if doc.resolved().get(k) == base.get(k) and k not in doc.variants.get(name, {}) \
                        and doc.shared_variants.get(name, {}).get(k) != c:
                    doc.variants.setdefault(name, {})[k] = c
    return left, whose


def cmd_compose(a):
    """Stack the layers into OUT's frame. --rekey: a dry run first finds the keys that clash and where they can go;
    those move in the layers' docs (in memory, the files stay as they are) and the compose runs for real."""
    layers = compose_layers(a)
    gone = {}
    if getattr(a, "rekey", False):
        try:
            with contextlib.redirect_stdout(io.StringIO()):  # its notes are the real run's
                compose(a, layers, dry=True)
        except PxError as e:
            for path, moves in getattr(e, "moves", {}).items():
                for lay, *_ in layers:
                    if lay.doc.path.resolve() == path:
                        rekey(lay.doc, moves, [lay.frame])
                        gone[id(lay.doc)] = set(moves)
                src = next(lay.doc.path for lay, *_ in layers if lay.doc.path.resolve() == path)
                print(said_rekey(src, split_sel(a.o)[0], moves))
    compose(a, layers, gone=gone)


def compose_layers(a):
    layers = []
    for n, spec in enumerate(a.layers, 1):
        label = f"layer {n} ({spec.rpartition('@')[0] or spec})"  # the layer, without its @x,y
        label = getattr(a, "words", {}).get("label", label)
        with reading(label):
            p, x, y = split_at(spec)
            lay = place_item(p, "layer")
            if not lay.doc:
                fail("E_BAD_ARG", f"compose layers must be .px frames, got {lay.label}")
        layers.append((lay, x, y, label))
    return layers


def compose(a, layers, dry=False, gone=None):
    """compose's run over loaded layers; dry: stop before writing (conflicts are raised all the same, with the keys they
    can move to as e.moves). gone: {id(layer doc): keys --rekey moved away}, left out of a new OUT's palette."""
    opath, osel = split_sel(a.o)
    note_suffix(opath)
    fresh, under = not pathlib.Path(opath).exists(), None  # under: the frame the layers go behind
    with reading(f"-o ({a.o})"):
        if getattr(a, "under", False) and not osel and not fresh:  # OUT's single grid, which frame_slot clears
            was = parse(opath, allow_empty=True)
            under = list(was.frames[0].grid) if was.implicit else None
        doc, target = frame_slot(opath, osel)
    if getattr(a, "under", False):  # (crop has no --under)
        under = list(target.grid) if osel else under
        if not under:
            fail("E_BAD_ARG", f"--under draws the layers behind OUT's frame, and {a.o} has none yet; compose it first "
                 "(or drop --under)")
        if a.size and parse_size(a.size) != (len(under[0]), len(under)):
            fail("E_BAD_ARG", f"--under keeps the frame being replaced, {len(under[0])}x{len(under)}; drop --size "
                 f"{a.size}")
        target.grid = under
    whose = {}  # key -> the layer whose color OUT has
    if fresh:
        left_out, seeded = seed_palette(doc, layers, gone, getattr(a, "used_keys_only", False))
        whose = {k: w[0] for k, w in seeded.items()}
        left = {}
        for k, lost, kept, uses in left_out:
            left.setdefault((lost, kept, uses), []).append(k)
        for (lost, kept, uses), ks in left.items():
            print(f"note: {opath} leaves out {lost}'s color{'s' * (len(ks) > 1)} for {''.join(ks)!r} (unused "
                  f"there): it has {kept}'s, " + ("which that layer uses" if uses else "the earlier layer's"))
    if a.size:
        size, why = tuple(map(int, a.size.split("x"))), "--size"
    elif target.grid:
        size, why = target.size, "the frame being replaced"
    elif osel and any(f.grid for f in doc.frames if f.group == target.group and f is not target):
        size = next(f.size for f in doc.frames if f.group == target.group and f.grid and f is not target)
        why = f"the rest of {target.group!r}"
    else:
        size, why = layers[0][0].frame.size, "the first layer"
    target.grid = ["." * size[0]] * size[1]
    clashed = {}  # every layer's conflicts at once, before anything is drawn, gathered by source file
    for n, (lay, x, y, label) in enumerate(layers, 1):
        keys, pal = set("".join(lay.frame.grid)), lay.doc.resolved()
        bad = clashes(doc, lay.doc, keys)
        if bad:
            c = clashed.setdefault(lay.doc.path.resolve(), {"layers": [], "keys": set()})
            c["layers"].append((n, label, lay.doc))
            c["keys"].update(bad)
        for k in sorted(keys):
            if pal[k][3] and k not in doc.resolved():
                doc.add_key(k, pal[k])
                whose[k] = label
    if clashed:  # one recolor per file, covering every layer of it; free keys chosen once, so no two collide
        have, issues, found, copies = doc.resolved(), [], {}, set()
        taken = set(have) | {k for lay, *_ in layers for k in lay.doc.resolved()}
        for path, c in clashed.items():
            src, ns = c["layers"][0][2], [n for n, *_ in c["layers"]]
            bad = sorted(c["keys"])
            moves = new_keys(bad, src.resolved(), have, taken)
            words = getattr(a, "words", {})
            what = words.get("what") or ("this layer" if len(ns) == 1 else "these layers")
            issue = conflict_issue(bad, src, have, what, f"the new {opath}" if fresh else opath,
                                   words.get("redo", "compose"), moves, whose, rekey_copy(src.path, opath, copies))
            issue.ctx = c["layers"][0][1] if len(ns) == 1 else f"layers {spans(ns)} ({src.path})"
            issues.append(issue)
            if moves:
                found[path] = moves
        err = PxError(issues)
        err.moves = found
        raise err
    if dry:
        return
    for lay, x, y, label in layers:
        w, h = lay.frame.size
        cut = sum(1 for yy, row in enumerate(lay.frame.grid) for xx, ch in enumerate(row)
                  if ch != "." and lay.doc.resolved()[ch][3]
                  and not (0 <= x + xx < size[0] and 0 <= y + yy < size[1]))
        if cut and getattr(a, "cut_note", True):
            print(f"note: {cut} px of {lay.label} fall outside the {size[0]}x{size[1]} canvas "
                  f"(size from {why}) and were cropped")
        with reading(label):
            stamp(doc, target, lay.doc, lay.frame, (x, y))
    if under:  # the frame's own pixels stay on top: the layers show only through its empty ones
        pal = doc.resolved()
        target.grid = ["".join(o if pal[o][3] else n for o, n in zip(was, now)) for was, now in zip(under, target.grid)]
    if fresh and getattr(a, "used_keys_only", False):  # keys that landed on the canvas; a cropped-away one goes
        left = set("".join(target.grid))
        doc.palette = {k: c for k, c in doc.palette.items() if k in left}
        doc.variants = {n: {k: c for k, c in over.items() if k in left} for n, over in doc.variants.items()}
    print(write_doc(doc, opath) + (f" frame {osel}" if osel else ""))


def cmd_dup(a):
    path, sel = split_sel(a.src)
    with reading(f"FILE ({a.src})"):
        doc = parse(path)
    src = doc.get(sel) if sel else None
    if not src:
        fail("E_SELECT", f"dup needs FILE:frame-id of an existing frame; frames: "
             f"{', '.join(doc.label(f) for f in doc.frames)}")
    if doc.get(a.new) or not ID_RE.match(a.new):
        fail("E_DUP_FRAME" if doc.get(a.new) else "E_BAD_ID", f"can't use {a.new!r} as the new frame id")
    new = Frame(a.new, list(src.grid), src.ms, pivot=src.pivot)
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
    if k == "pivot":
        if not PIVOT_RE.match(v):
            fail("E_BAD_ARG", f"pivot={v!r} must be x,y (integers, e.g. pivot=8,23)")
        return tuple(map(int, v.split(",")))
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
    with reading(f"FILE ({a.target})"):
        doc = parse(path)
    out = pathlib.Path(a.o) if a.o else doc.path
    if not sel and (a.still or a.no_still):
        sel = "*"  # the whole file: '@still *'
    if not sel:
        fail("E_SELECT", f"anim-set needs FILE:GROUP (an animation's @anim line) or FILE:GROUP/ID (one frame's ms=); "
             f"animations: {', '.join(g for g in doc.groups() if g) or 'none'}", path=doc.path)
    said = set_still(doc, sel, a.still, a.no_still)
    if said and not a.settings:
        print(f"{said}; {write_doc(doc, out)}")
        return
    kw = {}
    for arg in a.settings:
        k, eq, v = arg.partition("=")
        if not eq or k not in ("ms", "direction", "repeat", "pivot"):
            fail("E_BAD_ARG", f"anim-set: {arg!r}; settings are ms=N, direction=D, repeat=N, pivot=X,Y (KEY= clears "
                 "one)", path=doc.path)
        kw[k] = timing_value(k, v)
    if not kw:
        fail("E_BAD_ARG", "anim-set: give ms=N, direction=D, repeat=N, pivot=X,Y, --still and/or --no-still",
             path=doc.path)
    groups = doc.groups()
    if sel in groups and sel:
        anim = doc.anims.setdefault(sel, {})
        anim.update(kw)
        line = next(text for anchor, _, text in doc.lines() if anchor == ("anim", sel))
        for k in ("ms", "pivot"):
            for f in groups[sel] if kw.get(k) else []:
                if getattr(f, k):
                    print(f"note: {f.id} keeps its own {k}={fmt_setting(getattr(f, k))} (anim-set {doc.path}:{f.id} "
                          f"{k}= clears it)")
    else:
        f = doc.get(sel)
        if not f:
            fail("E_SELECT", f"{sel!r} is neither an animation nor a frame; animations: "
                 f"{', '.join(g for g in groups if g) or 'none'}", path=doc.path)
        if set(kw) - {"ms", "pivot"}:
            fail("E_BAD_ARG", f"{sel!r} is one frame, which takes only ms= and pivot=; direction= and repeat= belong "
                 f"to its animation: anim-set {doc.path}:{f.group or 'GROUP'} ...", path=doc.path)
        for k, v in kw.items():
            setattr(f, k, v)
        line = next(text for anchor, _, text in doc.lines() if anchor == ("frame", f.id))
    print(f"{line}; " + (f"{said}; " if said else "") + write_doc(doc, out))


def set_still(doc, sel, still, no_still):
    """anim-set --still / --no-still: add or remove '@still GROUP' ('*': every frame). What it did, or None."""
    if not still and not no_still:
        if sel == "*":
            fail("E_SELECT", "FILE:* is for --still / --no-still ('@still *'); timing goes on FILE:GROUP",
                 path=doc.path)
        return None
    groups = [g for g in doc.groups() if g]
    if sel != "*" and sel not in groups:
        f = doc.get(sel)
        why = (f"{sel!r} is a top-level frame, which is never animated" if f and not f.group else
               f"{sel!r} is one frame; @still marks its group: anim-set {doc.path}:{f.group} --still" if f else
               f"{sel!r} is no group; groups: {', '.join(groups) or 'none'}")
        fail("E_SELECT", f"--{'still' if still else 'no-still'} marks a group of frames (or FILE for all): {why}",
             path=doc.path)
    if still:
        if sel in doc.stills:
            return f"already @still {sel}"
        if "*" in doc.stills:
            return f"already still: '@still *' marks every frame"
        if sel == "*" and doc.frames and all(f.group and doc.still(f.group) for f in doc.frames):
            have = ", ".join(f"@still {g}" for g in doc.stills if g in doc.groups())
            return f"already still: every frame is in a still group ({have}), so '@still *' would add nothing"
        doc.stills.append(sel)
        if sel in doc.anims:
            print(f"note: @anim {sel} stays; its timing is unused while the group is still")
        return f"@still {sel}"
    if sel != "*" and "*" in doc.stills:
        fail("E_BAD_ARG", f"'@still *' marks every group, {sel!r} too; remove it with anim-set {doc.path} --no-still",
             path=doc.path)
    if sel not in doc.stills:
        return f"not still: {sel}"
    doc.stills.remove(sel)
    return f"removed @still {sel}"


def cmd_palette(a):
    with reading(f"FILE ({a.file})"):
        doc = parse(a.file, palette_only=not _has_grid(a.file))
    for m in a.add or []:
        k, _, v = m.partition("=")
        if not COLOR_RE.match(v) and v != "transparent":
            fail("E_BAD_COLOR", f"{m!r}: want key=#rrggbb, key=#rrggbbaa or key=transparent")
        if len(k) != 1:
            fail("E_BAD_KEY", f"{k!r}: keys are one character")
        doc.add_key(k, CLEAR if v == "transparent" else hex2rgba(v))
    if a.add:
        print(write_doc(doc))
    if a.repoint and not a.extract_to:
        fail("E_BAD_ARG", "--repoint points FILE at the palette file --extract-to OUT.px writes; give both")
    if a.extract_to:
        extract_palette(doc, pathlib.Path(a.extract_to), a.repoint)
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
    if a.add or a.export or a.extract_to:
        return
    for k, v in pal.items():
        src = "shared" if k in doc.shared and k not in doc.palette else ("local" if k != "." else "built-in")
        print(f"{k} {fmt_color(v):11} {src:8}" + (f" used {used.get(k, 0)}" if doc.frames else ""))
    names = sorted(set(doc.variants) | set(doc.shared_variants))
    if names:
        print("variants:", ", ".join(names))
    for name in names:  # what each recolors, and the base keys it leaves alone (a glow kept out of dusk)
        over = {**doc.shared_variants.get(name, {}), **doc.variants.get(name, {})}
        sets = [k for k in pal if k in over and k != "."]
        keeps = [k for k in pal if k not in over and k != "."]
        print(f"  {name}: overrides {' '.join(sets) or 'nothing'}; keeps {' '.join(keeps) or 'nothing'}")


def extract_palette(doc, out, repoint=False):
    """palette FILE --extract-to OUT.px: FILE's whole palette (imported keys too, with local ones winning, as FILE
    renders) and every variant as a palette-only file. repoint: FILE's @palette, key and @variant lines become one
    '@palette OUT.px' line, so it renders the same from there."""
    if doc.path and out.resolve() == doc.path.resolve():
        fail("E_BAD_ARG", f"--extract-to {out} is FILE itself")
    note_suffix(out)
    pal = Doc(out)
    pal.version = FORMAT_VERSION
    pal.palette = {k: c for k, c in doc.resolved().items() if k != "."}
    for name in list(doc.shared_variants) + [n for n in doc.variants if n not in doc.shared_variants]:
        pal.variants[name] = {**doc.shared_variants.get(name, {}), **doc.variants.get(name, {})}
    notes, pal.comments = palette_notes(doc)
    pal.lead.update(notes)
    said = [write_doc(pal, out) + f" ({len(pal.palette)} key(s)" + (f", variants {', '.join(pal.variants)})"
                                                                     if pal.variants else ")")]
    if repoint:
        ref = pathlib.Path(os.path.relpath(out.resolve(), doc.path.resolve().parent)).as_posix()
        first = next((anchor for anchor, _, _ in doc.lines() if anchor[0] in ("palref", "key", "variant")), None)
        lead = doc.lead.get(first)
        if first and first[0] != "palref" and lead:  # its comments went to OUT with its line; the blank lines stay
            lead = [l for l in lead if not l.strip()]
        doc.palette_refs, doc.palette, doc.variants, doc.dot_at = [ref], {}, {}, None
        doc.shared, doc.shared_variants = dict(pal.palette), {n: dict(v) for n, v in pal.variants.items()}
        if lead is not None:
            doc.lead[("palref", ref)] = lead
        said.append(write_doc(doc) + f" (@palette {ref})")
    print("; ".join(said))


def palette_notes(doc, seen=None):
    """The comments that document doc's palette, for --extract-to: ({anchor: lead}, header). The leads are those of its
    key, @variant and variant key lines that carry a comment (blank lines in them kept), its @palette imports' first,
    so its own win; the header is each palette-only file's comments above its first line (doc's too when it is one: a
    sprite's header is about the sprite, and stays with it). An import that can't be read adds nothing."""
    seen = set() if seen is None else seen
    notes, head = {}, []
    if doc.path is not None:
        seen.add(doc.path.resolve())
    for ref in doc.palette_refs:
        target = doc.path.parent / ref
        if target.resolve() in seen:
            continue
        try:
            sub = parse(target, palette_only=True)
        except (OSError, PxError):
            continue
        n, h = palette_notes(sub, seen)
        notes.update(n)
        head += h
    notes.update({a: list(lead) for a, lead in doc.lead.items()
                  if a[0] in ("key", "variant", "vkey") and any(l.strip() for l in lead)})
    if not doc.frames:
        head += [l for l in doc.comments if l.strip()]
    return notes, head


def export_frames(args):
    """export's FILE[:SEL]... : one file, the union of the selections in file order (no SEL: every frame)."""
    paths = list(dict.fromkeys(split_sel(f)[0] for f in args))
    if len(paths) > 1:
        fail("E_BAD_ARG", f"export reads one file, got {', '.join(paths)}; pick parts of one file with "
             f"FILE:SEL FILE:SEL ...")
    with reading(f"FILE ({paths[0]})"):
        doc = parse(paths[0])
    sels = [split_sel(f)[1] for f in args]
    if None in sels:
        return doc, list(doc.frames)
    chosen = set()
    for arg, sel in zip(args, sels):
        with reading(f"FILE ({arg})"):
            chosen |= {id(f) for f in doc.select(sel)}
    return doc, [f for f in doc.frames if id(f) in chosen]


def pivot_slices(doc, its):
    """Pivots as Aseprite's JSON has them (meta.slices, the same shape Aseprite's own sheet export writes): one slice
    named 'pivot' with a key for every frame, in sheet order. A key holds from its frame on, so every frame gets one:
    bounds = the whole frame (its sourceSize, since spriteSourceSize is 0,0), and 'pivot' relative to those bounds, left
    out for a frame without a pivot. No pivots in the file: no slices, as before."""
    if not any(doc.pivot(it.frame) for it in its):
        return []
    keys = []
    for n, it in enumerate(its):
        key = {"frame": n, "bounds": {"x": 0, "y": 0, "w": it.img.width, "h": it.img.height}}
        if doc.pivot(it.frame):
            key["pivot"] = dict(zip("xy", doc.pivot(it.frame)))
        keys.append(key)
    return [{"name": "pivot", "color": "#0000ffff", "keys": keys}]


def cmd_export(a):
    doc, picked = export_frames(a.files)
    variants = {split_variant(f)[1] for f in a.files} - {None}
    if len(variants) > 1:
        fail("E_BAD_ARG", f"export: one variant per export, got %{' %'.join(sorted(variants))}")
    variant = variants.pop() if variants else a.variant
    its = [Item(doc.label(f), doc.image(f, variant), doc.ms(f), doc, f) for f in picked]
    wrote = []
    if a.frames:
        for it in its:
            p = outpath(pathlib.Path(a.frames) / (it.label + ".png"))
            it.img.save(p)
            wrote.append(str(p))
        pivots = {it.label: dict(zip("xy", doc.pivot(it.frame))) for it in its if doc.pivot(it.frame)}
        if pivots:  # only when the file has pivots: {"walk/0": {"x": 8, "y": 23}, ...}, in export order
            p = outpath(pathlib.Path(a.frames) / "pivots.json")
            p.write_text(json.dumps(pivots, indent=1) + "\n")
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
        for g, fs in doc.groups(picked).items():
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
            "scale": "1", "frameTags": tags, "layers": [], "slices": pivot_slices(doc, its2)}}
        jp.write_text(json.dumps(data, indent=1) + "\n")
        wrote += [str(ip), str(jp)]
    if a.tiled:
        if len({it.img.size for it in its}) > 1:
            fail("E_TILE_SIZE", "a Tiled tileset needs every frame the same size: "
                 + ", ".join(f"{it.label} {it.img.width}x{it.img.height}" for it in its)
                 + f"; export only same-size frames with FILE:SEL (export {doc.path}:GROUP ... --tiled X.tsj)")
        its = grouped(its)
        sheet_img, spots, cols, cw, ch = pack(its)
        tp = outpath(a.tiled)
        ip = tp.with_suffix(".png")
        sheet_img.save(ip)
        index = {id(it): n for n, it in enumerate(its)}
        tiles = []
        for g, fs in doc.groups(picked).items():
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
        with reading(f"-o ({a.o})"):
            doc = parse(out, allow_empty=True)
    else:
        doc = start_doc(out or imgs[0][0].with_suffix(".px"), a.palette)
    named = bool(a.id) or len(imgs) > 1 or (doc.frames and not doc.implicit) or (out and out.exists())
    if named and doc.implicit:
        if not ID_RE.match(doc.stem):
            fail("E_MIXED_FRAMES", f"{out} holds one unnamed grid, and its name {doc.stem!r} can't be a frame id to "
                 "give it; import into a new file or one with @frame ids")
        doc.promote()
        print(f"note: {out}'s unnamed grid is now '@frame {doc.stem}' (the id it went by)")
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
        print(write_doc(doc, out) + (f" ({len(imgs)} frame(s))" if named else ""))
    else:
        print(doc.text(), end="")


# ---------------------------------------------------------------------------- per-command help

# 'pxart CMD -h' prints CMD's section of the reference above (__doc__, the one source), then a line naming the
# shared blocks it relies on, to read in pxart -h, rather than pasting them in: each is short, and pasting FORMAT,
# EDITING and DRAWING into every command made its -h long. A NOTES block runs from the line starting with its first
# prefix to the line before the one starting with its second; the tests fail when a command has no section or a
# block loses its first or last line. PASTE is the exception: a section that finishes this command's own text.
NOTES = {
    "FORMAT: frames and animation": ("  Several frames per file", "  pivot=x,y (optional)"),
    "FORMAT: pivots and timing": ("  pivot=x,y (optional)", "  Frame groups that aren't animations"),
    "FORMAT: still groups": ("  Frame groups that aren't animations", "  Palette variants"),
    "FORMAT: variants": ("  Palette variants", "  Anywhere a command takes FILE"),
    "FORMAT: selecting frames": ("  Anywhere a command takes FILE", "LOOKING"),
    "LOOKING: centering": ("  Centering:", "CHECKING"),
    "EDITING": ("EDITING (writes .px", "  flip FILE"),
    "DRAWING": ("DRAWING (edits like EDITING", "  line FILE"),
}
GIST = {  # what each block (or another command's section) has, for the see-also line
    "FORMAT: frames and animation": "@frame ids, groups, @anim",
    "FORMAT: pivots and timing": "pivot=x,y, direction, repeat, ms",
    "FORMAT: still groups": "@still GROUP, @still *",
    "FORMAT: variants": "@variant, %VARIANT",
    "FORMAT: selecting frames": "FILE:SEL, an unnamed grid's name, zsh's \"${F}:sel\"",
    "LOOKING: centering": "frames of different sizes, --bg",
    "EDITING": "-o OUT gets the whole file, only changed lines are rewritten, 'no change'",
    "DRAWING": "FILE[:SEL], KEY, clipping, 'painted N px'",
    "compose": "OUT's palette, frame placement, E_KEY_CONFLICT, --rekey",
    "scene": "--tint, items, maps",
}
EDITS = ["EDITING", "FORMAT: selecting frames"]
DRAWS = ["DRAWING", "EDITING", "FORMAT: selecting frames"]
SEE = {  # what a command's section relies on: other commands' sections (by name) and NOTES, named, not pasted
    "render": ["FORMAT: variants", "LOOKING: centering"], "sheet": ["FORMAT: variants", "LOOKING: centering"],
    "anim": ["FORMAT: frames and animation", "FORMAT: pivots and timing", "FORMAT: variants", "LOOKING: centering"],
    "onion": ["FORMAT: pivots and timing", "LOOKING: centering"], "scene": ["FORMAT: variants"], "tint": ["scene"],
    "check": ["FORMAT: still groups"], "stats": ["FORMAT: selecting frames"],
    "frames": ["FORMAT: frames and animation", "FORMAT: pivots and timing", "FORMAT: still groups",
               "FORMAT: selecting frames"],
    "flip": ["FORMAT: pivots and timing"] + EDITS, "shift": EDITS, "set": EDITS, "fill": EDITS,
    "new": ["compose", "FORMAT: still groups"] + EDITS, "put": ["compose"] + EDITS, "mask": EDITS,
    "crop": ["compose"] + EDITS, "extract": ["FORMAT: variants"] + EDITS, "recolor": ["FORMAT: variants"] + EDITS,
    "paste": ["compose"] + EDITS, "compose": EDITS, "dup": ["FORMAT: frames and animation"] + EDITS,
    "anim-set": ["FORMAT: frames and animation", "FORMAT: pivots and timing", "FORMAT: still groups"] + EDITS,
    "palette": ["FORMAT: variants"] + EDITS,
    "line": DRAWS, "rect": DRAWS, "poly": DRAWS, "ellipse": DRAWS, "arc": DRAWS, "flood": DRAWS,
    "rotate": ["FORMAT: pivots and timing"] + DRAWS, "transpose": ["FORMAT: pivots and timing"] + DRAWS,
    "shade": DRAWS, "outline": DRAWS,
    "export": ["FORMAT: frames and animation", "FORMAT: pivots and timing", "FORMAT: still groups",
               "FORMAT: variants", "FORMAT: selecting frames"],
    "from-png": [],
}
PASTE = {"rotate": ["transpose"]}  # transpose's section ends with the paragraph both share


def reference(cmd):
    """CMD's section of pxart -h: its usage line (an indent of 2, then CMD and a usage word, not prose) and the lines
    under it, up to the next line indented 2 or less that isn't blank. None when -h has no section for it."""
    lines = __doc__.splitlines()
    start = next((i for i, l in enumerate(lines[lines.index("LOOKING"):], lines.index("LOOKING"))
                  if re.match(rf"^  {re.escape(cmd)}( +(?![a-z]+( |$))\S|$)", l)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) <= 2), len(lines))
    return "\n".join(lines[start:end]).rstrip()


def note(name):
    """A NOTES slice of pxart -h, or None when its first or last line is gone."""
    lines, (first, after) = __doc__.splitlines(), NOTES[name]
    i = next((i for i, l in enumerate(lines) if l.startswith(first)), None)
    j = next((j for j in range(i + 1, len(lines)) if lines[j].startswith(after)), None) if i is not None else None
    return None if j is None else "\n".join(lines[i:j]).rstrip()


def command_help(cmd):
    """What 'pxart CMD -h' prints under argparse's usage line: CMD's section (and PASTE's), then one see-also line
    naming the blocks of pxart -h it relies on, each with what it has."""
    parts = [reference(cmd) or f"  (pxart -h has no section for {cmd})"]
    parts += [f"{ref} (from pxart -h):\n{reference(ref)}" for ref in PASTE.get(cmd, [])]
    refs = SEE.get(cmd, [])
    if refs:
        also = "See also, in pxart -h: " + "; ".join(f"{r} ({GIST[r]})" for r in refs) + "."
        parts.append("\n".join(textwrap.wrap(also, 92, subsequent_indent="  ", break_on_hyphens=False)))
    return "\n\n".join(parts) + "\n\npxart -h has the whole reference."


def said(cmd, issue):
    """An error line as the CLI prints it: 'ellipse: E_BAD_ARG: ...', 'compose: layer 2 (x.px): x.px:4: E_...'. A
    message that starts with the command's own name doesn't say it twice."""
    if not issue.ctx and issue.msg.startswith(f"{cmd}: "):
        issue = Issue(issue.code, issue.msg[len(cmd) + 2:], issue.path, issue.line, issue.frame, issue.row, issue.cols)
    return f"{cmd}: {issue}"


USED_HELP = "a new OUT gets only the keys the frame uses (default: the sources' whole palettes, for shade ramps)"
REKEY_HELP = "give keys that clash with OUT's colors free keys in OUT only; the source files stay as they are"


def parser(describe=True):
    """The command line: (the parser, its subcommands' action). describe: give each subcommand its -h text."""
    ap = argparse.ArgumentParser(prog="pxart", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("render"); p.add_argument("files", nargs="+"); p.add_argument("-o", default="preview.png")
    p.add_argument("--png", action="store_true")
    p.add_argument("--scale", type=int, default=8); p.add_argument("--bg", default="#3a3a44")
    p.add_argument("--no-grid", action="store_true"); p.add_argument("--variant")
    p = sub.add_parser("sheet"); p.add_argument("files", nargs="+"); p.add_argument("-o", required=True)
    p.add_argument("--scale", type=int, default=8); p.add_argument("--cols", type=int, default=8)
    p.add_argument("--bg", default="#3a3a44"); p.add_argument("--grid", action="store_true"); p.add_argument("--variant")
    p.add_argument("--fit", action="store_true", help="each cell its own frame's size, each row its tallest frame's")
    p = sub.add_parser("anim"); p.add_argument("files", nargs="+"); p.add_argument("-o", help="GIF; without it, only the numbers")
    p.add_argument("--fps", type=int); p.add_argument("--scale", type=int, default=8); p.add_argument("--variant")
    p = sub.add_parser("onion"); p.add_argument("a"); p.add_argument("b"); p.add_argument("-o", required=True)
    p.add_argument("--scale", type=int, default=8)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--rows", help="Y0-Y1: only these canvas rows count for the readout and the best shift")
    g.add_argument("--feet", type=int, metavar="N", help="only the bottom N rows count (--rows for the feet)")
    p.add_argument("--tint-a", nargs="?", const="#ff4060a0", metavar="COLOR",
                   help="draw A as a silhouette in COLOR (default #ff4060a0) instead of faded")
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
    p.add_argument("--copy-to", nargs="+", metavar=("DST", "ID"), help="copy frames (FILE:SEL, or these ids) into DST")
    p.add_argument("--move"); p.add_argument("--after"); p.add_argument("--before")
    p.add_argument("--rekey", action="store_true", help=REKEY_HELP)
    p = sub.add_parser("flip"); p.add_argument("file"); p.add_argument("-o"); p.add_argument("--v", action="store_true")
    p = sub.add_parser("rotate"); p.add_argument("file"); p.add_argument("angle", choices=["90", "180", "270"])
    p.add_argument("-o")
    p = sub.add_parser("transpose"); p.add_argument("file"); p.add_argument("-o")
    p = sub.add_parser("shift"); p.add_argument("file"); p.add_argument("-o")
    p.add_argument("--dx", type=int, default=0); p.add_argument("--dy", type=int, default=0); p.add_argument("--region")
    p.add_argument("--wrap", action="store_true")
    p.add_argument("--fill", help="key for the pixels the shift leaves behind (default '.')")
    p = sub.add_parser("mask"); p.add_argument("file"); p.add_argument("-o")
    p.add_argument("--keep", action="append", help="x,y,w,h (repeatable: kept = inside any shape)")
    p.add_argument("--keep-circle", action="append", help="cx,cy,r (repeatable)")
    p.add_argument("--dither", type=int, help="ordered-dither falloff band N px wide inside each circle's edge")
    p.add_argument("--invert", action="store_true", help="erase inside the shapes, keep the outside")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--keep-keys", help="erase every pixel whose key isn't one of these")
    g.add_argument("--drop-keys", help="erase every pixel whose key is one of these")
    p = sub.add_parser("recolor"); p.add_argument("file"); p.add_argument("maps", nargs="+"); p.add_argument("-o")
    p.add_argument("--region")
    p = sub.add_parser("set"); p.add_argument("file"); p.add_argument("key"); p.add_argument("points", nargs="+")
    p.add_argument("-o")
    p = sub.add_parser("crop"); p.add_argument("src"); p.add_argument("rect"); p.add_argument("-o", required=True)
    p.add_argument("--rekey", action="store_true", help=REKEY_HELP)
    p.add_argument("--used-keys-only", action="store_true", help=USED_HELP)
    p = sub.add_parser("paste"); p.add_argument("src"); p.add_argument("--into", required=True)
    p.add_argument("--at", required=True); p.add_argument("--region"); p.add_argument("-o")
    p.add_argument("--under", action="store_true", help="only onto --into's empty pixels (behind what's there)")
    p.add_argument("--rekey", action="store_true", help=REKEY_HELP)
    p = sub.add_parser("new"); p.add_argument("out"); p.add_argument("--size", required=True)
    p.add_argument("--key", help="fill with this key (default '.')"); p.add_argument("--palette", help="new OUT imports this .px")
    p.add_argument("--still", action="store_true", help="mark the frame's group '@still GROUP'")
    p = sub.add_parser("put"); p.add_argument("target"); p.add_argument("-o")
    p = sub.add_parser("fill"); p.add_argument("file"); p.add_argument("key"); p.add_argument("--region")
    p.add_argument("-o")
    coord = re.compile(r"^-\d+(\.\d+)?(,-?\d+(\.\d+)?)*$")  # a negative x,y is an argument, not an option
    ap._negative_number_matcher = coord
    p = sub.add_parser("line"); p.add_argument("file"); p.add_argument("key"); p.add_argument("p0"); p.add_argument("p1")
    p.add_argument("--width", type=int, default=1); p.add_argument("-o")
    p = sub.add_parser("rect"); p.add_argument("file"); p.add_argument("key"); p.add_argument("rect")
    p.add_argument("--fill", action="store_true"); p.add_argument("-o")
    p = sub.add_parser("poly"); p.add_argument("file"); p.add_argument("key"); p.add_argument("points", nargs="+")
    p.add_argument("--fill", action="store_true"); p.add_argument("-o")
    p = sub.add_parser("ellipse"); p.add_argument("file"); p.add_argument("key"); p.add_argument("shape")
    p.add_argument("--fill", action="store_true"); p.add_argument("-o")
    p = sub.add_parser("arc"); p.add_argument("file"); p.add_argument("key"); p.add_argument("circle")
    p.add_argument("angles"); p.add_argument("--width", type=int, default=1); p.add_argument("-o")
    p = sub.add_parser("flood"); p.add_argument("file"); p.add_argument("key"); p.add_argument("at")
    p.add_argument("--diagonal", action="store_true"); p.add_argument("-o")
    p = sub.add_parser("outline"); p.add_argument("file"); p.add_argument("--key", required=True)
    p.add_argument("--lit", help="lighter key for the edges facing the light (selective outline)")
    p.add_argument("--selective", action="store_true"); p.add_argument("--light", choices=list(LIGHTS), default="nw")
    p.add_argument("--preview", help="render the result to this PNG; write nothing else")
    g = p.add_mutually_exclusive_group(); g.add_argument("--inside", action="store_true")
    g.add_argument("--outside", action="store_true"); p.add_argument("--corners", action="store_true")
    p.add_argument("-o")
    p = sub.add_parser("shade"); p.add_argument("file"); p.add_argument("--ramp", required=True)
    p.add_argument("--keys", help="the material's keys (default: the ramp's)"); p.add_argument("--base")
    p.add_argument("--light", choices=list(LIGHTS), default="nw"); p.add_argument("--strength", type=float, default=2)
    p.add_argument("--region"); p.add_argument("--dither", action="store_true"); p.add_argument("--preview")
    p.add_argument("-o")
    for name in ("line", "rect", "poly", "ellipse", "arc", "flood", "crop"):  # crop -2,-2,20,20: a rectangle
        sub.choices[name]._negative_number_matcher = coord
    p = sub.add_parser("extract"); p.add_argument("file"); p.add_argument("-o", required=True)
    p.add_argument("--inline-palette", action="store_true", help="copy the imported keys in; drop @palette")
    p = sub.add_parser("compose"); p.add_argument("layers", nargs="+"); p.add_argument("-o", required=True)
    p.add_argument("--size"); p.add_argument("--under", action="store_true", help="draw the layers behind OUT's frame")
    p.add_argument("--rekey", action="store_true", help=REKEY_HELP)
    p.add_argument("--used-keys-only", action="store_true", help=USED_HELP)
    p = sub.add_parser("dup"); p.add_argument("src"); p.add_argument("new"); p.add_argument("-o")
    p.add_argument("--after")
    p = sub.add_parser("anim-set"); p.add_argument("target"); p.add_argument("settings", nargs="*"); p.add_argument("-o")
    g = p.add_mutually_exclusive_group(); g.add_argument("--still", action="store_true", help="add '@still GROUP'")
    g.add_argument("--no-still", action="store_true", help="remove '@still GROUP'")
    p = sub.add_parser("palette"); p.add_argument("file"); p.add_argument("--add", nargs="+"); p.add_argument("--export")
    p.add_argument("--extract-to", help="write FILE's palette and variants as a palette file")
    p.add_argument("--repoint", action="store_true", help="with --extract-to: FILE then imports it")
    p.add_argument("--used", action="store_true")
    p = sub.add_parser("export"); p.add_argument("files", nargs="+"); p.add_argument("--frames"); p.add_argument("--aseprite")
    p.add_argument("--tiled"); p.add_argument("--variant")
    p = sub.add_parser("from-png"); p.add_argument("pngs", nargs="+"); p.add_argument("-o"); p.add_argument("--id")
    p.add_argument("--palette", help="new OUT imports this palette file and reuses its keys")
    for name, p in sub.choices.items() if describe else ():  # 'pxart CMD -h': its section, not only its flags
        p.description, p.formatter_class = command_help(name), argparse.RawDescriptionHelpFormatter
    return ap, sub


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    ap, _ = parser(describe="-h" in args or "--help" in args)
    a, extra = ap.parse_known_args(argv)
    if extra and a.cmd == "anim-set" and not any(x.startswith("-") for x in extra):
        a.settings += extra  # 'anim-set F:G --still ms=50': argparse spends a '*' positional before the option
    elif extra:
        ap.parse_args(argv)  # argparse's own error
    try:
        globals()["cmd_" + a.cmd.replace("-", "_")](a)
    except PxError as e:  # every error line starts with the command, then the input: 'compose: layer 2 (x.px): ...'
        sys.exit("\n".join(said(a.cmd, i) for i in e.issues))
    except OSError as e:
        sys.exit(file_error(e))


if __name__ == "__main__":
    main()
