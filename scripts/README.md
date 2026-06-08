# 脚本

## 常规使用

| 脚本 | 作用 |
|------|------|
| `verify_mjcf.py` | 校验 MJCF 可加载并打印关节摘要 |
| `build_glb_robot_asset_pipeline.sh` | 调用 `robot_asset_pipeline` 输出到 `assets/glb/`（`piper.glb`、`piper.xml`、`meshes/`；默认 `--skip-preview`） |

## 历史导入工具

| 脚本 | 作用 |
|------|------|
| `sync_mjcf_from_robot_mj_model.sh` | 从 `robot-mj-model/models/PIPER` 导入到 `assets/mjcf/piper_mujoco/`（排除 `*.glb`） |
| `sync_glb_from_upstream.sh` | 从外部 Agilex Piper 资产源拷贝所有 `*.glb` 到 `assets/glb/piper_upstream/` |
