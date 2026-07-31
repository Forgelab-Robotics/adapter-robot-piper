from __future__ import annotations

import math
import unittest
from types import SimpleNamespace
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


class _SetupBus(_FakeBus):
    def __init__(
        self,
        *,
        fail_at: str | None = None,
        failure: RuntimeError | None = None,
        disable_failure: RuntimeError | None = None,
        disconnect_failure: RuntimeError | None = None,
    ) -> None:
        super().__init__()
        self.fail_at = fail_at
        self.failure = failure or RuntimeError(f"{fail_at} failed")
        self.disable_failure = disable_failure
        self.disconnect_failure = disconnect_failure
        self.setup_calls: list[str] = []
        self._gripper_attempts = 0

    def _fail_if_requested(self, stage: str) -> None:
        if self.fail_at == stage:
            raise self.failure

    def ConnectPort(self) -> None:
        self.setup_calls.append("connect")
        self._fail_if_requested("connect")

    def MasterSlaveConfig(self, *_values: int) -> None:
        self.setup_calls.append("config")
        self._fail_if_requested("config")

    def EnablePiper(self) -> bool:
        self.setup_calls.append("enable")
        self._fail_if_requested("enable")
        return True

    def DisablePiper(self) -> bool:
        self.setup_calls.append("disable")
        if self.disable_failure is not None:
            raise self.disable_failure
        return True

    def DisconnectPort(self) -> None:
        self.setup_calls.append("disconnect")
        if self.disconnect_failure is not None:
            raise self.disconnect_failure

    def GripperCtrl(self, *values: int) -> None:
        super().GripperCtrl(*values)
        self._gripper_attempts += 1
        if self.fail_at == "home" and self._gripper_attempts == 2:
            raise self.failure


def _raw_angle(value: float) -> int:
    return int(math.degrees(value) * AgilexPiperDriver.ANGLE_SCALE)


class SparseCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.driver = AgilexPiperDriver(auto_connect=False)
        self.bus = _FakeBus()
        self.driver.bus = self.bus  # type: ignore[assignment]

    def test_gripper_command_does_not_send_arm_frame(self) -> None:
        self.driver.set_command(JointCommand(name=["gripper"], position=[0.04]))

        self.assertEqual(self.bus.motion_calls, [])
        self.assertEqual(self.bus.joint_calls, [])
        self.assertEqual(self.bus.gripper_calls, [(40_000, 1000, 0x01, 0)])

    def test_gripper_state_decodes_sdk_units_to_meters(self) -> None:
        joints = SimpleNamespace(
            joint_1=0,
            joint_2=0,
            joint_3=0,
            joint_4=0,
            joint_5=0,
            joint_6=0,
        )
        self.bus.GetArmJointMsgs = Mock(  # type: ignore[attr-defined]
            return_value=SimpleNamespace(joint_state=joints)
        )
        self.bus.GetArmGripperMsgs = Mock(  # type: ignore[attr-defined]
            return_value=SimpleNamespace(
                gripper_state=SimpleNamespace(grippers_angle=40_000)
            )
        )

        state = self.driver.get_state()

        self.assertEqual(state.position[-1], 0.04)

    def test_legacy_millimeter_gripper_command_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "meters, not millimeters"):
            self.driver.set_command(JointCommand(name=["gripper"], position=[40.0]))

        self.assertEqual(self.bus.motion_calls, [])
        self.assertEqual(self.bus.joint_calls, [])
        self.assertEqual(self.bus.gripper_calls, [])

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

        self.driver.set_command(JointCommand(name=["joint2"], position=[0.75]))

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
                position=[*measured, 0.025],
            )
        )

        self.driver.set_command(JointCommand(name=["joint2"], position=[0.75]))

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
                    position=[0.04],
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


class ConnectionLifecycleTest(unittest.TestCase):
    def test_lifecycle_grippers_are_validated_before_bus_construction(self) -> None:
        invalid_positions = (
            ("initial", 40.0),
            ("rest", -0.001),
            ("initial", math.nan),
            ("rest", math.inf),
        )

        for position_name, gripper in invalid_positions:
            with self.subTest(position_name=position_name, gripper=gripper):
                with (
                    patch(
                        "robots_agilex_piper.driver.C_PiperInterface_V2"
                    ) as bus_factory,
                    self.assertRaisesRegex(ValueError, "meters, not millimeters"),
                ):
                    AgilexPiperDriver(
                        positions={position_name: {"gripper": gripper}},
                        auto_connect=True,
                    )

                bus_factory.assert_not_called()

    def test_unknown_lifecycle_name_is_rejected_before_bus_construction(self) -> None:
        with (
            patch("robots_agilex_piper.driver.C_PiperInterface_V2") as bus_factory,
            self.assertRaisesRegex(ValueError, "Unknown lifecycle position: inital"),
        ):
            AgilexPiperDriver(
                positions={"inital": {"joint1": 0.1}},
                auto_connect=True,
            )

        bus_factory.assert_not_called()

    def test_unknown_actuator_is_rejected_before_bus_construction(self) -> None:
        with (
            patch("robots_agilex_piper.driver.C_PiperInterface_V2") as bus_factory,
            self.assertRaisesRegex(ValueError, "Unknown actuators.*griper"),
        ):
            AgilexPiperDriver(
                positions={"initial": {"griper": 0.04}},
                auto_connect=True,
            )

        bus_factory.assert_not_called()

    def test_lifecycle_arm_targets_keep_existing_clipping_and_cache_behavior(
        self,
    ) -> None:
        bus = _SetupBus()
        driver = AgilexPiperDriver(
            positions={"initial": {"joint1": 100.0}},
            auto_connect=False,
        )

        with (
            patch("robots_agilex_piper.driver.C_PiperInterface_V2", return_value=bus),
            patch("robots_agilex_piper.driver.time.sleep"),
        ):
            driver.connect()

        expected_joint1 = _raw_angle(2.618)
        self.assertEqual([frame[0] for frame in bus.joint_calls], [expected_joint1] * 2)
        arm_target_cache = driver._arm_target_cache
        self.assertIsNotNone(arm_target_cache)
        assert arm_target_cache is not None
        self.assertEqual(arm_target_cache["joint1"], 2.618)
        self.assertIs(driver.bus, bus)

    def test_failed_connect_rolls_back_each_setup_stage_without_rest(self) -> None:
        cases = (
            ("connect", False, 0),
            ("config", False, 0),
            ("enable", True, 0),
            ("home", True, 2),
        )

        for fail_at, should_disable, expected_home_frames in cases:
            with self.subTest(fail_at=fail_at):
                failure = RuntimeError(f"primary {fail_at} failure")
                bus = _SetupBus(fail_at=fail_at, failure=failure)
                driver = AgilexPiperDriver(
                    positions={
                        "initial": {"joint1": 0.1},
                        "rest": {"joint1": 0.2},
                    },
                    auto_connect=False,
                )
                driver._arm_target_cache = dict.fromkeys(_ARM_JOINT_NAMES, 0.25)

                with (
                    patch(
                        "robots_agilex_piper.driver.C_PiperInterface_V2",
                        return_value=bus,
                    ) as bus_factory,
                    patch("robots_agilex_piper.driver.time.sleep"),
                    self.assertRaises(RuntimeError) as raised,
                ):
                    driver.connect()

                self.assertIs(raised.exception, failure)
                bus_factory.assert_called_once_with("can0")
                self.assertEqual(bus.setup_calls.count("disable"), int(should_disable))
                self.assertEqual(bus.setup_calls.count("disconnect"), 1)
                self.assertEqual(bus.setup_calls[-1], "disconnect")
                self.assertIsNone(driver.bus)
                self.assertIsNone(driver._arm_target_cache)

                initial_joint1 = _raw_angle(0.1)
                rest_joint1 = _raw_angle(0.2)
                sent_joint1 = [frame[0] for frame in bus.joint_calls]
                self.assertEqual(sent_joint1, [initial_joint1] * expected_home_frames)
                self.assertNotIn(rest_joint1, sent_joint1)
                self.assertEqual(len(bus.gripper_calls), expected_home_frames)

    def test_cleanup_failures_do_not_mask_connect_failure(self) -> None:
        failure = RuntimeError("primary enable failure")
        bus = _SetupBus(
            fail_at="enable",
            failure=failure,
            disable_failure=RuntimeError("disable cleanup failure"),
            disconnect_failure=RuntimeError("disconnect cleanup failure"),
        )
        driver = AgilexPiperDriver(auto_connect=False)

        with (
            patch("robots_agilex_piper.driver.C_PiperInterface_V2", return_value=bus),
            patch("robots_agilex_piper.driver.time.sleep"),
            self.assertRaises(RuntimeError) as raised,
        ):
            driver.connect()

        self.assertIs(raised.exception, failure)
        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)
        self.assertIsNone(driver._arm_target_cache)
        self.assertEqual(bus.joint_calls, [])
        self.assertEqual(bus.gripper_calls, [])


if __name__ == "__main__":
    unittest.main()
