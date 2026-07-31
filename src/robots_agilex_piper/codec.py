"""Agilex Piper gripper conversions at the Forge/SDK boundary."""

from __future__ import annotations

import math

GRIPPER_SDK_UNITS_PER_METER = 1_000_000
GRIPPER_MIN_OPENING_METERS = 0.0
GRIPPER_MAX_OPENING_METERS = 0.105
GRIPPER_MIN_SDK = 0
GRIPPER_MAX_SDK = 105_000


def validate_gripper_opening_meters(opening_meters: float) -> float:
    """Validate and normalize a two-finger total opening expressed in meters."""
    opening = float(opening_meters)
    if not math.isfinite(opening) or not (
        GRIPPER_MIN_OPENING_METERS <= opening <= GRIPPER_MAX_OPENING_METERS
    ):
        raise ValueError(
            "gripper total opening must be between "
            f"{GRIPPER_MIN_OPENING_METERS} and {GRIPPER_MAX_OPENING_METERS} meters; "
            f"got {opening_meters!r}. Forge gripper values are meters, not millimeters."
        )
    return opening


def gripper_meters_to_sdk(opening_meters: float) -> int:
    """Encode a Forge total opening in meters as Piper SDK 1e-6 m units."""
    opening = validate_gripper_opening_meters(opening_meters)
    return round(opening * GRIPPER_SDK_UNITS_PER_METER)


def gripper_sdk_to_meters(sdk_value: int) -> float:
    """Decode observed SDK units without hiding out-of-range hardware feedback."""
    if isinstance(sdk_value, bool) or not isinstance(sdk_value, int):
        raise TypeError(f"gripper SDK value must be an integer; got {sdk_value!r}")
    return sdk_value / GRIPPER_SDK_UNITS_PER_METER
