# Agilex Piper Robot Adapter

[English](README.md) | [简体中文](README_zh.md)

[查看机器人构型说明](description.md) ·
[开源审计记录](OPEN_SOURCE_AUDIT.md)

> [!WARNING]
> 本项目可以向真实机械臂发送运动指令，但不是经过功能安全认证的控制系统。
> 首次连接真机前必须阅读 [SAFETY.md](SAFETY.md)，验证厂商急停、隔离工作区，
> 并使用低速、小幅、单关节动作。使用者自行承担人身和设备风险。

## 交付内容

| 内容 | 路径 |
|------|------|
| **MJCF + meshes** | `assets/mjcf/piper_mujoco/`，仿真入口为 `scene.xml`，主模型为 `PIPER.xml` |
| **GLB / 可视化资产** | `assets/glb/piper.glb`，由本仓 MJCF 转换；上游 GLB 另保留追溯 |
| **仿真配置示例** | `examples/03_workflows/simulation/mujoco_piper/` |
| **真机节点源码** | `src/robots_agilex_piper/`，实现 Forge robot driver 与 Dora 节点入口 |

机器人模型来源与第三方许可见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。仿真配置位于
`examples/03_workflows/simulation/mujoco_piper/`，其 `simulator.yaml`
直接引用本仓 `assets/mjcf/piper_mujoco/scene.xml`。

## 安装与测试

需要 Python 3.12 或更高版本及
[`uv`](https://docs.astral.sh/uv/)。核心 Forge 包与其他 Python 依赖均从
PyPI 安装，`--frozen` 确保实际环境与 `uv.lock` 一致：

```bash
uv sync --frozen --extra test
uv run python -m unittest discover -s tests -v
uv run robots-agilex-piper --version
```

真机运行还需要 Linux、可用的 SocketCAN 接口及 AgileX Piper 硬件。Dora
workflow 中的通用仿真、TaskRobot、录制和查看节点由外部 Forge runtime 提供。
运行相关 dataflow 前设置：

```bash
export FORGE_RUNTIME_ROOT=/absolute/path/to/forge-runtime
export FORGE_RUNTIME_BIN="$FORGE_RUNTIME_ROOT/bin"
```

仅执行 SDK、配置解析和资产检查时不需要连接真机。CI 不运行任何真机动作。

## 配置

真机 follower 的权威示例为
`config/agilex_piper_slave.yaml.example`：

```bash
cp config/agilex_piper_slave.yaml.example config/agilex_piper_node.yaml
uv run robots-agilex-piper run --config config/agilex_piper_node.yaml
```

也可设置 `AGILEX_PIPER_NODE_CONFIG`。显式 `--config` 优先；Dora dataflow
应通过 `args: --config <path>` 传入。主要字段：

- `port`：SocketCAN 设备名，例如 `can0`。
- `is_follower`：`true` 驱动从臂，`false` 只读主臂。
- `motion_speed_percent`：硬件速度百分比 `1..100`，首次测试建议 `30` 或更低。
- `positions.initial` / `positions.reset`：连接和断开时使用的生命周期位姿。
- `debug`：是否启用调试日志。

配置仅在启动时读取，修改后需重启节点，不支持运行时热更新。完整说明见
[`config/README.md`](config/README.md)。

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
| `assets/glb/` | Web / 可视化 GLB（转换产物 + 上游 GLB 追溯） |
| `assets/urdf/` | 官方 Piper 单臂 + 夹爪 URDF、mesh 与上游许可 |
| `examples/01_sdk_tests/` | 直连厂商 SDK 的最小测试（与 Forge 解耦） |
| `examples/02_dora_tests/` | Dora 节点与 Topic 集成测试 |
| `examples/03_workflows/` | Forge 集成模板与已验证 workflow（仿真 / 真机） |
| `src/` | Forge 规范机器人节点源码位置说明 |
| `scripts/` | 节点 PyInstaller 打包脚本 |
| `config/` | 端口、相机、关节顺序、VR 标定等 |

## 资产状态

Agilex Piper 的 MJCF、mesh 与上游 GLB 已完成同步并落盘到本仓，后续仿真与交付以本仓 `assets/` 下内容为准：

- `assets/mjcf/piper_mujoco/scene.xml`：MuJoCo 仿真入口，`attach` 前缀为
  `item_1/`；补充 `left_pillar`、`top`、`angle` 三个固定场景相机
- `assets/mjcf/piper_mujoco/PIPER.xml`：Agilex Piper 单臂 + 夹爪主体，含腕部相机 `wrist_cam`
- `assets/glb/piper.glb`：Web / 可视化交付资产（由本仓 MJCF 转换）
- `assets/glb/piper_upstream/`：上游自带 GLB 保留追溯
- `assets/urdf/piper_with_gripper.urdf`：`piper_description` 1.0.0 单臂 + 夹爪模型；mesh 已改为仓内相对路径，不包含桌子或其他场景资产

## 仿真接入流程

分步说明、与 Forge runtime 对接要点及复现命令见：

**`examples/03_workflows/simulation/SIMULATION_INTEGRATION.md`**

摘要：资产齐 → 对齐约定 → 运行本仓 **`examples/03_workflows/simulation/mujoco_piper/`**（`model_path` 指本仓 `scene.xml`，`prefix: item_1/`，7 个逻辑控制量与 `task_robot` 一致）→ 自动 sweep smoke test → 原生 MuJoCo GUI 手动检查 → 与真机对表。检查记录见 `examples/03_workflows/simulation/JOINT_SWEEP_CHECKLIST.md`。

## `src/` 与 Forge 节点

Agilex Piper 真机 / Dora 节点实现位于
`src/robots_agilex_piper/`（包名 `robots_agilex_piper`）。本仓 workflow
中的 Agilex Piper 节点均指向该本地源码。

## 验证与交付文档

- 无硬件测试：`uv run python -m unittest discover -s tests -v`
- 锁文件安装与构建：`uv sync --frozen --extra test && uv build`
- 发版流程：[RELEASING.md](RELEASING.md)
- 开源验收：[OPEN_SOURCE_AUDIT.md](OPEN_SOURCE_AUDIT.md)
- 本地验收产物策略：[validation_output/README.md](validation_output/README.md)
- MJCF / GLB 资产策略：[assets/mjcf/README.md](assets/mjcf/README.md)、
  [assets/glb/README.md](assets/glb/README.md)
- 仿真检查：
  [JOINT_SWEEP_CHECKLIST.md](examples/03_workflows/simulation/JOINT_SWEEP_CHECKLIST.md)

## 常见问题与限制

- 仅真机驱动支持 Linux SocketCAN；其他系统可运行无硬件测试和资产检查。
- `Permission denied`：检查 CAN 接口权限，使用
  `uv run robots-agilex-piper activate-devices` 激活设备。
- 主从角色异常：先运行 `list-devices` 和 `check-role`，必要时经现场确认后使用
  `set-role`。
- 夹爪命令被拒绝或截取：确认值为两指总开口米值，不要直接使用旧毫米制数据。
- Dora 集成模板依赖外部 Forge runtime，并要求设置 `FORGE_RUNTIME_ROOT` /
  `FORGE_RUNTIME_BIN`。
- CI 不连接真机；CAN、固件限位、急停、方向和生命周期位姿仍需现场验收。

## 许可证

本仓自有代码、配置和文档采用
[Apache License 2.0](LICENSE)。机器人模型与衍生的 GLB/USD 保留各自上游
MIT 许可；完整归属见 [NOTICE](NOTICE) 和
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。Apache-2.0 不授予
AgileX、Piper 或其他第三方商标的使用权。

## Forge 2.x 迁移

本分支准备节点版本 `2.0.0`，适配 Dora 1.x，迁移验证锁定 Dora `1.0.1`。使用正式 Forge 2.x 分发包；Common 至少为 `2.1.0`。此次更新包括依赖锁文件与各独立可执行入口。

每轮报告必须列出仓库、改动和测试证据，包括各节点的 `dora run` 记录，以及包含 `adapter-forge-gateway` 的串联测试。缺少硬件或模型的验收项保持待验证。源码 PR 不等于正式发布；整体验收通过后再同步 GitLab。
