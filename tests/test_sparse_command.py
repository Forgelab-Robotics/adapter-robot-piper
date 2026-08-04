from __future__ import annotations

import math
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from forge_msgs import JointCommand, JointState

from robots_agilex_piper.driver import (
    _ARM_JOINT_NAMES,
    _ENABLE_FEEDBACK_CAN_IDS,
    _ENABLE_FEEDBACK_STREAMS,
    _POSITION_FEEDBACK_STREAMS,
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


class _FakeFeedbackCounter:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.fps_data = {
            name: 0
            for name in (*_POSITION_FEEDBACK_STREAMS, *_ENABLE_FEEDBACK_STREAMS)
        }


class _SetupBus(_FakeBus):
    def __init__(
        self,
        *,
        fail_at: str | None = None,
        failure: RuntimeError | None = None,
        disable_failure: BaseException | None = None,
        disable_result: bool = True,
        enable_statuses: list[list[bool]] | None = None,
        refresh_enable_feedback_on_poll: bool = True,
        refreshed_enable_streams: tuple[str, ...] = _ENABLE_FEEDBACK_STREAMS,
        refresh_enable_feedback_during_disable: bool = False,
        refresh_position_feedback_on_command: bool = False,
        enable_can_ids: tuple[int, ...] = _ENABLE_FEEDBACK_CAN_IDS,
        disconnect_failure: BaseException | None = None,
    ) -> None:
        super().__init__()
        self.fail_at = fail_at
        self.failure = failure or RuntimeError(f"{fail_at} failed")
        self.disable_failure = disable_failure
        self.disable_result = disable_result
        self.enable_statuses = enable_statuses or [[False] * 6]
        self.refresh_enable_feedback_on_poll = refresh_enable_feedback_on_poll
        self.refreshed_enable_streams = refreshed_enable_streams
        self.refresh_enable_feedback_during_disable = (
            refresh_enable_feedback_during_disable
        )
        self.refresh_position_feedback_on_command = (
            refresh_position_feedback_on_command
        )
        self.enable_can_ids = enable_can_ids
        self.enable_status_calls = 0
        self.disconnect_failure = disconnect_failure
        self.setup_calls: list[str] = []
        self._gripper_attempts = 0
        self.feedback_counter = _FakeFeedbackCounter()
        setattr(
            self,
            "_C_PiperInterface_V2__fps_counter",
            self.feedback_counter,
        )

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
        if self.refresh_enable_feedback_during_disable:
            with self.feedback_counter.lock:
                for name in _ENABLE_FEEDBACK_STREAMS:
                    self.feedback_counter.fps_data[name] += 1
        return self.disable_result

    def GetArmLowSpdInfoMsgs(self) -> SimpleNamespace:
        if self.refresh_enable_feedback_on_poll:
            with self.feedback_counter.lock:
                for name in self.refreshed_enable_streams:
                    self.feedback_counter.fps_data[name] += 1
        index = min(self.enable_status_calls, len(self.enable_statuses) - 1)
        self.enable_status_calls += 1
        statuses = self.enable_statuses[index]
        motors = {
            f"motor_{motor_index}": SimpleNamespace(
                can_id=self.enable_can_ids[motor_index - 1],
                foc_status=SimpleNamespace(
                    driver_enable_status=statuses[motor_index - 1]
                ),
            )
            for motor_index in range(1, 7)
        }
        return SimpleNamespace(**motors)

    def DisconnectPort(self) -> None:
        self.setup_calls.append("disconnect")
        if self.disconnect_failure is not None:
            raise self.disconnect_failure

    def JointCtrl(self, *values: int) -> None:
        super().JointCtrl(*values)
        if self.refresh_position_feedback_on_command:
            with self.feedback_counter.lock:
                for name in _POSITION_FEEDBACK_STREAMS:
                    self.feedback_counter.fps_data[name] += 1

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

    def test_configured_motion_speed_is_sent_to_hardware(self) -> None:
        driver = AgilexPiperDriver(motion_speed_percent=30, auto_connect=False)
        bus = _FakeBus()
        driver.bus = bus  # type: ignore[assignment]
        driver._arm_target_cache = dict.fromkeys(_ARM_JOINT_NAMES, 0.0)

        driver.set_command(JointCommand(name=["joint1"], position=[0.1]))

        self.assertEqual(bus.motion_calls, [(0x01, 0x01, 30, 0x00)])

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
            ("reset", -0.001),
            ("initial", math.nan),
            ("reset", math.inf),
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
        driver._wait_for_position = Mock(return_value=True)  # type: ignore[method-assign]

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
        initial_target = driver._wait_for_position.call_args.args[0]
        self.assertEqual(initial_target["joint1"], 2.618)
        self.assertIs(driver.bus, bus)

    def test_initial_feedback_baseline_is_sampled_after_command(self) -> None:
        bus = _SetupBus(refresh_position_feedback_on_command=True)
        driver = AgilexPiperDriver(auto_connect=False)
        driver._wait_for_position = Mock(return_value=True)  # type: ignore[method-assign]

        with (
            patch("robots_agilex_piper.driver.C_PiperInterface_V2", return_value=bus),
            patch("robots_agilex_piper.driver.time.sleep"),
        ):
            driver.connect()

        self.assertEqual(
            driver._wait_for_position.call_args.kwargs["after"],
            (2, 2, 2, 2),
        )

    def test_reset_convergence_uses_clipped_command_target(self) -> None:
        bus = _SetupBus()
        driver = AgilexPiperDriver(
            positions={"reset": {"joint1": 100.0}},
            auto_connect=False,
        )
        driver.bus = bus  # type: ignore[assignment]
        driver._wait_for_position = Mock(return_value=True)  # type: ignore[method-assign]

        driver.move_to_reset_position()

        actual_target = driver._wait_for_position.call_args.args[0]
        self.assertEqual(actual_target["joint1"], 2.618)
        self.assertEqual(bus.joint_calls[0][0], _raw_angle(2.618))

    def test_fixed_lifecycle_moves_initial_and_reset_then_disables(self) -> None:
        bus = _SetupBus()
        driver = AgilexPiperDriver(auto_connect=False)
        driver._wait_for_position = Mock(return_value=True)  # type: ignore[method-assign]

        with (
            patch("robots_agilex_piper.driver.C_PiperInterface_V2", return_value=bus),
            patch("robots_agilex_piper.driver.time.sleep"),
        ):
            driver.connect()
            driver.disconnect()

        self.assertEqual(len(bus.joint_calls), 3)
        self.assertEqual(len(bus.gripper_calls), 3)
        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        waited_targets = [
            invocation.args[0] for invocation in driver._wait_for_position.call_args_list
        ]
        self.assertEqual(
            waited_targets,
            [driver._positions["initial"], driver._positions["reset"]],
        )
        self.assertIsNone(driver.bus)
        self.assertIsNone(driver._arm_target_cache)

    def test_initial_position_timeout_disables_and_disconnects(self) -> None:
        bus = _SetupBus()
        driver = AgilexPiperDriver(auto_connect=False)
        driver._wait_for_position = Mock(return_value=False)  # type: ignore[method-assign]

        with (
            patch("robots_agilex_piper.driver.C_PiperInterface_V2", return_value=bus),
            patch("robots_agilex_piper.driver.time.sleep"),
            self.assertRaisesRegex(RuntimeError, "initial position"),
        ):
            driver.connect()

        self.assertEqual(len(bus.joint_calls), 2)
        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)
        self.assertIsNone(driver._arm_target_cache)

    def test_position_wait_rejects_default_state_without_fresh_feedback(self) -> None:
        bus = _SetupBus()
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver._LIFECYCLE_POSITION_TIMEOUT_SEC = 0.0
        driver._feedback_generation = Mock(  # type: ignore[method-assign]
            return_value=(0, 0, 0, 0)
        )
        driver.get_state = Mock(  # type: ignore[method-assign]
            return_value=JointState(
                name=driver.joint_order,
                position=[0.0] * 7,
            )
        )

        reached = driver._wait_for_position(
            driver._positions["initial"],
            after=(0, 0, 0, 0),
        )

        self.assertFalse(reached)
        driver.get_state.assert_not_called()

    def test_position_wait_rejects_partial_fresh_feedback(self) -> None:
        bus = _SetupBus()
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver._LIFECYCLE_POSITION_TIMEOUT_SEC = 0.0
        driver._feedback_generation = Mock(  # type: ignore[method-assign]
            return_value=(1, 1, 1, 0)
        )
        driver.get_state = Mock()  # type: ignore[method-assign]

        reached = driver._wait_for_position(
            driver._positions["initial"],
            after=(0, 0, 0, 0),
        )

        self.assertFalse(reached)
        driver.get_state.assert_not_called()

    def test_position_wait_accepts_fresh_feedback_at_target(self) -> None:
        bus = _SetupBus()
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver._feedback_generation = Mock(  # type: ignore[method-assign]
            return_value=(1, 1, 1, 1)
        )
        driver.get_state = Mock(  # type: ignore[method-assign]
            return_value=JointState(
                name=driver.joint_order,
                position=[0.0] * 7,
            )
        )

        reached = driver._wait_for_position(
            driver._positions["initial"],
            after=(0, 0, 0, 0),
        )

        self.assertTrue(reached)
        driver.get_state.assert_called_once_with()

    def test_rest_driver_contract_is_removed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown lifecycle position: rest"):
            AgilexPiperDriver(positions={"rest": {}}, auto_connect=False)
        self.assertFalse(hasattr(AgilexPiperDriver, "move_to_rest_position"))

    def test_pre_1_1_positional_driver_arguments_remain_compatible(self) -> None:
        driver = AgilexPiperDriver("can9", "slave", True, None, False)

        self.assertEqual(driver.port, "can9")
        self.assertTrue(driver.is_follower)
        self.assertIsNone(driver.bus)

    def test_reset_failure_still_disables_disconnects_and_is_reraised(self) -> None:
        failure = RuntimeError("reset failed")
        bus = _SetupBus()
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver.move_to_reset_position = Mock(  # type: ignore[method-assign]
            side_effect=failure
        )

        with self.assertRaises(RuntimeError) as raised:
            driver.disconnect()

        self.assertIs(raised.exception, failure)
        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)

    def test_disable_failure_does_not_prevent_disconnect(self) -> None:
        bus = _SetupBus(disable_failure=RuntimeError("disable failed"))
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver.move_to_reset_position = Mock()  # type: ignore[method-assign]

        with self.assertRaisesRegex(RuntimeError, "disable failed"):
            driver.disconnect()

        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)

    def test_missing_feedback_counter_fails_after_disable_and_still_disconnects(
        self,
    ) -> None:
        bus = _SetupBus()
        delattr(bus, "_C_PiperInterface_V2__fps_counter")
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver.move_to_reset_position = Mock()  # type: ignore[method-assign]

        with self.assertRaisesRegex(RuntimeError, "feedback counter is unavailable"):
            driver.disconnect()

        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)

    def test_disable_ignores_sdk_pre_command_result_and_polls_post_status(self) -> None:
        bus = _SetupBus(
            disable_result=False,
            enable_statuses=[[True] * 6, [False] * 6],
        )
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver.move_to_reset_position = Mock()  # type: ignore[method-assign]

        with patch("robots_agilex_piper.driver.time.sleep"):
            driver.disconnect()

        self.assertEqual(bus.enable_status_calls, 2)
        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)

    def test_disable_status_timeout_is_failure_after_disconnect(self) -> None:
        bus = _SetupBus(enable_statuses=[[True] * 6])
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver.move_to_reset_position = Mock()  # type: ignore[method-assign]
        driver._DISABLE_AGILEX_PIPER_TIMEOUT_SEC = 0.0

        with self.assertRaisesRegex(RuntimeError, "fresh disabled feedback"):
            driver.disconnect()

        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)

    def test_default_disabled_state_without_fresh_feedback_is_rejected(self) -> None:
        bus = _SetupBus(refresh_enable_feedback_on_poll=False)
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver.move_to_reset_position = Mock()  # type: ignore[method-assign]
        driver._DISABLE_AGILEX_PIPER_TIMEOUT_SEC = 0.0

        with self.assertRaisesRegex(RuntimeError, "fresh disabled feedback"):
            driver.disconnect()

        self.assertEqual(bus.enable_status_calls, 1)
        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)

    def test_feedback_received_during_disable_is_not_accepted(self) -> None:
        bus = _SetupBus(
            refresh_enable_feedback_on_poll=False,
            refresh_enable_feedback_during_disable=True,
        )
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver.move_to_reset_position = Mock()  # type: ignore[method-assign]
        driver._DISABLE_AGILEX_PIPER_TIMEOUT_SEC = 0.0

        with self.assertRaisesRegex(RuntimeError, "fresh disabled feedback"):
            driver.disconnect()

        self.assertEqual(bus.enable_status_calls, 1)
        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)

    def test_partial_motor_feedback_is_rejected(self) -> None:
        bus = _SetupBus(refreshed_enable_streams=_ENABLE_FEEDBACK_STREAMS[:-1])
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver.move_to_reset_position = Mock()  # type: ignore[method-assign]
        driver._DISABLE_AGILEX_PIPER_TIMEOUT_SEC = 0.0

        with self.assertRaisesRegex(RuntimeError, "fresh disabled feedback"):
            driver.disconnect()

        self.assertEqual(bus.enable_status_calls, 1)
        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)

    def test_invalid_motor_feedback_ids_are_rejected(self) -> None:
        bus = _SetupBus(enable_can_ids=(0, 0, 0, 0, 0, 0))
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver.move_to_reset_position = Mock()  # type: ignore[method-assign]
        driver._DISABLE_AGILEX_PIPER_TIMEOUT_SEC = 0.0

        with self.assertRaisesRegex(RuntimeError, "fresh disabled feedback"):
            driver.disconnect()

        self.assertEqual(bus.enable_status_calls, 1)
        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)

    def test_base_exception_during_disable_still_disconnects_and_is_reraised(
        self,
    ) -> None:
        interruption = KeyboardInterrupt()
        bus = _SetupBus(disable_failure=interruption)
        driver = AgilexPiperDriver(auto_connect=False)
        driver.bus = bus  # type: ignore[assignment]
        driver.move_to_reset_position = Mock()  # type: ignore[method-assign]

        with self.assertRaises(KeyboardInterrupt) as raised:
            driver.disconnect()

        self.assertIs(raised.exception, interruption)
        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)

    def test_failed_connect_rolls_back_each_setup_stage_without_reset(self) -> None:
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
                        "reset": {"joint1": 0.2},
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
                reset_joint1 = _raw_angle(0.2)
                sent_joint1 = [frame[0] for frame in bus.joint_calls]
                self.assertEqual(sent_joint1, [initial_joint1] * expected_home_frames)
                self.assertNotIn(reset_joint1, sent_joint1)
                self.assertEqual(len(bus.gripper_calls), expected_home_frames)

    def test_disable_timeout_during_connect_rollback_preserves_setup_failure(
        self,
    ) -> None:
        failure = RuntimeError("primary home failure")
        bus = _SetupBus(
            fail_at="home",
            failure=failure,
            enable_statuses=[[True] * 6],
        )
        driver = AgilexPiperDriver(auto_connect=False)
        driver._DISABLE_AGILEX_PIPER_TIMEOUT_SEC = 0.0

        with (
            patch("robots_agilex_piper.driver.C_PiperInterface_V2", return_value=bus),
            patch("robots_agilex_piper.driver.time.sleep"),
            self.assertRaises(RuntimeError) as raised,
        ):
            driver.connect()

        self.assertIs(raised.exception, failure)
        self.assertGreaterEqual(bus.enable_status_calls, 1)
        self.assertEqual(bus.setup_calls[-2:], ["disable", "disconnect"])
        self.assertIsNone(driver.bus)

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
