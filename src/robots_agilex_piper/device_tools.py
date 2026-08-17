# SPDX-License-Identifier: Apache-2.0

"""Agilex Piper CAN 设备 CLI（list / activate / test），JSON 格式遵循 forge_robot.device_tools。"""

from __future__ import annotations

import json
import math
import select
import subprocess
import sys
import termios
import time
import tty
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from forge_robot.device_tools import (
    address_info,
    error_result,
    ok_result,
    print_json_result,
)

from robots_agilex_piper.codec import (
    gripper_meters_to_sdk,
    gripper_sdk_to_meters,
)

_LIST_CAN_SCRIPT = r"""
for iface in $(ip -br link show type can 2>/dev/null | awk '{print $1}'); do
    BUS_INFO=$(ethtool -i "$iface" 2>/dev/null | grep "bus-info" | awk '{print $2}')
    STATUS=$(ip -br link show "$iface" 2>/dev/null | awk '{print $2}')
    if [ -n "$BUS_INFO" ]; then
        echo "$iface $BUS_INFO $STATUS"
    fi
done
"""

_ACTIVATE_CAN_SCRIPT = """
# Check if ethtool is installed.
if ! dpkg -l | grep -q "ethtool"; then
    echo "Error: ethtool not detected in the system."
    exit 1
fi

# Check if can-utils is installed.
if ! dpkg -l | grep -q "can-utils"; then
    echo "Error: can-utils not detected in the system."
    exit 1
fi

for iface in $(ip -br link show type can | awk '{print $1}'); do
    BUS_INFO=$(ethtool -i "$iface" 2>/dev/null | grep "bus-info" | awk '{print $2}')
    if [ -n "$BUS_INFO" ]; then
        echo "Activating interface $iface ($BUS_INFO)..."
        sudo ip link set "$iface" down
        sudo ip link set "$iface" type can bitrate 1000000
        sudo ip link set "$iface" up
    fi
done
echo "All CAN interfaces processed."
"""

_LINKAGE_MASTER = 0xFA
_LINKAGE_SLAVE = 0xFC
_ENABLE_AGILEX_PIPER_TIMEOUT_SEC = 2.0
_ANGLE_SCALE = 1000.0
_EE_MILLIMETERS_SCALE = 1000.0
_JOINT_NAMES = ("joint1", "joint2", "joint3", "joint4", "joint5", "joint6")
_DEFAULT_WATCH_STATE_SAVE_PATH = "agilex_piper_watch_state.jsonl"


def _query_can_devices() -> list[dict]:
    """查询 CAN 接口，返回 address_info 列表。"""
    try:
        out = subprocess.run(
            ["bash", "-c", _LIST_CAN_SCRIPT],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        devices: list[dict] = []
        if out.returncode == 0 and out.stdout.strip():
            for line in out.stdout.strip().split("\n"):
                parts = line.strip().split()
                if len(parts) >= 3:
                    devices.append(
                        address_info(
                            name=parts[0],
                            address=parts[1],
                            status=parts[2].upper() == "UP",
                        )
                    )
        return devices
    except Exception:  # noqa: BLE001 - discovery failures mean no devices.
        return []


def get_device_names() -> list[str]:
    """返回 CAN 设备名列表（与 list-devices 一致）。"""
    return [d["name"] for d in _query_can_devices()]


def _print_list_devices_text(devices: list[dict]) -> None:
    if not devices:
        print("(无 CAN 接口或超时)")
        return
    for d in devices:
        flag = "UP" if d.get("status") else "DOWN"
        print(f"  {d['name']} {d['address']} {flag}")


def cmd_list_devices(*, use_json: bool = True) -> int:
    """列出 CAN 接口。"""
    devices = _query_can_devices()
    result = ok_result(devices=devices)
    if use_json:
        print_json_result(result)
    else:
        _print_list_devices_text(devices)
    return 0


def cmd_activate_devices(*, use_json: bool = True) -> int:
    """激活所有 CAN 接口（需 pkexec）。"""
    try:
        proc = subprocess.run(
            ["pkexec", "bash", "-c", _ACTIVATE_CAN_SCRIPT],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        message = stdout or stderr or "All CAN interfaces processed."
        devices = _query_can_devices()

        if proc.returncode == 0:
            result = ok_result(message=message, devices=devices)
            exit_code = 0
        else:
            result = error_result(
                message or "Activation failed.",
                devices=devices,
            )
            exit_code = 1
    except FileNotFoundError:
        result = error_result("pkexec not found", devices=[])
        exit_code = 1
    except subprocess.TimeoutExpired:
        result = error_result("Activation timed out", devices=[])
        exit_code = 1
    except Exception as e:  # noqa: BLE001 - CLI returns structured errors.
        result = error_result(str(e), devices=[])
        exit_code = 1

    if use_json:
        print_json_result(result)
    else:
        if result["ok"]:
            print(result["message"])
        else:
            print(result["message"], file=sys.stderr)
    return exit_code


def _scaled_radians(raw_value: float) -> float:
    return math.radians(float(raw_value) / _ANGLE_SCALE)


def _scaled_ee_mm(raw_value: float) -> float:
    return float(raw_value) / _EE_MILLIMETERS_SCALE


def _scaled_gripper_m(raw_value: int) -> float:
    return gripper_sdk_to_meters(raw_value)


def _read_joint_and_gripper(
    agilex_piper: object,
) -> tuple[dict[str, float], float]:
    joint_msg = agilex_piper.GetArmJointMsgs()
    gripper_msg = agilex_piper.GetArmGripperMsgs()
    joints = joint_msg.joint_state
    gripper = gripper_msg.gripper_state

    joint_values = {
        "joint1": _scaled_radians(joints.joint_1),
        "joint2": _scaled_radians(joints.joint_2),
        "joint3": _scaled_radians(joints.joint_3),
        "joint4": _scaled_radians(joints.joint_4),
        "joint5": _scaled_radians(joints.joint_5),
        "joint6": _scaled_radians(joints.joint_6),
    }
    return joint_values, _scaled_gripper_m(gripper.grippers_angle)


def _read_ee_pose(agilex_piper: object) -> dict[str, float]:
    end_pose_msg = agilex_piper.GetArmEndPoseMsgs()
    end_pose = end_pose_msg.end_pose
    return {
        "x": _scaled_ee_mm(end_pose.X_axis),
        "y": _scaled_ee_mm(end_pose.Y_axis),
        "z": _scaled_ee_mm(end_pose.Z_axis),
        "rx": _scaled_radians(end_pose.RX_axis),
        "ry": _scaled_radians(end_pose.RY_axis),
        "rz": _scaled_radians(end_pose.RZ_axis),
    }


def _read_watch_state(
    agilex_piper: object,
    *,
    port: str,
) -> dict:
    joints, gripper = _read_joint_and_gripper(agilex_piper)
    ee = _read_ee_pose(agilex_piper)
    return {
        "port": port,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "joints": joints,
        "gripper": gripper,
        "ee": ee,
    }


def _append_watch_state_jsonl(frame: dict, save_path: str | Path) -> Path:
    path = Path(save_path)
    with path.open("a", encoding="utf-8") as f:
        json.dump(frame, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    return path


@contextmanager
def _watch_state_keypress_mode(enabled: bool) -> Iterator[bool]:
    if not enabled or not sys.stdin.isatty():
        yield False
        return

    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)


def _read_pressed_keys(enabled: bool) -> list[str]:
    if not enabled:
        return []

    keys: list[str] = []
    while True:
        readable, _, _ = select.select([sys.stdin], [], [], 0)
        if not readable:
            return keys
        key = sys.stdin.read(1)
        if not key:
            return keys
        keys.append(key)


def _format_watch_state(
    frame: dict,
    *,
    save_path: str | Path,
    save_count: int,
    save_message: str | None,
    keypress_enabled: bool,
) -> str:
    lines = [
        "Agilex Piper state monitor",
        f"port={frame['port']} time={frame['timestamp']}",
        f"press s to save current frame -> {save_path}",
        "",
        "joints (radians)",
    ]
    joints = frame["joints"]
    for name in _JOINT_NAMES:
        lines.append(f"  {name:<7} {joints[name]:> .6f}")
    lines.extend(
        [
            "",
            f"gripper total opening (m) {frame['gripper']:> .6f}",
            "",
            "ee position (mm)",
            f"  x  {frame['ee']['x']:> .3f}",
            f"  y  {frame['ee']['y']:> .3f}",
            f"  z  {frame['ee']['z']:> .3f}",
            "",
            "ee orientation (radians)",
            f"  rx {frame['ee']['rx']:> .6f}",
            f"  ry {frame['ee']['ry']:> .6f}",
            f"  rz {frame['ee']['rz']:> .6f}",
        ]
    )
    if save_message is not None:
        lines.extend(["", save_message])
    elif save_count > 0:
        lines.extend(["", f"saved frames: {save_count}"])
    if not keypress_enabled:
        lines.extend(["", "keypress disabled because stdin is not a TTY"])
    return "\n".join(lines)


def cmd_watch_state(
    port: str = "can0",
    *,
    hz: float = 10.0,
    save_path: str | Path = _DEFAULT_WATCH_STATE_SAVE_PATH,
) -> int:
    """只读持续显示指定 CAN 端口的关节、夹爪和末端位姿状态。"""
    if hz <= 0:
        print("--hz 必须大于 0", file=sys.stderr)
        return 2

    from piper_sdk import C_PiperInterface_V2

    agilex_piper = C_PiperInterface_V2(port)
    period = 1.0 / hz
    save_count = 0
    save_message: str | None = None
    save_message_deadline = 0.0

    try:
        agilex_piper.ConnectPort()
        with _watch_state_keypress_mode(True) as keypress_enabled:
            while True:
                frame = _read_watch_state(
                    agilex_piper,
                    port=port,
                )
                for key in _read_pressed_keys(keypress_enabled):
                    if key.lower() == "s":
                        try:
                            saved_path = _append_watch_state_jsonl(frame, save_path)
                        except OSError as e:
                            save_message = f"save failed: {e}"
                        else:
                            save_count += 1
                            save_message = f"saved #{save_count} to {saved_path}"
                        save_message_deadline = time.monotonic() + 3.0

                current_save_message = (
                    save_message if time.monotonic() < save_message_deadline else None
                )
                output = _format_watch_state(
                    frame,
                    save_path=save_path,
                    save_count=save_count,
                    save_message=current_save_message,
                    keypress_enabled=keypress_enabled,
                )
                print("\033[2J\033[H" + output, end="", flush=True)
                time.sleep(period)
    except KeyboardInterrupt:
        print()
        return 0
    finally:
        agilex_piper.DisconnectPort()


def _verify_agilex_piper_online(port: str, wait_s: float = 0.08) -> bool:
    """用 piper_sdk 校验设备是否真正在线。"""
    try:
        from piper_sdk import C_PiperInterface_V2

        agilex_piper = C_PiperInterface_V2(port)
        agilex_piper.ConnectPort()
        time.sleep(wait_s)
        try:
            maxspd = agilex_piper.GetAllMotorAngleLimitMaxSpd()
            return maxspd.time_stamp != 0
        finally:
            agilex_piper.DisconnectPort()
    except Exception:  # noqa: BLE001 - hardware probe failures mean offline.
        return False


def cmd_check_role(
    ports: list[str] | None = None,
    *,
    use_json: bool = True,
    wait: float = 2.0,
) -> int:
    """主从检测：对每个 CAN 发 0x4AF，根据响应判 Slave/Master/Offline。"""
    if not ports:
        ports = get_device_names()

    try:
        import can
    except ImportError:
        result = error_result("python-can 未安装", devices=[])
        if use_json:
            print_json_result(result)
        else:
            print(result["message"], file=sys.stderr)
        return 1

    devices: list[dict] = []
    for can_interface in ports:
        role = "Offline"
        try:
            bus = can.interface.Bus(channel=can_interface, bustype="socketcan")
            msg = can.Message(
                arbitration_id=0x4AF,
                data=[0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                dlc=8,
                is_extended_id=False,
            )
            bus.send(msg)
            start = time.monotonic()
            while (time.monotonic() - start) < wait:
                recv = bus.recv(timeout=1.0)
                if recv is not None:
                    if recv.arbitration_id == 0x2A1:
                        role = "Slave"
                        break
                    role = "Master"
            bus.shutdown()
        except Exception:  # noqa: BLE001 - CAN probe failures mean offline.
            role = "Offline"

        if role in ("Slave", "Master") and not _verify_agilex_piper_online(
            can_interface
        ):
            role = "Offline"

        devices.append(
            address_info(
                name=can_interface,
                status=role != "Offline",
                role=role,
            )
        )

    result = ok_result(devices=devices)
    if use_json:
        print_json_result(result)
    else:
        for d in devices:
            print(f"  {d['name']}: {d.get('role', 'Unknown')}")
    return 0


def cmd_set_role(
    port: str,
    role: Literal["master", "slave"],
    *,
    use_json: bool = True,
) -> int:
    """设置指定 CAN 端口机械臂为主臂或从臂。"""
    try:
        from piper_sdk import C_PiperInterface_V2
    except ImportError:
        result = error_result("piper_sdk 未安装")
        if use_json:
            print_json_result(result)
        else:
            print(result["message"], file=sys.stderr)
        return 1

    linkage = _LINKAGE_MASTER if role == "master" else _LINKAGE_SLAVE
    try:
        agilex_piper = C_PiperInterface_V2(port)
        agilex_piper.ConnectPort()
        time.sleep(0.2)
        agilex_piper.MasterSlaveConfig(linkage, 0, 0, 0)
        agilex_piper.DisconnectPort()
        result = ok_result(
            message=f"端口 {port} 已设置为 {role} 臂",
            devices=[address_info(name=port, role=role)],
        )
        exit_code = 0
    except Exception as e:  # noqa: BLE001 - CLI returns structured errors.
        result = error_result(
            str(e),
            devices=[address_info(name=port, role=role)],
        )
        exit_code = 1

    if use_json:
        print_json_result(result)
    else:
        if result["ok"]:
            print(result["message"])
        else:
            print(f"设置失败: {result['message']}", file=sys.stderr)
    return exit_code


def cmd_test(port: str = "can0", duration: float = 15.0) -> int:
    """
    夹爪循环：连接指定 CAN 端口，短时运行夹爪开合，
    便于确认该设备与机械臂的对应关系。
    """
    from piper_sdk import C_PiperInterface_V2

    agilex_piper = C_PiperInterface_V2(port)
    agilex_piper.ConnectPort()
    agilex_piper.MasterSlaveConfig(_LINKAGE_SLAVE, 0, 0, 0)

    time.sleep(0.5)
    agilex_piper.ModeCtrl(0x01, 0x01, 30, 0x00)
    time.sleep(0.5)

    def wait_enable() -> bool:
        deadline = time.monotonic() + _ENABLE_AGILEX_PIPER_TIMEOUT_SEC
        while not agilex_piper.EnablePiper():
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)
        return True

    if not wait_enable():
        print(
            f"EnablePiper 在 {_ENABLE_AGILEX_PIPER_TIMEOUT_SEC:.1f}s 内超时，正在 ResetPiper 并重试一次...",
            file=sys.stderr,
        )
        agilex_piper.ResetPiper()
        if not wait_enable():
            print(
                "ResetPiper 后 EnablePiper 仍失败，请检查机械臂状态与连接。",
                file=sys.stderr,
            )
            agilex_piper.DisconnectPort()
            return 1
    agilex_piper.EnableArm(7)

    agilex_piper.JointCtrl(0, 0, 0, 0, 0, 0)
    agilex_piper.GripperCtrl(0, 1000, 0x01, 0)
    time.sleep(0.5)

    range_hw = gripper_meters_to_sdk(0.05)
    count = 0
    phase = 0
    step_loops = 300
    start = time.monotonic()

    try:
        while (time.monotonic() - start) < duration:
            if count == 0:
                phase = 0
            elif count == step_loops:
                phase = 1
            elif count == 2 * step_loops:
                phase = 2
                count = -1
            count += 1
            range_val = 0 if (phase == 0 or phase == 2) else range_hw
            agilex_piper.GripperCtrl(range_val, 1000, 0x01, 0)
            time.sleep(0.005)
    finally:
        agilex_piper.GripperCtrl(0, 1000, 0x01, 0)
        time.sleep(0.2)
        agilex_piper.DisconnectPort()
    return 0
