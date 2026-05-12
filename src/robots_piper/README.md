# Piper 节点

基于 dora-rs 的 Piper 机器人节点：订阅 TaskRobot 下发的 `RobotAction`，通过 Piper 底层 SDK / CAN 与硬件交互，将读到的状态以 `RobotState` 输出，供 TaskRobot 聚合为 `ProprioState`。

## 位置

本实现已迁入机器人交付仓：

`robots/piper/src/robots_piper/`

来源为工作区内 `forge_robots/packages/piper/`。

## 配置

复制 `config.example.yaml` 为现场配置并修改。配置来源（优先级从高到低）：

- `--config /path/to/config.yaml`
- 环境变量 `PIPER_NODE_CONFIG`
- dataflow 节点参数中的 `config` / `config_path`

本仓同时提供：

- `config/piper_master.yaml.example`
- `config/piper_slave.yaml.example`

## Dataflow 使用

在本仓 workflow 中，Piper 节点路径应指向：

```yaml
path: ../../../src/robots_piper/main.py
```

典型连接关系：

- TaskRobot 输出 `robot_0/action`，连接到 Piper follower 节点输入 `action`。
- Piper 节点输出 `state`，连接到 TaskRobot 输入 `robot_0/state`。
- master / follower 模式中，`piper_master/state` 可连接到 `piper_slave/master_state`。

## CLI 子命令

`main.py` 同时作为 dora 节点与 CLI 入口：

| 子命令 | 说明 |
|--------|------|
| `run --config ...` 或无子命令 | 运行 dora 节点 |
| `gripper-cycle [PORT] [-d SEC]` | 夹爪循环，确认端口与机械臂对应 |
| `list-ports` | 列出 CAN 接口 |
| `activate-ports` | 激活所有 CAN 接口（需权限） |
| `check-role` | 主从检测 |

示例：

```bash
cd robots/piper/src/robots_piper
uv run python main.py list-ports --json
uv run python main.py check-role can0 can1 --json
uv run python main.py gripper-cycle can0 --duration 15
```

## 打包

```bash
cd robots/piper/src/robots_piper
./build_pyinstaller.sh
```

产物默认在 `src/robots_piper/dist/robot_piper`。

## 关节顺序

Piper 的 actuator 顺序与节点实现绑定，固定为：

`joint1`、`joint2`、`joint3`、`joint4`、`joint5`、`joint6`、`gripper`

TaskRobot 中该机器人的 `actuator_order` / `joints` 需与此一致。
