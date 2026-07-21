#!/usr/bin/env python3
"""Import the official Piper arm URDF and build task-robot variants."""

from __future__ import annotations

import argparse
import copy
import hashlib
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET

SOURCE_URDF = "piper_description_v100.urdf"
EXPECTED_SHA256 = "f45e318ad58339945e5845f4e7a6db22dd334c1f8d4f1f1004285b6fd3be8529"
PACKAGE_MESH_PREFIX = "package://piper_description/meshes/"
PROVENANCE = (
    f"Imported from piper_description 1.0.0; {SOURCE_URDF} "
    f"SHA-256 {EXPECTED_SHA256}; joint frames aligned to the delivered MJCF; "
    "fixed TCP at link6 +Z 0.13503 m."
)
MJCF_JOINT_ORIGINS = {
    "joint1": ("0 0 0.123", "0 0 -1.5708005694"),
    "joint2": ("0 0 0", "1.5708003268 0 -1.5708003268"),
    "joint3": ("0.28358 0.028726 0", "0 0 0.1009501011"),
    "joint4": ("-0.24221 0.068514 0", "-1.5707994075 0.0000007137 1.382599809"),
    "joint5": ("0 0 0", "1.5708005694 0 0"),
    "joint6": ("0 0.091 0.0014165", "1.5707920842 0 -3.1415926536"),
    "joint7": ("0 0 0.13503", "1.5708005694 0 3.1415926"),
    "joint8": ("0 0 0.13503", "-1.5708005694 0 3.1415926"),
}
HARDWARE_JOINT_LIMITS = {
    "joint1": ("-2.618", "2.618"),
    "joint2": ("0", "3.14"),
    "joint3": ("-2.967", "0"),
    "joint4": ("-1.745", "1.745"),
    "joint5": ("-1.32", "1.32"),
    "joint6": ("-2.094", "2.094"),
    "joint7": ("0", "0.0525"),
    "joint8": ("-0.0525", "0"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_package", type=Path, help="ROS piper_description package")
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Root containing robots/ and taskRobots/",
    )
    return parser.parse_args()


def load_arm(source_package: Path) -> ET.Element:
    source = source_package / "urdf" / SOURCE_URDF
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"Unexpected source URDF SHA-256: {digest}")
    robot = ET.parse(source).getroot()
    robot.set("name", "agilex_piper_with_gripper")
    for joint in robot.findall("joint"):
        joint_name = joint.get("name")
        if joint_name not in MJCF_JOINT_ORIGINS:
            continue
        origin = joint.find("origin")
        if origin is None:
            raise ValueError(f"Source joint has no origin: {joint_name}")
        xyz, rpy = MJCF_JOINT_ORIGINS[joint_name]
        origin.attrib.update({"xyz": xyz, "rpy": rpy})
    for joint_name, (lower, upper) in HARDWARE_JOINT_LIMITS.items():
        limit = robot.find(f"joint[@name='{joint_name}']/limit")
        if limit is None:
            raise ValueError(f"Source joint has no limit: {joint_name}")
        limit.attrib.update({"lower": lower, "upper": upper})
    joint8 = robot.find("joint[@name='joint8']")
    if joint8 is None:
        raise ValueError("Source URDF has no joint8")
    ET.SubElement(
        joint8,
        "mimic",
        {"joint": "joint7", "multiplier": "-1", "offset": "0"},
    )
    ET.SubElement(robot, "link", {"name": "tcp"})
    add_fixed_joint(robot, "tcp_joint", "link6", "tcp", "0 0 0.13503", "0 0 0")
    for mesh in robot.iter("mesh"):
        filename = mesh.get("filename")
        if filename and filename.startswith(PACKAGE_MESH_PREFIX):
            mesh.set("filename", f"meshes/{filename.removeprefix(PACKAGE_MESH_PREFIX)}")
    return robot


def prefixed_arm(arm: ET.Element, prefix: str) -> list[ET.Element]:
    elements = [copy.deepcopy(element) for element in arm]
    for element in elements:
        if element.tag in {"link", "joint"} and element.get("name"):
            element.set("name", f"{prefix}/{element.get('name')}")
        for tag in ("parent", "child"):
            for reference in element.iter(tag):
                if reference.get("link"):
                    reference.set("link", f"{prefix}/{reference.get('link')}")
        for mimic in element.iter("mimic"):
            if mimic.get("joint"):
                mimic.set("joint", f"{prefix}/{mimic.get('joint')}")
    return elements


def add_fixed_joint(
    robot: ET.Element,
    name: str,
    parent: str,
    child: str,
    xyz: str,
    rpy: str,
) -> None:
    joint = ET.SubElement(robot, "joint", {"name": name, "type": "fixed"})
    ET.SubElement(joint, "origin", {"xyz": xyz, "rpy": rpy})
    ET.SubElement(joint, "parent", {"link": parent})
    ET.SubElement(joint, "child", {"link": child})


def build_unimanual(arm: ET.Element) -> ET.Element:
    robot = ET.Element("robot", {"name": "unimanual_piper_withtable"})
    root = "unimanual_piper_withtable_baselink"
    ET.SubElement(robot, "link", {"name": root})
    robot.extend(copy.deepcopy(list(arm)))
    add_fixed_joint(robot, "piper_mount", root, "arm_base", "0.469 0.575 0", "0 0 3.1416")
    return robot


def build_bimanual(arm: ET.Element) -> ET.Element:
    robot = ET.Element("robot", {"name": "bimanual_piper_withtable_aloha"})
    root = "bimanual_piper_withtable_aloha_baselink"
    ET.SubElement(robot, "link", {"name": root})
    for prefix, x in (("robot_right", "-0.3"), ("robot_left", "0.3")):
        robot.extend(prefixed_arm(arm, prefix))
        add_fixed_joint(
            robot,
            f"{prefix}/piper_mount",
            root,
            f"{prefix}/arm_base",
            f"{x} 0.875 0",
            "0 0 -1.57079",
        )
    return robot


def write_robot(robot: ET.Element, destination: Path) -> None:
    robot.insert(0, ET.Comment(f" {PROVENANCE} "))
    ET.indent(robot, space="  ")
    ET.ElementTree(robot).write(destination, encoding="utf-8", xml_declaration=True)


def copy_distribution_files(
    source_package: Path,
    destination: Path,
    robot: ET.Element,
) -> None:
    mesh_dir = destination / "meshes"
    shutil.rmtree(mesh_dir, ignore_errors=True)
    mesh_dir.mkdir(parents=True, exist_ok=True)
    mesh_paths = {
        Path(filename.removeprefix("meshes/"))
        for mesh in robot.iter("mesh")
        if (filename := mesh.get("filename")) and filename.startswith("meshes/")
    }
    for relative_path in sorted(mesh_paths):
        target = mesh_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_package / "meshes" / relative_path, target)
    shutil.copy2(source_package.parents[1] / "LICENSE", destination / "LICENSE.piper_ros-noetic")


def main() -> None:
    args = parse_args()
    source_package = args.source_package.resolve()
    workspace = args.workspace_root.resolve()
    arm = load_arm(source_package)

    targets = (
        (
            workspace / "robots/agilex_piper/assets/urdf",
            "piper_with_gripper.urdf",
            arm,
        ),
        (
            workspace / "taskRobots/unimanual_piper_withtable/assets/urdf",
            "unimanual_piper_withtable.urdf",
            build_unimanual(arm),
        ),
        (
            workspace / "taskRobots/bimanual_piper_withtable_aloha/assets/urdf",
            "bimanual_piper_withtable_aloha.urdf",
            build_bimanual(arm),
        ),
    )
    for directory, filename, robot in targets:
        directory.mkdir(parents=True, exist_ok=True)
        copy_distribution_files(source_package, directory, robot)
        write_robot(robot, directory / filename)
        print(directory / filename)


if __name__ == "__main__":
    main()
