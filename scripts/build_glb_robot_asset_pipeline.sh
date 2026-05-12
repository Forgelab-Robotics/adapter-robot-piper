#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$(cd "$ROOT/../.." && pwd)"
PIPE="$WORKSPACE/robot_asset_pipeline"
PYTHON_BIN="${PIPER_PIPELINE_PYTHON:-/home/donglinghan/miniforge3/bin/python}"
IN_XML="$ROOT/assets/mjcf/piper_mujoco/PIPER.xml"
OUT_DIR="${PIPER_GLB_OUT:-$ROOT/assets/glb}"
NAME="${PIPER_GLB_NAME:-piper}"
SKIP_PREVIEW="${PIPER_SKIP_PREVIEW:-1}"
if [[ ! -f "$IN_XML" ]]; then echo "Missing input: $IN_XML" >&2; exit 1; fi
if [[ ! -f "$PIPE/main.py" ]]; then echo "robot_asset_pipeline not found at: $PIPE" >&2; exit 1; fi
if [[ ! -x "$PYTHON_BIN" ]]; then echo "Python not found or not executable: $PYTHON_BIN" >&2; exit 1; fi
extra=()
if [[ "$SKIP_PREVIEW" == "1" ]]; then extra+=(--skip-preview); fi
mkdir -p "$OUT_DIR"
cd "$PIPE"
"$PYTHON_BIN" main.py "$IN_XML" -o "$OUT_DIR" -n "$NAME" "${extra[@]}"
