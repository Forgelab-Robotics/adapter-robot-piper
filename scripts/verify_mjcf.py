#!/usr/bin/env python3
"""Load Piper MJCF and verify joints plus total-opening gripper actuators."""

from __future__ import annotations

import argparse
import importlib
import math
import os
import sys
from typing import Any

_GRIPPER_CTRL_RANGE = (0.0, 0.105)
_GRIPPER_GEAR = 2.0
_GRIPPER_FORCE_RANGE = (-5.0, 5.0)
_GRIPPER_KP = 10.0
_GRIPPER_KV = 1.25
_FINGER_LIMIT = 0.0525
_MIDPOINT_OPENING = 0.0525
_ABS_TOL = 1e-9


def _object_name(mujoco: Any, model: Any, object_type: Any, object_id: int) -> str:
    name = mujoco.mj_id2name(model, object_type, object_id)
    return name or f"<{object_type} {object_id}>"


def _assert_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=_ABS_TOL):
        raise ValueError(f"{label}: expected {expected}, got {actual}")


def _assert_range(actual: Any, expected: tuple[float, float], label: str) -> None:
    _assert_close(float(actual[0]), expected[0], f"{label} lower")
    _assert_close(float(actual[1]), expected[1], f"{label} upper")


def _is_gripper_name(name: str | None) -> bool:
    return name == "gripper" or (name is not None and name.endswith("/gripper"))


def _actuator_label(mujoco: Any, model: Any, actuator_id: int) -> str:
    name = mujoco.mj_id2name(
        model,
        mujoco.mjtObj.mjOBJ_ACTUATOR,
        actuator_id,
    )
    return repr(name) if name else f"<unnamed actuator {actuator_id}>"


def _find_finger_pairs(
    mujoco: Any,
    model: Any,
) -> list[tuple[int, int, str, str, str]]:
    joint7_by_name: dict[str, int] = {}
    joint8_by_name: dict[str, int] = {}
    for joint_id in range(model.njnt):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id)
        if name is None:
            continue
        if name.endswith("joint7"):
            joint7_by_name[name] = joint_id
        elif name.endswith("joint8"):
            joint8_by_name[name] = joint_id

    if not joint7_by_name and not joint8_by_name:
        raise ValueError("no joint7/joint8 finger pairs")

    for joint8_name in joint8_by_name:
        joint7_name = f"{joint8_name.removesuffix('joint8')}joint7"
        if joint7_name not in joint7_by_name:
            raise ValueError(f"{joint8_name}: missing paired joint {joint7_name}")

    pairs: list[tuple[int, int, str, str, str]] = []
    for joint7_name, joint7_id in sorted(
        joint7_by_name.items(),
        key=lambda item: item[1],
    ):
        prefix = joint7_name.removesuffix("joint7")
        joint8_name = f"{prefix}joint8"
        joint8_id = joint8_by_name.get(joint8_name)
        if joint8_id is None:
            raise ValueError(f"{joint7_name}: missing paired joint {joint8_name}")

        slide_joint_type = int(mujoco.mjtJoint.mjJNT_SLIDE)
        for joint_id, joint_name in (
            (joint7_id, joint7_name),
            (joint8_id, joint8_name),
        ):
            actual_type = int(model.jnt_type[joint_id])
            if actual_type != slide_joint_type:
                type_name = {0: "free", 1: "ball", 2: "slide", 3: "hinge"}.get(
                    actual_type,
                    str(actual_type),
                )
                raise ValueError(
                    f"{joint_name}: expected a slide finger joint, got {type_name}"
                )

        pairs.append(
            (
                joint7_id,
                joint8_id,
                joint7_name,
                joint8_name,
                f"{prefix}gripper",
            )
        )
    return pairs


def _find_matching_gripper_actuators(
    mujoco: Any,
    model: Any,
    pairs: list[tuple[int, int, str, str, str]],
) -> list[int]:
    joint_transmission_type = int(mujoco.mjtTrn.mjTRN_JOINT)
    joint_target_types = {
        joint_transmission_type,
        int(mujoco.mjtTrn.mjTRN_JOINTINPARENT),
    }
    pair_by_member_id = {
        member_id: (pair, member_name)
        for pair in pairs
        for member_id, member_name in (
            (pair[0], pair[2]),
            (pair[1], pair[3]),
        )
    }
    mappings_by_joint7_id = {pair[0]: [] for pair in pairs}
    mapping_errors: list[str] = []

    for actuator_id in range(model.nu):
        name = mujoco.mj_id2name(
            model,
            mujoco.mjtObj.mjOBJ_ACTUATOR,
            actuator_id,
        )
        label = _actuator_label(mujoco, model, actuator_id)
        transmission_type = int(model.actuator_trntype[actuator_id])

        if transmission_type in joint_target_types:
            joint_id = int(model.actuator_trnid[actuator_id, 0])
            member = pair_by_member_id.get(joint_id)
            if member is not None:
                pair, member_name = member
                is_canonical = (
                    transmission_type == joint_transmission_type
                    and joint_id == pair[0]
                    and name == pair[4]
                )
                if is_canonical:
                    mappings_by_joint7_id[pair[0]].append(actuator_id)
                else:
                    mapping_errors.append(
                        f"{label} targets finger joint {member_name!r}; only canonical "
                        f"mapping {pair[4]!r} -> {pair[2]!r} is allowed"
                    )
            elif _is_gripper_name(name):
                joint_name = _object_name(
                    mujoco,
                    model,
                    mujoco.mjtObj.mjOBJ_JOINT,
                    joint_id,
                )
                mapping_errors.append(
                    f"{label} maps to non-finger joint {joint_name!r}; expected its "
                    "paired joint7"
                )
        elif _is_gripper_name(name):
            mapping_errors.append(f"{label} has a non-joint transmission")

    matched_actuators: list[int] = []
    for joint7_id, _, joint7_name, _, expected_name in pairs:
        mappings = mappings_by_joint7_id[joint7_id]
        if len(mappings) != 1:
            found = ", ".join(
                _actuator_label(mujoco, model, actuator_id) for actuator_id in mappings
            )
            mapping_errors.append(
                f"{joint7_name!r}: expected exactly one canonical mapping "
                f"{expected_name!r} -> {joint7_name!r}, found {len(mappings)} "
                f"({found or 'none'})"
            )
        else:
            matched_actuators.append(mappings[0])

    if mapping_errors:
        raise ValueError("; ".join(mapping_errors))
    return matched_actuators


def _verify_finger_equality(
    mujoco: Any,
    model: Any,
    joint7_id: int,
    joint8_id: int,
    label: str,
) -> None:
    joint_equality_type = int(mujoco.mjtEq.mjEQ_JOINT)
    finger_joint_ids = {joint7_id, joint8_id}
    touching_equalities: list[int] = []
    pair_equalities: list[int] = []
    for equality_id in range(model.neq):
        if int(model.eq_type[equality_id]) != joint_equality_type:
            continue
        object1_id = int(model.eq_obj1id[equality_id])
        object2_id = int(model.eq_obj2id[equality_id])
        if object1_id in finger_joint_ids or object2_id in finger_joint_ids:
            touching_equalities.append(equality_id)
        if (object1_id, object2_id) in (
            (joint8_id, joint7_id),
            (joint7_id, joint8_id),
        ):
            pair_equalities.append(equality_id)

    joint7_name = _object_name(
        mujoco,
        model,
        mujoco.mjtObj.mjOBJ_JOINT,
        joint7_id,
    )
    joint8_name = _object_name(
        mujoco,
        model,
        mujoco.mjtObj.mjOBJ_JOINT,
        joint8_id,
    )
    unrelated_equalities = [
        equality_id
        for equality_id in touching_equalities
        if equality_id not in pair_equalities
    ]
    if unrelated_equalities:
        raise ValueError(
            f"{label}: finger joints {joint7_name!r}/{joint8_name!r} participate "
            f"in non-canonical equality constraint(s) {unrelated_equalities}; only the "
            "single canonical pair equality is allowed"
        )
    if not pair_equalities:
        raise ValueError(
            f"{label}: missing canonical equality {joint8_name!r} = -{joint7_name!r}"
        )
    if len(pair_equalities) != 1:
        raise ValueError(
            f"{label}: expected exactly one equality between {joint7_name!r} and "
            f"{joint8_name!r}, found {len(pair_equalities)}; duplicate/conflicting "
            "pair equalities are not allowed"
        )

    equality_id = pair_equalities[0]
    if (
        int(model.eq_obj1id[equality_id]) != joint8_id
        or int(model.eq_obj2id[equality_id]) != joint7_id
    ):
        raise ValueError(
            f"{label}: non-canonical pair equality; expected joint1={joint8_name!r} "
            f"and joint2={joint7_name!r}"
        )
    if not bool(model.eq_active0[equality_id]):
        raise ValueError(f"{label} equality is inactive (eq_active0=0)")

    expected_polycoef = (0.0, -1.0, 0.0, 0.0, 0.0)
    for index, expected in enumerate(expected_polycoef):
        _assert_close(
            float(model.eq_data[equality_id, index]),
            expected,
            f"{label} equality polycoef[{index}]",
        )


def _verify_gripper_actuator(
    mujoco: Any,
    model: Any,
    actuator_id: int,
) -> None:
    actuator_name = _object_name(
        mujoco,
        model,
        mujoco.mjtObj.mjOBJ_ACTUATOR,
        actuator_id,
    )
    if not bool(model.actuator_ctrllimited[actuator_id]):
        raise ValueError(f"{actuator_name}: ctrlrange is not limited")
    _assert_range(
        model.actuator_ctrlrange[actuator_id],
        _GRIPPER_CTRL_RANGE,
        f"{actuator_name} ctrlrange",
    )
    _assert_close(
        float(model.actuator_gear[actuator_id, 0]),
        _GRIPPER_GEAR,
        f"{actuator_name} gear",
    )
    for gear_index in range(1, model.actuator_gear.shape[1]):
        _assert_close(
            float(model.actuator_gear[actuator_id, gear_index]),
            0.0,
            f"{actuator_name} gear[{gear_index}]",
        )

    if not bool(model.actuator_forcelimited[actuator_id]):
        raise ValueError(f"{actuator_name}: forcerange is not limited")
    _assert_range(
        model.actuator_forcerange[actuator_id],
        _GRIPPER_FORCE_RANGE,
        f"{actuator_name} forcerange",
    )
    _assert_close(
        float(model.actuator_gainprm[actuator_id, 0]),
        _GRIPPER_KP,
        f"{actuator_name} kp",
    )
    _assert_close(
        float(model.actuator_biasprm[actuator_id, 1]),
        -_GRIPPER_KP,
        f"{actuator_name} position bias",
    )
    _assert_close(
        float(model.actuator_biasprm[actuator_id, 2]),
        -_GRIPPER_KV,
        f"{actuator_name} kv",
    )

    if int(model.actuator_trntype[actuator_id]) != int(mujoco.mjtTrn.mjTRN_JOINT):
        raise ValueError(f"{actuator_name}: transmission is not a joint")
    joint7_id = int(model.actuator_trnid[actuator_id, 0])
    joint7_name = _object_name(
        mujoco,
        model,
        mujoco.mjtObj.mjOBJ_JOINT,
        joint7_id,
    )
    if not joint7_name.endswith("joint7"):
        raise ValueError(
            f"{actuator_name}: expected joint7 transmission, got {joint7_name}"
        )
    joint8_name = f"{joint7_name.removesuffix('joint7')}joint8"
    joint8_id = mujoco.mj_name2id(
        model,
        mujoco.mjtObj.mjOBJ_JOINT,
        joint8_name,
    )
    if joint8_id < 0:
        raise ValueError(f"{actuator_name}: missing paired joint {joint8_name}")

    if not bool(model.jnt_limited[joint7_id]):
        raise ValueError(f"{joint7_name}: joint range is not limited")
    if not bool(model.jnt_limited[joint8_id]):
        raise ValueError(f"{joint8_name}: joint range is not limited")
    _assert_range(
        model.jnt_range[joint7_id],
        (0.0, _FINGER_LIMIT),
        f"{joint7_name} range",
    )
    _assert_range(
        model.jnt_range[joint8_id],
        (-_FINGER_LIMIT, 0.0),
        f"{joint8_name} range",
    )
    _verify_finger_equality(
        mujoco,
        model,
        joint7_id,
        joint8_id,
        actuator_name,
    )

    data = mujoco.MjData(model)
    joint7_qpos = int(model.jnt_qposadr[joint7_id])
    joint8_qpos = int(model.jnt_qposadr[joint8_id])
    expected_finger_position = _MIDPOINT_OPENING / _GRIPPER_GEAR
    data.qpos[joint7_qpos] = expected_finger_position
    data.qpos[joint8_qpos] = -expected_finger_position
    data.ctrl[actuator_id] = _MIDPOINT_OPENING
    mujoco.mj_forward(model, data)

    opening = float(data.qpos[joint7_qpos] - data.qpos[joint8_qpos])
    _assert_close(opening, _MIDPOINT_OPENING, f"{actuator_name} midpoint opening")
    _assert_close(
        float(data.actuator_length[actuator_id]),
        _MIDPOINT_OPENING,
        f"{actuator_name} midpoint actuator length",
    )
    _assert_close(
        float(data.ctrl[actuator_id] - data.actuator_length[actuator_id]),
        0.0,
        f"{actuator_name} midpoint servo error",
    )

    print(
        f"  gripper {actuator_name!r}: ctrl=[0, 0.105] gear=2; "
        f"midpoint 0.0525 -> {joint7_name}=0.02625, {joint8_name}=-0.02625"
    )


def verify_gripper_semantics(mujoco: Any, model: Any) -> int:
    """Verify every joint7/joint8 pair and return the matched actuator count."""
    pairs = _find_finger_pairs(mujoco, model)
    actuator_ids = _find_matching_gripper_actuators(mujoco, model, pairs)
    for actuator_id in actuator_ids:
        _verify_gripper_actuator(mujoco, model, actuator_id)
    return len(actuator_ids)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Piper MJCF loading, joints, and gripper semantics."
    )
    parser.add_argument("--xml", required=True, help="Path to scene.xml or main MJCF")
    args = parser.parse_args()
    xml_path = os.path.abspath(args.xml)
    if not os.path.isfile(xml_path):
        print(f"File not found: {xml_path}", file=sys.stderr)
        return 2

    try:
        mujoco = importlib.import_module("mujoco")
    except ImportError:
        print("Install mujoco: pip install mujoco", file=sys.stderr)
        return 1

    try:
        model = mujoco.MjModel.from_xml_path(xml_path)
    except Exception as error:  # noqa: BLE001 - MuJoCo load errors vary by version.
        print(f"Failed to load MJCF: {error}", file=sys.stderr)
        return 1

    print(f"ok load: {xml_path}")
    print(
        f"  nbody={model.nbody} njoint={model.njnt} nq={model.nq} "
        f"nv={model.nv} nu={model.nu}"
    )

    joint_types = {0: "free", 1: "ball", 2: "slide", 3: "hinge"}
    for joint_id in range(model.njnt):
        name = _object_name(
            mujoco,
            model,
            mujoco.mjtObj.mjOBJ_JOINT,
            joint_id,
        )
        joint_type = int(model.jnt_type[joint_id])
        type_name = joint_types.get(joint_type, str(joint_type))
        qpos_address = int(model.jnt_qposadr[joint_id])
        range_summary = ""
        if model.jnt_limited[joint_id]:
            lower, upper = model.jnt_range[joint_id]
            range_summary = f" range=[{lower:.6g}, {upper:.6g}]"
        print(
            f"  joint[{joint_id}] {name!r} type={type_name} "
            f"qposadr={qpos_address}{range_summary}"
        )

    try:
        gripper_actuator_count = verify_gripper_semantics(mujoco, model)
    except ValueError as error:
        print(f"Gripper verification failed: {error}", file=sys.stderr)
        return 1

    print(f"ok gripper semantics: verified {gripper_actuator_count} actuator(s)")
    print("  tip: compare names/order with simulator.yaml / TaskRobot actuator_order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
