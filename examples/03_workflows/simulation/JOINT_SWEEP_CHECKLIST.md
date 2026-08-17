# 仿真关节 / 自由度检查记录

本文件记录 Agilex Piper MuJoCo 模型的仿真检查：仓内 actuator-specific `test_action_source.py` 自动动作驱动，以及原生 MuJoCo GUI 手动检查。它不是逐关节 min / max / 回零验收表；真机方向、零位、限位仍归入后续实机复核。

## 检查前提

- 交付 MJCF 中 gripper 为总开口 `ctrlrange=0..0.105`、`gear=2`，中点映射与 `joint7/8` equality 已按文档约定落盘。
- `mujoco_piper/simulator.yaml` 与 `mujoco_piper/task_robot.yaml` 已按 `item_1/` 前缀、7 个逻辑控制量、四路相机 topic 对齐。

## 本次检查范围

| 组别 | 检查对象 | 结论 |
|------|----------|------|
| 单臂 | `joint1` ~ `joint6` | 自动 sweep 与原生 GUI 手动检查均正常 |
| 夹爪 | `gripper`（总开口米值，状态为 `joint7 - joint8`） | 迁移后命令范围已检查；GUI 记录为迁移前历史结果 |
| 相机 | `image/hand`、`image/top`、`image/angle`、`image/left_pillar` | 四路图像 topic 正常，约 26~30 FPS |

## 检查记录

- 2026-05-12：激活 项目虚拟环境 后运行 `mujoco_piper/dataflow.test_action_source.yaml` 做短时间自动 sweep smoke test。`dora build` 通过，`dora run` 中 `mujoco`、`task_robot`、`test_action_source`、`image_viewer`、`stream_viewer` 均 ready；MuJoCo 成功映射 7 个逻辑控制量与夹爪派生状态，`task_robot` 持续收发 `proprio_state`、`action`、`image/hand`、`image/top`、`image/angle`、`image/left_pillar`。验收记录。
- 2026-05-12：使用原生 MuJoCo viewer 加载 `assets/mjcf/piper_mujoco/scene.xml` 手动调整控制量。`joint1` ~ `joint6` 与 `gripper` 夹爪均可正常响应，未见异常抖动、方向异常、明显穿模、飞出或模型爆炸。此记录早于总开口米值迁移。验收记录。
- 2026-07-30：交付 MJCF 已按总开口 gripper 语义整理；仓内 sweep source 的夹爪范围更新为 `0..0.105 m`。尚未重跑迁移后的 Dora workflow 或原生 GUI 动态观察。

## 后续真机对照

与 URDF、厂商文档或真机视频对照；修改方向或限位时，在 MR 说明依据并更新 `config/`。
