# 03 — Forge 端到端 workflow

## 本仓已落地

| workflow | 路径 | 状态 |
|----------|------|------|
| MuJoCo 仿真 smoke test | `simulation/mujoco_piper/` | 已接入本仓 `assets/mjcf/piper_mujoco/scene.xml`，已完成 Dora build / run 与 GUI 检查 |

## 复用已有 Forge / runtime

| workflow | 现有入口 | 说明 |
|----------|----------|------|
| 仿真录制 / 推理 | `sim_record/`、`simulation/mujoco_piper/` | 本仓已复制 / 生成 dataflow，model_path 指向 `assets/mjcf/piper_mujoco/scene.xml` |
| 真机录制 | `real_record/` | 本仓已复制 dataflow，Agilex Piper 节点指向 `src/robots_agilex_piper/`，运行依赖现场 CAN / camera |
| 真机回放 / 从臂 | `real_playback/` | 本仓已复制 dataflow，用回放 action 驱动 follower Agilex Piper |
| PhyAgentOS bridge | `forge_runtime/examples/phyagentos_forge_bridge/` | 复用同一 joint order：`joint1` ~ `joint6`、`gripper` |

仿真检查记录见 `simulation/JOINT_SWEEP_CHECKLIST.md`。
仿真交付记录与 Forge 对接说明见 `simulation/SIMULATION_INTEGRATION.md`；`simulation/simulator.agilex_piper.example.yaml` 为 MuJoCo 节点配置骨架（完整示例以 **`mujoco_piper/simulator.yaml`** 为准）。
