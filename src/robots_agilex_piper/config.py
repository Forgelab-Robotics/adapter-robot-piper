"""Agilex Piper 节点配置加载与校验。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Any

import yaml
from forge_robot import ActuatorSpec

from robots_agilex_piper.codec import (
    GRIPPER_MAX_OPENING_METERS,
    GRIPPER_MIN_OPENING_METERS,
    validate_gripper_opening_meters,
)

# Keep the six arm limits aligned with piper-sdk's C_PiperParamManager defaults.
AGILEX_PIPER_ACTUATOR_SPECS = (
    ActuatorSpec(
        name="joint1",
        kind="revolute",
        min_position=-2.6179,
        max_position=2.6179,
    ),
    ActuatorSpec(
        name="joint2",
        kind="revolute",
        min_position=0.0,
        max_position=3.140,
    ),
    ActuatorSpec(
        name="joint3",
        kind="revolute",
        min_position=-2.967,
        max_position=0.0,
    ),
    ActuatorSpec(
        name="joint4",
        kind="revolute",
        min_position=-1.745,
        max_position=1.745,
    ),
    ActuatorSpec(
        name="joint5",
        kind="revolute",
        min_position=-1.22,
        max_position=1.22,
    ),
    ActuatorSpec(
        name="joint6",
        kind="revolute",
        min_position=-2.09439,
        max_position=2.09439,
    ),
    ActuatorSpec(
        name="gripper",
        kind="prismatic",
        position_unit="meters",
        min_position=GRIPPER_MIN_OPENING_METERS,
        max_position=GRIPPER_MAX_OPENING_METERS,
    ),
)

# 与 driver 中关节/夹爪顺序一致，固定不可配置
AGILEX_PIPER_ACTUATOR_ORDER = [spec.name for spec in AGILEX_PIPER_ACTUATOR_SPECS]

_SAFETY_CONFIG_KEYS = ("motion_speed_percent",)
_REMOVED_BEHAVIOR_KEYS = ("startup_behavior", "shutdown_behavior")


AGILEX_PIPER_DEFAULT_POSITIONS: dict[str, dict[str, float]] = {
    "initial": {name: 0.0 for name in AGILEX_PIPER_ACTUATOR_ORDER},
    "reset": {
        "joint1": 0.0,
        "joint2": 0.0,
        "joint3": 0.0,
        "joint4": 0.0,
        "joint5": 0.3,
        "joint6": 0.0,
        "gripper": 0.0,
    },
}


def _parse_positions(data: Any) -> dict[str, dict[str, float]] | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("positions 必须是字典。")  # noqa: TRY004

    allowed_position_names = set(AGILEX_PIPER_DEFAULT_POSITIONS)
    allowed_actuator_names = set(AGILEX_PIPER_ACTUATOR_ORDER)
    parsed: dict[str, dict[str, float]] = {}

    for position_name, position in data.items():
        raw_name = str(position_name)
        if raw_name not in allowed_position_names:
            raise ValueError(
                f"未知 positions 名称: {raw_name}，可用值: "
                f"{sorted(allowed_position_names)}"
            )
        name = raw_name
        if not isinstance(position, dict):
            raise ValueError(f"positions.{raw_name} 必须是字典。")  # noqa: TRY004

        parsed_position: dict[str, float] = {}
        for actuator_name, value in position.items():
            key = str(actuator_name)
            if key not in allowed_actuator_names:
                raise ValueError(
                    f"未知 actuator 名称: {key}，可用值: {AGILEX_PIPER_ACTUATOR_ORDER}"
                )
            parsed_value = float(value)
            if key == "gripper":
                parsed_value = validate_gripper_opening_meters(parsed_value)
            parsed_position[key] = parsed_value
        parsed[name] = parsed_position

    return parsed


@dataclass
class AgilexPiperNodeConfig:
    """Agilex Piper 节点配置。"""

    """与 task_robot 中 robots[].id 对应，用于 dataflow 中 input/output 的语义一致。"""
    port: str
    is_follower: bool
    debug: bool = False
    positions: dict[str, dict[str, float]] | None = None
    motion_speed_percent: int = 100

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgilexPiperNodeConfig:
        """从字典解析配置。"""
        known_keys = {
            "port",
            "is_follower",
            "debug",
            "positions",
            *_SAFETY_CONFIG_KEYS,
        }
        for key in set(data) - known_keys:
            removed_matches = get_close_matches(
                str(key),
                _REMOVED_BEHAVIOR_KEYS,
                n=1,
                cutoff=0.6,
            )
            if removed_matches:
                raise ValueError(
                    f"配置项 {key!r} 已不再支持；Follower 生命周期固定为 "
                    "连接回 initial、关闭/断开回 reset"
                )
            speed_matches = get_close_matches(
                str(key),
                _SAFETY_CONFIG_KEYS,
                n=1,
                cutoff=0.6,
            )
            if speed_matches:
                raise ValueError(
                    f"未知配置项 {key!r}，是否想写 {speed_matches[0]!r}？"
                )

        port = data.get("port", "can0")
        is_follower = data.get("is_follower", True)
        debug = data.get("debug", False)
        motion_speed_percent = data.get("motion_speed_percent", 100)
        if (
            isinstance(motion_speed_percent, bool)
            or not isinstance(motion_speed_percent, int)
            or not 1 <= motion_speed_percent <= 100
        ):
            raise ValueError(
                "motion_speed_percent 必须是 1..100 的整数，"
                f"当前为: {motion_speed_percent!r}"
            )
        positions = _parse_positions(data.get("positions"))
        return cls(
            port=port,
            is_follower=is_follower,
            debug=debug,
            positions=positions,
            motion_speed_percent=motion_speed_percent,
        )

    def resolved_position(self, name: str) -> dict[str, float]:
        """返回完整生命周期位姿，未配置的关节使用默认值。"""
        if name not in AGILEX_PIPER_DEFAULT_POSITIONS:
            raise ValueError(
                f"未知 positions 名称: {name}，"
                f"可用值: {sorted(AGILEX_PIPER_DEFAULT_POSITIONS)}"
            )
        position = dict(AGILEX_PIPER_DEFAULT_POSITIONS[name])
        if self.positions and name in self.positions:
            position.update(self.positions[name])
        return position

    @classmethod
    def from_yaml_path(cls, path: str | Path) -> AgilexPiperNodeConfig:
        """从 YAML 文件加载配置。"""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"配置文件不存在: {p}")
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            raise ValueError(f"配置文件为空: {p}")
        return cls.from_dict(data)


def load_config(
    config_path: str | Path | None = None,
    dataflow_config: dict[str, Any] | None = None,
) -> AgilexPiperNodeConfig:
    """
    加载配置，支持多种来源（优先级从高到低）：
    1. dataflow_config 中的 config_path 或内联 config
    2. config_path 参数
    3. 环境变量 AGILEX_PIPER_NODE_CONFIG

    Args:
        config_path: 可选，YAML 配置文件路径
        dataflow_config: 可选，dora 节点 config 字段

    Returns:
        AgilexPiperNodeConfig
    """
    data: dict[str, Any] | None = None

    if dataflow_config:
        if "config" in dataflow_config:
            data = dataflow_config["config"]
        elif "config_path" in dataflow_config:
            return AgilexPiperNodeConfig.from_yaml_path(dataflow_config["config_path"])

    path = config_path
    if path is None and data is None:
        path = os.environ.get("AGILEX_PIPER_NODE_CONFIG")

    if path:
        return AgilexPiperNodeConfig.from_yaml_path(path)

    if data:
        return AgilexPiperNodeConfig.from_dict(data)

    raise ValueError(
        "未找到配置。请设置 AGILEX_PIPER_NODE_CONFIG 环境变量、"
        "或通过 --config 指定配置文件、或使用 dataflow config。"
    )
