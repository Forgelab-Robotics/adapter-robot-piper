# Agilex Piper 节点

基于 dora-rs 的 Agilex Piper 机器人节点：订阅 TaskRobot 下发的 `JointCommand`，通过 Agilex Piper 底层 SDK / CAN 与硬件交互，将读到的状态以 `JointState` 输出，供 TaskRobot 聚合为 `proprio_state`。

## 位置

本实现已迁入机器人交付仓：

`robots/agilex_piper/src/robots_agilex_piper/`

来源为工作区内 `forge_robots/packages/piper/`。

## 配置

复制 `config.example.yaml` 为现场配置并修改。配置来源（优先级从高到低）：

- `--config config/agilex_piper_slave.yaml.example`
- 环境变量 `AGILEX_PIPER_NODE_CONFIG`
- dataflow 节点参数中的 `config` / `config_path`

本仓同时提供：

- `config/agilex_piper_master.yaml.example`
- `config/agilex_piper_slave.yaml.example`

## Dataflow 使用

在本仓 workflow 中，Agilex Piper 节点路径应指向：

```yaml
path: ../../../src/robots_agilex_piper/main.py
```

典型连接关系：

- TaskRobot 输出 `robot_0/action`，连接到 Agilex Piper follower 节点输入 `action`。
- Agilex Piper 节点输出 `state`，连接到 TaskRobot 输入 `robot_0/state`。
- master / follower 模式中，`agilex_piper_master/state` 可连接到 `agilex_piper_slave/master_state`。

## CLI 子命令

`main.py` 同时作为 dora 节点与 CLI 入口：

| 子命令 | 说明 |
|--------|------|
| `run --config ...` 或无子命令 | 运行 dora 节点 |
| `test [DEVICE] [-d SEC]` | 夹爪循环，确认设备与机械臂对应 |
| `watch-state [DEVICE]` | 监视状态；夹爪总开口显示为米，EE 平移保持毫米 |
| `list-devices` | 列出 CAN 接口 |
| `activate-devices` | 激活所有 CAN 接口（需权限） |
| `check-role` | 主从检测（Agilex Piper 专用） |
| `set-role DEVICE ROLE` | 设置主/从臂（Agilex Piper 专用） |

示例：

```bash
cd robots/agilex_piper
uv run robots-agilex-piper list-devices --json
uv run robots-agilex-piper check-role can0 can1 --json
uv run robots-agilex-piper test can0 --duration 15
```

## 打包

```bash
cd robots/agilex_piper
./scripts/build_pyinstaller.sh
```

产物默认在 `dist/robots_agilex_piper`。

## 关节顺序

Agilex Piper 的 actuator 顺序与节点实现绑定，固定为：

`joint1`、`joint2`、`joint3`、`joint4`、`joint5`、`joint6`、`gripper`

TaskRobot 中该机器人的 `actuator_order` / `joints` 需与此一致。

`joint1`～`joint6` 使用弧度；`gripper` 使用米，表示两指总开口，合法范围 `0..0.105`。SDK 的 `grippers_angle` 仍是 `0..105000`（每单位 `1e-6 m`），由驱动严格转换。旧毫米值（例如 `40.0`）会报错，迁移时应改为 `0.04`。
