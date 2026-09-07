"""资源池管理

管理串口资源的并发访问，防止多个测试任务同时使用同一个串口。
使用 asyncio.Lock 实现。
"""
import asyncio
import logging
from typing import Dict, Optional
from ..engine.serial_client import SerialClient

logger = logging.getLogger(__name__)


class ResourcePool:
    """串口资源池

    管理串口资源的分配和释放，确保同一串口不会被多个测试任务同时使用。
    """

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._clients: Dict[str, SerialClient] = {}
        self._in_use: Dict[str, bool] = {}

    async def acquire_serial(self, port: str, baudrate: int = 115200) -> Optional[SerialClient]:
        """获取串口资源

        如果串口已被占用，等待释放。

        Args:
            port: 串口设备路径，如 /dev/ttyUSB0
            baudrate: 波特率

        Returns:
            SerialClient 实例，如果获取失败返回 None
        """
        if port not in self._locks:
            self._locks[port] = asyncio.Lock()

        try:
            acquired = await asyncio.wait_for(
                self._locks[port].acquire(),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.error(f"获取串口 {port} 锁超时")
            return None

        try:
            if not acquired:
                logger.error(f"获取串口 {port} 锁失败")
                return None

            client = SerialClient(port, baudrate)
            if not client.open():
                return None

            self._clients[port] = client
            self._in_use[port] = True
            logger.info(f"串口 {port} 已分配")
            return client
        finally:
            self._locks[port].release()

    def release_serial(self, port: str):
        """释放串口资源"""
        if port in self._clients:
            self._clients[port].close()
            del self._clients[port]
        self._in_use[port] = False
        if port in self._locks:
            try:
                self._locks[port].release()
            except RuntimeError:
                pass  # 锁可能已被释放
        logger.info(f"串口 {port} 已释放")

    def get_available_ports(self) -> list:
        """获取所有可用串口"""
        ports = SerialClient.scan_ports()
        for port_info in ports:
            port_info["in_use"] = self._in_use.get(port_info["port"], False)
        return ports

    def get_usage_status(self) -> dict:
        """获取资源使用状态"""
        total = len(self._locks)
        used = sum(1 for v in self._in_use.values() if v)
        return {
            "total_managed_ports": total,
            "ports_in_use": used,
            "ports_available": total - used,
            "details": {
                port: {"in_use": self._in_use.get(port, False)}
                for port in self._locks
            },
        }
