#!/bin/bash
# Render the editor icons (white SVG strokes) to 64 px PNGs: a power-of-two size, so they get mipmaps.
# Usage: render_icons.sh <output folder>. Widgets tint the icons; build_gf.py and the native tests import them.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
out=$1
rm -rf "$out" && mkdir -p "$out"
for svg in "$repo"/unreal/icons/*.svg; do
    magick -background none -density 512 "$svg" -resize 64x64 "PNG32:$out/$(basename "${svg%.svg}").png"
done
