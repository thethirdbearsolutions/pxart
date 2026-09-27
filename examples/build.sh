#!/usr/bin/env bash
# Regenerate every output under examples/ from the .px sources, with pxart commands.
#
#   examples/build.sh           rebuild in place
#   examples/build.sh DEST      write every example's sources and outputs to DEST instead
#                               (not the READMEs or this script)
#
# Each example copies only its sources into a scratch directory and runs there, so an
# output left over from an earlier build never feeds a later command.
# tests/test_examples.py builds into a temp dir and checks every committed file is
# byte-identical, so a pxart change that alters an example fails the tests.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
DEST=${1:-$HERE}
PYTHON=${PYTHON:-python3}   # the pxart.py beside examples/ runs under this
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

pxart() { "$PYTHON" "$HERE/../pxart.py" "$@"; }

# stage DIR FILE...: copy an example's sources into the scratch dir and cd there.
stage() {
  local dir=$1; shift
  mkdir -p "$WORK/$dir"
  (cd "$HERE/$dir" && for f in "$@"; do mkdir -p "$WORK/$dir/$(dirname "$f")"; cp "$f" "$WORK/$dir/$f"; done)
  cd "$WORK/$dir"
}

# shq ARGS...: the args as you'd type them, single-quoting any a shell would mangle.
shq() {
  local a out=()
  for a in "$@"; do
    if [[ $a =~ ^[A-Za-z0-9_./:,%@=+-]+$ ]]; then out+=("$a"); else out+=("'$a'"); fi
  done
  echo "${out[*]}"
}

# txt OUT.txt ARGS...: run 'pxart ARGS', saving the command line and everything it printed
# (a failing command too: its exit code goes in the file, and the build goes on).
txt() {
  local out=$1; shift
  local code=0
  { echo "\$ pxart $(shq "$@")"; pxart "$@" 2>&1 || code=$?; [ $code -eq 0 ] || echo "(exit $code)"; } > "$out.tmp"
  mv "$out.tmp" "$out"
}

# ---------------------------------------------------------------------------------------
# 01-format: one sprite with its own keys, one that imports a shared palette file.
stage 01-format barrel.px lamp.px palette.px
pxart render barrel.px -o barrel.preview.png --png
pxart render lamp.px -o lamp.preview.png --png

# ---------------------------------------------------------------------------------------
# 02-animation: @anim / @frame timing and pivots; anim's GIF, strip and readout; onion.
stage 02-animation hero.px hero-palette.px
pxart sheet hero.px --fit --rows group --align pivot --scale 4 -o sheet.png
pxart anim hero.px:walk/down -o walk.gif --scale 6 > /dev/null
pxart anim hero.px:idle/right -o idle.gif --scale 4 > /dev/null
txt anim-walk.txt anim hero.px:walk/down
txt anim-idle.txt anim hero.px:idle/right
txt onion.txt onion hero.px:walk/down/0 hero.px:walk/down/1 -o onion.png
txt onion-feet.txt onion hero.px:walk/down/0 hero.px:walk/down/3 --feet 6 -o onion-feet.png

# ---------------------------------------------------------------------------------------
# 03-variants: a @variant in a shared palette file, a derived one, and %VARIANT renders.
# The README walks these in order, one image per step; each scene is 4x (scene's default).
stage 03-variants coast.px palette.px
pxart scene --size 48x64 --bg '#8ccfd6' -o base.x4.png \
  coast.px:sand@0,48 coast.px:sand@16,48 coast.px:sand@32,48 \
  coast.px:lighthouse@2,6 coast.px:keeper@16,26
pxart scene --size 48x64 --bg '#5a86b0' -o night.x4.png \
  coast.px:sand%night@0,48 coast.px:sand%night@16,48 coast.px:sand%night@32,48 \
  coast.px:lighthouse%night@2,6 coast.px:keeper%night@16,26
mkdir derived
cp palette.px coast.px derived/
txt derive.txt palette derived/palette.px --variant dusk --derive-from base \
  --darken 0.2 --tint '#ff6a3a38' --keep-lit l,g
pxart scene --size 48x64 --bg '#e0936a' -o dusk-derived.x4.png \
  derived/coast.px:sand%dusk@0,48 derived/coast.px:sand%dusk@16,48 derived/coast.px:sand%dusk@32,48 \
  derived/coast.px:lighthouse%dusk@2,6 derived/coast.px:keeper%dusk@16,26
txt add.txt palette derived/palette.px --variant dusk --add 'w=#f2c6a8'
pxart scene --size 48x64 --bg '#e0936a' -o dusk.x4.png \
  derived/coast.px:sand%dusk@0,48 derived/coast.px:sand%dusk@16,48 derived/coast.px:sand%dusk@32,48 \
  derived/coast.px:lighthouse%dusk@2,6 derived/coast.px:keeper%dusk@16,26
txt palette.txt palette derived/palette.px
pxart scene --size 608x256 --scale 1 -o panels.x4.png \
  base.x4.png@0,0 dusk.x4.png@208,0 night.x4.png@416,0

# ---------------------------------------------------------------------------------------
# 04-drawing: run draw.sh a line at a time, keeping a copy of chest.px after each step.
stage 04-drawing draw.sh palette.px
mkdir steps
n=0
: > draw.txt
while IFS= read -r line; do
  [[ -z $line || $line == \#* ]] && continue
  n=$((n + 1))
  read -r -a args <<< "${line#pxart }"
  txt step.txt "${args[@]}"
  cat step.txt >> draw.txt && rm step.txt
  # the copy imports the same palette.px, from one directory down
  sed 's|^@palette palette.px$|@palette ../palette.px|' chest.px > "steps/$(printf %02d $n)-${args[0]}.px"
done < draw.sh
if grep -q '^(exit' draw.txt; then cat draw.txt >&2; exit 1; fi
pxart sheet steps/ --cols 6 --scale 4 -o steps.png
pxart render chest.px -o chest.preview.png --png

# ---------------------------------------------------------------------------------------
# 05-compose: three packs, three palettes, three night-ish variants, one dusk dock.
stage 05-compose harbor-market/harbor.px harbor-market/palette.px \
  lighthouse-keeper/keeper.px lighthouse-keeper/palette.px wick/player.px wick/pal.px
H=harbor-market/harbor.px
layers=(
  ${H}:water/0@0,0 ${H}:water/0@16,0 ${H}:water/0@32,0 ${H}:water/0@48,0 ${H}:water/0@64,0
  ${H}:cobble/a@0,16 ${H}:cobble/b@16,16 ${H}:cobble/c@32,16 ${H}:cobble/a@48,16 ${H}:cobble/b@64,16
  ${H}:cobble/c@0,32 ${H}:cobble/a@16,32 ${H}:cobble/b@32,32 ${H}:cobble/c@48,32 ${H}:cobble/a@64,32
  ${H}:stall@2,6 ${H}:lamp@36,8
  lighthouse-keeper/keeper.px:idle/down/0@42,14 wick/player.px:idle/0@62,28
)
txt conflict.txt compose -o dock.px --size 80x48 "${layers[@]}"
txt compose.txt compose -o dock.px --size 80x48 --rekey --variant-map dusk=night,dark "${layers[@]}"
pxart scene --size 80x48 --scale 1 -o dock.png dock.px@0,0
pxart scene --size 80x48 --scale 4 -o dock.x4.png dock.px@0,0
pxart scene --size 80x48 --scale 1 -o dock-dusk.png dock.px%dusk@0,0
pxart scene --size 80x48 --scale 4 -o dock-dusk.x4.png dock.px%dusk@0,0

# ---------------------------------------------------------------------------------------
# 06-scene: a four-layer .map (sky, tree line, field tiles, trees) with the hero on it.
stage 06-scene rooms/glade.map pal/far.px pal/mid.px pal/field.px pal/hero.px \
  layers/far.px layers/mid.px tiles/field.px tiles/tree.px sprites/hero.px
txt check.txt check rooms/glade.map
hero=(tiles/field.px:shadow_s@150,154 sprites/hero.px:walk/left/0@147,127)
txt scene.txt scene --map rooms/glade.map --scale 1 -o glade.png "${hero[@]}"
pxart scene --map rooms/glade.map --scale 2 -o glade.x2.png "${hero[@]}" 2> /dev/null
pxart scene --map rooms/glade.map --scale 1 --variant dusk -o glade-dusk.png "${hero[@]}" 2> /dev/null
pxart scene --map rooms/glade.map --scale 2 --variant dusk -o glade-dusk.x2.png "${hero[@]}" 2> /dev/null

# ---------------------------------------------------------------------------------------
# 07-import: lay the beetle's frames out as a PNG sheet, slice it back with from-png --grid,
# and prove with diff that every frame came back pixel for pixel.
stage 07-import beetle.px beetle_pal.px
items=()
for i in 0 1 2 3; do
  items+=(beetle.px:walk/right/${i}@$((16 * i)),0 beetle.px:walk_cave/right/${i}@$((16 * i)),16)
done
pxart scene --size 64x32 --scale 1 --bg transparent -o sheet.png "${items[@]}"
pxart scene --size 64x32 --scale 8 -o sheet.x8.png sheet.png@0,0
txt from-png.txt from-png sheet.png --grid 16x16 --names walk/right,walk_cave/right \
  --palette beetle_pal.px -o imported.px
pxart sheet imported.px --rows group --scale 4 -o imported.png
txt diff.txt diff beetle.px:walk/right imported.px:walk/right
txt diff-cave.txt diff beetle.px:walk_cave/right imported.px:walk_cave/right
txt diff-mismatch.txt diff beetle.px:walk/right imported.px:walk_cave/right

# ---------------------------------------------------------------------------------------
# 08-export: an Aseprite sheet + JSON, a Tiled tileset, and one PNG per frame.
stage 08-export alchemist.px hero_pal.px harbor.px harbor-palette.px
txt export-aseprite.txt export alchemist.px --aseprite alchemist.json
txt export-tiled.txt export harbor.px --tiled harbor.tsj
txt export-frames.txt export alchemist.px --frames frames
pxart scene --size 96x96 --scale 4 -o alchemist.x4.png alchemist.png@0,0
pxart scene --size 48x32 --scale 8 -o harbor.x8.png harbor.png@0,0
pxart sheet harbor.px --cols 6 --scale 6 -o harbor-tiles.png

# ---------------------------------------------------------------------------------------
# 09-check: check on a file with three mistakes and on its fixed version; stats.
stage 09-check broken.px fixed.px
txt check-broken.txt check broken.px
txt check-fixed.txt check fixed.px -v
txt stats.txt stats fixed.px
txt stats-colors.txt stats fixed.px:idle/0 --colors
txt stats-dark.txt stats fixed.px:idle/0%dark --colors --at 7,3
pxart sheet fixed.px --scale 6 -o fixed.png
pxart sheet fixed.px --scale 6 --variant dark -o fixed-dark.png

# ---------------------------------------------------------------------------------------
mkdir -p "$DEST"
cp -R "$WORK"/. "$DEST"/
echo "built examples into $DEST"
