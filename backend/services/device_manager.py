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

    def scan_network_devices(self) -> List[Dict]:
        """扫描网络中的设备

        读取 network_config.yaml 中的网段配置，
        扫描在线设备。
        """
        config = self._load_network_config()
        network_segment = config.get("network_segment", "")
        devices = []

        if not network_segment:
            return devices

        # 扫描网段（例如 192.168.1.）
        base_ip = network_segment.rsplit(".", 1)[0]
        for i in range(1, 255):
            ip = f"{base_ip}.{i}"
            if SSHClient.is_ip_alive(ip, timeout=2):
                devices.append({
                    "ip": ip,
                    "hostname": "",
                    "status": "online",
                    "device_type": "",
                })

        return devices

    def batch_scan_ips(self, ips: List[str], timeout: int = 2) -> List[Dict]:
        """批量扫描 IP 地址，返回在线设备列表"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def check_ip(ip: str) -> dict | None:
            if SSHClient.is_ip_alive(ip, timeout=timeout):
                return {"ip": ip, "hostname": "", "status": "online"}
            return None

        devices = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(check_ip, ip): ip for ip in ips}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    devices.append(result)
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
