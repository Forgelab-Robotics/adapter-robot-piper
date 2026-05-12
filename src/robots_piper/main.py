#!/usr/bin/env python3
"""Piper 统一入口：dora 节点（run）与端口子命令。打包后支持 robot_piper run | gripper-cycle | list-ports | ...。"""

from __future__ import annotations

import sys

import typer
from forge_common import get_logger

logger = get_logger(__name__)

app = typer.Typer(
    name="robot_piper",
    help="Piper 机械臂 dora 节点与 CAN 端口工具。无子命令时默认运行节点；可用 run / gripper-cycle / list-ports / activate-ports / check-role / set-role。",
    no_args_is_help=False,
)


def _run_node(config_path: str | None) -> int:
    """运行 Piper dora 节点。"""
    from robot_core import run_dora_robot_node

    from config import load_config
    from driver import PiperDriver

    config = load_config(config_path=config_path)
    driver = PiperDriver(
        port=config.port,
        is_follower=config.is_follower,
        auto_connect=True,
    )
    return run_dora_robot_node(
        driver,
        actuator_order=driver.actuator_order,
        is_follower=bool(getattr(config, "is_follower", True)),
        debug=bool(getattr(config, "debug", False)),
    )


@app.callback(invoke_without_command=True)
def _main(
    ctx: typer.Context,
    config: str | None = typer.Option(None, "--config", help="YAML 配置文件路径"),
) -> None:
    """无子命令时默认运行 Piper dora 节点。"""
    if ctx.invoked_subcommand is not None:
        return
    sys.exit(_run_node(config_path=config))


@app.command()
def run(
    config: str | None = typer.Option(None, "--config", help="YAML 配置文件路径"),
) -> None:
    """运行 Piper dora 节点。"""
    sys.exit(_run_node(config_path=config))


@app.command()
def gripper_cycle(
    port: str = typer.Argument("can0", help="CAN 端口名"),
    duration: float = typer.Option(15.0, "-d", "--duration", help="运行秒数"),
) -> None:
    """在指定 CAN 端口上运行夹爪开合循环，用于确认端口与机械臂对应关系。"""
    from piper_ports import cmd_gripper_cycle

    sys.exit(cmd_gripper_cycle(port=port, duration=duration))


@app.command("list-ports")
def list_ports(
    json_output: bool = typer.Option(True, "--json/--no-json", help="输出 JSON"),
) -> None:
    """列出 CAN 接口。"""
    from piper_ports import cmd_list_ports

    sys.exit(cmd_list_ports(use_json=json_output))


@app.command("activate-ports")
def activate_ports(
    json_output: bool = typer.Option(True, "--json/--no-json", help="输出 JSON"),
) -> None:
    """激活所有 CAN 接口（需 pkexec）。"""
    from piper_ports import cmd_activate_ports

    sys.exit(cmd_activate_ports(use_json=json_output))


@app.command("check-role")
def check_role(
    ports: list[str] = typer.Argument(None, help="CAN 端口列表；不传则通过 list-ports 查询后检测"),
    json_output: bool = typer.Option(True, "--json/--no-json", help="输出 JSON"),
    wait: float = typer.Option(2.0, "--wait", help="等待响应秒数"),
) -> None:
    """主从检测：对每个 CAN 发 0x4AF，根据是否收到 0x2A1 判 Slave/Master/Offline。"""
    from piper_ports import cmd_check_role

    sys.exit(cmd_check_role(ports=ports or [], use_json=json_output, wait=wait))


@app.command("set-role")
def set_role(
    port: str = typer.Argument(..., help="CAN 端口名（如 can0）"),
    role: str = typer.Argument(..., help="主/从臂：master 或 slave"),
    json_output: bool = typer.Option(True, "--json/--no-json", help="输出 JSON"),
) -> None:
    """传入端口参数设置机械臂为主臂或从臂。"""
    from piper_ports import cmd_set_role

    if role not in ("master", "slave"):
        logger.error("role 必须为 master 或 slave，当前为: %s", role)
        sys.exit(2)
    sys.exit(cmd_set_role(port=port, role=role, use_json=json_output))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
