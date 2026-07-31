# Agilex Piper URDF

`piper_with_gripper.urdf` 是 Piper 单臂加夹爪模型，不包含相机、桌子或其他场景资产。mesh 使用本目录内的相对路径，因此无需 ROS package 索引即可由 Pinocchio 等工具直接加载。

## 来源

- 上游包：`piper_description` 1.0.0
- 上游文件：`urdf/piper_description_v100.urdf`
- 源文件 SHA-256：`f45e318ad58339945e5845f4e7a6db22dd334c1f8d4f1f1004285b6fd3be8529`
- 本地源文件时间：2026-03-04
- 随上游仓库提供的许可：MIT；完整文本见 `LICENSE.piper_ros-noetic`

可运行 `scripts/import_piper_urdf.py /path/to/piper_description` 重新导入基础模型，并同步生成单臂、双臂任务构型 URDF。脚本会校验源 URDF 的 SHA-256，避免静默导入不同版本的 URDF；mesh 与许可文件仍取自同一上游工作树。

## 关节

机械臂关节为 `joint1`～`joint6`；夹爪由两个 prismatic 关节 `joint7`、`joint8` 描述，其中 `joint8` 通过 URDF mimic 约束跟随 `joint7`（`joint8 = -joint7`），与 MJCF equality 约束一致。Forge 中的 `gripper` 是由这两个关节合成的两指总开口米值（`joint7 - joint8`，范围 `0..0.105 m`），并不是 URDF 关节名。

为保证 Pinocchio 与交付 MJCF 同构，导入脚本使用 MJCF body 的局部 `pos/quat` 对齐 `joint1`～`joint8` frame，并增加 `link6 -> tcp` 的固定末端 frame（局部 +Z `0.13503 m`）。
