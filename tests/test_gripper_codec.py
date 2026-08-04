from __future__ import annotations

import unittest

from robots_agilex_piper.codec import (
    GRIPPER_MAX_OPENING_METERS,
    GRIPPER_MAX_SDK,
    GRIPPER_SDK_UNITS_PER_METER,
    gripper_meters_to_sdk,
    gripper_sdk_to_meters,
)
from robots_agilex_piper.config import (
    AGILEX_PIPER_ACTUATOR_SPECS,
    AgilexPiperNodeConfig,
)
from robots_agilex_piper.device_tools import _scaled_ee_mm, _scaled_gripper_m
from robots_agilex_piper.driver import AgilexPiperDriver


class GripperCodecTest(unittest.TestCase):
    def test_meter_sdk_round_trip(self) -> None:
        cases = ((0.0, 0), (0.04, 40_000), (0.105, 105_000))

        for meters, sdk_value in cases:
            with self.subTest(meters=meters, sdk_value=sdk_value):
                self.assertEqual(gripper_meters_to_sdk(meters), sdk_value)
                self.assertEqual(gripper_sdk_to_meters(sdk_value), meters)

    def test_encoding_rounds_to_nearest_sdk_unit(self) -> None:
        self.assertEqual(gripper_meters_to_sdk(0.0400004), 40_000)
        self.assertEqual(gripper_meters_to_sdk(0.0400006), 40_001)

    def test_legacy_millimeter_value_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "meters, not millimeters"):
            gripper_meters_to_sdk(40.0)

    def test_config_rejects_legacy_millimeter_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "meters, not millimeters"):
            AgilexPiperNodeConfig.from_dict(
                {"positions": {"initial": {"gripper": 40.0}}}
            )

    def test_pre_1_1_positional_config_arguments_remain_compatible(self) -> None:
        positions = {"initial": {"joint1": 0.25}}
        config = AgilexPiperNodeConfig("can2", True, False, positions)

        self.assertIs(config.positions, positions)
        self.assertEqual(config.motion_speed_percent, 100)

    def test_removed_lifecycle_behavior_switches_are_rejected(self) -> None:
        for key, value in (
            ("startup_behavior", "hold_current"),
            ("shutdown_behavior", "disable"),
        ):
            with self.subTest(key=key), self.assertRaisesRegex(
                ValueError, "已不再支持"
            ):
                AgilexPiperNodeConfig.from_dict({key: value})

    def test_config_rejects_misspelled_lifecycle_keys(self) -> None:
        for key in (
            "motion_speed_percnt",
            "startup_behaviour",
            "stratup_behavior",
            "shutdown_behaviour",
        ):
            expected = "未知配置项" if key == "motion_speed_percnt" else "已不再支持"
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, expected):
                AgilexPiperNodeConfig.from_dict({key: "hold_current"})

    def test_config_validates_motion_speed_percent(self) -> None:
        config = AgilexPiperNodeConfig.from_dict({"motion_speed_percent": 30})
        self.assertEqual(config.motion_speed_percent, 30)

        for value in (0, 101, 30.5, True, "30"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "motion_speed_percent"
            ):
                AgilexPiperNodeConfig.from_dict({"motion_speed_percent": value})

    def test_reset_position_is_canonical_and_rest_is_rejected(self) -> None:
        reset = AgilexPiperNodeConfig.from_dict(
            {"positions": {"reset": {"joint5": 0.25}}}
        )
        self.assertEqual(reset.resolved_position("reset")["joint5"], 0.25)

        with self.assertRaisesRegex(ValueError, "未知 positions 名称: rest"):
            AgilexPiperNodeConfig.from_dict(
                {"positions": {"rest": {"joint5": 0.2}}}
            )
        with self.assertRaisesRegex(ValueError, "未知 positions 名称: rest"):
            reset.resolved_position("rest")


    def test_observed_sdk_values_are_reported_even_outside_nominal_limits(self) -> None:
        self.assertEqual(gripper_sdk_to_meters(-1), -0.000001)
        self.assertEqual(
            gripper_sdk_to_meters(GRIPPER_MAX_SDK + 1),
            0.105001,
        )

    def test_forge_actuator_spec_uses_total_opening_meters(self) -> None:
        gripper_spec = next(
            spec for spec in AGILEX_PIPER_ACTUATOR_SPECS if spec.name == "gripper"
        )

        self.assertEqual(gripper_spec.position_unit, "meters")
        self.assertEqual(gripper_spec.min_position, 0.0)
        self.assertEqual(gripper_spec.max_position, GRIPPER_MAX_OPENING_METERS)
        self.assertEqual(GRIPPER_SDK_UNITS_PER_METER, 1_000_000)
        self.assertEqual(AgilexPiperDriver.GRIPPER_SCALE, 1_000_000)

    def test_device_tools_keep_ee_mm_and_gripper_m_separate(self) -> None:
        self.assertEqual(_scaled_ee_mm(40_000), 40.0)
        self.assertEqual(_scaled_gripper_m(40_000), 0.04)


if __name__ == "__main__":
    unittest.main()
