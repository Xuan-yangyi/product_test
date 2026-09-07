"""串口操作封装（适配器模式，封装现有 ops/common_ops.py 的串口操作）"""
import serial
import serial.tools.list_ports
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SerialClient:
    """串口客户端

    封装 pyserial 操作，提供：
    - 串口扫描：scan_ports() -> list[dict]
    - 命令发送：send_cmd(cmd, timeout) -> str
    - 适配现有 ops 模块的串口发送逻辑
    """

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 3.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._ser: Optional[serial.Serial] = None

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def open(self) -> bool:
        """打开串口"""
        try:
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            logger.info(f"串口 {self.port} 已打开")
            return True
        except serial.SerialException as e:
            logger.error(f"打开串口 {self.port} 失败: {e}")
            return False

    def close(self):
        """关闭串口"""
        if self._ser and self._ser.is_open:
            self._ser.close()
            logger.info(f"串口 {self.port} 已关闭")
        self._ser = None

    def send_cmd(self, cmd: str, timeout: float = 30.0, wait_str: str = "/ #") -> str:
        """发送命令并等待响应

        Args:
            cmd: 要发送的命令
            timeout: 超时时间（秒）
            wait_str: 等待的结束标志字符串

        Returns:
            命令输出结果
        """
        if not self.is_open:
            raise RuntimeError(f"串口 {self.port} 未打开")

        self._ser.timeout = timeout
        self._ser.write(f"{cmd}\n".encode())
        time.sleep(0.1)

        output = ""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._ser.in_waiting:
                chunk = self._ser.read(self._ser.in_waiting).decode(errors="ignore")
                output += chunk
                if wait_str in output:
                    break
            time.sleep(0.05)

        return output

    def send_cmd_interactive(self, cmd: str, prompts: dict, timeout: float = 30.0) -> str:
        """发送命令并根据提示自动交互

        prompts: {"prompt_text": "response_text", ...}
        """
        if not self.is_open:
            raise RuntimeError(f"串口 {self.port} 未打开")

        self._ser.timeout = timeout
        self._ser.write(f"{cmd}\n".encode())
        time.sleep(0.1)

        output = ""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._ser.in_waiting:
                chunk = self._ser.read(self._ser.in_waiting).decode(errors="ignore")
                output += chunk
                for prompt, response in prompts.items():
                    if prompt in output and response not in output:
                        self._ser.write(f"{response}\n".encode())
                        time.sleep(0.2)
                        break
                if "/ #" in output:
                    break
            time.sleep(0.05)

        return output

    @staticmethod
    def scan_ports() -> list:
        """扫描可用串口"""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                "port": port.device,
                "description": port.description,
                "hwid": port.hwid,
                "vid": port.vid,
                "pid": port.pid,
                "in_use": False,
            })
        return ports
