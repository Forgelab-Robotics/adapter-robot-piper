# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
import unittest

from robots_agilex_piper.config import AgilexPiperNodeConfig


ROOT = Path(__file__).resolve().parents[1]


class ConfigExamplesTest(unittest.TestCase):
    def test_delivered_node_configs_parse_and_validate(self) -> None:
        examples = {
            "config/config.example.yaml": True,
            "config/agilex_piper_slave.yaml.example": True,
            "config/agilex_piper_master.yaml.example": False,
        }

        for relative_path, expected_follower in examples.items():
            with self.subTest(path=relative_path):
                config = AgilexPiperNodeConfig.from_yaml_path(ROOT / relative_path)
                self.assertEqual(config.is_follower, expected_follower)
                self.assertTrue(config.port.startswith("can"))
                self.assertGreaterEqual(config.motion_speed_percent, 1)
                self.assertLessEqual(config.motion_speed_percent, 100)
                self.assertEqual(
                    set(config.resolved_position("initial")),
                    {
                        "joint1",
                        "joint2",
                        "joint3",
                        "joint4",
                        "joint5",
                        "joint6",
                        "gripper",
                    },
                )


if __name__ == "__main__":
    unittest.main()
