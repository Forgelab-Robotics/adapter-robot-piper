from __future__ import annotations

import math
import unittest
from unittest.mock import Mock, patch

from forge_msgs import JointCommand, JointState
from robots_agilex_piper.driver import (
    _ARM_JOINT_NAMES,
    AgilexPiperDriver,
)


class _FakeBus:
    def __init__(self) -> None:
        self.motion_calls: list[tuple[int, ...]] = []
        self.joint_calls: list[tuple[int, ...]] = []
        self.gripper_calls: list[tuple[int, ...]] = []

    def MotionCtrl_1(self, *values: int) -> None:
        self.motion_calls.append(values)

    def MotionCtrl_2(self, *values: int) -> None:
        self.motion_calls.append(values)

    def JointCtrl(self, *values: int) -> None:
        self.joint_calls.append(values)

    def GripperCtrl(self, *values: int) -> None:
        self.gripper_calls.append(values)


def _raw_angle(value: float) -> int:
    return int(math.degrees(value) * AgilexPiperDriver.ANGLE_SCALE)


class SparseCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.driver = AgilexPiperDriver(auto_connect=False)
        self.bus = _FakeBus()
        self.driver.bus = self.bus  # type: ignore[assignment]

    def test_gripper_command_does_not_send_arm_frame(self) -> None:
        self.driver.set_command(
            JointCommand(name=["gripper"], position=[40.0])
        )

        self.assertEqual(self.bus.motion_calls, [])
        self.assertEqual(self.bus.joint_calls, [])
        self.assertEqual(self.bus.gripper_calls, [(40_000, 1000, 0x01, 0)])

    def test_complete_arm_command_does_not_send_gripper(self) -> None:
        positions = [0.1, 0.5, -0.5, 0.2, -0.2, 0.3]
        self.driver.set_command(
            JointCommand(name=list(_ARM_JOINT_NAMES), position=positions)
        )

        self.assertEqual(len(self.bus.motion_calls), 1)
        self.assertEqual(
            self.bus.joint_calls,
            [tuple(_raw_angle(value) for value in positions)],
        )
        self.assertEqual(self.bus.gripper_calls, [])
        self.assertEqual(
            self.driver._arm_target_cache,
            dict(zip(_ARM_JOINT_NAMES, positions, strict=True)),
        )

    def test_partial_arm_command_holds_cached_targets(self) -> None:
        initial = [0.1, 0.5, -0.5, 0.2, -0.2, 0.3]
        self.driver._arm_target_cache = dict(
            zip(_ARM_JOINT_NAMES, initial, strict=True)
        )

        self.driver.set_command(
            JointCommand(name=["joint2"], position=[0.75])
        )

        expected = list(initial)
        expected[1] = 0.75
        self.assertEqual(
            self.bus.joint_calls,
            [tuple(_raw_angle(value) for value in expected)],
        )
        self.assertEqual(self.bus.gripper_calls, [])

    def test_first_partial_arm_command_seeds_cache_from_hardware_state(self) -> None:
        measured = [0.1, 0.5, -0.5, 0.2, -0.2, 0.3]
        self.driver.get_state = Mock(  # type: ignore[method-assign]
            return_value=JointState(
                name=[*_ARM_JOINT_NAMES, "gripper"],
                position=[*measured, 25.0],
            )
        )

        self.driver.set_command(
            JointCommand(name=["joint2"], position=[0.75])
        )

        expected = list(measured)
        expected[1] = 0.75
        self.assertEqual(
            self.bus.joint_calls,
            [tuple(_raw_angle(value) for value in expected)],
        )
        self.driver.get_state.assert_called_once_with()

    def test_non_position_command_is_rejected_without_writes(self) -> None:
        with self.assertRaisesRegex(ValueError, "mode='position'"):
            self.driver.set_command(
                JointCommand(
                    name=["gripper"],
                    mode="velocity",
                    position=[40.0],
                    velocity=[1.0],
                )
            )

        self.assertEqual(self.bus.motion_calls, [])
        self.assertEqual(self.bus.joint_calls, [])
        self.assertEqual(self.bus.gripper_calls, [])

    def test_reset_invalidates_cached_arm_targets(self) -> None:
        self.driver._arm_target_cache = dict.fromkeys(_ARM_JOINT_NAMES, 0.25)

        with patch("robots_agilex_piper.driver.time.sleep"):
            self.driver.reset()

        self.assertIsNone(self.driver._arm_target_cache)
        self.assertEqual(self.bus.motion_calls, [(0x02, 0, 0)])


if __name__ == "__main__":
    unittest.main()
