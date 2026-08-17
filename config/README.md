# 配置与标定

真机 follower 的权威交付示例为
`config/agilex_piper_slave.yaml.example`。复制后按现场设备修改，不要直接覆盖
示例文件：

```bash
cp config/agilex_piper_slave.yaml.example config/agilex_piper_node.yaml
uv run robots-agilex-piper run --config config/agilex_piper_node.yaml
```

也可将 `AGILEX_PIPER_NODE_CONFIG` 设置为配置文件路径；显式 `--config`
优先。Dataflow 应通过节点 `args: --config <path>` 传入。配置只在节点启动时
读取，修改后必须重启，当前不支持运行时热更新。

## 节点字段

- `port`：SocketCAN 设备，例如 `can0`。
- `is_follower`：`true` 接收动作并驱动机械臂；`false` 只读主臂状态。
- `motion_speed_percent`：硬件运动速度百分比，范围 `1..100`；首次真机测试建议
  使用 `30` 或更低。
- `positions.initial`：Follower 连接后移动并等待到位的生命周期位姿。
- `positions.reset`：Follower 关闭或断开前移动并等待到位的生命周期位姿。
- `debug`：启用调试日志。

生命周期位姿中的 `joint1`～`joint6` 使用弧度，`gripper` 是两指总开口米值，
范围 `0..0.105`。未配置的关节使用内置默认值。Follower 到达 reset 后保持使能
并断开 CAN，不主动调用 `DisablePiper()`；旧 `positions.rest` 不再接受。

## 其他示例

- `config/config.example.yaml`：字段完整的通用节点示例。
- `config/agilex_piper_master.yaml.example`：只读 master 示例。
- `config/vr_calibration.yaml.example`：VR 标定示例；不要提交现场敏感标定。
