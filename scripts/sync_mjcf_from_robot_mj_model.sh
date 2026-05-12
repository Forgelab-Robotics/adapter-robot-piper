#!/usr/bin/env bash
# 将 robot-mj-model 中 PIPER MJCF 同步到本仓 assets/mjcf/piper_mujoco/
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_SRC="$(cd "$ROOT/../.." && pwd)/robot-mj-model/models/PIPER"
SRC="${PIPER_MJCF_SRC:-$DEFAULT_SRC}"
DST="$ROOT/assets/mjcf/piper_mujoco"

if [[ ! -d "$SRC" ]]; then
  echo "Source not found: $SRC" >&2
  echo "Set PIPER_MJCF_SRC to your robot-mj-model/models/PIPER path." >&2
  exit 1
fi

mkdir -p "$DST"
# 不把 *.glb 同步进 mjcf/：GLB 由本仓 assets/glb/piper_upstream/ 维护（见 assets/glb/README.md）
rsync -a --delete --exclude='*.glb' "$SRC/" "$DST/"
echo "Synced MJCF assets:"
echo "  from: $SRC"
echo "  to:   $DST"
echo "  (excluded *.glb; copy GLB from upstream manually to assets/glb/piper_upstream/ if updated)"
