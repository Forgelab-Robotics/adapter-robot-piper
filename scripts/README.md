# 脚本

本目录仅保留节点打包相关脚本。

| 脚本 | 作用 |
|------|------|
| `build_pyinstaller.sh` | 在隔离构建环境中用 PyInstaller 打包 `robots_agilex_piper` 单文件可执行程序 |
| `robots_agilex_piper.spec` | PyInstaller 规格文件，由 `build_pyinstaller.sh` 调用 |

## 打包

```bash
cd robots/agilex_piper
./scripts/build_pyinstaller.sh
```

产物默认在 `dist/robots_agilex_piper`。
