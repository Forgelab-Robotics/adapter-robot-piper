#!/usr/bin/env bash
# 从 robot-mj-model/models/PIPER 仅同步 *.glb 到 assets/glb/piper_upstream/（保持相对路径）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_SRC="$(cd "$ROOT/../.." && pwd)/robot-mj-model/models/PIPER"
SRC="${PIPER_MJCF_SRC:-$DEFAULT_SRC}"
DST="$ROOT/assets/glb/piper_upstream"

if [[ ! -d "$SRC" ]]; then
  echo "Source not found: $SRC" >&2
  echo "Set PIPER_MJCF_SRC to your robot-mj-model/models/PIPER path." >&2
  exit 1
fi

mkdir -p "$DST"
n=0
while IFS= read -r -d '' f; do
  rel="${f#"$SRC"/}"
  out="$DST/$rel"
  mkdir -p "$(dirname "$out")"
  cp -v "$f" "$out"
  n=$((n + 1))
done < <(find "$SRC" -type f -name '*.glb' -print0)

if [[ "$n" -eq 0 ]]; then
  echo "No .glb files under: $SRC" >&2
  exit 1
fi
echo "Copied $n GLB file(s) to: $DST"
