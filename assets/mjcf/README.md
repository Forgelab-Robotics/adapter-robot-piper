# MJCF（MuJoCo）

仿真用 **`piper_mujoco/scene.xml` / `piper_mujoco/PIPER.xml` / `piper_mujoco/assets/`** 等直接放在本目录下。

## 资产状态

MJCF 与 mesh 已完成导入并作为本仓交付资产维护。常规仿真、CI 与示例运行均应直接使用本目录内容，不再依赖外部 `robot-mj-model` 仓库。

## 场景入口

| 文件 / 目录 | 说明 |
|-------------|------|
| `piper_mujoco/scene.xml` | 地面 + 固定观察相机 + `PIPER.xml` attach，`attach` 前缀 `item_1/` |
| `piper_mujoco/PIPER.xml` | Piper 单臂 + 夹爪主体，含腕部相机 `wrist_cam` |
| `piper_mujoco/assets/` | 模型网格 |
| `piper_mujoco/Variant/` | 上游扩展模型；可直接加载的 gripper actuator 与主模型保持同一总开口语义 |

## MJCF 校验

```bash
python scripts/verify_mjcf.py --xml assets/mjcf/piper_mujoco/scene.xml
```

校验器除加载模型和打印关节外，还会检查 gripper actuator 的 `ctrlrange=0 0.105`、`gear=2`、等效动态参数、`joint7/8` 限位/equality，以及 `0.0525 m` 中点映射。

## 与 GLB 的关系

见 `assets/glb/README.md`。仿真入口使用 `assets/mjcf/piper_mujoco/scene.xml`，不要把 `assets/glb/piper.xml`（pipeline 归一化产物）误当仿真入口。
