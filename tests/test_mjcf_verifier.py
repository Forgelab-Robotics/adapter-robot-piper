from __future__ import annotations

import importlib
import importlib.util
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any

mujoco: Any
try:
    mujoco = importlib.import_module("mujoco")
except ImportError:  # pragma: no cover - exercised only without the test dependency.
    mujoco = None


def _load_verifier() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts/verify_mjcf.py"
    spec = importlib.util.spec_from_file_location("verify_mjcf", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load MJCF verifier: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gripper_model_xml(
    prefixes: tuple[str, ...],
    *,
    finger_joint_type: str = "slide",
    inactive_equality: str | None = None,
    legacy_actuator: str | None = None,
    omitted_actuator: str | None = None,
    extra_equalities: tuple[str, ...] = (),
    extra_actuators: tuple[str, ...] = (),
) -> str:
    bodies: list[str] = []
    equalities: list[str] = []
    actuators: list[str] = []
    for index, prefix in enumerate(prefixes):
        bodies.extend(
            (
                f"""    <body name="finger7_{index}" pos="0 {index * 0.1} 0">
      <joint name="{prefix}joint7" type="{finger_joint_type}" axis="1 0 0" range="0 0.0525" />
      <geom type="sphere" size="0.01" mass="0.1" />
    </body>""",
                f"""    <body name="finger8_{index}" pos="0 {index * 0.1 + 0.03} 0">
      <joint name="{prefix}joint8" type="{finger_joint_type}" axis="1 0 0" range="-0.0525 0" />
      <geom type="sphere" size="0.01" mass="0.1" />
    </body>""",
            )
        )
        active = ' active="false"' if prefix == inactive_equality else ""
        equalities.append(
            f'    <joint joint1="{prefix}joint8" joint2="{prefix}joint7" '
            f'polycoef="0 -1 0 0 0"{active} />'
        )
        if prefix == omitted_actuator:
            continue
        actuator_name = (
            f"{prefix}joint7" if prefix == legacy_actuator else f"{prefix}gripper"
        )
        actuators.append(
            f'    <position name="{actuator_name}" joint="{prefix}joint7" '
            'inheritrange="0" ctrlrange="0 0.105" gear="2" kp="10" '
            'kv="1.25" forcerange="-5 5" />'
        )

    equalities.extend(extra_equalities)
    actuators.extend(extra_actuators)
    return f"""<mujoco model="gripper-verifier-test">
  <compiler autolimits="true" />
  <option gravity="0 0 0" />
  <worldbody>
{chr(10).join(bodies)}
  </worldbody>
  <equality>
{chr(10).join(equalities)}
  </equality>
  <actuator>
{chr(10).join(actuators)}
  </actuator>
</mujoco>
"""


@unittest.skipIf(
    mujoco is None,
    "mujoco is not installed; run with the test extra: uv run --extra test python -m unittest tests/test_mjcf_verifier.py",
)
class MjcfVerifierTest(unittest.TestCase):
    def _verify(self, xml: str) -> int:
        verifier = _load_verifier()
        model = mujoco.MjModel.from_xml_string(xml)
        with redirect_stdout(StringIO()):
            return verifier.verify_gripper_semantics(mujoco, model)

    def test_valid_two_arm_model_verifies_every_pair(self) -> None:
        xml = _gripper_model_xml(("left/", "right/"))

        self.assertEqual(self._verify(xml), 2)

    def test_inactive_matching_equality_is_rejected(self) -> None:
        xml = _gripper_model_xml(("",), inactive_equality="")

        with self.assertRaisesRegex(
            ValueError,
            r"equality is inactive \(eq_active0=0\)",
        ):
            self._verify(xml)

    def test_two_arm_partial_legacy_mapping_is_rejected(self) -> None:
        xml = _gripper_model_xml(
            ("left/", "right/"),
            legacy_actuator="right/",
        )

        with self.assertRaisesRegex(
            ValueError,
            r"right/joint7.*only canonical mapping.*right/gripper.*right/joint7",
        ):
            self._verify(xml)

    def test_gripper_actuator_count_must_match_pair_count(self) -> None:
        xml = _gripper_model_xml(
            ("left/", "right/"),
            omitted_actuator="right/",
        )

        with self.assertRaisesRegex(
            ValueError,
            r"right/joint7.*expected exactly one canonical mapping.*found 0",
        ):
            self._verify(xml)

    def test_actuator_targeting_joint8_is_rejected(self) -> None:
        xml = _gripper_model_xml(
            ("",),
            extra_actuators=('    <motor name="joint8-drive" joint="joint8" />',),
        )

        with self.assertRaisesRegex(
            ValueError,
            r"joint8-drive.*targets finger joint 'joint8'.*only canonical mapping.*'gripper'.*'joint7'",
        ):
            self._verify(xml)

    def test_duplicate_canonical_equality_is_rejected(self) -> None:
        xml = _gripper_model_xml(
            ("",),
            extra_equalities=(
                (
                    '    <joint name="duplicate" joint1="joint8" joint2="joint7" '
                    'polycoef="0 -1 0 0 0" />'
                ),
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            r"expected exactly one equality.*found 2.*duplicate/conflicting",
        ):
            self._verify(xml)

    def test_conflicting_pair_equality_is_rejected(self) -> None:
        xml = _gripper_model_xml(
            ("",),
            extra_equalities=(
                (
                    '    <joint name="conflict" joint1="joint8" joint2="joint7" '
                    'polycoef="0 1 0 0 0" />'
                ),
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            r"expected exactly one equality.*found 2.*duplicate/conflicting",
        ):
            self._verify(xml)

    def test_equality_touching_only_one_finger_joint_is_rejected(self) -> None:
        xml = _gripper_model_xml(
            ("",),
            extra_equalities=(
                (
                    '    <joint name="finger-lock" joint1="joint7" '
                    'polycoef="0 0 0 0 0" />'
                ),
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            r"joint7.*joint8.*non-canonical equality constraint.*only the single canonical",
        ):
            self._verify(xml)

    def test_hinge_finger_pair_is_rejected(self) -> None:
        xml = _gripper_model_xml(("",), finger_joint_type="hinge")

        with self.assertRaisesRegex(
            ValueError,
            r"joint7: expected a slide finger joint, got hinge",
        ):
            self._verify(xml)


if __name__ == "__main__":
    unittest.main()
