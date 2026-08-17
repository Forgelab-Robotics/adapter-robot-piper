# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


class DeliveryPathsTest(unittest.TestCase):
    def test_public_delivery_paths_are_stable(self) -> None:
        required_paths = (
            "LICENSE",
            "NOTICE",
            "THIRD_PARTY_NOTICES.md",
            "CHANGELOG.md",
            "CONTRIBUTING.md",
            "RELEASING.md",
            "SAFETY.md",
            "validation_output/README.md",
            ".github/workflows/ci.yml",
            "config/config.example.yaml",
            "config/agilex_piper_master.yaml.example",
            "config/agilex_piper_slave.yaml.example",
            "assets/mjcf/piper_mujoco/scene.xml",
            "assets/glb/piper.glb",
            "examples/03_workflows/simulation/mujoco_piper/"
            "dataflow.test_action_source.yaml",
        )

        missing = [path for path in required_paths if not (ROOT / path).exists()]
        self.assertEqual(missing, [], f"missing public delivery paths: {missing}")

    def test_simulation_dataflow_keeps_public_path_and_topic_contract(self) -> None:
        path = (
            ROOT
            / "examples/03_workflows/simulation/mujoco_piper/"
            "dataflow.test_action_source.yaml"
        )
        dataflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        nodes = {node["id"]: node for node in dataflow["nodes"]}

        self.assertEqual(
            nodes["mujoco"]["path"],
            "${FORGE_RUNTIME_ROOT}/packages/nodes/simulators/mujoco/main.py",
        )
        self.assertEqual(
            nodes["task_robot"]["path"],
            "${FORGE_RUNTIME_ROOT}/packages/nodes/task_robot/main.py",
        )
        self.assertEqual(nodes["test_action_source"]["path"], "test_action_source.py")
        self.assertEqual(
            nodes["task_robot"]["inputs"]["action"],
            "test_action_source/action",
        )
        self.assertEqual(
            nodes["mujoco"]["inputs"]["action"],
            "task_robot/action",
        )
        self.assertEqual(
            nodes["task_robot"]["inputs"]["proprio_state"],
            "mujoco/proprio_state",
        )

    def test_hardware_workflows_reference_local_robot_node_or_runtime_env(self) -> None:
        workflows = (
            "examples/03_workflows/real_record/dataflow.yaml",
            "examples/03_workflows/real_playback/dataflow.yaml",
        )

        for relative_path in workflows:
            with self.subTest(path=relative_path):
                path = ROOT / relative_path
                dataflow = yaml.safe_load(path.read_text(encoding="utf-8"))
                robot_nodes = [
                    node
                    for node in dataflow["nodes"]
                    if node["id"].startswith("agilex_piper_")
                ]
                self.assertTrue(robot_nodes)
                for node in dataflow["nodes"]:
                    node_path = node["path"]
                    if node_path.startswith("${FORGE_RUNTIME_"):
                        continue
                    resolved = (path.parent / node_path).resolve()
                    self.assertTrue(
                        resolved.is_file(),
                        f"{relative_path}: missing node path {node_path}",
                    )
                for node in robot_nodes:
                    self.assertEqual(
                        (path.parent / node["path"]).resolve(),
                        ROOT / "src/robots_agilex_piper/main.py",
                    )


if __name__ == "__main__":
    unittest.main()
