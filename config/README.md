# 配置与标定

- **真机 / Dora 节点**：端口、`robot_id`、主从模式等，与 `robots/agilex_piper/src/robots_agilex_piper` 中 `config.example.yaml` 对齐；可复制到本目录并改名 `agilex_piper_node.yaml` 纳入版本管理（注意勿提交密钥）。生命周期位姿中的 `gripper` 是两指总开口米值，范围 `0..0.105`。
- **真机采集生命周期**：建议显式设置 `motion_speed_percent: 30`。Follower 连接固定回 `positions.initial` 并等待到位；关闭/断开固定回 `positions.reset`，到位后禁用；旧 `positions.rest` 不再接受。
- **VR 与同构**：见 `vr_calibration.yaml.example`，填写后改名为 `vr_calibration.yaml`（若含敏感标定，可用 CI 密钥注入，勿提交实测机密）。VR 映射输出的 `gripper` 同样必须是总开口米值。
