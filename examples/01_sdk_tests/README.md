# 01 — SDK / 底层最小测试

本目录记录不依赖 Forge / Dora 的 Piper 底层验证入口。当前可复用工作区已有资源，不在本仓重复复制 SDK：

| 验证项 | 现有入口 |
|--------|----------|
| Piper SDK demo | `piper_sdk/piper_sdk/demo/V2/` |
| 读状态 | `piper_sdk/piper_sdk/demo/V2/piper_read_status.py` |
| 单关节 / 回零 | `piper_sdk/piper_sdk/demo/V2/piper_ctrl_joint.py`、`piper_ctrl_go_zero.py` |
| 夹爪 | `robots/piper/src/robots_piper/main.py gripper-cycle <can>` |
| CAN 端口发现 / 激活 / 主从检测 | `robots/piper/src/robots_piper/main.py list-ports`、`activate-ports`、`check-role` |

示例：

```bash
cd /home/donglinghan/chenruobing/robots/piper/src/robots_piper
uv run python main.py list-ports --json
uv run python main.py check-role can0 can1 --json
uv run python main.py gripper-cycle can0 --duration 15
```

上述测试依赖真机上电、急停释放、CAN 设备已激活；实机结果应记录到 MR 或 `config/` 中，不提交现场私有端口/标定密钥。
