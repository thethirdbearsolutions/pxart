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
# 01-format: one sprite with its own keys, one drawn by hand, one that imports a shared
# palette file; the hand-drawn one then imports it too, and both go dusk together.
# The README walks these in order, one image per step.
stage 01-format barrel.px gem.px lamp.px palette.px
pxart render barrel.px -o barrel.preview.png --png
pxart render gem.px --scale 16 -o gem.preview.png
pxart render lamp.px -o lamp.preview.png --png
txt import.txt palette gem.px --import palette.px -o gem-shared.px
pxart render lamp.px gem-shared.px --variant dusk -o dusk.preview.png
pxart scene --size 96x40 --bg '#dfe8e6' -o shelf.x4.png \
  barrel.px@4,20 lamp.px@24,4 gem-shared.px@42,28 lamp.px%dusk@62,4 gem-shared.px%dusk@80,28

# ---------------------------------------------------------------------------------------
# 02-animation: @anim / @frame timing and pivots; anim's GIF, strip and readout; onion.
# The README walks these in order.
stage 02-animation hero.px hero-palette.px
pxart sheet hero.px --fit --rows group --align pivot --scale 4 -o sheet.png
txt anim-walk.txt anim hero.px:walk/down -o walk.gif --scale 6
txt anim-idle.txt anim hero.px:idle/right -o idle.gif --scale 4
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
mkdir -p derived
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
# 04-drawing: run draw.sh a line at a time, keeping a copy of chest.px after each step and
# a picture of it (the README shows one per step), then all the steps on one sheet.
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
  step=steps/$(printf %02d $n)-${args[0]}
  pxart render chest.px --scale 10 -o "$step.png" > /dev/null
  # the copy imports the same palette.px, from one directory down
  sed 's|^@palette palette.px$|@palette ../palette.px|' chest.px > "$step.px"
done < draw.sh
if grep -q '^(exit' draw.txt; then cat draw.txt >&2; exit 1; fi
pxart sheet steps/ --cols 6 --scale 4 -o steps.png
pxart render chest.px --scale 10 -o chest.preview.png --png
rm chest.px   # so Step 1's 'pxart new chest.px' works in a copy of the folder (steps/ has it)

# ---------------------------------------------------------------------------------------
# 05-compose: three packs, three palettes, three night-ish variants, one dusk dock.
# The README walks these in order: the conflict, --rekey alone (a dusk that misses two
# layers), then --variant-map; each scene is 4x (scene's default).
stage 05-compose harbor-market/harbor.px harbor-market/palette.px \
  lighthouse-keeper/keeper.px lighthouse-keeper/palette.px wick/player.px wick/pal.px
pxart sheet harbor-market/harbor.px lighthouse-keeper/keeper.px wick/player.px --fit --scale 4 -o packs.png
H=harbor-market/harbor.px
layers=(
  ${H}:water/0@0,0 ${H}:water/0@16,0 ${H}:water/0@32,0 ${H}:water/0@48,0 ${H}:water/0@64,0
  ${H}:cobble/a@0,16 ${H}:cobble/b@16,16 ${H}:cobble/c@32,16 ${H}:cobble/a@48,16 ${H}:cobble/b@64,16
  ${H}:cobble/c@0,32 ${H}:cobble/a@16,32 ${H}:cobble/b@32,32 ${H}:cobble/c@48,32 ${H}:cobble/a@64,32
  ${H}:stall@2,6 ${H}:lamp@36,8
  lighthouse-keeper/keeper.px:idle/down/0@42,14 wick/player.px:idle/0@62,28
)
txt conflict.txt compose -o dock.px --size 80x48 "${layers[@]}" --replace
txt rekey.txt compose -o dock.px --size 80x48 --rekey "${layers[@]}" --replace
pxart scene --size 80x48 -o dock-halfdusk.x4.png dock.px%dusk@0,0
txt compose.txt compose -o dock.px --size 80x48 --rekey --variant-map dusk=night,dark "${layers[@]}" --replace
pxart scene --size 80x48 -o dock-dusk.x4.png dock.px%dusk@0,0
pxart scene --size 80x48 -o dock.x4.png dock.px@0,0
pxart scene --size 656x192 --scale 1 -o panels.x4.png dock.x4.png@0,0 dock-dusk.x4.png@336,0

# ---------------------------------------------------------------------------------------
# 06-scene: a four-layer .map (sky, tree line, field tiles, trees) with the hero on it.
# The README walks these in order; each render is 2x.
stage 06-scene rooms/glade.map pal/far.px pal/mid.px pal/field.px pal/hero.px \
  layers/far.px layers/mid.px tiles/field.px tiles/tree.px sprites/hero.px
txt check.txt check rooms/glade.map
# the README's layers picture: the map's first 1, 2, 3 and 4 layers, 1x, in a 2x2 grid
for n in 1 2 3 4; do
  awk -v n=$n '/^---$/ { k++ } k < n' rooms/glade.map > rooms/_first$n.map
  pxart scene --map rooms/_first$n.map --size 256x224 --scale 1 -o _layers$n.png > /dev/null 2>&1
done
pxart scene --size 528x464 --scale 1 -o layers.png \
  _layers1.png@0,0 _layers2.png@272,0 _layers3.png@0,240 _layers4.png@272,240
rm rooms/_first?.map _layers?.png
txt scene.txt scene --map rooms/glade.map --scale 2 -o glade.x2.png \
  tiles/field.px:shadow_s@150,154 sprites/hero.px:walk/left/0@147,127
txt scene-dusk.txt scene --map rooms/glade.map --scale 2 --variant dusk -o glade-dusk.x2.png \
  tiles/field.px:shadow_s@150,154 sprites/hero.px:walk/left/0@147,127
txt compose.txt compose --map rooms/glade.map -o glade.px --rekey \
  tiles/field.px:shadow_s@150,154 sprites/hero.px:walk/left/0@147,127 --replace
txt check-glade.txt check glade.px
pxart scene --size 1040x448 --scale 1 -o panels.x2.png glade.x2.png@0,0 glade-dusk.x2.png@528,0

# ---------------------------------------------------------------------------------------
# 07-import: lay the beetle's frames out as a PNG sheet, slice it back with from-png --grid,
# and prove with diff that every frame came back pixel for pixel. The README walks these
# in order; the sheet and its 8x view are its "Where the sheet comes from" section.
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
txt diff.txt diff beetle.px imported.px
txt diff-mismatch.txt diff beetle.px:walk/right/0 imported.px:walk_cave/right/0 -o diff.png

# ---------------------------------------------------------------------------------------
# 08-export: an Aseprite sheet + JSON, a Tiled tileset, and one PNG per frame; then the
# README's pictures of them (its "The pictures" section).
stage 08-export alchemist.px hero_pal.px harbor.px harbor-palette.px
txt export-aseprite.txt export alchemist.px --aseprite alchemist.json
txt export-tiled.txt export harbor.px --tiled harbor.tsj
txt export-frames.txt export alchemist.px --frames frames
pxart scene --size 96x96 --scale 4 -o alchemist.x4.png alchemist.png@0,0
pxart scene --size 48x32 --scale 8 -o harbor.x8.png harbor.png@0,0
pxart sheet harbor.px --cols 6 --scale 6 -o harbor-tiles.png
pxart scene --size 56x32 -o frames.x4.png frames/walk/right/0.png@0,0 frames/attack/right/3.png@32,0

# ---------------------------------------------------------------------------------------
# 09-check: check on a file with three mistakes. The README fixes them one at a time in a
# text editor and checks after each; here the same edits go to a copy in fixing/, which
# is removed after. Then stats and a sheet of the fixed file.
stage 09-check broken.px fixed.px
txt check-broken.txt check broken.px
mkdir fixing
cp broken.px fixing/
(
  cd fixing
  fix() { sed "$1" broken.px > broken.tmp && mv broken.tmp broken.px; }
  fix '41s/$/./'           # the short row gets its missing '.'
  txt ../check-fix1.txt check broken.px
  fix '63s/W/w/'           # a 'W' that isn't in the palette, meant as 'w'
  txt ../check-fix2.txt check broken.px
  fix '85s/с/c/'           # that first letter is a Cyrillic 'с', typed for the key 'c'
  txt ../check-fix3.txt check broken.px
)
rm -r fixing
txt stats-colors.txt stats fixed.px:idle/0 --colors
pxart sheet fixed.px --scale 6 -o fixed.png

# ---------------------------------------------------------------------------------------
mkdir -p "$DEST"
cp -R "$WORK"/. "$DEST"/
echo "built examples into $DEST"
