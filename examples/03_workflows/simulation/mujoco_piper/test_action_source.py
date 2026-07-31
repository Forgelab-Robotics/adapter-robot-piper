#!/usr/bin/env python3
"""Agilex Piper sweep source with actuator-specific SI position ranges."""

from __future__ import annotations

import argparse
import sys
import time

from dora import Node
from forge_msgs import JointCommand

_SWEEP_RANGES = (
    ("joint1", -1.2, 1.2),
    ("joint2", 0.0, 1.2),
    ("joint3", -1.2, 0.0),
    ("joint4", -1.2, 1.2),
    ("joint5", -1.0, 1.0),
    ("joint6", -1.2, 1.2),
    ("gripper", 0.0, 0.105),
)


def build_sweep_command(elapsed_seconds: float, joint_seconds: float) -> JointCommand:
    """Build a full command while sweeping one actuator within its valid range."""
    cycle_seconds = joint_seconds * len(_SWEEP_RANGES)
    cycle_position = elapsed_seconds % cycle_seconds
    active_index = int(cycle_position // joint_seconds)
    phase = (cycle_position % joint_seconds) / joint_seconds

    positions = [0.0] * len(_SWEEP_RANGES)
    _, lower, upper = _SWEEP_RANGES[active_index]
    positions[active_index] = upper + (lower - upper) * phase
    return JointCommand(
        name=[name for name, _, _ in _SWEEP_RANGES],
        mode="position",
        position=positions,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--joint-seconds",
        type=float,
        default=2.0,
        help="Seconds for each actuator to sweep from its upper to lower target.",
    )
    args = parser.parse_args()
    if args.joint_seconds <= 0.0:
        parser.error("--joint-seconds must be greater than zero")
    return args


def main() -> int:
    args = _parse_args()
    node = Node()
    start = time.monotonic()

    for event in node:
        match event["type"]:
            case "INPUT" if event["id"] == "tick":
                command = build_sweep_command(
                    time.monotonic() - start,
                    args.joint_seconds,
                )
                node.send_output("action", command.to_arrow())
            case "STOP":
                break
            case "ERROR":
                print(
                    f"[piper_test_action_source] {event.get('error', 'unknown error')}",
                    file=sys.stderr,
                )
                return 1
            case _:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
