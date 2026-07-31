# Agilex Piper 真机录制 workflow

本 workflow 已从 `forge_runtime/examples/real_record/` 迁入本仓，并将 Agilex Piper 节点路径改为本仓源码：

`../../../src/robots_agilex_piper/main.py`

## 数据流

- `camera_hand`：采集真实摄像头图像，输出 `image`。
- `agilex_piper_master`：以 master 模式读取主臂状态。
- `agilex_piper_slave`：以 follower 模式接收 master_state 并驱动从臂。
- `task_robot`：聚合 Agilex Piper 状态与图像，输出 `proprio_state` / `action` / `image/hand`。
- `mcap_recorder`：录制 `proprio_state`、`action` 与 `image/hand`。
- `image_viewer`：显示 `image/hand`。

## 前置条件

1. 真机 Agilex Piper 已上电、急停释放、CAN 设备可用。
2. `agilex_piper_master.yaml` / `agilex_piper_slave.yaml` 的 `port` 已按现场修改。
3. 摄像头设备与 `camera.yaml` 一致。
4. `dataflow.yaml` 中的 `camera_hand` 依赖 `forge_runtime/target/release/forge-runtime-camera`。当前开发机未检测到该 release 产物；真机录制前需先在 `forge_runtime` 构建 camera 节点，或按现场 camera 节点实现替换该路径。
5. 新录制的 `gripper` 字段为两指总开口米值 `0..0.105`；不要与旧毫米制数据混用。

## 运行

```bash
cd robots/agilex_piper/examples/03_workflows/real_record
dora build dataflow.yaml --uv
dora run dataflow.yaml --uv
```

## 配置文件

| 文件 | 说明 |
|------|------|
| `dataflow.yaml` | 真机录制链路，Agilex Piper 节点已指向本仓 `src/robots_agilex_piper/main.py` |
| `task_robot.yaml` | Agilex Piper joint order 与 image 转发 |
| `agilex_piper_master.yaml` | master 模式示例 |
| `agilex_piper_slave.yaml` | follower 模式示例 |
| `camera.yaml` | 摄像头设备、分辨率、格式、帧率 |
