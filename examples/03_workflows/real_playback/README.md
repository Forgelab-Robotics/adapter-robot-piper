# Agilex Piper 真机回放 / 从臂驱动 workflow

本 workflow 使用本仓 Agilex Piper 节点源码：

`../../../src/robots_agilex_piper/main.py`

## 数据流

- `mcap_playback`：读取 MCAP 中的 action。
- `task_robot`：将 action 转为 `robot_0/action`。
- `agilex_piper_slave`：订阅 `robot_0/action` 并驱动真机 Agilex Piper。
- `control_gateway`：提供 playback 控制入口。

## 前置条件

1. 真机 Agilex Piper 已上电、急停释放、CAN 设备可用。
2. `agilex_piper_slave.yaml` 的 `port` 已按现场修改。
3. `dataflow.yaml` 中 `--mcap-path ./logs/recording.mcap` 需要替换为实际回放文件，或将文件放到该路径。
4. 回放涉及真机运动，必须先确认急停、限位、速度和操作空间。
5. 仅回放 `gripper` 为两指总开口米值 `0..0.105` 的新数据；旧毫米制 MCAP 必须先将该字段除以 `1000`，否则驱动会拒绝命令。
6. 设置 `FORGE_RUNTIME_ROOT`，使 dataflow 可以定位 playback、TaskRobot
   和 control gateway 节点。

## 运行

```bash
cd robots/agilex_piper/examples/03_workflows/real_playback
export FORGE_RUNTIME_ROOT=/absolute/path/to/forge-runtime
dora build dataflow.yaml --uv
dora run dataflow.yaml --uv
```
