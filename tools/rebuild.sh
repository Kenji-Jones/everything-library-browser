#!/bin/bash
# Re-export every category from itchSourceFiles into EverythingLibraryBrowser and rebuild the catalog.
# Usage: tools/rebuild.sh            (takes about 2 minutes)
set -e
LIB="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$LIB/EverythingLibraryBrowser"
SRC="$LIB/itchSourceFiles"
B="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
LOGS="$(mktemp -d)"

rm -rf "$OUT/models" "$OUT/thumbs" "$OUT/data/parts"
run() { "$B" -b "$1" --python "$LIB/tools/export_library.py" -- "$OUT" "${@:2}" > "$LOGS/$2.log" 2>&1 || { echo "$2 failed, see $LOGS/$2.log"; exit 1; }; }
run "$SRC/EverythingLibrary_Animals_002/EverythingLibrary_Animals_002.blend" Animals &
run "$SRC/EverythingLibrary_Buildings_001/EverythingLibrary_Buildings_001.blend" Buildings &
run "$SRC/EverythingLibrary_Consumables/EverythingLibrary_Consumables_002.blend" Consumables 0.01 &
run "$SRC/EverythingLibrary_Furnishings_001/EverythingLibrary_Furnishings_001.blend" Furnishings &
run "$SRC/EverythingLibrary_Geology/EverythingLibrary_Geology_001.blend" Geology &
for c in Human Microscopic Plants Space Trees Underwater Vehicles Zeometry; do
  [ -d "$LIB/canvasSourceFiles/$c" ] || continue
  CANVAS_DIR="$LIB/canvasSourceFiles/$c" "$B" -b --factory-startup --python "$LIB/tools/export_library.py" -- "$OUT" "$c" > "$LOGS/$c.log" 2>&1 &
done
wait
"$B" -b --factory-startup --python "$LIB/tools/finalize_blends.py" -- "$OUT" > "$LOGS/finalize.log" 2>&1
python3 "$LIB/tools/build_catalog.py" "$OUT"
echo "Done. Logs in $LOGS"
