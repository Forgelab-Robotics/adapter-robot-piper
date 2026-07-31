from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType


def _load_action_source() -> ModuleType:
    path = (
        Path(__file__).parents[1]
        / "examples/03_workflows/simulation/mujoco_piper/test_action_source.py"
    )
    spec = importlib.util.spec_from_file_location("piper_test_action_source", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load example action source: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExampleSweepTest(unittest.TestCase):
    def test_gripper_sweep_uses_total_opening_meters(self) -> None:
        action_source = _load_action_source()
        joint_seconds = 2.0
        gripper_start = 6 * joint_seconds

        opened = action_source.build_sweep_command(gripper_start, joint_seconds)
        midpoint = action_source.build_sweep_command(
            gripper_start + joint_seconds / 2,
            joint_seconds,
        )

        self.assertEqual(opened.name[-1], "gripper")
        self.assertEqual(opened.position[:-1], [0.0] * 6)
        self.assertEqual(opened.position[-1], 0.105)
        self.assertEqual(midpoint.position[-1], 0.0525)


if __name__ == "__main__":
    unittest.main()
