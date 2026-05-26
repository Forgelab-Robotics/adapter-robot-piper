#!/usr/bin/env bash

set -euo pipefail

# 打包 Piper 节点为单文件可执行程序。
# 产物在本包 dist/robots_agilex_piper，中间文件在本包 build/pyinstaller/。
# 需先安装打包依赖，例如：
#   uv sync --extra pyinstaller
#   ./scripts/build_pyinstaller.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${PACKAGE_DIR}/dist"
WORK_DIR="${PACKAGE_DIR}/build/pyinstaller"

cd "${PACKAGE_DIR}"
mkdir -p "${DIST_DIR}" "${WORK_DIR}"
rm -f "${DIST_DIR}/robots_agilex_piper" "${DIST_DIR}/robots_agilex_piper.exe"

echo "==> Building robots_agilex_piper with PyInstaller (using ${PACKAGE_DIR}/robots_piper.spec)"

uv run --extra pyinstaller pyinstaller \
  --noconfirm \
  --clean \
  --distpath "${DIST_DIR}" \
  --workpath "${WORK_DIR}" \
  "${PACKAGE_DIR}/robots_piper.spec"

EXE_NAME="robots_agilex_piper"
if [[ -f "${DIST_DIR}/${EXE_NAME}" ]]; then
  echo "OK: ${DIST_DIR}/${EXE_NAME}"
elif [[ -f "${DIST_DIR}/${EXE_NAME}.exe" ]]; then
  echo "OK: ${DIST_DIR}/${EXE_NAME}.exe"
else
  echo "WARNING: ${DIST_DIR}/${EXE_NAME} 未找到，请检查 PyInstaller 输出。" >&2
  exit 1
fi
