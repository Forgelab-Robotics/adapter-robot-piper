# 模型对齐记录

## 结论

- 仿真入口：`assets/mjcf/piper_mujoco/scene.xml`
- 主模型：`assets/mjcf/piper_mujoco/PIPER.xml`
- attach 前缀：`item_1/`
- 场景位置：`scene.xml` 中 `body name="item_1"` 位于 `pos="0.0 0.0 0.0"`
- 相机：`item_1/wrist_cam` 转发为 `image/hand`；`left_pillar`、`top`、`angle` 为场景级固定相机
- GLB：`assets/glb/piper.glb`，仅作为 Web / 可视化交付资产
- 夹爪：Forge/MuJoCo `gripper` 为两指总开口 `0..0.105 m`；actuator `gear=2` 映射到保留原限位/equality 的 `joint7/8`

## 记录

- 2026-05-12：基于既有 `forge_runtime` Agilex Piper 示例和本仓 MJCF 资产建立 Agilex Piper 仿真资产与 workflow 配置；仿真 SSOT 以 `assets/mjcf/piper_mujoco/scene.xml` 为准。真机方向、零位、限位待后续实机资料复核。记录人：陈若冰。
