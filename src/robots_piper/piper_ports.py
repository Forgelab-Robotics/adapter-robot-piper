"""
CAN 端口工具：列出/激活接口、主从检测、夹爪循环。
由 main 统一入口以子命令调用：list-ports、activate-ports、check-role、gripper-cycle。

端口与真实机械臂的对应关系需用户现场观察（如使用 robot_piper gripper-cycle 观察哪只臂在动）并自行记录到配置。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from typing import Literal


_LIST_PORTS_SCRIPT = r"""
for iface in $(ip -br link show type can 2>/dev/null | awk '{print $1}'); do
    BUS_INFO=$(ethtool -i "$iface" 2>/dev/null | grep "bus-info" | awk '{print $2}')
    STATUS=$(ip -br link show "$iface" 2>/dev/null | awk '{print $2}')
    if [ -n "$BUS_INFO" ]; then
        echo "$iface $BUS_INFO $STATUS"
    fi
done
"""


def _query_ports() -> list[dict]:
    """内部：查询 CAN 接口列表，返回 [{ \"name\", \"address\", \"status\" }]，异常时返回 []。"""
    try:
        out = subprocess.run(
            ["bash", "-c", _LIST_PORTS_SCRIPT],
            capture_output=True,
            text=True,
            timeout=10,
        )
        ports: list[dict] = []
        if out.returncode == 0 and out.stdout.strip():
            for line in out.stdout.strip().split("\n"):
                parts = line.strip().split()
                if len(parts) >= 3:
                    ports.append({
                        "name": parts[0],
                        "address": parts[1],
                        "status": parts[2].upper() == "UP",
                    })
        return ports
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return []


def get_port_names() -> list[str]:
    """通过 list_ports 相同逻辑查询并返回 CAN 端口名列表。"""
    return [p["name"] for p in _query_ports()]


def cmd_list_ports(use_json: bool = True) -> int:
    """列出 CAN 接口，输出 JSON { \"ports\": [{ \"name\", \"address\", \"status\" }] }。"""
    ports = _query_ports()
    result = {"ports": ports}
    if use_json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        if ports:
            for p in ports:
                print(f"  {p['name']} {p['address']} {'UP' if p['status'] else 'DOWN'}")
        else:
            print("(无 CAN 接口或超时)")
    return 0


_ACTIVATE_PORTS_SCRIPT = """
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


def cmd_activate_ports(use_json: bool = True) -> int:
    """激活所有 CAN 接口（需 pkexec）。输出 JSON { \"ok\": bool, \"message\": str }。"""

    try:
        proc = subprocess.run(
            ["pkexec", "bash", "-c", _ACTIVATE_PORTS_SCRIPT],
            capture_output=True,
            text=True,
            timeout=60,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        if proc.returncode == 0:
            result = {"ok": True, "message": stdout.strip() or "All CAN interfaces processed."}
        else:
            result = {"ok": False, "message": f"{stdout}\n{stderr}".strip() or "Activation failed."}
        if use_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            if result["ok"]:
                print(result["message"])
            else:
                print(result["message"], file=sys.stderr)
        return 0
    except FileNotFoundError:
        result = {"ok": False, "message": "pkexec not found"}
        if use_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(result["message"], file=sys.stderr)
        return 0
    except subprocess.TimeoutExpired:
        result = {"ok": False, "message": "Activation timed out"}
        if use_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(result["message"], file=sys.stderr)
        return 0
    except Exception as e:
        result = {"ok": False, "message": str(e)}
        if use_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(str(e), file=sys.stderr)
        return 0



def _verify_piper_online(port: str, wait_s: float = 0.08) -> bool:
    """用 piper_sdk 读固件版本，若为 -0x4AF 表示设备未真正在线（如断电）。"""
    try:
        from piper_sdk import C_PiperInterface_V2

        piper = C_PiperInterface_V2(port)
        piper.ConnectPort()
        time.sleep(wait_s)
        try:
            # fw = piper.GetPiperFirmwareVersion()
            maxspd = piper.GetAllMotorAngleLimitMaxSpd()
            return maxspd.time_stamp != 0
        finally:
            piper.DisconnectPort()
    except Exception:
        return False


def cmd_check_role(
    ports: list[str] | None = None,
    use_json: bool = True,
    wait: float = 2.0,
) -> int:
    """主从检测：对每个 CAN 发 0x4AF，根据是否收到 0x2A1 判 Slave/Master/Offline；Slave/Master 再用固件版本校验以排除断电等无效回复。"""
    if not ports:
        ports = get_port_names()

    try:
        import can
    except ImportError:
        result = {"ports": []}
        if use_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print("(python-can 未安装，返回空)")
        return 0

    results: list[dict] = []
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
                    else:
                        role = "Master"
            bus.shutdown()
        except Exception:
            role = "Offline"
        # 设备断电时仍可能回复 0x4AF/0x2A1 但无意义，用固件版本校验
        if role in ("Slave", "Master") and not _verify_piper_online(can_interface):
            role = "Offline"
        results.append({"name": can_interface, "role": role})

    out = {"ports": results}
    if use_json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        for r in results:
            print(f"  {r['name']}: {r['role']}")
    return 0


# 主从配置：与 driver 中一致，0xFA 示教输入臂(主)，0xFC 运动输出臂(从)
_LINKAGE_MASTER = 0xFA
_LINKAGE_SLAVE = 0xFC


def cmd_set_role(
    port: str,
    role: Literal["master", "slave"],
    use_json: bool = True,
) -> int:
    """
    通过端口设置机械臂为主臂或从臂。
    连接指定 CAN 端口，调用 MasterSlaveConfig 后断开。
    """
    try:
        from piper_sdk import C_PiperInterface_V2
    except ImportError:
        result = {"ok": False, "message": "piper_sdk 未安装"}
        if use_json:
            print(json.dumps(result, ensure_ascii=False))
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
        result = {"ok": True, "port": port, "role": role}
        if use_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"端口 {port} 已设置为 {role} 臂")
        return 0
    except Exception as e:
        result = {"ok": False, "port": port, "role": role, "message": str(e)}
        if use_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"设置失败: {e}", file=sys.stderr)
        return 1


# EnablePiper 等待超时时间（秒），超时后尝试 ResetPiper 再重试一次
_ENABLE_PIPER_TIMEOUT_SEC = 2.0


def cmd_gripper_cycle(port: str = "can0", duration: float = 15.0) -> int:
    """
    夹爪循环：连接指定 CAN 端口，短时运行夹爪开合，
    便于用户在真实世界中确认该端口对应的机械臂。
    """
    from piper_sdk import C_PiperInterface_V2

    piper = C_PiperInterface_V2(port)
    piper.ConnectPort()
    piper.MasterSlaveConfig(0xFC, 0, 0, 0)

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

    range_hw = int(0.05 * 1000 * 1000)  # 0.05m = 50mm 对应硬件单位
    count = 0
    phase = 0  # 0: 闭合, 1: 张开, 2: 闭合
    step_loops = 300
    start = time.monotonic()
    last_print = 0.0

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
            now = time.monotonic()
            if now - last_print >= 0.5:
                last_print = now
            time.sleep(0.005)
    finally:
        piper.GripperCtrl(0, 1000, 0x01, 0)
        time.sleep(0.2)
        # piper.DisablePiper()
        piper.DisconnectPort()
    return 0
