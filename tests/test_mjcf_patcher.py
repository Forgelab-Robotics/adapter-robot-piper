from __future__ import annotations

import importlib.util
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType


def _load_patcher() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts/patch_mjcf_gripper_actuators.py"
    spec = importlib.util.spec_from_file_location("patch_mjcf_gripper_actuators", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load MJCF patcher: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MjcfPatcherTest(unittest.TestCase):
    def test_gripper_semantics_are_migrated_without_touching_arm_actuator(
        self,
    ) -> None:
        patcher = _load_patcher()
        source = """<mujoco>
  <actuator>
    <position name="joint1" joint="joint1" kp="80" />
    <position name="gripper" joint="joint7" class="finger" kp="40" kv="5" />
  </actuator>
</mujoco>
"""

        patched, matches = patcher.patch_mjcf_text(source)

        self.assertEqual(matches, 1)
        self.assertIn(
            '<position name="gripper" joint="joint7" class="finger" '
            'inheritrange="0" ctrlrange="0 0.105" gear="2" kp="10" '
            'kv="1.25" forcerange="-5 5" />',
            patched,
        )
        self.assertIn(
            '<position name="joint1" joint="joint1" kp="80" />',
            patched,
        )

    def test_multiline_gripper_preserves_includes_and_comments(self) -> None:
        patcher = _load_patcher()
        source = """<mujoco>
  <!-- <position name="joint7" joint="joint7" /> -->
  <include file="shared_defaults.xml" />
  <actuator>
    <position
      name="left/gripper"
      joint="left/joint7"
      class="finger"
      kp="40"
      kv="5"
    /> <!-- keep this actuator comment -->
  </actuator>
</mujoco>
"""

        patched, matches = patcher.patch_mjcf_text(source)

        self.assertEqual(matches, 1)
        self.assertIn(
            '<position name="left/gripper" joint="left/joint7" class="finger" '
            'inheritrange="0" ctrlrange="0 0.105" gear="2" kp="10" '
            'kv="1.25" forcerange="-5 5" />',
            patched,
        )
        self.assertIn('  <include file="shared_defaults.xml" />\n', patched)
        self.assertIn(
            '  <!-- <position name="joint7" joint="joint7" /> -->\n',
            patched,
        )
        self.assertIn("<!-- keep this actuator comment -->", patched)

    def test_legacy_joint7_name_fails_explicitly(self) -> None:
        patcher = _load_patcher()
        source = """<mujoco>
  <actuator>
    <position name="left/joint7" joint="left/joint7" class="finger" />
  </actuator>
</mujoco>
"""

        with self.assertRaisesRegex(
            patcher.PatchError,
            r"non-canonical joint7 actuator name 'left/joint7'.*'left/gripper'",
        ):
            patcher.patch_mjcf_text(source)

    def test_non_self_closing_joint7_actuator_is_unpatchable(self) -> None:
        patcher = _load_patcher()
        source = """<mujoco>
  <actuator>
    <position name="gripper" joint="joint7" class="finger"></position>
  </actuator>
</mujoco>
"""

        with self.assertRaisesRegex(patcher.PatchError, "is not self-closing"):
            patcher.patch_mjcf_text(source)

    def test_malformed_xml_is_rejected(self) -> None:
        patcher = _load_patcher()
        source = """<mujoco>
  <actuator>
    <position name="gripper" joint="joint7" />
  </mujoco>
"""

        with self.assertRaisesRegex(
            patcher.PatchError,
            r"cannot parse XML document: mismatched tag",
        ):
            patcher.patch_mjcf_text(source)

    def test_unquoted_joint_is_rejected_even_with_valid_actuator(self) -> None:
        patcher = _load_patcher()
        source = """<mujoco>
  <actuator>
    <position name="gripper" joint="joint7" class="finger" kp="40" kv="5" />
    <position name="malformed" joint=joint7 />
  </actuator>
</mujoco>
"""

        with self.assertRaisesRegex(
            patcher.PatchError,
            r"cannot parse XML document: not well-formed",
        ):
            patcher.patch_mjcf_text(source)

    def test_directory_failure_is_not_hidden_by_a_matching_file(self) -> None:
        patcher = _load_patcher()
        good_source = """<mujoco>
  <actuator>
    <position name="gripper" joint="joint7" class="finger" kp="40" kv="5" />
  </actuator>
</mujoco>
"""
        bad_source = """<mujoco>
  <actuator>
    <position name="right/joint7" joint="right/joint7" class="finger" />
  </actuator>
</mujoco>
"""

        with TemporaryDirectory() as directory:
            root = Path(directory)
            good_path = root / "good.xml"
            bad_path = root / "legacy.xml"
            good_path.write_text(good_source, encoding="utf-8")
            bad_path.write_text(bad_source, encoding="utf-8")
            stderr = StringIO()

            with redirect_stderr(stderr):
                result = patcher.main([str(root)])

            self.assertEqual(result, 1)
            self.assertIn(str(bad_path), stderr.getvalue())
            self.assertIn("non-canonical", stderr.getvalue())
            self.assertEqual(good_path.read_text(encoding="utf-8"), good_source)
            self.assertEqual(bad_path.read_text(encoding="utf-8"), bad_source)

    def test_already_correct_actuator_is_an_exact_no_op(self) -> None:
        patcher = _load_patcher()
        source = """<mujoco>
  <actuator>
    <position joint="joint7" name="gripper" class="finger" forcerange="-5 5" kv="1.25" kp="10" gear="2" ctrlrange="0 0.105" inheritrange="0" data-source="keep"/>
  </actuator>
</mujoco>
"""

        patched, matches = patcher.patch_mjcf_text(source)

        self.assertEqual(matches, 1)
        self.assertEqual(patched, source)


if __name__ == "__main__":
    unittest.main()
