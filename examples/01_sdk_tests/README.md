# 01 — SDK / 底层最小测试

本目录记录不依赖 Forge / Dora workflow 的 Agilex Piper 底层验证入口。
`piper-sdk==0.6.2` 由 PyPI 安装，本仓不复制其 demo：

| 验证项 | 现有入口 |
|--------|----------|
| 上游 SDK demo | [AgileX `piper_sdk` demos](https://github.com/agilexrobotics/piper_sdk/tree/master/piper_sdk/demo/V2) |
| 状态监视 | `uv run robots-agilex-piper watch-state <can>` |
| 夹爪 | `uv run robots-agilex-piper test <can>` |
| CAN 设备发现 / 激活 / 主从检测 | `uv run robots-agilex-piper list-devices`、`activate-devices`、`check-role` |

示例：

```bash
uv run robots-agilex-piper list-devices --json
uv run robots-agilex-piper check-role can0 can1 --json
uv run robots-agilex-piper test can0 --duration 15
```

上述测试依赖真机上电、急停释放、CAN 设备已激活；脱敏后的实机结果可记录到
本地 `validation_output/`，不要提交现场端口、标定、录制或其他私有信息。

单位边界：Forge `gripper` 为两指总开口 `0..0.105 m`，SDK `GripperCtrl` / `grippers_angle` 为 `0..105000`（每单位 `1e-6 m`）。底层示例若直接调用 SDK，应传 SDK 整数，不要传 Forge 米值。
