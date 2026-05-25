# Forge 机器人节点源码（`src/`）

本仓已迁入 Piper 真机 / Dora 节点源码：

`src/robots_piper/`

来源为工作区内 `forge_robots/packages/piper/`，主要文件包括 `main.py`、`driver.py`、`config.py`、`device_tools.py`，打包 spec 与脚本位于仓库根目录和 `scripts/`。

本仓 `examples/03_workflows/real_record/`、`real_playback/`、`sim_record/` 中的 Piper 节点路径均指向该本地源码。若后续更新上游实现，请同步迁入本目录并在提交 / MR 中记录来源 commit。
