# Agilex Piper（Forge 机器人交付包）

[查看机器人构型说明](description.md)

## 交付内容

| 内容 | 路径 |
|------|------|
| **MJCF + meshes** | `assets/mjcf/piper_mujoco/`，仿真入口为 `scene.xml`，主模型为 `PIPER.xml` |
| **GLB / 可视化资产** | `assets/glb/piper.glb`，由 `robot_asset_pipeline` 生成；上游 GLB 另保留追溯 |
| **仿真配置示例** | `examples/03_workflows/simulation/mujoco_piper/` |
| **真机节点源码** | `src/robots_agilex_piper/`，由 `forge_robots/packages/piper/` 迁入 |

本仓以 `robot-mj-model/models/PIPER` 与既有 `forge_runtime` Agilex Piper 示例为资产和 workflow 来源，已在 `examples/03_workflows/simulation/mujoco_piper/` 提供本仓可运行配置，其 `simulator.yaml` 的 `model_path` 指向本仓 `assets/mjcf/piper_mujoco/scene.xml`。

## 夹爪单位契约

- Forge 层的 `gripper` 表示**两指总开口**，SI 单位为米，范围 `0..0.105 m`。
- Piper SDK 边界保持整数 `0..105000`，每单位为 `1e-6 m`；驱动严格按米编解码。运行时越界命令会记录 warning 并截取到合法范围，不会把旧毫米值解释成毫米。
- MuJoCo actuator 直接接收总开口米值；`gear=2` 将总开口映射为 `joint7 = gripper / 2`，equality 保持 `joint8 = -joint7`。
- 旧配置、action 或 MCAP 中的毫米值必须显式除以 `1000` 后再使用；本仓不会把 `40.0` 等旧值解释为 `40 mm`（运行时会 warning 后截取为最大开口 `0.105 m`，配置值仍会拒绝）。
- `piper-sdk` 的默认软件夹爪限位是 `0..0.07 m`，对应小夹爪；协议还支持 `100 mm` 大夹爪参数。本项目保留交付模型定义的 `0..0.105 m` 总开口契约，且未启用 SDK 自带的夹爪软件限位。部署时应按实际夹爪型号确认固件参数。

## 六轴关节限位

驱动、MJCF 和 URDF 与锁定的 `piper-sdk==0.6.2` 中 `C_PiperParamManager` 默认软件限位保持一致：

| 关节 | 范围（rad） | 范围（°） |
|------|-------------|-----------|
| joint1 | `[-2.6179, 2.6179]` | `[-150, 150]` |
| joint2 | `[0, 3.14]` | `[0, 180]` |
| joint3 | `[-2.967, 0]` | `[-170, 0]` |
| joint4 | `[-1.745, 1.745]` | `[-100, 100]` |
| joint5 | `[-1.22, 1.22]` | `[-70, 70]` |
| joint6 | `[-2.09439, 2.09439]` | `[-120, 120]` |

SDK 还提供 `GetAllMotorAngleLimitMaxSpd()`，可从已连接真机读取固件当前限位；现场反馈应作为最终验收依据。

## 真机生命周期

- Follower 连接后固定移动到 `positions.initial` 并等待到位，关闭/断开前固定移动到 `positions.reset`；任一到位等待超时都会返回失败，不再提供跳过生命周期位姿的行为开关。
- 新的真机采集 Workflow 应显式设置 `motion_speed_percent: 30`，首次验收使用受限硬件速度。
- reset 位到位后直接断开 CAN，不发送 `DisablePiper()`，避免正常关闭时立即失去保持力；reset 到位失败仍会继续断开 CAN，但节点最终返回失败。连接初始化失败的回滚流程仍会尝试失能。现场仍需保留厂商急停与人工安全边界。
- 生命周期字段只接受 `initial` 与 `reset`；旧 `positions.rest` 和 `move_to_rest_position()` 已删除，不提供兼容别名。

## 目录结构

| 路径 | 说明 |
|------|------|
| `assets/mjcf/` | MJCF、mesh、`scene.xml` |
| `assets/glb/` | Web / 可视化 GLB（pipeline 产物 + 上游 GLB 追溯） |
| `assets/urdf/` | 官方 Piper 单臂 + 夹爪 URDF、mesh 与上游许可 |
| `examples/01_sdk_tests/` | 直连厂商 SDK 的最小测试（与 Forge 解耦） |
| `examples/02_dora_tests/` | Dora 节点与 Topic 集成测试 |
| `examples/03_workflows/` | 端到端 Forge workflow（仿真 / 真机 / 同构 / VR） |
| `src/` | Forge 规范机器人节点源码位置说明 |
| `scripts/` | 节点 PyInstaller 打包脚本 |
| `config/` | 端口、相机、关节顺序、VR 标定等 |

## 资产状态

Agilex Piper 的 MJCF、mesh 与上游 GLB 已完成同步并落盘到本仓，后续仿真与交付以本仓 `assets/` 下内容为准：

- `assets/mjcf/piper_mujoco/scene.xml`：MuJoCo 仿真入口，`attach` 前缀为 `item_1/`
- `assets/mjcf/piper_mujoco/PIPER.xml`：Agilex Piper 单臂 + 夹爪主体，含腕部相机 `wrist_cam`
- `assets/mjcf/piper_mujoco/scene.xml`：在上游场景基础上补充 `left_pillar`、`top`、`angle` 三个固定场景相机，用于兼容既有 Forge image topic
- `assets/glb/piper.glb`：Web / 可视化交付资产（pipeline 产物）
- `assets/glb/piper_upstream/`：上游自带 GLB 保留追溯
- `assets/urdf/piper_with_gripper.urdf`：`piper_description` 1.0.0 单臂 + 夹爪模型；mesh 已改为仓内相对路径，不包含桌子或其他场景资产

## 仿真接入流程

分步说明、与 `forge_runtime` 对接要点及复现命令见：

**`examples/03_workflows/simulation/SIMULATION_INTEGRATION.md`**

摘要：资产齐 → 对齐约定 → 运行本仓 **`examples/03_workflows/simulation/mujoco_piper/`**（`model_path` 指本仓 `scene.xml`，`prefix: item_1/`，7 个逻辑控制量与 `task_robot` 一致）→ 自动 sweep smoke test → 原生 MuJoCo GUI 手动检查 → 与真机对表。检查记录见 `examples/03_workflows/simulation/JOINT_SWEEP_CHECKLIST.md`。

## `src/` 与 Forge 节点

当前 Agilex Piper 真机 / Dora 节点实现已从 `forge_robots/packages/piper/` 迁入本仓 `src/robots_agilex_piper/`（包名 `robots_agilex_piper`）。本仓 workflow 中的 Agilex Piper 节点均指向该本地源码；后续若上游实现更新，应同步迁入并记录来源 commit。
