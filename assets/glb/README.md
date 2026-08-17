# GLB / 可视化

本目录放 **面向 Web / 可视化 / 资源分发** 的产物，与 **`assets/mjcf/`**（MuJoCo 仿真主数据：`*.xml` + 原始 mesh）分开。

## 当前文件

| 文件 / 目录 | 说明 |
|-------------|------|
| `piper.glb` | 由 `../mjcf/piper_mujoco/PIPER.xml` 导出并压缩 |
| `piper_upstream/` | 上游自带 GLB，保留用于对照与追溯 |

GLB 是自包含二进制，不依赖本目录外部 mesh。公开包不包含转换过程中产生的
归一化 MJCF 和中间 mesh。

## 来源与许可

`piper.glb` 由 `../mjcf/piper_mujoco/PIPER.xml` 转换得到，
`piper_upstream/` 保留上游对照资产。两者均源自
[MuJoCo Menagerie — AgileX Piper](https://github.com/google-deepmind/mujoco_menagerie/tree/main/agilex_piper)
的 MIT 资产，保留 `Copyright (c) 2024 RosenYin`。完整许可文本见
`../mjcf/piper_mujoco/LICENSE`，仓库级汇总见 `../../THIRD_PARTY_NOTICES.md`。

本开源包不附带转换流水线；交付以本目录已落盘、自包含的 GLB 文件为准。
