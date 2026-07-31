# MuJoCo + Agilex Piper（Forge / dora-rs）

本目录放在 **`examples/03_workflows/simulation/`**，与 Agilex Piper 资产、仿真说明同一套工作流；配置对应本仓 **`assets/mjcf/piper_mujoco/scene.xml`**（`attach` 前缀 `item_1/`）。

## 约定摘要

- **7 个逻辑控制量**：`joint1` ~ `joint6` + `gripper`。
- **夹爪**：`gripper` 是两指总开口米值 `0..0.105`，直接映射到底层 actuator；状态为 `joint7 - joint8`，`state_scale: 1.0`。
- **模型映射**：actuator 使用 `gear=2`，因此中点 `0.0525` 对应 `joint7=0.02625`、`joint8=-0.02625`。
- **图像**：`item_1/wrist_cam` → `image/hand`；`top`、`angle`、`left_pillar` 为本仓场景相机。

## 运行（test_action_source）

```bash
cd robots/agilex_piper/examples/03_workflows/simulation/mujoco_piper
dora build dataflow.test_action_source.yaml --uv
dora run dataflow.test_action_source.yaml --uv
```

仓内 `test_action_source.py` 使用 actuator-specific 合法范围：六轴按各自方向扫描，夹爪仅扫描 `0..0.105 m`，不会依赖 MuJoCo 饱和掩盖单位错误。模型数值检查可从仓根运行：

```bash
python scripts/verify_mjcf.py --xml assets/mjcf/piper_mujoco/scene.xml
```
