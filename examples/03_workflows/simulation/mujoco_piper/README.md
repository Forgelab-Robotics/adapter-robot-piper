# MuJoCo + Agilex Piper（Forge / dora-rs）

本目录放在 **`examples/03_workflows/simulation/`**，与 Agilex Piper 资产、仿真说明同一套工作流；配置对应本仓 **`assets/mjcf/piper_mujoco/scene.xml`**（`attach` 前缀 `item_1/`）。

## 约定摘要

- **7 个逻辑控制量**：`joint1` ~ `joint6` + `gripper`。
- **夹爪**：`gripper` 映射到底层 actuator `gripper`，状态由 `joint7` / `joint8` 派生为毫米量。
- **图像**：`item_1/wrist_cam` → `image/hand`；`top`、`angle`、`left_pillar` 为本仓场景相机。

## 运行（test_action_source）

```bash
cd robots/agilex_piper/examples/03_workflows/simulation/mujoco_piper
dora build dataflow.test_action_source.yaml --uv
dora run dataflow.test_action_source.yaml --uv
```
