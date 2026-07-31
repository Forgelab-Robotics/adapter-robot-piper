# Agilex Piper 仿真交付记录

本文件记录 Agilex Piper 仿真资产、MuJoCo 配置与 Dora workflow 的交付状态。当前交付已建立可复现的仿真配置；2026-05-12 的自动 sweep / GUI 记录属于夹爪单位迁移前历史结果，迁移后的静态映射由增强版 `verify_mjcf.py` 验证，GUI 动态复核仍需另行执行。

---

## 1. 资产整理（MJCF / GLB）

**结论**：仿真只依赖本仓 MJCF + mesh；交付另备 GLB。当前未固定 URDF 版本。

| 资产 | 本仓路径 | 状态自检 |
|------|-----------|----------|
| MJCF + mesh | **`assets/mjcf/piper_mujoco/`** | 已落盘，仿真入口为 `scene.xml` |
| GLB（Web/交付） | `assets/glb/piper.glb` | 已由 `robot_asset_pipeline` 生成 |
| URDF | `assets/urdf/` | 当前目录预留 |

---

## 2. MJCF 核查（名称、顺序、单位、限位、层级、mesh）

**结论**：模型入口、前缀、执行器与 `mujoco_piper/simulator.yaml` 已按以下约定整理。

复现检查命令：

```bash
cd /path/to/robots/agilex_piper
python scripts/verify_mjcf.py --xml assets/mjcf/piper_mujoco/scene.xml
```

- **前缀**：`scene.xml` 使用 `attach` 前缀 `item_1/`，故模型内关节全名形如 `item_1/joint1`。Forge 配置里写无前缀的逻辑名 + `robots[].prefix: item_1/`。
- **执行器**：`PIPER.xml` 中 `<actuator>` 共 **7** 个（6 个 arm position actuator、1 个 gripper actuator），与 `simulator.yaml` / `task_robot.yaml` 的 `actuator_order` 一致。
- **夹爪**：`gripper` 为两指总开口米值 `0..0.105`。actuator 显式设置 `inheritrange=0`、`ctrlrange="0 0.105"`、`gear=2`；状态由 `joint7 - joint8` 直接派生，`state_scale=1.0`。
- **夹爪动态**：保留 `joint7/8` 的 `±0.0525 m` 限位与 `joint8=-joint7` equality。为近似保持旧 joint-space `kp=40`、`kv=5`、力限 `±10`，新 actuator 使用 `kp=10`、`kv=1.25`、`forcerange="-5 5"`。
- **相机**：`item_1/wrist_cam` 转发为 `image/hand`，场景级 `top`、`angle`、`left_pillar` 分别转发到同名 topic，以兼容既有 Forge Agilex Piper 示例。

---

## 3. 模型对齐（原点、朝向、缩放）

**结论**：仿真入口以 `assets/mjcf/piper_mujoco/scene.xml` 为准；GLB 仅作为 Web / 可视化交付资产。

- **仿真 SSOT**：以 **`assets/mjcf/piper_mujoco/`** 为准。
- **留痕记录**：模型对齐记录见 **`MODEL_ALIGNMENT_NOTES.md`**。

---

## 4. Workflow 与节点（Forge / Dora）

**结论**：本仓已提供 Dora workflow 配置，MuJoCo 节点可通过该配置加载本仓模型，`task_robot` 的关节顺序与仿真配置一致。

**运行记录**：

- 2026-05-12：激活 `forge_runtime/.venv` 后执行 `dora build dataflow.test_action_source.yaml --uv` 通过；随后使用 `timeout 12s dora run dataflow.test_action_source.yaml --uv` 做短时间 smoke test。`mujoco`、`task_robot`、`test_action_source`、`image_viewer`、`stream_viewer` 均 ready。MuJoCo 成功映射 7 个逻辑控制量与夹爪派生状态，`task_robot` 持续收发 `proprio_state`、`action`、`image/hand`、`image/top`、`image/angle`、`image/left_pillar`；四路图像 topic 约 26~30 FPS。`stream_viewer` 使用 `8771` 端口以避免与其它机器人示例冲突。记录人：陈若冰。
- 2026-05-12：使用原生 MuJoCo viewer 手动调整控制量，`joint1` ~ `joint6` 与 `gripper` 夹爪均可正常响应，未见异常抖动、方向异常、明显穿模、飞出或模型爆炸。此记录早于总开口米值迁移。记录人：陈若冰。
- 2026-07-30：增强版 `verify_mjcf.py` 分别加载运行时 `scene.xml`、主模型、3 个 Variant 和 2 个 GLB XML 镜像，检查 gripper ctrl/force range、gear、编译后 kp/kv、joint limits/equality，并验证中点 `0.0525 -> joint7=0.02625, joint8=-0.02625`。迁移后的 GUI 动态与真机仍待复核。

---

## 5. 仿真关节 / 执行器检查

**结论**：仓内 range-aware sweep source 已覆盖夹爪 `0..0.105 m` 命令生成，增强版 verifier 覆盖静态 actuator/中点映射；2026-05-12 的 Dora/GUI 结果保留为迁移前历史记录。迁移后 GUI 动态复核未宣称完成，详见 `JOINT_SWEEP_CHECKLIST.md`。

---

## 6. 真机 / 文档对照边界

**结论**：本次交付覆盖仿真资产与仿真 workflow 配置；真机方向、零位、限位属于后续实机复核项，不阻塞当前仿真接入骨架。

## 交付复现命令

1. 在 `robots/agilex_piper` 根目录运行：`python scripts/verify_mjcf.py --xml assets/mjcf/piper_mujoco/scene.xml`。
2. 进入 **`examples/03_workflows/simulation/mujoco_piper/`**，按该目录 **`README.md`** 执行 `dora build` / `dora run`。
3. 复核 **`mujoco_piper/simulator.yaml`** 与 **`mujoco_piper/task_robot.yaml`** 的 `actuator_order` 与相机 topic。
