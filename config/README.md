# 配置与标定

- **真机 / Dora 节点**：端口、`robot_id`、主从模式等，与 `robots/piper/src/robots_piper` 中 `config.example.yaml` 对齐；可复制到本目录并改名 `piper_node.yaml` 纳入版本管理（注意勿提交密钥）。
- **VR 与同构**：见 `vr_calibration.yaml.example`，填写后改名为 `vr_calibration.yaml`（若含敏感标定，可用 CI 密钥注入，勿提交实测机密）。
