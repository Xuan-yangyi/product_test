"""设备操作封装

封装现有 ops/Athena2_ops.py 和 ops/common_ops.py 的设备操作逻辑，
包括：进入串口 root、读取 SN、检查芯片类型、DDR 大小、MAC 地址等。
"""
import logging
import re
from typing import Optional, Tuple
from .serial_client import SerialClient

logger = logging.getLogger(__name__)


class DeviceOps:
    """设备操作类

    封装 Athena2 设备特定的操作，复用现有 ops 模块的逻辑。
    """

    def __init__(self, serial: SerialClient):
        self.serial = serial

    def enter_root(self) -> bool:
        """通过串口进入设备 root 权限"""
        output = self.serial.send_cmd("", timeout=3.0)
        if "#" in output:
            return True  # 已在 root

        self.serial.send_cmd("root", timeout=3.0, wait_str="Password:")
        output = self.serial.send_cmd("root", timeout=5.0)
        return "#" in output

    def get_device_sn(self) -> str:
        """读取设备序列号"""
        output = self.serial.send_cmd("fw_printenv serial_number 2>/dev/null", timeout=10.0)
        match = re.search(r"serial_number[= ](\S+)", output)
        if match:
            return match.group(1).strip()
        return ""

    def get_board_sn(self) -> str:
        """读取主板序列号"""
        output = self.serial.send_cmd("fw_printenv board_sn 2>/dev/null", timeout=10.0)
        match = re.search(r"board_sn[= ](\S+)", output)
        if match:
            return match.group(1).strip()
        return ""

    def get_chip_type(self) -> str:
        """读取芯片类型，如 BM1684, BM1688"""
        output = self.serial.send_cmd("cat /proc/cpuinfo | grep -i model | head -1", timeout=10.0)
        if "BM1688" in output:
            return "BM1688"
        if "BM1684" in output:
            return "BM1684"
        return "unknown"

    def get_ddr_size(self) -> str:
        """读取 DDR 大小"""
        output = self.serial.send_cmd("cat /proc/meminfo | grep MemTotal", timeout=10.0)
        match = re.search(r"(\d+)\s*kB", output)
        if match:
            size_kb = int(match.group(1))
            size_gb = size_kb / (1024 * 1024)
            return f"{size_gb:.1f}GB"
        return "unknown"

    def get_mac_address(self, interface: str = "eth0") -> str:
        """读取 MAC 地址"""
        output = self.serial.send_cmd(f"cat /sys/class/net/{interface}/address 2>/dev/null", timeout=10.0)
        mac = output.strip().split("\n")[0] if output.strip() else ""
        return mac

    def check_firmware_version(self, fw_version: str) -> bool:
        """检查固件版本"""
        output = self.serial.send_cmd("cat /etc/sophgo/build_version 2>/dev/null", timeout=10.0)
        return fw_version in output

    def is_chip(self, expected_chip: str) -> bool:
        """检查芯片类型是否匹配"""
        actual = self.get_chip_type()
        return actual.upper() == expected_chip.upper()

    def check_interface_exists(self, interface: str) -> bool:
        """检查网络接口是否存在"""
        output = self.serial.send_cmd(f"ip link show {interface} 2>/dev/null", timeout=10.0)
        return interface in output and "does not exist" not in output

    def check_device_file(self, path: str) -> bool:
        """检查设备文件是否存在"""
        output = self.serial.send_cmd(f"test -e {path} && echo EXISTS || echo NOT_FOUND", timeout=10.0)
        return "EXISTS" in output

    def check_usb_device(self) -> list:
        """检查 USB 设备"""
        output = self.serial.send_cmd("lsusb 2>/dev/null", timeout=10.0)
        devices = []
        for line in output.strip().split("\n"):
            if line.strip():
                devices.append(line.strip())
        return devices

    def check_nvme_drive(self) -> bool:
        """检查 NVMe 硬盘"""
        return self.check_device_file("/dev/nvme0n1")

    def check_emmc(self) -> bool:
        """检查 eMMC"""
        output = self.serial.send_cmd("cat /sys/block/mmcblk0/size 2>/dev/null", timeout=10.0)
        return output.strip().isdigit() and int(output.strip()) > 0
