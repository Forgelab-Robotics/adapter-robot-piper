#!/usr/bin/env bash

set -euo pipefail

# 打包 piper 节点为单文件可执行程序。
# 产物始终在 forge_robots/dist/robot_piper，PyInstaller 中间文件在 forge_robots/build/piper/
#（由脚本路径解析仓库根，与从何处调用无关）。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORGE_ROBOTS_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DIST_DIR="${FORGE_ROBOTS_ROOT}/dist"
WORK_DIR="${FORGE_ROBOTS_ROOT}/build/$(basename "${SCRIPT_DIR}")"
cd "${SCRIPT_DIR}"
mkdir -p "${DIST_DIR}" "${WORK_DIR}"

echo "==> Building robot_piper with PyInstaller (using ${SCRIPT_DIR}/robot_piper.spec)"

pyinstaller \
  --noconfirm \
  --clean \
  --distpath "${DIST_DIR}" \
  --workpath "${WORK_DIR}" \
  "${SCRIPT_DIR}/robot_piper.spec"

EXE_NAME="robot_piper"
if [[ -f "${DIST_DIR}/${EXE_NAME}" ]]; then
  echo "OK: ${DIST_DIR}/${EXE_NAME}"
elif [[ -f "${DIST_DIR}/${EXE_NAME}.exe" ]]; then
  echo "OK: ${DIST_DIR}/${EXE_NAME}.exe"
else
  echo "WARNING: ${DIST_DIR}/${EXE_NAME} 未找到，请检查 PyInstaller 输出。" >&2
  exit 1
fi
