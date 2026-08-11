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

from robots_agilex_piper.codec import (
    GRIPPER_SDK_UNITS_PER_METER,
    gripper_meters_to_sdk,
    gripper_sdk_to_meters,
)
from robots_agilex_piper.config import (
    AGILEX_PIPER_ACTUATOR_ORDER,
    AGILEX_PIPER_ACTUATOR_SPECS,
    AGILEX_PIPER_DEFAULT_POSITIONS,
)

logger = get_logger(__name__)

_ACTUATOR_SPECS_DICT = specs_by_name(AGILEX_PIPER_ACTUATOR_SPECS)
_ARM_JOINT_NAMES = tuple(AGILEX_PIPER_ACTUATOR_ORDER[:6])
_POSITION_FEEDBACK_STREAMS = (
    "ArmJoint_12",
    "ArmJoint_34",
    "ArmJoint_56",
    "ArmGripper",
)
_ENABLE_FEEDBACK_STREAMS = tuple(
    f"ArmMotorDriverInfoLowSpd_{index}" for index in range(1, 7)
)
_ENABLE_FEEDBACK_CAN_IDS = tuple(range(0x261, 0x267))


def _clip_position_command(command: JointCommand) -> JointCommand:
    if len(command.name) != len(command.position):
        raise ValueError("JointCommand name and position lengths must match")
    for name, position in zip(command.name, command.position, strict=True):
        if not math.isfinite(position):
            raise ValueError(
                f"Position command for {name} must be finite, got {position!r}"
            )

    safe_command = clip_and_validate_position_command(command, _ACTUATOR_SPECS_DICT)
    requested_positions = dict(zip(command.name, command.position, strict=False))
    safe_positions = dict(
        zip(safe_command.name, safe_command.position, strict=False)
    )

    for name, safe_position in safe_positions.items():
        requested_position = requested_positions.get(name)
        if requested_position == safe_position:
            continue
        spec = _ACTUATOR_SPECS_DICT[name]
        logger.warning(
            "Position command for %s is outside [%s, %s] %s; clipping %s to %s.",
            name,
            spec.min_position,
            spec.max_position,
            spec.position_unit,
            requested_position,
            safe_position,
        )

    return safe_command


class AgilexPiperDriver(BaseRobotDriver):
    """
    Agilex Piper 机械臂硬件驱动。

    通过 CAN 与 piper-sdk 通信。主从：role="slave"（从站）连接后使能；
    role="master"（主站）仅连接不使能。单位：关节弧度、夹爪两指总开口米。
    """

    @property
    def joint_order(self) -> list[str]:
        return list(AGILEX_PIPER_ACTUATOR_ORDER)

    ANGLE_SCALE = 1000.0
    GRIPPER_SCALE = GRIPPER_SDK_UNITS_PER_METER

    _LINKAGE_MASTER = 0xFA
    _LINKAGE_SLAVE = 0xFC

    def __init__(
        self,
        port: str = "can0",
        role: Literal["master", "slave"] = "slave",
        is_follower: bool | None = None,
        positions: dict[str, dict[str, float]] | None = None,
        auto_connect: bool = True,
        *,
        motion_speed_percent: int = 100,
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
        if (
            isinstance(motion_speed_percent, bool)
            or not isinstance(motion_speed_percent, int)
            or not 1 <= motion_speed_percent <= 100
        ):
            raise ValueError("motion_speed_percent must be an integer from 1 to 100")
        self.motion_speed_percent = motion_speed_percent
        self._positions = self._resolve_positions(positions)
        self._validate_lifecycle_positions()
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
            allowed_actuators = set(AGILEX_PIPER_ACTUATOR_ORDER)
            for name, position in positions.items():
                if name not in resolved:
                    raise ValueError(f"Unknown lifecycle position: {name}")
                unknown_actuators = sorted(set(position) - allowed_actuators)
                if unknown_actuators:
                    raise ValueError(
                        f"Unknown actuators in lifecycle position {name}: "
                        f"{unknown_actuators}"
                    )
                resolved[name].update(position)
        return resolved

    def _prepare_lifecycle_position(
        self,
        target: dict[str, float],
    ) -> tuple[dict[str, float], tuple[int, ...], int]:
        # Validate the requested opening before the generic actuator validator can
        # clip it; accepting legacy millimeter values here would be unsafe.
        gripper_meters_to_sdk(target.get("gripper", 0.0))
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
        action_dict = dict(zip(safe_command.name, safe_command.position, strict=True))
        joint_values = tuple(
            int(math.degrees(action_dict[name]) * self.ANGLE_SCALE)
            for name in _ARM_JOINT_NAMES
        )
        gripper = gripper_meters_to_sdk(action_dict["gripper"])
        return action_dict, joint_values, gripper

    def _validate_lifecycle_positions(self) -> None:
        for name in AGILEX_PIPER_DEFAULT_POSITIONS:
            self._prepare_lifecycle_position(self._positions[name])

    @staticmethod
    def _feedback_generation(
        bus: C_PiperInterface_V2,
        stream_names: tuple[str, ...],
    ) -> tuple[int, ...]:
        """Snapshot per-CAN-stream frame counters from locked piper-sdk 0.6.2."""
        counter = getattr(bus, "_C_PiperInterface_V2__fps_counter", None)
        if counter is None:
            raise RuntimeError(
                "piper-sdk feedback counter is unavailable; "
                "cannot verify fresh hardware feedback"
            )

        try:
            with counter.lock:
                missing = [
                    name for name in stream_names if name not in counter.fps_data
                ]
                if missing:
                    raise RuntimeError(
                        f"Missing piper-sdk feedback counters: {missing}"
                    )
                return tuple(int(counter.fps_data[name]) for name in stream_names)
        except AttributeError as error:
            raise RuntimeError(
                "piper-sdk feedback counter has an unsupported structure; "
                "cannot verify fresh hardware feedback"
            ) from error

    def connect(self) -> None:
        if self.bus is not None:
            logger.warning("Robot is already connected.")
            return

        self._validate_lifecycle_positions()
        bus = C_PiperInterface_V2(self.port)
        self.bus = bus
        should_disable_on_failure = False
        try:
            logger.info("Connecting to Agilex Piper robot at port %s...", self.port)
            bus.ConnectPort()

            linkage = self._LINKAGE_SLAVE if self.is_follower else self._LINKAGE_MASTER
            bus.MasterSlaveConfig(linkage, 0, 0, 0)

            if self.is_follower:
                should_disable_on_failure = True
                self._connect_follower_mode()
                logger.info("Successfully connected and enabled the robot (slave).")
            else:
                self._connect_master_mode()
                logger.info("Successfully connected (master, not enabled).")
        except BaseException:
            self._rollback_failed_connect(
                bus,
                disable=should_disable_on_failure,
            )
            raise

    def _rollback_failed_connect(
        self,
        bus: C_PiperInterface_V2,
        *,
        disable: bool,
    ) -> None:
        if disable:
            try:
                self._disable_follower_and_wait(bus)
            except BaseException as error:  # noqa: BLE001 - preserve setup error.
                logger.error(
                    "Failed to verify disabled robot during connect rollback: %s",
                    error,
                )

        try:
            bus.DisconnectPort()
        except BaseException as error:  # noqa: BLE001 - preserve setup error.
            logger.error(
                "Failed to disconnect robot during connect rollback: %s", error
            )
        finally:
            self.bus = None
            self._arm_target_cache = None

    # EnablePiper 等待超时时间（秒），超时后尝试 ResetPiper 再重试一次
    _ENABLE_AGILEX_PIPER_TIMEOUT_SEC = 2.0
    _DISABLE_AGILEX_PIPER_TIMEOUT_SEC = 2.0
    _LIFECYCLE_POSITION_TIMEOUT_SEC = 10.0
    _ARM_POSITION_TOLERANCE_RAD = 0.05
    _GRIPPER_POSITION_TOLERANCE_M = 0.005

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
        if self.bus is None:
            raise RuntimeError("Robot disconnected during initial positioning")
        initial_target = self.move_to_home_position()
        feedback_generation = self._feedback_generation(
            self.bus,
            _POSITION_FEEDBACK_STREAMS,
        )
        if not self._wait_for_position(
            initial_target,
            after=feedback_generation,
        ):
            raise RuntimeError(
                "Timed out waiting "
                f"{self._LIFECYCLE_POSITION_TIMEOUT_SEC:.1f}s for initial position"
            )

    def move_to_home_position(self) -> dict[str, float]:
        """下发配置的连接初始位，并返回实际裁剪后的目标。"""
        return self._move_to_position(
            "initial",
            self._positions["initial"],
            speed=30,
        )

    def move_to_reset_position(self) -> None:
        """将关节与夹爪移动到配置的关闭/断开复位位。"""
        if self.bus is None:
            raise RuntimeError("Robot is not connected. Call connect() first.")
        target = self._move_to_position("reset", self._positions["reset"], speed=30)
        feedback_generation = self._feedback_generation(
            self.bus,
            _POSITION_FEEDBACK_STREAMS,
        )
        if not self._wait_for_position(
            target,
            after=feedback_generation,
        ):
            raise RuntimeError(
                "Timed out waiting "
                f"{self._LIFECYCLE_POSITION_TIMEOUT_SEC:.1f}s for reset position"
            )

    def _wait_for_position(
        self,
        target: dict[str, float],
        *,
        after: tuple[int, ...],
    ) -> bool:
        if self.bus is None:
            raise RuntimeError("Robot is not connected. Call connect() first.")
        deadline = time.monotonic() + self._LIFECYCLE_POSITION_TIMEOUT_SEC
        while True:
            generation = self._feedback_generation(
                self.bus,
                _POSITION_FEEDBACK_STREAMS,
            )
            feedback_is_fresh = all(
                current > baseline
                for current, baseline in zip(generation, after, strict=True)
            )
            if feedback_is_fresh:
                state = self.get_state()
                positions = dict(zip(state.name, state.position, strict=True))
                reached = all(
                    abs(positions[name] - value)
                    <= (
                        self._GRIPPER_POSITION_TOLERANCE_M
                        if name == "gripper"
                        else self._ARM_POSITION_TOLERANCE_RAD
                    )
                    for name, value in target.items()
                )
                if reached:
                    return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)

    def _move_to_position(
        self,
        name: str,
        target: dict[str, float],
        *,
        speed: int,
    ) -> dict[str, float]:
        """下发生命周期位姿并返回实际裁剪后的目标。"""
        if self.bus is None:
            raise RuntimeError("Robot is not connected. Call connect() first.")

        action_dict, joint_values, gripper = self._prepare_lifecycle_position(target)

        logger.info("Moving robot to %s position: %s", name, action_dict)
        self.bus.MotionCtrl_2(0x01, 0x01, speed)
        self.bus.JointCtrl(*joint_values)
        self.bus.GripperCtrl(gripper, 1000, 0x01, 0)
        self._arm_target_cache = {
            joint_name: action_dict[joint_name] for joint_name in _ARM_JOINT_NAMES
        }
        return action_dict

    def _connect_master_mode(self) -> None:
        logger.info("Robot configured in master mode.")

    def disconnect(self) -> None:
        if self.bus is None:
            logger.warning("Robot is not connected.")
            return

        bus = self.bus
        pending_error: BaseException | None = None

        if self.is_follower:
            logger.info("Safety sequence: Moving to reset position before disconnect...")
            try:
                self.move_to_reset_position()
            except BaseException as error:  # Cleanup continues, then failure is raised.
                pending_error = error

        logger.info("Disconnecting from the robot without disabling it...")
        try:
            bus.DisconnectPort()
        except BaseException as error:
            if pending_error is None:
                pending_error = error
            else:
                logger.error("CAN disconnect failed during cleanup: %s", error)
        finally:
            self.bus = None
            self._arm_target_cache = None

        if pending_error is not None:
            raise pending_error
        logger.info("Disconnected from the robot.")

    def _disable_follower_and_wait(self, bus: C_PiperInterface_V2) -> None:
        # piper-sdk 0.6.2 returns the pre-command state from DisablePiper and
        # initializes missing low-speed feedback as disabled. Require one fresh
        # frame from every motor stream after the command before accepting it.
        bus.DisablePiper()
        feedback_generation = self._feedback_generation(
            bus,
            _ENABLE_FEEDBACK_STREAMS,
        )
        deadline = time.monotonic() + self._DISABLE_AGILEX_PIPER_TIMEOUT_SEC
        while True:
            feedback = bus.GetArmLowSpdInfoMsgs()
            generation = self._feedback_generation(
                bus,
                _ENABLE_FEEDBACK_STREAMS,
            )
            feedback_is_fresh = all(
                current > baseline
                for current, baseline in zip(
                    generation,
                    feedback_generation,
                    strict=True,
                )
            )
            if feedback_is_fresh:
                motors = tuple(
                    getattr(feedback, f"motor_{index}") for index in range(1, 7)
                )
                can_ids = tuple(motor.can_id for motor in motors)
                enabled = tuple(
                    motor.foc_status.driver_enable_status for motor in motors
                )
                if can_ids == _ENABLE_FEEDBACK_CAN_IDS and not any(enabled):
                    return
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "Timed out waiting for fresh disabled feedback from all "
                    "Piper arm motors"
                )
            time.sleep(0.01)

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
        """从硬件读取状态，转为 JointState（弧度/夹爪总开口米）。Leader 全 0 时返回缓存。"""
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
                and self._state_cache is not None
            ):
                return self._state_cache
            # 全 0 且无缓存时仍返回全 0 的 state，避免调用方报错

        state = JointState(
            name=self.joint_order,
            position=[
                math.radians(joints.joint_1 / self.ANGLE_SCALE),
                math.radians(joints.joint_2 / self.ANGLE_SCALE),
                math.radians(joints.joint_3 / self.ANGLE_SCALE),
                math.radians(joints.joint_4 / self.ANGLE_SCALE),
                math.radians(joints.joint_5 / self.ANGLE_SCALE),
                math.radians(joints.joint_6 / self.ANGLE_SCALE),
                gripper_sdk_to_meters(gripper.grippers_angle),
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
        safe_command = _clip_position_command(command)
        if not safe_command.position:
            raise ValueError("Agilex Piper requires a position JointCommand")
        action_dict = dict(zip(safe_command.name, safe_command.position, strict=True))

        arm_updates = {
            name: action_dict[name] for name in _ARM_JOINT_NAMES if name in action_dict
        }
        arm_targets: dict[str, float] | None = None
        joint_values: list[int] | None = None
        if arm_updates:
            if len(arm_updates) == len(_ARM_JOINT_NAMES):
                arm_targets = dict(arm_updates)
            else:
                if self._arm_target_cache is None:
                    state = self.get_state()
                    state_by_name = dict(zip(state.name, state.position, strict=True))
                    self._arm_target_cache = {
                        name: state_by_name[name] for name in _ARM_JOINT_NAMES
                    }
                arm_targets = dict(self._arm_target_cache)
                arm_targets.update(arm_updates)

            joint_values = [
                int(math.degrees(arm_targets[name]) * self.ANGLE_SCALE)
                for name in _ARM_JOINT_NAMES
            ]

        gripper = (
            gripper_meters_to_sdk(action_dict["gripper"])
            if "gripper" in action_dict
            else None
        )

        if joint_values is not None and arm_targets is not None:
            self.bus.MotionCtrl_2(
                0x01,
                0x01,
                self.motion_speed_percent,
                0x00,
            )
            self.bus.JointCtrl(*joint_values)
            self._arm_target_cache = arm_targets

        if gripper is not None:
            self.bus.GripperCtrl(gripper, 1000, 0x01, 0)
