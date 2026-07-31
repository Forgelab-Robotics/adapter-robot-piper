# GLB / 可视化

本目录放 **面向 Web / 可视化 / 资源分发** 的产物，与 **`assets/mjcf/`**（MuJoCo 仿真主数据：`*.xml` + 原始 mesh）分开。

## 当前文件（`robot_asset_pipeline` 生成）

| 文件 / 目录 | 说明 |
|-------------|------|
| `piper.glb` | 由 `../mjcf/piper_mujoco/PIPER.xml` 导出并压缩 |
| `piper.xml` | **归一化后的 MJCF**（与 `../mjcf/` 中仿真用 XML **不是同一份**）；gripper actuator 同步为总开口 `0..0.105 m` / `gear=2` |
| `meshes/` | 流水线写出的网格，供上述 `piper.xml` 引用 |
| `piper_upstream/` | 上游自带 GLB，保留用于对照与追溯 |

## 重新生成

```bash
./scripts/build_glb_robot_asset_pipeline.sh
```

需要 **1080 预览图** 时去掉 `--skip-preview` 或设 `PIPER_SKIP_PREVIEW=0`（需安装 Blender）。重新生成后应对生成的 XML 再运行 `scripts/verify_mjcf.py`，避免流水线丢失总开口 actuator 属性。
