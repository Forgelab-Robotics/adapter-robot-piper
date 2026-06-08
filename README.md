# Agilex Piper（Forge 机器人交付包）

## 交付内容

| 内容 | 路径 |
|------|------|
| **MJCF + meshes** | `assets/mjcf/piper_mujoco/`，仿真入口为 `scene.xml`，主模型为 `PIPER.xml` |
| **GLB / 可视化资产** | `assets/glb/piper.glb`，由 `robot_asset_pipeline` 生成；上游 GLB 另保留追溯 |
| **仿真配置示例** | `examples/03_workflows/simulation/mujoco_piper/` |
| **真机节点源码** | `src/robots_agilex_piper/`，由 `forge_robots/packages/piper/` 迁入 |

本仓以 `robot-mj-model/models/PIPER` 与既有 `forge_runtime` Agilex Piper 示例为资产和 workflow 来源，已在 `examples/03_workflows/simulation/mujoco_piper/` 提供本仓可运行配置，其 `simulator.yaml` 的 `model_path` 指向本仓 `assets/mjcf/piper_mujoco/scene.xml`。

## 目录结构

| 路径 | 说明 |
|------|------|
| `assets/mjcf/` | MJCF、mesh、`scene.xml` |
| `assets/glb/` | Web / 可视化 GLB（pipeline 产物 + 上游 GLB 追溯） |
| `assets/urdf/` | URDF 预留目录；当前未固定 Agilex Piper URDF 版本 |
| `examples/01_sdk_tests/` | 直连厂商 SDK 的最小测试（与 Forge 解耦） |
| `examples/02_dora_tests/` | Dora 节点与 Topic 集成测试 |
| `examples/03_workflows/` | 端到端 Forge workflow（仿真 / 真机 / 同构 / VR） |
| `src/` | Forge 规范机器人节点源码位置说明 |
| `scripts/` | MJCF 校验、GLB 构建、历史资产导入工具 |
| `config/` | 端口、相机、关节顺序、VR 标定等 |

## 资产状态

Agilex Piper 的 MJCF、mesh 与上游 GLB 已完成同步并落盘到本仓，后续仿真与交付以本仓 `assets/` 下内容为准：

- `assets/mjcf/piper_mujoco/scene.xml`：MuJoCo 仿真入口，`attach` 前缀为 `item_1/`
- `assets/mjcf/piper_mujoco/PIPER.xml`：Agilex Piper 单臂 + 夹爪主体，含腕部相机 `wrist_cam`
- `assets/mjcf/piper_mujoco/scene.xml`：在上游场景基础上补充 `left_pillar`、`top`、`angle` 三个固定场景相机，用于兼容既有 Forge image topic
- `assets/glb/piper.glb`：Web / 可视化交付资产（pipeline 产物）
- `assets/glb/piper_upstream/`：上游自带 GLB 保留追溯
- `assets/urdf/`：当前未固定 URDF；如后续补充，请记录来源版本与 MJCF 对应关系

## 仿真接入流程

分步说明、与 `forge_runtime` 对接要点及复现命令见：

**`examples/03_workflows/simulation/SIMULATION_INTEGRATION.md`**

摘要：资产齐 → `verify_mjcf` → 对齐约定 → 运行本仓 **`examples/03_workflows/simulation/mujoco_piper/`**（`model_path` 指本仓 `scene.xml`，`prefix: item_1/`，7 个逻辑控制量与 `task_robot` 一致）→ 自动 sweep smoke test → 原生 MuJoCo GUI 手动检查 → 与真机对表。检查记录见 `examples/03_workflows/simulation/JOINT_SWEEP_CHECKLIST.md`。

## `src/` 与 Forge 节点

当前 Agilex Piper 真机 / Dora 节点实现已从 `forge_robots/packages/piper/` 迁入本仓 `src/robots_agilex_piper/`（包名 `robots_agilex_piper`）。本仓 workflow 中的 Agilex Piper 节点均指向该本地源码；后续若上游实现更新，应同步迁入并记录来源 commit。
