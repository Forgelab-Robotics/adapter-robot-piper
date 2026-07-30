"""Agilex Piper 机械臂硬件驱动，实现 forge_robot.BaseRobotDriver 协议。"""

from __future__ import annotations

import math
import time
from typing import Literal

from forge_common import get_logger
from forge_msgs import JointCommand, JointState
from forge_robot import (
    BaseRobotDriver,
    clip_and_validate_position_command,
    specs_by_name,
)
from piper_sdk import C_PiperInterface_V2

from robots_agilex_piper.config import (
    AGILEX_PIPER_ACTUATOR_ORDER,
    AGILEX_PIPER_ACTUATOR_SPECS,
    AGILEX_PIPER_DEFAULT_POSITIONS,
)

logger = get_logger(__name__)

_ACTUATOR_SPECS_DICT = specs_by_name(AGILEX_PIPER_ACTUATOR_SPECS)
_ARM_JOINT_NAMES = tuple(AGILEX_PIPER_ACTUATOR_ORDER[:6])


class AgilexPiperDriver(BaseRobotDriver):
    """
    Agilex Piper 机械臂硬件驱动。

    通过 CAN 与 piper-sdk 通信。主从：role="slave"（从站）连接后使能；
    role="master"（主站）仅连接不使能。单位：关节弧度、夹爪毫米。
    """

    @property
    def joint_order(self) -> list[str]:
        return list(AGILEX_PIPER_ACTUATOR_ORDER)

    ANGLE_SCALE = 1000.0
    GRIPPER_SCALE = 1000.0

    _LINKAGE_MASTER = 0xFA
    _LINKAGE_SLAVE = 0xFC

    def __init__(
        self,
        port: str = "can0",
        role: Literal["master", "slave"] = "slave",
        is_follower: bool | None = None,
        positions: dict[str, dict[str, float]] | None = None,
        auto_connect: bool = True,
    ):
        if role == "master":
            self.is_follower = False
        elif is_follower is not None:
            self.is_follower = is_follower
        else:
            self.is_follower = True
        self.role: Literal["master", "slave"] = (
            "slave" if self.is_follower else "master"
        )
        self.port = port
        self._positions = self._resolve_positions(positions)
        self.bus: C_PiperInterface_V2 | None = None
        # Leader 模式下 get_state 不是总有数据，全 0 视为无效，用缓存
        self._state_cache: JointState | None = None
        # Piper JointCtrl requires a complete six-axis frame. Sparse arm commands
        # update this cache; omitted joints retain their previous target.
        self._arm_target_cache: dict[str, float] | None = None

        if auto_connect:
            self.connect()

    @staticmethod
    def _resolve_positions(
        positions: dict[str, dict[str, float]] | None,
    ) -> dict[str, dict[str, float]]:
        resolved = {
            name: dict(position)
            for name, position in AGILEX_PIPER_DEFAULT_POSITIONS.items()
        }
        if positions:
            for name, position in positions.items():
                if name in resolved:
                    resolved[name].update(position)
        return resolved

    def connect(self) -> None:
        if self.bus is not None:
            logger.warning("Robot is already connected.")
            return

        self.bus = C_PiperInterface_V2(self.port)
        logger.info("Connecting to Agilex Piper robot at port %s...", self.port)
        self.bus.ConnectPort()

        linkage = self._LINKAGE_SLAVE if self.is_follower else self._LINKAGE_MASTER
        self.bus.MasterSlaveConfig(linkage, 0, 0, 0)

        if self.is_follower:
            self._connect_follower_mode()
            logger.info("Successfully connected and enabled the robot (slave).")
        else:
            self._connect_master_mode()
            logger.info("Successfully connected (master, not enabled).")

    # EnablePiper 等待超时时间（秒），超时后尝试 ResetPiper 再重试一次
    _ENABLE_AGILEX_PIPER_TIMEOUT_SEC = 2.0

    def _connect_follower_mode(self) -> None:
        logger.info("Enabling the robot in follower mode...")

        def wait_enable() -> bool:
            """等待 EnablePiper 成功，超时返回 False。"""
            deadline = time.monotonic() + self._ENABLE_AGILEX_PIPER_TIMEOUT_SEC
            while not self.bus.EnablePiper():
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.01)
            self.bus.MotionCtrl_2(0x01, 0x01, 30)
            return True

        if not wait_enable():
            logger.warning(
                "EnablePiper timed out after %.1fs, calling ResetPiper and retrying once...",
                self._ENABLE_AGILEX_PIPER_TIMEOUT_SEC,
            )
            self.bus.ResetPiper()
            time.sleep(0.5)
            if not wait_enable():
                raise RuntimeError(
                    "EnablePiper failed after ResetPiper retry. Check robot state and connection."
                )

        self.move_to_home_position()
        time.sleep(0.1)
        self.move_to_home_position()

    def move_to_home_position(self) -> None:
        """将关节与夹爪移动到配置的连接初始位。"""
        self._move_to_position("initial", self._positions["initial"], speed=30)

    def move_to_rest_position(self) -> None:
        """将关节与夹爪移动到配置的断开安全位。"""
        self._move_to_position("rest", self._positions["rest"], speed=30)

    def _move_to_position(
        self,
        name: str,
        target: dict[str, float],
        *,
        speed: int,
    ) -> None:
        """下发生命周期位姿，单位为关节弧度、夹爪毫米。"""
        if self.bus is None:
            raise RuntimeError("Robot is not connected. Call connect() first.")

        command = JointCommand(
            name=self.joint_order,
            mode="position",
            position=[target.get(actuator, 0.0) for actuator in self.joint_order],
            velocity=[],
            effort=[],
            kp=[],
            kd=[],
        )
        safe_command = clip_and_validate_position_command(command, _ACTUATOR_SPECS_DICT)
        action_dict = dict(
            zip(safe_command.name, safe_command.position, strict=False)
        )

        j1 = int(math.degrees(action_dict.get("joint1", 0.0)) * self.ANGLE_SCALE)
        j2 = int(math.degrees(action_dict.get("joint2", 0.0)) * self.ANGLE_SCALE)
        j3 = int(math.degrees(action_dict.get("joint3", 0.0)) * self.ANGLE_SCALE)
        j4 = int(math.degrees(action_dict.get("joint4", 0.0)) * self.ANGLE_SCALE)
        j5 = int(math.degrees(action_dict.get("joint5", 0.0)) * self.ANGLE_SCALE)
        j6 = int(math.degrees(action_dict.get("joint6", 0.0)) * self.ANGLE_SCALE)
        gripper = int(action_dict.get("gripper", 0.0) * self.GRIPPER_SCALE)

        logger.info("Moving robot to %s position: %s", name, action_dict)
        self.bus.MotionCtrl_2(0x01, 0x01, speed)
        self.bus.JointCtrl(j1, j2, j3, j4, j5, j6)
        self.bus.GripperCtrl(abs(gripper), 1000, 0x01, 0)
        self._arm_target_cache = {
            joint_name: action_dict[joint_name] for joint_name in _ARM_JOINT_NAMES
        }

    def _connect_master_mode(self) -> None:
        logger.info("Robot configured in master mode.")

    def disconnect(self) -> None:
        if self.bus is None:
            logger.warning("Robot is not connected.")
            return

        if self.is_follower:
            logger.info("Safety sequence: Moving to rest position before disable...")
            try:
                self.move_to_rest_position()
            except Exception as e:
                logger.error("Failed to move to rest position: %s", e)

        logger.info("Disabling and disconnecting from the robot...")
        self.bus.DisconnectPort()
        self.bus = None
        self._arm_target_cache = None
        logger.info("Disconnected from the robot.")

    def reset(self) -> None:
        if self.bus is None:
            raise RuntimeError("Robot is not connected. Call connect() first.")
        logger.info("Starting homing sequence...")
        time.sleep(3)
        self.bus.MotionCtrl_1(0x02, 0, 0)
        self._arm_target_cache = None
        logger.info("Homing command sent.")
        time.sleep(1)

    def get_state(self) -> JointState:
        """从硬件读取状态，转为 JointState（弧度/毫米）。Leader 模式下全 0 视为无效，返回缓存。"""
        if self.bus is None:
            raise RuntimeError("Robot is not connected. Call connect() first.")

        if self.is_follower:
            joints = self.bus.GetArmJointMsgs().joint_state
            gripper = self.bus.GetArmGripperMsgs().gripper_state
        else:
            joints = self.bus.GetArmJointCtrl().joint_ctrl
            gripper = self.bus.GetArmGripperCtrl().gripper_ctrl
            # Leader 下全 0 表示无有效数据，用缓存
            if (
                joints.joint_1 == 0
                and joints.joint_2 == 0
                and joints.joint_3 == 0
                and joints.joint_4 == 0
                and joints.joint_5 == 0
                and joints.joint_6 == 0
                and gripper.grippers_angle == 0
            ):
                if self._state_cache is not None:
                    return self._state_cache
                # 无缓存时仍返回全 0 的 state，避免调用方报错

        state = JointState(
            name=self.joint_order,
            position=[
                math.radians(joints.joint_1 / self.ANGLE_SCALE),
                math.radians(joints.joint_2 / self.ANGLE_SCALE),
                math.radians(joints.joint_3 / self.ANGLE_SCALE),
                math.radians(joints.joint_4 / self.ANGLE_SCALE),
                math.radians(joints.joint_5 / self.ANGLE_SCALE),
                math.radians(joints.joint_6 / self.ANGLE_SCALE),
                gripper.grippers_angle / self.GRIPPER_SCALE,
            ],
        )
        if not self.is_follower:
            self._state_cache = state
        return state

    def set_command(self, command: JointCommand) -> None:
        """Apply a sparse position command without changing omitted actuators."""
        if self.bus is None:
            raise RuntimeError("Robot is not connected. Call connect() first.")

        if getattr(command, "mode", "position") != "position":
            raise ValueError("Agilex Piper requires JointCommand mode='position'")
        safe_command = clip_and_validate_position_command(command, _ACTUATOR_SPECS_DICT)
        if not safe_command.position:
            raise ValueError("Agilex Piper requires a position JointCommand")
        action_dict = dict(
            zip(safe_command.name, safe_command.position, strict=True)
        )

        arm_updates = {
            name: action_dict[name]
            for name in _ARM_JOINT_NAMES
            if name in action_dict
        }
        if arm_updates:
            if len(arm_updates) == len(_ARM_JOINT_NAMES):
                arm_targets = dict(arm_updates)
            else:
                if self._arm_target_cache is None:
                    state = self.get_state()
                    state_by_name = dict(
                        zip(state.name, state.position, strict=True)
                    )
                    self._arm_target_cache = {
                        name: state_by_name[name] for name in _ARM_JOINT_NAMES
                    }
                arm_targets = dict(self._arm_target_cache)
                arm_targets.update(arm_updates)

            joint_values = [
                int(math.degrees(arm_targets[name]) * self.ANGLE_SCALE)
                for name in _ARM_JOINT_NAMES
            ]
            self.bus.MotionCtrl_2(0x01, 0x01, 100, 0x00)
            self.bus.JointCtrl(*joint_values)
            self._arm_target_cache = arm_targets

        if "gripper" in action_dict:
            gripper = int(action_dict["gripper"] * self.GRIPPER_SCALE)
            self.bus.GripperCtrl(abs(gripper), 1000, 0x01, 0)
