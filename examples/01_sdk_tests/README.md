# 01 — SDK / 底层最小测试

本目录记录不依赖 Forge / Dora 的 Agilex Piper 底层验证入口。当前可复用工作区已有资源，不在本仓重复复制 SDK：

| 验证项 | 现有入口 |
|--------|----------|
| Agilex Piper SDK demo | `piper_sdk/piper_sdk/demo/V2/` |
| 读状态 | `piper_sdk/piper_sdk/demo/V2/piper_read_status.py` |
| 单关节 / 回零 | `piper_sdk/piper_sdk/demo/V2/piper_ctrl_joint.py`、`piper_ctrl_go_zero.py` |
| 夹爪 | `uv run robots-agilex-piper test <can>` |
| CAN 设备发现 / 激活 / 主从检测 | `uv run robots-agilex-piper list-devices`、`activate-devices`、`check-role` |

示例：

```bash
cd robots/agilex_piper
uv run robots-agilex-piper list-devices --json
uv run robots-agilex-piper check-role can0 can1 --json
uv run robots-agilex-piper test can0 --duration 15
```

上述测试依赖真机上电、急停释放、CAN 设备已激活；实机结果应记录到 MR 或 `config/` 中，不提交现场私有端口/标定密钥。

单位边界：Forge `gripper` 为两指总开口 `0..0.105 m`，SDK `GripperCtrl` / `grippers_angle` 为 `0..105000`（每单位 `1e-6 m`）。底层示例若直接调用 SDK，应传 SDK 整数，不要传 Forge 米值。
