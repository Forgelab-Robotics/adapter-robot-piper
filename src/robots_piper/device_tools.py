"""Piper CAN 设备 CLI（list / activate / test），JSON 格式遵循 forge_robot.device_tools。"""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Literal

from forge_robot.device_tools import (
    address_info,
    error_result,
    ok_result,
    print_json_result,
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
_ENABLE_PIPER_TIMEOUT_SEC = 2.0


def _query_can_devices() -> list[dict]:
    """查询 CAN 接口，返回 address_info 列表。"""
    try:
        out = subprocess.run(
            ["bash", "-c", _LIST_CAN_SCRIPT],
            capture_output=True,
            text=True,
            timeout=10,
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
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
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
    except Exception as e:
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


def _verify_piper_online(port: str, wait_s: float = 0.08) -> bool:
    """用 piper_sdk 校验设备是否真正在线。"""
    try:
        from piper_sdk import C_PiperInterface_V2

        piper = C_PiperInterface_V2(port)
        piper.ConnectPort()
        time.sleep(wait_s)
        try:
            maxspd = piper.GetAllMotorAngleLimitMaxSpd()
            return maxspd.time_stamp != 0
        finally:
            piper.DisconnectPort()
    except Exception:
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
        except Exception:
            role = "Offline"

        if role in ("Slave", "Master") and not _verify_piper_online(can_interface):
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
        piper = C_PiperInterface_V2(port)
        piper.ConnectPort()
        time.sleep(0.2)
        piper.MasterSlaveConfig(linkage, 0, 0, 0)
        piper.DisconnectPort()
        result = ok_result(
            message=f"端口 {port} 已设置为 {role} 臂",
            devices=[address_info(name=port, role=role)],
        )
        exit_code = 0
    except Exception as e:
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

    piper = C_PiperInterface_V2(port)
    piper.ConnectPort()
    piper.MasterSlaveConfig(_LINKAGE_SLAVE, 0, 0, 0)

    time.sleep(0.5)
    piper.ModeCtrl(0x01, 0x01, 30, 0x00)
    time.sleep(0.5)

    def wait_enable() -> bool:
        deadline = time.monotonic() + _ENABLE_PIPER_TIMEOUT_SEC
        while not piper.EnablePiper():
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)
        return True

    if not wait_enable():
        print(
            f"EnablePiper 在 {_ENABLE_PIPER_TIMEOUT_SEC:.1f}s 内超时，正在 ResetPiper 并重试一次...",
            file=sys.stderr,
        )
        piper.ResetPiper()
        if not wait_enable():
            print(
                "ResetPiper 后 EnablePiper 仍失败，请检查机械臂状态与连接。",
                file=sys.stderr,
            )
            piper.DisconnectPort()
            return 1
    piper.EnableArm(7)

    piper.JointCtrl(0, 0, 0, 0, 0, 0)
    piper.GripperCtrl(0, 1000, 0x01, 0)
    time.sleep(0.5)

    range_hw = int(0.05 * 1000 * 1000)
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
            piper.GripperCtrl(abs(range_val), 1000, 0x01, 0)
            time.sleep(0.005)
    finally:
        piper.GripperCtrl(0, 1000, 0x01, 0)
        time.sleep(0.2)
        piper.DisconnectPort()
    return 0
