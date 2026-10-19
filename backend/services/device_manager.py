"""设备管理服务

管理串口设备扫描和网络设备发现。
"""
import logging
import yaml
from typing import List, Dict
from ..engine.serial_client import SerialClient
from ..engine.ssh_client import SSHClient
from ..config import Config

logger = logging.getLogger(__name__)


class DeviceManager:
    """设备管理服务"""

    def scan_serial_devices(self) -> List[Dict]:
        """扫描所有串口设备"""
        return SerialClient.scan_ports()

    def _detect_device_info(self, ip: str) -> dict:
        """通过 SSH 检测设备信息

        执行 show_ddr 命令，解析芯片型号和 DDR 容量。
        同时读取 /factory/OEMconfig.ini 获取 MODULE_TYPE。
        执行 bm_version 获取 SDK 版本。
        Returns: {"device_type": str, "chip_model": str, "ddr_capacity": str, "module_type": str, "sdk_version": str}
        """
        import re
        info = {"device_type": "", "chip_model": "", "ddr_capacity": "", "module_type": "", "sdk_version": ""}
        try:
            ssh = SSHClient()
            # quiet=True: 网段内非板卡主机连接失败属预期，不打 ERROR 日志
            if not ssh.connect(ip, user="linaro", password="linaro", timeout=2, quiet=True):
                return info

            # 三条命令合并为一次 exec_cmd（单 channel、单次 sudo），减少往返
            # 用分隔标记切分结果：SHOW_DDR / OEMCONFIG / BM_VERSION
            MARK = "___SN_MONITOR_SPLIT___"
            merged_cmd = (
                f"show_ddr 2>/dev/null; echo {MARK}; "
                f"cat /factory/OEMconfig.ini 2>/dev/null; echo {MARK}; "
                f"bm_version 2>/dev/null"
            )
            merged_out, _, _ = ssh.exec_cmd(merged_cmd, timeout=15,
                                            sudo=True, sudo_password="linaro")
            parts = merged_out.split(MARK)
            if len(parts) != 3:
                # 设备命令异常时回退到原始单命令行为
                parts = [merged_out, "", ""]
            stdout, stdout2, stdout3 = parts[0], parts[1], parts[2]

            # 1. show_ddr — 芯片型号 & DDR 容量
            out = stdout.strip()
            out_lower = out.lower()
            if "bm1688" in out_lower:
                info["chip_model"] = "bm1688"
                info["device_type"] = "SE9"
            elif "cv186ah" in out_lower:
                info["chip_model"] = "cv186ah"
                info["device_type"] = "SE9"
            elif "cv84x6" in out_lower:
                info["chip_model"] = "cv84x6"
                info["device_type"] = "SE12"
            elif out:
                m = re.search(r'(bm\d+|cv\w+)', out_lower)
                if m:
                    info["chip_model"] = m.group(1)
                    info["device_type"] = "其他"

            m = re.search(r'SIZE\s*:\s*(\d+)\s*(MB|GB)', out, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                unit = m.group(2).upper()
                if unit == 'MB':
                    val = val // 1024
                if val > 0:
                    info["ddr_capacity"] = f"{val}GB"

            # 2. OEMconfig.ini — MODULE_TYPE（已在合并命令中取回）
            oem_out = stdout2.strip()
            if oem_out:
                # 正则提取（跳过 flag 值如 INTERFACE_FLAG、0x01 等）
                m = re.search(r'MODULE_TYPE\s*=\s*(\S+)', oem_out)
                if m:
                    val = m.group(1)
                    # 过滤掉明显不是型号值的 flag 类字符串
                    if val not in ("INTERFACE_FLAG",) and not re.match(r'^0x[0-9a-fA-F]+$', val):
                        info["module_type"] = val

            # 3. bm_version — SDK 版本，提取版本号如 "2.2"（已在合并命令中取回）
            ssh.close()
            sdk_out = stdout3.strip()
            if sdk_out:
                # 从 "SophonSDK(BM1688) 2.2" 中提取版本号
                m = re.search(r'(\d+\.\d+(?:\.\d+)?)', sdk_out)
                if m:
                    info["sdk_version"] = f"SDK {m.group(1)}"
                else:
                    info["sdk_version"] = sdk_out

        except Exception:
            pass
        return info

    def _fill_device_types(self, devices: List[Dict]):
        """并行检测在线设备的类型、芯片和 DDR 容量"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def detect(dev: dict):
            info = self._detect_device_info(dev["ip"])
            dev["device_type"] = info["device_type"]
            dev["chip_model"] = info["chip_model"]
            dev["ddr_capacity"] = info["ddr_capacity"]
            dev["module_type"] = info["module_type"]
            dev["sdk_version"] = info["sdk_version"]

        with ThreadPoolExecutor(max_workers=32) as executor:
            futures = [executor.submit(detect, d) for d in devices]
            for future in as_completed(futures):
                future.result()

    def scan_network_devices(self) -> List[Dict]:
        """扫描网络中的设备

        读取 network_config.yaml 中的网段配置，
        扫描在线设备并检测设备类型。
        """
        config = self._load_network_config()
        network_segment = config.get("network_segment", "")
        devices = []

        if not network_segment:
            return devices

        # 扫描网段（例如 192.168.1.）
        # 并行探测：串行 254 个 IP × 2s 最坏 508s，改为 32 并发后约 16s
        from concurrent.futures import ThreadPoolExecutor, as_completed
        base_ip = network_segment.rsplit(".", 1)[0]
        candidates = [f"{base_ip}.{i}" for i in range(1, 255)]

        def probe(ip: str) -> dict | None:
            # 先用 ICMP ping 判活，再确认 22 端口开放；两者都过才算候选设备，
            # 避免把网关/办公 PC 等非产测主机当作设备去 SSH 探测
            if not SSHClient.is_ip_alive(ip, timeout=2):
                return None
            if not SSHClient.is_ssh_alive(ip, timeout=1):
                return None
            return {"ip": ip, "hostname": "", "status": "online", "device_type": ""}

        with ThreadPoolExecutor(max_workers=32) as executor:
            futures = [executor.submit(probe, ip) for ip in candidates]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    devices.append(result)

        # 并行检测设备类型
        if devices:
            self._fill_device_types(devices)

        return devices

    def batch_scan_ips(self, ips: List[str], timeout: int = 2) -> List[Dict]:
        """批量扫描 IP 地址，返回在线设备列表并检测设备类型"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def check_ip(ip: str) -> dict | None:
            # ping 判活 + 22 端口确认，过滤掉网关/PC 等非产测主机
            if not SSHClient.is_ip_alive(ip, timeout=timeout):
                return None
            if not SSHClient.is_ssh_alive(ip, timeout=1):
                return None
            return {"ip": ip, "hostname": "", "status": "online", "device_type": ""}

        devices = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(check_ip, ip): ip for ip in ips}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    devices.append(result)

        # 并行检测设备类型
        if devices:
            self._fill_device_types(devices)

        return devices

    def get_device_info_via_ssh(self, ip: str, user: str = "root", password: str = "") -> dict:
        """通过 SSH 获取设备信息"""
        info = {"ip": ip, "hostname": "", "device_type": ""}
        try:
            with SSHClient() as ssh:
                if ssh.connect(ip, user, password, timeout=5):
                    stdout, _, _ = ssh.exec_cmd("hostname", timeout=5)
                    info["hostname"] = stdout.strip()
                    stdout, _, _ = ssh.exec_cmd("cat /proc/cpuinfo | grep -i model | head -1", timeout=5)
                    info["device_type"] = stdout.strip()
        except Exception as e:
            logger.error(f"获取设备信息失败 {ip}: {e}")
        return info

    def _load_network_config(self) -> dict:
        """加载网络配置"""
        cfg_path = Config.CFG_DIR / "network_config.yaml"
        try:
            if cfg_path.exists():
                with open(cfg_path, "r") as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"加载网络配置失败: {e}")
        return {}

    def get_network_config(self) -> dict:
        """获取网络配置（公开接口）"""
        return self._load_network_config()
