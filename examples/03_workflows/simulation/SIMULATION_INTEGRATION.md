# Piper 仿真交付记录

本文件记录 Piper 仿真资产、MuJoCo 配置与 Dora workflow 的交付状态。当前交付已建立可复现的仿真配置，并完成 `mujoco_piper/dataflow.test_action_source.yaml` 自动 sweep smoke test 与原生 MuJoCo GUI 手动检查。

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
cd /path/to/robots/piper
python scripts/verify_mjcf.py --xml assets/mjcf/piper_mujoco/scene.xml
```

- **前缀**：`scene.xml` 使用 `attach` 前缀 `item_1/`，故模型内关节全名形如 `item_1/joint1`。Forge 配置里写无前缀的逻辑名 + `robots[].prefix: item_1/`。
- **执行器**：`PIPER.xml` 中 `<actuator>` 共 **7** 个（6 个 arm position actuator、1 个 gripper actuator），与 `simulator.yaml` / `task_robot.yaml` 的 `actuator_order` 一致。
- **夹爪**：`gripper` 为逻辑量，映射到 `gripper` actuator；状态由 `joint7` 与 `joint8` 的开口差派生为毫米量。
- **相机**：`item_1/wrist_cam` 转发为 `image/hand`，场景级 `top`、`angle`、`left_pillar` 分别转发到同名 topic，以兼容既有 Forge Piper 示例。

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
- 2026-05-12：使用原生 MuJoCo viewer 手动调整控制量，`joint1` ~ `joint6` 与 `gripper` 夹爪均可正常响应，未见异常抖动、方向异常、明显穿模、飞出或模型爆炸。记录人：陈若冰。

---

## 5. 仿真关节 / 执行器检查

**结论**：已完成自动 sweep smoke test 与原生 MuJoCo GUI 手动检查，四路图像 topic 正常；单臂与夹爪控制均未见明显异常。详细记录见 `JOINT_SWEEP_CHECKLIST.md`。

---

## 6. 真机 / 文档对照边界

**结论**：本次交付覆盖仿真资产与仿真 workflow 配置；真机方向、零位、限位属于后续实机复核项，不阻塞当前仿真接入骨架。

## 交付复现命令

1. 在 `robots/piper` 根目录运行：`python scripts/verify_mjcf.py --xml assets/mjcf/piper_mujoco/scene.xml`。
2. 进入 **`examples/03_workflows/simulation/mujoco_piper/`**，按该目录 **`README.md`** 执行 `dora build` / `dora run`。
3. 复核 **`mujoco_piper/simulator.yaml`** 与 **`mujoco_piper/task_robot.yaml`** 的 `actuator_order` 与相机 topic。
