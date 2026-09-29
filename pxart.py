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

  A comment right above a line is that line's; a header is above 'pxart 1' or a blank line.
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
  @anim line, and a frame flipped alone gets its own.
  direction: forward | reverse | pingpong | pingpong_reverse (Aseprite's words).
  repeat: 0 or absent = loop forever; N = play N times. ms: default frame duration.
  'anim-set hero.px:walk/down ms=125' writes these, pivot=8,23 too (FILE:GROUP/ID: a frame's).
  Frame groups that aren't animations (UI icons, a parts file): '@still ui/life' keeps them
  out of animation exports and checks; '@still *' marks every frame in the file, top-level
  ids with no '/' included (a parts file; frames then lists them as 'still'). A frame copied
  as a still (a top-level id, or a @still group) drops its ms and keeps its pivot, with a note.
  Palette variants (recolors): keys listed after '@variant night' override the base
  palette. Variants in a @palette file are inherited; local keys (and local variant keys)
  override imported ones, and check notes the override, and a local key that repeats an
  imported one's color (with the palette --remove that drops its line when nothing changes).
  A variant a file gets only from its @palette leaves the file's own keys at base colors;
  commands that render it print a WARNING naming them and the fix, and check notes it.

  Anywhere a command takes FILE, FILE:SEL picks frames: SEL is a frame id or a parent
  path (FILE:walk/down = every walk/down/* frame), or a list of them, FILE:idle,walk/0.
  No SEL (or *) means every frame. A file with one unnamed grid (no @frame) calls it by
  the file's name, as frames lists it: ant.px's grid is ant.px:ant. Writing a named frame into such a file (compose, crop, new, put -o
  ant.px:ID, or from-png into it) first makes the grid '@frame ant', with a note; with ID
  ant that is the frame written. Add %VARIANT to render with a variant: FILE:idle/0%night.
  +----------------------------------------------------------------------------------------+
  | zsh users: write "${F}:walk", not "$F:walk" (zsh reads ':w' as a modifier), or quote   |
  | the whole argument. A missing hero.pxalk/0 or hero.pxidle is reported as that mistake. |
  +----------------------------------------------------------------------------------------+
  An output under a file (-o hero.px/walk/0) is E_FILE; an image output with no image
  extension (-o /dev/null, -o x.px) is E_BAD_ARG.
  Paths: a path typed on the command line is read from the current directory, as the
  shell's are: FILE, -o OUT, layers and items, and every path option (--palette, --import,
  --match, --copy-to, --into, --map, --labels, --in, --extract-to, --export, --preview,
  --frames, --aseprite, --tiled). A path written inside a file is read from that file's
  directory: a .px's '@palette pal.px', a .map's legend entries, a --labels CSV's file
  names. A file pxart writes elsewhere gets its @palette lines re-pointed (see EDITING). An
  output's missing directory is made, and said: 'created out/'. An E_FILE for a relative
  path says so, and a path option's names the option: 'palette: --match
  (../wick/pal.px%dark): ../wick/pal.px (from the current directory): E_FILE: No such file or
  directory'.

LOOKING
  render FILE... [-o preview.png] [--scale 8] [--no-grid] [--variant V] [--png [DIR]] [--plain]
         [--dry-run]
      Preview sheet with a pixel grid and x/y rulers every 4px (default --scale 8; sheet,
      anim and onion too). --png also writes each single-frame .px at 1x, FILE.png beside it
      or in DIR, and says so. --plain writes -o as the one frame alone, its exact size
      (--scale 1 by default), no grid, rulers, labels or --bg: for diff (--no-grid still
      pads and labels).
  sheet FILE|DIR... -o sheet.png [--scale 8] [--cols 8] [--grid] [--variant V] [--bg COLOR]
        [--fit] [--align bottom|pivot] [--rows cols|group] [--exclude GLOB] [--dry-run]
      Compare any mix of .px/.png frames, labeled with id, WxH and color count. A directory
      stands for every .px under it, recursively, sorted by path ('sheet crossover/ -o
      s.png'; PNGs in it are left out, a sheet rendered there too). --exclude GLOB
      (repeatable) leaves files out: one whose name or path under the directory matches
      ('_*.px', 'wip/*.px'), or every file under a directory that does ('wip'). A glob that
      leaves out every file is E_FILE. A palette file (no frames) among the inputs, a
      directory's or a glob's, is skipped with a note ('note: sheet skips palette.px: a
      palette file, no frames'); given alone it is E_NO_FRAMES. Every cell is the largest
      frame's size (a frame over 8x the median frame's area gets a note); --fit makes each
      cell its own frame's width (or its label's, if wider) and each row as tall as its
      tallest frame, --cols cells to a row, frames bottom-aligned in their row. A PNG whose
      four corners are exactly the --bg color (a scene rendered with the same --bg) doesn't
      count that color: it's the backdrop. Frames with the same id from different files are
      labeled with their file's stem in front (hero:idle/0, beast:idle/0); render and anim
      label them the same way.
      --align pivot lines up each animation group's frames by pivot, as anim and onion do:
      the group's frames are drawn on one canvas, every pivot on the same pixel. The
      default, --align bottom, bottom-aligns each frame in its cell.
      --rows group starts a row for each animation group (one file's walk/down, then its
      walk/up, ...; a file's top-level frames share one; a PNG has its own) and wraps within
      a group only when it has more than --cols frames: 'sheet party.px --fit --rows group
      --align pivot -o party.png' is one walk per row. The default, --rows cols, fills each
      row with --cols frames.
  anim FILE... [-o walk.gif|DIR] [--scale 8] [--fps N] [--variant V] [--dry-run]
      walk.gif (one file: each frame at --scale, its 1x and 2x copies beside it in the same
      picture), plus walk.strip.png: row 1 = frames, row 2 = what changed from the previous
      frame after removing the whole-sprite shift ("shift dx,dy then N px (P%) (no shift: M px)";
      P: N as a percent of the frame's opaque pixels, or of both frames' if more; a bob alone
      shows "then 0px (0%)"). The numbers print too, a line per frame (a FILE of several
      groups: a block each, top-level and @still frames skipped; -o a DIR);
      without -o, anim prints only those lines and writes nothing. Read the strip: the Read
      tool shows only a GIF's first frame. Durations come from the file (@anim/@frame ms)
      unless --fps is given. A group with repeat=1 plays once: frame 0 gets no wrap-around diff.
      --variant V counts V's render: a halo transparent in the base counts, at any alpha.
      An idle: when the bottom stays exactly put (rows Y down identical, 0 px changed) and
      only the part above moves (a breath), shifting would light up the legs, so the strip
      shows the unshifted diff: "no shift then M px (P%) (rows Y+ still; shift dx,dy: N px)".
      Both counts are always shown. That is for an idle, whose legs keep their shape in every
      frame of the animation: a walk whose leg moved even 1px keeps the shift, and in a walk
      a frame whose legs happen to stay put is the body's bob: "shift +0,+1 then 23px (6%) (no
      shift: 201px)". A frame recolored whole (a glow) doesn't count as the legs moving; a
      shadow that changes shape does. So that the rise and the fall of a breath read alike,
      once one frame shows rows still and rows Y down are identical in every frame of the
      animation, every frame whose shift would light them up shows the unshifted diff too; a
      walk over a static shadow keeps every shift.
      Tiles and overlays: frames that fill the canvas and are a ground tile (every pixel
      opaque) or a sparse overlay (at most 1/4 opaque: snow) also try every wrap-around scroll
      (shift --wrap), shown when it leaves strictly fewer pixels changed than the best plain
      shift: "shift dx,dy (wrap) then N px (P%) (no shift: M px)". A character sprite never wraps.
  onion A B -o x.png [--scale 8] [--rows Y0-Y1 | --feet N] [--tint-a [COLOR] | --fade-a]
        [--variant V] [--dry-run]
      B at 80% opacity drawn over A as a flat silhouette in a translucent red (#ff4060a0),
      with render's grid and rulers, so where A shows past B is plain to see.
      Prints where each frame's opaque pixels sit on the shared canvas and how B's edges moved
      from A's, then the whole-sprite shift that best explains B, as anim finds it:
      "B vs A: left +0, right +0, top -1, bottom +0; best shift +0,-1 then 4px changed (no
      shift: 20px)": the head rose 1px, the feet stayed. Two different sprites (other sizes, or
      more than half the larger one's opaque pixels still changed at the whole sprites' best
      shift; --rows and --feet don't change that; two frames of one animation in one file
      are always one sprite, however much changed) print
      "...; different sprites: edges only": their edges still compare where the feet stand,
      but a best shift between two characters means nothing. y grows down, so +1 is lower.
      The edges are the sides of each frame's opaque bounding box: 'top -1' is B's top row 1px
      above A's.
      --rows Y0-Y1 (canvas rows as the readout prints them, both included; one row: --rows Y)
      or --feet N (the bottom N rows) limit the edges and the best shift to that band, so a
      weapon swing above doesn't hide what the feet did: 'B vs A (bottom 4 canvas rows 20-23;
      A opaque in 20-23, B in 21-23): left +0, ...'. The shift still moves all of A (pixels
      come into the band from above) and counts only the band's pixels; when the bottom edges
      agree, one up or down only lines up what moved above them, and the readout says no
      shift. The PNG darkens the rows outside the band.
      --tint-a COLOR draws the silhouette in another color. --fade-a draws A itself at 35%
      opacity instead.
  scene -o s.png [--scale 4] [--size WxH] [--bg #472d3c] [--map M --tile 16x16] [--variant V]
        [--tint #rrggbbaa] [--dry-run] ITEM@x,y ...
      Default --scale 4 (not render's 8).
      Size: --size, else the map's, else 96x64 (six 16x16 tiles by four). Pixels past the
      edge are cropped, with a note per item (and one for the map) saying how many; at the
      default size a note also names the --size that holds every item.
      ITEM is FILE[:frame][%variant][+h|+v|+hv]: +h mirrors it left-right, +v top-bottom
      (hero.px:walk/0+h@3,4; '+' needs no quoting, where '!' would be history expansion). Map legend entries (which also take +b, see
      Placement) and compose layers take +h/+v too. --map draws a text tilemap first:
      legend lines '<char> <FILE[:frame][%variant]>', a blank line, then rows of legend
      chars ('.' = empty). In a legend line the rest of the line is the path, relative to
      the map file: spaces are fine ('b ../png/trees and bushes/bush.png'), "quotes"
      optional. A legend entry that can't load is an error at its legend line.
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
      props over them (compose --map builds the same room as a .px). The stall's cell is
      16,16, so it draws at 16 + (16-32)//2, 16 + 16 - 32 = 8,0; the lamps at 48,0 and 80,0
      (mirrored); the crate, mirrored, at its cell's top-left, 0,32.
      --variant V renders every map tile and .px item with V (a whole dark room), except
      those with their own %variant, which wins; a .px without V is an E_SELECT error.
      %base is the base palette, so 'lamp.px%base@40,20' (or a legend entry 'L lamp.px%base')
      stays unrecolored in a --variant night scene (a lit window, a glowing lamp). '%base'
      works wherever %variant does, and a variant can't be named base.
      Items and legend entries can be PNGs (hero.png@3,4). x,y may be negative (drawn
      partly off the left/top edge), in scene and in compose.
      --tint '#10183080' lays that color, at its alpha, over the whole finished scene (bg,
      map, every item, those with their own %variant too) at 1x, before --scale: a night
      scene in one step. To keep a light bright, mask its circle out of the untinted render
      and lay that over the tinted one.
  tint IN.png '#rrggbbaa' [-o OUT.png]
      scene --tint on a PNG (a rendered scene): lays the color, at its alpha, over every
      pixel; each pixel keeps its alpha, so transparent pixels stay transparent. Without -o,
      IN is rewritten.
  world W.world|ROOM.tmj -o world.png [--scale 2] [--dry-run]
  Centering: frames of different sizes are bottom-aligned and centered, with the odd
  pixel going left (x = (canvas - frame) // 2). render and sheet put a grey checkerboard
  behind frames; --bg (render, sheet, scene) takes a flat #rrggbb, #rrggbbaa or 'transparent'
  (as does every color typed on the command line: --tint, tint, palette --add
  k=transparent; the '#' may be left off, and in a script a '#' color needs quotes, or the
  shell reads a comment).
  --dry-run (render, sheet, anim, onion, scene) prints the readout and each output's size and
  layout, writes nothing and says '(dry run; nothing written)'. -o may then be left off. An
  image over 4096 px on a side or 16M px gets a WARNING, dry run or not.

CHECKING
  check FILE|DIR... [--palette P] [--size WxH] [--max-colors N] [--strict] [-v] [--exclude GLOB]
      Every format error with a code and location, then size / off-palette colors /
      color budget / unused keys. One line per file: 'ok   party.px: 40 frames, 32x32, 16x16,
      3-14c', or 'FAIL party.px: 2 of 40 frames fail' and a line for each of those frames
      (a file of one frame gets that frame's line); -v prints a line for every frame, as
      'ok   party.px:walk/down/0: 32x32 9c'. Notes follow their file's line, and checking
      more than one file ends with a summary: '6 files, 150 frames, 3 warnings' (', 1
      failed' when one did; a warning is a note line). A directory checks every .px and .map
      under it, recursively, sorted by path ('check crossover/'); a palette file (no frames)
      is checked as one: 'ok   palette.px: palette file, 17 key(s), variants night'. P is a
      .px, .gpl, .hex, or text of #rrggbb. --strict also rejects unknown @sections and
      @anim/@still lines whose group has no frames (else a note). Exit 1 on any failure.
      --exclude GLOB leaves files out, as for sheet.
      A .map (scene --map) is checked too: every row char has a legend line and every
      legend entry loads as one frame; .world, .tmj: help worlds.
      Non-ASCII chars that look like ASCII (Cyrillic/Greek 'а е о р с х у', fullwidth
      'ｋ') get a note naming the line, row and column and the letter they pass for.
  stats FILE|DIR... [--colors] [--at x,y] [--exclude GLOB] [--variant V]
      Size, bbox ('x 1..22, y 0..20': ends included), colors (a directory, palette files and
      --exclude as for sheet).
      FILE:SEL%VARIANT reads the colors a variant renders (--variant V: every FILE's): 'stats
      hero.px:idle/0%night'. --colors lists each frame's rendered colors, most pixels first,
      each with its pixel count and the keys that draw it ('#120e22 40 px (k)'). --at x,y
      (repeatable) prints that pixel's key and its color in the base palette and in every
      variant ('at 3,4: key k; base #3f2631, night #120e22'), or only in the one named.
  diff A B [--variant V] [--strict-alpha] [--exclude GLOB] [-o DIFF.png|DIR [--scale N]]
       [--labels CSV [--label-col C] [--file-col C]]
      Compare renders pixel by pixel, one line per pair ('same: 16x16, every pixel', or what
      differs: '12 px differ in 3,4,6,6 (x,y,w,h)', 'sizes 16x16 and 16x24') and for several a
      count ('132 frame(s): 130 same, 1 differ, 1 unpaired'). It exits 1 when anything differs
      or has no pair, as check does.
      A and B are:
        two files, FILE[:SEL][%VARIANT] or PNGs: one frame each, or frames paired by id (in
          order when their ids differ but their counts match: diff wick.px:walk
          party.px:wick/walk, copies made with --prefix wick/);
        a file and a directory of PNGs: each frame against DIR/<id>.png, as export --frames
          writes them, or with --labels CSV against the PNG whose row names it so: 'diff
          town.px pack/ --labels pack/labels.csv' proves a port lossless in one call;
        a directory of .px files and one of PNGs: every frame of every .px, as above ('diff
          town/ pack/ --labels pack/labels.csv'; an id two files share is E_BAD_ARG; a note
          counts the PNGs left over);
        two other directories: the .png and .px files under them paired by path (with
          --labels, a PNG goes by its row's name), a .px pair frame by frame.
      A frame with no PNG, or a file only one side has, is unpaired. --exclude GLOB leaves
      a directory's files out, as for check.
      Transparency: a pixel whose alpha is 0 matches any other whose alpha is 0, whatever
      its rgb; any other pixel compares on all four channels. --strict-alpha compares all
      four everywhere. --variant V renders both sides with V, and a side's own %VARIANT
      wins. -o DIFF.png draws A, B and the differing pixels in magenta side by side
      (top-left aligned) of the one pair that differs; -o DIR gets one per pair that differs.
      A render or scaled copy of a frame gets a note naming render --plain.
  frames FILE[:SEL] [--rm [ID...]] [--move ID --after|--before ID] [--rename GROUP NEWGROUP]
         [--copy-to DST [ID...] [--rekey [KEYS]] [--variant-map NAME=V1,V2]
          [--prefix P | --rename GROUP NEWGROUP]]
      List frames, sizes, durations (only for animation frames; 'still' for @still groups
      and every frame under '@still *') and animations; or delete / reorder frames (prints
      what it removed or moved, not the listing; a move to where the frames already are
      prints "already in place" and writes nothing). FILE:SEL lists only those frames; 'frames
      hero.px:walk/left --rm' removes them (ids after --rm are frame ids, in SEL), and 'frames
      hero.px:walk/left --after idle/3' moves them there as a block, in order. --move ID
      takes a plain FILE and one frame id (a group moves with FILE:GROUP --after ID).
      Removing a group's last frame removes its @anim and @still lines too. A move puts the
      @anim lines in the order of their groups' first frames (with their comments; lines of
      groups with no frames after), so the file reads in play order, and says so.
      --copy-to DST copies FILE's frames (FILE:SEL's, or the ids after DST) into the existing
      DST as they play in FILE: each frame's ms and pivot (on its @frame line when DST's @anim
      would change them), the @anim line of a group DST lacks, and @still. They keep FILE's
      order and land after their group's last frame in DST, at the end for a new group, or
      at --after/--before a DST frame: 'frames hero.px:walk --copy-to beast.px --after idle/3'.
      Their keys join DST's palette and variants as compose's layers join an existing OUT
      (see compose): E_KEY_CONFLICT, the variant WARNINGs, --rekey [KEYS] and --variant-map
      dusk=night work alike. A frame id DST already has is E_DUP_FRAME, and so are two
      copies --rename would give one id (--rename walk w --rename run w).
      DST must exist: 'extract FILE:SEL -o DST' starts one with FILE's palette, and 'new DST
      --empty --palette P.px' one with no frames that imports P.
      Copies under other ids, when DST has those already (two packs' walk/*): --prefix wick/
      puts wick/ in front of every copy's id ('frames wick.px:walk --copy-to party.px --prefix
      wick/' writes wick/walk/down/0 and '@anim wick/walk/down'), and --rename walk wick/walk
      renames only the group (or frame) it names; FILE stays as it is. --rename repeats.
      --rename GROUP NEWGROUP without --copy-to renames in FILE itself: GROUP's frames (walk/0,
      walk/1, or the frame GROUP) become NEWGROUP's (wick/walk/0, ...), and the @anim and
      @still lines of GROUP and the groups under it follow, with their comments. A NEWGROUP
      FILE already has is E_DUP_FRAME.

EDITING (writes .px; -o defaults to editing the input in place)
  -o OUT always gets the whole file: with FILE:SEL, OUT is a copy of FILE with the selected
  frames edited and every other frame as it was, and a note says so.
  To get only some frames, extract them. An OUT in another directory gets its @palette
  lines re-pointed from there ('@palette ../pal.px' in -o art/x.px), so it imports the
  same palette file. Edits rewrite only what changed: other lines keep their spelling and
  the blank lines and comments above them, and new frames get the file's spacing between
  @frame blocks. An edit changing nothing (set to the same key, flip of a symmetric frame) prints
  "no change: FILE" and writes nothing; one that edits several frames names them.
  --dry-run (any edit) prints its diff and writes nothing. There's no undo: use git.
  Coordinates (x,y, --region, --at) need FILE:SEL on a file of several frames, saying which
  ('FILE:*': all).
  Limits: sections are written in a fixed order (palette, @variant, @anim/@still, frames,
  unknown @sections), so an @anim written between frames moves up; a comment inside the
  file stays with the line below it and goes when that line goes (a removed frame, cut rows).
  flip FILE [-o OUT] [--v]          mirror selected frames left-right (--v: top-bottom)
      'flip hero.px:walk/left -o hero.px:walk/right' flips a copy (--replace: over its frames).
  shift FILE [-o OUT] --dx N --dy N [--region x,y,w,h] [--wrap] [--fill KEY]
      Move the frame's pixels (or only the region's) by dx,dy. Pixels moved past the frame's
      edge are dropped, and the pixels the move leaves behind (vacated) become '.', or KEY
      with --fill KEY (a floor under a moved prop). With --region the moved block may land
      outside the region; its '.' pixels don't overwrite what they land on.
      --wrap scrolls pixels around the edges (for animating tiles) instead of dropping them.
  set FILE[:frame] KEY x,y [x,y ...] [-o OUT]    paint single pixels ('.' erases)
      Prints "painted N px" ("erased" for '.').
  fill FILE[:frame] KEY [--region x,y,w,h] [-o OUT]   paint a rectangle (default: the frame; '.' clears)
  new OUT[:frame] --size WxH [--key K] [--palette P.px] [--still]
  new OUT --empty [--palette P.px]
      A blank frame ('.'), or one filled with K, in a new file or added to an existing one
      (placed like compose). --palette P.px starts a new OUT that imports P. A frame that
      already exists is E_DUP_FRAME: fill it instead. --still marks its group '@still GROUP'
      (new ui.px:icons/life --still).
      --empty starts a new OUT with no frames: the version line and, with --palette, its
      @palette line. It is where frames --copy-to puts another file's frames against a
      shared palette: 'new party.px --empty --palette palette.px', then 'frames
      keeper.px:walk --copy-to party.px --rekey'.
  put FILE[:frame] [-o OUT] < grid.txt
      Replace one frame's grid with the rows on stdin. Stdin is rows, or palette lines then
      rows; the keys the rows use join FILE's palette the way compose's layers do (a key
      FILE has in another color is E_KEY_CONFLICT), and other keys must be FILE's. Rows are
      checked like a file's (widths, keys), errors point at stdin's lines, and
      nothing is written on an error. Only that frame's lines change.
      A frame that doesn't exist yet is added, placed like new; a new FILE is started.
      Stdin has no variants: a key in FILE's color is FILE's key, variant colors and all, and
      a new key stays at its base color in FILE's variants.
  mask FILE[:frame] --keep x,y,w,h | --keep-circle cx,cy,r ... [--dither N] [--invert]
       [--keep-keys K,K | --drop-keys K,K] [-o OUT]
      Erase (set to '.') every pixel outside the rectangle or circle (kept: distance from
      the pixel to cx,cy <= r). --dither N fades the circle's last N px inside its edge
      with a 4x4 ordered (Bayer) dither: a light radius. --invert erases the inside and
      keeps the outside, dither band mirrored, so a mask and its --invert split the image
      with no overlap or gap. --keep and --keep-circle repeat, and mix: the kept area is
      their union, and --dither and --invert work over the union.
      FILE may be a PNG (a scene rendered at --scale 1: coordinates are its pixels): outside
      pixels become transparent. -o, if given, must be a .png too.
      --keep-keys W,T,t (or WTt) erases every pixel whose key isn't one of those; --drop-keys
      erases those keys' pixels. Alone, they mask by key over the whole frame; with shapes, a
      pixel stays only when both keep it (the shapes, --invert and --dither as above). .px only.
  crop FILE:frame x,y,w,h -o OUT[:frame] [--rekey [KEYS]] [--used-keys-only]
       [--variant-map NAME=V1,V2]
      Cut the w x h rectangle at x,y out of one frame into a frame of its own: 'crop
      hero.px:idle/0 4,0,8,8 -o parts.px:head'. Quietly: the pixels outside the rectangle are
      what crop is for, so there's no note about them; a rectangle that runs past the frame's
      edge (or starts at a negative x,y) gets '.' there. FILE:frame must be one .px frame.
      OUT is written as compose writes it, FILE's frame its one layer (see compose): a new
      OUT gets FILE's whole palette (--used-keys-only: the cut's keys), OUT:frame adds or
      replaces that frame in an existing OUT, and a plain OUT with one unnamed grid has it
      replaced. A key OUT has in another color is E_KEY_CONFLICT, with free keys; --rekey
      gives the cut those keys in OUT and leaves FILE as it is.
  extract FILE:SEL -o OUT [--inline-palette] [--replace]
      Write only the selected frames to a new OUT, with FILE's palette, @palette imports,
      variants, and @anim/@still lines (minus those of groups left behind;
      @anim lines in the order of the frames' groups): 'extract hero.px:walk/down -o
      walk.px'. An OUT that exists is E_FILE, since its frames would be lost (E_DUP_FRAME
      when it has one of the ids): 'frames FILE:SEL --copy-to OUT' adds them to it, and
      --replace overwrites it. --inline-palette makes OUT self-contained for a hand-off: the
      imported keys it uses become key lines, with their variant colors, and the @palette
      lines go. OUT renders exactly like the source frames, in every variant.
  recolor FILE a=b ['a<>b'] ['a>b'] [c=#rrggbb] [-o OUT] [--region x,y,w,h] [--variant V]
      a=b repaints key a's pixels as key b (optionally only inside --region); 'a<>b' swaps
      keys a and b (in the region) in one step; quote it, since unquoted < and > are shell
      redirections. 'a>b' gives a's pixels a new key b, in a's color (and a's variant
      colors): when no pixel keeps a and a is FILE's own key, a's palette lines become b's
      (a rename), else b is added and a stays: it frees a key without a visible change;
      onto a key b already in a's color (a near-duplicate), the error says to write a=b, a repaint that
      looks the same. c=#hex changes key c's color everywhere. '.' works as a source key.
      Order: the key moves of one call apply together, each pixel by the key it had before
      the call, so no move feeds another: 'a<>b' c=a turns a's pixels to b and b's and c's
      to a, and a=b b=a is a swap too. The renames apply together as well: a key another
      'a>b' of the call renames away is free for a new key, so 'g>r' 'd>g' renames g to r and
      d to g, and 'a>b' 'b>a' swaps two keys' names (every pixel keeps its look). A key the
      call keeps (pixels outside --region or the selection draw with it, it is imported, or
      c=g paints with it) isn't free. A key moved twice is E_BAD_ARG. Color changes (V's:
      --variant V) set the palette, moving no pixels: c=#hex, c=d and 'b>t' t=#hex share a
      call.
  paste SRC[+h|+v|+hv] --into DST[:frame] --at x,y [--region x,y,w,h] [--under] [--rekey [KEYS]]
        [--variant-map NAME=V1,V2] [--align shift|pivot|bottom|bbox] [-o OUT]
      Copy SRC's frame (or --region of it) onto DST at x,y; '.' never overwrites. +h / +v
      mirror SRC first, as for compose layers and scene items (--region is then in the
      mirrored frame's coordinates). --under fills only DST's empty pixels: SRC goes behind.
      SRC's keys join DST as a compose layer's join an existing OUT: E_KEY_CONFLICT, the
      variant WARNINGs, --rekey [KEYS] and --variant-map work alike. --align: one paste
      follows a bob across frames.
  compose -o OUT[:frame] [--size WxH] [--under] [--rekey [KEYS]] [--used-keys-only]
          [--variant-map NAME=V1,V2] [--replace] [--dry-run] LAYER@x,y ...
  compose --map MAP [--tile N] -o OUT[:frame] [the options above] [LAYER@x,y ...]
      Stack single frames (later layers on top; '.' never overwrites) into one frame.
      Rules ('pxart help compose-rules' prints only these):
        - A new OUT gets the layers' whole palettes, drawn with or not (for shade ramps). When
          every layer imports the same @palette file, OUT imports it too; else its keys become
          key lines.
        - An existing OUT keeps its own palette, @palette and variants; each layer's keys join
          it.
        - Variants merge by name: OUT's night colors each layer's pixels as that layer's own
          file's night does, and a layer whose file has no night stays at its base colors in
          it. --variant-map dusk=night reads another name as OUT's dusk.
        - A key a layer has in another color than OUT's is E_KEY_CONFLICT; --rekey gives it a
          free key in OUT. The layers' files are read, never written.
        - OUT:frame adds that frame to OUT, or replaces it; a plain OUT is one unnamed grid.
      Examples: 'compose -o room.px tiles.px:cobble@0,0 hero.px:idle/0@4,2', 'compose -o
      party.px:keeper/walk keeper.px:walk/0@0,0 --rekey' (keeper.px's k is another color in
      party.px, so it gets a free key there). --dry-run prints what compose says (notes,
      conflicts, --rekey's moves) and OUT's diff (a new OUT: every line); nothing is written.

      A new OUT (rule 1; a shared import re-pointed from OUT's directory): local keys follow
      the import, the keys the layers use first: a key layers have in different colors gets
      the color of the layer that uses it, else the earlier layer's, and one line per source
      file names its colors left out and why: a key none of the file's layers here
      draw with is no conflict, and OUT has the color of the layer named (which draws with it,
      or is the earlier layer). That line is a WARNING when the file needs a key it lost (its
      other frames draw with it, named, or a variant lists it unchanged or keeps it while
      recoloring most keys: a lamp kept lit); --rekey then keeps such keys under free keys in
      OUT.

      --used-keys-only gives a new OUT only the keys its frame uses (and their variant colors;
      a @palette they all import is still imported, since it adds no key lines), so check has
      no 'unused keys' to note. It isn't the default because the unused keys are often a
      material's ramp: a cloak drawn in its base key c still needs X x C w for 'shade --ramp
      XxcCw' to re-shade it. An existing OUT only ever gets the used keys. So they are no
      surprise, a new OUT's note names the keys its frame doesn't draw with, by file ('...
      from its layers' whole palettes (for shade ramps and recolors): wick.px's E'), and
      check's 'unused keys' note offers the palette --remove that drops them.

      An existing OUT (rule 2): a layer's key is added unless OUT has it in that color, in
      the colors the layer's file gives it in OUT's variants of the same name (a variant the
      file hasn't got leaves the key at its base color there, and a file with variants, none
      of them OUT's, gets a note saying so and naming the --variant-map that would read one
      as OUT's). A plain OUT that exists (no :frame) keeps its palette too, keys from an
      earlier run included, and a note says so: 'note: glade.px exists: keeping its palette
      (61 keys, @variant dusk); --replace starts it fresh' (an E_KEY_CONFLICT says it as
      well). --replace starts it as if new: the layers' palettes, nothing of the old file
      (not with OUT:frame, whose other frames it would drop, or with --under).

      Key conflicts: a key a layer uses in another color than OUT's (or an earlier layer's) is
      E_KEY_CONFLICT, one line per source file (all its layers: 'layers 1-4, 7 (field.px)')
      naming every key and both colors, and free keys for them ('s>a' 't>b'). The free keys
      are chosen once for the whole compose, so no two lines' suggestions collide: a key OUT
      already has in that color first, then the key an earlier file of this compose was given
      for a color that looks the same in every variant (two packs' one outline share one key,
      and the note says so), then letters and digits, then % + - / : ^ _, and only when those
      run out the keys a shell reads (! $ ` ' * ? [ ] { } ~ & ; | < > ( )) or pxart does (,
      and =). A key any layer's file has isn't free, used here or not. Two ways to use them:
        --rekey: compose gives those keys the free ones in OUT as it goes, and a note says
          which: 'note: --rekey gives field.px's keys free ones in scene.px: 's>a' 't>b'
          (field.px is unchanged)'.
        a copy: 'pxart recolor field.px 's>a' 't>b' -o rekeyed/field.px' (rekeyed/ beside
          OUT), then compose from rekeyed/field.px; the line prints it ready to run.

      --rekey KEYS touches only the keys it lists. --rekey o,r gives o and r free keys and
      leaves the others as they are (a key of another color is still E_KEY_CONFLICT, a variant
      clash still a WARNING). KEY=OUTKEY puts KEY on OUT's key OUTKEY instead of a free one:
      --rekey k=j,n=q uses OUT's j and q, which must be in k's and n's base colors (else
      E_KEY_CONFLICT), and must not be keys of the layer's file; where OUT's variants color
      them otherwise, a WARNING per key names each color that changes. Both mix: k=j,n,s gives
      n and s free keys, and r=r keeps r as it is on purpose. An entry FILE.px:KEY[=OUTKEY] is
      for that source file alone: --rekey o,girl.px:T=V puts girl.px's T on V, gives every
      file's o a free key, and leaves the other files' T alone (a file's own entry wins over
      one for every file; FILE.px is a path, or the name of one source file). When --rekey
      gives a key a free one though an existing OUT has its base color under another key (in
      other variant colors, so it wasn't reused), a note names that key and the --rekey list
      that uses it anyway: 'note: party.px has the base colors of k n as j q, in other variant
      colors; --rekey k=j,n=q uses those anyway'. After crop's --rekey, four digits are the
      rectangle; write --rekey=1,2,3,4 to name four digit keys there.

      The report: compose reports per source file, in layer order, one line per reason: what
      --rekey moved and why (another color there; OUT's base color but other variant colors; a
      key its layers here don't draw with that the file needs; a key --rekey KEY=OUTKEY
      named), the colors a new OUT left out, which of the file's frames draw with a key it
      lost, and one WARNING per key OUT's variants color otherwise ('WARNING: layer 2
      (keeper.px:idle) draws 'r' #c4473a in party.px's variant colors, not keeper.px's: dusk
      #a33a4c (keeper.px: #83344e); compose --rekey r gives it a key of its own'). An
      E_KEY_CONFLICT line offers the same moves --rekey makes, with the same reasons.

      Variants (rule 3) come along for the keys OUT has, in the colors of the layer whose
      key OUT has. Layers from files with different variants (a market's dusk, a keeper's
      night, a candle's dark): each of OUT's variants covers only the layers whose file has
      it, and a note per variant says which layers stay at their base colors in it.
      --variant-map dusk=night,dark (repeatable) builds OUT's dusk from each layer's first
      of dusk, night, dark, so every layer dims together; a new OUT's palette is then
      inlined (its variants are built, not imported). The map adds to the same-name lookup,
      never replaces it: it says only where OUT's dusk comes from, and OUT's other variants,
      night among them, still read each file's variant of the same name (a keeper's night is
      then OUT's dusk and OUT's night too), and may feed several maps. A new OUT merges a variant into the map's only
      when every file that has it gave it to the map (the keeper's night, read as dusk):
      then it gets no variant of its own. One that a file keeps as its own (its file has a
      dusk too) stays one of OUT's variants. With an existing OUT, whose variants stay its
      own, the map says which of each layer's variants to read as OUT's dusk (dusk must be
      one of OUT's). A key a layer draws in OUT's base color but that its file's variants
      color otherwise (one red awning, recolored by one pack's dusk and another's night), in
      a new OUT or an existing one, gets a WARNING: OUT's variants color those pixels OUT's
      way. --rekey gives such a key a free key of its own, as it does a key of another
      color, reusing a key of OUT only when it looks the same in every variant. crop writes
      a new OUT the same way, and crop, paste and frames --copy-to bring keys in the same
      way.

      Comments: the comments above the layers' key and @variant lines come along, as for
      palette --extract-to; a comment naming a key --rekey renamed says so: '# lamp colors
      (l, g) stay lit (renamed l>I g>J)'. The keys right below a key's comment in its file
      (the keys it is about: '# light-emitting keys' above f a i) stay below it. From
      several files, each saying which file's it is ('from keeper.px's @variant night, dusk
      here'), and one that names a variant --variant-map merged into another says so ('from
      player.px, whose dark is dusk here'). A @variant's comment names only the files whose
      variant lines gave OUT's own @variant keys, and when OUT imports the rest, says so
      ('from visitors.px's @variant night; the rest from pal.px's night'). An OUT whose
      palette is inlined also gets the palette files' header comments at the top of its
      palette, each with the files it came from.
      A new OUT's header says how it was made: '# composed by: pxart compose --map room.map -o
      room.px', its paths from OUT's folder (composing OUT whole again updates it). A variant
      WARNING about OUT then also offers composing it again, with --replace, once the sources
      have that variant.

      Frames and canvas: layers can be frames of one parts file: parts.px:hat@3,0
      parts.px:body@0,8. OUT:frame keeps OUT's other frames (OUT may be a palette-only file),
      and the 'wrote' line says when it replaced one. A new frame goes after the last frame of
      its animation (like dup), or at the end when the animation is new. Canvas size: --size,
      else --map's, else the frame being replaced, else the other frames of its animation,
      else the first layer. Pixels that land outside the canvas are cropped, with a note saying
      how many. --under keeps OUT's frame and draws the layers behind it: they fill only its
      empty pixels (a floor or a shadow under a finished sprite). The frame must exist.

      From a map: --map MAP reads scene's tilemap (legend, rows, '---' layers, +b, a '#'
      legend line; see scene) and makes each cell a layer, drawn where scene draws it, then
      the LAYER@x,y given over them; --tile is scene's (N means NxN). Palette, --rekey and
      --variant-map work as for any layers. A legend entry with its own %VARIANT comes in
      that variant's colors, as a file of its own (tiles.px%dark; --rekey tells it from
      tiles.px), and a PNG in keys of its own: OUT's variants leave both as they are, as
      scene --variant does. So 'compose --map market.map -o market.px' renders as 'scene
      --map market.map --bg transparent --scale 1 -o market.png' does, pixel for pixel, in
      every variant too, except where a translucent pixel lands on another: a .px pixel is
      one key, so it replaces what scene blends.
  dup FILE:ID NEWID [--after ID | --replace] [-o OUT]
  dup FILE:GROUP NEWGROUP [--after ID] [--replace] [-o OUT]
      Copy a frame under a new id, placed after the last frame of NEWID's animation, or
      when that animation is new, after the source's whole animation (or after --after).
      A new animation inherits the source's @anim timing.
      A GROUP copies its frames (walk/0 -> run/0), @anim and @still lines too.
  anim-set FILE:GROUP [ms=N] [direction=D] [repeat=N] [pivot=X,Y] [--still | --no-still] [-o OUT]
      Write timing: updates the '@anim GROUP' line, or adds one, in the order of the frames.
      FILE:GROUP/ID (one frame) takes only ms=N and pivot=X,Y and sets that frame's own
      ('@frame ID ms=N pivot=X,Y'), which wins over the group's. KEY= with no value clears
      a setting.
      A path that is both a group and a frame means the group. Only that one line changes.
      --still adds '@still GROUP' (the group is no animation: UI icons, parts), --no-still
      removes it; FILE with no :GROUP (or FILE:*) --still writes '@still *' (every frame),
      unless every frame already is in a @still group: then it says so and adds nothing. An
      @anim line stays, unused while the group is still.
  palette FILE [--add k=#hex ...] [--variant NAME [--add k=#hex ...] [--keep KEYS]]
          [--variant NAME --derive-from base|VARIANT [--match FILE%V] [--darken F] [--tint COLOR]
           [--keep-lit KEYS] [--lift-darks]]
          [--comment KEY|@variant NAME 'text' [KEY 'text' ...]] [--comment-header 'text']
          [--hoist KEYS] [--export out.gpl|out.hex [--used]] [--extract-to P.px [--repoint]]
          [--remove KEYS [--to KEY]] [--in DIR] [--import P.px] [--order KEYS] [-o OUT] [--dry-run]
      Rules ('pxart help palette-rules' prints only these):
        - No flags lists the palette: each key, its color, where it comes from and how often
          it's drawn, then what each variant recolors.
        - Edits write FILE's own lines (-o OUT: a copy; --dry-run: a diff, nothing written). An
          imported key or variant is edited in its palette file: --hoist moves FILE's keys
          there, and --remove of an imported key takes it out there when no other sprite under
          the directory uses it.
        - A variant is key lines over the base: --variant NAME --add sets keys in it (a key in
          its base color stays lit), --keep lets keys inherit, and --derive-from builds a
          whole variant from the base (--match fits another palette's mood; keys darker than a
          quarter are held dark).
        - Only a variant's edits (--variant with --add, --keep or --derive-from) and --remove
          --to change how FILE renders. --add of base keys, --import, --hoist, --extract-to
          --repoint, --order, --comment and --remove of undrawn keys keep every pixel, in
          every variant.
        - Sharing one palette file: --extract-to P.px [--repoint] writes it from FILE,
          --import P.px points FILE at one, and --in DIR says which sprites under DIR import
          it.
      Examples: 'palette party.px' lists it; 'palette pal.px --variant night --add k=#120e22
      w=#9fb0d4'; 'palette pal.px --variant dusk --derive-from base --match mossback.px%dusk'.

      Listing: after the keys (rule 1), each variant's line: 'dusk: recolors (darker) o x X
      c C; inherits: e E q' (the keys it recolors, then the base keys it leaves alone, both
      in palette order). A recolor is darker, brighter ('brightens y W': lamps lit brighter
      at night) or as bright (Rec. 709 luma, times alpha). A key the variant lists in its
      base color (a lamp that stays lit at night) is neither: 'night: recolors (darker) k w;
      relists unchanged: l g; inherits: nothing'. The palette's comments come along: the
      palette files' header on top, a key's comment after its line ('E #ffe07a local #
      light-emitting keys'), each variant's comment under its line, and the comments on its
      key lines as 'y: # lit in rain: harbor lamp'. A palette file has no 'used' column; --in
      DIR counts the .px files under DIR that import it ('imported by 3 of the .px files under
      crossover/') and, per key, how many of them draw with it ('used by 2 files').

      Base keys: --add k=#hex (or a palette line as the file has it, 'k #hex') adds base keys.

      Authoring a variant: with --variant NAME, --add sets the keys in that variant instead,
      over what it had, and makes the variant when FILE has none by that name (the example
      above). --variant NAME --keep l,g lets keys inherit the
      base colors: their lines in the variant go, and a key an imported variant recolors gets
      its base color on a line of FILE's own, since the import can't change from here. --add
      and --keep can share one call; the keys must be in the base palette. A key --add gives
      the color it already has is left as it is, and said so: 'k is already #0f0f22 in night;
      unchanged'.

      Deriving a variant: --variant night --derive-from base --darken 0.35 --tint '#10183060'
      --keep-lit y,W sets every key of FILE's palette (imported ones too, unless FILE imports
      a night) in night from its base color (or from another variant's: --derive-from
      dusk), each channel times 1 - F (--darken 0.35 keeps 65%), then the --tint color laid
      over at its alpha, the math of scene --tint; the --keep-lit keys keep their
      --derive-from color, listed as lamps kept lit. A key that comes out in its base color
      gets no line. --add in the same call then sets single keys over the derived ones.

      --match FILE%dusk (or FILE:dusk; FILE alone means the variant being made) first maps
      each channel the way FILE's own base -> dusk does, a gain and an offset per channel
      fitted by least squares over the keys that variant recolors (not the ones it relists,
      the lamps), then --darken and --tint as above: the example above gives the cast
      another pack's dusk (a red gain, a blue offset), where one darken and one tint move
      every channel alike. The output prints the fit: 'r x0.92 -17, g x0.81 -11, b x0.78
      +10'. The hold: a key darker than a quarter (Rec. 709 luma, .2126 R + .7152 G + .0722
      B of the sRGB values, under 64) never comes out with a higher luma than its
      --derive-from color: it is scaled back to that luma, its hue kept (a warmer red may
      look a shade lighter), and listed as held, so a near-black outline stays dark under a
      blue tint or offset; else 'held: none'.
      --lift-darks lets the derive brighten them (a fog), and names the ones it did; --add
      sets one anyway.

      Comments: --comment KEY 'text' sets the comment right above FILE's line for KEY
      (replacing the comment lines there; blank lines stay); --comment @variant night 'text'
      the one above '@variant night', which --extract-to and compose carry as the variant's
      section note; with --variant NAME, --comment KEY is KEY's line in that variant. A line
      of FILE's own: an imported key or variant is commented in its palette file.
      --comment-header 'text' sets the comment at the top of FILE. '' removes a comment; a
      newline in the text makes two comment lines. One --comment takes several in turn
      ('palette pal.px --comment y "lamp" E "flame"'), and both repeat and go with --add in
      one call (the key added first): 'palette pal.px --variant night --add k=#120e22
      --comment @variant night "night: only lamps glow"'.

      Removing keys: --remove k,n takes FILE's own keys out: their key lines, their lines in
      FILE's variants, and the comments above those. A key a frame still draws with is
      E_SELECT (naming the frames and how many px), unless --to j repaints those pixels as j
      first: 'palette party.px --remove k,n --to j'. An imported key is repainted the same way
      in FILE, then removed from the palette file that defines it only when no other .px under
      DIR uses it (draws with it, or lists it in a variant, with no key line of its own); DIR
      is --in DIR, else the directory holding both FILE and the palette file. Otherwise it
      stays there, and a line names who uses it: 'b stays in pal.px: cavegirl.px uses it'.
      A palette file's own --remove can't see the sprites that import it: check them after
      (palette pal.px --in DIR shows who draws with each key).

      Order: --order o,t,k (or otk) moves FILE's own key lines to the top of its palette in
      that order, each with the comment and blank lines above it, the other keys after them as
      they were: group a material's ramp, or put the outline first. Variants and a
      '. transparent' line keep their places.

      Sharing a palette file: --import P.px adds '@palette P.px' to FILE (re-pointed from
      FILE's directory) and drops FILE's key lines P has in the same colors (and their variant
      lines P's variants say already), saying which: 'dropped o t k (their key lines: the same
      colors in pal.px)'. A key FILE has in another color than P's is E_KEY_CONFLICT, with
      free keys for FILE's and the recolor that moves them ('pxart recolor boy.px 'k>a''),
      then --import again. FILE renders as before, in every variant it had: where P's variant
      of that name would recolor a key FILE keeps, FILE's variant lists the key's color, and
      says so. A variant only P has comes along (a note says so).

      --hoist l,g moves FILE's own keys into the palette file it imports (its one @palette),
      with their lines in FILE's variants and the comments above both, so every sprite that
      imports it gets them; FILE renders as before. A key the palette file has in another
      color is E_KEY_CONFLICT (give FILE's a free key first: recolor FILE 'l>L'); a variant
      line the palette file has in another color stays in FILE.

      --extract-to P.px writes FILE's whole palette as a palette file for @palette: every key
      FILE renders with (imported ones too, local ones winning) and every variant, with the
      comments that document them: those above key and @variant lines (a section comment, '#
      glow: left out of dusk on purpose'), from FILE and the palette files it imports, and a
      palette file's header comment (a sprite's header is about the sprite and stays).
      --repoint then replaces FILE's @palette, key and @variant lines with '@palette P.px'
      (re-pointed from FILE's directory): FILE renders the same, and other sprites can share
      P.px.

DRAWING (edits like EDITING: FILE[:SEL] draws on every selected frame, -o OUT, only changed rows
  are rewritten; KEY is a palette key, or '.' to erase). Shapes are clipped to the frame (a
  note says how many px fell outside); x,y may be negative. line, rect, poly, ellipse, arc and
  flood print "painted N px" ("erased" for '.').
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
  ellipse FILE[:frame] KEY cx,cy,rx,ry | --box x,y,w,h [--fill | --ring N]
      The ellipse inscribed in the box cx-rx..cx+rx, cy-ry..cy+ry: 2*rx+1 wide, so a whole
      center and radius give odd sizes (4,4,3,3 is 7x7) and both ending in .5 give even ones
      (3.5,3.5,3.5,2.5 is 8x6 at 0,1; so is --box 0,1,8,6, rect's x,y,w,h: no halves). A thin
      8-connected outline (Zingl's algorithm), mirror-symmetric, no stray pixels; boxes 1 or
      2 px across are filled. --ring N: N px thick, inward (a halo).
  arc FILE[:frame] KEY cx,cy,r a0,a1 [--width N]
      Part of the circle ellipse cx,cy,r,r draws, from angle a0 to a1 in degrees, counter-
      clockwise, 0 = right, 90 = up (0,90 is the upper-right quarter; 300,60 wraps through 0;
      a1 - a0 >= 360 is the whole circle). A pixel is on the arc when the direction from the
      center to it is in the range, ends included. --width N thickens it inward: a smear or
      swoosh ('arc hero.px:attack/2 W 16,20,14 20,160 --width 3').
  flood FILE[:frame] KEY x,y [--diagonal]
      Bucket fill: repaint the region of x,y's key that touches x,y through sides (4-connected),
      or corners too with --diagonal.
  rotate FILE[:SEL] 90|180|270 [-o OUT]    turn frames clockwise (a WxH frame becomes HxW)
  transpose FILE[:SEL] [-o OUT]            mirror across the top-left/bottom-right diagonal
      For deriving path edges and corners from one tile. -o FILE:NEWGROUP turns a copy, as
      flip's. The shading turns with the pixels (a note says where the light went), so
      re-light with shade and outline --selective after.
  shade FILE[:frame] --ramp d2,d1,base,l1[,l2] [--keys k1,k2] [--base K] [--light nw]
        [--strength N] [--region x,y,w,h] [--dither] [--preview P.png]
      Re-shade a material: the pixels whose key is in --keys (default: the ramp's keys, so a
      shaded material re-shades) get ramp tones by how they face the light. The ramp runs
      darkest to lightest; the base is its middle key (d2,d1,base,l1: the extra key goes
      dark), or --base K. Keys are 'a,b,c' or 'abc'. Nothing outside the material changes.
      --region x,y,w,h repaints only the material inside it, shaded as part of the whole
      frame's material: the region's border is not an edge, only a real one is (an empty
      pixel, another material, or the frame's side).
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
           tone) takes its neighbors' commonest tone. No noise.
      --dither mixes adjacent tones with a 4x4 ordered (Bayer) pattern where the lighting is
      within a quarter step of a band boundary (and skips the stray-pixel pass). --light: n
      ne e se s sw w nw (default nw). --preview P.png renders the result (render's grid and
      rulers) and writes nothing else. Prints the pixels it changed, by the tone they got,
      darkest first: "changed 24 px: 4->A, 8->B, 8->D, 4->E" (with --preview, "would change").
      'shade hero.px:idle/0 --ramp XxcCw --keys c' shades the cloak c with the ramp X x c C w.
  outline FILE[:frame] --key K [--outside | --inside] [--lit L [--selective]] [--light nw]
          [--corners] [--preview P.png]
      Outline the frame's shape (every pixel that draws in some variant). --outside (the
      default) paints the empty pixels touching the shape on a side; --inside repaints the
      shape's own pixels that have an empty side (off the frame counts as empty). Sides only is
      the pixel-perfect rule: a diagonal edge gets a 1px staircase and a square corner is cut,
      so there are no doubled (L-shaped) corners; --corners also takes the pixels touching only
      at a corner (square corners, a 2px staircase). Selective outline (--lit L, or
      --selective --lit L): outline pixels facing the light get L (a darker tone of the
      material, say) and the rest K. Facing: the outline pixel's outward normal (shade's, over
      2px) dotted with the light's direction; above 0 is lit, so a nw light lights the top and
      left edges and a 45-degree edge (ne, sw) stays K. --light and --preview as for shade.
      Prints the pixels it changed, by the key they got:
      "changed 12 px: 6->o, 6->l" (outline pixels that already had their key don't count).

CONVERTING
  export FILE|DIR[:SEL]... [--frames DIR] [--aseprite sheet.json] [--tiled tiles.tsj] [--variant V]
         [--prefix-file] [--exclude GLOB]
      --frames: one PNG per frame at DIR/<frame id>.png, and DIR/pivots.json when frames have
        pivots: {"walk/0": {"x": 8, "y": 23}, ...} (frames without one are left out)
      --aseprite: sheet PNG + Aseprite-style JSON (frames, durations, frameTags; pivots as
        Aseprite writes them: meta.slices = one slice "pivot" with a key per frame index,
        {"frame": N, "bounds": {"x": 0, "y": 0, "w": W, "h": H}, "pivot": {"x": X, "y": Y}},
        bounds = the whole frame, pivot relative to it, "pivot" left out for a frame without)
      --tiled: sheet PNG + Tiled tileset JSON with per-tile animations (worlds: help worlds)
      (--aseprite x.json and --tiled x.tsj write the same x.png)
      FILE:SEL exports only those frames; several selectors of one file add up, in file
      order: 'export harbor.px:cobble harbor.px:water --tiled t.tsj' (no 32x32 props).
      Several files and directories export together, file by file in the order named; a
      directory stands for every .px under it (palette files skipped, --exclude as for
      sheet): 'export town/ --frames out/'. No two frames may get one name: an id two files
      share (each file's idle/0; two animations of one name too), or, with --frames, two ids
      that differ only in case (Door, door: one file on macOS), is E_DUP_FRAME, and nothing
      is written. --prefix-file ids them FILE/ID, FILE being the file's path under its
      directory without .px, or a named file's stem (roofs/roof-red, props/well/well; an
      unnamed grid is FILE alone), in the PNG paths, the Aseprite filenames and tags and the
      Tiled animations.
      Id order (the Aseprite frame index, the Tiled tile id, the sheet position): 0, 1, 2...
      over the exported frames, file by file, with each animation group contiguous, groups
      in order of first appearance, and all top-level frames (no '/' in the id) together as
      one group where the first of them appears. A file that keeps each group together, and
      its top-level frames together, gets ids in file order; otherwise a frame moves up to
      its group: a/0 b/0 a/1 -> a/0=0 a/1=1 b/0=2, and icon walk/0 badge -> icon=0 badge=1
      walk/0=2. Adding, removing or moving frames can renumber others, and a Tiled map
      painted with the old tileset keeps the old ids.
  from-png A.png [B.png ...] [-o OUT.px] [--id PREFIX] [--prefix-dir] [--palette P.px] [--colors N]
           [--names A,B,... | --labels FILE.csv [--label-col proposed_name] [--file-col filename]]
  from-png SHEET.png --grid WxH [--names A,B,...] [--by rows|cols] [-o OUT.px] [--id PREFIX] [--palette P.px]
      PNG -> .px with exact pixels. One PNG and no --id: a single unnamed grid.
      Several PNGs, --id, or an existing OUT: frames named PREFIX/<png stem>, added
      to OUT (replacing same-id frames, which the 'wrote' line names). Two PNGs of one run that would get one id (two packs'
      tile_0002.png) are E_DUP_FRAME, naming both: --prefix-dir ids each one FOLDER/STEM
      by its directory's name (dungeon/tile_0002, creatures/tile_0002). Colors
      already in OUT keep their keys, so frames imported in separate runs share one
      palette. --palette P.px starts a new OUT that imports P and reuses its keys.
      Naming loose PNGs: --names A,B,... gives one frame id per PNG, in order (as many names
      as PNGs; '' skips one). --labels FILE.csv names them from a CSV, the way packs ship
      one ('filename,proposed_name,...'): each PNG takes the --label-col (default
      proposed_name) of the row whose --file-col (default filename) names it, a path
      relative to the CSV's directory, or else its file name alone. --labels repeats, one
      CSV per pack (with --prefix-dir: dungeon/wall-stone-top, creatures/skeleton). A PNG no
      row names is E_SELECT. --prefix-dir and --id PREFIX go in front of either.
      --grid 16x16 slices one sheet into 16x16 cells, a frame each; a cell with no opaque
      pixel is skipped. Each row of cells is a group (--by cols: each column), its cells left
      to right (top to bottom) frames 0, 1, ...: --names names the groups in turn (an empty
      name skips its row), else they are STEM/row0, STEM/row1 (col0, ...); --id PREFIX goes
      in front. A pack whose columns are directions and rows are steps:
      'from-png Walk.png --grid 16x16 --by cols --names walk/down,walk/up,walk/left,walk/right
      -o boy.px' writes walk/down/0-3 and so on. A sheet that isn't a whole number of cells
      is E_BAD_ARG, unless the strip left over is empty (then a note says so).
      More colors than keys (a photo): --colors N reduces the PNGs to N first, inexactly,
      and says by how much.

HELP
  help [all | recipes | TOPIC | CMD]
      'pxart help recipes': seven workflows, command by command; 'help worlds': Tiled worlds.
      'pxart help all' prints this whole reference; 'pxart help TOPIC' one part of
      it (a heading here, any case); 'pxart help CMD' is 'pxart CMD -h'.
      'pxart help compose-rules' and 'pxart help palette-rules' print only the rules those
      sections open with.

ERROR CODES
  E_VERSION E_BAD_KEY E_DOT_RESERVED E_BAD_COLOR E_DUP_KEY E_PALETTE_AFTER_GRID
  E_PALETTE_FILE E_BAD_ROW E_ROW_WIDTH E_UNKNOWN_KEY E_EMPTY_FRAME E_NO_FRAMES
  E_BAD_ID E_DUP_FRAME E_MIXED_FRAMES E_BAD_ARG E_VARIANT_KEY E_UNKNOWN_SECTION
  E_SELECT E_KEY_CONFLICT E_TILE_SIZE E_FILE
  Every error line starts with the command ('ellipse: E_BAD_ARG: cy=1.5 and ry=1 ...'). An
  error in an input file also says which input it came from, then where in the file:
  'compose: layer 2 (parts.px:hat): parts.px:4: E_ROW_WIDTH (frame hat, ...'.
  A file that can't be read is one E_FILE line too (see FORMAT: paths).
  Inputs are named like -h names them: FILE, SRC, --into, -o, OUT, A/B, layer N, item N,
  file N (the Nth of several), --map, --palette, stdin. check reports per file instead.
  A command that fails prints none of its notes or WARNINGs: they describe the write it was
  about to make (a grid renamed, keys rekeyed), and nothing was written.
"""
import argparse, contextlib, csv, difflib, fnmatch, io, itertools, json, math, os, pathlib, posixpath, re, shlex, string, sys, textwrap, unicodedata
from PIL import Image, ImageChops, ImageDraw, ImageFont

WORLDS = """WORLDS (pxart help worlds)
  export world.src.json|ROOM.map|DIR... --tiled [--tile 16x16] [--tileset T.tsj]
  check world.src.json|W.world|ROOM.tmj|DIR... [--tile 16x16] [--tileset T.tsj]
  world W.world|ROOM.tmj -o world.png [--scale 2] [--dry-run]
      A world is rooms drawn as .map files (scene --map's format) and a world.src.json that
      places them and wires their doors. --tiled (with no X.tsj) compiles them to Tiled's
      files, beside them: rooms/NAME.map -> rooms/NAME.tmj, world.src.json -> world.world
      (NAME.src.json -> NAME.world). check runs the same compile and writes nothing: 'ok
      world.src.json: 3 rooms placed, interior tower, 1 door pair, start in shore', or FAIL
      and every error. A DIR stands for the world sources under it (a rooms/ directory is
      an error naming its world). --tile: the rooms' tile size (default 16x16).
      The source:
          {"layout": ["shore point", "cove  ."],
           "start": {"room": "shore", "at": "@"},
           "doors": [["point D", "tower d"], ["shore H", "hut h", {"trigger": "use"}]]}
      layout draws where rooms sit ('.': none; a column as wide as its widest room, a row as
      tall as its tallest, an empty one as the largest room). A room only doors name is an
      interior: compiled, not in the .world. start: a point object (class start) at the
      feet (bottom centre) of the one cell shore.map draws '@' on. A door pair is two door
      objects (class door), each the rectangle of cells its char is drawn on, with target
      (the other's .tmj), entry (the other's name) and the pair's {...} as properties
      (trigger: touch, the default, or use; target and entry are the compiler's).
      Variant tiles: a legend line may list tiles, '1 sand.png sand2.png sand3.png' (two or
      more, each a .png or .px[:frame], quoted if it has spaces). Each cell drawn with 1
      gets one, picked by cell_hash(room, x, y), the room being the map's file name without
      .map; scene, compose --map and export --tiled pick the same one.
      What a room compiles to: a layer's one-tile cells make a tile layer ('layer N'); +b
      entries, art of another size, and cells an earlier object in the layer overhangs are
      tile objects named by their char ('layer N objects', in draw order), where scene
      draws them, so Tiled renders what scene --map does, pixel for pixel. Flips are GID
      flags. The .tmj's 'source' property names its .map.
      Tilesets: a cell's art is found in <dir>/tiled/*.tsj in the directories above it (its
      pack's; the search stops at a directory holding a *.src.json or .git) and in
      --tileset's: a PNG by a tile's png property (or image), a .px frame by its pixels. A
      GID is firstgid + that tile's stable id. Tilesets start at firstgid 1, 1001, 2001...
      (a bigger one at the next such after its end), so one that grows moves no other; a
      tileset keeps its previous firstgid while it fits.
      Object ids are stable: a recompile reads the previous .tmj and keeps the id of the
      object of the same layer, class and name at the same cell; a new object takes
      nextobjectid; an id is never reused. An object in the previous .tmj that isn't from
      the source (added in Tiled) is dropped, with a WARNING. A .tmj whose 'source' isn't
      its .map (a room made in Tiled) is never overwritten (E_GENERATED). A .map that's a
      world's room (rooms/ beside a *.src.json, or a .tmj with doors or a start) isn't
      compiled alone (E_WORLD): compile its world.
      Errors are said all at once, at file:line:col, and nothing is written: a ragged row
      (E_ROW_WIDTH), a ground (layer 1) shorter than the room (E_MAP_SIZE), an unknown char
      (E_UNKNOWN_KEY), art no tileset has (E_TILESET), a door or start char not drawn as one
      rectangle or at one cell (E_DOOR, E_START), a bad world source (E_WORLD). A shorter
      layer above the ground, and art bigger than a cell without +b (placed by its
      top-left), get a WARNING. Then the world rules run on the compiled files: doors pair
      up and have a walkable cell beside them, one start, not in a solid, every door
      reachable from it, rooms don't overlap. A broken rule is 'E_WORLD: door-arrival:
      ...'; a warning (an edge walkable on one side only, a room nothing reaches) is a
      WARNING line. The rules are one spec with shared fixtures, run by pxart and the
      harness: tests/fixtures/world_rules/ (SPEC.md) in the pxart repo.
      Compiled worlds (the runtime files, so a world made in Tiled too): check W.world runs
      the world rules on the .world, the rooms it places and every room a door leads to,
      exactly as the compile runs them: 'ok   world.world: 3 rooms placed, interior tower, 1
      door pair, start in shore', or FAIL and each error, 'rooms/point.tmj: E_WORLD:
      door-pair [D, cell 10,7]: ...' (the door's or start's name, or the edge's side, and
      the cell); a warning is a WARNING line. A lone ROOM.tmj is a world of that one room
      (placed at 0,0, its doors leading to its interiors); a .tmj that a .world beside it or
      one directory up has (placed, or through doors) is E_WORLD: give the world (and so
      is one beside a .world that can't be loaded: fix that). A DIR checks the world
      sources and the .world files under it, but not a .world beside a *.src.json (its
      source is the same compile); a DIR of .tmj rooms only says to check their world.
      Only orthogonal, finite maps with CSV (JSON array) tile data, in JSON files, are read
      (a .world placing maps by patterns, a .tmx map or .tsx tileset is E_WORLD, naming what
      to change in Tiled), as the harness reads them: SPEC.md, 'Not rules'.
      world draws one: each room as Tiled draws it (markers too), the placed ones where
      the .world puts them, spread apart so a shared side shows as a gap, and interiors in
      a column to the right. Across each shared edge, a band per cell: yellow where both
      sides are walkable (you can cross), magenta where only one is (edge-one-side; the
      walkable cell outlined), nothing where both are solid. Each door is outlined, with a
      dot on each cell you arrive on beside it and a line to its entry, arrowheads at the
      doors it leads to (a door that doesn't pair up: magenta, one arrowhead). The start
      is a green cell, markers cyan rings. Every rule issue is a numbered magenta tag
      where it is (a cell, a door, a room; tags that would overlap move aside), listed
      under the picture and printed ('[1]
      WARNING: rooms/cove.tmj: edge-one-side [north, cell 1,0]: ...'); an unreachable
      room is hatched, a room the .world names but can't load crossed out. A broken world
      still draws (exit 0): check is the verdict. world reads compiled files only ('export
      world.src.json --tiled' first). --scale (default 2) scales the rooms, not the gaps
      or labels.
      Error codes: E_MAP_SIZE E_TILESET E_GENERATED E_WORLD E_DOOR E_START, and the map's
      own (E_ROW_WIDTH E_UNKNOWN_KEY E_BAD_ROW E_FILE).
"""


RECIPES = """RECIPES (pxart help recipes)
  Seven workflows, end to end. Each runs as written from a folder holding the files it names;
  'pxart help CMD' has the rest of each command.

  1. Port a pack and prove it lossless
     A pack's loose PNGs and the labels.csv it ships become one .px, or several in a folder.
     One diff then checks every frame against its PNG and exits 1 if any differs: a .px's
     frames, or every frame of every .px in the folder (--exclude GLOB leaves some out).
       $ pxart from-png pack/*.png --labels pack/labels.csv -o town.px
       $ pxart diff town.px pack/ --labels pack/labels.csv
       $ pxart from-png pack/tile_0000.png pack/tile_0002.png --labels pack/labels.csv -o town/ground.px
       $ pxart from-png pack/tile_0001.png pack/tile_0003.png --labels pack/labels.csv -o town/props.px
       $ pxart diff town/ pack/ --labels pack/labels.csv
       $ pxart check town/

  2. Merge packs, variants and all
     Two characters from different packs into one file that imports a shared palette: --prefix
     keeps their ids apart, --rekey their keys, and --variant-map reads the keeper's dark as
     party.px's night. diff proves each copy renders as its original, variant by variant.
       $ pxart new party.px --empty --palette pal.px
       $ pxart frames wick.px:walk --copy-to party.px --prefix wick/
       $ pxart frames keeper.px:walk --copy-to party.px --prefix keeper/ --rekey --variant-map night=dark
       $ pxart diff keeper.px:walk party.px:keeper/walk
       $ pxart diff keeper.px:walk%dark party.px:keeper/walk%night
       $ pxart diff wick.px:walk%night party.px:wick/walk%night

  3. Build a dusk or a night
     A night derived from the base colors (darkened, tinted, the lamp kept lit), or a dusk
     fitted to another pack's; then read what each recolors, and one pixel in every variant.
       $ pxart palette pal.px --variant night --derive-from base --darken 0.35 --tint '#10183060' --keep-lit y
       $ pxart palette pal.px --variant dusk --derive-from base --match mossback.px%dusk
       $ pxart palette pal.px
       $ pxart stats hero.px:idle/0 --at 7,2
       $ pxart sheet hero.px --variant night -o night.png

  4. Slice a sheet
     A 64x64 sheet whose columns are directions: a group per column, then timing, and a look.
       $ pxart from-png Walk.png --grid 16x16 --by cols --names walk/down,walk/up,walk/left,walk/right -o boy.px
       $ pxart anim-set boy.px:walk/down ms=120 direction=pingpong
       $ pxart frames boy.px
       $ pxart sheet boy.px --rows group -o boy.png

  5. Make a scene from a map
     A text tilemap (scene in 'pxart help LOOKING' has the format) renders as a PNG, or
     composes into a .px room that renders the same, pixel for pixel, base and night (the
     proofs render at 1x on a transparent --bg). --rekey gives the map's lamp.px%base its own
     keys, so the room's night leaves it lit, as scene does.
       $ pxart check market.map
       $ pxart compose --map market.map -o market.px --rekey
       $ pxart scene --map market.map --bg transparent --scale 1 -o market.png
       $ pxart diff market.px market.png
       $ pxart scene --map market.map --bg transparent --scale 1 --variant night -o night.png
       $ pxart diff market.px%night night.png

  6. Check an animation's feet
     anim prints what moved in each frame: 'rows 9+ still' says rows 9 down (the feet) never
     moved, where 'shift +0,+1 then 0px' would be the whole sprite bobbing, feet and all. onion
     --feet 3 reads the bottom 3 rows alone ('bottom +0': the feet stayed put). A pivot on the
     feet then lines the frames up in sheet and anim. A whole-sprite bob ('shift +0,+1 then
     0px', feet and all) isn't a feet problem, and no pivot fixes it: shift that frame back up
     (shift FILE:frame --dy -1), then lower only the body (--region x,y,w,h above the feet).
       $ pxart anim hero.px:walk/down
       $ pxart onion hero.px:walk/down/0 hero.px:walk/down/1 --feet 3 -o feet.png
       $ pxart anim-set hero.px:walk/down pivot=8,11
       $ pxart sheet hero.px:walk/down --align pivot --fit -o walk.png
       $ pxart anim hero.px:walk/down -o walk.gif

  7. Stamp an overlay behind every frame of an animation
     A glow drawn once, as a frame of its own, goes behind every frame of a flight: --align
     shift moves it as anim's best shifts say the body bobs (--at places it in the first
     frame; bbox would follow the wing tips), and --under keeps it behind. Its key is
     transparent by day and lit at night, so the sheet shows the flight and the glow (FILE:a,b
     lists them) at night.
       $ pxart palette pal.px --add G=transparent
       $ pxart palette pal.px --variant night --add 'G=#f3cf6b60'
       $ pxart new bat.px:glow --size 16x12
       $ pxart ellipse bat.px:glow G --box 2,0,12,9 --ring 2
       $ pxart paste bat.px:glow --into bat.px:fly --at 0,1 --under --align shift
       $ pxart sheet bat.px:fly,glow --variant night -o glow.png
"""


KEY_HELP = "a palette key, or '.' to erase"
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
    def __init__(self, code, msg, path=None, line=None, frame=None, row=None, cols=None, col=None):
        self.code, self.msg, self.path, self.line = code, msg, path, line
        self.frame, self.row, self.cols, self.col = frame, row, cols, col  # col: 1-based, printed as path:line:col
        self.ctx = None  # which input of the command it came from: 'layer 2 (parts.px:hat)' (see reading())

    def __str__(self):
        if self.ctx and self.ctx != str(self.path):
            here = Issue(self.code, self.msg, self.path, self.line, self.frame, self.row, self.cols, self.col)
            return f"{self.ctx}: {here}"
        where = str(self.path or "")
        if self.line:
            where += f":{self.line}" + (f":{self.col}" if self.col else "")
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


def guess(word, names):
    """'; did you mean 'idle'?' for a misspelled name among names (difflib's closest), or ''."""
    got = difflib.get_close_matches(word, [n for n in dict.fromkeys(names) if n != word], n=1)
    return f"; did you mean {got[0]!r}?" if got else ""


def fail(code, msg, **kw):
    raise PxError(Issue(code, msg, **kw))


@contextlib.contextmanager
def reading(label):
    """Errors inside name the input they came from: 'layer 2 (parts.px:hat)'; main adds the command in front.
    The innermost label wins. A file a path option names that can't be read (an OSError) carries the option's label
    too, for its E_FILE line: '--match (../wick/pal.px%dark)'."""
    try:
        yield
    except PxError as e:
        for i in e.issues:
            i.ctx = i.ctx or label
        raise
    except OSError as e:
        if label.startswith("--") and not getattr(e, "option", None):
            e.option = label
        raise


def typed_path(p):
    """A path as typed on the command line, for a message: with ' (from the current directory)' when it is relative,
    since every such path is read from there (a path inside a file is read from that file's directory)."""
    return f"{p} (from the current directory)" if not os.path.isabs(str(p)) else str(p)


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
        self.before = None          # edit_target: each frame's grid before the edit, to say what it touched
        self.dest = None            # palette -o: where the edited file goes instead of path

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
                fail("E_SELECT", f"unknown variant {variant!r} (have: {', '.join(have) or 'none'})"
                     + guess(variant, have), path=self.path)
            pal.update(self.shared_variants.get(variant, {}))
            pal.update(self.variants.get(variant, {}))
        return pal

    def blanks(self):
        """The keys that draw nothing: '.', and a key transparent in the base and in every variant. A key transparent
        only in the base (a halo lit at night) draws: what a frame has is its keys, not its base colors."""
        pals = [self.resolved()] + [self.resolved(n) for n in variant_names(self)]
        return {k for k in pals[0] if not any(p[k][3] for p in pals)}

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
        if sel and "," in sel:  # FILE:a,b,c: each one's frames, in the order named, each frame once
            got = {}
            for part in sel.split(","):
                if not part:
                    fail("E_SELECT", f"{sel!r} has an empty item; a list is ids or groups between commas: "
                         f"{','.join(p for p in sel.split(',') if p)}", path=self.path)
                got.update({id(f): f for f in self.select(part) if id(f) not in got})
            return list(got.values())
        if not sel or sel == "*":  # FILE:* says every frame out loud
            return list(self.frames)
        if self.implicit and sel == self.stem:  # the unnamed grid goes by the file's name, as frames lists it
            return list(self.frames)
        got = [f for f in self.frames if f.id == sel or (f.id or "").startswith(sel + "/")]
        if not got:
            fail("E_SELECT", f"no frame or group {sel!r}; {self.listing()}" + guess(sel, self.paths()), path=self.path)
        return got

    def listing(self):
        """'groups: walk/down, idle; frames: walk/down/0, ...' (no groups: only the frames), for a selector's error."""
        groups = list(dict.fromkeys(f.group for f in self.frames if f.group))
        return (f"groups: {', '.join(groups)}; " if groups else "") + \
            f"frames: {', '.join(self.label(f) for f in self.frames)}"

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

    def paths(self):
        """Every frame id and group path (walk/down/0, walk/down, walk): what FILE:SEL can name."""
        out = []
        for f in self.frames:
            parts = self.label(f).split("/")
            out += ["/".join(parts[:i]) for i in range(len(parts), 0, -1)]
        return list(dict.fromkeys(out))

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
        warn_half(self, variant)
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
        for n, (anchor, gap, line) in enumerate(self.lines()):
            lead = self.lead.get(anchor)
            add = lead if lead is not None else [""] * gap if out else []
            if n == 0 and anchor[0] == "key" and out and out[-1].strip() and not (add and not add[0].strip()):
                add = [""] + add  # a header right above the first key line would read as that key's comment
            out += add
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
                fail("E_PALETTE_FILE", f"can't find palette file {typed_path(palette)}")
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
        if not started and not s.startswith("@") and PAL_RE.match(s):
            # the first line a key line: the comments right above it (no blank line between) are its own; the header
            # is what a blank line separates from it
            cut = max((i for i, l in enumerate(doc.comments) if not l.strip()), default=-1) + 1
            pending[:] = doc.comments[cut:]
            del doc.comments[cut:]
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
                    err("E_PALETTE_FILE", f"can't find palette file {ref!r} (relative to this file, so {target})"
                        + skip, n)
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
    def __init__(self, label, img, ms, doc=None, frame=None, variant=None):
        self.label, self.img, self.ms, self.doc, self.frame = label, img, ms, doc, frame
        self.variant = variant      # onion: the variant it's drawn in, when one was named


def items(arg, variant=None, strict=False):
    variant = split_variant(arg)[1] or variant
    path, sel = split_sel(arg)
    if path.endswith(".png") or path.endswith(".gif"):
        return [Item(pathlib.Path(path).stem, Image.open(path).convert("RGBA"), DEFAULT_MS)]
    doc = parse(path, strict)
    return [Item(doc.label(f), doc.image(f, variant), doc.ms(f), doc, f) for f in doc.select(sel)]


def all_items(args, variant=None):
    """render's and sheet's frames, in order. A frame drawn in a variant is labeled with it, 'idle/0%night': an
    argument's own %variant, else --variant, so its cells read apart from the base ones beside them and a whole sheet
    at night says so."""
    out, paths, owns = [], [], []
    for n, a in enumerate(args, 1):
        with reading(f"file {n} ({a})"):
            got = items(a, variant)
        out += got
        paths += [split_sel(a)[0]] * len(got)
        owns += [split_variant(a)[1] or variant] * len(got)
    tell_apart(out, paths)  # by frame id: hero's and beast's idle/0 collide, whatever variant each is in
    for it, own in zip(out, owns):
        it.label += f"%{own}" if own else ""
    return out


def in_dirs(args, exts=(".px",), exclude=()):
    """check/sheet/stats FILE...: a directory stands for every file under it with one of exts, recursively, sorted by
    path. A directory with none is E_FILE. exclude (--exclude GLOB, repeatable) leaves out a file whose name, or path
    under its directory (or as given), matches a glob, and everything under a directory of the tree that matches one;
    a glob that leaves nothing out gets a note, and one that leaves out every file is E_FILE."""
    out, hit = [], set()

    def excluded(rel):
        got = globs_hit(rel, exclude)
        hit.update(got)
        return bool(got)
    for arg in args:
        if not os.path.isdir(arg):
            if not excluded(split_sel(arg)[0].replace(os.sep, "/")):
                out.append(arg)
            continue
        found = sorted((p for p in pathlib.Path(arg).rglob("*") if p.name.endswith(exts) and p.is_file()),
                       key=lambda p: p.parts)
        if not found:
            kinds = ["*" + e for e in exts]
            said = f"{', '.join(kinds[:-1])} or {kinds[-1]}" if len(kinds) > 1 else kinds[0]
            fail("E_FILE", f"{arg} is a directory with no {said} files under it")
        out += [str(p) for p in found if not excluded(p.relative_to(arg).as_posix())]
    if exclude and not out:
        fail("E_FILE", f"--exclude {' --exclude '.join(exclude)} leaves out every file")
    for g in exclude:
        if g not in hit:
            print(f"note: --exclude {g} matches no file")
    return out


def globs_hit(rel, globs):
    """The --exclude globs that leave out the file at rel (a path under its directory, or as given): matching its name,
    or its path or a directory's it is under ('wip', 'wip/old', 'wip/old/a.px')."""
    parts = pathlib.PurePosixPath(rel).parts
    heads = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
    return [g for g in globs if fnmatch.fnmatchcase(parts[-1], g) or any(fnmatch.fnmatchcase(h, g) for h in heads)]


def frames_only(args, cmd):
    """sheet/stats: palette-only .px files (no frames: nothing to show) are skipped with a note, unless nothing else is
    left; then they stay, for E_NO_FRAMES."""
    pal = [a for a in args if split_sel(a)[1] is None and a.endswith(".px") and os.path.isfile(a) and not _has_grid(a)]
    if len(pal) == len(args):
        return args
    for a in pal:
        print(f"note: {cmd} skips {a}: a palette file, no frames")
    return [a for a in args if a not in pal]


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


def in_file_order(doc, frames):
    """A selection (FILE:hat,idle lists frames in the order named) in the file's order, for a command that writes
    frames where they sit (extract, frames --copy-to/--rm): an animation keeps its play order."""
    ids = {id(f) for f in frames}
    return [f for f in doc.frames if id(f) in ids]


def one_id(sel, arg, what):
    """A selector where one frame (or group) id goes: a list (FILE:a,b) is E_BAD_ARG saying so, not a missing id."""
    if sel and "," in sel:
        fail("E_BAD_ARG", f"{what} {arg!r}: lists aren't supported here; give one id")


def one_frame(arg, what="input", variant=None):
    one_id(split_sel(arg)[1], arg, what)
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


LINE_H = 12  # a strip label line: the pixel font's 11px and a pixel between


def strip_font():
    """anim's strip labels: Pillow's pixel font (its spaces and colons show at 1x, where the default's small
    FreeType face draws '(no shift: 79px)' as '(noshift 79px)'); the default where Pillow has no pixel font."""
    try:
        return ImageFont.load_default_imagefont()
    except AttributeError:
        return ImageFont.load_default()


def fit_lines(d, text, width, font):
    """text in lines no wider than width px, broken at spaces (a word wider than that alone is broken where it must
    be); [] for ''."""
    lines = []
    for word in text.split():
        cand = f"{lines[-1]} {word}" if lines else word
        if lines and d.textlength(cand, font=font) <= width:
            lines[-1] = cand
            continue
        while d.textlength(word, font=font) > width and len(word) > 1:
            n = max(1, max(k for k in range(1, len(word) + 1) if d.textlength(word[:k], font=font) <= width)
                    if d.textlength(word[:1], font=font) <= width else 1)
            lines.append(word[:n])
            word = word[n:]
        lines.append(word)
    return lines


def text_w(d, s):
    return int(d.textlength(s)) if hasattr(d, "textlength") else 6 * len(s)


def outpath(p, make=True):
    """Output path with its directory created (not with make False: a dry run), saying so: 'created out/' for the
    topmost directory it had to make, once a run (the ones under a directory this run made go unsaid). A file where a
    directory should be is a clear E_FILE."""
    p = pathlib.Path(p)
    for d in reversed(p.parents):
        if d.exists() and not d.is_dir():
            hint = f" (a frame goes after ':', as in {d}:{p.relative_to(d).as_posix()})" if d.suffix == ".px" else ""
            fail("E_FILE", f"can't write {p}: {d} is a file, not a directory{hint}")
    if make and not p.parent.exists():
        top = next(d for d in reversed(p.parents) if not d.exists())
        p.parent.mkdir(parents=True, exist_ok=True)
        if not any(d.resolve() in CREATED for d in top.parents):
            print(f"created {top.as_posix()}/")
        CREATED.add(top.resolve())
    return p


CREATED = set()  # directories outpath made this run: one 'created DIR/' line for a tree of them


DRY = {"run": False}  # --dry-run (render, sheet, anim, onion, scene): everything computed and printed, nothing written


def wrote(*paths):
    """The line saying what a looking command wrote: 'wrote a.gif and a.strip.png', or on a dry run what it would
    have, 'would write a.gif and a.strip.png (dry run; nothing written)'."""
    paths = [str(p) for p in paths if p is not None]
    if DRY["run"]:
        return (f"would write {' and '.join(paths)} " if paths else "") + "(dry run; nothing written)"
    return "wrote " + " and ".join(paths)


HUGE_SIDE, HUGE_AREA = 4096, 16_000_000  # an image output past either gets a WARNING: viewers shrink or refuse it


def huge(size):
    """Why an image of this size is too big to look at comfortably, or None."""
    w, h = size
    if max(w, h) > HUGE_SIDE:
        return f"over {HUGE_SIDE} px on a side"
    if w * h > HUGE_AREA:
        return f"over {HUGE_AREA // 1_000_000}M px"
    return None


def save_image(img, p, what="-o", about=None, smaller=None, **kw):
    """img written to p (its directory made, as outpath does), in the format p's extension names. A name with no
    extension, or one Pillow can't write (-o /dev/null, -o out.px), is E_BAD_ARG before anything is written, and so is
    a format that can't hold the image (RGBA as .jpg); a file that can't be written is the usual E_FILE. Returns p.
    A dry run prints the image's size and `about` (its layout) instead of writing it; an image huge() calls too big
    gets a WARNING either way, with `smaller`, what would shrink it."""
    if p is None and DRY["run"]:  # a dry run with no -o: nothing to check, only the size to tell
        said_size(img, what if what != "-o" else "the image (no -o)", about, smaller)
        return None
    p = pathlib.Path(p)
    ext = p.suffix.lower()
    fmt = Image.registered_extensions().get(ext)
    name = ".gif" if kw.get("save_all") else ".png"  # an animation, or a picture
    if fmt is None or fmt not in Image.SAVE:
        why = f"{ext!r} isn't an image type pxart can write" if ext else "it has no extension to tell the image type by"
        fail("E_BAD_ARG", f"{what} {p}: {why}; name it {name}")
    if kw.get("save_all") and fmt not in Image.SAVE_ALL:
        fail("E_BAD_ARG", f"{what} {p}: a {fmt} can't hold an animation; name it {name}")
    if kw.pop("check_only", False):  # only the name's checks, before a command prints anything
        return p
    p = outpath(p, make=not DRY["run"])
    said_size(img, p.as_posix(), about, smaller)
    if DRY["run"]:
        return p
    try:
        img.save(p, **kw)
    except OSError as e:
        if e.errno is not None or e.filename:  # the file itself: PermissionError and the like, E_FILE in main
            raise
        fail("E_BAD_ARG", f"{what} {p}: a {fmt} can't hold this image ({e}); name it {name}")
    except (ValueError, KeyError, TypeError) as e:
        fail("E_BAD_ARG", f"{what} {p}: can't write it as {fmt} ({e}); name it {name}")
    return p


def said_size(img, name, about, smaller):
    """save_image's lines: on a dry run 'sheet.png: 1234x567 px, 12 cells in ...'; a WARNING for a huge image."""
    if DRY["run"]:
        print(f"{name}: {img.width}x{img.height} px" + (f", {about}" if about else ""))
    why = huge(img.size)
    if why:
        print(f"WARNING: {name} {'would be' if DRY['run'] else 'is'} {img.width}x{img.height} px ({why}): image "
              "viewers and the Read tool may shrink or refuse it" + (f"; {smaller}" if smaller else ""))


ZSH_EATEN_RE = re.compile(r"\.(px|png)[A-Za-z]")


def file_error(cmd, e):
    """An OSError as one E_FILE line that starts with the command, like every error line; the path relative to the
    current directory when it is under it, and then '(from the current directory)', the base every path typed on the
    command line is read from. A path option's line names the option: 'palette: --match (../wick/pal.px%dark):
    ../wick/pal.px (from the current directory): E_FILE: ...'. A missing input like 'hero.pxalk/0' gets the
    zsh-modifier hint."""
    name = str(e.filename or "")
    if os.path.isabs(name):
        rel = os.path.relpath(name)
        name = name if rel.startswith("..") else rel
    where = typed_path(name) if name else ""
    head = f"{cmd}: {e.option}" if getattr(e, "option", None) else cmd
    msg = f"{head}: {where}: E_FILE: {e.strerror or e}" if name else f"{head}: E_FILE: {e.strerror or e}"
    if isinstance(e, FileNotFoundError) and any(ZSH_EATEN_RE.search(part) for part in pathlib.Path(name).parts):
        msg += (f"; {name!r} looks like zsh ate a ':' as a modifier (\"$F:walk/0\" applies :w to $F, \"$F:t\" "
                "applies :t). Write \"${F}:walk/0\" or quote the whole argument.")
    return msg


def sheet_rows(its, cols, rows="cols"):
    """The sheet's rows, as lists of item indexes: --cols items each, or with rows 'group' one animation group per row
    (a file's frames of one group; a file's top-level frames together; a PNG alone), groups in order of first
    appearance, wrapping within a group longer than --cols."""
    if rows != "group":
        return [list(range(n, min(n + cols, len(its)))) for n in range(0, len(its), cols)]
    groups = {}
    for n, it in enumerate(its):
        key = (str(it.doc.path.resolve()), it.frame.group if it.frame else "") if it.doc else ("png", n)
        groups.setdefault(key, []).append(n)
    return [ns[i:i + cols] for ns in groups.values() for i in range(0, len(ns), cols)]


CHECKER = ((0x5c, 0x5c, 0x66, 255), (0x6a, 0x6a, 0x74, 255))  # render's and sheet's default behind a frame: greys a
CELL_BG = "#3a3a44"  # dark outline shows on. CELL_BG: a sheet cell around its frame (and --bg's old default)


def checker(w, h, sq):
    """A w x h checkerboard of sq-px squares in CHECKER's greys: what shows through a frame's transparent pixels."""
    img = Image.new("RGBA", (w, h), CHECKER[0])
    d = ImageDraw.Draw(img)
    for y in range(0, h, sq):
        for x in range((y // sq) % 2 * sq, w, 2 * sq):
            d.rectangle([x, y, x + sq - 1, y + sq - 1], fill=CHECKER[1])
    return img


def sheet(its, out, scale=8, cols=8, bg=None, grid=False, rulers=False, fit=False, align="bottom", rows="cols",
          what="-o"):
    """Frames in a grid of --cols cells, each labeled. Every cell is the largest frame's size; fit: each cell is its own
    frame's (and label's) width, and each row as tall as its tallest frame, rows packed left to right. align 'pivot':
    the frames of one animation group (one file's) are drawn on one canvas each, lined up by pivot as anim does
    (pivot_layout), so a frame whose pivot says its feet are 1px lower sits 1px lower; frames are bottom-aligned in
    their cells either way."""
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    shown = {id(it): it.img for it in its}  # what each cell draws: the frame, or it on its group's pivot canvas
    if align == "pivot":
        groups = {}
        for it in its:
            if it.doc and it.frame and it.frame.group:
                groups.setdefault((it.doc.path.resolve(), it.frame.group), []).append(it)
        for g in groups.values():
            lay = pivot_layout(g)
            for it, at in zip(g, lay[2] if lay else ()):
                shown[id(it)] = placed(it.img, lay[0], lay[1], at, CLEAR)
    tiles = [(it, upscale(shown[id(it)], scale, grid, rulers)) for it in its]
    ruled = 16 if grid and rulers and scale >= 4 else 0  # where upscale's rulers put the frame in its tile
    lws = [max(text_w(probe, it.label), text_w(probe, f"{it.img.width}x{it.img.height} 99c")) for it in its]
    lw = max(lws)
    iw = max((it.img.width for it in its if it.img.height <= 22), default=0)
    cw = max(max(t.width for _, t in tiles), lw + iw + 8)
    ch = max(t.height for _, t in tiles)
    pad, lab = 10, 26
    cols = max(1, min(cols, len(tiles)))
    lines = sheet_rows(its, cols, rows)
    order = [n for line in lines for n in line]  # the items in the order they're drawn
    spots = {}
    if fit:
        cws = [max(t.width, l + (it.img.width if it.img.height <= 22 else 0) + 8) for (it, t), l in zip(tiles, lws)]
        y = pad
        for line in lines:
            h, x = max(tiles[n][1].height for n in line), pad
            for n in line:
                spots[n] = (x, y, cws[n], h, lws[n])
                x += cws[n] + pad
            y += h + lab + pad
        size = (max(x + w + pad for x, _, w, _, _ in spots.values()), y)
    else:
        for r, line in enumerate(lines):
            for c, n in enumerate(line):
                spots[n] = (pad + c * (cw + pad), pad + r * (ch + lab + pad), cw, ch, lw)
        size = (pad + max(len(line) for line in lines) * (cw + pad), pad + len(lines) * (ch + lab + pad))
    widest = max(len(line) for line in lines)
    about = (f"{len(its)} frame{'s' * (len(its) != 1)} in " + (f"{len(lines)} rows of up to {widest}" if len(lines) > 1
                                                             else "one row"))
    if fit:
        about += " (--fit: each cell its own frame's size)"
    else:
        about += ", every cell " + cell_size(its, tiles, cw, ch, scale)
    about += (f", at --scale {scale}" if fit else "") + (" (--rows group: a row per animation group)" if rows == "group"
                                                          else "")
    tiles, spots = [tiles[n] for n in order], [spots[n] for n in order]
    s = Image.new("RGBA", size, (30, 30, 36, 255))
    d = ImageDraw.Draw(s)
    for (it, big), (x, y, cw, ch, lw) in zip(tiles, spots):
        d.rectangle([x, y, x + cw - 1, y + ch - 1], fill=rgba(bg if bg is not None else CELL_BG))
        at = (x + (cw - big.width) // 2, y + ch - big.height)
        if bg is None:  # no --bg: a checkerboard behind the frame itself, a square per pixel (4 px at least)
            fw, fh = shown[id(it)].width * scale, shown[id(it)].height * scale
            s.alpha_composite(checker(fw, fh, scale * max(1, -(-4 // scale))), (at[0] + ruled, at[1] + ruled))
        s.alpha_composite(big, at)
        if it.img.height <= lab - 4 and it.img.width <= cw - lw - 6:
            s.alpha_composite(it.img, (x + cw - it.img.width - 2, y + ch + 4))  # 1x beside the label
        d.text((x, y + ch + 2), it.label, fill=(220, 220, 220, 255))
        d.text((x, y + ch + 13), f"{it.img.width}x{it.img.height} {n_colors(it, bg)}c", fill=(150, 150, 160, 255))
    save_image(s, out, what if out is not None else "the sheet (no -o)", about=about,
               smaller="a lower --scale, fewer frames, or other --cols makes it smaller")
    return out


def cell_size(its, tiles, cw, ch, scale):
    """The dry run's 'every cell WxH: ...': the largest frame at --scale (and with its rulers), and what made the cell
    bigger than it: a label wider than every frame, or a wider or taller frame."""
    big, tile = max(tiles, key=lambda t: t[0].img.width * t[0].img.height)
    one = len(its) == 1
    said = f"{cw}x{ch}: {'frame' if one else 'the largest frame'} {big.img.width * scale}x{big.img.height * scale} " \
        f"at x{scale}" + (f", {tile.width}x{tile.height} with its rulers" if tile.size != (big.img.width * scale,
                                                                                            big.img.height * scale) else "")
    if cw > max(t.width for _, t in tiles):
        said += f", widened to fit {'its label' if one else 'the widest label'}"
    elif cw > tile.width:
        said += ", widened to fit the widest frame"
    if ch > tile.height:
        said += ", as tall as the tallest frame"
    return said


def n_colors(it, bg):
    """The sheet label's color count. A PNG (a scene rendered with this --bg) whose four corners are exactly the
    --bg color doesn't count that color: it's the backdrop, not the art's."""
    cs = colors(it.img)
    if bg is None:  # the checkerboard: no backdrop color a PNG could have been rendered on
        return len(cs)
    bg = rgba(bg)
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
    """Frames ordered so each animation group (of each file) is contiguous (first-appearance order)."""
    order = {}
    for it in its:
        order.setdefault((id(it.doc), it.frame.group if it.frame else ""), len(order))
    return sorted(its, key=lambda it: order[(id(it.doc), it.frame.group if it.frame else "")])


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
    @palette lines are re-pointed from there (repoint). doc.dest (palette -o) stands in for doc.path. A dry run
    (palette --dry-run) prints the diff it would make and writes nothing."""
    path = pathlib.Path(path or doc.dest or doc.path)
    repoint(doc, path)
    if doc.before is not None:  # an edit of several frames says which: FILE with no :SEL is every frame
        touched = [doc.label(f) for f in doc.frames if id(f) in doc.before and f.grid != doc.before[id(f)]]
        if len(touched) > 1:
            print(f"edited {len(touched)} frames: {listed(touched, 7 if len(touched) <= 8 else 3)}")
    text, had = doc.text(), None
    try:
        with open(path, newline="") as fh:
            had = fh.read()
    except (OSError, ValueError):  # missing, or not text
        pass
    if had == text:
        return f"no change: {path}"
    if DRY["run"]:  # a new OUT (palette -o) is shown against the FILE it copies
        base, name = (had, path) if had is not None or not doc.path or not doc.path.exists() else \
            (doc.path.read_text(), doc.path)
        for line in difflib.unified_diff((base or "").splitlines(), text.splitlines(),
                                         str(name) if base is not None else "/dev/null", str(path), lineterm="", n=0):
            print(line)
        return f"would write {path}"
    return f"wrote {doc.save(path)}"


def edit_target(arg, out, label="FILE", coords=None):
    """The shared edit path: (doc, selected frames, where to write). -o gets the whole file with the selection
    edited, never just the selection (that's extract). coords names the pixel coordinates the command was given
    ('x,y', '--region'): on a file of several frames they need FILE:SEL to say which frames they go to, FILE:* for
    all."""
    path, sel = split_sel(arg)
    with reading(f"{label} ({arg})"):
        doc = parse(path)
        if coords and not sel and len(doc.frames) > 1:
            ids = [doc.label(f) for f in doc.frames]
            group = next((f.group for f in doc.frames if f.group), None)
            fail("E_SELECT", f"pixel coordinates ({coords}) need you to say which frames they go to: {path} has "
                 f"{len(ids)} frames: {', '.join(ids)}; {path}:{ids[0]} (a frame)"
                 + (f", {path}:{group} (a group)" if group else "") + f", or '{path}:*' (every frame; quoted, "
                 "or the shell expands the *)", path=path)
        frames = doc.select(sel)
    out = pathlib.Path(out) if out else doc.path
    if sel and sel != "*" and out.resolve() != doc.path.resolve():
        print(f"note: {out} gets all of {doc.path} with {sel} edited; for only those frames use "
              f"'pxart extract {doc.path}:{sel} -o {out}'")
    doc.before = {id(f): list(f.grid) for f in doc.frames}
    return doc, frames, out


def clashes(dst_doc, src_doc, keys, clear=False):
    """The keys src uses (those that draw, Doc.blanks; every one with clear, when a whole grid is copied, not stamped) that
    dst_doc has in other colors, sorted."""
    src_pal, have, blank = src_doc.resolved(), dst_doc.resolved(), src_doc.blanks()
    return [k for k in sorted(keys) if k != "." and (clear or k not in blank) and k in have and have[k] != src_pal[k]]


def new_keys(bad, src_pal, have, taken, fits=None, given=None, looks=None):
    """Where src's clashing keys can go, chosen once for the whole command: a key dst already has in the same color (and
    src hasn't; and fits(k, it), when given: the same colors in dst's variants too), else the key an earlier source of
    the same command was given for a color that looks the same in every variant (given {looks(k): key}, which it adds
    to; looks(k): k's base color and its colors in dst's variants), else the first free key in FREE_ORDER (shell-safe
    first) that isn't in `taken`, which it adds to, so no two suggestions collide. {key: new key}, or None when there
    aren't enough free keys."""
    moves = {}
    for k in bad:
        same = next((c for c, v in have.items() if v == src_pal[k] and c != "." and c not in src_pal
                     and c not in moves.values() and (fits is None or fits(k, c))), None)
        if same is None and given is not None:
            same = given.get(looks(k))
            same = same if same not in src_pal and same not in moves.values() else None
        pick = same or next((c for c in FREE_ORDER if c not in taken and c not in have and c not in src_pal), None)
        if pick is None:
            return None
        moves[k] = pick
        taken.add(pick)
        if given is not None:
            given.setdefault(looks(k), pick)
    return moves


def conflict_issue(bad, src_doc, have, what, dst_name, redo, moves, whose=None, copy=None, whys=None):
    """One E_KEY_CONFLICT naming every clashing key of src, both colors (and whose dst's is: whose, key -> label), and
    two fixes that keep both colors and leave src as it is: `redo` --rekey, which gives src's keys `moves` in dst only,
    or recolor 'k>K' into `copy` (a path under dst's directory) and `redo` from that. A copy that is src itself (it
    already is one) is recolored in place. moves may hold more than the clashing keys, those --rekey moves for another
    reason (whys, as compose's: a key whose variants clash, a needed key OUT would leave out): named with why."""
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
        more = [k for k in moves if k not in bad]
        why = ""
        if more:
            var = [k for k in more if (whys or {}).get(k, ("",))[0] == "variant"]
            need = [k for k in more if k not in var]
            why = "".join(
                ([f"; {' '.join(var)}: {dst_name}'s base color but other variant colors"] if var else [])
                + ([f"; {' '.join(need)}: unused here, but {src_doc.path.name} needs "
                    f"{'them' if len(need) > 1 else 'it'}"] if need else []))
        fix = (f"; to keep both colors (no pixel changes color), add --rekey: {redo} then gives {whose_keys} keys "
               f"free ones in {dst_name} ({mv}{why})" + (
                   f" ({src_doc.made})" if getattr(src_doc, "made", None) else  # no file of its own to recolor
                   f" and leaves {src} as it is. Or " + (
                       f"give them those keys in {src} itself: {recipe}" if same else
                       f"give them those keys in a copy and {REDO_FROM.get(redo, redo)} from that: {recipe}")))
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


def key_conflicts(dst_doc, src_doc, keys, what, dst_name, redo, clear=False, dst_path=None, vmap=None):
    """One source's clashes with dst as an E_KEY_CONFLICT Issue (conflict_issue), or None when there are none. The
    free keys it suggests are the ones --rekey gives (rekey_moves)."""
    bad = clashes(dst_doc, src_doc, keys, clear)
    if not bad:
        return None
    have = dst_doc.resolved()
    moves = new_keys(bad, src_doc.resolved(), have, set(have) | set(src_doc.resolved()),
                     fits_in(dst_doc, src_doc, vmap))
    return conflict_issue(bad, src_doc, have, what, dst_name, redo, moves,
                          copy=rekey_copy(src_doc.path, dst_path or dst_name))


def colors_in(d, k, names, vmap=None):
    """Key k in each of OUT's variants `names`, as d's file draws it: in its variant by that name (or the one
    --variant-map reads as it), else in its base color, since a file without that variant stays at base colors in
    it."""
    lv = layer_variants(d, vmap or {})
    return [d.resolved(lv[n])[k] if n in lv else d.resolved()[k] for n in names]


def vclashes(dst, src, keys, vmap=None, clear=False):
    """The keys src uses that dst has in the same base color (no E_KEY_CONFLICT) but that dst's variants color
    otherwise than src's file does (colors_in): src's pixels would take dst's variant colors, one pack recoloring
    another. Sorted; none when dst has no variants."""
    names = variant_names(dst)
    if not names:
        return []
    have, pal, blank = dst.resolved(), src.resolved(), src.blanks()
    looks = {n: dst.resolved(n) for n in names}
    return [k for k in sorted(keys) if k != "." and (clear or k not in blank) and have.get(k) == pal[k]
            and colors_in(src, k, names, vmap) != [looks[n][k] for n in names]]


def fits_in(dst, src, vmap=None):
    """new_keys' test for reusing dst's key c for src's key k: c looks like k in every variant of dst too."""
    names = variant_names(dst)
    looks = {n: dst.resolved(n) for n in names}
    return lambda k, c: colors_in(src, k, names, vmap) == [looks[n][c] for n in names]


def import_keys(dst, src, keys, vmap=None, clear=False):
    """The keys src uses that dst hasn't got join dst's palette (those that draw, Doc.blanks; every one with clear, when whole grids
    are copied), each colored in dst's variants as src's file colors it: its variant by that name (or the one
    --variant-map reads as it) gets a line when it recolors the key or lists it (a lamp kept lit). A variant src's
    file hasn't got leaves the key at its base color. Returns the keys added, sorted."""
    names, pal, added, blank = variant_names(dst), src.resolved(), [], src.blanks()
    lv = layer_variants(src, vmap or {})
    for k in sorted(keys):
        if k == "." or k in dst.resolved() or not (clear or k not in blank):
            continue
        dst.add_key(k, pal[k])
        added.append(k)
        for n in names:
            if n not in lv:
                continue
            c = src.resolved(lv[n])[k]
            if c != pal[k] or k in src.variants.get(lv[n], {}) or k in src.shared_variants.get(lv[n], {}):
                dst.variants.setdefault(n, {})[k] = c
    return added


def check_vmap(vmap, dst, dst_name, srcs, fresh=False):
    """--variant-map's names must be there: each V1, V2 in some source file, and (for a DST that exists, whose
    variants stay its own) each NAME one of DST's variants."""
    have = sorted({n for d in srcs for n in variant_names(d)})
    for name, ns in vmap.items():
        missing = [n for n in ns[1:] if n not in have]
        if missing:
            fail("E_SELECT", f"--variant-map {name}={','.join(ns[1:])}: no source file has @variant "
                 f"{', '.join(map(repr, missing))} (they have: {', '.join(have) or 'none'})"
                 + (guess(missing[0], have) if len(missing) == 1 else ""))
        if not fresh and name not in variant_names(dst):
            fail("E_SELECT", f"--variant-map {name}={','.join(ns[1:])}: {dst_name} has no @variant {name!r} (it has: "
                 f"{', '.join(variant_names(dst)) or 'none'}); the map reads the sources' variants as DST's own"
                 + guess(name, variant_names(dst)))


def said_vclash(label, d, ks, dst, opath, vmap, rekey_said, asked=None):
    """One WARNING per key of d's file (label: which input) that dst has in its base color but other variant colors
    (vclashes): dst's variants would color those pixels dst's way, not d's file's (a scarf taking an awning's dusk).
    Each names its colors both ways, and --rekey KEY, which gives it a key of its own; asked {key: the key --rekey
    KEY=DSTKEY moved it from}: that key is where --rekey was told to put it, and the WARNING says so."""
    names = variant_names(dst)
    looks = {n: dst.resolved(n) for n in names}
    lines = []
    for k in ks:
        base, mine = d.resolved()[k], colors_in(d, k, names, vmap)
        each = ", ".join(f"{n} {fmt_color(looks[n][k])} ({d.path.name}: {fmt_color(c)})"
                         for n, c in zip(names, mine) if c != looks[n][k])
        if asked and k in asked:
            lines.append(f"WARNING: --rekey {asked[k]}={k}: {label}'s {asked[k]!r} {fmt_color(base)} is {opath}'s "
                         f"{k!r}, which {opath}'s variants color otherwise: {each}; those pixels take {opath}'s colors "
                         "there")
        else:
            lines.append(f"WARNING: {label} draws {k!r} {fmt_color(base)} in {opath}'s variant colors, not "
                         f"{d.path.name}'s: {each}; {rekey_said} {k} gives it a key of its own")
    return lines


def said_uncovered(label, d, dst, opath, vmap, added):
    """A note when d's file adds keys to an existing dst but has none of some of dst's variants (though it has variants
    of its own): those keys stay at base colors there, and --variant-map would read one of its variants as that one."""
    if not added or not variant_names(d):
        return None
    lv = layer_variants(d, vmap or {})
    lacks = [n for n in variant_names(dst) if n not in lv]
    if not lacks:
        return None
    theirs = variant_names(d)
    return (f"{d.path.name} has no @variant {' or '.join(lacks)} (it has {', '.join(theirs)}), so the keys "
            f"{label} adds to {opath} ({' '.join(added)}) stay at base colors in its {' and '.join(lacks)}; "
            f"--variant-map {lacks[0]}={theirs[0]} reads its {theirs[0]} as {lacks[0]}")


def rekey_moves(dst, src, keys, vmap=None, clear=False):
    """--rekey for one source going into an existing dst (frames --copy-to, paste): where the keys that clash go, those
    of another color and those dst's variants color otherwise (vclashes), each to a key dst has that looks the same in
    every variant, else a free one. {} when nothing clashes, None when free keys run out."""
    bad = sorted(set(clashes(dst, src, keys, clear)) | set(vclashes(dst, src, keys, vmap, clear)))
    if not bad:
        return {}
    have = dst.resolved()
    return new_keys(bad, src.resolved(), have, set(have) | set(src.resolved()), fits_in(dst, src, vmap))


def rekey(doc, moves, frames=()):
    """--rekey: doc's keys move in memory only (doc is never saved): each k's pixels become v in every frame (and in
    `frames`, copies such as a mirrored layer), and k's palette and variant lines become v's (rename_key)."""
    for f in {id(f): f for f in list(doc.frames) + list(frames)}.values():
        f.grid = ["".join(moves.get(c, c) for c in r) for r in f.grid]
    for k, v in moves.items():
        rename_key(doc, k, v)


def said_rekey(src, dst, moves, asked=()):
    """What --rekey moved: 'k>j' each; asked, the keys --rekey KEY=DSTKEY named (not free ones)."""
    free = [k for k in moves if k not in asked]
    return (f"note: --rekey gives {src}'s keys {'free ones' if not asked else 'other ones'} in {dst}: "
            + " ".join(shlex.quote(f"{k}>{v}") for k, v in moves.items()) + f" ({src} is unchanged)"
            + (f"; {' '.join(k for k in moves if k in asked)} as --rekey named, {' '.join(free) or 'none'} free"
               if asked else ""))


REKEY_KEY = r"[^\s#@.\"\\,=]"
REKEY_ONE = rf"([^\s,]+\.px:)?{REKEY_KEY}(={REKEY_KEY})?"  # k, k=j, or FILE.px:k=j (that layer file's k only)
REKEY_RE = re.compile(rf"^{REKEY_ONE}(,{REKEY_ONE})*$")
RECT_ARG_RE = re.compile(r"^-?\d+(,-?\d+){3}$")  # crop's x,y,w,h after --rekey is the rectangle, not keys
SCOPED_RE = re.compile(r"^(?P<file>[^\s,]+\.px):(?P<k>\S)(?:=(?P<j>\S))?$")


def rekey_spec(value):
    """--rekey's argument: None when not given; else (only, asked, scoped): only, the keys it may give free keys (None:
    every key that needs one, bare --rekey), asked {key: the key it goes to}, from KEY=DSTKEY, and scoped {FILE.px as
    typed: (only, asked)} for the entries FILE.px:KEY[=DSTKEY], which touch that source file's KEY alone. A list names
    every key --rekey touches: 'o,r' moves only o and r, 'k=j,n' puts k on j and gives n a free key, and
    'girl.px:T=V' puts girl.px's T on V and leaves the other files' T alone."""
    if value is None:
        return None
    if value == "":
        return None, {}, {}
    only, asked, scoped = set(), {}, {}
    for t in value.split(","):
        got = SCOPED_RE.match(t)
        k, eq, j = (got["k"], got["j"] is not None, got["j"]) if got else t.partition("=")
        if len(k) != 1 or k not in KEYS or (eq and (len(j) != 1 or j not in KEYS)):
            fail("E_BAD_ARG", f"--rekey {value!r}: want keys, comma-separated (--rekey o,r: only those get free keys), "
                 "or KEY=DSTKEY (--rekey k=j: k's pixels take DST's key j), each for every source file or for one "
                 "(girl.px:T=V); bare --rekey moves every key that needs it")
        mine_only, mine_asked = scoped.setdefault(got["file"], (set(), {})) if got else (only, asked)
        if k in mine_only or k in mine_asked:
            fail("E_BAD_ARG", f"--rekey {value!r} names {(got['file'] + ':') if got else ''}{k!r} twice")
        if eq:
            mine_asked[k] = j
        else:
            mine_only.add(k)
    for o, a_ in [(only, asked)] + list(scoped.values()):
        both = sorted(set(a_.values()) & o)
        if both:
            fail("E_BAD_ARG", f"--rekey {value!r}: {' '.join(both)} is where --rekey puts another key; it can't also "
                 "get a free key")
    return only, asked, scoped


def scoped_to(scoped, paths, value):
    """--rekey FILE.px:KEY entries by the source file each names: {resolved path: (only, asked)}. FILE.px is a path
    (from here) or, when only one source file has that name, its name. One that names no source is E_SELECT."""
    out = {}
    for name, spec in scoped.items():
        path = pathlib.Path(name).resolve()
        hit = [p for p in paths if p == path] or [p for p in paths if p.name == pathlib.Path(name).name]
        if len(hit) != 1:
            fail("E_SELECT", f"--rekey {value}: {name} is " + ("the name of several source files; give its path"
                                                             if hit else "no source file here") + " (they are: "
                 + ", ".join(sorted(dict.fromkeys(os.path.relpath(p) for p in paths))) + ")")
        o, a_ = out.setdefault(hit[0], (set(), {}))
        o |= spec[0]
        a_.update(spec[1])
    return out


def check_asked(asked, src, dst, dst_name, what):
    """--rekey KEY=DSTKEY for one source file: the key must be one src's pixels use (checked by the caller), and
    DSTKEY a key src hasn't got (other than KEY itself), in KEY's base color when dst has it."""
    pal, have = src.resolved(), dst.resolved() if dst is not None else {}
    for k, j in asked.items():
        if j != k and j in pal:
            fail("E_KEY_CONFLICT", f"--rekey {k}={j}: {what} has a key {j!r} of its own ({fmt_color(pal[j])}); name a "
                 f"key it hasn't got")
        if j in have and have[j] != pal[k]:
            fail("E_KEY_CONFLICT", f"--rekey {k}={j}: {dst_name}'s {j!r} is {fmt_color(have[j])}, and {what}'s {k!r} "
                 f"{fmt_color(pal[k])}: its pixels would change color. Name a key {dst_name} has in "
                 f"{fmt_color(pal[k])}, or give {k} a free one: --rekey {k}")


def rekey_one(value, dst, src, keys, vmap, clear, dst_name, what, frames=()):
    """--rekey [KEYS | KEY=DSTKEY,...] for one source going into an existing dst (frames --copy-to, paste): the named
    keys go where they were told, then the keys that need free ones (rekey_moves; with a list, only those it names)
    get them; src moves in memory (rekey). Prints what moved and, for a key it moved to a free one while dst has its
    base color under a key whose variants differ, how to use that key anyway. Returns ({old: new}, {new: old} of the
    asked moves)."""
    spec = rekey_spec(value)
    if spec is None:
        return {}, {}
    only, asked, scoped = spec
    for o, a_ in scoped_to(scoped, [src.path.resolve()], value).values():  # the one source: its own entries win
        only, asked = (only - set(a_)) | o, {**{k: j for k, j in asked.items() if k not in o}, **a_}
    unused = [k for k in sorted((only or set()) | set(asked)) if k not in keys]
    if unused:
        fail("E_SELECT", f"--rekey {value}: {what} doesn't draw with {' '.join(unused)}")
    check_asked(asked, src, dst, dst_name, what)
    moves = {k: j for k, j in asked.items() if j != k}
    if moves:
        rekey(src, moves, frames)
        keys = {moves.get(k, k) for k in keys}
    auto = rekey_moves(dst, src, keys - set(asked.values()), vmap, clear) or {}
    if only is not None:
        needless = sorted(only - set(auto))
        auto = {k: v for k, v in auto.items() if k in only}
        if needless:
            print(f"note: --rekey {' '.join(needless)}: {'they need' if len(needless) > 1 else 'it needs'} no other "
                  f"key; {dst_name} has {'them' if len(needless) > 1 else 'it'} in the same colors")
    if auto:
        rekey(src, auto, frames)
    back = {v: k for k, v in moves.items()}
    done = {back.get(k, k): v for k, v in list(moves.items()) + list(auto.items())}
    if done:
        print(said_rekey(src.path, dst_name, done, set(asked)))
        hint = same_base_hint({back.get(k, k): v for k, v in auto.items()}, asked, src, dst, dst_name)
        if hint:
            print(hint)
    return done, {j: k for k, j in asked.items()}


def same_base_hint(auto, asked, src, dst, dst_name):
    """For keys --rekey gave free ones (auto {old: new}) though dst has their base color under a key whose variants
    differ (so it wasn't reused): a note naming those keys and the --rekey list that uses them anyway, the other keys
    it moved kept as they went (asked KEY=DSTKEY, the rest by name). None when there are none."""
    have, pal = dst.resolved(), src.resolved()
    same = {}
    for k, v in auto.items():
        c = next((c for c, col in have.items() if c not in (".", k) and col == pal.get(v) and c not in pal), None)
        if c:
            same[k] = c
    if not same:
        return None
    arg = [f"{k}={j}" for k, j in asked.items()] + [f"{k}={same[k]}" if k in same else k for k in auto]
    return (f"note: {dst_name} has the base colors of {' '.join(same)} as {' '.join(same.values())}, in other variant "
            f"colors; --rekey {','.join(arg)} uses those anyway (a warning then says which variant colors "
            "change)")


def spans(ns):
    """[1, 2, 3, 5] -> '1-3, 5'."""
    out = []
    for n in ns:
        if out and out[-1][1] == n - 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in out)


def stamp(dst_doc, dst, src_doc, src, at, region=None, under=False, what="SRC", redo="paste", out=None, vmap=None):
    """Copy src frame (or a region of it) onto dst frame at `at`; keys that draw nothing (Doc.blanks) don't overwrite, but
    a key transparent only in the base does (a night halo). under: only onto dst's empty pixels (by the same test), so
    src goes behind what dst has. Returns the keys it added (import_keys)."""
    src_blank = src_doc.blanks()
    clash = key_conflicts(dst_doc, src_doc, set("".join(src.grid)), what, out or dst_doc.path, redo)
    if clash:
        raise PxError(clash)
    added = import_keys(dst_doc, src_doc, set("".join(src.grid)), vmap)  # sorted: one order every run
    x0, y0, w, h = parse_rect(region, src.size)
    W, H = dst.size
    g = [list(r) for r in dst.grid]
    dst_blank = dst_doc.blanks()
    for y in range(h):
        for x in range(w):
            if not (0 <= y0 + y < src.size[1] and 0 <= x0 + x < src.size[0]):
                continue
            ch = src.grid[y0 + y][x0 + x]
            tx, ty = at[0] + x, at[1] + y
            if ch not in src_blank and 0 <= tx < W and 0 <= ty < H and not (under and g[ty][tx] not in dst_blank):
                g[ty][tx] = ch
    dst.grid = ["".join(r) for r in g]
    return added


# ---------------------------------------------------------------------------- commands

def need_o(a, eg):
    """sheet, onion and scene write -o OUT, which only --dry-run (the readout and sizes alone) goes without."""
    if a.o is None and not DRY["run"]:
        fail("E_BAD_ARG", f"-o is required: -o {eg} (or --dry-run to print the readout and write nothing)")


def cmd_render(a):
    its = all_items(a.files, a.variant)
    for f in a.files if a.png is not None else ():
        path, sel = split_sel(f)
        n = len(parse(path).frames) if path.endswith(".px") else 0
        if sel or n != 1:
            why = "a selection" if sel else "a PNG" if not path.endswith(".px") else f"{n} frames"
            print(f"note: --png skips {f}: {why}; --png writes a single-frame .px at 1x ('render --plain FILE:ID -o "
                  "x.png' writes one frame, 'export --frames DIR' every frame)")
            continue
        doc = parse(path)
        out = (pathlib.Path(a.png) if a.png else pathlib.Path(path).parent) / (pathlib.Path(path).stem + ".png")
        save_image(doc.image(doc.frames[0], a.variant), out, "--png", about=f"{path} at 1x")
        print(f"{'would write' if DRY['run'] else 'wrote'} {out.as_posix()} (--png: {path} at 1x)")
    if a.plain:
        if len(its) != 1:
            fail("E_BAD_ARG", f"--plain writes one frame alone, and {' '.join(a.files)} "
                 f"{'is' if len(a.files) == 1 else 'are'} {len(its)} frames: pick one (FILE:ID), or 'export --frames DIR' "
                 "writes each frame at 1x")
        img = its[0].img
        if a.bg is not None:
            img = on_bg(img, img.width, img.height, parse_color(a.bg, "--bg"))
        s = a.scale or 1
        print(wrote(save_image(img.resize((img.width * s, img.height * s), Image.NEAREST), a.o,
                               about=f"{its[0].label} alone, {img.width}x{img.height} at --scale {s}",
                               smaller="a lower --scale makes it smaller")))
        return
    bg = parse_color(a.bg, "--bg") if a.bg else None
    print(wrote(sheet(its, a.o, a.scale or 8, bg=bg, grid=not a.no_grid, rulers=not a.no_grid)))


def cmd_sheet(a):
    a.bg = parse_color(a.bg, "--bg") if a.bg else None
    files = frames_only(in_dirs(a.files, exclude=a.exclude or ()), "sheet")
    need_o(a, "sheet.png")
    its = all_items(files, a.variant)
    note = outsized(its, a.fit)
    if note:
        print(note)
    print(wrote(sheet(its, a.o, a.scale, a.cols, a.bg, grid=a.grid, fit=a.fit, align=a.align, rows=a.rows)))


OUTSIZED = 8  # sheet notes a frame over this many times the median frame's area


def outsized(its, fit):
    """sheet's note for frames much bigger than the rest (over OUTSIZED times the median frame's area, among three or
    more): with --fit each sets its row's height, and without it every cell's size. None when there are none."""
    areas = sorted(it.img.width * it.img.height for it in its)
    if len(areas) < 3:
        return None
    n = len(areas)
    mid = areas[n // 2] if n % 2 else (areas[n // 2 - 1] + areas[n // 2]) / 2
    big = [it for it in its if it.img.width * it.img.height > OUTSIZED * mid]
    if not big:
        return None
    many = len(big) > 1
    top = max(big, key=lambda it: it.img.width * it.img.height)
    cost = (f"make{'' if many else 's'} its row {max(it.img.height for it in big)} px tall" if fit else
            f"make{'' if many else 's'} every cell {top.img.width}x{top.img.height} (--fit sizes each cell to its frame)")
    def home(it):
        return it.doc.path.resolve() if it.doc else id(it)
    shared = {home(it) for it in its if it not in big} & {home(it) for it in big}
    names = sorted({it.doc.path.name for it in big if it.doc})
    leave = ("pick the other frames with FILE:SEL" if shared else
             f"--exclude {' --exclude '.join(names)}" if names and len(names) == len({home(it) for it in big}) else
             f"--exclude {'their files' if many else 'its file'}")
    return (f"note: {listed([f'{it.label} ({it.img.width}x{it.img.height})' for it in big], 5)} "
            f"{'are' if many else 'is'} over {OUTSIZED}x the median frame's area ({mid:g} px) and {cost}: {leave}, "
            f"or give {'them a sheet of their' if many else 'it a sheet of its'} own")


def cmd_anim(a):
    """GIF + strip, and one line of numbers per frame; without -o only the numbers (nothing is written). A FILE or
    FILE:SEL over several groups (a walk's four directions) animates each group on its own, with a block of numbers
    each: -o then names one GIF only for one group, else a DIR that gets one per group (DIR/walk/down.gif)."""
    per, paths = [], []  # each FILE's items, as all_items reads them
    for n, arg in enumerate(a.files, 1):
        with reading(f"file {n} ({arg})"):
            per.append(items(arg, a.variant))
        paths += [split_sel(arg)[0]] * len(per[-1])
    tell_apart([it for got in per for it in got], paths)
    blocks = []  # [[name, items, joined]]: a FILE over several groups gives one per group; the others play as one
    spread = False  # a FILE spanned several groups (-o is then a DIR, even when only one of them animates)
    for arg, got in zip(a.files, per):
        groups = {}
        for it in got:
            groups.setdefault(it.frame.group if it.frame else "", []).append(it)
        rest, skipped = [g for g, fs in groups.items() if not (fs[0].doc and not fs[0].doc.animated(g))], False
        if len(groups) > 1 and rest and len(rest) < len(groups):  # top-level frames and @still groups beside
            skip = [g for g in groups if g not in rest]               # animations aren't animations: left out
            what = [listed([it.label for it in groups[""]]) + (" (top-level frames)" if len(groups[""]) > 1 else
                                                                 " (a top-level frame)")] if "" in skip else []
            what += [f"{g} (@still)" for g in skip if g]
            print(f"note: {split_variant(arg)[0]}: skipping what isn't an animation: {listed(what)}")
            got = [it for g in rest for it in groups[g]]
            groups, skipped = {g: groups[g] for g in rest}, True
        if len(groups) == 1 and not (skipped and a.o and pathlib.Path(a.o).suffix.lower() != ".gif"):
            if blocks and blocks[-1][2]:
                blocks[-1][0] += " " + arg
                blocks[-1][1].extend(got)
            else:
                blocks.append([arg, list(got), True])
            continue
        path = split_sel(arg)[0]
        names = [g or "(top level)" for g in groups]
        spread = True
        if len(groups) > 1:
            print(f"note: {split_variant(arg)[0]} is {len(groups)} groups: {listed(names)}; animating each on its own; "
                  f"pick one with {path}:{next(g for g in groups if g)}")
        blocks += [[f"{path}:{g}" if g else f"{path} (top level)", fs, False] for g, fs in groups.items()]
    gif = a.o and pathlib.Path(a.o).suffix.lower() == ".gif"
    if len(blocks) == 1 and not (spread and a.o and not gif):
        if a.o and not gif:
            fail("E_BAD_ARG", f"-o {a.o}: anim writes a GIF (and its strip beside it, as .strip.png); name it .gif")
        return animate(a, blocks[0][1], a.o)
    if gif:
        fail("E_BAD_ARG", f"-o {a.o} is one GIF, and these are {len(blocks)} animations: "
             f"{listed([n for n, *_ in blocks])}; pick one group, or give -o a DIR for one GIF per group")
    outs = [anim_path(a.o, fs) if a.o else None for _, fs, _ in blocks]
    clash = next((o for o in outs if o and outs.count(o) > 1), None)
    if clash:
        fail("E_BAD_ARG", f"-o {a.o}: two animations would be written to {clash}; animate them apart")
    for (name, got, _), out in zip(blocks, outs):
        print(name)
        animate(a, got, out)


def plays_once(its):
    """Whether the one group all of its frames are in has repeat=1: it plays through once, so the last frame never
    loops back to the first. repeat=0 loops; repeat=2 and up play the wrap-around between passes."""
    keys = {(id(it.doc), it.frame.group) if it.doc is not None and it.frame is not None else None for it in its}
    if len(keys) != 1 or None in keys:
        return False
    return its[0].doc.anims.get(its[0].frame.group, {}).get("repeat") == 1


def anim_path(d, its):
    """Where anim -o DIR writes one group's GIF: DIR/walk/down.gif, or DIR/<file stem>.gif for top-level frames."""
    first = its[0]
    stem = first.frame.group if first.frame and first.frame.group else \
        (first.doc.stem if first.doc else pathlib.Path(first.label).stem)
    return str(pathlib.Path(d) / f"{stem}.gif")


def animate(a, its, out):
    """One animation: its numbers, and with out (a .gif) its GIF and strip."""
    frames = [it.img for it in its]
    durs = [1000 // a.fps if a.fps else it.ms for it in its]
    lay = pivot_layout(its)  # pivots, when the file has them, line up; else frames are bottom-centered
    w, h = lay[:2] if lay else (max(f.width for f in frames), max(f.height for f in frames))

    def fit(i, bg="#3a3a44"):
        return placed(frames[i], w, h, lay[2][i], bg) if lay else on_bg(frames[i], w, h, bg)
    framed = [fit(i) for i in range(len(frames))]
    S, gap = a.scale, 8
    if out or DRY["run"]:  # a dry run with no -o still tells the GIF's size
        gif = []
        for f in framed:
            canvas = Image.new("RGBA", (w * S + gap * 3 + w * 3, max(h * S, h * 3 + gap)), (30, 30, 36, 255))
            canvas.alpha_composite(f.resize((w * S, h * S), Image.NEAREST), (0, 0))
            canvas.alpha_composite(f, (w * S + gap, 0))                                        # 1x
            canvas.alpha_composite(f.resize((w * 2, h * 2), Image.NEAREST), (w * S + gap * 2 + w, 0))  # 2x
            gif.append(canvas.convert("P", palette=Image.ADAPTIVE))
        save_image(gif[0], out, "-o" if out else "the GIF (no -o)", save_all=True, append_images=gif[1:],
                   duration=durs, loop=0, disposal=2, smaller="a lower --scale makes it smaller",
                   about=f"{len(gif)} frame{'s' * (len(gif) != 1)} of a {w}x{h} canvas at --scale {S}, its 1x and 2x "
                         f"copies beside it, {sum(durs)} ms a loop")
    # Compare on a shared canvas, placed as drawn, so frames of different sizes diff too.
    clear = [fit(i, "#00000000") for i in range(len(frames))]
    pairs = [(clear[i - 1], clear[i], frames[i - 1].size == frames[i].size == (w, h) and may_wrap(clear[i - 1], clear[i]))
             for i in range(len(frames))]
    once = plays_once(its)  # repeat=1: the last frame never loops back to the first, so frame 0 has nothing to diff
    moves = [None if once and i == 0 else motion(p, c, wrap=t) for i, (p, c, t) in enumerate(pairs)]
    legs = still_rows(clear)
    if still_rows(clear, shape=True) is None:  # the legs move somewhere in the animation (a walk): a frame whose legs
        moves = [m and m[:4] + (None,) + m[5:] for m in moves]  # happen to stay put bobbed, and the shift says so
    elif legs is not None and any(m and m[4] is not None for m in moves):  # one frame showed the legs still; so does
        # every frame whose shift would light them
        moves = [motion(*pairs[i][:2], wrap=pairs[i][2], legs=legs) if m and m[4] is None and m[:2] != (0, 0)
                 and not m[5] else m for i, m in enumerate(moves)]
    cells = []  # per frame: (framed, what changed, its label, head, alt), for the strip
    for i, fr in enumerate(framed):
        prev, cur = pairs[i][:2]
        if moves[i] is None:
            head = "plays once (repeat=1); no wrap-around"
            print(f"  {its[i].label:24} {durs[i]:5}ms  {head}")
            cells.append((fr, diff_frame(cur, cur), f"{its[i].label} {durs[i]}ms", head, ""))
            continue
        dx, dy, n_shift, n_none, still, wrapped = moves[i]
        opaque = sum(cur.getchannel("A").histogram()[1:])

        def px(n, base):  # '72px (9%)': of the frame's opaque pixels, or when more changed (the frame before covered
            op = opaque   # pixels this one doesn't), of the pixels opaque in either: never over 100%
            if n > op:
                op = max(n, sum(ImageChops.lighter(base.getchannel("A"), cur.getchannel("A")).histogram()[1:]))
            return f"{n}px ({(200 * n + op) // (2 * op)}%)" if op else f"{n}px"
        if wrapped:
            base = rolled(prev, dx, dy); head = f"shift {dx:+d},{dy:+d} (wrap) then {px(n_shift, base)}"
            alt = f"(no shift: {n_none}px)"
        elif still is None:
            base = shifted(prev, dx, dy); head = f"shift {dx:+d},{dy:+d} then {px(n_shift, base)}"
            alt = f"(no shift: {n_none}px)" if (dx, dy) != (0, 0) else ""
        else:
            base, head = prev, f"no shift then {px(n_none, prev)}"
            alt = f"(rows {still}+ still; shift {dx:+d},{dy:+d}: {n_shift}px)"
        print(f"  {its[i].label:24} {durs[i]:5}ms  vs {its[i - 1].label}: {head}" + (f" {alt}" if alt else ""))
        cells.append((fr, diff_frame(base, cur), f"{its[i].label} {durs[i]}ms", head, alt))
    if not out and not DRY["run"]:
        return
    # the strip: frames over what changed, each cell's labels wrapped to its width in a pixel font that draws the
    # readout's own words (its spaces and colons too), the label rows as tall as the most lines any cell needs
    pad, font = 8, strip_font()
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    wrap = [[fit_lines(probe, t, w * S, font) for t in c[2:]] for c in cells]
    n1, n2 = max(len(x[0]) for x in wrap), max(len(x[1]) + len(x[2]) for x in wrap)
    size = (pad + len(cells) * (w * S + pad), pad + 2 * (h * S + pad) + (n1 + n2) * LINE_H + 2)
    strip = Image.new("RGBA", size, (30, 30, 36, 255))
    d = ImageDraw.Draw(strip)
    for i, ((fr, changed, *_), (label, head, alt)) in enumerate(zip(cells, wrap)):
        x = pad + i * (w * S + pad)
        strip.alpha_composite(upscale(fr, S, grid=True), (x, pad))
        for j, line in enumerate(label):
            d.text((x, pad + h * S + 1 + j * LINE_H), line, font=font, fill=(220, 220, 220, 255))
        y2 = pad * 2 + h * S + n1 * LINE_H
        strip.alpha_composite(upscale(on_bg(changed, w, h, "#1e1e24"), S, grid=True), (x, y2))
        for j, (line, color) in enumerate([(l, (255, 120, 220, 255)) for l in head]
                                          + [(l, (200, 140, 190, 255)) for l in alt]):
            d.text((x, y2 + h * S + 1 + j * LINE_H), line, font=font, fill=color)
    sp = pathlib.Path(out).with_suffix(".strip.png") if out else None
    save_image(strip, sp, "the strip" if out else "the strip (no -o)", smaller="a lower --scale makes it smaller",
               about=f"{len(cells)} frame{'s' * (len(cells) != 1)} over what changed, at --scale {S}")
    print(wrote(out, sp))


def cmd_onion(a):
    need_o(a, "x.png")
    its = []
    for n, arg in (("A", a.a), ("B", a.b)):
        with reading(f"{n} ({arg})"):
            its.append(one_frame(arg, variant=a.variant))
        v = split_variant(arg)[1] or a.variant
        if v and its[-1].doc:  # the readout names the variant each frame is drawn in
            its[-1].label += f"%{v}"
            its[-1].variant = v
    ia, ib = its
    A, B = ia.img, ib.img
    lay = pivot_layout([ia, ib])
    w, h = lay[:2] if lay else (max(A.width, B.width), max(A.height, B.height))
    spots = lay[2] if lay else [((w - A.width) // 2, h - A.height), ((w - B.width) // 2, h - B.height)]
    band = onion_band(a, h)
    base = on_bg(Image.new("RGBA", (1, 1), CLEAR), w, h)
    if not a.fade_a:  # A as a flat silhouette in one color, at that color's alpha: where it shows past B is plain
        c = parse_color(a.tint_a or TINT_A, "--tint-a")
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
    save_image(upscale(base, a.scale, grid=True, rulers=True), a.o, "-o" if a.o else "the onion (no -o)",
               about=f"A and B on one {w}x{h} canvas at --scale {a.scale}, with the grid and rulers",
               smaller="a lower --scale makes it smaller")
    one = bool(split_sel(a.a)[0] == split_sel(a.b)[0] and ia.frame and ib.frame and ia.frame.group
               and ia.frame.group == ib.frame.group)  # frames of one animation: one sprite, whatever their sizes
    kin = True if one else None if A.size == B.size else False
    for line in alignment(ia, ib, w, h, spots, "lined up by pivot" if lay else "bottom-centered", band, kin,
                          feet=a.feet is not None):
        print(line)
    print(wrote(a.o))


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


def box_text(b):
    """A bounding box as every readout prints it, first and last pixel both included: (1, 0, 23, 21), PIL's
    exclusive getbbox(), is 'x 1..22, y 0..20'."""
    return f"x {b[0]}..{b[2] - 1}, y {b[1]}..{b[3] - 1}"


def spans_of(y0, y1):
    """'row 20' or 'rows 20-23'."""
    return f"row {y0}" if y0 == y1 else f"rows {y0}-{y1}"


def alignment(ia, ib, w, h, spots, how, band=None, kin=True, feet=False):
    """onion's readout: where each frame's opaque pixels sit on the shared canvas ('A (frame walk/0) covers x 3..20,
    y 1..31': its opaque bounding box), how B's edges moved from A's (a 1px
    jump of the feet is 'bottom +1'), and the whole-sprite shift that best explains B (anim's). band (y0, y1): only
    those canvas rows count, for the edges and the shift (band_shift), and the readout names the band as what it is
    (feet: --feet N's 'bottom N canvas rows', else --rows' 'canvas rows') and the rows each frame is opaque in there
    ('bottom 3 canvas rows 13-15; A opaque in 13-15, B in 14-15'). In a band whose bottom edges agree (the feet stayed)
    a best shift up or down only lines up what moved above them: the readout says no shift, and names that one as
    such. kin: True, frames of one animation (one sprite, however much changed); False, two different sprites (other
    sizes); None, it depends: more than half the larger one's opaque pixels still changed at the whole sprites' best
    shift (band or not) makes them two. Two different sprites get their edges only: a best shift between two
    characters means nothing."""
    clear = [placed(it.img, w, h, at, "#00000000") for it, at in zip((ia, ib), spots)]
    if band:
        alpha = [c.getchannel("A") for c in clear]
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rectangle([0, band[0], w - 1, band[1]], fill=255)
        boxes = [ImageChops.multiply(al, mask).getbbox() for al in alpha]
        n = band[1] - band[0] + 1
        name = (f"bottom {n} canvas {spans_of(*band)}" if feet else f"canvas {spans_of(*band)}")
        opaque = [(f"{b[1]}" if b[1] == b[3] - 1 else f"{b[1]}-{b[3] - 1}") if b else None for b in boxes]
        rows = name + ("; " + (f"opaque in {opaque[0]}" if opaque[0] == opaque[1] else
                               f"A opaque in {opaque[0]}, B in {opaque[1]}") if all(boxes) else "")
    else:
        boxes = [c.getchannel("A").getbbox() for c in clear]
    where = f"{spans_of(*band)} of the {w}x{h} canvas" if band else f"on the {w}x{h} canvas"
    lines = [f"{n} (frame {it.label}) " + (f"covers {box_text(b)}" if b else "is empty" + unseen(it, it.variant).replace(" (", ": ", 1)[:-1]
                                           if not band else "covers nothing" if n == "A" else
                                           f"covers nothing in {spans_of(*band)}")
             + (f" ({where}, {how})" if n == "A" else "")
             for n, it, b in zip("AB", (ia, ib), boxes)]
    if all(boxes):
        (l0, t0, r0, b0), (l1, t1, r1, b1) = boxes
        whole = motion(*clear)[:4]
        dx, dy, n_shift, n_none = band_shift(*clear, *band) if band else whole
        most = max(sum(c.getchannel("A").histogram()[1:]) for c in clear)  # the whole sprites, band or not
        edges = f"B vs A{f' ({rows})' if band else ''}: left {l1 - l0:+d}, right {r1 - r0:+d}, top {t1 - t0:+d}, " \
                f"bottom {b1 - b0:+d}"
        if kin is False or (kin is None and 2 * whole[2] > most):
            lines.append(f"{edges}; different sprites: edges only")
        elif band and b1 == b0 and dy:
            lines.append(f"{edges}; bottom edges agree, so no shift: {n_none}px changed (the band's best shift "
                         f"{dx:+d},{dy:+d} then {n_shift}px only lines up what moved above its bottom edge)")
        else:
            lines.append(f"{edges}; best shift {dx:+d},{dy:+d} then {n_shift}px changed (no shift: {n_none}px)")
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
                picks = None if q or ch == "#" else variant_list(rest)
                if picks:  # '1 sand.png sand2.png sand3.png': one per cell, by cell_hash (room, x, y)
                    legend[ch], where[ch] = tuple(str(path.parent / t) for t in picks), (n, picks)
                    continue
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


MAP_TOKEN_RE = re.compile(r"^.+\.(px(:[A-Za-z0-9_\-./]+)?|png)(%[A-Za-z0-9_\-]+)?(\+[hvb]{1,3})?(%[A-Za-z0-9_\-]+)?$")


def variant_list(rest):
    """A legend line's rest as a list of tiles ('sand.png sand2.png sand3.png', "quoted" ones too), when it is two or
    more tokens and every one names a .png or .px[:frame]; else None (one path, spaces and all)."""
    try:
        toks = shlex.split(rest)
    except ValueError:
        return None
    return toks if len(toks) > 1 and all(MAP_TOKEN_RE.match(t) for t in toks) else None


def legend_entries(legend, where):
    """[(char, item_arg, the path as written)], a variant list's tiles each in turn."""
    out = []
    for ch, arg in legend.items():
        written = where[ch][1]
        if isinstance(arg, tuple):
            out += [(ch, a, w) for a, w in zip(arg, written)]
        else:
            out.append((ch, arg, written))
    return out


def cell_hash(room, x, y):
    """The variant pick's hash of (room, x, y), unsigned 32-bit: FNV-1a over the room's name (UTF-8), xor'd with the
    beach kit's cell mix (sprites.js groundTilePath: x*73856093 ^ y*19349663, then two xorshift-multiplies). scene
    --map, compose --map and export --tiled all pick with it, so a render is what the compiled room ships."""
    m = 0xFFFFFFFF
    h = 2166136261
    for b in room.encode("utf-8"):
        h = ((h ^ b) * 16777619) & m
    h ^= ((x * 73856093) & m) ^ ((y * 19349663) & m)
    h = ((h ^ (h >> 13)) * 0x5bd1e995) & m
    return (h ^ (h >> 15)) & m


def pick_variant(arg, room, x, y):
    """A legend entry's tile for cell x,y of room: the entry, or one of a variant list's by cell_hash."""
    return arg[cell_hash(room, x, y) % len(arg)] if isinstance(arg, tuple) else arg


def map_room(path):
    """A map's room name, the hash's room: its file name without .map (rooms/point.map is 'point')."""
    return pathlib.Path(path).stem


def read_map(path, tile, notes=None):
    """Returns [(item_arg, x, y)] and the map size in px; '#' legend notes go to `notes`. A variant list's cell gets
    its pick (pick_variant)."""
    path = pathlib.Path(path)
    room = map_room(path)
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
            out.append((pick_variant(legend[ch], room, x, y), x * tile[0], y * tile[1]))
    width = max((len(r) for rows in layers for _, r in rows), default=0) * tile[0]
    return out, (width, max(len(rows) for rows in layers) * tile[1])


def load_legend(path, variant=None):
    """Load every legend entry as one frame: {item_arg: Item} (place_item's: its image, and for a .px its doc and
    frame, mirrored by +h/+v). A target that can't be loaded is an error at its legend line, naming the path as
    written."""
    legend, _, _, where = parse_map(path)
    imgs, failed = {}, []  # failed: (ch, line, as written, code, what went wrong, the line saying it for one entry)
    for ch, arg, written in legend_entries(legend, where):
        n = where[ch][0]
        try:
            imgs[arg] = place_item(arg, f"legend {ch!r}", variant, anchor=True)
        except PxError as e:
            for i in e.issues:
                msg = i.msg + (f" ({i.path}:{i.line})" if i.line else "")
                failed.append((ch, n, written, i.code, msg, f"legend {ch!r}: {written!r}: {msg}"))
        except OSError as e:
            failed.append((ch, n, written, "E_FILE", f"can't load (relative to the map file): {e.strerror or e}",
                           f"legend {ch!r}: can't load {written!r} (relative to the map file): {e.strerror or e}"))
    if failed:
        raise PxError(legend_issues(path, failed, variant, any(it.doc for it in imgs.values())))
    return imgs


def legend_issues(path, failed, variant, some_have):
    """load_legend's errors, one line per entry, except that entries failing alike share one line: a --variant no
    legend file has is one line naming the variants they do have (with how many entries have each), and any other
    message that repeats is one line naming its entries."""
    lack = re.compile(r"^unknown variant '.*' \(have: (.*?)\)(; did you mean '.*'\?)?$")
    issues = []
    if variant and not some_have and any(lack.match(f[4]) for f in failed):
        have = {}
        for f in failed:
            for v in lack.match(f[4]).group(1).split(", ") if lack.match(f[4]) else ():
                have[v] = have.get(v, 0) + (v != "none")
        have.pop("none", None)
        issues.append(Issue("E_SELECT", f"no legend file has @variant {variant!r}; " + (
            "the legend's variants: " + ", ".join(f"{v} ({c} entr{'y' if c == 1 else 'ies'})"
                                                  for v, c in sorted(have.items(), key=lambda vc: (-vc[1], vc[0])))
            if have else "its files have no variants"), str(path)))
        failed = [f for f in failed if not lack.match(f[4])]
    groups = {}  # a missing file is its own problem: entries of one file share a line
    for f in failed:
        groups.setdefault((f[3], f[4], split_sel(split_flip(f[2])[0])[0] if f[3] == "E_FILE" else None), []).append(f)
    for (code, msg, _), fs in groups.items():
        n = fs[0][1]
        if len(fs) == 1:
            issues.append(Issue(code, fs[0][5], str(path), n))
            continue
        files = list(dict.fromkeys(split_sel(split_flip(w)[0])[0] for _, _, w, *_ in fs))
        issues.append(Issue(code, f"legend {listed(repr(f[0]) for f in fs)} (lines {spans([f[1] for f in fs])}; "
                            f"{listed(repr(f) for f in files)}): {msg}", str(path), n))
    return sorted(issues, key=lambda i: i.line or 0)


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
    save_image(tinted(Image.open(a.file).convert("RGBA"), color), out)
    print("wrote", out)


def outside_px(img, x, y, w, h):
    """How many of img's opaque pixels fall outside a w x h canvas when img is drawn at x,y."""
    alpha = img.getchannel("A").point(lambda v: 255 if v else 0)
    total = alpha.histogram()[255]
    box = (max(0, -x), max(0, -y), min(img.width, w - x), min(img.height, h - y))
    inside = alpha.crop(box).histogram()[255] if box[0] < box[2] and box[1] < box[3] else 0
    return total - inside


SCENE_SIZE = (96, 64)  # scene without --size or --map: a small room of 16x16 tiles, 6 by 4


def parse_tile(s):
    """--tile: 'WxH', or 'N' for NxN."""
    if re.match(r"^\d+$", s or ""):
        s = f"{s}x{s}"
    return parse_size(s, "--tile")


def cmd_scene(a):
    need_o(a, "s.png")
    tint = parse_tint(a.tint) if a.tint else None
    bg = parse_color(a.bg, "--bg")
    placed = []
    tile = parse_tile(a.tile)
    if a.map:
        notes = []
        with reading(f"--map ({a.map})"):
            placed, msize = read_map(a.map, tile, notes)
        for n in notes:
            print("note:", n)
    W, H = map(int, a.size.split("x")) if a.size else (msize if a.map else SCENE_SIZE)
    sc = Image.new("RGBA", (W, H), bg)
    with reading(f"--map ({a.map})"):
        tiles = load_legend(a.map, a.variant) if a.map else {}
    cut, reach = [], [0, 0]  # cut: (what, px outside the canvas); reach: the size that holds every item

    def lay(what, img, x, y):
        draw_at(sc, img, x, y)
        n = outside_px(img, x, y, W, H)
        if n:
            cut.append((what, n))
        reach[0], reach[1] = max(reach[0], x + img.width), max(reach[1], y + img.height)
    for arg, x, y in placed:
        lay("the map", tiles[arg].img, *cell_spot(arg, tiles[arg].img, x, y, tile))
    for n, spec in enumerate(a.specs, 1):
        with reading(f"item {n} ({spec.rpartition('@')[0] or spec})"):
            path, x, y = split_at(spec)
            img = place_item(path, "scene item", a.variant).img
        lay(f"item {n} ({path})", img, x, y)
    why = "--size" if a.size else "--map" if a.map else "the default"
    for what, n in [(w, sum(n for x, n in cut if x == w)) for w in dict.fromkeys(w for w, _ in cut)]:
        print(f"note: {n} px of {what} fall outside the {W}x{H} scene (size from {why}) and were cropped")
    if cut and why == "the default":
        print(f"note: {W}x{H} (six 16x16 tiles by four) is scene's size when nothing sizes it (no --size, no "
              f"--map); --size {reach[0]}x{reach[1]} holds every item")
    if tint:
        sc = tinted(sc, tint)
    n = len(a.specs)
    save_image(sc.resize((W * a.scale, H * a.scale), Image.NEAREST), a.o, "-o" if a.o else "the scene (no -o)",
               about=f"a {W}x{H} scene at --scale {a.scale}" + (f", the map's {len(placed)} cells" if a.map else "")
               + (f", {n} item{'s' * (n != 1)}" if n else ""), smaller="a lower --scale makes it smaller")
    print(wrote(a.o))


def check_map(path):
    """check for a scene tilemap: every legend entry loads as one frame and every row char has one. (ok, how many notes
    it printed)."""
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
    return not issues, len(notes)


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


def check_args(files, exclude):
    """check's files: a DIR stands for the .px, .map, world sources and Tiled worlds under it (in_dirs), except a
    .world compiled from a *.src.json beside it (the source is checked: the same compile, the same rules). A DIR with
    only Tiled rooms (.tmj) says to check their world."""
    for f in files:
        if os.path.isdir(f) and not any(p.is_file() and p.name.endswith((".px", ".map", WORLD_SRC, ".world"))
                                        for p in pathlib.Path(f).rglob("*")):
            rooms = sorted(pathlib.Path(f).rglob("*.tmj"))
            if rooms:
                worlds = sorted(pathlib.Path(f).resolve().parent.glob("*.world"))
                fail("E_FILE", f"{f} holds Tiled rooms (.tmj) only: check their world ("
                     + (f"'check {posix_rel(worlds[0], os.getcwd())}'" if worlds else "'check W.world'")
                     + f"), or one room alone ('check {posix_rel(rooms[0], os.getcwd())}')")
    out = []
    given = set(files)
    for arg in in_dirs(files, (".px", ".map", WORLD_SRC, ".world"), exclude):
        if arg.endswith(".world") and arg not in given and any(pathlib.Path(arg).parent.glob("*" + WORLD_SRC)):
            continue
        out.append(arg)
    return out


def cmd_check(a):
    with reading(f"--palette ({a.palette})"):
        allowed = load_palette(a.palette) if a.palette else None
    want = tuple(map(int, a.size.split("x"))) if a.size else None
    failed = False
    tally = {"files": 0, "frames": 0, "warnings": 0, "failed": 0}
    for arg in dict.fromkeys(check_args(a.files, a.exclude or ())):
        path, sel = split_sel(arg)
        tally["files"] += 1
        bad_before = failed
        failed = False
        try:
            if path.endswith(TILED_EXTS):
                ok, said = check_tiled(path)
                failed |= not ok
                tally["warnings"] += said
                continue
            if is_world_src(path):
                ok, said = check_world(path, parse_tile(a.tile), a.tileset or ())
                failed |= not ok
                tally["warnings"] += said
                continue
            if path.endswith(".map"):
                ok, said = check_map(path)
                failed |= not ok
                tally["warnings"] += said
                continue
            if path.endswith(".px") and not sel and not _has_grid(path):
                try:
                    pdoc = parse(path, a.strict, palette_only=True)
                    print(f"ok   {path}: palette file, {len(pdoc.palette)} key(s)"
                          + (f", variants {', '.join(pdoc.variants)}" if pdoc.variants else ""))
                    for name, ks in half_variants(pdoc):
                        print(f"     {path}: {said_half(pdoc, name, ks)}")
                        tally["warnings"] += 1
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
                same = [k for k in doc.palette if k in doc.shared and k not in over]
                if same:
                    idle = [k for k in same if redundant(doc, k)]
                    notes.append("local keys repeat @palette colors: " + "".join(same) + (
                        f" (the same in every variant too: 'pxart palette {path} --remove {','.join(idle)}' drops "
                        f"{'those lines' if len(idle) > 1 else 'that line'} and renders the same)" if idle == same else
                        f" ({''.join(k for k in same if k not in idle)}: with a variant line of {path}'s own"
                        + (f"; 'pxart palette {path} --remove {','.join(idle)}' drops the others' lines and renders "
                           "the same" if idle else "") + ")"))
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
                for name, ks in half_variants(doc):
                    notes.append(said_half(doc, name, ks))
                for text, n in orphans(doc):
                    msg = f"{text!r} names a group with no frames; remove the line or add frames to it"
                    if a.strict:
                        failed = True
                        print(f"FAIL {path}:{n}: E_SELECT: {msg}")
                    else:
                        notes.append(f"line {n}: {msg} (check --strict fails on it)")
                used = set("".join(r for f in doc.frames for r in f.grid))
                blank = doc.blanks()
                unused = [k for k in doc.palette if k not in used and k not in blank]
                if unused:
                    them = "them" if len(unused) > 1 else "it"
                    notes.append("unused keys " + "".join(unused) + f" (no frame draws with {them}: 'pxart palette "
                                 f"{path} --remove {','.join(unused)}' drops {them}; compose and crop give a new OUT "
                                 "their sources' whole palettes unless --used-keys-only)")
            lines, sizes, ncs, nbad = [], [], [], 0
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
                nbad += bool(probs)
                sizes.append(f"{it.img.width}x{it.img.height}")
                ncs.append(len(cs))
                name = path if len(its) == 1 and not (it.frame and it.frame.id) else f"{path}:{it.label}"
                lines.append((bool(probs), f"{'FAIL' if probs else 'ok  '} {name}: {it.img.width}x{it.img.height} "
                                           f"{len(cs)}c" + "".join(f"; {x}" for x in probs)))
            tally["frames"] += len(its)
            if a.verbose or len(its) == 1:  # a frame per line (one frame: the file's line is the frame's)
                print("\n".join(l for _, l in lines))
            else:  # a line for the file, then the frames that fail
                cs = f"{min(ncs)}c" if min(ncs) == max(ncs) else f"{min(ncs)}-{max(ncs)}c"
                print(f"FAIL {path}: {nbad} of {len(its)} frames fail" if nbad else
                      f"ok   {path}: {len(its)} frames, {listed(dict.fromkeys(sizes), 4)}, {cs}")
                for bad, l in lines:
                    if bad:
                        print(f"     {l}")
            for note in notes:
                print(f"     {path}: {note}")
                tally["warnings"] += 1
        finally:  # after the file's own lines, like its other notes
            for note in lookalike_notes(path) if path.endswith((".px", ".map")) else []:
                print(f"     note: {note}")
                tally["warnings"] += 1
            tally["failed"] += failed
            failed |= bad_before
    if tally["files"] > 1:
        t = tally
        print(f"{t['files']} files, {t['frames']} frame{'s' * (t['frames'] != 1)}, {t['warnings']} "
              f"warning{'s' * (t['warnings'] != 1)}" + (f", {t['failed']} failed" if t["failed"] else ""))
    sys.exit(1 if failed else 0)


def cmd_stats(a):
    spots = [coords(s, ("x", "y"), "--at") for s in a.at or []]
    for n, arg in enumerate(frames_only(in_dirs(a.files, exclude=a.exclude or ()), "stats"), 1):
        name, own = split_variant(arg)
        v = own or a.variant
        with reading(f"file {n} ({arg})"):
            its = items(arg, a.variant)
        for it in its:
            cs, box = colors(it.img), it.img.getchannel("A").getbbox()
            print(f"{arg if not (it.frame and it.frame.id) else split_sel(name)[0] + ':' + it.label}"
                  + (f"%{v}" if v and it.doc and (it.frame.id or not own) else "")
                  + f": {it.img.width}x{it.img.height} bbox {box_text(box) if box else 'none' + unseen(it, v)}; "
                  + f"colors={len(cs)} " + " ".join(rgba2hex(c) for c in cs[:32]))
            if a.colors:
                for line in color_counts(it):
                    print(f"  {line}")
            for x, y in spots:
                with reading(f"file {n} ({arg})"):
                    print(f"  {pixel_at(it, int(x), int(y), v)}")


def unseen(it, variant=None):
    """stats, for a frame that renders empty: ' (96 px drawn, all transparent in the base; visible in night)' when its
    grid draws keys that its palette makes transparent (a halo lit only at night), else ''."""
    if not it.frame:
        return ""
    drawn = [c for row in it.frame.grid for c in row if c != "."]
    if not drawn:
        return ""
    d, keys = it.doc, set(drawn)
    here = variant if variant and variant != "base" else "base"
    seen = [n for n in ["base"] + variant_names(d) if n != here and any(d.resolved(n)[k][3] for k in keys)]
    return (f" ({len(drawn)} px drawn, all transparent in {'the base' if here == 'base' else here}; "
            + (f"visible in {listed(seen)}" if seen else "in every variant too") + ")")


def color_counts(it):
    """stats --colors: a frame's rendered colors, most pixels first (then by color), each with its pixel count and, for
    a .px frame, the keys that draw it: ['#120e22 40 px (k)', ...]. Transparent pixels aren't colors."""
    count, keys = {}, {}
    grid = "".join(it.frame.grid) if it.frame else None
    for i, c in enumerate(pixels(it.img)):
        if not c[3]:
            continue
        count[c] = count.get(c, 0) + 1
        if grid is not None:
            keys.setdefault(c, {})[grid[i]] = True
    return [f"{rgba2hex(c)} {n} px" + (f" ({' '.join(keys[c])})" if c in keys else "")
            for c, n in sorted(count.items(), key=lambda cn: (-cn[1], cn[0]))]


def pixel_at(it, x, y, variant=None):
    """stats --at x,y: 'at 3,4: key k; base #3f2631, night #120e22' (every variant of the frame's file, or only
    `variant` when the input named one); a PNG's pixel is its color alone. Outside the frame is E_BAD_ARG."""
    w, h = it.img.size
    if not (0 <= x < w and 0 <= y < h):
        fail("E_BAD_ARG", f"--at {x},{y} is outside {it.label}'s {w}x{h} frame")
    if not it.frame:
        return f"at {x},{y}: {fmt_color(it.img.getpixel((x, y)))}"
    k, d = it.frame.grid[y][x], it.doc
    names = [variant] if variant and variant != "base" else ["base"] + variant_names(d)
    for n in names:
        warn_half(d, n)
    return f"at {x},{y}: key {k}; " + ", ".join(f"{n} {fmt_color(d.resolved(n)[k])}" for n in names)


def cmd_diff(a):
    """diff A B [--variant V] [--strict-alpha] [--labels CSV]: renders compared pixel by pixel, one line per pair and a
    count for several; exit 1 when anything differs or has no pair. A and B: two files (one frame each, or frames
    paired by id), a file and a directory of PNGs (each frame against DIR/<id>.png, or the PNG --labels names so), or
    two directories (their .png and .px files paired by path)."""
    for flag, v in (("--label-col", a.label_col), ("--file-col", a.file_col)):
        if v is not None and not a.labels:
            fail("E_BAD_ARG", f"{flag} names a column of --labels FILE.csv; give --labels too")
    dirs = [os.path.isdir(x) for x in (a.a, a.b)]
    if a.labels and not any(dirs):
        fail("E_BAD_ARG", "--labels names the PNGs of a directory: diff FILE.px DIR --labels DIR/labels.csv")
    pxs = [d and any(p.is_file() for p in pathlib.Path(x).rglob("*.px")) for d, x in zip(dirs, (a.a, a.b))]
    if a.exclude and not any(dirs):
        fail("E_BAD_ARG", "--exclude leaves .px files out of a directory: diff DIR PNG_DIR --exclude GLOB")
    if all(dirs) and pxs.count(True) == 1:  # a directory of .px against one of PNGs: frames by id (or --labels)
        pairs = px_dir_pairs(a, flip=pxs[1])
    elif all(dirs):
        pairs = dir_pairs(a)
    elif a.exclude:
        fail("E_BAD_ARG", f"--exclude leaves .px files out of a directory, and {a.a if dirs[1] else a.b} is a file: "
             "drop --exclude, or give the directory")
    elif any(dirs):
        pairs = file_dir_pairs(a, flip=dirs[0])
    else:
        pairs = file_pairs(a)
    one = len(pairs) == 1 and pairs[0][0] is None  # one frame each: -o is a PNG; else a directory of them
    if a.o and (one and not isinstance(pairs[0][2], str) or not one and pathlib.Path(a.o).suffix):
        save_image(Image.new("RGBA", (1, 1)), a.o, "-o", check_only=True)  # a bad -o fails before the readout
    same = differ = alone = 0
    shown = []  # (label, A, B): the pairs that differ, for -o
    for lab, x, y in pairs:
        if isinstance(y, str):  # no pair: y says what's missing
            alone += 1
            print(f"{lab}: {y}")
            continue
        said = diff_images(x.img, y.img, a.strict_alpha)
        differ += said is not None
        same += said is None
        print(f"{lab + ': ' if lab else ''}{said or 'same: ' + f'{x.img.width}x{x.img.height}, every pixel'}")
        if said:
            shown.append((lab, x, y))
        if x.img.size != y.img.size:
            hint = rendered_hint(x, y)
            if hint:
                print(f"note: {hint}")
    if len(pairs) > 1 or (pairs and pairs[0][0] is not None):
        print(f"{len(pairs)} frame(s): {same} same" + (f", {differ} differ" if differ else "")
              + (f", {alone} unpaired" if alone else ""))
    if a.o and not one and pathlib.Path(a.o).suffix:  # an image -o over several pairs: fine when one pair differs
        if len(shown) > 1:
            fail("E_BAD_ARG", f"-o {a.o}: {len(shown)} of the {len(pairs)} pairs differ ({listed(l for l, *_ in shown)}), "
                 "and -o names one image; name a directory for them (one image per pair that differs): -o diffs/")
        if shown:
            print(wrote(save_image(diff_picture(*shown[0][1:], a.strict_alpha, a.scale), a.o))
                  + f" (the one pair that differs: {shown[0][0]})")
        else:
            print(f"note: -o {a.o} not written: no pair differs")
    elif a.o:
        diff_pictures(a, shown, one)
    if differ or alone:
        sys.exit(1)


SHEET_BACKDROP = (30, 30, 36, 255)  # render's and sheet's backdrop, around the cells


def rendered_hint(x, y):
    """For two sizes that differ: when one side is a PNG bigger than the other both ways and looks like a pxart render
    (a sheet's backdrop in its corner) or the other scaled up whole, the words naming render --plain. Else None."""
    for side, it, other in (("A", x, y), ("B", y, x)):
        img, o = it.img, other.img
        if it.doc is not None or img.width <= o.width or img.height <= o.height:
            continue
        k = img.width // o.width
        if img.getpixel((0, 0)) == SHEET_BACKDROP:
            return (f"{side} ({img.width}x{img.height}) looks like a pxart render or sheet of a {o.width}x{o.height} "
                    "frame (its padding, labels, grid and rulers): 'pxart render --plain FILE:ID -o x.png' writes the "
                    "frame alone at its exact size")
        if k > 1 and img.size == (o.width * k, o.height * k):
            return (f"{side} ({img.width}x{img.height}) is {o.width}x{o.height} times {k}: a render at --scale {k}? "
                    "'pxart render --plain FILE:ID -o x.png' writes the frame at 1x")
    return None


DIFF_MARK = (255, 0, 255, 255)  # diff -o: a pixel that differs


def diff_picture(x, y, strict=False, scale=None):
    """diff -o's picture of one pair: A, B, and B dimmed with every pixel that differs in magenta, side by side, each
    labeled, on render's backdrop. Frames of two sizes are compared top-left aligned, over both: a pixel only one side
    has differs when it isn't transparent. scale: 8, or less to keep the picture within 2048 px wide."""
    A, B = x.img, y.img
    w, h = max(A.width, B.width), max(A.height, B.height)
    pa, pb = Image.new("RGBA", (w, h), CLEAR), Image.new("RGBA", (w, h), CLEAR)
    pa.paste(A, (0, 0)); pb.paste(B, (0, 0))
    mark = Image.new("RGBA", (w, h), CLEAR)
    gray = B.convert("LA").convert("RGBA")
    gray.putalpha(B.getchannel("A").point(lambda v: v * 35 // 100))
    mark.paste(gray, (0, 0))
    n = 0
    for i, (p, q) in enumerate(zip(pixels(pa), pixels(pb))):
        if p != q and (strict or p[3] or q[3]):
            mark.putpixel((i % w, i // w), DIFF_MARK)
            n += 1
    pad, lab = 8, 14
    s = scale or max(1, min(8, (2048 - 4 * pad) // (3 * w)))
    panels = ((pa, f"A {A.width}x{A.height}"), (pb, f"B {B.width}x{B.height}"), (mark, f"{n} px differ"))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    cw = max([w * s] + [text_w(probe, words) + 4 for _, words in panels])
    out = Image.new("RGBA", (pad + 3 * (cw + pad), pad + lab + h * s + pad), SHEET_BACKDROP)
    d = ImageDraw.Draw(out)
    for c, (img, words) in enumerate(panels):
        at = pad + c * (cw + pad)
        d.rectangle([at, pad + lab, at + w * s - 1, pad + lab + h * s - 1], fill=rgba("#3a3a44"))
        out.alpha_composite(img.resize((w * s, h * s), Image.NEAREST), (at, pad + lab))
        d.text((at, pad), words, fill=(255, 120, 220, 255) if c == 2 else (220, 220, 220, 255))
    return out


def diff_pictures(a, shown, one):
    """diff -o: one pair's picture as -o, or with several pairs a picture per pair that differs in the directory -o,
    each named by its pair's label ('walk/0' -> walk_0.png)."""
    if one:
        if shown:
            print(wrote(save_image(diff_picture(*shown[0][1:], a.strict_alpha, a.scale), a.o)))
        else:
            print(f"note: -o {a.o} not written: nothing differs")
        return
    names = set()
    for lab, x, y in shown:
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", re.sub(r"\.(px|png)\b", "", lab)).strip("_") or "pair"
        base, k = name, 2
        while name in names:
            name, k = f"{base}-{k}", k + 1
        names.add(name)
        save_image(diff_picture(x, y, a.strict_alpha, a.scale), pathlib.Path(a.o) / f"{name}.png")
    d = pathlib.Path(a.o).as_posix().rstrip("/")
    print(f"wrote {len(shown)} diff image{'s' * (len(shown) != 1)} in {d}/, one per pair that differs" if shown
          else f"note: nothing written in {d}/: no pair differs")


def file_pairs(a):
    """diff FILE FILE: [(label, A's Item, B's Item)]: one frame each (labeled None), or frames paired by id, or in order
    when their ids differ but their counts match (copies made with --prefix)."""
    sides = []
    for what, arg in (("A", a.a), ("B", a.b)):
        with reading(f"{what} ({arg})"):
            sides.append(items(arg, a.variant))
    ia, ib = sides
    la, lb = {it.label: it for it in ia}, {it.label: it for it in ib}
    if len(ia) == 1 and len(ib) == 1:
        return [(None, ia[0], ib[0])]
    if set(la) == set(lb):
        return [(lab, la[lab], lb[lab]) for lab in la]
    if len(ia) == len(ib):  # copies under other ids (frames --copy-to --prefix wick/): in order
        return [(f"{x.label} vs {y.label}", x, y) for x, y in zip(ia, ib)]
    only = [f"{what} has {listed(sorted(set(x) - set(y)), 5)} and {other} hasn't"
            for what, other, x, y in (("A", "B", la, lb), ("B", "A", lb, la)) if set(x) - set(y)]
    fail("E_SELECT", f"A is {len(ia)} frame(s) and B {len(ib)}, paired by id: " + "; ".join(only)
         + "; pick frames with FILE:SEL")


def dir_pngs(d, a):
    """{name: path} of the PNGs under directory d: each by its path under d without .png ('walk/0'), or with --labels
    by the name its CSV row gives (as from-png ids it: a char an id can't have becomes '_'), in its folder. Two PNGs
    with one name are E_BAD_ARG."""
    name_of = csv_labels(a) if a.labels else None
    out = {}
    for p in sorted(pathlib.Path(d).rglob("*.png"), key=lambda p: p.parts):
        rel = p.relative_to(d).with_suffix("")
        got = name_of(p) if name_of else None
        name = (rel.parent / re.sub(r"[^A-Za-z0-9_\-./]", "_", got)).as_posix() if got else rel.as_posix()
        if name in out:
            fail("E_BAD_ARG", f"{out[name]} and {p} are both named {name!r} under {d}"
                 + (" by --labels" if name_of else "") + "; pair them one at a time")
        out[name] = p
    return out


def file_dir_pairs(a, flip=False):
    """diff FILE DIR (or DIR FILE): each frame of FILE (FILE:SEL) against the PNG under DIR named like it, DIR/<id>.png
    (or the PNG --labels names so). A frame no PNG is named like is unpaired: (label, Item, what's missing)."""
    farg, d = (a.b, a.a) if flip else (a.a, a.b)
    with reading(f"{'B' if flip else 'A'} ({farg})"):
        its = items(farg, a.variant)
    pngs = dir_pngs(d, a)
    out = []
    for it in its:
        p = pngs.get(it.label)
        if p is None:
            out.append((it.label, it, f"no PNG under {d} named {it.label} by --labels" if a.labels else
                        f"no {pathlib.Path(d) / (it.label + '.png')}"))
            continue
        with reading(f"{'A' if flip else 'B'} ({p})"):
            png = items(str(p))[0]
        lab = f"{it.label} vs {p.relative_to(d).as_posix()}" if a.labels else it.label
        out.append((lab, png, it) if flip else (lab, it, png))
    return out


def px_dir_pairs(a, flip=False):
    """diff DIR PNG_DIR (or PNG_DIR DIR), one directory holding .px files and the other none: every frame of every .px
    under DIR (sorted by path; palette files skipped, --exclude GLOB as for check) against the PNG under PNG_DIR named
    like its id, or with --labels the one its CSV row names so, as for diff FILE DIR. An id two files share is
    E_BAD_ARG (they'd claim one PNG). A frame no PNG is named like is unpaired; a note counts the PNGs no frame took."""
    pdir, d = (a.b, a.a) if flip else (a.a, a.b)
    files = [f for f in in_dirs([pdir], exclude=a.exclude or ()) if _has_grid(f)]
    if not files:
        fail("E_FILE", f"{pdir} holds no .px files with frames" + (" (after --exclude)" if a.exclude else ""))
    pngs = dir_pngs(d, a)
    out, whose, took = [], {}, set()
    for f in files:
        with reading(f"{'B' if flip else 'A'} ({f})"):
            its = items(f, a.variant)
        rel = pathlib.Path(f).relative_to(pdir).as_posix()
        for it in its:
            if it.label in whose and whose[it.label] != rel:
                fail("E_BAD_ARG", f"{whose[it.label]} and {rel} under {pdir} both have a frame {it.label!r}, and "
                     "would claim one PNG; diff them one at a time (diff FILE PNG_DIR), or --exclude one")
            whose[it.label] = rel
            name = rel if it.doc.implicit else f"{rel}:{it.label}"
            p = pngs.get(it.label)
            if p is None:
                out.append((name, it, f"no PNG under {d} named {it.label} by --labels" if a.labels else
                            f"no {pathlib.Path(d) / (it.label + '.png')}"))
                continue
            took.add(p)
            with reading(f"{'A' if flip else 'B'} ({p})"):
                png = items(str(p))[0]
            lab = f"{name} vs {p.relative_to(d).as_posix()}"
            out.append((lab, png, it) if flip else (lab, it, png))
    left = [p.relative_to(d).as_posix() for p in pngs.values() if p not in took]
    if left:
        print(f"note: {len(left)} PNG{'s' * (len(left) > 1)} under {d} no frame is named like"
              + (" by --labels" if a.labels else "") + f": {listed(left, 5)}")
    return out


def dir_pairs(a):
    """diff DIR_A DIR_B: the .png and .px files under both (not palette files, nor those --exclude leaves out), paired by
    path under each (with --labels, a PNG goes by the name its row gives); a .px pair's frames paired as for two files, labeled 'path:id'. A file only
    one side has is unpaired: (path, None, which side has it)."""
    sides = []
    for d in (a.a, a.b):
        pngs = {f"{name}.png": p for name, p in dir_pngs(d, a).items()}
        pxs = {p.relative_to(d).as_posix(): p for p in sorted(pathlib.Path(d).rglob("*.px"), key=lambda p: p.parts)
               if _has_grid(p)}  # a palette file has no frames to compare
        sides.append({r: p for r, p in {**pngs, **pxs}.items()
                      if not globs_hit(p.relative_to(d).as_posix(), a.exclude or ())})
    for g in a.exclude or ():
        if not any(globs_hit(p.relative_to(d).as_posix(), [g]) for d in (a.a, a.b)
                   for p in pathlib.Path(d).rglob("*") if p.suffix in (".png", ".px")):
            print(f"note: --exclude {g} matches no file")
    sa, sb = sides
    if not sa and not sb:
        fail("E_FILE", f"{a.a} and {a.b} hold no .png or .px files")
    out = []
    for rel in sorted(set(sa) | set(sb), key=lambda r: pathlib.PurePosixPath(r).parts):
        if rel not in sb or rel not in sa:
            out.append((rel, None, f"only in A ({a.a})" if rel in sa else f"only in B ({a.b})"))
        elif rel.endswith(".png"):
            with reading(f"A ({sa[rel]})"):
                x = items(str(sa[rel]))[0]
            with reading(f"B ({sb[rel]})"):
                y = items(str(sb[rel]))[0]
            real = [p.relative_to(d).as_posix() for p, d in ((sa[rel], a.a), (sb[rel], a.b))]
            out.append((rel if real == [rel, rel] else " vs ".join(real), x, y))  # --labels: the files' own names
        else:
            sub = argparse.Namespace(**{**vars(a), "a": str(sa[rel]), "b": str(sb[rel])})
            out += [(f"{rel}:{lab or x.label}", x, y) for lab, x, y in file_pairs(sub)]
    return out


def diff_images(a, b, strict=False):
    """None when two RGBA images are pixel-for-pixel the same (every transparent pixel alike, whatever its rgb, unless
    strict: --strict-alpha), else what differs: 'sizes 16x16 and 16x24', or '12 px differ in 3,4,6,6 (x,y,w,h)'."""
    if a.size != b.size:
        return f"sizes {a.width}x{a.height} and {b.width}x{b.height}"
    w = a.width
    bad = [i for i, (p, q) in enumerate(zip(pixels(a), pixels(b))) if p != q and (strict or p[3] or q[3])]
    if not bad:
        return None
    xs, ys = [i % w for i in bad], [i // w for i in bad]
    return (f"{len(bad)} px differ in {min(xs)},{min(ys)},{max(xs) - min(xs) + 1},{max(ys) - min(ys) + 1} "
            "(x,y,w,h)")


def cmd_frames(a):
    path, sel = split_sel(a.file)
    with reading(f"FILE ({a.file})"):
        doc = parse(path, allow_empty=True)
        picked = in_file_order(doc, doc.select(sel)) if sel else doc.frames
    if a.prefix is not None and not a.copy_to:
        fail("E_BAD_ARG", f"--prefix names the copies --copy-to DST makes; to rename frames in {path}: frames "
             f"{path} --rename GROUP NEWGROUP")
    if a.rename and a.prefix is not None:
        fail("E_BAD_ARG", "give --prefix P (every copied id gets P in front) or --rename GROUP NEWGROUP, not both")
    if a.dry_run and not (a.copy_to or a.rename or a.rm is not None or a.move or a.after or a.before):
        fail("E_BAD_ARG", "--dry-run goes with an edit (--rm, --move, --after/--before, --rename, --copy-to); the "
             "listing writes nothing")
    if a.copy_to:
        if a.rm is not None or a.move:
            fail("E_BAD_ARG", "--copy-to copies frames; --rm and --move edit FILE: give one")
        if a.after and a.before:
            fail("E_BAD_ARG", "give --after or --before, not both")
        print(frames_copy(a, doc, sel, picked))
        return
    if a.rename:
        if a.rm is not None or a.move or a.after or a.before:
            fail("E_BAD_ARG", "--rename renames in place; --rm, --move, --after and --before are other edits: give one")
        if sel:
            fail("E_BAD_ARG", f"--rename GROUP NEWGROUP names what it renames; give FILE without :{sel}: frames {path} "
                 f"--rename {sel} NEWGROUP")
        print("; ".join(rename_frames(doc, a.rename) + [write_doc(doc)]))
        return
    if a.rm is not None or a.move or a.after or a.before:
        if doc.implicit:
            fail("E_MIXED_FRAMES", "this file has one unnamed grid; nothing to move or remove")
        if a.after and a.before:
            fail("E_BAD_ARG", "give --after or --before, not both")
        had, lines = set(doc.groups()), {anchor for anchor, _, _ in doc.lines()}
        did = (frames_sel_edit if sel else frames_edit)(a, doc, sel, picked)
        did += drop_orphans(doc, had - set(doc.groups()))
        keep_spacing(doc, lines - {anchor for anchor, _, _ in doc.lines()})
        print("; ".join(did + [write_doc(doc)]))
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
    renames = [tuple(r) for r in a.rename or []]
    if a.prefix is not None:
        renames = [(g, a.prefix + g) for g in dict.fromkeys(f.id.split("/", 1)[0] for f in picked)]
        if not a.prefix or not all(ID_RE.match(n) for _, n in renames):
            fail("E_BAD_ID", f"--prefix {a.prefix!r}: the copies' ids would be {', '.join(n for _, n in renames)}; "
                 "a prefix is a path of letters, digits, _ - and . ('wick/', or 'wick-')")
    check_renames(renames, [f.id for f in picked], f"{a.file}'s frames to copy")
    new_id = {id(f): renamed_id(f.id, renames) for f in picked}
    froms = {}
    for f in picked:
        froms.setdefault(new_id[id(f)], []).append(f.id)
    twice = {n: olds for n, olds in froms.items() if len(olds) > 1}
    if twice:
        fail("E_DUP_FRAME", "--rename gives two copies one id (the later would replace the earlier): "
             + "; ".join(f"{n} (from {', '.join(olds)})" for n, olds in twice.items())
             + "; rename them into different groups")
    if not pathlib.Path(dpath).exists():
        fail("E_FILE", f"--copy-to {typed_path(dpath)}: no such file; to start one with these frames and {doc.path}'s palette: "
             f"pxart extract {doc.path}{':' + sel if sel else ''} -o {dpath}; to copy them into a file that imports "
             f"another palette, start it empty first: pxart new {dpath} --empty --palette P.px")
    with reading(f"--copy-to ({dpath})"):
        dst = parse(dpath, allow_empty=True)
    if dst.implicit:
        if not ID_RE.match(dst.stem):
            fail("E_MIXED_FRAMES", f"{dpath} has one unnamed grid, and its name {dst.stem!r} can't be a frame id")
        dst.promote()
        print(f"note: {dpath}'s unnamed grid is now '@frame {dst.stem}' (the id it went by)")
    dups = [new_id[id(f)] for f in picked if dst.get(new_id[id(f)])]
    if dups:
        fail("E_DUP_FRAME", f"{dpath} already has {', '.join(dups)}; remove them first (pxart frames {dpath} --rm "
             f"{' '.join(dups)}), copy the others, or copy them under other ids (--prefix P, or --rename GROUP "
             "NEWGROUP)")
    anchor = dst.get(a.after or a.before or "")
    if (a.after or a.before) and not anchor:
        fail("E_SELECT", f"--{'after' if a.after else 'before'} {a.after or a.before!r}: no such frame in {dpath}")
    keys = set("".join(r for f in picked for r in f.grid))
    vmap = variant_map(a.variant_map)
    check_vmap(vmap, dst, dpath, [doc])
    label = f"FILE ({a.file})"
    _, asked = rekey_one(a.rekey, dst, doc, keys, vmap, True, dpath, label)
    keys = set("".join(r for f in picked for r in f.grid))
    clash = key_conflicts(dst, doc, keys, "FILE", dpath, "frames --copy-to", clear=True, vmap=vmap)
    if clash:
        clash.ctx = label
        raise PxError(clash)
    warn = said_vclash(label, doc, vclashes(dst, doc, keys, vmap, clear=True), dst, dpath, vmap,
                       "frames --copy-to --rekey", asked)
    uncovered = said_uncovered(label, doc, dst, dpath, vmap, import_keys(dst, doc, keys, vmap, clear=True))
    for n, src in layer_variants(doc, vmap).items():  # a variant of DST the copies take from FILE's import alone
        if n in variant_names(dst):
            warn_half(doc, src)
    for line in warn + ([f"note: {uncovered}"] if uncovered else []):  # one line per key, and per reason
        print(line)
    said = []
    landed = {Frame(new_id[id(f)]).group for f in picked}  # the groups the copies land in (a frame renamed top-level: none)
    for g in dict.fromkeys(f.group for f in picked if f.group):
        n = renamed_id(g, renames)
        if n not in landed:  # no copy lands in it: its @anim or @still line would name a group with no frames
            continue
        if g in doc.anims and n not in dst.anims:
            dst.anims[n] = dict(doc.anims[g])
            said.append(f"added @anim {n}")
        elif g in doc.anims and any(doc.anims[g].get(k) != dst.anims[n].get(k) for k in ("direction", "repeat")):
            print(f"note: {dpath}'s @anim {n} stays (direction and repeat are the group's)")
        if doc.still(g) and not dst.still(n):
            dst.stills.append(n)
            said.append(f"added @still {n}")
    at = dst.frames.index(anchor) + (1 if a.after else 0) if anchor else None
    stilled = []
    for f in picked:
        new = Frame(new_id[id(f)], list(f.grid), f.ms, pivot=f.pivot)
        if at is not None:
            dst.frames.insert(at, new)
            at += 1
        else:
            same = [x for x in dst.frames if x.group == new.group] if new.group else []
            dst.frames.insert(dst.frames.index(same[-1]) + 1 if same else len(dst.frames), new)
        if doc.animated(f.group) and not dst.animated(new.group):  # an animation frame lands as a still
            stilled.append(as_still(new, doc, f, dst))
            continue
        if dst.ms(new) != doc.ms(f):
            new.ms = doc.ms(f)
        if dst.pivot(new) != doc.pivot(f):
            if doc.pivot(f) is None:
                print(f"note: {f.id} has no pivot in {doc.path}, and takes {dpath}'s @anim {new.group} pivot there")
            else:
                new.pivot = doc.pivot(f)
    for n in [n for n in dst.anims if f"added @anim {n}" in said]:
        place_anim(dst, n)
    if stilled:
        print(said_stilled(stilled, dpath))
    where = f" ({'after' if a.after else 'before'} {anchor.id})" if anchor else ""
    names = [f"{o} as {n}" for o, n in renames if any(new_id[id(f)] != f.id and renamed_id(f.id, [(o, n)]) != f.id
                                                       for f in picked)]
    return "; ".join([f"copied {', '.join(f.id for f in picked)} to {dpath}{where}"
                      + (f", {', '.join(names)}" if names else "")] + said + [write_doc(dst)])


def as_still(new, doc, f, dst):
    """An animation frame f of doc copied as new into dst, where its id is a still (a top-level id, or a @still group):
    stills have no timing, so its ms goes, and it keeps its pivot (its @anim's written on its own line). For the note:
    (new id, the ms it had, the pivot it keeps, why it's a still)."""
    new.ms, new.pivot = None, doc.pivot(f)
    why = "a top-level id" if not new.group else f"@still {new.group}" if new.group in dst.stills else "@still *"
    return new.id, doc.ms(f), new.pivot, why


def said_stilled(stilled, dpath):
    """The note for the frames as_still made stills: 'note: hero lands in beast.px as a still (a top-level id): its
    ms=140 goes (stills have no timing); pivot 8,15 kept'."""
    many = len(stilled) > 1
    whys = list(dict.fromkeys(w for *_, w in stilled))
    pivots = [f"{fmt_setting(p)}" for _, _, p, _ in stilled if p]
    return (f"note: {', '.join(i for i, *_ in stilled)} land{'' if many else 's'} in {dpath} as "
            f"{'stills' if many else 'a still'} "
            f"({', '.join(whys)}): {'their' if many else 'its'} ms="
            + ",".join(dict.fromkeys(str(ms) for _, ms, _, _ in stilled)) + " dropped (stills have no timing)"
            + (f"; pivot{'s' * (len(pivots) > 1)} {' '.join(pivots)} kept" if pivots else ""))


def renamed_id(fid, renames):
    """A frame id or group under --rename's [(OLD, NEW)]: OLD itself becomes NEW, OLD/rest becomes NEW/rest (the first
    rename that names it); any other id stays."""
    for old, new in renames:
        if fid == old:
            return new
        if fid and fid.startswith(old + "/"):
            return new + fid[len(old):]
    return fid


def check_renames(renames, ids, where):
    """--rename's pairs against the frame ids they rename: each OLD names some of them, each new id is a valid one."""
    for old, new in renames:
        if not any(i == old or i.startswith(old + "/") for i in ids):
            fail("E_SELECT", f"--rename {old} {new}: no frame {old!r} or {old}/... in {where}; frames: "
                 f"{', '.join(ids) or 'none'}" + guess(old, [i.rsplit("/", n)[0] for i in ids
                                                              for n in range(i.count("/") + 1)]))
    bad = [renamed_id(i, renames) for i in ids if not ID_RE.match(renamed_id(i, renames))]
    if bad:
        fail("E_BAD_ID", f"--rename gives bad frame ids: {', '.join(map(repr, bad))} (ids are paths of letters, "
             "digits, _ - and .)")


def rename_frames(doc, renames):
    """frames FILE --rename GROUP NEWGROUP (repeatable): the frames of GROUP (or the frame GROUP) get NEWGROUP's ids,
    and GROUP's @anim and @still lines name NEWGROUP; comments above them stay with them. What it did."""
    renames = [tuple(r) for r in renames]
    ids = [f.id for f in doc.frames if f.id]
    if doc.implicit:
        fail("E_MIXED_FRAMES", f"{doc.path} has one unnamed grid; nothing to rename")
    check_renames(renames, ids, doc.path)
    moving = {i for i in ids if renamed_id(i, renames) != i}
    new_ids = [renamed_id(i, renames) for i in ids]
    taken = [n for i, n in zip(ids, new_ids) if i in moving and (n in set(ids) - moving or new_ids.count(n) > 1)]
    groups = {f.group for f in doc.frames if f.id not in moving}
    into = [new for _, new in renames if new in groups or new in set(ids) - moving]
    if taken or into:
        what = sorted(set(taken)) or into
        fail("E_DUP_FRAME", f"--rename: {doc.path} already has {listed(what, 5)}; rename into a group it hasn't "
             "got (or remove those frames first: frames FILE:GROUP --rm)")
    for store in (doc.lead, doc.raw, doc.at):
        for anchor in [k for k in store if k[0] in ("frame", "row", "anim", "still") and k[1] is not None]:
            new = renamed_id(anchor[1], renames)
            if new != anchor[1]:
                store[(anchor[0], new) + anchor[2:]] = store.pop(anchor)
    for f in doc.frames:
        f.id = renamed_id(f.id, renames)
    said = []
    anims = {}
    for g, v in doc.anims.items():
        n = renamed_id(g, renames)
        anims[n] = v
        if n != g:
            said.append(f"@anim {n}")
    doc.anims = anims
    stills = []
    for g in doc.stills:
        n = renamed_id(g, renames) if g != "*" else g
        stills.append(n)
        if n != g:
            said.append(f"@still {n}")
    doc.stills = stills
    per = [f"{old} -> {new} ({sum(1 for i in ids if renamed_id(i, [(old, new)]) != i)} frame(s))"
           for old, new in renames]
    return [f"renamed {', '.join(per)}" + (f"; {', '.join(said)}" if said else "")]


def drop_orphans(doc, emptied):
    """The @anim and @still lines of groups that just lost their last frame go too: what went."""
    gone = [f"@anim {g}" for g in doc.anims if g in emptied] + [f"@still {g}" for g in doc.stills if g in emptied]
    doc.anims = {g: v for g, v in doc.anims.items() if g not in emptied}
    doc.stills = [g for g in doc.stills if g not in emptied]
    return [f"removed {', '.join(gone)} (no frames left)"] if gone else []


def keep_spacing(doc, gone):
    """Lines just removed (anchors) take their comments with them, but not the blank lines above them: those go to the
    next line the file had that is still there (in file order), unless it has blank lines above it already, so a
    '@palette' line keeps its blank line after it when the @anim below it goes."""
    order = sorted(doc.at, key=doc.at.get)
    there = {anchor for anchor, _, _ in doc.lines()}
    for anchor in sorted(gone, key=lambda x: doc.at.get(x, 0), reverse=True):  # last first: blanks move down once
        lead = doc.lead.get(anchor) or []
        blank = list(itertools.takewhile(lambda l: not l.strip(), lead))
        if not blank or anchor not in doc.at:
            continue
        nxt = next((x for x in order if doc.at[x] > doc.at[anchor] and x in there), None)
        if nxt is None or doc.lead.get(nxt) is None:
            continue
        if not (doc.lead[nxt] and not doc.lead[nxt][0].strip()):
            doc.lead[nxt] = blank + doc.lead[nxt]


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
        inside = [g.id for g in doc.frames if (g.id or "").startswith(fid + "/")]
        if not f and inside:
            fail("E_BAD_ARG", f"--rm {fid!r} is a group ({', '.join(inside)}); --rm takes frame ids. A group goes in "
                 f"the selector: frames {doc.path}:{fid} --rm")
        if not f:
            fail("E_SELECT", f"--rm {fid!r}: no such frame; frames: {', '.join(doc.label(g) for g in doc.frames)}"
                 + guess(fid, [g.id for g in doc.frames]))
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
        did.append(f"already in place: {where}" if doc.frames == was else f"moved {where}" + anims_follow(doc))
    return did


def anims_follow(doc):
    """After frames move: the @anim lines go in the order of their groups' first frames (lines of groups with no
    frames after, as they were), so the file reads in play order. What it says when they moved, else ''."""
    was = list(doc.anims)
    order_anims(doc, [f.group for f in doc.frames if f.group])
    return "; @anim lines follow the frames" if list(doc.anims) != was else ""


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
            groups = [fid for fid in out if any(i.startswith(fid + "/") for i in ids)]
            if groups:
                fail("E_BAD_ARG", f"--rm {', '.join(groups)}: {'a group' if len(groups) == 1 else 'groups'} in "
                     f"{sel!r}; --rm takes frame ids. A group goes in the selector: frames {doc.path}:{groups[0]} "
                     "--rm")
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
    return [f"already in place: {where}" if doc.frames == was else f"moved {where}" + anims_follow(doc)]


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


def copy_target(a):
    """flip, rotate, transpose: edit_target, or with -o FILE:NEWGROUP a copy of FILE:GROUP within FILE (dup_group; with
    --replace over NEWGROUP's frames) as the frames to edit. (doc, frames, where to write, what the copy did)."""
    opath, osel = split_sel(a.o) if a.o else (None, None)
    turn = f" {a.angle}" if a.cmd == "rotate" else ""
    if osel is None:
        if a.replace:
            fail("E_BAD_ARG", f"--replace goes with -o FILE:NEWGROUP, a copy made over NEWGROUP's frames ('{a.cmd} "
                 f"FILE:walk/right{turn} -o FILE:walk/left --replace')")
        return edit_target(a.file, a.o) + ([],)
    path, sel = split_sel(a.file)
    one_id(osel, a.o, "-o")
    one_id(sel, a.file, "FILE")
    verb = {"flip": "flips", "rotate": "turns", "transpose": "transposes"}[a.cmd]
    if not sel or pathlib.Path(opath).resolve() != pathlib.Path(path).resolve():
        fail("E_BAD_ARG", f"-o {a.o}: -o FILE:GROUP {verb} a copy of FILE:GROUP within FILE ('{a.cmd} {path}:walk/right"
             f"{turn} -o {path}:walk/left'); to another file, copy first (frames --copy-to) and {a.cmd} there")
    with reading(f"FILE ({a.file})"):
        doc = parse(path)
        if doc.get(sel) or not any((f.id or "").startswith(sel + "/") for f in doc.frames):
            doc.select(sel)  # a missing selector's error, with its guess
            fail("E_BAD_ARG", f"-o {a.o}: {a.cmd} into a copy takes a group (FILE:GROUP); for one frame, dup it "
                 f"first: dup {path}:{sel} NEWID, then {a.cmd} {path}:NEWID{turn}")
    said, frames = dup_group(doc, sel, osel, how=f"{a.cmd} {a.file}{turn} -o {a.o}", replace=a.replace)
    return doc, frames, doc.path, said


def cmd_flip(a):
    doc, frames, out, said = copy_target(a)
    move_pivots(doc, frames, lambda f: (lambda x, y, h=f.size[1]: (x, h - 1 - y)) if a.v else
                (lambda x, y, w=f.size[0]: (w - 1 - x, y)))
    mirrored_pivots(doc, frames, "y" if a.v else "x")
    for f in frames:
        f.grid = f.grid[::-1] if a.v else [r[::-1] for r in f.grid]
    print("; ".join(said + [write_doc(doc, out)]))


def mirrored_pivots(doc, frames, axes):
    """flip, rotate: a note when a frame with a pivot is mirrored across an even size (axes: 'x' across its width, 'y'
    its height, 'xy' both). The pivot keeps its pixel (x -> w-1-x), which is right for a pixel; a pivot meant as the
    point between the two middle pixels lands 1px off it, and pivots have no half pixels."""
    for axis in axes:
        size = (lambda f: f.size[0]) if axis == "x" else (lambda f: f.size[1])
        hit = [f for f in frames if doc.pivot(f) is not None and size(f) % 2 == 0]
        if not hit:
            continue
        n = size(hit[0])
        print(f"note: {listed([doc.label(f) for f in hit])}: pivot{'s' * (len(hit) > 1)} mirrored pixel for pixel "
              f"({axis} -> {n - 1}-{axis} across {n} px); a pivot meant as the centre between two pixels ends 1px off "
              "it (pivots are whole pixels): check with onion")
        return


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
    doc, frames, out, said = copy_target(a)
    move, vec = TURNS[how]
    mirrored_pivots(doc, frames, {"90": "y", "180": "xy", "270": "x", "transpose": ""}[how])  # what each mirrors
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
    light = f"a top-left light is now {names[now['nw']]} (--light {now['nw']})" if now["nw"] != "nw" else \
        f"a top-left light stays top-left, a top-right one is now {names[now['ne']]} (--light {now['ne']})"
    msg = write_doc(doc, out)
    if not msg.startswith("no change"):
        print(f"note: the shading turned with the pixels ({light}); re-light with 'shade' and 'outline --selective'")
    print("; ".join(said + [msg]))


def cmd_rotate(a):
    turn(a, a.angle)


def cmd_transpose(a):
    turn(a, "transpose")


def cmd_shift(a):
    """Vacated pixels (in the region, not under the moved block) become '.', or --fill KEY."""
    doc, frames, out = edit_target(a.file, a.o, coords=a.region and "--region")
    pal, blank = doc.resolved(), doc.blanks()
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
                if 0 <= tx < W and 0 <= ty < H and ch not in blank:
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
        save_image(img, out)
        print(f"erased {erased} px; " + wrote(out))
        return
    doc, frames, out = edit_target(a.file, a.o, coords=(a.keep or a.keep_circle) and "--keep"
                                   + "-circle" * (not a.keep))
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
    """Key moves (a=b, 'a<>b', 'a>b') apply together: each pixel is repainted by the move of the key it had before the
    call, so they can't feed each other, and a key 'a>b' frees ('b>c' in the same call) can be a new key's name: 'a>b'
    'b>a' swaps two keys' names, pixels and colors staying as they look. Color changes (c=#hex) set the palette and
    are independent of moves."""
    doc, frames, out = edit_target(a.file, a.o, coords=a.region and "--region")
    pal = doc.resolved()
    if a.variant:
        doc.resolved(a.variant)  # an unknown variant is E_SELECT, with its guess
    moves, said, renames, later = {}, {}, {}, {}  # later: colors for keys a move of this call makes ('b>t' t=#hex)
    made = {m[2] for m in a.maps if len(m) == 3 and m[1] == ">"}
    for m in a.maps:
        if len(m) == 3 and m[1] == ">":  # 'a>b': a's pixels get the new key b, in a's color
            k, v = m[0], m[2]
            if k not in pal or k == ".":
                fail("E_SELECT", f"recolor: {m!r}: key {k!r} not in palette" if k != "." else
                     f"recolor: {m!r}: '.' is transparent, not a color to give a new key")
            if v in renames.values():
                first = next(said[j] for j, w in renames.items() if w == v)
                fail("E_BAD_ARG", f"recolor: {m!r} and {first!r} both give pixels the new key {v!r}; each new key "
                     "takes one key's pixels")
            if v not in KEYS and v != ".":
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
        color = v.startswith("#") or v == "transparent"
        if k not in pal and not (color and k in made):
            if color:
                fail("E_BAD_ARG", f"recolor: {m!r}: key {k!r} isn't in the palette, and no 'a>{k}' in this call makes "
                     f"it; to add it: pxart palette {doc.path} --add '{k}=" + (
                         f"#rrggbb' (its base color), then this recolor" if a.variant else f"{v}'"))
            fail("E_SELECT", f"recolor: key {k!r} not in palette")
        if color:
            if a.region:
                fail("E_BAD_ARG", "--region only applies to key=key repaints; a color change affects every pixel "
                     "of that key. Add a new key (palette --add) and repaint the region to it instead.")
            if v != "transparent" and not COLOR_RE.match(v):
                fail("E_BAD_COLOR", f"{v!r} isn't #rrggbb or #rrggbbaa")
            if ("#", k) in said:
                fail("E_BAD_ARG", f"recolor: key {k!r} gets two colors ({said[('#', k)]} and {m})")
            said[("#", k)] = m
            # A shared key recolored here becomes a local override for this file only; a key a move makes gets its
            # color once the move has made it.
            (later if k in made else doc.variants.setdefault(a.variant, {}) if a.variant else doc.palette)[k] = \
                CLEAR if v == "transparent" else hex2rgba(v)
            continue
        if v not in pal:
            fail("E_SELECT", f"recolor: key {v!r} not in palette (add it with palette --add)")
        for k, v in pairs:
            if k in moves:
                fail("E_BAD_ARG", f"recolor: key {k!r} is moved twice ({said[k]} and {m}); key moves apply "
                     "together, so each key can go one place")
            moves[k], said[k] = v, m
    painted = {v for k, v in moves.items() if k not in renames}  # a=b paints pixels b: b stays
    rects = {id(f): parse_rect(a.region, f.size) for f in frames}
    chosen = {id(f) for f in frames}

    def outside(f, x, y):
        if id(f) not in chosen:
            return True
        x0, y0, w, h = rects[id(f)]
        return not (x0 <= x < x0 + w and y0 <= y < y0 + h)
    left = {k for k in renames if k in painted or any(
        c == k and outside(f, x, y) for f in doc.frames for y, row in enumerate(f.grid) for x, c in enumerate(row))}
    freed = {k for k in renames if k in doc.palette and k not in left}  # its lines become the new key's
    for k, v in renames.items():
        m = said[k]
        if v == k:
            fail("E_BAD_ARG", f"recolor: {m!r} gives {k}'s pixels the key they have; name a new key")
        if v not in pal or v in freed:
            continue
        free = [c for c in FREE_ORDER if c not in pal and c not in renames.values()][:3]
        if v in renames:
            why = ("it comes from an imported palette file" if v not in doc.palette else
                   f"{next(said[j] for j, w in moves.items() if w == v and j not in renames)!r} paints pixels {v}"
                   if v in painted else
                   "pixels outside the recolor still draw with it")
            fail("E_BAD_ARG", f"recolor: {m!r} needs a new key, and {v!r} stays one: {said[v]!r} leaves it in the "
                 f"palette ({why}); name a free key ({' '.join(repr(f'{k}>{c}') for c in free[:1])}; free: "
                 f"{' '.join(free) or 'none'})")
        new = f"name a free key ({' '.join(repr(f'{k}>{c}') for c in free[:1])}; free: {' '.join(free) or 'none'})"
        if pal[v] == pal[k]:  # the key it wants already draws that color: a repaint, not a new key
            other = [n for n in variant_names(doc) if doc.resolved(n)[v] != doc.resolved(n)[k]]
            if not other:
                fail("E_BAD_ARG", f"recolor: {m!r} needs a new key, and {v!r} is already one, in {k}'s color "
                     f"({fmt_color(pal[v])}" + (", in every variant too" if variant_names(doc) else "") + "): to "
                     f"draw {k}'s pixels with {v}, write '{k}={v}' (a repaint that looks the same); for a new key, "
                     + new)
            fail("E_BAD_ARG", f"recolor: {m!r} needs a new key, and {v!r} is already one, in {k}'s base color "
                 f"({fmt_color(pal[v])}) but not in " + ", ".join(
                     f"{n} ({k} {fmt_color(doc.resolved(n)[k])}, {v} {fmt_color(doc.resolved(n)[v])})" for n in other)
                 + f", so '{k}={v}' would change how {' and '.join(other)} look{'s' * (len(other) == 1)}: " + new
                 + (f", or free {v!r} in the same call: '{v}>{free[0]}' {m!r}" if free and v in doc.palette else ""))
        fail("E_BAD_ARG", f"recolor: {m!r} needs a new key, and {v!r} is already one ({fmt_color(pal[v])}): " + new
             + (f", or free {v!r} in the same call: '{v}>{free[0]}' {m!r}" if free and v in doc.palette else ""))
    for f in frames:
        x0, y0, w, h = rects[id(f)]
        f.grid = ["".join(moves.get(c, c) if x0 <= x < x0 + w and y0 <= y < y0 + h else c
                          for x, c in enumerate(row)) for y, row in enumerate(f.grid)]
    rename_keys(doc, renames, left)
    for k, c in later.items():
        (doc.variants.setdefault(a.variant, {}) if a.variant else doc.palette)[k] = c
    print(*recolor_counts(doc, frames, moves, [k for k in said if isinstance(k, tuple)], a.variant),
          write_doc(doc, out))


def recolor_counts(doc, frames, moves, recolored, variant=None):
    """What recolor did, as fill and paste say it: 'repainted 12 px;' for the key moves (per key when several, 'repainted
    5 px: 3 k->j, 2 j->k;', and per frame, all of up to 8), and
    'recolored o #112233: 40 px;' for each color change, counting the pixels drawn with that key in every frame (a
    color is the whole file's)."""
    out = [px_changed(doc, frames, "repainted", 7, [(k, v) for k, v in moves.items() if k != v]
                      if len(moves) > 1 else None)] if moves else []
    for _, k in recolored:
        counts = [(doc.label(f), sum(row.count(k) for row in f.grid)) for f in doc.frames]
        hit = [f"{label} {n}" for label, n in counts if n]
        out.append(f"recolored {k}" + (f" in {variant}" if variant else "")
                   + f" {fmt_color(doc.resolved(variant)[k])}: {sum(n for _, n in counts)} px"
                   + (f" ({listed(hit, 7)})" if len(hit) > 1 else "") + ";")
    return out


def rename_key(doc, k, v):
    """recolor 'k>v' for one key (rename_keys)."""
    rename_keys(doc, {k: v})


def rename_keys(doc, renames, left=None):
    """recolor 'k>v' ...: each new key v gets k's color, in every variant too, all at once (so 'a>b' 'b>a' swaps
    names). When no pixel keeps k (left: the keys some pixel keeps; by default, those a frame still draws with) and it
    is this file's own key, its lines become v's in place (a rename); otherwise v is added and k stays."""
    names = sorted(set(doc.variants) | set(doc.shared_variants))
    want = {(n, k): doc.resolved(n)[k] for n in names for k in renames}
    listed = {(n, k) for n in names for k in renames
              if k in doc.variants.get(n, {}) or k in doc.shared_variants.get(n, {})}
    base = doc.resolved()
    if left is None:
        left = {k for k in renames if any(k in row for f in doc.frames for row in f.grid)}
    full = {k: v for k, v in renames.items() if k in doc.palette and k not in left}
    if full:
        doc.palette = {full.get(key, key): c for key, c in doc.palette.items()}
        for store in (doc.lead, doc.at):
            got = {k: store.pop(("key", k)) for k in full if ("key", k) in store}
            store.update({("key", full[k]): x for k, x in got.items()})
        for name, over in doc.variants.items():
            if any(k in over for k in full):
                doc.variants[name] = {full.get(key, key): c for key, c in over.items()}
                got = {k: doc.lead.pop(("vkey", name, k)) for k in full if ("vkey", name, k) in doc.lead}
                doc.lead.update({("vkey", name, full[k]): x for k, x in got.items()})
    for k, v in renames.items():
        if k in full:
            continue
        doc.palette[v] = base[k]
        if k in left:
            print(f"note: {k!r} stays in the palette: pixels outside the recolor still use it")
    for k, v in renames.items():
        for n in names:  # a variant that lists k (a relist too: a lamp kept lit) lists v
            c = want[(n, k)]
            if doc.resolved(n)[v] != c or ((n, k) in listed and v not in doc.variants.get(n, {})):
                doc.variants.setdefault(n, {})[v] = c


def cmd_set(a):
    doc, frames, out = edit_target(a.file, a.o, coords="x,y")
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
    print(px_changed(doc, frames, "erased" if a.key == "." else "painted"), write_doc(doc, out))


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
    ddoc, dframes, out = edit_target(a.into, a.o, "--into", coords="--at")
    ax, ay = map(int, a.at.split(","))
    vmap = variant_map(a.variant_map)
    check_vmap(vmap, ddoc, out, [src.doc])
    label = f"SRC ({a.src})"
    _, asked = rekey_one(a.rekey, ddoc, src.doc, set("".join(src.frame.grid)), vmap, False, out, label, [src.frame])
    warn = said_vclash(label, src.doc, vclashes(ddoc, src.doc, set("".join(src.frame.grid)), vmap), ddoc, out, vmap,
                       "paste --rekey", asked)
    if a.keys is not None and not a.align:
        fail("E_BAD_ARG", "--keys picks the drawing --align follows; add --align shift, bbox or bottom")
    offsets = aligned(ddoc, dframes, a.align, a.keys) if a.align else {}
    added = []
    for f in dframes:
        dx, dy = offsets.get(id(f), (0, 0))
        with reading(label):
            added += stamp(ddoc, f, src.doc, src.frame, (ax + dx, ay + dy), a.region, a.under, out=out, vmap=vmap)
    uncovered = said_uncovered(label, src.doc, ddoc, out, vmap, added)
    moved = [f"{ax + offsets[id(f)][0]},{ay + offsets[id(f)][1]} in {ddoc.label(f)}" for f in dframes] \
        if len(dframes) > 1 and a.align else []
    for line in warn + ([f"note: {uncovered}"] if uncovered else []):  # one line per key, and per reason
        print(line)
    if moved:
        print(f"note: --align {a.align} pastes at {listed(moved, 5)}")
    print(px_changed(ddoc, dframes, "pasted"), write_doc(ddoc, out))


def aligned(doc, frames, how, keys=None):
    """paste --align: each frame's (dx, dy) from the first frame's, so a paste made for the first follows the others:
    pivot, their pivots (else bottom-centre, as anim's); bottom, their drawing's bottom row (dy only: feet on the
    ground); bbox, their drawing's top-left (a hop, when nothing sticks out); shift, the sum of each frame's best shift
    from the one before, as anim's readout computes it on its shared canvas (a body's bob, whatever its wings do). The
    drawing is the pixels of keys that draw (Doc.blanks), or of `keys` only, before the paste; shift reads them in their
    base colors. A frame that shows nothing has nothing to follow: E_BAD_ARG."""
    blank = doc.blanks()
    if keys is not None:
        if how == "pivot":
            fail("E_BAD_ARG", "--keys picks the drawing that --align bbox, bottom or shift follows; --align pivot "
                 "reads only the pivots")
        keys = key_list(keys, "--keys")
        pal = doc.resolved()
        unknown = [k for k in keys if k not in pal]
        if unknown:
            fail("E_BAD_ARG", f"--keys: {'keys' if len(unknown) > 1 else 'key'} {', '.join(map(repr, unknown))} "
                 f"{'aren' if len(unknown) > 1 else 'isn'}'t in the palette"
                 + guess(unknown[0], sorted(pal)), path=doc.path)
        blank = set(doc.resolved()) - set(keys)

    def nothing(f):
        of = f" of {','.join(keys)}" if keys else ""
        fail("E_BAD_ARG", f"--align {how}: {doc.label(f)} " + (
            f"shows no pixel{of} in its base colors, and shift follows the base render; --align bbox reads keys lit "
            f"only in a variant too" if how == "shift" else
            f"draws nothing{' in ' + ','.join(keys) if keys else ''}, so there's no drawing to follow; paste into it "
            f"on its own ({doc.path}:{doc.label(f)})"))
    if how == "shift":
        pal = doc.resolved()
        its = []
        for f in frames:
            img = Image.new("RGBA", f.size)
            img.putdata([CLEAR if c in blank else pal[c] for row in f.grid for c in row])
            if not img.getbbox():
                nothing(f)
            its.append(Item(doc.label(f), img, 0, doc, f))
        lay = pivot_layout(its)  # the canvas anim diffs on: pivots lined up, else bottom-centered
        w, h = lay[:2] if lay else (max(it.img.width for it in its), max(it.img.height for it in its))
        spots = lay[2] if lay else [((w - it.img.width) // 2, h - it.img.height) for it in its]
        canvas = [placed(it.img, w, h, at, "#00000000") for it, at in zip(its, spots)]
        out, cx, cy = {id(frames[0]): (0, 0)}, 0, 0
        for i in range(1, len(frames)):
            dx, dy, _ = best_shift(canvas[i - 1], canvas[i])
            cx, cy = cx + dx, cy + dy
            out[id(frames[i])] = (cx + spots[0][0] - spots[i][0], cy + spots[0][1] - spots[i][1])
        return out

    def spot(f):
        if how == "pivot":
            return doc.pivot(f) or (f.size[0] // 2, f.size[1] - 1)
        ys = [y for y, row in enumerate(f.grid) if any(c not in blank for c in row)]
        if not ys:
            nothing(f)
        return (0, ys[-1]) if how == "bottom" else (min(x for row in f.grid for x, c in enumerate(row)
                                                        if c not in blank), ys[0])
    first = spot(frames[0])
    return {id(f): (x - first[0], y - first[1]) for f, (x, y) in ((f, spot(f)) for f in frames)}


def cmd_extract(a):
    """Only the selected frames, with the file's palette, @palette imports (re-pointed from OUT's directory),
    variants, and @anim/@still lines except those of groups the selection left behind."""
    path, sel = split_sel(a.file)
    with reading(f"FILE ({a.file})"):
        doc = parse(path)
        keep = in_file_order(doc, doc.select(sel))
    gone = {f.group for f in doc.frames} - {f.group for f in keep}  # groups the selection leaves behind
    out = pathlib.Path(a.o)
    note_suffix(out)
    if out.exists() and not a.replace:
        try:
            had = parse(out, allow_empty=True) if out.suffix == ".px" else None
        except (PxError, OSError, ValueError):  # not a .px it can read: still not extract's to overwrite
            had = None
        what = (f"its frames {listed([had.label(f) for f in had.frames], 5)}" if had and had.frames else
                "its palette" if had else "its contents")
        same = [f.id for f in keep if had and f.id and had.get(f.id)]
        fail("E_DUP_FRAME" if same else "E_FILE",
             f"{out} exists, and extract writes a new file: {what} would be lost"
             + (f" ({listed(same, 5)} under the same id{'s' * (len(same) > 1)})" if same else "")
             + f"; to add the frames to it: pxart frames {a.file} --copy-to {out}; to overwrite it: --replace")
    doc.frames = keep
    order_anims(doc, [f.group for f in keep])
    doc.anims = {g: v for g, v in doc.anims.items() if g not in gone}
    doc.stills = [g for g in doc.stills if g not in gone]
    if a.inline_palette:
        inline_palette(doc)
    print(write_doc(doc, out), f"({len(doc.frames)} frame(s))")


def place_anim(doc, group):
    """A new '@anim GROUP' line (just added, so last) moves among the others to where its group's first frame puts it:
    after the last line whose group starts earlier, so the lines follow the frames; the lines already there keep their
    order. Blank lines above the first @anim line stay first."""
    first = {}
    for i, f in enumerate(doc.frames):
        first.setdefault(f.group, i)
    rest, end = [g for g in doc.anims if g != group], len(doc.frames)
    at = max((i + 1 for i, g in enumerate(rest) if first.get(g, end) < first.get(group, end)), default=0)
    if at == 0 and rest:  # it goes first: it takes the blank lines above the old first line, which keeps its comment
        lead = doc.lead.get(("anim", rest[0]))
        if lead is not None:
            n = next((i for i, x in enumerate(lead) if x.strip()), len(lead))
            doc.lead[("anim", group)], doc.lead[("anim", rest[0])] = lead[:n], lead[n:]
    doc.anims = {g: doc.anims[g] for g in rest[:at] + [group] + rest[at:]}


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


def frame_slot(opath, osel, palette=None, flag="-o", fresh=False):
    """Open OUT (or start it, importing `palette`; fresh: start it though it exists) and find or make the frame
    OUT[:frame] names: (doc, frame). A new frame goes after the last frame of its animation, or at the end when the
    animation is new."""
    one_id(osel, f"{opath}:{osel}", flag)
    doc = parse(opath, allow_empty=True) if pathlib.Path(opath).exists() and not fresh else start_doc(opath, palette)
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
    if a.empty:
        return new_empty(a, opath, osel)
    if not a.size:
        fail("E_BAD_ARG", f"new needs --size WxH for the frame (or --empty for a file with no frames: pxart new "
             f"{opath} --empty --palette P.px)")
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


def new_empty(a, opath, osel):
    """new OUT --empty [--palette P.px]: a file with no frames (and no palette lines), only the version line and P's
    @palette import, for frames --copy-to or compose -o OUT:ID to fill."""
    if osel:
        fail("E_BAD_ARG", f"--empty starts a file with no frames; drop :{osel} (then add frames with frames "
             f"--copy-to or compose -o {opath}:{osel})")
    given = [f for f, v in (("--size", a.size), ("--key", a.key), ("--still", a.still)) if v]
    if given:
        fail("E_BAD_ARG", f"--empty makes no frame, so {', '.join(given)} has nothing to apply to")
    if pathlib.Path(opath).exists():
        fail("E_BAD_ARG", f"--empty starts a new file, and {opath} exists")
    with reading(f"OUT ({a.out})"):
        doc = start_doc(opath, a.palette)
    print(write_doc(doc, opath) + (f" (no frames; imports {doc.palette_refs[0]})" if a.palette else " (no frames)"))


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
    doc, frames, out = edit_target(a.file, a.o, coords=a.region and "--region")
    if a.key not in doc.resolved():
        fail("E_SELECT", f"fill: key {a.key!r} not in palette (add it with palette --add)")
    for f in frames:
        x0, y0, w, h = parse_rect(a.region, f.size)
        f.grid = ["".join(a.key if x0 <= x < x0 + w and y0 <= y < y0 + h else c for x, c in enumerate(row))
                  for y, row in enumerate(f.grid)]
    print(px_changed(doc, frames, "erased" if a.key == "." else "painted"), write_doc(doc, out))


def px_changed(doc, frames, verb, most=5, keys=None):
    """'painted 12 px;' for an edit of one frame; of several, per frame that changed: 'painted 40 px (walk/0 12, walk/1
    16, walk/2 12);', the first `most` of them. keys: the key moves [(a, b)] to count one by one, in that order,
    'repainted 5 px: 3 k->j, 2 j->k (a 2, b 3);'. From doc.before (edit_target)."""
    counts, pairs = [], {}
    for f in frames:
        n = 0
        for was, now in zip(doc.before[id(f)], f.grid):
            for p, q in zip(was, now):
                if p != q:
                    n += 1
                    pairs[(p, q)] = pairs.get((p, q), 0) + 1
        counts.append((doc.label(f), n))
    hit = [f"{label} {n}" for label, n in counts if n]
    return f"{verb} {sum(n for _, n in counts)} px" \
        + (": " + ", ".join(f"{pairs.get(k, 0)} {k[0]}->{k[1]}" for k in keys) if keys else "") \
        + (f" ({listed(hit, most)})" if len(hit) > 1 else "") + ";"


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
                 f"or both ending in .5 ({eg[1]}: 8 across)"
                 + ("; or give the pixel box instead, as rect's: --box x,y,w,h" if what == "ellipse" else ""))
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
    where = {"line": "x0,y0 x1,y1", "rect": "x,y,w,h", "poly": "x,y ...", "ellipse": "cx,cy,rx,ry", "arc": "cx,cy,r",
             "flood": "x,y"}[a.cmd] if not getattr(a, "box", None) else "--box"
    doc, frames, out = edit_target(a.file, a.o, coords=where)
    if a.key not in doc.resolved():
        fail("E_SELECT", f"{a.cmd}: key {a.key!r} not in palette (add it with palette --add)")
    changed = 0
    for f in frames:
        c, cut = paint(f, shape(f), a.key)
        changed += c
        if cut:
            print(f"note: {cut} px of the {a.cmd} fall outside {doc.label(f)} ({f.size[0]}x{f.size[1]}) and were "
                  "clipped")
    print(f"{'erased' if a.key == '.' else 'painted'} {changed} px;", write_doc(doc, out))


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
    if (a.shape is None) == (a.box is None):
        fail("E_BAD_ARG", "ellipse takes cx,cy,rx,ry or --box x,y,w,h (the pixel box it fills, as rect's), one of them")
    if a.box:
        x, y, w, h = coords(a.box, ("x", "y", "w", "h"), "--box")
        if w < 1 or h < 1:
            fail("E_BAD_ARG", f"--box {a.box}: w and h must be at least 1")
        box = (x, y, x + w - 1, y + h - 1)
    else:
        box = ellipse_box(*coords(a.shape, ("cx", "cy", "rx", "ry"), "ellipse", half=True), "ellipse")
    if a.ring is not None and (a.ring < 1 or a.fill):
        fail("E_BAD_ARG", f"--ring {a.ring}: the outline's thickness in px, N >= 1" if a.ring < 1 else
             "--ring N draws an outline N px thick and --fill the whole shape: give one of them")
    pts = ellipse_ring(box, a.ring) if a.ring else ellipse_points(*box, fill=a.fill)
    draw(a, lambda f: sorted(pts, key=lambda p: (p[1], p[0])))


def ellipse_ring(box, n):
    """ellipse --ring N: the outline N px thick, inside the shape: the filled ellipse less what is left of it after N
    steps of peeling off every pixel with a side outside it. --ring 1 is the plain outline, pixel for pixel; a ring
    thicker than half the shape is the filled shape."""
    filled = ellipse_points(*box, fill=True)
    core = set(filled)
    for _ in range(n):
        core = {(x, y) for x, y in core if {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} <= core}
    return filled - core


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
    """The frame's shape: its pixels whose key draws (Doc.blanks), a night-only halo's included."""
    blank = doc.blanks()
    return {(x, y) for y, row in enumerate(f.grid) for x, ch in enumerate(row) if ch not in blank}


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
    return f"{what}; wrote {sheet(its, png, 8, grid=True, rulers=True, what='--preview')} (preview; {doc.path} unchanged)"


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
    doc, frames, out = edit_target(a.file, a.o, coords=a.region and "--region")
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


def variant_map(specs):
    """compose --variant-map NAME=V1,V2 (repeatable): {NAME: [NAME, V1, V2]}, the variants of the layers' files that
    OUT's variant NAME is built from, each layer taking the first of them its file has."""
    vmap = {}
    for spec in specs or []:
        name, eq, srcs = spec.partition("=")
        names = list(dict.fromkeys([name] + srcs.split(",")))
        if not eq or not srcs or name == "base" or not all(re.match(r"^[A-Za-z0-9_\-]+$", n) for n in names):
            fail("E_BAD_ARG", f"--variant-map {spec!r}: want NAME=V1,V2 (variant names; OUT's variant NAME takes, "
                 "for each layer, the first of NAME, V1, V2 its file has), and not NAME 'base'")
        if name in vmap:
            fail("E_BAD_ARG", f"--variant-map: {name!r} is mapped twice ({name}={','.join(vmap[name][1:])} and "
                 f"{spec}); give each of OUT's variants one map, its sources in order: {name}=V1,V2")
        vmap[name] = names
    return vmap


def variant_names(d):
    """A doc's variants, its own first, then the imported ones."""
    return list(d.variants) + [n for n in d.shared_variants if n not in d.variants]


def half_variants(d, only=None):
    """The variants d gets only through its @palette imports (no '@variant NAME' line of its own) that leave some of its
    own keys at their base colors, since the palette file's variant can't know them: [(name, keys)], the keys in
    palette order, those its frames draw (a palette file, with no frames: all its own). only: that variant alone. A
    file with its own @variant line of that name has chosen what its keys do there, and is left alone."""
    if not d.palette_refs:
        return []
    drawn = set("".join(r for f in d.frames for r in f.grid)) if d.frames else None
    out = []
    for name, over in d.shared_variants.items():
        if name in d.variants or name == "base" or (only is not None and name != only):
            continue
        ks = [k for k, c in d.palette.items() if c[3] and k not in over and (drawn is None or k in drawn)]
        if ks:
            out.append((name, ks))
    return out


def lit_keys(d):
    """The keys of d's own (the ones a derive into an imported variant writes) that d's variants already treat as
    lights: [(key, why)] in palette order. A light is a key some variant of d leaves at its base color (no line, or
    relisted unchanged) or makes brighter; for a key d's @palette defines too, that palette's variants count as well.
    A variant d gets only from its import can't know d's keys, so it says nothing about them."""
    out = []
    for k, c in d.palette.items():
        if k == "." or not c[3]:
            continue
        whys = []
        seen = [(n, f"{n}", c, d.variants[n]) for n in d.variants]
        if k in d.shared:  # the import defines k too: its variants say what k does there
            seen += [(n, f"{' and '.join(d.palette_refs)}'s {n}", d.shared[k], o)
                     for n, o in d.shared_variants.items() if n not in d.variants]
        for n, label, base, over in seen:
            got = d.resolved(n)[k] if n in d.variants else over.get(k, base)
            if brightness(got) > brightness(base):
                whys.append(f"brighter in {label}")
            elif got == base:
                whys.append(f"{'relisted unchanged' if k in over else 'left at base'} in {label}")
        if whys:
            out.append((k, ", ".join(whys)))
    return out


def said_half(d, name, ks):
    """The words for one of half_variants: which file, which variant, the keys it leaves at base, and the fix, with the
    lights lit_keys infers kept lit (and why each), since a derive would dim them."""
    refs = d.palette_refs
    pal = (d.path.parent / refs[0]).as_posix() if len(refs) == 1 else "P.px"
    pal = os.path.normpath(pal) if len(refs) == 1 and not os.path.isabs(pal) else pal
    many = len(ks) > 1
    lit = lit_keys(d)
    whys = {}
    for k, why in lit:
        whys.setdefault(why, []).append(k)
    told = ("lights inferred: " + "; ".join(f"{' '.join(v)} {w}" for w, v in whys.items())) if lit else \
        "no lights inferred; add --keep-lit for any"
    return (f"@variant {name} comes only from its @palette {' and '.join(refs)}, which gives no {name} "
            f"color{'s' * many} to its own key{'s' * many} {' '.join(ks)}: in {name} {'they stay at their' if many else 'it stays at its'} base "
            f"color{'s' * many}. Give it a {name} of its own: 'pxart palette {d.path} --variant {name} "
            f"--derive-from base --match {pal}" + (f" --keep-lit {','.join(k for k, _ in lit)}" if lit else "")
            + f"' ({told}), or --add 'K=#rrggbb'" + said_recompose(d, name))


def said_recompose(d, name):
    """For a half variant of a file its header says compose made: composing it again, once its sources have a `name`
    of their own, is the other fix (its layers' own variants color their pixels)."""
    how = composed_from(d)
    if how is None:
        return ""
    cmd, line = how
    return (f"; or, since its header says it was composed ({line!r}), give its sources a {name} of their own and "
            + (f"compose it again: '{cmd}'" if cmd else "compose it again from its map or layers"))


WARNED = set()  # (path, variant) whose half_variants WARNING this run printed: once per file and variant


def warn_half(d, name):
    """Rendering d in variant `name`: a WARNING (once per file and variant a run) when name comes only from d's
    @palette and leaves keys of d's own at their base colors (half_variants)."""
    if not name or name == "base" or d is None or d.path is None:
        return
    for n, ks in half_variants(d, name):
        if (d.path.resolve(), n) not in WARNED:
            WARNED.add((d.path.resolve(), n))
            print(f"WARNING: {d.path}: {said_half(d, n, ks)}")


def layer_variants(d, vmap):
    """{OUT's variant: the variant of d's file it takes}. A map entry NAME=V1,V2 only says where OUT's NAME comes from
    (d's first of NAME, V1, V2); every other variant of OUT reads d's variant of the same name, one the map also reads
    as NAME included: the map adds to that lookup, never replaces it. In the order of d's variants."""
    have = variant_names(d)
    out = {}
    for n in have:  # one variant of the file may be several of OUT's: night read as dusk (and rain), and as night
        for t in [t for t, ns in vmap.items() if n in ns] + ([n] if n not in vmap else []):
            out.setdefault(t, next(x for x in vmap[t] if x in have) if t in vmap else n)
    return out


def merged_away(docs, vmap):
    """The variants a new OUT leaves out: a name the map reads as another of OUT's (the keeper's night, as dusk) that
    every file having it gave to the map. One a file keeps as its own (a palette with both dusk and night) stays."""
    given = {id(d): {src for t, src in layer_variants(d, vmap).items() if t in vmap and src != t} for d in docs}
    return {n for d in docs for n in given[id(d)]
            if not any(n in variant_names(e) and n not in given[id(e)] for e in docs)}


def listed(items, most=3):
    """'a, b, c' for a few, 'a, b, c and 19 more' for many."""
    items = list(items)
    return ", ".join(items) if len(items) <= most + 1 else f"{', '.join(items[:most])} and {len(items) - most} more"


def special_keys(d):
    """The keys of d's file that losing would cost something: {key: why}. Its frames draw with them, or a variant
    treats them on purpose: lists them in their base color (a lamp kept lit), or leaves them alone while it recolors
    most of the other keys (a glow left out of the dark)."""
    base, why, drawn, blank = d.resolved(), {}, {}, d.blanks()
    for f in d.frames:
        for k in dict.fromkeys("".join(f.grid)):
            drawn.setdefault(k, []).append(d.label(f))
    for k in base:
        if k in blank:
            continue
        fs = drawn.get(k, [])
        says = [f"its frame{'s' * (len(fs) > 1)} {listed(fs)} draw{'s' * (len(fs) == 1)} with it"] if fs else []
        for n in variant_names(d):
            over = {**d.shared_variants.get(n, {}), **d.variants.get(n, {})}
            recolored = sum(1 for x, c in over.items() if x != k and base.get(x) not in (None, c))
            if over.get(k) == base[k]:
                says.append(f"@variant {n} relists it unchanged")
            elif k not in over and 2 * recolored > len(base) - 2:  # not counting '.' and k itself
                says.append(f"@variant {n} keeps it while it recolors most keys")
        if says:
            why[k] = says
    return why


KEY_TOKEN = r"(?<![A-Za-z0-9]){}(?![A-Za-z0-9])"


def renamed_lead(lead, moves, own=None):
    """A comment carried into compose's OUT, where --rekey gave some of its file's keys new ones: each comment line that
    names a renamed key (a letter or digit standing alone, as in 'lamp colors (l, g) stay lit') gets '(renamed l>P
    g>Q)'; own (old, new): the key line it sits above was renamed, said on its last comment line if no line names it."""
    out, told = [], set()
    for line in lead:
        text = line.split("#", 1)[1] if "#" in line else ""
        ks = [k for k in moves if k.isalnum() and re.search(KEY_TOKEN.format(re.escape(k)), text)]
        told |= set(ks)
        out.append(line + (" (renamed " + " ".join(f"{k}>{moves[k]}" for k in ks) + ")" if ks else ""))
    if own and own[0] not in told:
        last = max((i for i, l in enumerate(out) if l.strip().startswith("#")), default=None)
        if last is not None:
            out[last] += f" (renamed {own[0]}>{own[1]})"
    return out


NAME_TOKEN = r"(?<![A-Za-z0-9_\-]){}(?![A-Za-z0-9_\-])"


def labeled(lines, label):
    """Carried comment lines with `label` said on the last comment line, in its '(renamed ...)' if it has one."""
    out = list(lines)
    last = max((i for i, l in enumerate(out) if l.strip().startswith("#")), default=None)
    if last is None or not label:
        return out
    m = re.search(r" \(renamed [^()]*\)$", out[last])
    out[last] = out[last][:-1] + f"; {label})" if m else out[last] + f" ({label})"
    return out


def mapped_mentions(lines, d, vmap):
    """The variants of d's file that --variant-map merged into another of OUT's that these comment lines name, as
    'dark is dusk here' (a comment saying 'not in @variant dark' about an OUT that has no dark)."""
    text = " ".join(l.split("#", 1)[1] for l in lines if "#" in l)
    return [f"{src} is {out} here" for out, src in layer_variants(d, vmap).items()
            if src != out and re.search(NAME_TOKEN.format(re.escape(src)), text)]


def comment_blocks(doc, seen=None):
    """{key: the keys after it} for each key line of doc's palette (and the palette files it imports) that has a
    comment above it and key lines right below it, no blank or comment line between: the keys that comment is about
    ('# light-emitting keys' above f a i)."""
    seen = set() if seen is None else seen
    out = {}
    if doc.path is not None:
        seen.add(doc.path.resolve())
    for ref in doc.palette_refs:
        target = doc.path.parent / ref
        if target.resolve() in seen:
            continue
        try:
            out.update(comment_blocks(parse(target, palette_only=True), seen))
        except (OSError, PxError):
            continue
    head = None
    for k in doc.palette:
        lead = doc.lead.get(("key", k)) or []
        if any(l.strip() for l in lead):
            head = k
            out[head] = []
        elif lead or head is None:
            head = None
        else:
            out[head].append(k)
    return {k: ks for k, ks in out.items() if ks}


def carry_notes(doc, docs, notes, renamed, owners, vmap):
    """compose's new OUT gets the comments that document its keys and variants in the layers' palettes (as --extract-to
    carries them): above a key line, its owner's comment for it, with the keys right below it in the source (the keys
    it is about) moved up under it when OUT has them from that file; above a @variant line, the comments above the
    variants it takes, the layers' in order; above a variant key line, its owner's. A key --rekey renamed says so
    (renamed_lead). From several files, each comment says which file's it is ('from keeper.px's @variant night'), and
    a comment naming a variant --variant-map merged into another says so ('dark is dusk here'). A variant --variant-map
    merged from several gets a line naming them. notes: {path: (palette_notes, comment_blocks)} of each layer's file,
    read before --rekey moved keys."""
    multi = len(docs) > 1

    def lead_of(d, anchor, own=None):
        got = notes.get(d.path.resolve(), ({}, {}))[0].get(anchor)
        return renamed_lead(got, renamed.get(d.path.resolve(), {}), own) if got else None

    def label(d, lines, what):  # 'from player.px, whose dark is dusk here'
        named = mapped_mentions(lines, d, vmap)
        if not multi:
            return "; ".join(named)
        return f"from {what}" + (f", whose {' and '.join(named)}" if named else "")

    def old(d, k):
        return next((o for o, n in renamed.get(d.path.resolve(), {}).items() if n == k), k)

    def new(d, k):
        return renamed.get(d.path.resolve(), {}).get(k, k)
    order = list(doc.palette)
    for k in list(order):
        d = owners.get(k)
        got = lead_of(d, ("key", old(d, k)), (old(d, k), k) if old(d, k) != k else None) if d is not None else None
        if not got:
            continue
        doc.lead[("key", k)] = labeled(got, label(d, got, d.path.name))
        after = [new(d, x) for x in notes.get(d.path.resolve(), ({}, {}))[1].get(old(d, k), [])]
        after = [x for x in after if x in doc.palette and x != k and owners.get(x) is not None
                 and owners[x].path.resolve() == d.path.resolve()]
        for x in after:  # the keys the comment is about follow it, in the source's order
            order.remove(x)
        order[order.index(k) + 1:order.index(k) + 1] = after
    if order != list(doc.palette):
        doc.palette = {k: doc.palette[k] for k in order}
    for name, over in doc.variants.items():
        takes = [(d, layer_variants(d, vmap)[name]) for d in docs if name in layer_variants(d, vmap)]
        groups = {}  # the same comment lines from several files (one shared palette): said once, naming them all
        for d, src in takes:
            got = [l for l in lead_of(d, ("variant", src)) or [] if l.strip()]
            if got:
                groups.setdefault(tuple(got), []).append((d, src))
        lines = []
        # credit the files whose variant lines gave OUT's own @variant keys, a line of the file's variant (its own or
        # imported) in the color OUT's has (a file whose recolored keys all come from OUT's shared import gave none),
        # and the import for the rest
        def lines_of(d, src):
            return {**d.shared_variants.get(src, {}), **d.variants.get(src, {})}
        gave = {id(d) for d, src in takes if any(lines_of(d, src).get(k) == c for k, c in over.items())}
        rest = [f"{pathlib.PurePath(r).name}'s" for r in doc.palette_refs] if name in doc.shared_variants else []
        rest = f"{' and '.join(rest)} {name}" if rest else ""
        named = set()  # the files a comment's tag credits
        for got, whose in groups.items():
            credited = [(d, src) for d, src in whose if id(d) in gave] if multi else whose
            if not credited and not rest:  # nothing better to go on: every file that has it
                credited = whose
            named |= {id(d) for d, _ in credited}
            srcs = list(dict.fromkeys(src for _, src in credited))
            what = " and ".join(dict.fromkeys(f"{d.path.name}'s" for d, _ in credited)) + f" @variant {'/'.join(srcs)}"
            here = f", {name} here" if srcs != [name] else ""
            if multi and not credited:
                tag = f"from {rest}"
            elif multi:
                tag = f"from {what}{here}" + (f"; the rest from {rest}" if rest else "")
            else:
                tag = f"@variant {'/'.join(srcs)}{here}" if here else ""
            lines += labeled(list(got), tag)
        froms = list(dict.fromkeys(f"{d.path.name}'s {src}" for d, src in takes))
        if name in vmap and any(src != name for _, src in takes):
            lines.append(f"# {name}: {', '.join(froms)} (compose --variant-map)")
        elif multi and lines:  # a file whose variant gave keys but no comment is credited too, so no tag reads as all
            also = [(d, src) for d, src in takes if id(d) in gave and id(d) not in named]
            if also:
                same = all(src == name for _, src in also)  # 'far.px's and mid.px's dusk', else each one's
                whose = [f"{d.path.name}'s" + ("" if same else f" {src}") for d, src in also]
                lines.append(f"# {name}: also from {', '.join(whose[:-1]) + ' and ' if len(whose) > 1 else ''}"
                             f"{whose[-1]}" + (f" {name}" if same else ""))
        if lines:
            doc.lead[("variant", name)] = [""] + lines
        for k in over:
            d = owners.get(k)
            src = layer_variants(d, vmap).get(name) if d is not None else None
            got = lead_of(d, ("vkey", src, old(d, k)), (old(d, k), k) if old(d, k) != k else None) if src else None
            if got:
                doc.lead[("vkey", name, k)] = labeled(got, label(d, got, f"{d.path.name}'s @variant {src}"))


def carry_header(doc, heads):
    """A new compose OUT whose palette is inlined gets the header comments of the palette files its layers import
    (their comments above their first line; a sprite's own header is about the sprite and stays), at the top of its
    palette, each saying which layers' files it came from: heads {layer file name: header lines}."""
    if doc.palette_refs:  # OUT imports the palette files themselves, headers and all
        return
    groups = {}
    for name, head in heads.items():
        if head:
            groups.setdefault(tuple(head), []).append(name)
    lines = [l for head, names in groups.items() for l in labeled(list(head), f"from {', '.join(names)}")]
    first = next((anchor for anchor, _, _ in doc.lines() if anchor[0] in ("key", "variant")), None)
    if lines and first:
        doc.lead[first] = [""] + lines + [""] + [l for l in doc.lead.get(first) or [] if l.strip()]


def seed_palette(doc, layers, gone=None, used_only=False, vmap=None, owners=None):
    """A new compose OUT starts with its layers' whole palettes, not only the keys they use, so a later shade ramp
    or recolor finds its keys. When every layer imports the same @palette files, OUT imports them too (re-pointed
    from OUT; not with --variant-map, whose variants OUT builds); otherwise their colors become key lines. Then each
    layer's keys join in layer order, the keys the layers use first: a key OUT already has in the same color is
    skipped, one that overrides an import (as in the layer) stays an override, and an unused key whose char another
    layer has in another color is left out (a used one is E_KEY_CONFLICT when stamped). Variants come along for the
    keys OUT has, each in the colors of the layer whose key OUT has (its owner), so one file's variant never recolors
    another file's pixels; vmap (--variant-map) merges several variants into one. Returns what was left out, [(key, the
    layer it's left out of, the layer whose color OUT has, whether that layer uses it)], and {key: (the layer whose
    color OUT has, whether it uses it)}; owners, when given, gets {key: that layer's doc}. gone: {id(layer doc): keys
    --rekey moved away}, which a shared import may still hold: never seeded. used_only (--used-keys-only): only the
    keys the layers use become key lines (a shared @palette is still imported)."""
    vmap = vmap or {}
    owners = {} if owners is None else owners
    docs = list({id(lay.doc): lay.doc for lay, *_ in layers}.values())
    names = {}
    for lay, _, _, label in layers:
        names.setdefault(id(lay.doc), label)
    imports = {tuple((d.path.parent / r).resolve() for r in d.palette_refs) for d in docs}
    keep = imports.pop() if len(imports) == 1 and not vmap else ()
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
                    doc.palette[k], whose[k], owners[k] = c, (names[id(d)], want_used), d
                elif have[k] != c and not want_used:
                    left.append((k, names[id(d)]) + whose[k])
    looks = {}  # (id(doc), variant) -> its resolved palette

    def color(d, name, k):  # k in OUT's variant name, as d's file draws it (its base color when it has no such variant)
        src = layer_variants(d, vmap).get(name)
        if (id(d), src) not in looks:
            looks[(id(d), src)] = d.resolved(src)
        return looks[(id(d), src)].get(k)
    gone_names = merged_away(docs, vmap)
    for d in docs:
        base, lv = d.resolved(), layer_variants(d, vmap)
        mine = list(d.variants) + ([] if keep else [n for n in d.shared_variants if n not in d.variants])
        for out, name in lv.items():  # one of the file's variants may be two of OUT's: night as dusk, and as night
            if name not in mine or out in gone_names:
                continue
            over = {**({} if keep else d.shared_variants.get(name, {})), **d.variants.get(name, {})}
            if out not in doc.shared_variants:
                doc.variants.setdefault(out, {})  # there even when its keys all belong to other layers' files
            for k, c in over.items():
                owner = owners.get(k)
                if doc.resolved().get(k) == base.get(k) and k not in doc.variants.get(out, {}) \
                        and doc.shared_variants.get(out, {}).get(k) != c \
                        and (owner is None or owner is d or color(owner, out, k) == c):
                    doc.variants.setdefault(out, {})[k] = c
    return left, whose


def cmd_compose(a):
    """Stack the layers into OUT's frame. --rekey: a dry run first finds the keys that clash (in color, or in how the
    variants color them) and where they can go; those move in the layers' docs (in memory, the files stay as they are)
    and the compose runs for real."""
    layers = compose_layers(a)
    vmap = variant_map(getattr(a, "variant_map", None))
    notes = {}  # the comments on the layers' palettes, read before --rekey moves keys in memory
    for lay, *_ in layers:
        if lay.doc.path.resolve() not in notes:
            said, head = palette_notes(lay.doc)
            notes[lay.doc.path.resolve()] = (said, comment_blocks(lay.doc), head)
    gone, renamed, why = {}, {}, {}
    spec = rekey_spec(getattr(a, "rekey", None))
    if spec is not None:
        only, asked, scoped = spec
        files = {}  # path -> [its layers' docs (one per layer), their frames, the keys they draw with]
        for lay, *_ in layers:
            got = files.setdefault(lay.doc.path.resolve(), [[], [], set()])
            got[0].append(lay.doc)
            got[1].append(lay.frame)
            got[2] |= set("".join(lay.frame.grid))
        unused = sorted(k for k in (only or set()) | set(asked) if not any(k in used for *_, used in files.values()))
        if unused:
            fail("E_SELECT", f"--rekey {a.rekey}: no layer draws with {' '.join(unused)}")
        scope = scoped_to(scoped, list(files), a.rekey)  # path -> (only, asked) of FILE.px:KEY entries
        for path, (o, a_) in scope.items():
            unused = sorted(k for k in o | set(a_) if k not in files[path][2])
            if unused:
                fail("E_SELECT", f"--rekey {a.rekey}: {os.path.relpath(path)}'s layers don't draw with "
                     f"{' '.join(unused)}")
        opath = split_sel(a.o)[0]
        with reading(f"-o ({a.o})"):
            odoc = parse(opath, allow_empty=True) if pathlib.Path(opath).exists() and not getattr(a, "replace", False) \
                else None
        def move(path, moves):  # every layer's doc of that file (each layer reads its own; a map's cells share one)
            ds, frames, _ = files[path]
            each = {}
            for d, f in zip(ds, frames):
                each.setdefault(id(d), (d, []))[1].append(f)
            for d, fs in each.values():
                if moves:
                    rekey(d, moves, fs)
                gone.setdefault(id(d), set()).update(moves)
        def dry():  # where --rekey would move keys now: {path: moves}, {path: why}
            try:
                with contextlib.redirect_stdout(io.StringIO()):  # its notes are the real run's
                    return compose(a, layers, dry=True, gone=gone, vmap=vmap)
            except PxError as e:
                return getattr(e, "moves", {}), getattr(e, "why", {})
        # KEY=DSTKEY first, for the files whose KEY --rekey would move (every file drawing it, when none needs to),
        # then the free keys are found around them
        found = dry()[0] if asked else {}
        took = {}
        for path, (ds, frames, used) in files.items():
            mine = {k: j for k, j in asked.items() if k in used and (
                k in found.get(path, {}) or not any(k in found.get(p, {}) for p in files))}
            mine.update(scope.get(path, ((), {}))[1])
            if not mine:
                continue
            check_asked(mine, ds[0], odoc, opath, ds[0].path)
            moves = {k: j for k, j in mine.items() if j != k}
            move(path, moves)
            renamed[path] = moves
            why[path] = {k: ("asked", j) for k, j in mine.items()}
            took[path] = set(mine.values())
        found, whys = dry()
        needless = set(only or ()) | {k for o, _ in scope.values() for k in o}
        for path, moves in found.items():
            moves = {k: v for k, v in moves.items() if (only is None or k in only or k in scope.get(path, ((),))[0])
                     and k not in took.get(path, ())}
            needless -= set(moves)
            move(path, moves)
            renamed[path] = {**renamed.get(path, {}), **moves}
            why.setdefault(path, {}).update({k: w for k, w in whys.get(path, {}).items() if k in moves})
        if needless:
            print(f"note: --rekey {' '.join(sorted(needless))}: no other key needed; {opath} has "
                  f"{'them' if len(needless) > 1 else 'it'} in the same colors")
        renamed = {p: m for p, m in renamed.items() if m}
    compose(a, layers, gone=gone, vmap=vmap, notes=notes, renamed=renamed, moved=why)


def by_file(entries):
    """[(layer number, label, doc)] -> labels, one per source file: 'layer 3 (keeper.px:idle/down/0)' for one layer,
    'layers 1-2 (harbor.px)' for several of one file."""
    files = {}
    for n, label, d in entries:
        files.setdefault(d.path.resolve(), []).append((n, label, d))
    return [es[0][1] if len(es) == 1 else f"layers {spans([n for n, *_ in es])} ({es[0][2].path})"
            for es in files.values()]


class Note(str):
    """A compose note of a kind grouped_notes can count (kind: 'rekey', 'left', 'variant', 'merge', 'undrawn'), with
    what the count needs (data). It prints as itself."""
    def __new__(cls, text, kind, data=None):
        note = super().__new__(cls, text)
        note.kind, note.data = kind, data
        return note


GROUP_NOTES = 3  # compose prints more of these notes than this as grouped_notes, without -v


def grouped_notes(opath, lines):
    """compose's notes in short, one line per kind with its count, for a compose that has many (--rekey across packs):
    which files --rekey gave free keys, the colors a new OUT left out (keys their layers here don't draw with), the
    variants that cover only some layers and the --variant-map that merges them, and the keys OUT's frame doesn't
    draw with (that note as it is). Then how many notes that was and -v for them in full. WARNINGs aren't Notes: they
    print in full all the same."""
    notes = [line for line in lines if isinstance(line, Note)]
    of = {k: [n for n in notes if n.kind == k] for k in ("rekey", "left", "variant", "merge", "undrawn")}
    out = []
    if of["rekey"]:
        n = sum(k for _, k in (x.data for x in of["rekey"]))
        out.append(f"note: --rekey gave {n} key{'s free ones' if n > 1 else ' a free one'} in {opath}: "
                   + ", ".join(f"{path} {k}" for path, k in (x.data for x in of["rekey"]))
                   + f" (the {'files are' if len(of['rekey']) > 1 else 'file is'} unchanged)")
    if of["left"]:
        n = sum(len(ks) for _, ks in (x.data for x in of["left"]))
        out.append(f"note: {opath} left out {n} color{'s' * (n > 1)} for keys some layers don't draw with, and has "
                   "other layers' colors for them (no conflict): "
                   + "; ".join(f"{path} {' '.join(ks)}" for path, ks in (x.data for x in of["left"])))
    if of["variant"]:
        n = len(of["variant"])
        out.append(f"note: {n} of {opath}'s variants cover{'s' * (n == 1)} only some layers, the others staying at base "
                   f"colors in {'it' if n == 1 else 'each'}: "
                   + ", ".join(f"{name} ({', '.join(paths)})" for name, paths in (x.data for x in of["variant"]))
                   + "".join(f"; {x.data} gives every layer one" for x in of["merge"]))
    out += of["undrawn"]
    n = len(notes)
    return out + [f"note: that's {n} note{'s' * (n > 1)} in short; -v prints {'each' if n > 1 else 'it'} in full"]


def said_left_out(opath, doc, d, label, entries, rekey_said):
    """A new OUT left out some of d's file's keys, which none of its layers here (label) draw with, so they don't
    conflict, and which OUT has in another layer's colors: entries [(key, the layer whose color OUT has, whether it
    draws with it)]. (loud, text): loud when a key is one d's file needs (special_keys: its other frames draw with it,
    or a variant keeps it lit), with --rekey as the way to keep them."""
    why = special_keys(d)
    loud = [k for k, *_ in entries if why.get(k)]
    text = ", ".join(f"{k!r} {fmt_color(d.resolved()[k])} ({fmt_color(doc.palette[k])} there, from {kept}, which "
                     + ("draws with it" if uses else "doesn't draw with it either: the earlier layer's")
                     + (f"; {d.path.name} needs it: {', '.join(why[k])}" if why.get(k) else "") + ")"
                     for k, kept, uses in entries)
    many = label.startswith("layers ")
    who, pl = "those layers don't" if many else "that layer doesn't", len(entries) > 1
    return bool(loud), (f"{opath} leaves out {label}'s colors for {' '.join(k for k, *_ in entries)}, "
                        f"{'keys' if pl else 'a key'} {who} draw with (so {'they don' if pl else 'it doesn'}'t "
                        f"conflict), and has other layers' colors for {'them' if pl else 'it'}: {text}"
                        + (f"; {rekey_said} keeps {' '.join(loud)} under free keys in {opath}" if loud else ""))


def said_moves(src, opath, moves, why, d):
    """compose --rekey's moves for one source file, and why each key moved, grouped: 'other colors there', 'OUT's
    base color but other variant colors', or a key its layers here don't draw with that its file needs."""
    kinds = {}
    for k in moves:
        kinds.setdefault(why.get(k, ("color",))[0], []).append(k)
    said = (f"--rekey gives {src}'s keys {'other' if 'asked' in kinds else 'free'} ones in {opath}: "
            + " ".join(shlex.quote(f"{k}>{v}") for k, v in moves.items()) + f" ({src} is unchanged)")
    if set(kinds) <= {"color"}:
        return said
    parts = [f"{' '.join(kinds['asked'])} as --rekey named"] if "asked" in kinds else []
    if "color" in kinds:
        one = len(kinds["color"]) == 1
        parts.append(f"{' '.join(kinds['color'])} {'is another color' if one else 'are other colors'} there")
    if "variant" in kinds:
        ks = kinds["variant"]
        parts.append(f"{' '.join(ks)} {'have' if len(ks) > 1 else 'has'} {opath}'s base color but other variant colors")
    if "needed" in kinds:
        groups = {}
        for k in kinds["needed"]:
            groups.setdefault(tuple(why[k][1]), []).append(k)
        parts.append(f"its layers here don't draw with {' '.join(kinds['needed'])}, but {d.path.name} needs "
                     f"{'them' if len(kinds['needed']) > 1 else 'it'} (" + "; ".join(
                         f"{' '.join(ks)}: {', '.join(says)}" for says, ks in groups.items()) + ")")
    return said + ": " + "; ".join(parts)


def said_by_file(opath, layers, doc, left_out, renamed, why, vclashed, added, vmap, rekey_said, fresh):
    """compose's report, per source file in layer order, one line per reason: what --rekey moved and why (and the keys
    of OUT it could have used anyway), the keys a new OUT left out (a WARNING when the file lost a key it needs), one
    WARNING per key OUT's variants color otherwise (said_vclash), and the keys an existing OUT got at base colors in a
    variant the file hasn't got (said_uncovered)."""
    entries = [(n, label, lay.doc) for n, (lay, _, _, label) in enumerate(layers, 1)]
    files = {}
    for n, label, d in entries:
        files.setdefault(d.path.resolve(), []).append((n, label, d))
    lost = {}
    for k, gone_from, kept, uses in left_out:
        d = next(d for _, label, d in entries if label == gone_from)
        got = lost.setdefault(d.path.resolve(), {})
        got.setdefault(k, (kept, uses))
    lines, given = [], {}  # given: new key -> the file --rekey first gave it to
    for path, es in files.items():
        d = es[0][2]
        mine = why.get(path, {})
        if renamed.get(path):
            again = [k for k, v in renamed[path].items() if given.get(v, path) != path]
            whose = list(dict.fromkeys(given[renamed[path][k]] for k in again))
            lines.append(Note("note: " + said_moves(d.path, opath, renamed[path], mine, d) + (
                f"; {' '.join(again)} share the keys {' and '.join(str(w) for w in whose)} got for the same colors "
                "(in every variant too)" if again else ""), "rekey", (d.path, len(renamed[path]))))
            for v in renamed[path].values():
                given.setdefault(v, d.path)
            auto = {k: v for k, v in renamed[path].items() if mine.get(k, ("",))[0] != "asked"}
            asked = {k: w[1] for k, w in mine.items() if w[0] == "asked"}
            hint = None if fresh else same_base_hint(auto, asked, d, doc, opath)
            if hint:
                lines.append(hint)
        if lost.get(path):
            losing = [e for e in es if any(g == e[1] for _, g, *_ in left_out)]
            loud, text = said_left_out(opath, doc, d, by_file(losing)[0], [(k, *v) for k, v in lost[path].items()],
                                       rekey_said)
            lines.append(f"WARNING: {text}" if loud else Note(f"note: {text}", "left", (d.path, list(lost[path]))))
        if path in vclashed:
            lines += said_vclash(by_file(vclashed[path]["layers"])[0], d, sorted(vclashed[path]["keys"]), doc, opath,
                                 vmap, rekey_said, {w[1]: k for k, w in mine.items() if w[0] == "asked"})
        if not fresh and path in added:
            text = said_uncovered(by_file(added[path]["layers"])[0], d, doc, opath, vmap, added[path]["keys"])
            if text:
                lines.append(f"note: {text}")
    return lines


def compose(a, layers, dry=False, gone=None, vmap=None, notes=None, renamed=None, moved=None):
    """compose's run over loaded layers; dry: stop before writing (conflicts are raised all the same, with the keys they
    can move to as e.moves and why as e.why; with none, (moves, why) are returned). The moves: keys of another color,
    keys whose variants clash, and keys a new OUT would leave out that their file needs; why: {path: {key: ('color',) |
    ('variant',) | ('needed', reasons)}}. gone: {id(layer doc): keys --rekey moved away}, left out of a new OUT's
    palette. vmap: --variant-map. notes, renamed, moved: the layers' palette comments, the keys --rekey moved and why
    (carry_notes, said_by_file)."""
    vmap = vmap or {}
    opath, osel = split_sel(a.o)
    note_suffix(opath)
    replace = getattr(a, "replace", False)
    if replace and (osel or getattr(a, "under", False)):
        fail("E_BAD_ARG", f"--replace starts {opath} fresh, as if new, dropping all it has; " + (
            f"with -o {a.o} that would drop its other frames too: compose into -o {opath} (a file of one frame), or "
            "drop --replace (the frame is replaced anyway)" if osel else
            "--under draws behind the frame it has: give one"))
    fresh, under = not pathlib.Path(opath).exists() or replace, None  # under: the frame the layers go behind
    have_names = sorted({n for lay, *_ in layers for n in variant_names(lay.doc)})
    for name, ns in vmap.items():
        missing = [n for n in ns[1:] if n not in have_names]
        if missing:
            fail("E_SELECT", f"--variant-map {name}={','.join(ns[1:])}: no layer's file has @variant "
                 f"{', '.join(map(repr, missing))} (they have: {', '.join(have_names) or 'none'})")
    with reading(f"-o ({a.o})"):
        if getattr(a, "under", False) and not osel and not fresh:  # OUT's single grid, which frame_slot clears
            was = parse(opath, allow_empty=True)
            under = list(was.frames[0].grid) if was.implicit else None
        doc, target = frame_slot(opath, osel, fresh=fresh)
    replacing = bool(osel and target.grid)  # OUT:frame names a frame OUT has: said on the 'wrote' line
    kept = None if fresh else said_palette(doc)  # what OUT had, for the note
    if not fresh:  # an existing OUT keeps its variants: the map only reads the layers' variants as OUT's
        check_vmap(vmap, doc, opath, [lay.doc for lay, *_ in layers])
    if getattr(a, "under", False):  # (crop has no --under)
        under = list(target.grid) if osel else under
        if not under:
            fail("E_BAD_ARG", f"--under draws the layers behind OUT's frame, and {a.o} has none yet; compose it first "
                 "(or drop --under)")
        if a.size and parse_size(a.size) != (len(under[0]), len(under)):
            fail("E_BAD_ARG", f"--under keeps the frame being replaced, {len(under[0])}x{len(under)}; drop --size "
                 f"{a.size}")
        target.grid = under
    whose, owners, left_out = {}, {}, []  # whose: key -> the layer whose color OUT has; owners: its doc
    rekey_said = getattr(a, "words", {}).get("redo", "compose") + " --rekey"
    if fresh:
        left_out, seeded = seed_palette(doc, layers, gone, getattr(a, "used_keys_only", False), vmap, owners)
        whose = {k: w[0] for k, w in seeded.items()}
    if a.size:
        size, why = tuple(map(int, a.size.split("x"))), "--size"
    elif getattr(a, "map_size", None):
        size, why = a.map_size, "--map"
    elif target.grid:
        size, why = target.size, "the frame being replaced"
    elif osel and any(f.grid for f in doc.frames if f.group == target.group and f is not target):
        size = next(f.size for f in doc.frames if f.group == target.group and f.grid and f is not target)
        why = f"the rest of {target.group!r}"
    else:
        size, why = layers[0][0].frame.size, "the first layer"
    target.grid = ["." * size[0]] * size[1]
    # every layer's conflicts at once, before anything is drawn, gathered by source file: keys of another color
    # (clashed), keys OUT's variants color otherwise than the layer's file does (vclashed, see vclashes), and the keys
    # each file adds to an existing OUT, in its own variant colors (import_keys)
    clashed, vclashed, added = {}, {}, {}
    for n, (lay, x, y, label) in enumerate(layers, 1):
        keys = set("".join(lay.frame.grid))
        bad = clashes(doc, lay.doc, keys)
        if bad:
            c = clashed.setdefault(lay.doc.path.resolve(), {"layers": [], "keys": set()})
            c["layers"].append((n, label, lay.doc))
            c["keys"].update(bad)
        for k in vclashes(doc, lay.doc, keys - set(bad), vmap):
            c = vclashed.setdefault(lay.doc.path.resolve(), {"layers": [], "keys": set()})
            if (n, label, lay.doc) not in c["layers"]:
                c["layers"].append((n, label, lay.doc))
            c["keys"].add(k)
        for k in import_keys(doc, lay.doc, keys, vmap):
            whose[k] = label
            c = added.setdefault(lay.doc.path.resolve(), {"layers": [], "keys": []})
            if (n, label, lay.doc) not in c["layers"]:
                c["layers"].append((n, label, lay.doc))
            c["keys"].append(k)
    # where --rekey would move keys, chosen once for the whole compose so no two collide: each file's keys of another
    # color, then keys whose variants clash, then needed keys a new OUT would leave out; the E_KEY_CONFLICT lines
    # offer the same moves --rekey makes
    have, found, whys = doc.resolved(), {}, {}
    taken = set(have) | {k for lay, *_ in layers for k in lay.doc.resolved()}
    given, onames = {}, variant_names(doc)  # a color that looks the same in every variant keeps one new key

    def looks(src):
        return lambda k: (src.resolved()[k], tuple(colors_in(src, k, onames, vmap)))
    for path, c in clashed.items():
        src = c["layers"][0][2]
        moves = new_keys(sorted(c["keys"]), src.resolved(), have, taken, fits_in(doc, src, vmap), given, looks(src))
        found[path] = moves
        whys[path] = {k: ("color",) for k in moves or {}}
    for path, c in vclashed.items():
        src = c["layers"][0][2]
        moves = new_keys(sorted(c["keys"]), src.resolved(), have, taken, fits_in(doc, src, vmap), given,
                         looks(src)) or {}
        if found.get(path, {}) is not None:
            found.setdefault(path, {}).update(moves)
            whys.setdefault(path, {}).update({k: ("variant",) for k in moves})
    doc_of = {label: lay.doc for lay, _, _, label in layers}
    for k, lost, *_ in left_out:
        d = doc_of[lost]
        path = d.path.resolve()
        needs = special_keys(d)
        if k in needs and found.get(path, {}) is not None and k not in found.get(path, {}):
            moves = new_keys([k], d.resolved(), have, taken, fits_in(doc, d, vmap), given, looks(d)) or {}
            found.setdefault(path, {}).update(moves)
            whys.setdefault(path, {}).update({k: ("needed", needs[k]) for k in moves})
    if clashed:  # one line per file, covering every layer of it
        issues, copies = [], set()
        for path, c in clashed.items():
            src, ns = c["layers"][0][2], [n for n, *_ in c["layers"]]
            words = getattr(a, "words", {})
            what = words.get("what") or ("this layer" if len(ns) == 1 else "these layers")
            issue = conflict_issue(sorted(c["keys"]), src, have, what, f"the new {opath}" if fresh else opath,
                                   words.get("redo", "compose"), found[path], whose,
                                   rekey_copy(src.path, opath, copies), whys.get(path))
            issue.ctx = c["layers"][0][1] if len(ns) == 1 else f"layers {spans(ns)} ({src.path})"
            if not fresh and not osel and hasattr(a, "replace"):  # compose's plain OUT: its palette may be stale
                issue.msg += f". ({opath} exists, and keeps its palette: --replace starts it fresh, as if new)"
            issues.append(issue)
        err = PxError(issues)
        err.moves = {p: m for p, m in found.items() if m}
        err.why = whys
        raise err
    if dry:
        return {p: m for p, m in found.items() if m}, whys
    if not fresh and not osel and hasattr(a, "replace") and not getattr(a, "under", False):  # compose's plain OUT
        print(f"note: {opath} exists: keeping its palette ({kept}); --replace starts it fresh")
    for d in {id(lay.doc): lay.doc for lay, *_ in layers}.values():  # OUT's variants from a layer's import alone
        for n, src in layer_variants(d, vmap).items():
            if n in variant_names(doc):
                warn_half(d, src)
    said = said_by_file(opath, layers, doc, left_out, renamed or {}, moved or {}, vclashed, added, vmap, rekey_said,
                        fresh) + said_variants(opath, layers, doc, vmap, fresh)
    cuts = []  # the cropping notes, said after these (the drawing decides whether there is an undrawn-keys note)
    map_cut = 0  # a map's cells are one thing to crop, as scene says it
    for lay, x, y, label in layers:
        w, h = lay.frame.size
        blank = lay.doc.blanks()
        cut = sum(1 for yy, row in enumerate(lay.frame.grid) for xx, ch in enumerate(row)
                  if ch not in blank
                  and not (0 <= x + xx < size[0] and 0 <= y + yy < size[1]))
        if getattr(lay, "from_map", False):
            map_cut += cut
        elif cut and getattr(a, "cut_note", True):
            cuts.append(f"note: {cut} px of {lay.label} fall outside the {size[0]}x{size[1]} canvas "
                        f"(size from {why}) and were cropped")
        with reading(label):
            stamp(doc, target, lay.doc, lay.frame, (x, y), vmap=vmap)
    if map_cut:
        cuts.append(f"note: {map_cut} px of the map ({a.map}) fall outside the {size[0]}x{size[1]} canvas (size from "
                    f"{why}) and were cropped")
    if under:  # the frame's own pixels stay on top: the layers show only through its empty ones
        blank = doc.blanks()
        target.grid = ["".join(n if o in blank else o for o, n in zip(was, now)) for was, now in zip(under, target.grid)]
    if fresh and getattr(a, "used_keys_only", False):  # keys that landed on the canvas; a cropped-away one goes
        left = set("".join(target.grid))
        doc.palette = {k: c for k, c in doc.palette.items() if k in left}
        doc.variants = {n: {k: c for k, c in over.items() if k in left} for n, over in doc.variants.items()}
    undrawn = said_undrawn(opath, doc, target, owners) if fresh and not getattr(a, "used_keys_only", False) else None
    grouped = getattr(a, "cmd", None) == "compose" and not getattr(a, "verbose", False) and \
        sum(isinstance(line, Note) for line in said + [undrawn]) > GROUP_NOTES  # a few read fine in full
    for line in [line for line in said if not (grouped and isinstance(line, Note))] + cuts:
        print(line)
    for line in grouped_notes(opath, said + [undrawn]) if grouped else [undrawn] if undrawn else []:
        print(line)
    if fresh:
        docs = list({lay.doc.path.resolve(): lay.doc for lay, *_ in layers}.values())  # one per file
        carry_notes(doc, docs, notes or {}, renamed or {}, owners, vmap)
        carry_header(doc, {d.path.name: (notes or {}).get(d.path.resolve(), ({}, {}, []))[2] for d in docs})
    if getattr(a, "cmd", None) == "compose" and getattr(a, "argv", None) and (fresh or not osel):
        stamp_composed(doc, a.argv, opath, fresh)
    did = write_doc(doc, opath)
    wrote = did.startswith(("wrote", "would write"))  # 'no change' replaced nothing
    print(did + (f" frame {osel}" + (" (replaced the frame it had)" if replacing and wrote else "") if osel else ""))


COMPOSED_RE = re.compile(r"^#\s*composed by:\s*(.*?)\s*$")  # compose's provenance line, in a file's header
PATH_ARG_RE = re.compile(r"^(.*?\.(?:px|png|map))(?=$|[:%@+=])(.*)$", re.S)


def repointed(args, src, dst):
    """Command-line args with the path each starts with (a layer FILE.px:frame+h@x,y, -o OUT, --map room.map) read
    from directory src re-pointed to be read from dst, relative as @palette lines are (an absolute one too), since a
    path inside a file is read from its directory. Other args as they are."""
    out = []
    for x in args:
        m = PATH_ARG_RE.match(x)
        if m and not x.startswith("-"):
            x = pathlib.Path(os.path.relpath(pathlib.Path(src, m.group(1)).resolve(), pathlib.Path(dst).resolve())
                             ).as_posix() + m.group(2)
        out.append(x)
    return out


def stamp_composed(doc, argv, opath, fresh):
    """A compose OUT's header says how it was made: '# composed by: pxart compose ...', its paths re-pointed from
    OUT's directory (as a path inside a file is), so the line runs from there. A new OUT gets it; an existing one
    composed whole again has its line updated (and one without keeps its header as it is)."""
    argv = [x for x in argv[1:] if x != "--dry-run"]  # the line is the run that writes OUT
    line = "# composed by: pxart " + shlex.join(["compose"] + repointed(argv, ".", pathlib.Path(opath).parent))
    at = next((i for i, l in enumerate(doc.comments) if COMPOSED_RE.match(l)), None)
    if at is not None:
        doc.comments[at] = line
    elif fresh:
        doc.comments = [line]


def composed_from(d):
    """How d's header says it was made: ('pxart compose ...' re-pointed to run from the current directory, with
    --replace for a whole OUT (one that exists keeps its palette and variants otherwise), or None when the line has no
    command; the line as written), or None when no header line says it was composed."""
    for l in d.comments if d.path else ():
        m = COMPOSED_RE.match(l)
        if m or re.match(r"^#.*\bcomposed\b", l, re.I):
            cmd = m.group(1) if m else ""
            if cmd.startswith("pxart compose "):
                try:
                    args = shlex.split(cmd)[2:]
                except ValueError:  # unbalanced quotes: say the line as it is
                    args = None
                out = next((v for o, v in zip(args or [], (args or [])[1:]) if o == "-o"), "")
                if args is not None and "--replace" not in args and ":" not in out:  # an OUT that exists keeps its
                    args.append("--replace")  # palette, variants too, unless started fresh
                cmd = args and "pxart " + shlex.join(["compose"] + repointed(args, d.path.parent, "."))
            else:
                cmd = None
            return cmd, l.strip()
    return None


def said_undrawn(opath, doc, target, owners):
    """A new OUT gets its layers' whole palettes, so the keys its frame doesn't draw with are there on purpose (a shade
    ramp's, a recolor's), and would otherwise be a surprise in check's 'unused keys': a note naming them by file, and
    --used-keys-only. None when every key line is drawn with."""
    drawn, blank = set("".join(target.grid)), doc.blanks()
    files = {}
    for k in doc.palette:
        if k not in drawn and k not in blank:
            d = owners.get(k)
            files.setdefault(d.path.name if d is not None else "?", []).append(k)
    if not files:
        return None
    n = sum(len(ks) for ks in files.values())
    return Note(f"note: {opath} gets {n} key{'s' * (n > 1)} its frame doesn't draw with, from its layers' whole palettes "
            f"(for shade ramps and recolors): " + "; ".join(f"{name}'s {' '.join(ks)}" for name, ks in files.items())
            + f"; --used-keys-only leaves {'them' if n > 1 else 'it'} out", "undrawn")


def said_palette(doc):
    """What an OUT's palette holds, briefly: '12 keys, @palette pal.px, @variant dusk'."""
    n = len(doc.palette)
    return ", ".join([f"{n} key{'s' * (n != 1)}"] + [f"@palette {r}" for r in doc.palette_refs]
                     + [f"@variant {v}" for v in variant_names(doc)])


def said_variants(opath, layers, doc, vmap, fresh):
    """A new OUT whose variants come from layers of different files: which layers each variant covers (the others stay
    at their base colors in it), and how --variant-map would merge them."""
    lines, partial = [], []
    entries = [(n, label, lay.doc) for n, (lay, _, _, label) in enumerate(layers, 1)]
    for name in variant_names(doc) if fresh and any(variant_names(d) for *_, d in entries) else ():
        has = [e for e in entries if name in layer_variants(e[2], vmap)]
        lacks = [e for e in entries if e not in has]
        if lacks:
            partial.append(name)
            them = by_file(lacks)
            lines.append(Note(f"note: {opath}'s @variant {name} covers {' and '.join(by_file(has))} only: "
                              f"{' and '.join(them)} {'stays' if len(them) == 1 and len(lacks) == 1 else 'stay'} at "
                              "base colors in it", "variant", (name, list(dict.fromkeys(str(e[2].path) for e in has)))))
    if len(partial) > 1 and not vmap:
        lines.append(Note(f"note: to give every layer one variant, merge them: --variant-map {partial[0]}="
                          f"{','.join(partial[1:])} (each layer takes the first of {', '.join(partial)} its file has)",
                          "merge", f"--variant-map {partial[0]}={','.join(partial[1:])}"))
    return lines


def baked(doc, variant):
    """A --map legend entry FILE:frame%V as a compose layer: doc (parsed for this entry alone) with V's colors as its
    base palette, every key its own and no variants, so the layer draws in V's colors in OUT's base and every variant,
    as scene draws it. It goes by FILE%V, a file of its own to compose, --rekey and the notes."""
    pal = doc.resolved(variant)
    warn_half(doc, variant)
    doc.palette = {k: c for k, c in pal.items() if k != "."}
    doc.shared, doc.shared_variants, doc.variants, doc.palette_refs = {}, {}, {}, []
    doc.path = doc.path.with_name(f"{doc.path.name}%{variant}")
    doc.made = f"{doc.path.name} is a --map legend entry in its variant's colors, made in memory"
    return doc


def png_layer(path, img, keyof, taken):
    """A --map legend entry that is a PNG as a compose layer: a one-grid doc of its colors, each under a key no other
    layer's file (nor OUT) has, so no variant of OUT recolors it, as scene draws it; PNGs share keys for one color
    (keyof). Pixels whose alpha is 0 are '.'."""
    d = Doc(path)
    d.made = f"{path.name} is a --map legend entry, a PNG made into keys in memory"
    grid = []
    for y in range(img.height):
        row = ""
        for x in range(img.width):
            c = img.getpixel((x, y))
            if not c[3]:
                row += "."
                continue
            if c not in keyof:
                free = [k for k in FREE_ORDER if k not in taken]
                if not free:
                    fail("E_BAD_ARG", f"--map: {path} needs more palette keys than there are ({len(KEYS)})")
                keyof[c] = free[0]
                taken.add(free[0])
            d.palette[keyof[c]] = c
            row += keyof[c]
        grid.append(row)
    d.frames, d.implicit = [Frame(None, grid)], True
    return d


def map_layers(a):
    """compose --map MAP [--tile N]: the map's cells as layers, in scene's order (layer by layer, row by row), each
    at the spot scene draws it (cell_spot: top-left, or +b bottom-aligned); returns them and the map's size. A legend
    entry with its own %VARIANT is baked, a PNG made into keys (png_layer)."""
    tile = parse_tile(a.tile)
    notes = []
    with reading(f"--map ({a.map})"):
        placed, size = read_map(a.map, tile, notes)
        its = load_legend(a.map)
    for n in notes:
        print("note:", n)
    legend, _, _, where = parse_map(a.map)
    written = {arg: (ch, w) for ch, arg, w in legend_entries(legend, where)}
    for arg, it in its.items():
        variant = split_variant(split_flip(arg)[0])[1]
        if it.doc is not None and variant:
            it.doc = baked(it.doc, variant)
    opath = split_sel(a.o)[0]
    taken = {k for it in its.values() if it.doc is not None for k in it.doc.resolved()}
    if pathlib.Path(opath).exists() and not getattr(a, "replace", False):
        with reading(f"-o ({a.o})"):
            taken |= set(parse(opath, allow_empty=True).resolved())
    keyof = {}
    for arg, it in its.items():
        if it.doc is None:
            it.doc = png_layer(pathlib.Path(split_variant(split_flip(arg)[0])[0]), it.img, keyof, taken)
            it.frame = it.doc.frames[0]
        it.from_map = True
    layers = []
    for arg, x, y in placed:
        it = its[arg]
        ch, path = written[arg]
        layers.append((it, *cell_spot(arg, it.img, x, y, tile), f"--map ({a.map}) {ch!r} ({path})"))
    return layers, size


def compose_layers(a):
    layers = []
    if getattr(a, "map", None):
        layers, a.map_size = map_layers(a)
    elif not a.layers:
        fail("E_BAD_ARG", "compose needs layers, LAYER@x,y ..., or a tilemap: --map MAP")
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


def cmd_dup(a):
    path, sel = split_sel(a.src)
    one_id(sel, a.src, "SRC")
    one_id(a.new, a.new, "NEWID")
    with reading(f"FILE ({a.src})"):
        doc = parse(path)
    src = doc.get(sel) if sel else None
    if not src and sel and any((f.id or "").startswith(sel + "/") for f in doc.frames):  # a group: dup GROUP NEWGROUP
        note_suffix(a.o or doc.path)
        print("; ".join(dup_group(doc, sel, a.new, a.after, a.o or doc.path, replace=a.replace)[0]
                        + [write_doc(doc, a.o)]))
        return
    if not src:
        fail("E_SELECT", f"dup needs FILE:frame-id of an existing frame, or FILE:GROUP; {doc.listing()}"
             + (guess(sel, doc.paths()) if sel else ""))
    if not ID_RE.match(a.new):
        fail("E_BAD_ID", f"can't use {a.new!r} as the new frame id")
    old = doc.get(a.new)
    if old is src:
        fail("E_BAD_ARG", f"{a.new!r} is the frame being copied; give another id")
    if old and not a.replace:
        fail("E_DUP_FRAME", f"{doc.path} already has frame {a.new!r}; to replace it, add --replace, or remove it "
             f"first: pxart frames {doc.path} --rm {a.new}")
    new = Frame(a.new, list(src.grid), src.ms, pivot=src.pivot)
    if old:  # the copy takes its place, and its comments
        if a.after:
            fail("E_BAD_ARG", f"--replace puts the copy where {a.new!r} is; drop --after, or move it after: "
                 f"frames {doc.path} --move {a.new} --after ID")
        doc.frames[doc.frames.index(old)] = new
        note_suffix(a.o or doc.path)
        print(write_doc(doc, a.o), "frame", a.new, "(replaced the frame it had)")
        return
    stilled = [as_still(new, doc, src, doc)] if doc.animated(src.group) and not doc.animated(new.group) else []
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
        place_anim(doc, new.group)
    note_suffix(a.o or doc.path)
    if stilled:
        print(said_stilled(stilled, a.o or doc.path))
    print(write_doc(doc, a.o), "frame", a.new)


def dup_group(doc, group, new, after=None, dpath=None, how=None, replace=False):
    """dup FILE:GROUP NEWGROUP: every frame under GROUP copied under NEWGROUP (walk/right/0 -> walk/left/0), with its
    ms and pivot, and the @anim and @still lines of GROUP and the groups under it, placed as dup places a frame: after
    NEWGROUP's last frame, else after GROUP's (or --after ID). replace: NEWGROUP's frames (and their @anim/@still lines)
    go first, and the copies take their place. how: the command, for E_DUP_FRAME. Returns (what it did, for the line;
    the copies)."""
    if not ID_RE.match(new):
        fail("E_BAD_ID", f"can't use {new!r} as the new group (ids are paths of letters, digits, _ - and .)")
    if new == group or new.startswith(group + "/"):
        fail("E_BAD_ARG", f"{new!r} is inside {group!r}: its copies would be copied too; give another group")
    if replace and group.startswith(new + "/"):
        fail("E_BAD_ARG", f"--replace removes {new!r}'s frames, and {group!r} is inside it; give another group")
    src = [f for f in doc.frames if (f.id or "").startswith(group + "/")]
    renames = [(group, new)]
    old = [f for f in doc.frames if (f.id or "").startswith(new + "/")] if replace else []
    taken = [renamed_id(f.id, renames) for f in src if doc.get(renamed_id(f.id, renames)) and not replace]
    if taken:
        fail("E_DUP_FRAME", f"{listed(taken)} already in {doc.path}: {how or f'dup {group} {new}'} would give those ids "
             f"twice; to replace {new}, add --replace, or remove it first: pxart frames {doc.path}:{new} --rm")
    if after:
        anchor = doc.get(after)
        if not anchor or anchor in old:
            fail("E_SELECT", f"--after {after!r}: no such frame" + (f" once --replace removes {new}" if anchor else
                                                                  guess(after, [f.id for f in doc.frames])))
    said, stilled, copies = [], [], []
    lines, had = {x for x, _, _ in doc.lines()}, set(doc.anims) | set(doc.stills)
    at = doc.frames.index(old[0]) if old else None  # the copies take the replaced frames' place
    if old:
        groups = set(doc.groups())
        for f in old:
            doc.frames.remove(f)
        drop_orphans(doc, groups - set(doc.groups()))
    if not after and at is None:
        same = [f for f in doc.frames if (f.id or "").startswith(new + "/")]
        anchor = (same or src)[-1]
    placed = []
    for g in dict.fromkeys(f.group for f in src):
        n = renamed_id(g, renames)
        if g in doc.anims and n not in doc.anims:
            doc.anims[n] = dict(doc.anims[g])
            placed.append(n)
            said += [] if n in had else [f"added @anim {n}"]
        if g in doc.stills and n not in doc.stills:
            doc.stills.append(n)
            said += [] if n in had else [f"added @still {n}"]
    at = doc.frames.index(anchor) + 1 if after or at is None else at
    for f in src:
        c = Frame(renamed_id(f.id, renames), list(f.grid), f.ms, pivot=f.pivot)
        doc.frames.insert(at, c)
        at += 1
        copies.append(c)
        if doc.animated(f.group) and not doc.animated(c.group):
            stilled.append(as_still(c, doc, f, doc))
    for n in placed:
        place_anim(doc, n)
    if old:  # a replaced id that no copy took leaves its blank lines to the next line
        keep_spacing(doc, lines - {x for x, _, _ in doc.lines()})
    if stilled:
        print(said_stilled(stilled, dpath or doc.path))
    return [f"copied {group} ({len(src)} frame{'s' * (len(src) != 1)}) as {new}"
            + (f", replacing its {len(old)} frame{'s' * (len(old) != 1)}" if old else "")] + said, copies


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
    one_id(sel, a.target, "FILE")
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
        if not anim:
            place_anim(doc, sel)
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
                 f"{', '.join(g for g in groups if g) or 'none'}" + guess(sel, doc.paths()), path=doc.path)
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


def key_color(m):
    """palette --add's 'k=#rrggbb', or a palette line as the file has it, 'k #rrggbb': (key, rgba)."""
    got = PAL_RE.match(m.strip())
    k, v = got.groups() if got else (m[0], m[2:]) if len(m) >= 2 and m[1] == "=" else m.partition("=")[::2]
    if not COLOR_RE.match(v) and v != "transparent":
        fail("E_BAD_COLOR", f"{m!r}: want key=#rrggbb, key=#rrggbbaa or key=transparent (or 'k #rrggbb')")
    if len(k) != 1:
        fail("E_BAD_KEY", f"{k!r}: keys are one character")
    return k, CLEAR if v == "transparent" else hex2rgba(v)


def cmd_palette(a):
    """-o OUT and --dry-run go with the edit modes; the listing and --export write no edited FILE."""
    edits = a.add or a.keep or a.derive_from is not None or a.comment or a.comment_header is not None or a.remove \
        or a.order or a.import_ or a.hoist or (a.extract_to and a.repoint)
    for flag, on in ((f"-o {a.o}", a.o), ("--dry-run", a.dry_run)):
        if on and not edits:
            fail("E_BAD_ARG", f"{flag} goes with an edit of FILE (--add, --variant, --remove, --order, --import, "
                 "--hoist, --comment, --extract-to --repoint): " + ("the listing writes nothing" if not
                 (a.export or a.extract_to) else f"{'--export' if a.export else '--extract-to'} writes its own file"))
    if a.o and a.hoist:
        fail("E_BAD_ARG", f"-o {a.o} writes an edited copy of FILE, and --hoist edits the palette file FILE imports "
             "too; run it without -o (--dry-run shows both changes)")
    if a.o and a.export:
        fail("E_BAD_ARG", f"-o {a.o} writes an edited copy of FILE; --export writes its own file: give them apart")
    palette_edit(a)


def palette_edit(a):
    with reading(f"FILE ({a.file})"):
        doc = parse(a.file, palette_only=not _has_grid(a.file))
    if a.o:
        doc.dest = pathlib.Path(a.o)
        note_suffix(doc.dest)
        if a.remove and any(k not in doc.palette for k in key_list(a.remove, "--remove")):
            fail("E_BAD_ARG", f"-o {a.o} writes an edited copy of FILE, and --remove of an imported key edits the "
                 "palette file that defines it too; run it without -o (--dry-run shows both changes)")
    if a.within and not os.path.isdir(a.within):
        fail("E_FILE", f"--in {typed_path(a.within)}: not a directory")
    notes = comment_args(a.comment)
    derive = a.derive_from is not None
    if (a.darken is not None or a.tint or a.keep_lit or a.match or a.lift_darks) and not derive:
        fail("E_BAD_ARG", "--darken, --tint, --match, --lift-darks and --keep-lit shape a derived variant: give them "
             "with --variant NAME --derive-from base|VARIANT")
    if derive and not a.variant:
        fail("E_BAD_ARG", f"--derive-from {a.derive_from} builds a variant: give --variant NAME (the one it writes)")
    if (a.keep or a.variant) and not (a.variant and (a.add or a.keep or notes or derive)):
        fail("E_BAD_ARG", "--keep KEYS goes with --variant NAME (the variant they inherit the base colors in)"
             if a.keep else f"--variant {a.variant} goes with --add 'k=#rrggbb' (set k in it), --keep KEYS (let "
             "them inherit the base colors) or --comment KEY 'text' (the comment above k's line in it)")
    if a.to is not None and not a.remove:
        fail("E_BAD_ARG", f"--to {a.to} goes with --remove KEYS: their pixels become {a.to} before the keys go")
    if a.order:
        given = [f for f, v in (("--add", a.add), ("--variant", a.variant), ("--keep", a.keep), ("--hoist", a.hoist),
                                ("--extract-to", a.extract_to), ("--export", a.export), ("--comment", notes),
                                ("--derive-from", a.derive_from), ("--remove", a.remove),
                                ("--import", a.import_)) if v] \
            + (["--comment-header"] if a.comment_header is not None else [])
        if given:
            fail("E_BAD_ARG", f"--order moves FILE's key lines: give it alone, not with {', '.join(given)}")
        print(order_keys(doc, key_list(a.order, "--order")))
        return
    if a.import_:
        given = [f for f, v in (("--add", a.add), ("--variant", a.variant), ("--keep", a.keep), ("--hoist", a.hoist),
                                ("--extract-to", a.extract_to), ("--export", a.export), ("--comment", notes),
                                ("--derive-from", a.derive_from), ("--remove", a.remove)) if v] \
            + (["--comment-header"] if a.comment_header is not None else [])
        if given:
            fail("E_BAD_ARG", f"--import adds a @palette line to FILE: give it alone, not with {', '.join(given)}")
        print(import_palette(doc, a.import_))
        return
    if a.remove:
        given = [f for f, v in (("--add", a.add), ("--variant", a.variant), ("--keep", a.keep), ("--hoist", a.hoist),
                                ("--extract-to", a.extract_to), ("--export", a.export), ("--comment", notes),
                                ("--derive-from", a.derive_from)) if v] \
            + (["--comment-header"] if a.comment_header is not None else [])
        if given:
            fail("E_BAD_ARG", f"--remove takes keys out of FILE: give it alone (or with --to KEY), not with "
                 f"{', '.join(given)}")
        print(remove_keys(doc, key_list(a.remove, "--remove"), a.to, a.within))
        return
    if a.hoist and (a.add or a.variant or a.extract_to or notes or a.comment_header is not None):
        fail("E_BAD_ARG", "--hoist moves keys into the imported palette file: give it alone")
    if (notes or a.comment_header is not None) and (a.extract_to or a.export):
        fail("E_BAD_ARG", "--comment and --comment-header edit FILE; run --extract-to or --export after")
    said = []
    if derive:
        said += derive_variant(doc, a.variant, a.derive_from, a.darken or 0.0, a.tint,
                               key_list(a.keep_lit, "--keep-lit") if a.keep_lit else [],
                               match_fit(a.match, a.variant) if a.match else None, a.lift_darks)
    if a.variant and (a.add or a.keep):
        said += variant_edit(doc, a.variant, [key_color(m) for m in a.add or []], key_list(a.keep, "--keep")
                             if a.keep else [])
    elif a.add:
        adds = [key_color(m) for m in a.add]
        same = [(k, c) for k, c in adds if doc.resolved().get(k) == c and k in doc.palette]
        new = [(k, c) for k, c in dict(adds).items() if k not in doc.resolved()]
        for k, c in adds:
            doc.add_key(k, c)
        said += ([f"added {', '.join(f'{k} {fmt_color(c)}' for k, c in new)}"] if new else []) \
            + ([said_already(same)] if same else [])
    if notes or a.comment_header is not None:
        said += set_comments(doc, notes, a.variant, a.comment_header)
    if a.add or a.keep or notes or a.comment_header is not None or derive:
        print("; ".join(said + [write_doc(doc)]))
    if a.hoist:
        print(hoist(doc, key_list(a.hoist, "--hoist")))
        return
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
        if not DRY["run"]:
            outpath(a.export).write_text(body)
        if any(v[3] < 255 for _, v in cols):
            print("note: .gpl/.hex carry no alpha; translucent colors were written opaque")
        print("would write" if DRY["run"] else "wrote", a.export)
    if a.add or a.keep or a.export or a.extract_to or notes or a.comment_header is not None or derive:
        return
    if a.within and doc.frames:
        fail("E_BAD_ARG", f"--in {a.within} counts the files that import a palette file, and {doc.path} has frames: "
             "its own column says how often each key is used")
    by = palette_users(doc, a.within) if a.within else None
    cmts, head = palette_notes(doc)
    for l in head:
        print(l)
    if by is not None:
        print(f"imported by {len(by)} of the .px files under {a.within}" + (f": {listed(sorted(by), 5)}" if by else ""))
    for k, v in pal.items():
        src = "shared" if k in doc.shared and k not in doc.palette else ("local" if k != "." else "built-in")
        use = f" used {used.get(k, 0)}" if doc.frames else ""
        if by is not None and k != ".":
            n = sum(1 for ks in by.values() if k in ks)
            use = f" used by {n} file{'s' * (n != 1)}"
        said = comment_text(cmts.get(("key", k)))
        print((f"{k} {fmt_color(v):11} {src:8}" + use).rstrip() + (f"  {said}" if said else ""))
    names = sorted(set(doc.variants) | set(doc.shared_variants))
    if names:
        print("variants:", ", ".join(names))
    for name in names:  # what each recolors (darker, brighter), relists in its base color (a lamp kept lit), leaves
        over = {**doc.shared_variants.get(name, {}), **doc.variants.get(name, {})}
        sets = [k for k in pal if k in over and k != "." and over[k] != pal[k]]
        same = [k for k in pal if k in over and k != "." and over[k] == pal[k]]
        keeps = [k for k in pal if k not in over and k != "."]
        how = {}
        for k in sets:
            d = brightness(over[k]) - brightness(pal[k])
            how.setdefault("darker" if d < 0 else "brighter" if d > 0 else "as bright", []).append(k)
        parts = ([f"recolors (darker) {' '.join(how['darker'])}"] if "darker" in how else []) \
            + ([f"recolors (as bright) {' '.join(how['as bright'])}"] if "as bright" in how else []) \
            + ([f"brightens {' '.join(how['brighter'])}"] if "brighter" in how else [])
        print(f"  {name}: {'; '.join(parts) or 'recolors nothing'}"
              + (f"; relists unchanged: {' '.join(same)}" if same else "")
              + f"; inherits: {' '.join(keeps) or 'nothing'}")
        for l in [l for l in cmts.get(("variant", name), []) if l.strip()]:
            print(f"    {l.strip()}")
        for _, ks in half_variants(doc, name):
            print(f"    WARNING: {said_half(doc, name, ks)}")
        for k in pal:
            said = comment_text(cmts.get(("vkey", name, k)))
            if said:
                print(f"    {k}: {said}")


def brightness(c):
    """How bright a color looks (Rec. 709 luma of its rgb, times its alpha), for palette's darker/brighter."""
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) * c[3] / 255


def comment_text(lead):
    """The comment lines above a line as one run of text ('# a' '# b' -> '# a / b'), or '' when there are none."""
    got = [l.strip().lstrip("#").strip() for l in lead or [] if l.strip()]
    return "# " + " / ".join(g for g in got if g) if any(got) else ""


def palette_users(doc, within):
    """palette PAL --in DIR: {path of each .px under DIR that imports PAL (through its @palette chain): the keys of PAL
    its frames draw with, those it doesn't define itself}."""
    target, out = doc.path.resolve(), {}
    for p in in_dirs([within]):
        if pathlib.Path(p).resolve() == target:
            continue
        try:
            d = parse(p, allow_empty=True)
        except (OSError, PxError):
            continue
        if target in import_chain(d):
            drawn = set("".join(r for f in d.frames for r in f.grid))
            out[p] = {k for k in drawn if k not in d.palette and k in doc.palette}
    return out


def import_chain(d, seen=None):
    """The resolved paths of every palette file d imports, directly or through another."""
    seen = set() if seen is None else seen
    for ref in d.palette_refs:
        t = (d.path.parent / ref).resolve()
        if t in seen:
            continue
        seen.add(t)
        try:
            import_chain(parse(t, palette_only=True), seen)
        except (OSError, PxError):
            pass
    return seen


def said_already(same, where=""):
    """palette --add of keys that already have those colors: 'k is already #0f0f22 in dusk; unchanged'."""
    return ", ".join(f"{k} is already {fmt_color(c)}" for k, c in same) + f"{where}; unchanged"


def variant_edit(doc, name, adds, keeps):
    """palette FILE --variant NAME --add 'k=#hex' ... --keep KEYS: set keys' colors in the variant (it is made when
    FILE has none by that name) and let others inherit the base colors: a local line goes, and a key an imported
    variant recolors gets its base color on a local line, since the import can't change from here. What it did."""
    if name == "base" or not re.match(r"^[A-Za-z0-9_\-]+$", name):
        fail("E_BAD_ARG", f"--variant {name!r}: a variant name is letters, digits, _ and -, and not 'base' (%base "
             "means the base palette)")
    both = sorted({k for k, _ in adds} & set(keeps))
    if both:
        fail("E_BAD_ARG", f"--add and --keep both name {''.join(both)!r}: a key is set in the variant or inherits "
             "the base color, not both")
    have = name in doc.variants or name in doc.shared_variants
    if keeps and not adds and not have:
        fail("E_SELECT", f"--keep: {doc.path} has no @variant {name!r} (have: "
             f"{', '.join(sorted(set(doc.variants) | set(doc.shared_variants))) or 'none'})"
             + guess(name, variant_names(doc)), path=doc.path)
    base = doc.resolved()
    for k in [k for k, _ in adds] + keeps:
        if k not in base or k == ".":
            fail("E_VARIANT_KEY", f"@variant {name} can't set {k!r}: the base palette doesn't define it (add it first: "
                 f"pxart palette {doc.path} --add '{k}=#rrggbb')", path=doc.path)
    said = [f"@variant {name}" if have else f"new @variant {name}"]
    same = [(k, c) for k, c in adds if doc.variants.get(name, {}).get(k) == c]  # its line says so already
    sets = [(k, c) for k, c in adds if (k, c) not in same]
    for k, c in sets:
        doc.variants.setdefault(name, {})[k] = c
    if sets:
        said.append("sets " + " ".join(f"{k} {fmt_color(c)}" + (" (its base color)" if c == base[k] else "")
                                      for k, c in sets))
    if same:
        said.append(said_already(same, f" in {name}"))
    gone, pinned, already = [], [], []
    for k in keeps:
        if k in doc.variants.get(name, {}):
            del doc.variants[name][k]
            doc.lead.pop(("vkey", name, k), None)
            gone.append(k)
        if doc.resolved(name)[k] != base[k]:  # an imported variant recolors it: say the base color here
            doc.variants.setdefault(name, {})[k] = base[k]
            pinned.append(k)
        elif k not in gone:
            already.append(k)

    def inherit(ks, what):
        return f"{' '.join(ks)} {what}" + ("s the base color" if len(ks) == 1 else " the base colors")
    if [k for k in gone if k not in pinned]:
        said.append(inherit([k for k in gone if k not in pinned], "inherit"))
    if pinned:
        said.append(f"{' '.join(pinned)} listed in {'its base color' if len(pinned) == 1 else 'their base colors'} "
                    f"(the imported @variant {name} recolors {'it' if len(pinned) == 1 else 'them'})")
    if already:
        said.append(inherit(already, "already inherit"))
    return said


DARK = 64  # derive never brightens a key darker than this (Rec. 709 luma of 255): an outline stays an outline


def derive_variant(doc, name, src, darken, tint, lit, match=None, lift=False):
    """palette FILE --variant NAME --derive-from base|VARIANT [--match FILE%V] [--darken F] [--tint COLOR]
    [--keep-lit KEYS] [--lift-darks]: NAME's line for every key of FILE's palette (imported keys too), in its color in
    `src` (the base palette, or a variant) mapped channel by channel as --match's file maps its base to its variant
    (match: (label, [(gain, offset)] * 3, how many keys it was fitted on)), made darker (each channel times 1 - F) and
    then tinted (COLOR laid over at its alpha, as scene --tint does); the --keep-lit keys keep their `src` color (a
    lamp). A key darker than DARK never comes out brighter (scaled back to its own brightness, the hue kept) unless
    lift. A key that comes out in its base color gets no line (it inherits), unless it is kept lit (then it is listed:
    a relist). NAME is made when FILE has none. What it did."""
    if name == "base" or not re.match(r"^[A-Za-z0-9_\-]+$", name):
        fail("E_BAD_ARG", f"--variant {name!r}: a variant name is letters, digits, _ and -, and not 'base'")
    if not 0 <= darken <= 1:
        fail("E_BAD_ARG", f"--darken {darken:g}: want a fraction from 0 (as is) to 1 (black), like 0.35")
    have = sorted(set(doc.variants) | set(doc.shared_variants))
    if src != "base" and src not in have:
        fail("E_SELECT", f"--derive-from {src}: {doc.path} has no @variant {src!r} (have: {', '.join(have) or 'none'}; "
             "or base, the base palette)" + guess(src, have + ["base"]), path=doc.path)
    base = doc.resolved()
    from_ = doc.resolved(None if src == "base" else src)
    for k in lit:
        if k not in base or k == ".":
            fail("E_VARIANT_KEY", f"--keep-lit {k!r}: the base palette doesn't define it", path=doc.path)
    color = parse_color(tint, "--tint") if tint else None
    made = name not in doc.variants and name not in doc.shared_variants
    own = name in doc.shared_variants  # an imported variant: FILE's own keys only; the import colors the rest
    had = name in doc.variants
    over = doc.variants.setdefault(name, {})
    recolored, held = [], []
    for k, c in base.items():
        if k == "." or not c[3] or (own and k not in doc.palette):
            continue
        if k in lit:
            got = from_[k]
        else:
            got = derived(matched(from_[k], match[1]) if match else from_[k], darken, color)
            if brightness(from_[k]) < DARK * from_[k][3] / 255 and brightness(got) > brightness(from_[k]):
                held.append(k)  # with lift: brightened, as asked
                got = got if lift else no_brighter(got, from_[k])
        if got == c and k not in lit:
            if k in over:
                del over[k]
                doc.lead.pop(("vkey", name, k), None)
            continue
        over[k] = got
        if got != c:
            recolored.append(k)
    if own and not had and not over:  # every key is imported, and the import's variant colors them all: nothing to add
        del doc.variants[name]
        print(f"note: {doc.path}'s keys all come from {' and '.join(doc.palette_refs)}, whose @variant {name} colors "
              f"them; no @variant {name} of its own to write (derive it in the palette file instead)" if not
              doc.palette else f"note: the derive leaves {doc.path}'s own keys at their base colors; no @variant "
              f"{name} of its own to write")
    how = ", ".join(([f"darkened {darken:.0%}"] if darken else []) + ([f"tinted {fmt_color(color)}"] if color else []))
    how = "; ".join(([f"matched {match[0]}, fitted on {match[2]} keys: {said_fit(match[1])}"] if match else [])
                    + ([how] if how else []))
    said = [f"new @variant {name}" if made else f"@variant {name}",
            f"derived from {src}" + (f" ({how})" if how else "") + f": recolors {len(recolored)} key(s)"
            + (f" of its own ({' and '.join(doc.palette_refs)}'s {name} colors the imported ones)" if own else "")]
    if lit:
        said.append(f"{' '.join(lit)} kept lit (in {'their' if len(lit) > 1 else 'its'} {src} "
                    f"color{'s' * (len(lit) > 1)})")
    if lift:  # the hold is off: say which dark keys it would have held
        said.append(f"--lift-darks: {' '.join(held)} brightened (darker than a quarter; the hold would have kept "
                    f"{'them' if len(held) > 1 else 'it'} dark)" if held else "--lift-darks: no dark key brightened")
    elif held:
        said.append(f"{' '.join(held)} held no brighter than {'their' if len(held) > 1 else 'its'} {src} "
                    f"color{'s' * (len(held) > 1)} by Rec. 709 luma (darker than a quarter: an outline stays dark; "
                    "--lift-darks lets the derive brighten them)")
    else:
        said.append("held: none (no key darker than a quarter came out brighter)")
    return said


def no_brighter(c, ref):
    """c scaled down (each channel, floored) to ref's brightness (Rec. 709 luma) at most: its hue kept, its luma never
    above ref's (a channel steps down where float rounding would leave it a hair over)."""
    b = brightness(c)
    if b <= brightness(ref):
        return c
    f = brightness(ref) / b
    out = [int(v * f) for v in c[:3]]
    while brightness(tuple(out) + (c[3],)) > brightness(ref) and any(out):
        out = [max(0, v - 1) for v in out]
    return tuple(out) + (c[3],)


def matched(c, fit):
    """One color through --match's per-channel map: each channel times its gain plus its offset, clamped."""
    return tuple(max(0, min(255, int(round(g * v + o)))) for v, (g, o) in zip(c[:3], fit)) + (c[3],)


def said_fit(fit):
    """'r x0.92 -17, g x0.81 -11, b x0.78 +10'."""
    return ", ".join(f"{ch} x{g:.2f} {o:+.0f}" for ch, (g, o) in zip("rgb", fit))


def match_fit(spec, name):
    """--match FILE[%VARIANT] (or FILE:VARIANT): the per-channel map, gain and offset by least squares, that takes
    FILE's base colors to their VARIANT colors (default: the variant being derived) over the keys VARIANT recolors
    (a key it lists unchanged, a lamp, isn't the mood). (label, [(gain, offset)] * 3, how many keys)."""
    path, sep, var = spec.rpartition("%") if "%" in spec else spec.rpartition(":") if re.search(
        r"\.px:[A-Za-z0-9_\-]+$", spec) else (spec, "", "")
    var = var or name
    with reading(f"--match ({spec})"):
        d = parse(path, palette_only=not _has_grid(path))
        base, look = d.resolved(), d.resolved(var)
    pairs = [(base[k], look[k]) for k in base if k != "." and base[k][3] and look[k] != base[k]]
    if len(pairs) < 2:
        fail("E_BAD_ARG", f"--match {spec}: {path}'s @variant {var} recolors {len(pairs)} key(s); a fit needs 2 or "
             "more")
    fit = []
    for ch in range(3):
        xs, ys = [p[0][ch] for p in pairs], [p[1][ch] for p in pairs]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        g = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 1.0
        fit.append((g, my - g * mx))
    return f"{path}'s {var}", fit, len(pairs)


def derived(c, darken, tint):
    """One color of derive_variant: each channel times 1 - darken, then `tint` laid over at its alpha (as scene
    --tint lays it over a scene); the alpha stays."""
    rgb = tuple(int(round(v * (1 - darken))) for v in c[:3]) + (c[3],)
    if tint is None:
        return rgb
    return tinted(Image.new("RGBA", (1, 1), rgb), tint).getpixel((0, 0))


def comment_args(given):
    """palette --comment's arguments: each --comment holds one or more of 'KEY TEXT', '@variant NAME TEXT' and
    '"@variant NAME" TEXT', in turn (--comment y 'lamp' E 'flame'). [((kind, name), text)], kind 'key' or 'variant'."""
    out = []
    for g in given or []:
        i = 0
        while i < len(g):
            if g[i] == "@variant" and i + 2 < len(g):
                out.append((("variant", g[i + 1]), g[i + 2]))
                i += 3
            elif g[i].startswith("@variant ") and i + 1 < len(g):
                out.append((("variant", g[i].split(None, 1)[1].strip()), g[i + 1]))
                i += 2
            elif len(g[i]) == 1 and g[i] != "@" and i + 1 < len(g):
                out.append((("key", g[i]), g[i + 1]))
                i += 2
            else:
                fail("E_BAD_ARG", f"--comment {' '.join(map(shlex.quote, g))}: want --comment KEY 'text' or --comment "
                     f"@variant NAME 'text', one or more in turn (--comment y 'lamp' E 'flame'); {g[i]!r} "
                     + ("has no text after it" if len(g[i]) == 1 or g[i].startswith("@variant") else
                        "isn't a key (one character) or @variant NAME") + " ('' removes a comment)")
    return out


def comment_lines(text):
    """'text' as comment lines: one '# ' line per line of it (a leading '#' is kept, not doubled); '' is none."""
    return [l if l.startswith("#") else f"# {l}".rstrip() for l in text.split("\n")] if text.strip() else []


def set_comments(doc, notes, variant=None, header=None):
    """palette --comment KEY|@variant NAME 'text' and --comment-header 'text': the comment lines right above that line
    of FILE (with --variant NAME, KEY is its line in that variant), or above the file's first line, become the text
    (one '# ' line per line of it); '' removes them. Blank lines above stay where they were. What it did."""
    said = []
    default = {anchor: gap for anchor, gap, _ in doc.lines()}
    for (kind, name), text in notes:
        if kind == "variant":
            if variant and variant != name:
                fail("E_BAD_ARG", f"--comment @variant {name} names its variant, and --variant {variant} another; "
                     f"comment @variant {variant} or drop --variant {variant}")
            if name not in doc.variants:
                fail("E_SELECT", f"--comment @variant {name}: {doc.path} has no @variant line {name!r}" + (
                    f" (it imports that variant; comment it in the palette file: pxart palette "
                    f"{doc.palette_refs[0] if len(doc.palette_refs) == 1 else 'P.px'} --comment @variant {name} ...)"
                    if name in doc.shared_variants else
                    f" (it has: {', '.join(doc.variants) or 'none'})" + guess(name, doc.variants)), path=doc.path)
            anchor, what = ("variant", name), f"@variant {name}"
        elif variant:
            if name not in doc.variants.get(variant, {}):
                fail("E_SELECT", f"--variant {variant} --comment {name}: @variant {variant} of {doc.path} has no line "
                     f"for {name!r} (give it one: palette {doc.path} --variant {variant} --add '{name}=#rrggbb')",
                     path=doc.path)
            anchor, what = ("vkey", variant, name), f"{name} in @variant {variant}"
        else:
            if name not in doc.palette:
                fail("E_SELECT", f"--comment {name}: {name!r} isn't one of {doc.path}'s own key lines" + (
                    f" (it comes from {doc.palette_refs[0] if len(doc.palette_refs) == 1 else 'an import'}; "
                    f"comment it there)" if name in doc.shared else ""), path=doc.path)
            anchor, what = ("key", name), name
        was = doc.lead.get(anchor)
        lead = list(was) if was is not None else [""] * default.get(anchor, 0)
        new = [l for l in lead if not l.strip()] + comment_lines(text)
        if new == lead:
            said.append(f"the comment above {what} is already that; unchanged")
            continue
        doc.lead[anchor] = new
        said.append(f"{'commented' if comment_lines(text) else 'uncommented'} {what}")
    if header is not None:
        new = comment_lines(header) + [l for l in doc.comments if not l.strip()]
        if new == doc.comments:
            said.append("the header is already that; unchanged")
        else:
            doc.comments = new
            said.append("commented the header" if comment_lines(header) else "uncommented the header")
    return said


def remove_keys(doc, keys, to=None, within=None):
    """palette FILE --remove KEYS [--to KEY] [--in DIR]: FILE's own key lines for KEYS go, with their lines in FILE's
    variants (and the comments above them). A key a frame still draws with is E_SELECT, unless --to KEY repaints those
    pixels as KEY first. An imported key (import_removal) is repainted the same way in FILE, then goes from the palette
    file that defines it when no other .px under DIR draws with it or lists it in a variant (DIR: --in, else the
    directory holding both FILE and that palette file); else it stays there, and the output says who uses it. What it
    did."""
    pal = doc.resolved()
    for k in keys:
        if k == ".":
            fail("E_BAD_ARG", "--remove '.': '.' is built in (always transparent), not a key line", path=doc.path)
        if k not in doc.palette and k not in doc.shared:
            fail("E_SELECT", f"--remove {k!r}: {doc.path} has no key {k!r}", path=doc.path)
    if to is not None and (to not in pal or to in keys or to == "."):
        fail("E_SELECT", f"--to {to!r}: " + (f"it is being removed" if to in keys else
                                              "'.' erases; repaint with fill or recolor first" if to == "." else
                                              f"not a key of {doc.path}"), path=doc.path)
    imported = [k for k in keys if k not in doc.palette]
    owners = {k: key_owner(doc, k) for k in imported}
    uses = {}
    for f in doc.frames:
        for k in keys:
            if redundant(doc, k):  # its pixels draw the imported key, the same color: nothing to repaint
                continue
            n = sum(r.count(k) for r in f.grid)
            if n:
                uses.setdefault(k, []).append((doc.label(f), n))
    if uses and to is None:
        each = "; ".join(f"{k}: {sum(n for _, n in fs)} px in {listed(l for l, _ in fs)}" for k, fs in uses.items())
        fail("E_SELECT", f"--remove {''.join(keys)}: frames still draw with {' '.join(uses)} ({each}); repaint them "
             f"first, or give --to KEY to repaint them as KEY: pxart palette {doc.path} --remove {''.join(keys)} "
             "--to K",
             path=doc.path)
    said = []
    if uses:
        moves = dict.fromkeys(keys, to)
        for f in doc.frames:
            f.grid = ["".join(moves.get(c, c) for c in r) for r in f.grid]
        said.append("repainted " + ", ".join(f"{sum(n for _, n in fs)} px of {k}" for k, fs in uses.items())
                    + f" as {to}")
    local = [k for k in keys if k in doc.palette]
    if local:
        said.append("removed " + ", ".join(drop_key_lines(doc, local)))
    back = [k for k in local if k in doc.shared]
    if back:
        said.append(f"{' '.join(back)} now {'have' if len(back) > 1 else 'has'} the imported color"
                    f"{'s' * (len(back) > 1)} ({', '.join(f'{k} {fmt_color(doc.shared[k])}' for k in back)})")
    if local and not doc.frames:
        said.append(f"sprites that import {doc.path.name} and draw with {' '.join(local)} no longer can (check them)")
    later = []
    if imported:
        said += import_removal(doc, owners, within, later)
    return "; ".join(said + [write_doc(doc)] + later)


def order_keys(doc, keys):
    """palette FILE --order KEYS: FILE's key lines for KEYS move to the top of its palette, in that order, each with
    the blank and comment lines above it; the other keys follow as they were. A '. transparent' line keeps its place
    in the list. What it did."""
    for k in keys:
        if k == ".":
            fail("E_BAD_ARG", "--order '.': '.' is built in; its '. transparent' line, if any, keeps its place",
                 path=doc.path)
        if k not in doc.palette:
            fail("E_SELECT", f"--order {k!r}: " + (
                f"it comes from {doc.palette_refs[0] if len(doc.palette_refs) == 1 else 'an imported palette file'}; "
                "order it there" if k in doc.shared else f"{doc.path} has no key {k!r}"), path=doc.path)
    was = list(doc.palette)
    order = keys + [k for k in was if k not in keys]
    doc.palette = {k: doc.palette[k] for k in order}
    if order == was:
        return f"already in that order; {write_doc(doc)}"
    return f"ordered {' '.join(keys)} first ({len(was) - len(keys)} other key{'s' * (len(was) - len(keys) != 1)} " \
           f"after, as they were); {write_doc(doc)}"


def import_palette(doc, pal):
    """palette FILE --import P.px: FILE gets '@palette P.px' (re-pointed from FILE's directory). FILE's own key lines
    that P gives the same color go (their comments too; P documents them). A key FILE has that P gives another color
    is E_KEY_CONFLICT, with free keys to move FILE's to first. FILE renders as before in its base palette and in every
    variant it had: where P's variant of that name would recolor a key FILE keeps, FILE's variant lists the key's
    color. What it did."""
    with reading(f"--import ({pal})"):
        try:
            sub = parse(pal, palette_only=True)
        except FileNotFoundError:
            fail("E_PALETTE_FILE", f"can't find palette file {typed_path(pal)}")
    target = pathlib.Path(pal).resolve()
    if target == doc.path.resolve() or doc.path.resolve() in import_chain(sub):
        fail("E_BAD_ARG", f"--import {pal}: {doc.path} can't import itself" + (
            "" if target == doc.path.resolve() else f" ({pal} imports it)"), path=doc.path)
    if target in import_chain(doc):
        return f"{doc.path} already imports {pal}; no change: {doc.path}"
    theirs, mine = sub.resolved(), doc.resolved()
    bad = [k for k in mine if k != "." and k in theirs and theirs[k] != mine[k]]
    if bad:
        moves = new_keys(bad, mine, theirs, set(mine) | set(theirs))
        each = ", ".join(f"{k!r} {fmt_color(mine[k])} ({pal}: {fmt_color(theirs[k])})" for k in bad)
        fix = (f"; give {doc.path}'s {'keys free ones' if len(bad) > 1 else 'key a free one'} first (no pixel changes "
               f"color): pxart recolor {shlex.quote(str(doc.path))} "
               + " ".join(shlex.quote(f"{k}>{v}") for k, v in moves.items())
               + f", then palette {doc.path} --import {pal}") if moves else \
            "; there aren't enough free keys to rename them: repaint some as keys both have in one color"
        fail("E_KEY_CONFLICT", f"--import {pal}: {len(bad)} key{'s' * (len(bad) > 1)} of {doc.path} "
             f"{'are other colors' if len(bad) > 1 else 'is another color'} in {pal}: {each}{fix}", path=doc.path)
    names = variant_names(doc)
    before = {n: doc.resolved(n) for n in names}
    ref = pathlib.Path(os.path.relpath(target, doc.path.resolve().parent)).as_posix()
    imports(doc, ref, sub)
    same = [k for k in doc.palette if k in theirs]
    order = list(doc.palette)
    if doc.dot_at is not None:
        doc.dot_at -= sum(1 for k in same if order.index(k) < doc.dot_at)
    for k in same:
        del doc.palette[k]
        for store in (doc.lead, doc.raw, doc.at):
            store.pop(("key", k), None)
    base, lines = doc.resolved(), []
    for n, over in list(doc.variants.items()):  # a dropped key's variant line P's variant says already goes too
        for k in [k for k in same if k in over and over[k] == doc.shared_variants.get(n, {}).get(k, base[k])]:
            del over[k]
            lines.append(n)
            for store in (doc.lead, doc.raw, doc.at):
                store.pop(("vkey", n, k), None)
        if not over and n in doc.shared_variants and not any(l.strip() for l in doc.lead.get(("variant", n)) or []):
            del doc.variants[n]
            for store in (doc.lead, doc.raw, doc.at):
                store.pop(("variant", n), None)
    kept = {}
    for n in names:
        now = doc.resolved(n)
        for k, c in before[n].items():
            if k != "." and now[k] != c:
                doc.variants.setdefault(n, {})[k] = c
                kept.setdefault(n, []).append(k)
    out = pathlib.Path(doc.dest or doc.path)  # palette -o: the file written, and its @palette line as written there
    shown = ref if out.resolve().parent == doc.path.resolve().parent else \
        pathlib.Path(os.path.relpath(target, out.resolve().parent)).as_posix()
    said = [f"imported {pal} (@palette {shown})"]
    if same:
        said.append(f"dropped {' '.join(same)} ({'their key lines' if len(same) > 1 else 'its key line'}"
                    + (f" and {len(lines)} line{'s' * (len(lines) > 1)} in @variant {', '.join(dict.fromkeys(lines))}"
                       if lines else "") + f": the same color{'s' * (len(same) > 1)} in {pal})")
    for n, ks in kept.items():
        said.append(f"@variant {n} lists {' '.join(ks)} in {doc.path.name}'s colors ({pal}'s {n} recolors "
                    f"{'them' if len(ks) > 1 else 'it'})")
    new = [n for n in variant_names(doc) if n not in names]
    if new:
        said.append(f"{out.name} now has {pal}'s @variant {', '.join(new)}")
    return "; ".join(said + [write_doc(doc)])


def redundant(doc, k):
    """doc's own key line for k repeats its import (the same color), and so do its variant lines for k, if any: taking
    them out (palette --remove) changes no pixel, in the base palette or any variant."""
    if k not in doc.palette or k not in doc.shared or doc.palette[k] != doc.shared[k]:
        return False
    return all(doc.variants[n][k] == doc.shared_variants.get(n, {}).get(k, doc.shared[k])
               for n in doc.variants if k in doc.variants[n])


def drop_key_lines(doc, keys):
    """doc's own key lines for keys go, with their lines in doc's variants and the comments above them. What went,
    as 'k (and its line in @variant night)' each."""
    order = list(doc.palette)
    if doc.dot_at is not None:  # a '. transparent' line keeps its place among the keys that stay
        doc.dot_at -= sum(1 for k in keys if order.index(k) < doc.dot_at)
    lines = []
    for k in keys:
        del doc.palette[k]
        for store in (doc.lead, doc.raw, doc.at):
            store.pop(("key", k), None)
        names = [n for n, over in doc.variants.items() if k in over]
        for n in names:
            del doc.variants[n][k]
            for store in (doc.lead, doc.raw, doc.at):
                store.pop(("vkey", n, k), None)
        lines.append(k + (f" (and its line in @variant {', '.join(names)})" if names else ""))
    return lines


def key_owner(doc, k):
    """The palette file whose key line gives doc its imported key k: the last @palette that has it (a later import
    wins), and within that file its own line before its imports'. Its path."""
    for ref in reversed(doc.palette_refs):
        t = pathlib.Path(os.path.normpath(doc.path.parent / ref))
        try:
            sub = parse(t, palette_only=True)
        except (OSError, PxError):
            continue
        if k in sub.palette:
            return t
        if k in sub.shared:
            return key_owner(sub, k)
    return None


def import_removal(doc, owners, within, later):
    """palette FILE --remove of imported keys ({key: the palette file defining it}): FILE's pixels are repainted
    already (remove_keys). Each palette file then loses the keys no other .px under DIR (within, else the directory
    holding FILE and it) uses: draws with it, or lists it in a variant, without a key line of its own. FILE's variant
    lines for a key that goes, go too. What it did; the palette files' 'wrote' lines go to `later`."""
    said = []
    for owner in dict.fromkeys(owners.values()):
        ks = [k for k, o in owners.items() if o == owner]
        where = pathlib.Path(within) if within else pathlib.Path(os.path.commonpath(
            [doc.path.resolve().parent, owner.resolve().parent]))
        rel = os.path.relpath(where)
        shown = str(within or (where if rel.startswith("..") else rel)).rstrip("/")
        users = key_users(owner, ks, where, doc.path)
        gone = [k for k in ks if not users.get(k)]
        for k in ks:
            if users.get(k):
                said.append(f"{k} stays in {owner}: {listed(users[k], 3)} "
                            f"{'uses' if len(users[k]) == 1 else 'use'} it (of the .px files under {shown}/)")
        if not gone:
            continue
        with reading(f"palette file ({owner})"):
            pdoc = parse(owner, palette_only=True)
        mine = [n for n, over in doc.variants.items() if any(k in over for k in gone)]
        for n in mine:
            for k in gone:
                if k in doc.variants[n]:
                    del doc.variants[n][k]
                    for store in (doc.lead, doc.raw, doc.at):
                        store.pop(("vkey", n, k), None)
        said.append(f"removed {', '.join(drop_key_lines(pdoc, gone))} from {owner} (no other .px under {shown}/ "
                    f"uses {'them' if len(gone) > 1 else 'it'})"
                    + (f", and {doc.path.name}'s lines for {'them' if len(gone) > 1 else 'it'} in @variant "
                       f"{', '.join(mine)}" if mine else ""))
        later.append(write_doc(pdoc))
    return said


def key_users(owner, keys, where, skip):
    """{key: the .px files under `where` (not `skip`, not the palette file itself) that import `owner` and use the key
    it defines: draw with it or list it in a variant, without a key line of their own}."""
    target, gone = pathlib.Path(owner).resolve(), {pathlib.Path(owner).resolve(), pathlib.Path(skip).resolve()}
    out = {}
    for p in in_dirs([str(where)]) if os.path.isdir(where) else []:
        if pathlib.Path(p).resolve() in gone:
            continue
        try:
            d = parse(p, allow_empty=True) if _has_grid(p) else parse(p, palette_only=True)
        except (OSError, PxError):
            continue
        if target not in import_chain(d):
            continue
        drawn = set("".join(r for f in d.frames for r in f.grid))
        listed_ = {k for over in d.variants.values() for k in over}
        for k in keys:
            if k not in d.palette and (k in drawn or k in listed_):
                out.setdefault(k, []).append(os.path.relpath(p, where))
    return out


def hoist(doc, keys):
    """palette FILE --hoist KEYS: FILE's own key lines (and its variant lines for them, and the comments above both)
    move into the palette file it imports, so its other sprites get them; FILE renders as before. The palette file must
    be FILE's only import and not have the key in another color."""
    if len(doc.palette_refs) != 1:
        fail("E_BAD_ARG", f"--hoist moves keys into the palette file {doc.path} imports, and it imports "
             + (f"{len(doc.palette_refs)}: {', '.join(doc.palette_refs)}; hoist from a file with one @palette"
                if doc.palette_refs else f"none; to start one: pxart palette {doc.path} --extract-to P.px --repoint"),
             path=doc.path)
    ref = doc.palette_refs[0]
    target = doc.path.parent / ref
    with reading(f"@palette ({ref})"):
        pal = parse(target, palette_only=True)
    for k in keys:
        if k not in doc.palette:
            fail("E_SELECT", f"--hoist {k!r}: not one of {doc.path}'s own keys ("
                 + (f"it comes from {ref} already" if k in doc.shared else "no such key") + ")", path=doc.path)
        if k in pal.resolved() and pal.resolved()[k] != doc.palette[k]:
            fail("E_KEY_CONFLICT", f"--hoist {k!r}: {ref} has {k!r} as {fmt_color(pal.resolved()[k])}, not "
                 f"{fmt_color(doc.palette[k])}, and changing it would recolor every sprite that imports {ref}; give "
                 f"{doc.path}'s {k!r} a free key first (pxart recolor {doc.path} '{k}>K')", path=doc.path)
    kept, order = [], list(doc.palette)
    if doc.dot_at is not None:  # a '. transparent' line keeps its place among the keys that stay
        doc.dot_at -= sum(1 for k in keys if order.index(k) < doc.dot_at)
    for k in keys:
        c = doc.palette.pop(k)
        if k not in pal.resolved():
            pal.palette[k] = c
            lead = doc.lead.pop(("key", k), None)
            if lead and any(l.strip() for l in lead):
                pal.lead[("key", k)] = lead
        for name, over in doc.variants.items():
            if k not in over:
                continue
            theirs = {**pal.shared_variants.get(name, {}), **pal.variants.get(name, {})}
            if theirs.get(k) == over[k]:  # the palette file already says so
                del over[k]
                doc.lead.pop(("vkey", name, k), None)
            elif k in theirs:
                kept.append(f"{k} in @variant {name}")  # the palette file has its own color for it: FILE's line stays
            else:  # a relist moves too: it says the key stays as it is in that variant (a lamp kept lit)
                pal.variants.setdefault(name, {})[k] = over.pop(k)
                lead = doc.lead.pop(("vkey", name, k), None)
                if lead and any(l.strip() for l in lead):
                    pal.lead[("vkey", name, k)] = lead
    for name in [n for n, over in doc.variants.items() if not over and (n in pal.variants or n in pal.shared_variants)]:
        del doc.variants[name]  # every line moved: the palette file's variant is FILE's now
        lead = [l for l in doc.lead.pop(("variant", name), None) or [] if l.strip()]
        if lead:  # its comment goes along, under the palette file's own
            had = [l for l in pal.lead.get(("variant", name), []) if l.strip()]
            pal.lead[("variant", name)] = [""] + had + [l for l in lead if l not in had]
    doc.shared, doc.shared_variants = {**pal.shared, **pal.palette}, {}
    for vname, over in list(pal.shared_variants.items()) + list(pal.variants.items()):
        doc.shared_variants.setdefault(vname, {}).update(over)
    note = f"; {', '.join(kept)} stays in {doc.path} ({ref} has its own color for it)" if kept else ""
    return f"hoisted {' '.join(keys)} to {ref}{note}; {write_doc(pal, target)}; {write_doc(doc)}"


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


def export_frames(args, exclude=()):
    """export's FILE|DIR[:SEL]... : [(doc, its frames, its name)] per file, in the order first named. A file's
    selections add up, in file order (a plain FILE: every frame). A directory stands for every .px under it (palette
    files skipped, --exclude as for sheet); its files' names are their paths under it without .px (town/roofs.px under
    town/ is 'roofs'), a file named directly goes by its stem."""
    files = frames_only(in_dirs(args, exclude=exclude), "export")
    names = {}
    for arg in args:
        if os.path.isdir(arg):
            for p in pathlib.Path(arg).rglob("*.px"):
                names.setdefault(str(p), p.relative_to(arg).with_suffix("").as_posix())
    order = list(dict.fromkeys(split_sel(f)[0] for f in files))
    out = []
    for path in order:
        mine = [f for f in files if split_sel(f)[0] == path]
        with reading(f"FILE ({path})"):
            doc = parse(path)
        sels = [split_sel(f)[1] for f in mine]
        if None in sels:
            picked = list(doc.frames)
        else:
            chosen = set()
            for arg, sel in zip(mine, sels):
                with reading(f"FILE ({arg})"):
                    chosen |= {id(f) for f in doc.select(sel)}
            picked = [f for f in doc.frames if id(f) in chosen]
        out.append((doc, picked, names.get(path, doc.stem)))
    return out


def export_id(doc, f, name, prefix):
    """A frame's id in export's output (the PNG's path under --frames, the Aseprite filename, the sheet's order):
    its label, or with --prefix-file NAME/ID (an unnamed grid: NAME alone)."""
    if not prefix:
        return doc.label(f)
    return name if doc.implicit else f"{name}/{f.id}"


def export_clashes(entries, prefix, frames_dir):
    """export's output names must not collide: two frames of one id (from two files) would be one PNG, one Aseprite
    filename, and two animations of one name one tag; with --frames, two ids that differ only in case are one file on
    a case-insensitive file system (macOS, Windows). E_DUP_FRAME naming each, and how to tell them apart."""
    ids, tags = {}, {}  # id (casefolded with --frames) -> [(id, file)]
    for doc, frames, name in entries:
        for f in frames:
            fid = export_id(doc, f, name, prefix)
            ids.setdefault(fid.casefold() if frames_dir else fid, []).append((fid, str(doc.path)))
        for g in doc.groups(frames):
            if doc.animated(g):
                tag = f"{name}/{g}" if prefix else g
                tags.setdefault(tag, []).append(str(doc.path))
    bad = [(k, v) for k, v in ids.items() if len(v) > 1]
    twice = [(t, fs) for t, fs in tags.items() if len(fs) > 1]
    if not bad and not twice:
        return
    said, files = [], set()
    for _, got in bad:
        files.update(p for _, p in got)
        if len({fid for fid, _ in got}) == 1:
            said.append(f"{got[0][0]} ({', '.join(p for _, p in got)})")
        else:
            said.append(" and ".join(f"{fid} ({p})" for fid, p in got) + " differ only in case, one file on a "
                        "case-insensitive file system (macOS, Windows)")
    for t, fs in twice:
        files.update(fs)
        said.append(f"animation {t} ({', '.join(fs)})")
    across = len(files) > 1 and not prefix
    fix = ("; --prefix-file ids each file's frames FILE/ID (roofs/red, walls/red), or export the files one at a "
           "time" if across else "; rename one ('frames FILE --rename OLD NEW') or export them one at a time")
    fail("E_DUP_FRAME", "frames that would get one name in the export (the later would replace the earlier): "
         + "; ".join(said) + fix)


def pivot_slices(its):
    """Pivots as Aseprite's JSON has them (meta.slices, the same shape Aseprite's own sheet export writes): one slice
    named 'pivot' with a key for every frame, in sheet order. A key holds from its frame on, so every frame gets one:
    bounds = the whole frame (its sourceSize, since spriteSourceSize is 0,0), and 'pivot' relative to those bounds, left
    out for a frame without a pivot. No pivots in the files: no slices, as before."""
    if not any(it.doc.pivot(it.frame) for it in its):
        return []
    keys = []
    for n, it in enumerate(its):
        key = {"frame": n, "bounds": {"x": 0, "y": 0, "w": it.img.width, "h": it.img.height}}
        if it.doc.pivot(it.frame):
            key["pivot"] = dict(zip("xy", it.doc.pivot(it.frame)))
        keys.append(key)
    return [{"name": "pivot", "color": "#0000ffff", "keys": keys}]


def cmd_export(a):
    if isinstance(a.tiled, str) and (is_room_src(a.tiled) or os.path.isdir(a.tiled)):
        a.files, a.tiled = [a.tiled] + a.files, True  # 'export --tiled world.src.json ...': a source, not X.tsj
    if a.tiled is True:
        a.files = source_args(a.files)
    if not a.files:
        fail("E_BAD_ARG", "export: give FILE|DIR... (.px frames), or world.src.json / .map sources with --tiled")
    srcs = [f for f in a.files if is_room_src(f)]
    if srcs:
        if len(srcs) < len(a.files):
            fail("E_BAD_ARG", "export: world sources (world.src.json, .map) and .px frames go in separate exports: "
                 + ", ".join(f for f in a.files if not is_room_src(f)))
        if a.tiled is not True or a.frames or a.aseprite:
            fail("E_BAD_ARG", "export --tiled on world sources takes no X.tsj: each .map compiles to the .tmj beside "
                 "it, a world.src.json to <name>.world and rooms/*.tmj ('export world.src.json --tiled')")
        return export_tiled(a, srcs)
    if a.tiled is True:
        fail("E_BAD_ARG", "export --tiled X.tsj: name the tileset to write (or give world.src.json / .map sources)")
    if a.tileset or a.tile != "16x16":
        fail("E_BAD_ARG", "--tileset and --tile are for world sources (world.src.json, .map)")
    if not (a.frames or a.aseprite or a.tiled):
        fail("E_BAD_ARG", "export: give --frames DIR, --aseprite X.json and/or --tiled X.tsj")
    variants = {split_variant(f)[1] for f in a.files} - {None}
    if len(variants) > 1:
        fail("E_BAD_ARG", f"export: one variant per export, got %{' %'.join(sorted(variants))}")
    variant = variants.pop() if variants else a.variant
    entries = export_frames(a.files, a.exclude or ())
    export_clashes(entries, a.prefix_file, bool(a.frames))
    its, docs = [], {}
    for doc, picked, name in entries:
        with reading(f"FILE ({doc.path})"):
            its += [Item(export_id(doc, f, name, a.prefix_file), doc.image(f, variant), doc.ms(f), doc, f)
                    for f in picked]
        docs[id(doc)] = name
    wrote = []
    if a.frames:
        pngs = []
        for it in its:
            p = save_image(it.img, pathlib.Path(a.frames) / (it.label + ".png"), "--frames")
            pngs.append(str(p))
        wrote += pngs if len(pngs) <= 8 else [f"{len(pngs)} PNGs under {a.frames} ({pngs[0]} ... {pngs[-1]})"]
        pivots = {it.label: dict(zip("xy", it.doc.pivot(it.frame))) for it in its if it.doc.pivot(it.frame)}
        if pivots:  # only when the files have pivots: {"walk/0": {"x": 8, "y": 23}, ...}, in export order
            p = outpath(pathlib.Path(a.frames) / "pivots.json")
            p.write_text(json.dumps(pivots, indent=1) + "\n")
            wrote.append(str(p))

    def groups():  # [(doc, group, its frames, the tag's name)], each file's groups in turn, as grouped() orders them
        return [(doc, g, fs, f"{docs[id(doc)]}/{g}" if a.prefix_file else g)
                for doc, picked, _ in entries for g, fs in doc.groups(picked).items()]
    if a.aseprite:
        its2 = grouped(its)
        sheet_img, spots, _, _, _ = pack(its2)
        jp = outpath(a.aseprite)
        ip = save_image(sheet_img, jp.with_suffix(".png"), "--aseprite's sheet")
        frames, tags, i = [], [], 0
        for it, (x, y) in zip(its2, spots):
            w, h = it.img.size
            frames.append({"filename": it.label, "frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False,
                           "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h},
                           "sourceSize": {"w": w, "h": h}, "duration": it.ms})
        for doc, g, fs, tag_name in groups():
            if not doc.animated(g):
                i += len(fs)
                continue
            meta = doc.anims.get(g, {})
            tag = {"name": tag_name, "from": i, "to": i + len(fs) - 1,
                   "direction": meta.get("direction") or "forward", "color": "#000000ff"}
            if meta.get("repeat"):
                tag["repeat"] = str(meta["repeat"])
            tags.append(tag)
            i += len(fs)
        data = {"frames": frames, "meta": {
            "app": "https://github.com/thethirdbearsolutions/pxart", "version": str(FORMAT_VERSION),
            "image": ip.name, "format": "RGBA8888", "size": {"w": sheet_img.width, "h": sheet_img.height},
            "scale": "1", "frameTags": tags, "layers": [], "slices": pivot_slices(its2)}}
        jp.write_text(json.dumps(data, indent=1) + "\n")
        wrote += [str(ip), str(jp)]
    if a.tiled:
        if len({it.img.size for it in its}) > 1:
            odd = entries[0][0].path if len(entries) == 1 else "FILE"
            fail("E_TILE_SIZE", "a Tiled tileset needs every frame the same size: "
                 + ", ".join(f"{it.label} {it.img.width}x{it.img.height}" for it in its)
                 + f"; export only same-size frames with FILE:SEL (export {odd}:GROUP ... --tiled X.tsj)")
        its = grouped(its)
        sheet_img, spots, cols, cw, ch = pack(its)
        tp = outpath(a.tiled)
        ip = save_image(sheet_img, tp.with_suffix(".png"), "--tiled's image")
        index = {id(it.frame): n for n, it in enumerate(its)}
        tiles = []
        for doc, g, fs, tag_name in groups():
            if not doc.animated(g) or len(fs) < 2:
                continue
            tiles.append({"id": index[id(fs[0])],
                          "animation": [{"tileid": index[id(f)], "duration": doc.ms(f)} for f in fs],
                          "properties": [{"name": "pxart_anim", "type": "string", "value": tag_name}]})
        data = {"type": "tileset", "version": "1.10", "name": entries[0][0].stem if len(entries) == 1 else tp.stem,
                "image": ip.name, "imagewidth": sheet_img.width, "imageheight": sheet_img.height,
                "tilewidth": cw, "tileheight": ch, "columns": cols, "tilecount": len(its),
                "margin": 0, "spacing": 0, "tiles": tiles}
        tp.write_text(json.dumps(data, indent=1) + "\n")
        wrote += [str(ip), str(tp)]
    print("wrote", " ".join(wrote))


# ---------------------------------------------------------------------------- worlds: .map + world.src.json -> Tiled

GID_H, GID_V, GID_D = 0x80000000, 0x40000000, 0x20000000  # Tiled's flip flags, the top bits of a GID
GID_FLAGS = 0xF0000000
TILED_FORMAT = "1.10"  # the JSON format version Tiled 1.10+ writes (as export --tiled's tilesets say)
WORLD_SRC = ".src.json"
WORLD_KEYS = ("layout", "start", "doors")
DOOR_RESERVED = ("target", "entry")  # a door pair's own properties: written by the compiler, never by hand
MARKER_CLASS = "character_frame"  # a tile object of this class is a marker: not drawn by the harness, never solid
ROOM_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def is_world_src(p):
    return str(p).endswith(WORLD_SRC)


def is_room_src(p):
    return str(p).endswith(".map") or is_world_src(p)


def tiled_props(obj):
    """A Tiled object's (or map's, tile's) properties as {name: value}."""
    return {p.get("name"): p.get("value") for p in obj.get("properties") or () if isinstance(p, dict)}


def tiled_class(obj):
    """An object's class: 'type', or 'class' as Tiled 1.9 saved it."""
    return obj.get("type") or obj.get("class") or ""


def posix_rel(path, start):
    return pathlib.PurePath(os.path.relpath(path, start)).as_posix()


class Tileset:
    """One .tsj as the compiler and the world rules read it: tiles by id, each tile's size, class, collision
    rectangles (its objectgroup, as bounding boxes) and identity (the pack path its `png` property names, else a
    collection tile's own image)."""

    def __init__(self, path, data):
        self.path, self.data = pathlib.Path(path), data
        self.tiles = {int(t["id"]): t for t in data.get("tiles") or () if isinstance(t, dict) and "id" in t}
        self.sheet = bool(data.get("image"))
        self._ids = None
        ids = list(self.tiles) + [int(data.get("tilecount") or 0) - 1, int(tiled_props(data).get("nextid") or 0) - 1]
        self.span = max(ids + [-1]) + 1  # every id the tileset has or has issued: its GID range
        self._pixels = None

    def has(self, tid):
        return tid in self.tiles or (self.sheet and 0 <= tid < int(self.data.get("tilecount") or 0))

    def size(self, tid):
        t = self.tiles.get(tid, {})
        if self.sheet:
            return int(self.data["tilewidth"]), int(self.data["tileheight"])
        if "width" in t and "x" in t:
            return int(t["width"]), int(t["height"])
        return int(t.get("imagewidth") or 0), int(t.get("imageheight") or 0)

    def cls(self, tid):
        return tiled_class(self.tiles.get(tid, {}))

    def collision(self, tid):
        """The tile's collision shapes as (x, y, w, h) in the tile's own pixels: each object's bounding box (a polygon's
        points' box); points and zero-area shapes block nothing."""
        out = []
        for o in (self.tiles.get(tid, {}).get("objectgroup") or {}).get("objects") or ():
            x, y, w, h = (float(o.get(k) or 0) for k in ("x", "y", "width", "height"))
            pts = o.get("polygon") or o.get("polyline")
            if pts:
                xs, ys = [x + p["x"] for p in pts], [y + p["y"] for p in pts]
                x, y, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
            if w > 0 and h > 0 and not o.get("point"):
                out.append((x, y, w, h))
        return out

    def identities(self):
        """{resolved file path: tile id}: a tile's `png` property (a pack path, from the pack's root: the tileset's
        directory's parent, <pack>/tiled/..), and a collection tile's own image (unless it's a sub-rectangle)."""
        if self._ids is not None:
            return self._ids
        out = self._ids = {}
        for tid, t in self.tiles.items():
            png = tiled_props(t).get("png")
            if png and "rect" not in tiled_props(t) and "x" not in t:
                out.setdefault(str((self.path.parent.parent / png).resolve()), tid)
            if t.get("image") and "x" not in t:
                out.setdefault(str((self.path.parent / t["image"]).resolve()), tid)
        return out

    def pixels(self):
        """{(w, h, RGBA bytes): [tile ids]}: every tile's art, for matching a .px frame by what it looks like."""
        if self._pixels is None:
            self._pixels = {}
            sheet = None
            if self.sheet:
                sheet = Image.open(self.path.parent / self.data["image"]).convert("RGBA")
                tw, th = self.size(0)
                cols = int(self.data.get("columns") or 1)
                m, sp = int(self.data.get("margin") or 0), int(self.data.get("spacing") or 0)
            for tid in (range(int(self.data.get("tilecount") or 0)) if self.sheet else self.tiles):
                if sheet is not None:
                    x, y = m + (tid % cols) * (tw + sp), m + (tid // cols) * (th + sp)
                    img = sheet.crop((x, y, x + tw, y + th))
                else:
                    t = self.tiles[tid]
                    if not t.get("image"):
                        continue
                    img = Image.open(self.path.parent / t["image"]).convert("RGBA")
                    if "x" in t:
                        img = img.crop((t["x"], t["y"], t["x"] + t["width"], t["y"] + t["height"]))
                if img.getbbox() is None:
                    continue  # a blank cell (a hole left by a removed tile) is nobody's art
                self._pixels.setdefault((img.width, img.height, img.tobytes()), []).append(tid)
        return self._pixels


def read_tileset(path):
    with open(path) as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or data.get("type", "tileset") != "tileset":
        raise ValueError("not a Tiled tileset")
    return Tileset(path, data)


class TileFinder:
    """Which tileset tile a legend entry is, by identity, never by position: a PNG by its path (a pack tileset's
    `png` property, or a collection tile's image), a .px frame (or a PNG no tileset names) by its pixels. The
    tilesets: every <dir>/tiled/*.tsj in a directory above the art (its pack's), plus --tileset ones."""

    def __init__(self, explicit=()):
        self.sets, self.seen, self.by_dir = [], {}, {}
        self.explicit = [self.add(p) for p in explicit]
        self.cache = {}

    def add(self, p):
        p = pathlib.Path(os.path.abspath(p))
        key = str(p.resolve())
        if key not in self.seen:
            try:
                ts = read_tileset(p)
            except (OSError, ValueError) as e:
                fail("E_TILESET", f"can't read the tileset: {getattr(e, 'strerror', None) or e}", path=str(p))
            self.seen[key] = ts
            self.sets.append(ts)
        return self.seen[key]

    def near(self, art):
        """The tilesets in <ancestor>/tiled/ of the art's (absolute, unresolved) path, nearest first."""
        out = []
        for anc in pathlib.Path(os.path.abspath(art)).parents:
            d = anc / "tiled"
            if str(d) not in self.by_dir:
                self.by_dir[str(d)] = [self.add(t) for t in sorted(d.glob("*.tsj"))] if d.is_dir() else []
            out += self.by_dir[str(d)]
            if (anc / ".git").exists() or any(anc.glob("*" + WORLD_SRC)):
                break  # the game's (or the repository's) root: tilesets above it aren't the art's
        return out

    def find(self, arg, img):
        """(Tileset, tile id) for a legend entry (FILE[:frame][%variant][+flips]) and its unflipped image; raises
        ValueError saying why not."""
        if arg in self.cache:
            return self.cache[arg]
        path = split_sel(split_variant(arg)[0])[0]
        scope = list(dict.fromkeys(self.near(path) + self.explicit))
        hits = []
        if path.endswith(".png"):
            want = str(pathlib.Path(path).resolve())
            hits = [(ts, ts.identities()[want]) for ts in self.sets if want in ts.identities()]
        if not hits:
            key = (img.width, img.height, img.tobytes())
            hits = [(ts, tid) for ts in scope for tid in ts.pixels().get(key, ())]
        if not hits:
            where = ", ".join(posix_rel(ts.path, os.getcwd()) for ts in scope)
            raise ValueError("no tileset has this art (" + (f"looked in {where}" if where else
                                                            "there's no <dir>/tiled/*.tsj above it") +
                             "; a pack's tilesets are <pack>/tiled/*.tsj, or name one with --tileset)")
        if len({(str(ts.path), tid) for ts, tid in hits}) > 1:
            raise ValueError("more than one tile has this art: " + ", ".join(
                f"{ts.path.name} tile {tid}" for ts, tid in hits[:4]) + "; name the PNG itself in the legend")
        self.cache[arg] = hits[0]
        return hits[0]


class RoomSrc:
    """A .map read for compiling: its legend, rows by layer, size, and where each glyph is drawn."""

    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.id = map_room(path)
        self.issues, self.notes, self.warns = [], [], []
        self.legend, self.layers, self.where, self.cells = {}, [], {}, {}
        self.lead = {}
        try:
            self.legend, self.layers, self.notes, self.where = parse_map(self.path)
            lines = self.path.read_text().splitlines()
        except OSError as e:
            self.issues.append(Issue("E_FILE", e.strerror or str(e), str(self.path)))
            self.layers, lines = [[]], []
        self.lead = {n: len(lines[n - 1]) - len(lines[n - 1].lstrip()) for rows in self.layers for n, _ in rows}
        rows_all = [(n, r) for rows in self.layers for n, r in rows]
        self.w = max((len(r) for _, r in rows_all), default=0)  # as scene: the widest row, the tallest layer
        self.h = max((len(rows) for rows in self.layers), default=0)
        if not rows_all:
            self.issues.append(Issue("E_MAP_SIZE", "no rows: a room is a legend, a blank line, then rows",
                                     str(self.path)))
        widest = next((n for n, r in rows_all if len(r) == self.w), None)
        for li, rows in enumerate(self.layers, 1):
            if li == 1 and rows and len(rows) < self.h:
                self.issues.append(Issue("E_MAP_SIZE", f"the ground (layer 1) has {len(rows)} rows, the room has "
                                         f"{self.h}: the rows under it would be holes in the floor", str(self.path),
                                         rows[-1][0]))
            elif rows and len(rows) < self.h:
                self.warns.append(f"{self.path}:{rows[-1][0]}: layer {li} has {len(rows)} rows, the room has "
                                  f"{self.h}: they're its top {len(rows)} (a row left out in the middle moves "
                                  "everything under it up one)")
            for y, (n, row) in enumerate(rows):
                if len(row) != self.w:
                    self.issues.append(Issue("E_ROW_WIDTH", f"row is {len(row)} wide, the room is {self.w} (its "
                                             f"widest row, line {widest}); scene pads it, leaving a hole",
                                             str(self.path), n, col=self.lead[n] + len(row) + 1))
                for x, ch in enumerate(row):
                    if ch == ".":
                        continue
                    if ch.isspace():
                        self.issues.append(Issue("E_BAD_ROW", "a space in a row (a legend line is one char, a "
                                                 "space, then the path)", str(self.path), n, col=self.col(n, x)))
                    elif ch not in self.legend:
                        self.issues.append(Issue("E_UNKNOWN_KEY", f"map char {ch!r} has no legend line"
                                                 + guess(ch, self.legend), str(self.path), n, col=self.col(n, x)))
                    else:
                        self.cells.setdefault(ch, [])
                        if (x, y) not in self.cells[ch]:
                            self.cells[ch].append((x, y))

    def col(self, n, x):
        return self.lead.get(n, 0) + x + 1

    def at(self, x, y, layer=0):
        """(line, col) of cell x,y in a layer (clamped into the room)."""
        rows = self.layers[layer] if layer < len(self.layers) and self.layers[layer] else self.layers[0]
        n = rows[max(0, min(y, len(rows) - 1))][0]
        return n, self.col(n, x)

    def glyph_at(self, ch):
        """(line, col) where ch is first drawn (layer by layer, row by row)."""
        for li, rows in enumerate(self.layers):
            for y, (n, row) in enumerate(rows):
                if ch in row:
                    return n, self.col(n, row.index(ch))
        return self.where.get(ch, (None,))[0], None

    def issue(self, code, msg, cell=None, ch=None):
        n, c = self.glyph_at(ch) if ch else self.at(*cell) if cell else (None, None)
        return Issue(code, msg, str(self.path), n, col=c)

    def rect(self, ch):
        """ch's cells as one rectangle (x, y, w, h), or None when they aren't one."""
        cells = self.cells.get(ch) or []
        if not cells:
            return None
        xs, ys = [x for x, _ in cells], [y for _, y in cells]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        return (x0, y0, x1 - x0 + 1, y1 - y0 + 1) if len(cells) == (x1 - x0 + 1) * (y1 - y0 + 1) else None


def object_cell(o, tw, th):
    """The cell an object stands for, from its geometry alone (so a previous .tmj's objects map to cells too): a
    point's or a tile object's feet (its bottom-centre; a point on a cell's bottom edge is that cell's), else a
    rectangle's top-left."""
    x, y, w, h = (float(o.get(k) or 0) for k in ("x", "y", "width", "height"))
    if o.get("point"):
        return math.floor(x / tw), math.ceil(y / th) - 1
    if "gid" in o:
        return math.floor((x + w / 2) / tw), math.ceil(y / th) - 1
    return math.floor(x / tw), math.floor(y / th)


def start_cell(o, tw, th):
    """A start's cell: under its feet, the point itself, or a shape's bottom centre (object_cell's rule for feet)."""
    if o.get("point") or o.get("gid"):
        return object_cell(o, tw, th)
    x, y, w, h = (float(o.get(k) or 0) for k in ("x", "y", "width", "height"))
    return math.floor((x + w / 2) / tw), math.ceil((y + h) / th) - 1


def object_key(layer, o, tw, th):
    """What names an object across compiles: its layer's name, class and name, and its cell (object_cell)."""
    return layer, tiled_class(o), o.get("name", ""), object_cell(o, tw, th)


def previous_ids(prev, tw, th):
    """From a previous .tmj: {object_key: [(id, the object), in file order]} and its next object id (never less than
    one past every id it has, so an id is never reused)."""
    keys, top = {}, 0
    for layer in all_layers(prev.get("layers") or ()):
        for o in layer.get("objects") or ():
            if isinstance(o, dict) and isinstance(o.get("id"), int):
                keys.setdefault(object_key(layer.get("name", ""), o, tw, th), []).append((o["id"], o))
                top = max(top, o["id"])
    return keys, max(int(prev.get("nextobjectid") or 1), top + 1)


def all_layers(layers):
    """Every layer, a group's too (depth first, in draw order)."""
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        yield layer
        if layer.get("type") == "group":
            yield from all_layers(layer.get("layers") or ())


def assign_ids(objs, prev, tw, th):
    """ADR 0009: an object keeps the previous .tmj's id for the same layer, class and name at the same cell (in file
    order when there are several); a new one takes the next id. objs: [(layer name, object)]. Returns (next object
    id, how many kept, the previous objects nothing took: [(layer name, object)])."""
    keys, nxt = previous_ids(prev, tw, th) if prev else ({}, 1)
    kept = 0
    for layer, o in objs:
        got = keys.get(object_key(layer, o, tw, th))
        if got:
            o["id"] = got.pop(0)[0]
            kept += 1
        else:
            o["id"], nxt = nxt, nxt + 1
    return nxt, kept, [(k[0], o) for k, left in keys.items() for _, o in left]


GID_SLOT = 1000  # tilesets start at firstgid 1, 1001, 2001, ...: room for a tileset to grow without moving the next


def gid_slot(end):
    """The first slot start (1 + a multiple of GID_SLOT) at or after end."""
    return 1 + math.ceil(max(end - 1, 0) / GID_SLOT) * GID_SLOT


def firstgids(used, prev, tmj_dir):
    """{Tileset: firstgid}: tilesets start on slots (1, 1001, 2001...; a tileset spanning more takes the next slot
    after its end), so a tileset that grows doesn't move the ones after it. A tileset the previous .tmj had keeps its
    firstgid while the ranges still fit (GIDs stay put); new ones take the next free slot; if anything would overlap,
    all are laid out on slots from 1, in that order."""
    old = {}
    for t in (prev or {}).get("tilesets") or ():
        if isinstance(t, dict) and t.get("source"):
            old[str((tmj_dir / t["source"]).resolve())] = int(t.get("firstgid") or 0)
    keep = sorted((ts for ts in used if str(ts.path.resolve()) in old), key=lambda ts: old[str(ts.path.resolve())])
    new = [ts for ts in used if ts not in keep]
    out = {ts: old[str(ts.path.resolve())] for ts in keep}
    end = max([g + max(ts.span, 1) for ts, g in out.items()] + [1])
    for ts in new:
        out[ts] = gid_slot(end)
        end = out[ts] + max(ts.span, 1)
    spans = sorted((g, g + max(ts.span, 1)) for ts, g in out.items())
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])) or any(g < 1 for g, _ in spans):
        out, end = {}, 1
        for ts in keep + new:
            out[ts] = gid_slot(end)
            end = out[ts] + max(ts.span, 1)
    return out


def room_tmj(src, tile, finder, tmj_path, doors=(), start=None):
    """Compile one room: (the .tmj as a dict, issues, warnings, how many ids were kept). doors: [(glyph, target .tmj
    path, entry glyph, extra properties)]; start: the glyph whose cell's feet the start goes at, or None."""
    tw, th = tile
    tmj_path = pathlib.Path(tmj_path)
    issues, warns = [], []
    prev = None
    if tmj_path.exists():
        try:
            prev = json.loads(tmj_path.read_text())
            if not isinstance(prev, dict):
                raise ValueError("not a JSON object")
        except ValueError as e:
            issues.append(Issue("E_GENERATED", f"the previous {tmj_path.name} can't be read ({e}); its object ids "
                                "are what keeps saved state pointing at the right objects, so fix or remove it",
                                str(tmj_path)))
            prev = None
        else:
            source = tiled_props(prev).get("source")
            want = posix_rel(src.path, tmj_path.parent)
            if not source:
                issues.append(Issue("E_GENERATED", f"{tmj_path.name} has no 'source' property, so it wasn't compiled "
                                    f"from {src.path.name} (a room made in Tiled?); export --tiled won't overwrite "
                                    "it: move it, or delete it to compile the .map", str(tmj_path)))
            elif source != want:
                issues.append(Issue("E_GENERATED", f"{tmj_path.name} was compiled from {source}, not {want}; "
                                    "export --tiled won't overwrite it", str(tmj_path)))
    try:
        imgs = load_legend(src.path)
    except PxError as e:
        return None, issues + e.issues, warns, 0
    looked, found = {}, {}
    ch_of = {a: ch for ch, a, _ in legend_entries(src.legend, src.where)}
    for arg, it in imgs.items():
        how = split_flip(arg)[1]
        plain = flipped(it.img, how.replace("b", ""))
        try:
            ts, tid = finder.find(split_flip(arg)[0], plain)
        except ValueError as e:
            issues.append(Issue("E_TILESET", f"legend {ch_of[arg]!r} ({posix_rel(split_flip(arg)[0], src.path.parent)})"
                                f": {e}", str(src.path), src.where[ch_of[arg]][0]))
            continue
        if ts.size(tid) != it.img.size:
            issues.append(Issue("E_TILESET", f"legend {ch_of[arg]!r}: its art is {it.img.width}x{it.img.height}, "
                                f"but {ts.path.name} tile {tid} is {ts.size(tid)[0]}x{ts.size(tid)[1]}",
                                str(src.path), src.where[ch_of[arg]][0]))
            continue
        found[arg] = (ts, tid)
        if "b" not in how and (it.img.width > tw or it.img.height > th):
            warns.append(f"{src.path}:{src.where[ch_of[arg]][0]}: legend {ch_of[arg]!r} is {it.img.width}x"
                         f"{it.img.height}, bigger than a {tw}x{th} cell, with no +b: it's placed by its top-left "
                         "corner, as scene draws it (+b stands its feet on the cell)")
    if issues:
        return None, issues, warns, 0
    W, H = src.w, src.h
    used, layers = [], []
    past = set()

    def gid_of(arg):
        ts, tid = found[arg]
        if ts not in used:
            used.append(ts)
        how = split_flip(arg)[1]
        return ts, tid, (GID_H if "h" in how else 0) | (GID_V if "v" in how else 0)
    cells_by_layer = []
    for li, rows in enumerate(src.layers, 1):
        data, objs, boxes = [0] * (W * H), [], []
        for y, (n, row) in enumerate(rows):
            for x, ch in enumerate(row[:W]):
                if ch == ".":
                    continue
                arg = pick_variant(src.legend[ch], src.id, x, y)
                img = imgs[arg].img
                ts, tid, flags = gid_of(arg)
                bottom = "b" in split_flip(arg)[1]
                cx, cy = x * tw, y * th
                over = any(bx < cx + tw and cx < bx + bw and by < cy + th and cy < by + bh for bx, by, bw, bh in boxes)
                if not bottom and img.size == (tw, th) and not over:
                    data[y * W + x] = (ts, tid, flags)
                    continue
                sx, sy = cell_spot(arg, img, cx, cy, tile)
                if (sx < 0 or sy < 0 or sx + img.width > W * tw or sy + img.height > H * th) and ch not in past:
                    past.add(ch)
                    warns.append(f"{src.path}:{n}:{src.col(n, x)}: {ch!r}'s art at cell {x},{y} reaches past the "
                                 f"room's edge (scene crops it; the compiled room keeps all of it)")
                boxes.append((sx, sy, img.width, img.height))
                objs.append({"id": 0, "name": ch, "type": "", "gid": (ts, tid, flags), "x": sx, "y": sy + img.height,
                             "width": img.width, "height": img.height, "rotation": 0, "visible": True})
        cells_by_layer.append((li, data, objs))
    world_objs = []
    for ch, target, entry, extra in doors:
        x, y, w, h = src.rect(ch)
        props = {"entry": ("string", entry), "target": ("file", posix_rel(target, tmj_path.parent))}
        for k, v in extra.items():
            props[k] = ("bool" if isinstance(v, bool) else "int" if isinstance(v, int) else
                        "float" if isinstance(v, float) else "string", v)
        world_objs.append({"id": 0, "name": ch, "type": "door", "x": x * tw, "y": y * th, "width": w * tw,
                           "height": h * th, "rotation": 0, "visible": True,
                           "properties": [{"name": k, "type": t, "value": v} for k, (t, v) in sorted(props.items())]})
    if start:
        (x, y), = src.cells[start]
        fx = x * tw + tw / 2
        world_objs.append({"id": 0, "name": "start", "type": "start", "point": True,
                           "x": int(fx) if fx == int(fx) else fx, "y": y * th + th, "width": 0, "height": 0,
                           "rotation": 0, "visible": True})
    nxt, kept, dropped = assign_ids([(f"layer {li} objects", o) for li, _, objs in cells_by_layer for o in objs]
                                    + [("world", o) for o in world_objs], prev, tw, th)
    ours = re.compile(r"^(layer \d+( objects)?|world)$")
    for layer, o in dropped:  # left over from the previous .tmj: a removed cell, or something added in Tiled
        if not (ours.match(layer) and (o.get("name") in src.legend or o.get("name") == "start")
                and tiled_class(o) in ("", "door", "start")):
            warns.append(f"{tmj_path}: object {o.get('id')} {o.get('name', '')!r} (layer {layer!r}) isn't from "
                         f"{src.path.name}, and this compile drops it: add it to the source, or make the room in "
                         "Tiled (a .tmj with no 'source')")
    gids = firstgids(used, prev, tmj_path.parent)

    def gid(t):
        return 0 if not t else gids[t[0]] + t[1] | t[2]
    lid = 0
    for li, data, objs in cells_by_layer:
        if any(data):
            lid += 1
            layers.append({"id": lid, "name": f"layer {li}", "type": "tilelayer", "width": W, "height": H, "x": 0,
                           "y": 0, "opacity": 1, "visible": True, "data": [gid(t) for t in data]})
        if objs:
            for o in objs:
                o["gid"] = gid(o["gid"])
            lid += 1
            layers.append({"id": lid, "name": f"layer {li} objects", "type": "objectgroup", "draworder": "index",
                           "x": 0, "y": 0, "opacity": 1, "visible": True, "objects": objs})
    if world_objs:
        lid += 1
        layers.append({"id": lid, "name": "world", "type": "objectgroup", "draworder": "index", "x": 0, "y": 0,
                       "opacity": 1, "visible": True, "objects": world_objs})
    tmj = {"type": "map", "version": TILED_FORMAT, "orientation": "orthogonal", "renderorder": "right-down",
           "width": W, "height": H, "tilewidth": tw, "tileheight": th, "infinite": False, "compressionlevel": -1,
           "nextlayerid": lid + 1, "nextobjectid": nxt,
           "properties": [{"name": "source", "type": "file", "value": posix_rel(src.path, tmj_path.parent)}],
           "layers": layers,
           "tilesets": [{"firstgid": g, "source": posix_rel(ts.path, tmj_path.parent)}
                        for ts, g in sorted(gids.items(), key=lambda tg: tg[1])]}
    return tmj, issues, warns, kept


def tiled_json(data):
    """A .tmj/.world as text: indent 1, as W1's tilesets, but a tile layer's data a row to a line."""
    rows = {}

    def mark(d):
        if isinstance(d, dict):
            if d.get("type") == "tilelayer" and isinstance(d.get("data"), list):
                key = f"@@rows{len(rows)}@@"
                w = int(d["width"]) or 1
                rows[key] = [d["data"][i:i + w] for i in range(0, len(d["data"]), w)]
                return {k: (key if k == "data" else mark(v)) for k, v in d.items()}
            return {k: mark(v) for k, v in d.items()}
        if isinstance(d, list):
            return [mark(v) for v in d]
        return d
    text = json.dumps(mark(data), indent=1)
    for key, rs in rows.items():
        m = re.search(rf'^( *)"data": "{re.escape(key)}"', text, re.M)
        pad = m.group(1) + " "
        body = ",\n".join(pad + ", ".join(str(v) for v in r) for r in rs)
        text = text.replace(f'"{key}"', "[\n" + body + "\n" + m.group(1) + "]")
    return text + "\n"


def json_at(text, token):
    """(line, col) of token's first appearance in text (a JSON string, quoted), or (None, None)."""
    i = text.find(json.dumps(token))
    if i < 0:
        return None, None
    return text.count("\n", 0, i) + 1, i - (text.rfind("\n", 0, i) + 1) + 1


class WorldSrc:
    """A world.src.json read and checked: its rooms (placed by layout, then interiors: rooms only doors name), the
    start, the door pairs; issues say what's wrong, at file:line:col."""

    def __init__(self, path, tile):
        self.path, self.tile = pathlib.Path(path), tile
        self.issues, self.notes = [], []
        self.grid, self.placed, self.interiors, self.rooms = [], [], [], {}
        self.start, self.doors = None, []
        try:
            self.text = self.path.read_text()
        except OSError as e:
            self.issues.append(Issue("E_FILE", e.strerror or str(e), str(self.path)))
            return
        try:
            data = json.loads(self.text)
        except ValueError as e:
            self.issues.append(Issue("E_WORLD", f"not JSON: {getattr(e, 'msg', e)}", str(self.path),
                                     getattr(e, "lineno", None), col=getattr(e, "colno", None)))
            return
        if not isinstance(data, dict):
            self.issues.append(Issue("E_WORLD", 'a world source is a JSON object: {"layout": [...], "start": '
                                     '{...}, "doors": [...]}', str(self.path), 1))
            return
        for k in data:
            if k not in WORLD_KEYS:
                self.err(f"unknown key {k!r} (a world source has {', '.join(WORLD_KEYS)}){guess(k, WORLD_KEYS)}", k)
        self.read_layout(data.get("layout"))
        self.read_doors(data.get("doors", []))
        self.read_start(data.get("start"))

    def err(self, msg, token=None, code="E_WORLD"):
        n, c = json_at(self.text, token) if token is not None else (None, None)
        self.issues.append(Issue(code, msg, str(self.path), n, col=c))

    def room(self, rid, token):
        """The room's RoomSrc (read once), or None when there's no rooms/<rid>.map (an issue)."""
        if rid in self.rooms:
            return self.rooms[rid]
        p = self.path.parent / "rooms" / f"{rid}.map"
        if not p.is_file():
            there = sorted(q.stem for q in (self.path.parent / "rooms").glob("*.map"))
            self.err(f"room {rid!r}: no {posix_rel(p, self.path.parent)} (a room is rooms/<name>.map beside "
                     f"{self.path.name}){guess(rid, there)}", token)
            self.rooms[rid] = None
            return None
        self.rooms[rid] = RoomSrc(p)
        return self.rooms[rid]

    def read_layout(self, layout):
        if layout is None:
            return self.err('no "layout": the rooms drawn where they sit, "layout": ["shore point", "cove ."]')
        if not isinstance(layout, list) or not all(isinstance(r, str) for r in layout):
            return self.err('"layout" is a list of strings, a row of room names each ("shore point")', "layout")
        seen = {}
        for row in layout:
            names = row.split()
            for name in names:
                if name == ".":
                    continue
                if not ROOM_RE.match(name):
                    self.err(f"layout: {name!r} isn't a room name (letters, digits, - and _; '.' for no room)", row)
                elif name in seen:
                    self.err(f"layout: room {name!r} is placed twice (a room sits in one place; reach it again "
                             "through a door)", row)
                else:
                    seen[name] = row
                    self.room(name, row)
            self.grid.append(names)
        self.placed = list(seen)
        if not seen:
            self.err('"layout" places no room', "layout")

    def door_end(self, end, token):
        m = re.match(r"^\s*(\S+)\s+(\S)\s*$", end) if isinstance(end, str) else None
        if not m or not ROOM_RE.match(m.group(1)):
            self.err(f"door end {end!r}: write 'ROOM CHAR', a room and the char drawn at the door ('point D')", token)
            return None
        return m.group(1), m.group(2)

    def read_doors(self, doors):
        if not isinstance(doors, list):
            return self.err('"doors" is a list of pairs: [["point D", "tower d"]]', "doors")
        ends = {}
        for pair in doors:
            token = pair[0] if isinstance(pair, list) and pair and isinstance(pair[0], str) else "doors"
            if not (isinstance(pair, list) and len(pair) in (2, 3) and all(isinstance(e, str) for e in pair[:2])
                    and (len(pair) == 2 or isinstance(pair[2], dict))):
                self.err('a door pair is ["ROOM CHAR", "ROOM CHAR"], and optionally {"trigger": "use", ...} for '
                         f"both doors' properties; got {json.dumps(pair)}", token)
                continue
            a, b = self.door_end(pair[0], pair[0]), self.door_end(pair[1], pair[1])
            extra = pair[2] if len(pair) == 3 else {}
            for k, v in extra.items():
                if k in DOOR_RESERVED:
                    self.err(f"door {pair[0]!r}: {k!r} is written by the compiler from the pair itself", k)
                elif k == "trigger" and v not in ("touch", "use"):
                    self.err(f"door {pair[0]!r}: trigger is 'touch' (the default) or 'use' (fires on "
                             f"world.use), not {v!r}", k, "E_DOOR")
                elif isinstance(v, (dict, list)) or v is None:
                    self.err(f"door {pair[0]!r}: property {k!r} is a string, number or true/false", k)
            if not a or not b:
                continue
            if a == b:
                self.err(f"door {pair[0]!r} is paired with itself", pair[0], "E_DOOR")
                continue
            ok = True
            for (rid, ch), token in ((a, pair[0]), (b, pair[1])):
                if (rid, ch) in ends:
                    self.err(f"door '{rid} {ch}' is in two pairs ({ends[(rid, ch)]!r} and this one); a door leads "
                             "to one place", token, "E_DOOR")
                    ok = False
                    continue
                ends[(rid, ch)] = token
                src = self.room(rid, token)
                if src is None:
                    ok = False
                elif ch not in src.cells:
                    self.err(f"door '{rid} {ch}': no {ch!r} drawn in {posix_rel(src.path, self.path.parent)}"
                             + guess(ch, src.cells), token, "E_DOOR")
                    ok = False
                elif src.rect(ch) is None:
                    cells = src.cells[ch]
                    self.issues.append(src.issue("E_DOOR", f"door '{rid} {ch}': {ch!r} is drawn at {len(cells)} "
                                                 "cells that aren't one rectangle (a door is one rectangle of cells: "
                                                 "a wide doorway is a row of them)", ch=ch))
                    ok = False
            if ok:
                self.doors.append((a, b, extra))
        for (rid, _), token in ends.items():
            if rid not in self.placed and rid not in self.interiors and self.rooms.get(rid):
                self.interiors.append(rid)

    def read_start(self, start):
        if start is None:
            return  # the world rules say it: start-count
        if not (isinstance(start, dict) and isinstance(start.get("room"), str) and isinstance(start.get("at"), str)
                and len(start["at"]) == 1):
            return self.err('"start" is {"room": ROOM, "at": CHAR}: the room, and the char drawn where the player '
                            'starts ("at": "@")', "start")
        rid, ch = start["room"], start["at"]
        if rid not in self.placed and rid not in self.interiors:
            return self.err(f"start: room {rid!r} isn't in the world (not in the layout, and no door leads there)"
                            + guess(rid, self.placed + self.interiors), rid, "E_START")
        src = self.rooms.get(rid)
        if src is None:
            return
        cells = src.cells.get(ch) or []
        if len(cells) != 1:
            return self.err(f"start: {ch!r} is drawn at {len(cells)} cells in {posix_rel(src.path, self.path.parent)}"
                            " (the start is at one)" + (": " + ", ".join(f"{x},{y}" for x, y in cells) if cells else
                                                        guess(ch, src.cells)), "start", "E_START")
        self.start = (rid, ch)

    def world_path(self):
        return self.path.parent / (self.path.name[:-len(WORLD_SRC)] + ".world")

    def tmj(self, rid):
        return self.path.parent / "rooms" / f"{rid}.tmj"

    def layout_px(self):
        """[(room, x, y, w, h)] in pixels: a layout column is as wide as its widest room, a row as tall as its
        tallest; a column or row with no room is the size of the world's largest room."""
        tw, th = self.tile
        size = {r: (s.w * tw, s.h * th) for r, s in self.rooms.items() if s}
        ncols = max((len(r) for r in self.grid), default=0)
        cols = [max((size[row[c]][0] for row in self.grid if c < len(row) and row[c] in size), default=None)
                for c in range(ncols)]
        rows = [max((size[n][1] for n in row if n in size), default=None) for row in self.grid]
        big_w, big_h = max((s[0] for s in size.values()), default=0), max((s[1] for s in size.values()), default=0)
        cols, rows = [c if c is not None else big_w for c in cols], [r if r is not None else big_h for r in rows]
        out = []
        for ri, row in enumerate(self.grid):
            for ci, name in enumerate(row):
                if name in size:
                    out.append((name, sum(cols[:ci]), sum(rows[:ri]), *size[name]))
        return out


RULE_HINT = {"start-count": ' (in world.src.json: "start": {"room": ROOM, "at": CHAR})'}


def compile_world(src_path, tile, finder):
    """world.src.json -> {path: .tmj/.world dict}, errors, warnings, a summary line. Rooms are rooms/<name>.map beside
    it; each compiles to rooms/<name>.tmj, the world to <name>.world. The world rules run on the compiled files."""
    w = WorldSrc(src_path, tile)
    issues, warns = list(w.issues), []
    rooms = {r: s for r, s in w.rooms.items() if s}
    for s in rooms.values():
        issues += s.issues
        warns += s.warns
    src_dir = w.path.parent
    others = sorted(p for p in (src_dir / "rooms").glob("*.map") if p.stem not in rooms) \
        if (src_dir / "rooms").is_dir() else []
    notes = [f"{posix_rel(p, os.getcwd())} isn't in the world (no layout cell or door names {p.stem!r}); not "
             "compiled" for p in others]
    if issues:
        return None, issues, warns, notes, None
    doors = {r: [] for r in rooms}
    for (ra, ca), (rb, cb), extra in w.doors:
        doors[ra].append((ca, w.tmj(rb), cb, extra))
        doors[rb].append((cb, w.tmj(ra), ca, extra))
    out, kept = {}, {}
    for rid in w.placed + w.interiors:
        s = rooms[rid]
        tmj, errs, ws, k = room_tmj(s, tile, finder, w.tmj(rid), doors[rid],
                                    w.start[1] if w.start and w.start[0] == rid else None)
        issues += errs
        warns += ws
        notes += s.notes
        if tmj:
            out[str(w.tmj(rid))], kept[rid] = tmj, (k, len([o for l in tmj["layers"] for o in l.get("objects", ())]))
    if issues:
        return None, issues, warns, notes, None
    wp = w.world_path()
    out[str(wp)] = {"type": "world", "onlyShowAdjacentMaps": False, "maps": [
        {"fileName": posix_rel(w.tmj(r), wp.parent), "x": x, "y": y, "width": ww, "height": hh}
        for r, x, y, ww, hh in w.layout_px()]}
    for ri in world_rules(str(wp), lambda p: out.get(str(pathlib.Path(p))) if str(pathlib.Path(p)) in out
                          else read_json(p)):
        s = rooms.get(ri.room)
        loc = None
        if s and ri.name and ri.code.startswith("door") and ri.name in s.cells:
            loc = s.glyph_at(ri.name)
        elif s and ri.cell:
            loc = s.at(*ri.cell)
        msg = f"{ri.code}: {ri.msg}" + RULE_HINT.get(ri.code, "")
        where = (str(s.path), *loc) if s and loc else (str(s.path), None, None) if s else (str(w.path), None, None)
        if ri.level == "error":
            issues.append(Issue("E_WORLD", msg, where[0], where[1], col=where[2]))
        else:
            warns.append(f"{where[0]}" + (f":{where[1]}:{where[2]}" if where[1] else "") + f": {msg}")
    if issues:
        return None, issues, warns, notes, None
    summary = (w, kept)
    return out, issues, warns, notes, summary


def read_json(p):
    try:
        with open(p) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# ---- the world rules (the spec: tests/fixtures/world_rules/SPEC.md; its fixtures run here and in the harness)

WORLD_RULES = {  # code: level. The same list as the spec's rules.json; a rule is added to both or the tests fail.
    "room-missing": "error", "room-id-dup": "error", "tileset-missing": "error",
    "start-count": "error", "start-solid": "error",
    "door-target": "error", "door-entry": "error", "door-pair": "error", "door-name-dup": "error",
    "door-trigger": "error", "door-arrival": "error", "door-unreachable": "error",
    "tiled-unsupported": "error", "room-overlap": "error",
    "edge-one-side": "warning", "room-unreachable": "warning", "door-arrival-split": "warning",
}
EDGES = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}


class RuleIssue:
    def __init__(self, code, room, name, cell, msg):
        self.level, self.code, self.room, self.name, self.cell, self.msg = WORLD_RULES[code], code, room, name, \
            (list(cell) if cell is not None else None), msg

    def key(self):
        return self.level, self.code, self.room, self.name, self.cell

    def __repr__(self):
        return f"{self.level} {self.code} room={self.room} name={self.name} cell={self.cell}: {self.msg}"


class RuleRoom:
    """A loaded room as the rules see it: size, which cells are solid, its doors and starts."""

    def __init__(self, path, data, read, out):
        self.path, self.data, self.out = path, data, out
        self.id = pathlib.PurePath(path).stem
        self.tw, self.th = int(data.get("tilewidth") or 1), int(data.get("tileheight") or 1)
        self.w, self.h = int(data.get("width") or 0), int(data.get("height") or 0)
        self.pos = None
        self.solid = set()
        self.doors, self.starts = [], []
        sets = []
        for t in data.get("tilesets") or ():
            if not isinstance(t, dict):
                continue
            if t.get("source"):
                sp = posixpath.normpath(posixpath.join(posixpath.dirname(path), t["source"]))
                got = read(sp)
                if not isinstance(got, dict):
                    out.append(RuleIssue("tileset-missing", self.id, None, None,
                                         f"{self.id}: tileset {t['source']} can't be loaded"))
                    sets.append((int(t.get("firstgid") or 1), None))  # its GIDs stay its own: unresolved
                    continue
                sets.append((int(t.get("firstgid") or 1), Tileset(sp, got)))
            else:
                sets.append((int(t.get("firstgid") or 1), Tileset(path, t)))
        self.sets = sorted(sets, key=lambda s: s[0])
        for _, ts in self.sets:
            d = ts.data if ts else {}
            if any(float((d.get("tileoffset") or {}).get(k) or 0) for k in ("x", "y")):
                self.unsupported("tileoffset", f"tileset {ts.path.name} has a tileoffset")
            if d.get("objectalignment") not in (None, "unspecified", "bottomleft"):
                self.unsupported("objectalignment", f"tileset {ts.path.name} aligns objects "
                                 f"{d.get('objectalignment')!r}, not bottom-left")
        for layer in all_layers(data.get("layers") or ()):
            if any(float(layer.get(k) or 0) for k in ("offsetx", "offsety")):
                self.unsupported("layer offset", f"layer {layer.get('name', '')!r} is offset")
            if layer.get("type") == "tilelayer":
                for i, g in enumerate(layer.get("data") or ()):
                    if g:
                        cx, cy = i % self.w, i // self.w
                        self.block(g, cx * self.tw, (cy + 1) * self.th, None, None)
            elif layer.get("type") == "objectgroup":
                for o in layer.get("objects") or ():
                    if not isinstance(o, dict):
                        continue
                    cls = self.cls(o)
                    if float(o.get("rotation") or 0) and (o.get("gid") or cls in ("door", "start")):
                        self.unsupported("rotation", f"object {o.get('id')} {o.get('name', '')!r} is rotated")
                    if cls == "door":
                        self.doors.append(o)
                    elif cls == "start":
                        self.starts.append(o)
                    elif o.get("gid"):
                        self.block(o["gid"], float(o.get("x") or 0), float(o.get("y") or 0),
                                   float(o.get("width") or 0), float(o.get("height") or 0))

    def unsupported(self, what, msg):
        if not any(i.code == "tiled-unsupported" and i.room == self.id and i.name == what for i in self.out):
            self.out.append(RuleIssue("tiled-unsupported", self.id, what, None, f"{self.id}: {msg} (the rules, "
                                      "and the harness, don't read that)"))

    def tile(self, gid):
        """(Tileset, tile id) for a GID: the tileset with the largest firstgid not above it. A missing tileset's
        range resolves to (None, None), never to the tileset before it."""
        g = gid & ~GID_FLAGS
        for first, ts in reversed(self.sets):
            if g >= first:
                return (ts, g - first) if ts else (None, None)
        return None, None

    def cls(self, o):
        """An object's class: its own, else (a tile object) its tile's."""
        own = tiled_class(o)
        if own or not o.get("gid"):
            return own
        ts, tid = self.tile(o["gid"])
        return ts.cls(tid) if ts else ""

    def block(self, gid, left, bottom, w, h):
        """Mark the cells a tile's collision shapes cover: the tile drawn with its bottom-left at left,bottom (w,h: a
        tile object's size, scaling the art; None: the art's own), flipped as its GID says. A marker blocks nothing."""
        ts, tid = self.tile(gid)
        if ts is None or ts.cls(tid) == MARKER_CLASS:
            return
        iw, ih = ts.size(tid)
        w, h = w or iw, h or ih
        sx, sy = (w / iw if iw else 1), (h / ih if ih else 1)
        for x, y, rw, rh in ts.collision(tid):
            if gid & GID_D:
                x, y, rw, rh = y, x, rh, rw
            if gid & GID_H:
                x = iw - x - rw
            if gid & GID_V:
                y = ih - y - rh
            x0, y0, x1, y1 = left + x * sx, bottom - h + y * sy, left + (x + rw) * sx, bottom - h + (y + rh) * sy
            for cy in range(math.floor(y0 / self.th), math.ceil(y1 / self.th)):
                for cx in range(math.floor(x0 / self.tw), math.ceil(x1 / self.tw)):
                    if min(x1, (cx + 1) * self.tw) > max(x0, cx * self.tw) and \
                            min(y1, (cy + 1) * self.th) > max(y0, cy * self.th):
                        self.solid.add((cx, cy))

    def inside(self, c):
        return 0 <= c[0] < self.w and 0 <= c[1] < self.h

    def walkable(self, c):
        return self.inside(c) and c not in self.solid

    def door_cells(self, o):
        """The cells a door's rectangle overlaps (a zero-size door: the cell it's in). A door that is a tile object
        covers its art: Tiled's y is then its bottom edge."""
        x, y, w, h = (float(o.get(k) or 0) for k in ("x", "y", "width", "height"))
        if o.get("gid"):
            y -= h
        if w <= 0 or h <= 0:
            return [(math.floor(x / self.tw), math.floor(y / self.th))]
        return [(cx, cy) for cy in range(math.floor(y / self.th), math.ceil((y + h) / self.th))
                for cx in range(math.floor(x / self.tw), math.ceil((x + w) / self.tw))]

    def beside(self, o):
        """Arrival cells: the walkable cells next to the door's rectangle (4 ways), outside it, inside the room."""
        cells = self.door_cells(o)
        out = []
        for cx, cy in cells:
            for dx, dy in EDGES.values():
                c = (cx + dx, cy + dy)
                if c not in cells and c not in out and self.walkable(c):
                    out.append(c)
        return out

    def regions(self, cells):
        """How many separate regions cells fall in: groups joined by 4-connected walkable cells of this room."""
        left, n = set(cells), 0
        while left:
            n += 1
            todo = [left.pop()]
            seen = set(todo)
            while todo:
                cx, cy = todo.pop()
                for dx, dy in EDGES.values():
                    c = (cx + dx, cy + dy)
                    if c not in seen and self.walkable(c):
                        seen.add(c)
                        todo.append(c)
            left -= seen
        return n

    def touch(self, o):
        """Cells the player can stand in and touch the door from: its walkable cells and the arrival cells."""
        return [c for c in self.door_cells(o) if self.walkable(c)] + self.beside(o)

    def world_cell(self, c):
        """The world point at the centre of cell c (which may be just outside the room)."""
        return self.pos[0] + (c[0] + 0.5) * self.tw, self.pos[1] + (c[1] + 0.5) * self.th

    def cell_at(self, px, py):
        return math.floor((px - self.pos[0]) / self.tw), math.floor((py - self.pos[1]) / self.th)

    def contains(self, px, py):
        return self.pos[0] <= px < self.pos[0] + self.w * self.tw and self.pos[1] <= py < self.pos[1] + self.h * self.th


def world_rules(world_path, read, model=None):
    """The world rules (SPEC.md beside tests/fixtures/world_rules/) over a Tiled world: world_path's .world and the
    rooms it places, and every room a door leads to (read(path) -> parsed JSON, or None when there's none; paths are
    POSIX, a file's references resolved from its directory). Returns [RuleIssue], errors and warnings, in a stable
    order. model: a dict to fill with what the rules saw, for the world preview to draw (pxart world): the world
    file's JSON, the rooms by path (None: can't be loaded), placed and live rooms, each door's partner and resolved
    target, the doors door-name-dup skips, the start, the reachable cells (None when there's no valid start), and
    every shared-edge crossing (room, side, cell, the room across, its cell)."""
    out = []
    world_path = posixpath.normpath(str(pathlib.PurePath(world_path).as_posix()))
    world = read(world_path) or {}
    rooms, order, placed = {}, [], []

    def load(p):
        if p not in rooms:
            data = read(p)
            rooms[p] = RuleRoom(p, data, read, out) if isinstance(data, dict) else None
            if rooms[p]:
                order.append(p)
        return rooms[p]
    for m in world.get("maps") or ():
        p = posixpath.normpath(posixpath.join(posixpath.dirname(world_path), m.get("fileName", "")))
        r = load(p)
        if r is None:
            out.append(RuleIssue("room-missing", pathlib.PurePath(p).stem, None, None,
                                 f"the world places {m.get('fileName')!r}, which can't be loaded"))
            continue
        r.pos = (float(m.get("x") or 0), float(m.get("y") or 0))
        placed.append(r)

    for i, a in enumerate(placed):  # placed rooms may touch, never overlap
        for b in placed[:i]:
            ax, ay, bx, by = a.pos + b.pos
            if min(ax + a.w * a.tw, bx + b.w * b.tw) > max(ax, bx) and \
                    min(ay + a.h * a.th, by + b.h * b.th) > max(ay, by):
                out.append(RuleIssue("room-overlap", a.id, b.id, None, f"{a.id} and {b.id} overlap in the world: "
                                     "rooms may share a side, never area"))

    targets = {}  # (room path, id(door)): the path its target resolves to, or None

    def target_of(r, o):
        if (r.path, id(o)) not in targets:
            t = tiled_props(o).get("target")
            targets[(r.path, id(o))] = posixpath.normpath(posixpath.join(posixpath.dirname(r.path), t)) \
                if isinstance(t, str) and t else None
        return targets[(r.path, id(o))]
    i = 0
    while i < len(order):  # interiors: rooms a door leads to, found by following targets
        r = rooms[order[i]]
        for o in r.doors:
            t = target_of(r, o)
            if t:
                load(t)
        i += 1
    live = [rooms[p] for p in order]
    ids = {}
    for r in live:
        ids.setdefault(r.id, []).append(r)
    for rid, rs in ids.items():
        if len(rs) > 1:
            out.append(RuleIssue("room-id-dup", rid, None, None, f"{len(rs)} rooms are called {rid!r} ("
                                 + ", ".join(x.path for x in rs) + "); a room's id is its file name"))
    # doors
    bad_arrival, partner, dups = set(), {}, []
    for r in live:
        names, doors = {}, []
        for o in r.doors:
            name = o.get("name", "")
            cell = r.door_cells(o)[0]
            if name in names:
                out.append(RuleIssue("door-name-dup", r.id, name, cell, f"{r.id} has two doors named {name!r}; a "
                                     "door's entry names one"))
                dups.append((r, o))
                continue
            doors.append(o)
            names[name] = o
            props = tiled_props(o)
            if props.get("trigger", "touch") not in ("touch", "use"):
                out.append(RuleIssue("door-trigger", r.id, name, cell, f"door {name!r} in {r.id}: trigger is "
                                     f"'touch' or 'use', not {props.get('trigger')!r}"))
            if not r.beside(o):
                bad_arrival.add((r.path, id(o)))
                out.append(RuleIssue("door-arrival", r.id, name, cell, f"door {name!r} in {r.id} has no walkable "
                                     "cell beside it, so arriving there would put the player inside a solid"))
            elif r.regions(r.beside(o)) > 1:
                out.append(RuleIssue("door-arrival-split", r.id, name, cell, f"door {name!r} in {r.id} has "
                                     "walkable cells beside it in separate regions, so where you arrive decides "
                                     "where you can go (the runtime arrives facing into the room)"))
            t = target_of(r, o)
            tr = rooms.get(t) if t else None
            if tr is None:
                out.append(RuleIssue("door-target", r.id, name, cell, f"door {name!r} in {r.id} " + (
                    f"leads to {props.get('target')!r}, which can't be loaded" if t else "has no target")))
                continue
            entry = props.get("entry")
            there = [d for d in tr.doors if d.get("name") == entry] if isinstance(entry, str) and entry else []
            if not there:
                out.append(RuleIssue("door-entry", r.id, name, cell, f"door {name!r} in {r.id} " + (
                    f"enters {tr.id} at {entry!r}, and {tr.id} has no door {entry!r}" if entry else "has no entry")))
                continue
            back = there[0]
            if target_of(tr, back) != r.path or tiled_props(back).get("entry") != name:
                out.append(RuleIssue("door-pair", r.id, name, cell, f"door {name!r} in {r.id} leads to {entry!r} in "
                                     f"{tr.id}, which doesn't lead back to {name!r} in {r.id} (doors pair up)"))
                continue
            partner[(r.path, id(o))] = (tr, back)
        r.doors = doors  # a later door with a name taken is left out of everything else
    # the start
    starts = [(r, o) for r in live for o in r.starts]
    start = None
    if not starts:
        out.append(RuleIssue("start-count", None, None, None, "the world has no start (a point object of class "
                             "'start', in exactly one room)"))
    elif len(starts) > 1:
        for r, o in starts:
            out.append(RuleIssue("start-count", r.id, o.get("name", ""), start_cell(o, r.tw, r.th),
                                 f"{len(starts)} starts in the world; there is exactly one"))
    else:
        r, o = starts[0]
        cell = start_cell(o, r.tw, r.th)
        if not r.walkable(cell):
            out.append(RuleIssue("start-solid", r.id, o.get("name", ""), cell, f"the start in {r.id} is at cell "
                                 f"{cell[0]},{cell[1]}, " + ("which is solid" if r.inside(cell) else
                                                              "outside the room")))
        else:
            start = (r, cell)
    reached = None
    # reachability: from the start, walking between walkable cells, across shared edges, through paired doors
    if start:
        seen = {(start[0].path, start[1])}
        todo = [(start[0], start[1])]
        touches = {}
        for r in live:
            for o in r.doors:
                for c in r.touch(o):
                    touches.setdefault((r.path, c), []).append(o)
        while todo:
            r, c = todo.pop()
            steps = []
            for dx, dy in EDGES.values():
                n = (c[0] + dx, c[1] + dy)
                if r.inside(n):
                    steps.append((r, n))
                elif r.pos is not None:
                    px, py = r.world_cell(n)
                    for b in placed:
                        if b is not r and b.contains(px, py):
                            steps.append((b, b.cell_at(px, py)))
                            break
            for o in touches.get((r.path, c), ()):
                if (r.path, id(o)) in partner:
                    tr, back = partner[(r.path, id(o))]
                    steps += [(tr, a) for a in tr.beside(back)]
            for b, n in steps:
                if b.walkable(n) and (b.path, n) not in seen:
                    seen.add((b.path, n))
                    todo.append((b, n))
        reached = seen
        for r in live:
            for o in r.doors:
                if (r.path, id(o)) not in bad_arrival and not any((r.path, c) in seen for c in r.touch(o)):
                    out.append(RuleIssue("door-unreachable", r.id, o.get("name", ""), r.door_cells(o)[0],
                                         f"door {o.get('name', '')!r} in {r.id} can't be reached from the start"))
            if not any(p == r.path for p, _ in seen):
                out.append(RuleIssue("room-unreachable", r.id, None, None, f"no walkable cell of {r.id} can be "
                                     "reached from the start"))
    # shared edges: walkable on one side only (reported from the walkable side, a stretch at a time). Every border
    # cell with a room across goes in crossings, for the preview: (room, side, its cell, the room across, that cell)
    crossings = []
    for a in placed:
        for side, (dx, dy) in EDGES.items():
            border = [(x, 0 if dy < 0 else a.h - 1) for x in range(a.w)] if dy else \
                [(0 if dx < 0 else a.w - 1, y) for y in range(a.h)]
            run = None
            for c in border + [None]:
                hit = None
                if c is not None:
                    px, py = a.world_cell((c[0] + dx, c[1] + dy))
                    b = next((b for b in placed if b is not a and b.contains(px, py)), None)
                    if b is not None:
                        crossings.append((a, side, c, b, b.cell_at(px, py)))
                    if b is not None and a.walkable(c) and not b.walkable(b.cell_at(px, py)):
                        hit = b
                if run and (hit is not run[0] or c is None):
                    b, first, n = run
                    out.append(RuleIssue("edge-one-side", a.id, side, first, f"{a.id}'s {side} edge from cell "
                                         f"{first[0]},{first[1]} ({n} cell{'s' * (n != 1)}) is walkable, and across "
                                         f"it {b.id} is solid: walking over puts the player in a solid"))
                    run = None
                if hit is not None:
                    run = (hit, c, 1) if run is None else (run[0], run[1], run[2] + 1)
    if model is not None:
        model.update(world_path=world_path, world=world, rooms=rooms, placed=placed, live=live, partner=partner,
                     start=start, reached=reached, targets=targets, dup_doors=dups, crossings=crossings)
    rank = {p: i for i, p in enumerate(order)}
    return sorted(out, key=lambda i: (i.level != "error", rank.get(next((p for p in order if rooms[p].id == i.room),
                                                                         ""), -1), i.code, str(i.name), i.cell or []))


def world_rules_files(files, world="world.world", root=None):
    """world_rules over an in-memory world, as the fixtures are: files {POSIX path: parsed JSON}; a path not in it is
    read from disk under root (a shared tileset)."""
    def read(p):
        if p in files:
            return files[p]
        return read_json(os.path.join(root, p)) if root else None
    return world_rules(world, read)


def room_summary(tmj):
    objs = [o for l in tmj["layers"] for o in l.get("objects", ())]
    return f"{tmj['width']}x{tmj['height']}, {len(objs)} object{'s' * (len(objs) != 1)}"


def world_room(map_path, tmj_path):
    """Why a .map is a world's room, not one to compile alone: a world source beside its rooms/ directory, or a
    previous .tmj with doors or a start in it. None when it's neither."""
    map_path = pathlib.Path(map_path)
    if map_path.parent.name == "rooms":
        worlds = sorted(map_path.parent.parent.glob("*" + WORLD_SRC))
        if worlds:
            return f"{map_path.name} is a room of {posix_rel(worlds[0], os.getcwd())}"
    prev = read_json(tmj_path) if pathlib.Path(tmj_path).exists() else None
    if isinstance(prev, dict) and any(tiled_class(o) in ("door", "start") for l in all_layers(prev.get("layers") or ())
                                      for o in l.get("objects") or () if isinstance(o, dict)):
        return f"{pathlib.Path(tmj_path).name} has doors or a start (a world's room)"
    return None


def source_args(files):
    """export --tiled's sources: a directory stands for the world sources under it (a rooms/ directory is an error
    naming the world source beside it)."""
    out = []
    for f in files:
        if not os.path.isdir(f):
            out.append(f)
            continue
        found = sorted(str(p) for p in pathlib.Path(f).rglob("*" + WORLD_SRC))
        if not found:
            beside = sorted(pathlib.Path(f).resolve().parent.glob("*" + WORLD_SRC))
            fail("E_FILE", f"{f} is a directory with no *{WORLD_SRC} under it" + (
                f"; its rooms are compiled with their world: export {posix_rel(beside[0], os.getcwd())} --tiled"
                if beside else "; name the .map files, or the world source"))
        out += found
    return out


def export_tiled(a, files):
    """export --tiled on sources: each world.src.json compiles with its rooms, each lone .map as a room with no
    doors or start."""
    tile = parse_tile(a.tile)
    with reading("--tileset"):
        finder = TileFinder(a.tileset or ())
    outputs, issues, warns, notes, lines = {}, [], [], [], []
    for f in files:
        if is_world_src(f):
            got, errs, ws, ns, summary = compile_world(f, tile, finder)
            issues += errs
            warns += ws
            notes += ns
            if got:
                w, kept = summary
                for rid in w.placed + w.interiors:
                    p = str(w.tmj(rid))
                    k, n = kept[rid]
                    lines.append((p, f"{room_summary(got[p])} ({k} kept id{'s' * (k != 1)}, {n - k} new)"
                                  + (", interior" if rid in w.interiors else "")))
                wp = str(w.world_path())
                lines.append((wp, f"{len(w.placed)} room{'s' * (len(w.placed) != 1)} placed"
                              + (f", interior{'s' * (len(w.interiors) != 1)} {', '.join(w.interiors)}"
                                 if w.interiors else "") + (f", start in {w.start[0]}" if w.start else "")))
                outputs.update(got)
        else:
            src = RoomSrc(f)
            tp = src.path.with_suffix(".tmj")
            why = world_room(src.path, tp)
            if why:
                issues.append(Issue("E_WORLD", f"{why}: compiled alone it would lose its doors and start; compile "
                                    "the world instead ('export WORLD.src.json --tiled')", str(src.path)))
                continue
            notes += src.notes
            warns += src.warns
            if src.issues:
                issues += src.issues
                continue
            tmj, errs, ws, k = room_tmj(src, tile, finder, tp)
            issues += errs
            warns += ws
            if tmj:
                n = sum(len(l.get("objects", ())) for l in tmj["layers"])
                outputs[str(tp)] = tmj
                lines.append((str(tp), f"{room_summary(tmj)} ({k} kept id{'s' * (k != 1)}, {n - k} new)"))
    for n in notes:
        print("note:", n)
    for w_ in warns:
        print("WARNING:", w_)
    if issues:
        raise PxError(issues)
    for p, data in outputs.items():
        outpath(p).write_text(tiled_json(data))
    for p, what in lines:
        print(f"wrote {p}: {what}")


def check_world(path, tile, tilesets=()):
    """check on a world.src.json: every error export --tiled would stop on, and its warnings; nothing written.
    (ok, how many warnings and notes it printed)."""
    try:
        got, issues, warns, notes, summary = compile_world(path, tile, TileFinder(tilesets))
    except PxError as e:
        got, issues, warns, notes, summary = None, e.issues, [], [], None
    if issues:
        print(f"FAIL {path}: {len(issues)} error(s)")
        for i in issues:
            print(f"     {i}")
    else:
        w = summary[0]
        print(f"ok   {path}: {len(w.placed)} room{'s' * (len(w.placed) != 1)} placed"
              + (f", interior{'s' * (len(w.interiors) != 1)} {', '.join(w.interiors)}" if w.interiors else "")
              + f", {len(w.doors)} door pair{'s' * (len(w.doors) != 1)}, start in {w.start[0]}")
    for n in notes:
        print(f"     note: {n}")
    for x in warns:
        print(f"     WARNING: {x}")
    return not issues, len(notes) + len(warns)


# ---- compiled worlds: check on a .world or .tmj, and the world preview (GAMES-286 decision 13, W9). Both read the
# runtime files as they are (a Tiled-authored world too) and run world_rules on them, as the compile does.

TILED_EXTS = (".world", ".tmj")


def tiled_format(path, data):
    """Why a room can't be read at all (the harness loader's rejections, design 02 · Formats, made before the rules
    run), or None: only orthogonal, finite maps with JSON-array tile data."""
    if data.get("orientation", "orthogonal") != "orthogonal":
        return f"{path} is {data.get('orientation')!r}: the rules and the harness read orthogonal maps only"
    if data.get("infinite"):
        return f"{path} is an infinite map: in Tiled, Map > Map Properties, untick Infinite"
    for t in data.get("tilesets") or ():
        if isinstance(t, dict) and str(t.get("source", "")).endswith(".tsx"):
            return (f"{path}: tileset {t['source']} is Tiled's XML format: export the tileset as JSON (.tsj) and "
                    "point the map at it")
    for layer in all_layers(data.get("layers") or ()):
        if layer.get("type") == "tilelayer" and not isinstance(layer.get("data"), list):
            return (f"{path}: layer {layer.get('name', '')!r} isn't a JSON array of tiles: in Tiled, Map > Map "
                    "Properties, Tile Layer Format: CSV")
    return None


def tiled_reader(fake=None):
    """read(path) for world_rules over files on disk: parsed JSON, or None when there's none; a room in a format
    nothing reads is E_WORLD (tiled_format). fake: {path: JSON} served first (a lone .tmj's one-room world)."""
    def read(p):
        if fake and p in fake:
            return fake[p]
        got = read_json(p)
        if isinstance(got, dict) and (got.get("type") == "map" or "layers" in got):
            why = tiled_format(p, got)
            if why:
                fail("E_WORLD", why, path=p)
        return got
    return read


def tiled_world(path):
    """A .world, or a .tmj as a world of that one room (placed at 0,0; the rooms its doors lead to are its interiors),
    as world_rules reads it: (the world's path, read). A file that isn't one is an error; so is a .tmj that's a room
    of a .world beside it or one directory up (its start, edges and doors are that world's: check the world)."""
    p = posixpath.normpath(pathlib.PurePath(path).as_posix())
    if is_room_src(p):
        fail("E_BAD_ARG", f"{path} is a world source; this reads the compiled Tiled files (.world, .tmj): 'pxart export "
             f"{path} --tiled' writes them beside it, and 'pxart check {path}' checks the source without writing")
    if not p.endswith(TILED_EXTS):
        fail("E_BAD_ARG", f"{path}: give a Tiled world (.world) or map (.tmj)")
    try:
        with open(p) as fh:
            data = json.load(fh)
    except ValueError as e:
        fail("E_WORLD", f"not JSON: {getattr(e, 'msg', e)}", path=p, line=getattr(e, "lineno", None),
             col=getattr(e, "colno", None))
    if p.endswith(".world"):
        if not isinstance(data, dict) or not isinstance(data.get("maps"), list):
            fail("E_WORLD", 'a Tiled world is a JSON object with a "maps" list ({"fileName", "x", "y", ...} each)',
                 path=p)
        tmx = [m.get("fileName") for m in data["maps"] if isinstance(m, dict) and
               str(m.get("fileName", "")).endswith(".tmx")]
        if tmx:
            fail("E_WORLD", f"places {tmx[0]}, Tiled's XML format: save each map as JSON (.tmj) and name those",
                 path=p)
        if data.get("patterns"):
            fail("E_WORLD", "places its maps by 'patterns' (a regexp over file names); list each map in 'maps' (in "
                 "Tiled, a world whose rooms you drag places them that way)", path=p)
        return p, tiled_reader()
    if not isinstance(data, dict) or not (data.get("type") == "map" or "layers" in data):
        fail("E_WORLD", 'a Tiled map is a JSON object with "type": "map" and its "layers"', path=p)
    why = tiled_format(p, data)
    if why:
        fail("E_WORLD", why, path=p)
    held = world_holding(p)
    if held:
        fail("E_WORLD", f"{p} is a room of {held[0]} ({held[1]}): its start, edges and doors are the world's; give "
             f"the world ({held[0]})", path=p)
    fake = posixpath.join(posixpath.dirname(p), posixpath.basename(p) + ".world")  # a name no file has: the one room
    return fake, tiled_reader({fake: {"type": "world", "maps": [
        {"fileName": posixpath.basename(p), "x": 0, "y": 0, "width": int(data.get("width") or 0)
         * int(data.get("tilewidth") or 0), "height": int(data.get("height") or 0) * int(data.get("tileheight") or 0)}]}})


def world_holding(tmj):
    """The .world beside tmj, or one directory up, whose world has it (placed, or an interior through its doors):
    (that .world, 'placed' or 'an interior'), or None. Its rooms are found as the rules find them."""
    want = os.path.realpath(tmj)
    here = pathlib.Path(tmj).resolve().parent
    for d in dict.fromkeys((here, here.parent)):
        for wp in sorted(d.glob("*.world")):
            name = wp.as_posix() if os.path.isabs(tmj) else posix_rel(wp, os.getcwd())
            data = read_json(wp)
            why = "it isn't JSON, or can't be read" if data is None else None
            if why is None and (not isinstance(data, dict) or not isinstance(data.get("maps"), list)):
                why = 'it has no "maps" list'
            model = {}
            if why is None:
                try:
                    world_rules(name, tiled_reader(), model)
                except PxError as e:
                    why = "; ".join(i.msg for i in e.issues)
            if why:  # never checked as a lone room when a world beside it might hold it
                fail("E_WORLD", f"{name} is beside it and can't be loaded ({why}), so whether {tmj} is one of its "
                     f"rooms can't be told; fix {name}, or check it", path=tmj)
            for rp, r in (model.get("rooms") or {}).items():
                if r is not None and os.path.realpath(rp) == want:
                    return name, "placed" if r in model["placed"] else "an interior"
    return None


def load_tiled(path):
    """world_rules on a compiled world (tiled_world): (the issues, the model it filled, the path to name for issues
    that have no room: the file given)."""
    wp, read = tiled_world(path)
    model = {}
    return world_rules(wp, read, model), model, posixpath.normpath(pathlib.PurePath(path).as_posix())


def rule_where(i, model, shown):
    """The file an issue is about: its room's .tmj (the first of that id), else the file given."""
    return next((r.path for r in model.get("live") or () if r.id == i.room), shown)


def rule_line(i, model, shown):
    """A rule issue as check and world print it: 'rooms/point.tmj: E_WORLD: door-pair [D, cell 10,7]: ...' for an
    error, 'rooms/cove.tmj: edge-one-side [north, cell 1,0]: ...' for a warning (check puts WARNING: first)."""
    tag = [str(i.name)] if i.name not in (None, "") else []
    tag += [f"cell {i.cell[0]},{i.cell[1]}"] if i.cell is not None else []
    what = i.code + (f" [{', '.join(tag)}]" if tag else "")
    return f"{rule_where(i, model, shown)}: " + ("E_WORLD: " if i.level == "error" else "") + f"{what}: {i.msg}"


def tiled_summary(model):
    """'3 rooms placed, interior tower, 1 door pair, start in shore', as check says it of a world source."""
    placed = model.get("placed") or []
    inner = [r.id for r in model.get("live") or () if r not in placed]
    pairs = len(model.get("partner") or {}) // 2
    start = model.get("start")
    return (f"{len(placed)} room{'s' * (len(placed) != 1)} placed"
            + (f", interior{'s' * (len(inner) != 1)} {', '.join(inner)}" if inner else "")
            + f", {pairs} door pair{'s' * (pairs != 1)}" + (f", start in {start[0].id}" if start else ", no start"))


def check_tiled(path):
    """check on a .world or .tmj: the world rules, exactly as export --tiled runs them on what it compiles. (ok, how
    many warnings it printed)."""
    try:
        issues, model, shown = load_tiled(path)
    except PxError as e:
        print(f"FAIL {path}: {len(e.issues)} error(s)")
        for i in e.issues:
            print(f"     {i}")
        return False, 0
    except OSError as e:
        print(f"FAIL {path}: 1 error(s)")
        print(f"     {path}: E_FILE: {e.strerror or e}")
        return False, 0
    errs = [rule_line(i, model, shown) for i in issues if i.level == "error"]
    warns = [rule_line(i, model, shown) for i in issues if i.level != "error"]
    if errs:
        print(f"FAIL {path}: {len(errs)} error(s)")
        for x in errs:
            print(f"     {x}")
    else:
        print(f"ok   {path}: {tiled_summary(model)}")
    for x in warns:
        print(f"     WARNING: {x}")
    return not errs, len(warns)


# ---- drawing a room as Tiled does, and the world preview

def tile_art(ts, tid, cache, missing):
    """A tile's art (RGBA), from its tileset's sheet or its own image; None when the file can't be read (named once
    in missing)."""
    key = (str(ts.path), tid)
    if key in cache:
        return cache[key]
    d, t, img = ts.data, ts.tiles.get(tid, {}), None
    src = d.get("image") if ts.sheet else t.get("image")
    where = ts.path.parent / src if src else None
    try:
        if where is None:
            raise OSError
        full = Image.open(where).convert("RGBA")
    except OSError:
        missing.setdefault(str(where or f"{ts.path} tile {tid}"), None)
        cache[key] = None
        return None
    if ts.sheet:
        tw, th = int(d["tilewidth"]), int(d["tileheight"])
        cols = int(d.get("columns") or max(1, full.width // tw))
        m, sp = int(d.get("margin") or 0), int(d.get("spacing") or 0)
        x, y = m + (tid % cols) * (tw + sp), m + (tid // cols) * (th + sp)
        img = full.crop((x, y, x + tw, y + th))
    elif "x" in t and "width" in t:  # a collection tile that is part of its image (Tiled 1.9+)
        x, y = int(t["x"]), int(t.get("y") or 0)
        img = full.crop((x, y, x + int(t["width"]), y + int(t["height"])))
    else:
        img = full
    cache[key] = img
    return img


def gid_art(room, gid, cache, missing):
    """A GID's art, flipped as its flags say (diagonal first, then horizontal, then vertical: the rules' order)."""
    ts, tid = room.tile(gid)
    img = tile_art(ts, tid, cache, missing) if ts is not None and ts.has(tid) else None
    if img is None:
        return None
    if gid & GID_D:
        img = img.transpose(Image.TRANSPOSE)
    if gid & GID_H:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if gid & GID_V:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    return img


def tiled_room_image(room, cache=None, missing=None):
    """A loaded room (RuleRoom) drawn as Tiled draws an orthogonal map, at 1x: visible tile layers cell by cell, each
    tile's art with its bottom-left on the cell's bottom-left; visible object layers' tile objects (in index order,
    or by y for draworder topdown), each art's bottom-left at the object's x,y, scaled to its size; GID flips; group
    layers and their visibility and opacity. Markers draw, as in Tiled. Art that can't be read is left out and
    named in missing ({path: None})."""
    cache = {} if cache is None else cache
    missing = {} if missing is None else missing
    tw, th = room.tw, room.th
    canvas = Image.new("RGBA", (room.w * tw, room.h * th), (0, 0, 0, 0))

    def layers(ls, opacity):
        for layer in ls:
            if not isinstance(layer, dict) or not layer.get("visible", True):
                continue
            op = opacity * float(layer.get("opacity", 1) if layer.get("opacity") is not None else 1)
            if layer.get("type") == "group":
                layers(layer.get("layers") or (), op)
                continue
            art = []
            if layer.get("type") == "tilelayer":
                lw = int(layer.get("width") or room.w)
                for i, g in enumerate(layer.get("data") or ()):
                    img = gid_art(room, g, cache, missing) if g else None
                    if img is not None:
                        art.append((img, (i % lw) * tw, (i // lw + 1) * th - img.height))
            elif layer.get("type") == "objectgroup":
                objs = [o for o in layer.get("objects") or () if isinstance(o, dict) and o.get("gid")
                        and o.get("visible", True)]
                if layer.get("draworder", "topdown") == "topdown":
                    objs = sorted(objs, key=lambda o: float(o.get("y") or 0))
                for o in objs:
                    img = gid_art(room, o["gid"], cache, missing)
                    if img is None:
                        continue
                    w, h = round(float(o.get("width") or img.width)), round(float(o.get("height") or img.height))
                    if (w, h) != img.size and w > 0 and h > 0:
                        img = img.resize((w, h), Image.NEAREST)
                    art.append((img, round(float(o.get("x") or 0)), round(float(o.get("y") or 0)) - img.height))
            if op >= 1:
                for img, x, y in art:
                    draw_at(canvas, img, x, y)
            elif art:
                sheet = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                for img, x, y in art:
                    draw_at(sheet, img, x, y)
                sheet.putalpha(sheet.getchannel("A").point(lambda v: round(v * max(0.0, op))))
                canvas.alpha_composite(sheet)
    layers(room.data.get("layers") or (), 1.0)
    return canvas


WP_BG, WP_ROOM, WP_LINE, WP_TEXT = (30, 33, 45, 255), (44, 48, 62, 255), (96, 102, 120, 255), (220, 224, 235, 255)
WP_EDGE, WP_DOOR, WP_START = (255, 210, 60, 255), (255, 120, 110, 255), (90, 230, 120, 255)
WP_MARKER, WP_ISSUE = (110, 210, 255, 255), (255, 60, 220, 255)
WP_MARGIN, WP_GAP, WP_LABEL = 16, 32, 14  # screen px: around the picture, between rooms, a text line
WP_KEY = [(WP_EDGE, "edge crossing"), (WP_DOOR, "door, its link, where you arrive"), (WP_START, "start"),
          (WP_MARKER, "marker"), (WP_ISSUE, "rule issue [n]")]


def world_layout(model, scale):
    """Where each room goes in the preview, in screen px: {room path: (x, y, w, h)}, the placed rooms (and any the
    .world places but can't load) at their world positions, times scale, spread apart by WP_GAP at each distinct left
    and top (so rooms that share a side show a gap to draw the edge in, and nothing overlaps that didn't); the
    interiors in a column to their right. Returns (boxes, the .world's missing entries [(fileName, box)])."""
    wd = posixpath.dirname(model.get("world_path") or "")
    rects = []  # (key, world x, y, w, h)
    for r in model.get("placed") or ():
        rects.append((r.path, r.pos[0], r.pos[1], r.w * r.tw, r.h * r.th))
    missing = []
    for m in (model.get("world") or {}).get("maps") or ():
        p = posixpath.normpath(posixpath.join(wd, m.get("fileName", "")))
        if (model.get("rooms") or {}).get(p) is None:
            rects.append((("missing", p), float(m.get("x") or 0), float(m.get("y") or 0),
                          float(m.get("width") or 0) or 64, float(m.get("height") or 0) or 64))
    xs = sorted({x for _, x, _, _, _ in rects})
    ys = sorted({y for _, _, y, _, _ in rects})
    x0 = min(xs, default=0)
    y0 = min(ys, default=0)
    boxes, right = {}, WP_MARGIN
    for key, x, y, w, h in rects:
        sx = WP_MARGIN + round((x - x0) * scale) + WP_GAP * xs.index(x)
        sy = WP_MARGIN + WP_LABEL + round((y - y0) * scale) + WP_GAP * ys.index(y)
        boxes[key] = (sx, sy, round(w * scale), round(h * scale))
        right = max(right, sx + round(w * scale))
    ix = right + WP_GAP * 2 if rects else WP_MARGIN
    iy = WP_MARGIN + WP_LABEL
    for r in model.get("live") or ():
        if r.path not in boxes:
            boxes[r.path] = (ix, iy, r.w * r.tw * scale, r.h * r.th * scale)
            iy += r.h * r.th * scale + WP_GAP
    return ({k: v for k, v in boxes.items() if not isinstance(k, tuple)},
            [(k[1], v) for k, v in boxes.items() if isinstance(k, tuple)])


def cell_box(box, room, c, scale):
    """A room's cell c on screen: (x0, y0, x1, y1), x1/y1 inclusive."""
    x, y = box[0] + c[0] * room.tw * scale, box[1] + c[1] * room.th * scale
    return x, y, x + room.tw * scale - 1, y + room.th * scale - 1


def arrow_head(d, tip, frm, color, size):
    """A filled arrowhead at tip, pointing away from frm."""
    ang = math.atan2(tip[1] - frm[1], tip[0] - frm[0])
    pts = [tip] + [(tip[0] - size * math.cos(ang + s * 0.5), tip[1] - size * math.sin(ang + s * 0.5)) for s in (1, -1)]
    d.polygon(pts, fill=color)


def centre(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def door_box(box, room, o, scale):
    """A door's cells on screen, as one box (x0, y0, x1, y1) (inclusive)."""
    cells = room.door_cells(o)
    bs = [cell_box(box, room, c, scale) for c in cells]
    return min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)


def key_rows(d, font, width):
    """The key's entries laid out in rows no wider than width (a row holds at least one): [[(color, text, x)]]."""
    rows, x = [[]], WP_MARGIN
    for color, what in WP_KEY:
        w = 11 + int(d.textlength(what, font=font))
        if rows[-1] and x + w > width - WP_MARGIN:
            rows.append([])
            x = WP_MARGIN
        rows[-1].append((color, what, x))
        x += w + 14
    return rows


def is_marker(room, o):
    """SPEC: a marker is a tile object whose tile's class is character_frame, whatever the object's own class."""
    if not o.get("gid"):
        return False
    ts, tid = room.tile(o["gid"])
    return ts is not None and ts.cls(tid) == MARKER_CLASS


def place_tag(taken, x, y, w, h, right):
    """Where a tag of w x h goes, at x,y or moved right (then down a row) until it overlaps no tag already placed."""
    x = max(WP_MARGIN, min(x, right - w))  # inside the picture
    while any(x < tx + tw and tx < x + w and y < ty + th and ty < y + h for tx, ty, tw, th in taken):
        x += 2
        if x + w > right:
            x, y = WP_MARGIN, y + h + 1
    taken.append((x, y, w, h))
    return x, y


def world_preview(model, issues, shown, scale=2, tags=None):
    """The world preview (decision 13): each room drawn as Tiled draws it, the placed ones where the .world puts them
    (spread apart by a gap) and the interiors to their right, labelled; the shared edges as bands across the gap,
    from the rules' own crossings (yellow where both sides are walkable, magenta where one side is: edge-one-side,
    with that cell outlined); each door outlined, with where you arrive beside it (dots) and a line to its entry
    (arrowheads at the doors it leads to); the start and the markers; and every rule issue as a numbered magenta tag
    where it is (a cell, a door, a room; tags that would cover each other move aside), listed under the picture.
    tags: a list to fill with each tag's (n, x, y, w, h). Returns (the image, art it couldn't read)."""
    font = strip_font()
    boxes, gone = world_layout(model, scale)
    live = model.get("live") or []
    cache, missing = {}, {}
    W = max([b[0] + b[2] for b in boxes.values()] + [b[0] + b[2] for _, b in gone] + [240]) + WP_MARGIN
    body = max([b[1] + b[3] for b in boxes.values()] + [b[1] + b[3] for _, b in gone] + [WP_MARGIN]) + WP_MARGIN
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lines = []
    for n, i in enumerate(issues, 1):
        text = f"[{n}] " + ("" if i.level == "error" else "WARNING: ") + rule_line(i, model, shown)
        lines += fit_lines(probe, text, W - 2 * WP_MARGIN, font)
    keys = key_rows(probe, font, W)
    key_h = len(keys) * WP_LABEL + 4
    H = body + key_h + len(lines) * WP_LABEL + (WP_MARGIN if lines else 4)
    img = Image.new("RGBA", (W, H), WP_BG)
    d = ImageDraw.Draw(img)
    unreachable = {i.room for i in issues if i.code == "room-unreachable"}
    placed = model.get("placed") or []
    label_end = {}  # room path: where its label (and 'unreachable') ends, for its room-level tags
    for r in live:
        x, y, w, h = boxes[r.path]
        d.rectangle((x, y, x + w - 1, y + h - 1), fill=WP_ROOM)
        art = tiled_room_image(r, cache, missing)
        img.alpha_composite(art.resize((w, h), Image.NEAREST) if scale != 1 else art, (x, y))
        d.rectangle((x - 1, y - 1, x + w, y + h), outline=WP_LINE)
        label = r.id + ("" if r in placed else " (interior)")
        d.text((x, y - WP_LABEL), label, fill=WP_TEXT, font=font)
        label_end[r.path] = x + int(d.textlength(label, font=font)) + 6
        if r.id in unreachable:  # hatched: nothing here can be reached
            hatch = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            hd = ImageDraw.Draw(hatch)
            for k in range(0, w + h, 8):
                hd.line((k, 0, k - h, h), fill=WP_ISSUE)
            img.alpha_composite(hatch, (x, y))
            d.text((label_end[r.path], y - WP_LABEL), "unreachable", fill=WP_ISSUE, font=font)
            label_end[r.path] += int(d.textlength("unreachable", font=font)) + 6
    for fn, (x, y, w, h) in gone:  # crossed out: the .world places a room that can't be loaded
        d.rectangle((x, y, x + w - 1, y + h - 1), outline=WP_ISSUE)
        d.line((x, y, x + w - 1, y + h - 1), fill=WP_ISSUE)
        d.line((x, y + h - 1, x + w - 1, y), fill=WP_ISSUE)
        d.text((x, y - WP_LABEL), f"{posixpath.basename(fn)} (can't be loaded)", fill=WP_ISSUE, font=font)
    # the shared edges, from the rules' crossings: a band across the gap per border cell that isn't solid; yellow
    # when the cell across is walkable too, magenta (and the cell outlined) when it isn't: edge-one-side
    for a, side, ca, b, cb in model.get("crossings") or ():
        if not a.walkable(ca):
            continue  # a wall on this side: the crossing the other way draws it, if that side is walkable
        color = WP_EDGE if b.walkable(cb) else WP_ISSUE
        pa, pb = cell_box(boxes[a.path], a, ca, scale), cell_box(boxes[b.path], b, cb, scale)
        if side in ("east", "west"):
            ax = pa[2] + 2 if side == "east" else pa[0] - 2
            bx = pb[0] - 2 if side == "east" else pb[2] + 2
            d.polygon([(ax, pa[1] + 1), (bx, pb[1] + 1), (bx, pb[3] - 1), (ax, pa[3] - 1)], fill=color)
        else:
            ay = pa[3] + 2 if side == "south" else pa[1] - WP_LABEL - 1  # clear of the lower room's label
            by = pb[1] - WP_LABEL - 1 if side == "south" else pb[3] + 2
            d.polygon([(pa[0] + 1, ay), (pb[0] + 1, by), (pb[2] - 1, by), (pa[2] - 1, ay)], fill=color)
        if color == WP_ISSUE:
            d.rectangle(pa, outline=WP_ISSUE)
    # doors: outline, arrival dots, the link to the entry. A door an issue names (by its name and first cell) is
    # magenta, and so is one door-name-dup skips (drawn, with no link: the rules leave it out of everything else)
    bad = {(i.room, i.name, tuple(i.cell)) for i in issues if i.code.startswith("door") and i.cell is not None}
    drawn = set()
    dot = max(1, scale)
    targets, rooms = model.get("targets") or {}, model.get("rooms") or {}

    def outline(r, o, broken):
        db = door_box(boxes[r.path], r, o, scale)
        color = WP_ISSUE if broken else WP_DOOR
        d.rectangle(db, outline=color, width=max(1, scale // 2 + 1))
        top = db[1] - WP_LABEL + 1
        ty = top if top >= boxes[r.path][1] else db[3] + 2  # the top row: below the door, clear of the room's label
        d.text((db[0], ty), str(o.get("name", "")), fill=color, font=font)
        return db
    for r in live:
        for o in r.doors:
            db = outline(r, o, (r.id, o.get("name", ""), r.door_cells(o)[0]) in bad)
            for c in r.beside(o):
                cx, cy = centre(cell_box(boxes[r.path], r, c, scale))
                d.rectangle((cx - dot, cy - dot, cx + dot - 1, cy + dot - 1), fill=WP_DOOR)
            pair = (model.get("partner") or {}).get((r.path, id(o)))
            if pair:
                tr, back = pair
                if (tr.path, id(back)) in drawn:
                    continue
                drawn.add((r.path, id(o)))
                p0, p1 = centre(db), centre(door_box(boxes[tr.path], tr, back, scale))
                d.line((p0, p1), fill=WP_DOOR, width=max(1, scale))
                arrow_head(d, p1, p0, WP_DOOR, 4 + 2 * scale)
                arrow_head(d, p0, p1, WP_DOOR, 4 + 2 * scale)
                continue
            tr = rooms.get(targets.get((r.path, id(o))))  # a door that doesn't pair: one-way, where it points
            there = [x for x in (tr.doors if tr else ()) if x.get("name") == tiled_props(o).get("entry")]
            if tr is not None and tr.path in boxes and there:
                p0, p1 = centre(db), centre(door_box(boxes[tr.path], tr, there[0], scale))
                d.line((p0, p1), fill=WP_ISSUE, width=max(1, scale))
                arrow_head(d, p1, p0, WP_ISSUE, 4 + 2 * scale)
    for r, o in model.get("dup_doors") or ():
        outline(r, o, True)
    # markers, then the start over them (the start is often a marker's cell: the keeper's @)
    for r in live:
        for layer in all_layers(r.data.get("layers") or ()):
            for o in layer.get("objects") or () if layer.get("type") == "objectgroup" else ():
                if not isinstance(o, dict) or not is_marker(r, o):
                    continue
                x, y, w, h = (float(o.get(k) or 0) for k in ("x", "y", "width", "height"))
                bx, by = boxes[r.path][:2]
                cx, cy = bx + (x + w / 2) * scale, by + (y - h / 2) * scale
                rad = max(w, h) * scale / 2 + 2
                d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=WP_MARKER, width=max(1, scale // 2))
    for r in live:
        for o in r.starts:
            c = start_cell(o, r.tw, r.th)
            ok = model.get("start") is not None and model["start"][0] is r
            sb = cell_box(boxes[r.path], r, c, scale)
            d.rectangle(sb, outline=WP_START if ok else WP_ISSUE, width=max(1, scale // 2 + 1))
            d.text((sb[0], sb[3] + 2), "start", fill=WP_START if ok else WP_ISSUE, font=font)
    # every issue, numbered where it is; a tag that would cover another moves right (then down)
    taken = []
    for n, i in enumerate(issues, 1):
        r = next((x for x in live if x.id == i.room), None)
        if r is not None and i.cell is not None:
            at = cell_box(boxes[r.path], r, i.cell, scale)[:2]
        elif r is not None:
            at = (label_end[r.path], boxes[r.path][1] - WP_LABEL)
        else:
            g = next((b for fn, b in gone if pathlib.PurePath(fn).stem == i.room), None)
            at = (g[0], g[1]) if g else (WP_MARGIN, 2)
        tag = f"[{n}]"
        tw_ = int(d.textlength(tag, font=font)) + 4
        x, y = place_tag(taken, at[0], at[1], tw_, WP_LABEL - 1, W)
        d.rectangle((x, y, x + tw_ - 1, y + WP_LABEL - 2), fill=WP_ISSUE)
        d.text((x + 2, y), tag, fill=WP_BG, font=font)
        if tags is not None:
            tags.append((n, x, y, tw_, WP_LABEL - 1))
    # the key (wrapped to the picture), then the issues
    for k, row in enumerate(keys):
        ky = body + k * WP_LABEL
        for color, what, x in row:
            d.rectangle((x, ky + 3, x + 7, ky + 10), fill=color)
            d.text((x + 11, ky), what, fill=WP_TEXT, font=font)
    for k, line in enumerate(lines):
        d.text((WP_MARGIN, body + key_h + k * WP_LABEL), line, fill=WP_ISSUE, font=font)
    return img, list(missing)


def cmd_world(a):
    """pxart world W.world|ROOM.tmj -o world.png: the world preview (world_preview), and what the rules say."""
    need_o(a, "world.png")
    if a.scale < 1:
        fail("E_BAD_ARG", f"--scale {a.scale}: a whole number, 1 or more")
    if a.o:
        save_image(Image.new("RGBA", (1, 1)), a.o, check_only=True)
    issues, model, shown = load_tiled(a.world)
    img, missing = world_preview(model, issues, shown, a.scale)
    for m in missing:
        print(f"note: {m} can't be read; its tiles are left out of the picture")
    for n, i in enumerate(issues, 1):
        print(f"[{n}] " + ("" if i.level == "error" else "WARNING: ") + rule_line(i, model, shown))
    ne, nw = sum(i.level == "error" for i in issues), sum(i.level != "error" for i in issues)
    said = [f"{ne} error{'s' * (ne != 1)}"] * bool(ne) + [f"{nw} warning{'s' * (nw != 1)}"] * bool(nw)
    save_image(img, a.o, about=f"{tiled_summary(model)}, at --scale {a.scale}", smaller="a lower --scale makes "
               "it smaller")
    print(wrote(a.o) + f": {shown}, {tiled_summary(model)}" + (
        f"; {' and '.join(said)}, tagged [n] in the picture" if said else ""))


def cmd_from_png(a):
    """PNG(s) -> .px. Colors already in OUT's palette keep their keys; new colors get free keys. --grid slices one
    sheet into frames (sheet_cells)."""
    if a.by and not a.grid:
        fail("E_BAD_ARG", "--by goes with --grid WxH (the sheet's cells)")
    if a.grid and len(a.pngs) > 1:
        fail("E_BAD_ARG", f"--grid slices one sheet; give one PNG (got {len(a.pngs)})")
    if a.grid and (a.prefix_dir or a.labels):
        fail("E_BAD_ARG", f"{'--prefix-dir' if a.prefix_dir else '--labels'} names loose PNGs; a --grid sheet's frames "
             "are named by --names or its rows")
    if a.names is not None and a.labels:
        fail("E_BAD_ARG", "give --names (one name per PNG) or --labels FILE.csv, not both")
    for flag, v in (("--label-col", a.label_col), ("--file-col", a.file_col)):
        if v is not None and not a.labels:
            fail("E_BAD_ARG", f"{flag} names a column of --labels FILE.csv; give --labels too")
    imgs = []
    for p in a.pngs:
        with reading(f"PNG ({p})"):
            imgs.append((pathlib.Path(p), Image.open(p).convert("RGBA")))
    names = None if a.grid else loose_names([p for p, _ in imgs], a)
    cells, notes = sheet_cells(imgs[0][0], imgs[0][1], a) if a.grid else (None, [])
    out = pathlib.Path(a.o) if a.o else None
    if out and out.exists():
        with reading(f"-o ({a.o})"):
            doc = parse(out, allow_empty=True)
    else:
        doc = start_doc(out or imgs[0][0].with_suffix(".px"), a.palette)
    named = bool(a.id) or a.prefix_dir or names is not None or len(imgs) > 1 or (doc.frames and not doc.implicit) or (out and out.exists()) or bool(a.grid)
    if named and doc.implicit:
        if not ID_RE.match(doc.stem):
            fail("E_MIXED_FRAMES", f"{out} holds one unnamed grid, and its name {doc.stem!r} can't be a frame id to "
                 "give it; import into a new file or one with @frame ids")
        doc.promote()
        print(f"note: {out}'s unnamed grid is now '@frame {doc.stem}' (the id it went by)")
    for n in notes:
        print(f"note: {n}")
    keyof = {c: k for k, c in doc.resolved().items() if c[3]}
    free = [k for k in KEYS if k not in doc.resolved()]
    entries = cells if cells is not None else [(png_id(path, a, name), path, img) for (path, img), name
                                               in zip(imgs, names or [None] * len(imgs)) if name != ""]
    for (path, _), name in zip(imgs, names or ()):
        if name == "":
            print(f"note: {path} skipped (its name is empty)")
    if not entries:
        fail("E_BAD_ARG", "every PNG's name is empty: nothing to import")
    if named:
        same_ids(entries, names is not None)
    replaced = [fid for fid, *_ in entries if named and doc.get(fid)]
    if a.colors is not None:
        entries = reduce_colors(entries, a.colors)
    for fid, path, img in entries:
        for c in colors(img):
            if c not in keyof:
                if not free:
                    fail("E_BAD_ARG", f"{path}: out of palette keys ({len(KEYS)} max)"
                         + ("" if a.colors is not None else
                            f"; --colors N reduces the PNGs to N colors first ({len(set().union(*(colors(i) for *_, i in entries)))} now)"))
                keyof[c] = free.pop(0)
                doc.palette[keyof[c]] = c
        grid = ["".join(keyof[p] if p[3] else "." for p in (img.getpixel((x, y)) for x in range(img.width)))
                for y in range(img.height)]
        if not named:
            doc.implicit, doc.frames = True, [Frame(None, grid)]
            continue
        old = doc.get(fid)
        if old:
            old.grid = grid
        else:
            doc.frames.append(Frame(fid, grid))
    if out:
        print(write_doc(doc, out) + (f" ({len(entries)} frame(s)" + (f": {said_cells(entries)}" if a.grid else "")
                                     + (f"; replaced {listed(replaced, 5)}, which {out} had" if replaced else "")
                                     + ")" if named else ""))
    else:
        print(doc.text(), end="")


def reduce_colors(entries, n):
    """from-png --colors N: every entry's pixels, all together, reduced to at most N colors (alpha too: octree, no
    dither), so a photo or a painting fits the palette keys. A fully transparent pixel stays transparent. Prints how far
    the result is from the PNGs: per channel, alpha-weighted, 0-255."""
    if not 1 <= n <= len(KEYS):
        fail("E_BAD_ARG", f"--colors {n}: give 1 to {len(KEYS)} (a palette has {len(KEYS)} keys)")
    before = set().union(*(colors(img) for *_, img in entries))
    if len(before) <= n:
        print(f"note: --colors {n}: the PNGs have {len(before)} color(s) already; nothing reduced")
        return entries
    # Only the drawn pixels go in, so a dark color can't merge with the transparent background and vanish.
    drawn = [p for *_, img in entries for p in pixels(img) if p[3]]
    row = Image.new("RGBA", (len(drawn), 1))
    row.putdata(drawn)
    q = iter(pixels(row.quantize(n, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).convert("RGBA")))
    out, errs = [], []
    for fid, path, img in entries:
        src = list(pixels(img))
        dst = [next(q) if p[3] else (0, 0, 0, 0) for p in src]
        r = Image.new("RGBA", img.size)
        r.putdata(dst)
        errs += [max(abs(p[3] - d[3]), *(abs(u * p[3] - v * d[3]) // 255 for u, v in zip(p[:3], d[:3])))
                 for p, d in zip(src, dst) if p[3]]
        out.append((fid, path, r))
    after = set().union(*(colors(img) for *_, img in out))
    far = sum(e > 16 for e in errs)
    print(f"reduced {len(before)} colors to {len(after)} (--colors {n}): off by {sum(errs) / max(len(errs), 1):.1f} "
          f"on average, {max(errs, default=0)} at most (per channel, alpha-weighted, 0-255); "
          f"{far} of {len(errs)} drawn px off by more than 16")
    return out


def png_id(path, a, name=None):
    """A loose PNG's frame id: its name (--names, --labels) or stem, after its folder's name with --prefix-dir
    (dungeon/tile_0002), with --id PREFIX in front. In a stem or a --labels name a char an id can't have becomes '_';
    a --names name is the id as typed, so a bad one is E_BAD_ID."""
    typed = name is not None and not a.labels
    fid = path.stem if name is None else name
    if not typed:
        fid = re.sub(r"[^A-Za-z0-9_\-./]", "_", fid)
    if a.prefix_dir:
        folder = re.sub(r"[^A-Za-z0-9_\-.]", "_", path.resolve().parent.name)
        fid = f"{folder}/{fid}" if folder else fid
    fid = f"{a.id}/{fid}" if a.id else fid
    fid = fid if typed else re.sub(r"[^A-Za-z0-9_\-./]", "_", fid)
    if not ID_RE.match(fid):
        fail("E_BAD_ID", f"{path}: {fid!r} can't be a frame id (letters, digits, _ - . and / between parts)")
    return fid


def loose_names(paths, a):
    """from-png's loose PNGs' names, one per PNG in order, or None for their stems: --names A,B,... (one per PNG; ''
    skips one), or --labels FILE.csv (repeatable), whose --file-col names each PNG relative to the CSV's own directory
    (or by its file name alone) and whose --label-col gives its name. A PNG no CSV names is E_SELECT, as is one two rows
    name differently."""
    if a.names is not None:
        names = a.names.split(",")
        if len(names) != len(paths):
            fail("E_BAD_ARG", f"--names has {len(names)} name{'s' * (len(names) != 1)} and there are {len(paths)} "
                 f"PNGs; give one per PNG, in order ('' skips one)")
        return names
    if not a.labels:
        return None
    name_of = csv_labels(a)
    names, unnamed = [], []
    for p in paths:
        got = name_of(p)
        if got is None:
            unnamed.append(str(p))
        names.append(got)
    if unnamed:
        fail("E_SELECT", f"--labels names no row for {listed(unnamed, 5)}; add them to the CSV (column "
             f"{a.file_col or 'filename'}) or leave them out")
    return names


def csv_labels(a):
    """--labels FILE.csv (repeatable) [--file-col] [--label-col], as from-png and diff read them: a function from a PNG's
    path to its name, or None when no row names it. A row's --file-col names a PNG relative to the CSV's own directory,
    or else by its file name alone (when no CSV's directory holds it); a file name that two CSVs name differently, or
    a PNG two rows name differently, is an error."""
    fcol, lcol = a.file_col or "filename", a.label_col or "proposed_name"
    by_path, by_name = {}, {}  # resolved path -> (name, where); file name -> [(name, where)]
    for csv_path in a.labels:
        with reading(f"--labels ({csv_path})"), open(csv_path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        head = [h.strip() for h in rows[0]] if rows else []
        missing = [c for c in (fcol, lcol) if c not in head]
        if missing:
            fail("E_BAD_ARG", f"--labels {csv_path}: no column {' or '.join(map(repr, missing))} (its columns: "
                 f"{', '.join(head) or 'none'}); pick them with --file-col and --label-col")
        fi, li = head.index(fcol), head.index(lcol)
        for n, row in enumerate(rows[1:], 2):
            if len(row) <= max(fi, li) or not row[fi].strip():
                continue
            file, name, where = row[fi].strip(), row[li].strip(), f"{csv_path}:{n}"
            if not name:
                fail("E_BAD_ARG", f"--labels {where}: {file} has no {lcol}")
            key = (pathlib.Path(csv_path).parent / file).resolve()
            if key in by_path and by_path[key][0] != name:
                fail("E_BAD_ARG", f"--labels: {file} is named twice: {by_path[key][0]!r} ({by_path[key][1]}) and "
                     f"{name!r} ({where})")
            by_path[key] = (name, where)
            by_name.setdefault(pathlib.PurePath(file).name, []).append((name, where))

    def name_of(p):
        p = pathlib.Path(p)
        got = by_path.get(p.resolve())
        if got is None:
            alike = {n for n, _ in by_name.get(p.name, [])}
            if len(alike) > 1:
                fail("E_SELECT", f"--labels: {p} is in no CSV's directory, and its file name {p.name} has several "
                     f"names: {', '.join(sorted(alike))}; put the CSV beside the PNGs it names")
            got = by_name[p.name][0] if alike else None
        return got[0] if got else None
    return name_of


def same_ids(entries, named=False):
    """from-png's frames, [(id, path, image)], must have one id each: a second PNG under an id would replace the first
    one in OUT (two packs' tile_0002.png). E_DUP_FRAME naming each id and its PNGs, and the ways to tell them apart
    (named: the ids came from --names or --labels already)."""
    paths = {}
    for fid, path, _ in entries:
        paths.setdefault(fid, []).append(str(path))
    twice = {fid: ps for fid, ps in paths.items() if len(ps) > 1}
    if twice:
        fail("E_DUP_FRAME", "PNGs that would get one frame id (the later would replace the earlier): "
             + "; ".join(f"{fid} ({', '.join(ps)})" for fid, ps in twice.items())
             + ("; tell them apart with --prefix-dir (ids FOLDER/NAME: dungeon/bat), or other names" if named else
                "; tell them apart with --prefix-dir (ids FOLDER/STEM: dungeon/tile_0002), --names A,B,... (one id "
                "per PNG, in order) or --labels FILE.csv"))


def sheet_cells(path, img, a):
    """from-png SHEET --grid WxH [--names A,B,...] [--by rows|cols]: the sheet's cells as frames, [(id, path, image)].
    Each row (--by cols: each column) is a group: named by --names in turn, else row0, row1 (col0, ...) under the
    sheet's stem; --id PREFIX goes in front of either. Its cells, left to right (top to bottom), are its frames 0, 1,
    ... counting only cells with an opaque pixel: empty ones are skipped. An empty name skips its row. Returns the
    cells and notes (a sheet whose size isn't a multiple of the grid, when the strip left over is empty)."""
    w, h = parse_size(a.grid, "--grid")
    by = a.by or "rows"
    if by not in ("rows", "cols"):
        fail("E_BAD_ARG", f"--by {by}: want rows (each row a group) or cols (each column a group)")
    cols, rows = img.width // w, img.height // h
    if not cols or not rows:
        fail("E_BAD_ARG", f"--grid {a.grid}: {path} is {img.width}x{img.height}, smaller than one cell")
    notes = []
    for what, box in (("right", (cols * w, 0, img.width, img.height)),
                      ("bottom", (0, rows * h, img.width, img.height))):
        if box[0] < box[2] and box[1] < box[3]:
            strip = f"the {box[2] - box[0] if what == 'right' else box[3] - box[1]}px strip at the {what}"
            if img.crop(box).getchannel("A").getbbox():
                fail("E_BAD_ARG", f"--grid {a.grid}: {path} is {img.width}x{img.height}, not a whole number of "
                     f"{w}x{h} cells, and {strip} has pixels; check the cell size")
            notes.append(f"{path} is {img.width}x{img.height}: {strip} is empty and left out")
    groups = rows if by == "rows" else cols
    names = a.names.split(",") if a.names is not None else None
    word = "row" if by == "rows" else "column"
    if names is not None and len(names) > groups:
        fail("E_BAD_ARG", f"--names has {len(names)} names and {path} has {groups} {word}s of {w}x{h} cells")
    out, blank = [], 0
    for g in range(groups):
        spots = [(g, c) for c in range(cols)] if by == "rows" else [(r, g) for r in range(rows)]
        cells = [img.crop((c * w, r * h, c * w + w, r * h + h)) for r, c in spots]
        full = [cell for cell in cells if cell.getchannel("A").getbbox()]
        blank += len(cells) - len(full)
        if names is not None and g >= len(names):
            if full:
                fail("E_BAD_ARG", f"--names has {len(names)} names, and {word} {g} of {path} has frames too; name "
                     f"every {word} with frames ('' skips one)")
            continue
        stem = re.sub(r"[^A-Za-z0-9_\-.]", "_", path.stem)
        name = names[g] if names is not None else ("" if a.id else f"{stem}/") + ("row" if by == "rows" else "col") \
            + str(g)
        if names is not None and name == "":
            if full:
                notes.append(f"{word} {g} skipped (its name is empty): {len(full)} cell(s) with pixels")
            continue
        fid_base = f"{a.id}/{name}" if a.id else name
        for i, cell in enumerate(full):
            fid = f"{fid_base}/{i}"
            if not ID_RE.match(fid):
                fail("E_BAD_ID", f"--names: {fid!r} can't be a frame id (letters, digits, _ - . and / between parts)")
            out.append((fid, path, cell))
    if not out:
        fail("E_BAD_ARG", f"--grid {a.grid}: every cell of {path} is empty")
    if blank:
        notes.append(f"{blank} empty cell{'s' * (blank != 1)} skipped")
    ids = [f for f, *_ in out]
    if len(set(ids)) < len(ids):
        dup = sorted({f for f in ids if ids.count(f) > 1})
        fail("E_DUP_FRAME", f"--names gives two {word}s one name: {', '.join(dup)}")
    return out, notes


def said_cells(entries):
    """'walk/down 4, walk/up 4': each group of the sliced frames and how many frames it got."""
    groups = {}
    for fid, *_ in entries:
        g = fid.rsplit("/", 1)[0]
        groups[g] = groups.get(g, 0) + 1
    return ", ".join(f"{g} {n}" for g, n in groups.items())


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
    "FORMAT: selecting frames": ("  Anywhere a command takes FILE", "  Paths:"),
    "FORMAT: paths": ("  Paths:", "LOOKING"),
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
    "FORMAT: paths": "what a path is read from: the current directory, or a file's own",
    "LOOKING: centering": "frames of different sizes, --bg, --dry-run",
    "EDITING": "-o OUT gets the whole file, only changed lines are rewritten, 'no change'",
    "DRAWING": "FILE[:SEL], KEY ('.' erases), clipping, 'painted N px'",
    "compose": "OUT's palette, frame placement, E_KEY_CONFLICT, --rekey",
    "scene": "--tint, items, maps",
}
EDITS = ["EDITING", "FORMAT: selecting frames"]
DRAWS = ["DRAWING", "EDITING", "FORMAT: selecting frames"]
SEE = {  # what a command's section relies on: other commands' sections (by name) and NOTES, named, not pasted
    "render": ["FORMAT: variants", "LOOKING: centering"], "sheet": ["FORMAT: variants", "LOOKING: centering"],
    "anim": ["FORMAT: frames and animation", "FORMAT: pivots and timing", "FORMAT: variants", "LOOKING: centering"],
    "onion": ["FORMAT: pivots and timing", "LOOKING: centering"],
    "scene": ["FORMAT: variants", "FORMAT: paths", "LOOKING: centering"], "tint": ["scene"],
    "world": ["LOOKING: centering"],
    "check": ["FORMAT: still groups", "FORMAT: paths"], "stats": ["FORMAT: variants", "FORMAT: selecting frames"],
    "diff": ["FORMAT: variants", "FORMAT: selecting frames"],
    "frames": ["FORMAT: frames and animation", "FORMAT: pivots and timing", "FORMAT: still groups",
               "FORMAT: selecting frames"],
    "flip": ["FORMAT: pivots and timing"] + EDITS, "shift": EDITS, "set": EDITS, "fill": EDITS,
    "new": ["compose", "FORMAT: still groups"] + EDITS, "put": ["compose"] + EDITS, "mask": EDITS,
    "crop": ["compose"] + EDITS, "extract": ["FORMAT: variants"] + EDITS, "recolor": ["FORMAT: variants"] + EDITS,
    "paste": ["compose"] + EDITS, "compose": EDITS, "dup": ["FORMAT: frames and animation"] + EDITS,
    "anim-set": ["FORMAT: frames and animation", "FORMAT: pivots and timing", "FORMAT: still groups"] + EDITS,
    "palette": ["FORMAT: variants", "FORMAT: paths"] + EDITS,
    "line": DRAWS, "rect": DRAWS, "poly": DRAWS, "ellipse": DRAWS, "arc": DRAWS, "flood": DRAWS,
    "rotate": ["FORMAT: pivots and timing"] + DRAWS, "transpose": ["FORMAT: pivots and timing"] + DRAWS,
    "shade": DRAWS, "outline": DRAWS,
    "export": ["FORMAT: frames and animation", "FORMAT: pivots and timing", "FORMAT: still groups",
               "FORMAT: variants", "FORMAT: selecting frames"],
    "from-png": ["FORMAT: paths"], "help": [],
}
SUMMARY = {  # 'pxart CMD -h': what CMD is for, in a line or three, above its options (its section's details follow them)
    "render": "Render frames to a preview PNG with a pixel grid and x/y rulers, to look at while you edit.",
    "sheet": "Many frames (.px/.png files, or every .px under a directory) side by side on one PNG, each\n"
             "labeled with its id, size and color count.",
    "anim": "An animation as one GIF, plus a strip of what changed frame to frame (the whole-sprite shift\n"
            "taken out) and one line of numbers per frame, so a walk that's secretly a bob shows up.",
    "onion": "Frame B drawn over A's silhouette, and a readout of how B's edges moved from A's ('top -1'),\n"
             "for a 1px jump too faint to see; --feet N reads only the bottom rows.",
    "scene": "Place .px/.png items at x,y (or a text tilemap with --map) on one canvas and render it,\n"
             "optionally in a variant (--variant night) or tinted (--tint).",
    "tint": "Lay a translucent color over a PNG, as scene --tint does (a night in one step).",
    "world": "Draw a compiled world (.world, or a lone .tmj): its rooms where they sit, interiors aside,\n"
             "edges, doors and where they lead, the start, markers, and every world-rule issue tagged.",
    "check": "Check .px and .map files: format errors with a code and location, size, colors, budget and\n"
             "unused keys; one line per file. Exits 1 on any failure.",
    "stats": "Size, bounding box and colors of frames, a variant's rendered colors (--colors), or one\n"
             "pixel's key and color in every variant (--at x,y).",
    "diff": "Compare renders pixel by pixel (a frame, a file, a folder of PNGs) and exit 1 when they differ:\n"
            "proof that a port or a copy renders as its original. -o DIFF.png draws what differs.",
    "frames": "List a file's frames and animations; or remove (--rm), move (--after/--before), rename\n"
              "(--rename) or copy them into another file (--copy-to).",
    "flip": "", "rotate": "", "transpose": "", "set": "", "fill": "", "rect": "",  # their usage line says it
    "shift": "Move a frame's pixels (or a region's) by dx,dy, dropping or wrapping what goes past the edge.",
    "mask": "Erase every pixel outside rectangles or circles (or inside, --invert), or by key; a PNG too.",
    "recolor": "Repaint, swap or rename palette keys in frames ('a=b', 'a<>b', 'a>b'), or give a key a new color.",
    "crop": "Cut a rectangle out of one frame into a frame of its own, in the same file or another.",
    "paste": "Copy one frame (or a region of it) onto another at x,y; '.' never overwrites.",
    "new": "Start a frame, blank or filled with one key, in a new file or an existing one; or a file with\n"
           "no frames that imports a palette (--empty).",
    "put": "Replace one frame's grid with rows from stdin (palette lines first, optionally).",
    "line": "Draw a line of a palette key between two points (Bresenham), --width N wide.",
    "poly": "Draw a closed polygon through the points, optionally --fill'ed.",
    "ellipse": "Draw a symmetric pixel ellipse (or circle), optionally --fill'ed; .5 centers give even sizes.",
    "arc": "Draw part of a circle, from angle a0 to a1 (a smear or swoosh), --width N wide.",
    "flood": "Bucket-fill the region of one key that touches x,y.",
    "outline": "Outline a frame's shape with a key, optionally lit on the side facing the light (--lit).",
    "shade": "Re-shade a material with a darkest-to-lightest ramp, by how each pixel faces the light.",
    "extract": "Write only the selected frames to a new file, with their palette, imports and @anim lines.",
    "compose": "Stack frames from any files (layers at x,y, or a --map's cells) into one frame of OUT,\n"
               "bringing their keys and variants into OUT's palette. Add --rekey when two sources (or a source\n"
               "and OUT) use the same key letter for different colors: E_KEY_CONFLICT says so.",
    "dup": "Copy a frame under a new id, placed after its animation's last frame, to edit the copy; or a\n"
           "whole group under a new name, with its timing, pivots and @anim line\n"
           "(dup hero.px:walk/right walk/left).",
    "anim-set": "Write an animation's timing and pivot on its @anim line (or one frame's), or mark it @still.",
    "palette": "List a file's palette and what each variant does; or edit it: add keys and variants, derive a\n"
               "night or dusk, hoist, import, remove, order, comment, export.",
    "export": "Write frames as PNGs (--frames), an Aseprite sheet and JSON (--aseprite) or a Tiled tileset\n"
              "(--tiled), from files or whole folders; or compile a world (world.src.json and its .map rooms)\n"
              "to Tiled maps and a .world (--tiled).",
    "help": "The reference: all of it, a topic, one command, or the seven worked recipes.",
    "from-png": "Convert PNGs (loose, a pack with a labels CSV, or one sheet sliced by --grid) to .px with\n"
                "exact pixels.",
}
PASTE = {"rotate": ["transpose"]}  # transpose's section ends with the paragraph both share


TOPICS = {"FORMAT": "FORMAT (.px)", "LOOKING": "LOOKING", "CHECKING": "CHECKING", "EDITING": "EDITING (",
          "DRAWING": "DRAWING (", "CONVERTING": "CONVERTING", "HELP": "HELP", "ERRORS": "ERROR CODES"}


def topic(name):
    """A top-level part of the reference (pxart help TOPIC): from its heading to the next one."""
    lines = __doc__.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(TOPICS[name]))
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^[A-Z]", lines[i])), len(lines))
    return "\n".join(lines[start:end]).rstrip()


def commands_by_topic():
    """{topic: its commands, in the reference's order}: each command under the heading its section sits below."""
    lines, heads, out = __doc__.splitlines(), {v: k for k, v in TOPICS.items()}, {}
    starts = {section_start(c): c for c in parser(describe=False)[1].choices if section_start(c) is not None}
    at = None
    for i, l in enumerate(lines):
        if re.match(r"^[A-Z]", l):
            at = next((k for v, k in heads.items() if l.startswith(v)), at)
        elif i in starts:
            out.setdefault(at, []).append(starts[i])
    return out


def overview():
    """pxart -h: what pxart is, the .px format in a few lines, the commands by topic, and where the rest is."""
    lines = __doc__.splitlines()
    fmt = lines.index("FORMAT (.px)")
    sample = lines[fmt + 1:lines.index("", fmt + 7)]  # the palette-and-grid example FORMAT opens with
    rows = [f"  {t:<11} {' '.join(cs)}" for t, cs in commands_by_topic().items()]
    box = lines.index(next(l for l in lines if l.startswith("  | zsh users:"))) - 1  # FORMAT's, as it is there
    zsh = [l[2:] for l in lines[box:box + 4]]
    return "\n".join([lines[0], "", "A sprite is a .px text file: a palette, then a grid of its keys.", *sample, "",
                      "Any command that takes FILE takes FILE:walk/down (a group) or FILE:walk/down/0 (a frame).",
                      *zsh, "",
                      "Commands by topic ('pxart CMD -h' for one, 'pxart help TOPIC' for a topic's reference):",
                      *rows, f"  {'(rename)':<11} {RENAME_HINT}", "",
                      "Topics: FORMAT (the .px format: frames, animation, pivots, variants, selecting frames), "
                      "LOOKING,", "CHECKING, EDITING, DRAWING, CONVERTING, HELP, ERRORS. 'pxart help all' prints the "
                      "whole reference.", "",
                      "Start here: 'pxart help recipes' walks through seven workflows end to end: port a pack and "
                      "prove", "it lossless, merge packs with variants, build a dusk or night, slice a sheet, make a "
                      "scene from a", "map, check an animation's feet, stamp an overlay behind an animation."])


def cmd_help(a):
    """pxart help [all | TOPIC | CMD]."""
    want = a.topic
    if want is None:
        print(parser()[0].format_help().rstrip())
    elif want == "all":
        print(__doc__.rstrip())
    elif want.lower() == "recipes":
        print(RECIPES.rstrip())
    elif want.lower() == "worlds":
        print(WORLDS.rstrip())
    elif want == "rename":
        print(f"rename: {RENAME_HINT}")
    elif want.endswith("-rules") and rules(want[:-len("-rules")]):
        cmd = want[:-len("-rules")]
        print(f"{cmd}: the rules ('pxart {cmd} -h' has the whole section)\n{rules(cmd)}")
    elif want in parser(describe=False)[1].choices:  # a command's name first: 'help help' is help's own -h
        print(parser()[1].choices[want].format_help().rstrip())
    elif want.upper() in TOPICS:
        print(topic(want.upper()))
    else:
        fail("E_BAD_ARG", f"help {want!r}: no such topic or command; topics: all, recipes, {', '.join(TOPICS)}, worlds, "
             f"{', '.join(f'{c}-rules' for c in RULED)}; commands: "
             f"{' '.join(sorted(parser(describe=False)[1].choices))}")


RULED = ("compose", "palette")  # sections that open with a 'Rules' list: 'pxart help compose-rules'


def rules(cmd):
    """The 'Rules' list at the top of CMD's section: its bullets, as the reference has them. None without one."""
    lines = (reference(cmd) or "").splitlines()
    at = next((i for i, l in enumerate(lines) if l.strip().startswith("Rules (")), None)
    if at is None:
        return None
    end = next((i for i in range(at + 1, len(lines)) if not lines[i].startswith("        ")), len(lines))
    return "\n".join(lines[at + 1:end])


def section_start(cmd):
    """The line of the reference where CMD's section starts: its usage line (an indent of 2, then CMD and a usage word,
    not prose), from LOOKING on. None when there is none."""
    lines = __doc__.splitlines()
    usage = re.compile(rf"^  {re.escape(cmd)}( +(?![a-z]+( |$))\S|$)")
    return next((i for i, l in enumerate(lines[lines.index("LOOKING"):], lines.index("LOOKING")) if usage.match(l)),
                None)


def reference(cmd):
    """CMD's section of the reference (pxart help all): its usage line (section_start) and the lines under it, up to
    the next line indented 2 or less that isn't blank. None when the reference has no section for it."""
    lines = __doc__.splitlines()
    usage = re.compile(rf"^  {re.escape(cmd)}( +(?![a-z]+( |$))\S|$)")
    start = section_start(cmd)
    if start is None:
        return None
    # a second usage line of CMD (new OUT --empty) is its section too
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) <= 2 and not usage.match(lines[i])),
               len(lines))
    return "\n".join(lines[start:end]).rstrip()


def note(name):
    """A NOTES slice of pxart -h, or None when its first or last line is gone."""
    lines, (first, after) = __doc__.splitlines(), NOTES[name]
    i = next((i for i, l in enumerate(lines) if l.startswith(first)), None)
    j = next((j for j in range(i + 1, len(lines)) if lines[j].startswith(after)), None) if i is not None else None
    return None if j is None else "\n".join(lines[i:j]).rstrip()


def split_section(cmd):
    """CMD's section of the reference as (its usage lines, the details under them): the usage lines are the leading
    ones that name CMD (indent 2) or carry on its options ('[--fit] ...')."""
    lines = (reference(cmd) or f"  (pxart help all has no section for {cmd})").splitlines()
    n = 1
    while n < len(lines) and (lines[n].lstrip().startswith("[") or lines[n].startswith(f"  {cmd} ")):
        n += 1
    return "\n".join(lines[:n]), "\n".join(lines[n:]).rstrip()


def command_help(cmd):
    """What 'pxart CMD -h' prints around argparse's options, as (above them, below them). Above: CMD's usage lines
    from the reference and its SUMMARY, so the options come early. Below: the rest of its section (the details and
    heuristics, and PASTE's), then one see-also line naming the blocks of pxart help all it relies on, each with what
    it has."""
    usage, details = split_section(cmd)
    summary = "\n".join("      " + l for l in SUMMARY.get(cmd, "").splitlines())
    parts = [details] if details else []
    parts += [f"{ref} (from pxart help all):\n{reference(ref)}" for ref in PASTE.get(cmd, [])]
    refs = SEE.get(cmd, [])
    if refs:
        also = "See also, in pxart help all: " + "; ".join(f"{r} ({GIST[r]})" for r in refs) + "."
        parts.append("\n".join(textwrap.wrap(also, 92, subsequent_indent="  ", break_on_hyphens=False)))
    return (usage + ("\n" + summary if summary else ""),
            "\n\n".join(parts + ["pxart help all has the whole reference, pxart help TOPIC one part of it."]))


class OneLine(argparse.RawDescriptionHelpFormatter):
    """'pxart CMD -h' lists each option on one line: its help beside the flag, never wrapped."""
    def __init__(self, prog):
        super().__init__(prog, max_help_position=38)

    def _split_lines(self, text, width):
        return [" ".join(text.split())]


def said(cmd, issue):
    """An error line as the CLI prints it: 'ellipse: E_BAD_ARG: ...', 'compose: layer 2 (x.px): x.px:4: E_...'. A
    message that starts with the command's own name doesn't say it twice."""
    if not issue.ctx and issue.msg.startswith(f"{cmd}: "):
        issue = Issue(issue.code, issue.msg[len(cmd) + 2:], issue.path, issue.line, issue.frame, issue.row, issue.cols)
    return f"{cmd}: {issue}"


EDIT_DRY = ("set", "fill", "put", "line", "rect", "poly", "ellipse", "arc", "flood", "shade", "outline", "flip", "shift",
            "rotate", "transpose", "mask", "recolor", "crop", "paste", "compose", "dup", "frames", "anim-set", "new",
            "palette")
EDIT_DRY_HELP = "print what the edit says and a diff of the file it would change; write nothing"
DRY_HELP = ("print the readout and each output's size and layout, write nothing ('(dry run; nothing written)'); -o "
            "may be left off")
USED_HELP = "a new OUT gets only the keys the frame uses (default: the sources' whole palettes, for shade ramps)"
TINT_A = "#ff4060a0"  # onion draws A as a silhouette in this translucent red
REKEY_HELP = ("give keys that clash with OUT's colors free keys in OUT only; the source files stay as they are. "
              "KEYS: only these ('o,r'), or KEY=OUTKEY to use OUT's key ('k=j,n=q')")
REPLACE_HELP = "with -o FILE:NEWGROUP: NEWGROUP's frames go first, and the copy takes their place"
VMAP_HELP = "OUT's variant NAME takes each source's first of NAME, V1, V2 (repeatable)"


def parser(describe=True):
    """The command line: (the parser, its subcommands' action). describe: give each subcommand its -h text."""
    ap = argparse.ArgumentParser(prog="pxart", description=overview() if describe else None,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("render"); p.add_argument("files", nargs="+"); p.add_argument("-o", default="preview.png")
    p.add_argument("--png", nargs="?", const="", metavar="DIR",
                   help="also write each single-frame .px as a 1x PNG: FILE.png beside FILE, or DIR/FILE.png")
    p.add_argument("--plain", action="store_true",
                   help="-o is the one frame alone: its exact size at --scale (default 1), no grid, rulers or labels")
    p.add_argument("--scale", type=int, help="default 8 (--plain: 1)")
    p.add_argument("--bg", help="a flat color (default: a grey checkerboard behind each frame; --plain: none, "
                   "transparent stays transparent)")
    p.add_argument("--no-grid", action="store_true")
    p.add_argument("--variant", metavar="V", help="draw every frame in V; each label says so (idle/0%%night)")
    p.add_argument("--dry-run", action="store_true", help=DRY_HELP)
    p = sub.add_parser("sheet"); p.add_argument("files", nargs="+"); p.add_argument("-o")
    p.add_argument("--scale", type=int, default=8); p.add_argument("--cols", type=int, default=8)
    p.add_argument("--bg", help="a flat color behind each frame (default: a grey checkerboard)")
    p.add_argument("--grid", action="store_true")
    p.add_argument("--variant", metavar="V", help="draw every frame in V; each label says so (idle/0%%night), as "
                   "FILE%%V's do, and an argument's own %%VARIANT wins")
    p.add_argument("--fit", action="store_true", help="each cell its own frame's size, each row its tallest frame's")
    p.add_argument("--align", choices=["bottom", "pivot"], default="bottom",
                   help="pivot: line up each animation's frames by pivot, as anim does (default: bottom)")
    p.add_argument("--rows", choices=["cols", "group"], default="cols",
                   help="group: one animation group per row, wrapping within it past --cols (default: --cols a row)")
    p.add_argument("--dry-run", action="store_true", help=DRY_HELP)
    p.add_argument("--exclude", action="append", metavar="GLOB",
                   help="leave out files whose name or path under DIR matches GLOB, or under a matching directory "
                        "(repeatable)")
    p = sub.add_parser("anim"); p.add_argument("files", nargs="+"); p.add_argument("-o", help="GIF; without it, only the numbers. A FILE of several groups: a DIR, "
                                                         "one DIR/GROUP.gif each (DIR/walk/down.gif)")
    p.add_argument("--fps", type=int); p.add_argument("--scale", type=int, default=8); p.add_argument("--variant")
    p.add_argument("--dry-run", action="store_true", help=DRY_HELP)
    p = sub.add_parser("onion"); p.add_argument("a"); p.add_argument("b"); p.add_argument("-o")
    p.add_argument("--scale", type=int, default=8); p.add_argument("--dry-run", action="store_true", help=DRY_HELP)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--rows", help="Y0-Y1: only these canvas rows count for the readout and the best shift")
    g.add_argument("--feet", type=int, metavar="N", help="only the bottom N rows count (--rows for the feet)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--tint-a", nargs="?", const=TINT_A, metavar="COLOR",
                   help=f"draw A as a silhouette in COLOR (the default, in {TINT_A})")
    g.add_argument("--fade-a", action="store_true", help="draw A faded to 35%% instead, as onion once did")
    p.add_argument("--variant", metavar="V", help="draw A and B in V (a halo lit only at night counts); an input's "
                   "own %%V wins")
    p = sub.add_parser("scene"); p.add_argument("specs", nargs="*"); p.add_argument("-o")
    p.add_argument("--dry-run", action="store_true", help=DRY_HELP)
    p.add_argument("--scale", type=int, default=4); p.add_argument("--bg", default="#472d3c")
    p.add_argument("--size", help="WxH; default 96x64, or the map's size with --map")
    p.add_argument("--map", help="tilemap file: legend lines '<char> <FILE[:frame]>' (rest of line = path), blank line, rows")
    p.add_argument("--tile", default="16x16", help="tile size for --map")
    p.add_argument("--variant", help="variant for every map tile and item without its own %%variant")
    p.add_argument("--tint", help="'#rrggbbaa' laid over the finished scene (quote it in scripts)")
    p = sub.add_parser("world"); p.add_argument("world"); p.add_argument("-o")
    p.add_argument("--scale", type=int, default=2); p.add_argument("--dry-run", action="store_true", help=DRY_HELP)
    p = sub.add_parser("tint"); p.add_argument("file"); p.add_argument("color"); p.add_argument("-o")
    p = sub.add_parser("check"); p.add_argument("files", nargs="+"); p.add_argument("--palette")
    p.add_argument("--size"); p.add_argument("--max-colors", type=int); p.add_argument("--strict", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true", help="a line per frame, not per file")
    p.add_argument("--exclude", action="append", metavar="GLOB",
                   help="leave out files whose name or path under DIR matches GLOB, or under a matching directory "
                        "(repeatable)")
    p.add_argument("--tile", default="16x16", help="a world source's tile size: WxH, or N for NxN (default 16x16)")
    p.add_argument("--tileset", action="append", metavar="T.tsj",
                   help="a world source's rooms may draw with this tileset too (repeatable)")
    p = sub.add_parser("stats"); p.add_argument("files", nargs="+")
    p.add_argument("--variant", metavar="V", help="render every frame in V (a FILE's own %%V wins): its bbox and colors")
    p.add_argument("--colors", action="store_true", help="each frame's rendered colors, pixel counts and keys")
    p.add_argument("--at", action="append", metavar="x,y",
                   help="the pixel's key and its color in the base palette and every variant (repeatable)")
    p.add_argument("--exclude", action="append", metavar="GLOB",
                   help="leave out files whose name or path under DIR matches GLOB, or under a matching directory "
                        "(repeatable)")
    p = sub.add_parser("diff"); p.add_argument("a"); p.add_argument("b")
    p.add_argument("--variant", help="render both with this variant (a side's own %%variant wins)")
    p.add_argument("--strict-alpha", action="store_true",
                   help="compare all four channels even where alpha is 0 (by default any two transparent pixels match)")
    p.add_argument("--labels", action="append", metavar="FILE.csv",
                   help="a directory's PNGs go by the names this CSV gives them, as from-png's --labels (repeatable)")
    p.add_argument("--label-col", metavar="COL", help="with --labels: the column of names (default proposed_name)")
    p.add_argument("--file-col", metavar="COL", help="with --labels: the column of PNG file names (default filename)")
    p.add_argument("--exclude", action="append", metavar="GLOB",
                   help="a directory of .px: leave out files whose name or path under it matches GLOB, or under a "
                        "matching directory (repeatable)")
    p.add_argument("-o", metavar="DIFF.png|DIR",
                   help="picture A, B and the differing pixels in magenta; with several pairs, DIR gets one per pair "
                        "that differs")
    p.add_argument("--scale", type=int, metavar="N", help="with -o: default 8, or less to keep the picture within 2048 "
                   "px wide")
    p = sub.add_parser("frames"); p.add_argument("file")
    p.add_argument("--rm", nargs="*", metavar="ID",
                   help="remove these frame ids, or FILE:SEL's frames with none (a group goes in the selector: "
                        "frames FILE:GROUP --rm)")
    p.add_argument("--copy-to", nargs="+", metavar=("DST", "ID"), help="copy frames (FILE:SEL, or these ids) into DST")
    p.add_argument("--move"); p.add_argument("--after"); p.add_argument("--before")
    p.add_argument("--rekey", nargs="?", const="", metavar="KEYS", help=REKEY_HELP)
    p.add_argument("--variant-map", action="append", metavar="NAME=V1,V2", help=VMAP_HELP)
    p.add_argument("--rename", nargs=2, action="append", metavar=("GROUP", "NEWGROUP"),
                   help="GROUP's frames (or the frame GROUP) get NEWGROUP's ids, @anim/@still lines too; with "
                        "--copy-to, only the copies (repeatable)")
    p.add_argument("--prefix", metavar="P", help="with --copy-to: every copy's id gets P in front ('wick/')")
    p = sub.add_parser("flip"); p.add_argument("file")
    p.add_argument("-o", help="OUT, or FILE:NEWGROUP to flip a copy of FILE:GROUP (dup GROUP NEWGROUP, then flip it)")
    p.add_argument("--v", action="store_true"); p.add_argument("--replace", action="store_true", help=REPLACE_HELP)
    p = sub.add_parser("rotate"); p.add_argument("file"); p.add_argument("angle", choices=["90", "180", "270"])
    p.add_argument("-o", help="OUT, or FILE:NEWGROUP to turn a copy of FILE:GROUP")
    p.add_argument("--replace", action="store_true", help=REPLACE_HELP)
    p = sub.add_parser("transpose"); p.add_argument("file")
    p.add_argument("-o", help="OUT, or FILE:NEWGROUP to transpose a copy of FILE:GROUP")
    p.add_argument("--replace", action="store_true", help=REPLACE_HELP)
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
    p.add_argument("--variant", metavar="V", help="c=#hex sets c's color in variant V (it must exist), not the base, and "
                   "'b>t' t=#hex gives the new key t a V color of its own; key moves repaint pixels, the same in "
                   "every variant")
    p = sub.add_parser("set"); p.add_argument("file"); p.add_argument("key", help=KEY_HELP); p.add_argument("points", nargs="+")
    p.add_argument("-o")
    p = sub.add_parser("crop"); p.add_argument("src"); p.add_argument("rect"); p.add_argument("-o", required=True)
    p.add_argument("--rekey", nargs="?", const="", metavar="KEYS", help=REKEY_HELP)
    p.add_argument("--variant-map", action="append", metavar="NAME=V1,V2", help=VMAP_HELP)
    p.add_argument("--used-keys-only", action="store_true", help=USED_HELP)
    p = sub.add_parser("paste"); p.add_argument("src"); p.add_argument("--into", required=True)
    p.add_argument("--at", required=True); p.add_argument("--region"); p.add_argument("-o")
    p.add_argument("--under", action="store_true", help="only onto --into's empty pixels (behind what's there)")
    p.add_argument("--align", choices=["shift", "pivot", "bottom", "bbox"],
                   help="into several frames: --at is for the first, and the paste moves in each other frame as the "
                        "body does: shift, by the best shifts anim prints, added up from the first frame (a glow "
                        "following a bob, wings and all); pivot, as its pivot; bottom, as its drawing's bottom row; "
                        "bbox, as its drawing's top-left (wings or an arm sticking out move it too)")
    p.add_argument("--keys", metavar="K,L", help="--align follows only these keys' pixels (the body, not the wings)")
    p.add_argument("--rekey", nargs="?", const="", metavar="KEYS", help=REKEY_HELP)
    p.add_argument("--variant-map", action="append", metavar="NAME=V1,V2", help=VMAP_HELP)
    p = sub.add_parser("new"); p.add_argument("out"); p.add_argument("--size", help="WxH of the frame")
    p.add_argument("--key", help="fill with this key (default '.')"); p.add_argument("--palette", help="new OUT imports this .px")
    p.add_argument("--still", action="store_true", help="mark the frame's group '@still GROUP'")
    p.add_argument("--empty", action="store_true", help="a new OUT with no frames (with --palette: only its import)")
    p = sub.add_parser("put"); p.add_argument("target"); p.add_argument("-o")
    p = sub.add_parser("fill"); p.add_argument("file"); p.add_argument("key"); p.add_argument("--region")
    p.add_argument("-o")
    coord = re.compile(r"^-\d+(\.\d+)?(,-?\d+(\.\d+)?)*$")  # a negative x,y is an argument, not an option
    ap._negative_number_matcher = coord
    p = sub.add_parser("line"); p.add_argument("file"); p.add_argument("key", help=KEY_HELP); p.add_argument("p0"); p.add_argument("p1")
    p.add_argument("--width", type=int, default=1); p.add_argument("-o")
    p = sub.add_parser("rect"); p.add_argument("file"); p.add_argument("key", help=KEY_HELP); p.add_argument("rect")
    p.add_argument("--fill", action="store_true"); p.add_argument("-o")
    p = sub.add_parser("poly"); p.add_argument("file"); p.add_argument("key", help=KEY_HELP); p.add_argument("points", nargs="+")
    p.add_argument("--fill", action="store_true"); p.add_argument("-o")
    p = sub.add_parser("ellipse"); p.add_argument("file"); p.add_argument("key", help=KEY_HELP); p.add_argument("shape", nargs="?")
    p.add_argument("--box", metavar="x,y,w,h", help="instead of cx,cy,rx,ry: the pixel box it fills, as rect's (no "
                   "half pixels: --box 0,0,8,6 is cx,cy,rx,ry 3.5,2.5,3.5,2.5)")
    p.add_argument("--fill", action="store_true")
    p.add_argument("--ring", type=int, metavar="N", help="an outline N px thick, inside the shape (1: the plain "
                   "outline); not with --fill")
    p.add_argument("-o")
    p = sub.add_parser("arc"); p.add_argument("file"); p.add_argument("key", help=KEY_HELP); p.add_argument("circle")
    p.add_argument("angles"); p.add_argument("--width", type=int, default=1); p.add_argument("-o")
    p = sub.add_parser("flood"); p.add_argument("file"); p.add_argument("key", help=KEY_HELP); p.add_argument("at")
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
    p.add_argument("--replace", action="store_true", help="overwrite an OUT that exists (its frames are lost)")
    p = sub.add_parser("compose"); p.add_argument("layers", nargs="*"); p.add_argument("-o", required=True)
    p.add_argument("--map", help="tilemap file, as scene --map: its cells become the layers (the canvas is its size)")
    p.add_argument("--tile", default="16x16", help="tile size for --map: WxH, or N for NxN (default 16x16)")
    p.add_argument("--size"); p.add_argument("--under", action="store_true", help="draw the layers behind OUT's frame")
    p.add_argument("--rekey", nargs="?", const="", metavar="KEYS", help=REKEY_HELP)
    p.add_argument("--used-keys-only", action="store_true", help=USED_HELP)
    p.add_argument("--variant-map", action="append", metavar="NAME=V1,V2",
                   help="a new OUT's variant NAME takes each layer's first of NAME, V1, V2 (repeatable)")
    p.add_argument("--replace", action="store_true", help="a plain OUT that exists is started fresh, as if new")
    p.add_argument("-v", "--verbose", action="store_true",
                   help=f"every note in full (more than {GROUP_NOTES} of them are otherwise put in short, a line per kind)")
    p = sub.add_parser("dup"); p.add_argument("src"); p.add_argument("new"); p.add_argument("-o")
    p.add_argument("--after")
    p.add_argument("--replace", action="store_true", help="NEWID (or NEWGROUP's frames) exists: the copy replaces it")
    p = sub.add_parser("anim-set"); p.add_argument("target"); p.add_argument("settings", nargs="*"); p.add_argument("-o")
    g = p.add_mutually_exclusive_group(); g.add_argument("--still", action="store_true", help="add '@still GROUP'")
    g.add_argument("--no-still", action="store_true", help="remove '@still GROUP'")
    p = sub.add_parser("palette", usage="pxart palette FILE [OPTIONS of one mode; the modes are below]")
    p.add_argument("file")
    g = p.add_argument_group("list (no edit options)", "Print the palette, where each key comes from and how "
                             "often it's drawn, and what each variant recolors.")
    g.add_argument("--in", dest="within", metavar="DIR",
                   help="for a palette file: how many .px files under DIR import it, and draw with each key")
    g = p.add_argument_group("add / remove / order base keys", "Edit FILE's own palette lines.")
    g.add_argument("--add", nargs="+", metavar="k=#rrggbb", help="add keys (with --variant: set them in that variant)")
    g.add_argument("--remove", metavar="KEYS", help="take these keys out of FILE (with their variant lines)")
    g.add_argument("--to", metavar="KEY", help="with --remove: repaint the removed keys' pixels as KEY first")
    g.add_argument("--order", metavar="KEYS", help="put these keys first in FILE's palette, in this order")
    g = p.add_argument_group("variants", "Set or inherit keys in one variant, by hand: --variant NAME --add k=#hex.")
    g.add_argument("--variant", metavar="NAME", help="--add, --keep and --derive-from edit this variant (made if FILE "
                   "has none)")
    g.add_argument("--keep", metavar="KEYS", help="with --variant: these keys inherit the base colors in it")
    g = p.add_argument_group("derive", "Build a whole variant from the base or another variant: --variant NAME "
                             "--derive-from base.")
    g.add_argument("--derive-from", metavar="base|VARIANT",
                   help="with --variant NAME: set every key in NAME from its color here, --darken'ed and --tint'ed")
    g.add_argument("--match", metavar="FILE[%VARIANT]",
                   help="with --derive-from: first map each channel as FILE's base->VARIANT does (a fitted "
                        "gain and offset)")
    g.add_argument("--darken", type=float, metavar="F", help="with --derive-from: each channel times 1 - F (0..1)")
    g.add_argument("--tint", metavar="COLOR", help="with --derive-from: '#rrggbbaa' laid over each color, as scene's")
    g.add_argument("--keep-lit", metavar="KEYS", help="with --derive-from: these keys keep their color (lamps)")
    g.add_argument("--lift-darks", action="store_true",
                   help="with --derive-from: let the derive brighten keys darker than a quarter (else never)")
    g = p.add_argument_group("import / hoist", "Share one palette file between sprites.")
    g.add_argument("--import", dest="import_", metavar="P.px",
                   help="add '@palette P.px' to FILE, dropping FILE's key lines P has in the same colors")
    g.add_argument("--hoist", metavar="KEYS", help="move these keys into the palette file FILE imports")
    g.add_argument("--extract-to", metavar="P.px", help="write FILE's palette and variants as a palette file")
    g.add_argument("--repoint", action="store_true", help="with --extract-to: FILE then imports it")
    g = p.add_argument_group("comments", "The comment lines above key and @variant lines, and FILE's header.")
    g.add_argument("--comment", nargs="+", action="append", metavar="KEY TEXT",
                   help="KEY 'text' or @variant NAME 'text', one or more in turn (--comment y 'lamp' E 'flame'): the "
                        "comment line above that line ('' removes it)")
    g.add_argument("--comment-header", metavar="TEXT", help="the comment at the top of FILE ('' removes it)")
    g = p.add_argument_group("export", "Write the palette for another tool.")
    g.add_argument("--export", metavar="OUT.gpl|OUT.hex", help="write the base palette as a GIMP .gpl or a .hex list")
    g.add_argument("--used", action="store_true", help="with --export: only the keys FILE's frames draw with")
    g = p.add_argument_group("where an edit goes", "With any edit above (not the listing or --export).")
    g.add_argument("-o", metavar="OUT", help="write the edited FILE to OUT (its @palette lines re-pointed from there); "
                   "FILE stays as it is")
    g.add_argument("--dry-run", action="store_true", help="print what the edit says and a diff of each file it would "
                   "change; write nothing")
    p = sub.add_parser("export"); p.add_argument("files", nargs="*"); p.add_argument("--frames"); p.add_argument("--aseprite")
    p.add_argument("--tile", default="16x16", help="sources: the rooms' tile size, WxH or N for NxN (default 16x16)")
    p.add_argument("--tiled", nargs="?", const=True, metavar="X.tsj",
                   help="frames: a Tiled tileset X.tsj; world.src.json or .map sources: their .tmj/.world beside them")
    p.add_argument("--variant")
    p.add_argument("--tileset", action="append", metavar="T.tsj",
                   help="sources: rooms may draw with this tileset too, beside their packs' tiled/*.tsj (repeatable)")
    p.add_argument("--prefix-file", action="store_true",
                   help="id each file's frames FILE/ID (FILE: its path under DIR, or its stem), so ids can't collide")
    p.add_argument("--exclude", action="append", metavar="GLOB",
                   help="leave out files whose name or path under DIR matches GLOB, or under a matching directory "
                        "(repeatable)")
    p = sub.add_parser("help")
    p.add_argument("topic", nargs="?", help="all, a TOPIC (FORMAT, EDITING, ...) or a command")
    p = sub.add_parser("from-png"); p.add_argument("pngs", nargs="+"); p.add_argument("-o"); p.add_argument("--id")
    p.add_argument("--palette", help="new OUT imports this palette file and reuses its keys")
    p.add_argument("--colors", type=int, metavar="N",
                   help="reduce the PNGs (all together) to at most N colors first, for a photo or painting with "
                        "more colors than palette keys; says how far that moved them")
    p.add_argument("--grid", metavar="WxH", help="slice one sheet into WxH cells, one frame each (empty ones skipped)")
    p.add_argument("--names", metavar="A,B,...",
                   help="one frame id per PNG, in order; with --grid: each row's (--by cols: column's) group name")
    p.add_argument("--labels", action="append", metavar="FILE.csv",
                   help="name each PNG from a CSV beside it: its --file-col row's --label-col (repeatable)")
    p.add_argument("--label-col", metavar="COL", help="with --labels: the column of names (default proposed_name)")
    p.add_argument("--file-col", metavar="COL", help="with --labels: the column of PNG file names (default filename)")
    p.add_argument("--by", metavar="rows|cols", help="with --grid: a group per row (the default) or per column")
    p.add_argument("--prefix-dir", action="store_true",
                   help="id each PNG FOLDER/STEM, FOLDER its directory's name (dungeon/tile_0002)")
    for name in EDIT_DRY[:-1]:  # palette has its own, in its 'where an edit goes' group
        sub.choices[name].add_argument("--dry-run", action="store_true", help=EDIT_DRY_HELP)
    for name, p in sub.choices.items() if describe else ():  # 'pxart CMD -h': usage, summary, options, details
        (p.description, p.epilog), p.formatter_class = command_help(name), OneLine
    return ap, sub


SPRITE_ARG_RE = re.compile(r"\.(px|png)([:%+].*)?$")  # 'hero.px', 'hero.px:walk/0', 'x.png': a file, not a DIR


def rekey_args(args):
    """A bare --rekey followed by an argument that isn't a key list (a layer, crop's x,y,w,h) is written --rekey= for
    argparse, which would otherwise take that argument as --rekey's KEYS; so is a bare --png followed by a file
    (render --png hero.px), which would be taken as its DIR."""
    out = list(args)
    for i, x in enumerate(out):
        nxt = out[i + 1] if i + 1 < len(out) else None
        if x == "--rekey" and (nxt is None or not REKEY_RE.match(nxt) or RECT_ARG_RE.match(nxt)):
            out[i] = "--rekey="
        if x == "--png" and nxt is not None and SPRITE_ARG_RE.search(nxt):  # render --png hero.px: a file, not DIR
            out[i] = "--png="
    return out


RENAME_HINT = "no command of its own: frames FILE --rename GROUP NEWGROUP renames frames; recolor FILE 'a>b' a key"


def main(argv=None):
    args = rekey_args(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["rename"]:
        sys.exit(f"rename: E_BAD_ARG: {RENAME_HINT}")
    ap, sub = parser(describe="-h" in args or "--help" in args)
    a, extra = ap.parse_known_args(args)
    a.argv = list(sys.argv[1:] if argv is None else argv)  # as typed: compose's '# composed by:' header
    if extra and a.cmd == "anim-set" and not any(x.startswith("-") for x in extra):
        a.settings += extra  # 'anim-set F:G --still ms=50': argparse spends a '*' positional before the option
    elif extra:  # argparse's own error, with the command's usage (the top level's names no option of it)
        sub.choices[a.cmd].error(f"unrecognized arguments: {' '.join(extra)}")
    WARNED.clear()
    CREATED.clear()
    DRY["run"] = bool(getattr(a, "dry_run", False))
    told = io.StringIO()  # what the command prints, held until it is done: see unsaid()
    try:
        with contextlib.redirect_stdout(told):
            globals()["cmd_" + a.cmd.replace("-", "_")](a)
    except PxError as e:  # every error line starts with the command, then the input: 'compose: layer 2 (x.px): ...'
        said_first(unsaid(told.getvalue()))
        sys.exit("\n".join(said(a.cmd, i) for i in e.issues))
    except OSError as e:
        said_first(unsaid(told.getvalue()))
        sys.exit(file_error(a.cmd, e))
    except BaseException:
        said_first(told.getvalue())
        raise
    if DRY["run"] and a.cmd in EDIT_DRY and "(dry run; nothing written)" not in told.getvalue():
        print("(dry run; nothing written)", file=told)
    said_first(told.getvalue())


def said_first(text):
    """Write what the command printed (held until it was done) and flush it, before anything goes to stderr (the error
    line sys.exit prints, a traceback): in one stream (2>&1, a pipe) the lines come out in the order they were said."""
    sys.stdout.write(text)
    sys.stdout.flush()


def unsaid(text):
    """A command that fails prints none of its notes and WARNINGs: they describe the write it was about to make (a grid
    renamed, keys rekeyed, colors left out), and that write didn't happen. Its other lines (a 'wrote' for a file an
    earlier step did write) stay."""
    return "".join(l for l in text.splitlines(True) if not l.startswith(("note:", "WARNING:")))


if __name__ == "__main__":
    main()
