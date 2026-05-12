# 02 — Dora 节点测试

本目录记录 Piper Dora 节点级验证入口。当前真机节点实现位于：

`robots/piper/src/robots_piper/`

可复用的现有 dataflow：

| 验证项 | 现有入口 |
|--------|----------|
| 仿真节点 + TaskRobot + test action | `examples/03_workflows/simulation/mujoco_piper/dataflow.test_action_source.yaml` |
| 真机录制链路 | `forge_runtime/examples/real_record/dataflow.yaml` |
| 真机回放 / 从臂驱动 | `forge_runtime/examples/real_playback/` |
| Piper 节点配置 | `config/piper_master.yaml.example`、`config/piper_slave.yaml.example` |

仿真节点级验证命令：

```bash
cd /home/donglinghan/chenruobing/robots/piper/examples/03_workflows/simulation/mujoco_piper
source /home/donglinghan/chenruobing/forge_runtime/.venv/bin/activate
dora build dataflow.test_action_source.yaml --uv
dora run dataflow.test_action_source.yaml --uv
```

真机 Dora 验证需要现场 CAN 与相机设备，当前不作为离线交付阻塞项。
