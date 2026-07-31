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
